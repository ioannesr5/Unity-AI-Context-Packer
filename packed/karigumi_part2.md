# 📁 解析結果 (Part 2 续篇)
- **生成日時:** `2026-07-29 14:10:41`

---

### File: `Scripts\Math\PointRansacReorder.cs`
```csharp
﻿using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

/// <summary>
/// RANSACによる対応付け・並べ替え結果を格納するクラス。
/// </summary>
public class RansacReorderResult
{
    /// <summary>
    /// Des[i] に対応する Mea の元座標。
    /// 
    /// 例：
    /// ReorderedMea[0] は Des[0] に対応すると判定された Mea の点。
    /// ReorderedMea[1] は Des[1] に対応すると判定された Mea の点。
    /// 
    /// 対応点が見つからなかった Des[i] には、
    /// new Vector3(float.NaN, float.NaN, float.NaN) が入る。
    /// </summary>
    public Vector3[] ReorderedMea { get; set; }

    /// <summary>
    /// Des[i] に対応する Mea が見つかったかどうか。
    /// true  : 対応点あり
    /// false : 対応点なし
    /// </summary>
    public bool[] Matched { get; set; }

    /// <summary>
    /// 最終的に対応付けできた点数。
    /// RANSACでは、この値が多い変換を優先して採用する。
    /// </summary>
    public int InlierCount { get; set; }

    /// <summary>
    /// 対応点におけるRMS誤差。
    /// RMS = sqrt(誤差二乗和 / 対応点数)
    /// 
    /// InlierCountが同じ場合は、この値が小さい方を良い変換として採用する。
    /// </summary>
    public double RmsError { get; set; }

    /// <summary>
    /// 最終的に採用された回転行列。
    /// この行列は Mea 座標系から Des 座標系へ回転させるためのもの。
    /// </summary>
    public Matrix4x4 Rotation { get; set; }

    /// <summary>
    /// 最終的に採用された並進量。
    /// Mea点を回転させた後、この値を加算して Des 座標系へ移動する。
    /// 
    /// 変換式：
    /// transformed = Rotation * Mea + Translation
    /// </summary>
    public Vector3 Translation { get; set; }

    /// <summary>
    /// Mea側インデックスからDes側インデックスへの対応表。
    /// 
    /// 例：
    /// MeaToDesIndex[5] = 2 の場合、
    /// Mea[5] は Des[2] に対応するという意味。
    /// 
    /// 未対応の場合は -1。
    /// </summary>
    public int[] MeaToDesIndex { get; set; }

    /// <summary>
    /// Des側インデックスからMea側インデックスへの対応表。
    /// 
    /// 例：
    /// DesToMeaIndex[2] = 5 の場合、
    /// Des[2] は Mea[5] に対応するという意味。
    /// 
    /// 未対応の場合は -1。
    /// </summary>
    public int[] DesToMeaIndex { get; set; }
}

/// <summary>
/// Mea点群を、Des点群に対応する順番へ並べ替えるためのクラス。
/// 
/// 前提：
/// ・Mea と Des のスケールは同じ
/// ・座標系は異なる
/// ・回転と平行移動のみ存在する
/// ・点数は一致していなくてもよい
/// ・外れ点が含まれていてもよい
/// 
/// 処理概要：
/// 1. Des側から安定した3点を選ぶ
/// 2. Mea側からランダムに3点を選ぶ
/// 3. 3点対応から Mea → Des の回転Rと並進tを求める
/// 4. 全Mea点を変換し、Des点との距離で対応点数とRMS誤差を評価する
/// 5. 対応点数が多く、RMS誤差が小さい変換を採用する
/// 6. 最終的に Des の順番に合わせて Mea を並べ替える
/// </summary>
public static class PointRansacReorder
{
    /// <summary>
    /// 3点で作る三角形のインデックス情報。
    /// 
    /// I0, I1, I2 は点配列内のインデックス。
    /// Area はその3点で作る三角形の面積。
    /// 
    /// 面積が大きい三角形ほど、回転推定が安定しやすい。
    /// </summary>
    private class TriangleIndex
    {
        public int I0;
        public int I1;
        public int I2;
        public double Area;
    }

    /// <summary>
    /// Mea点とDes点の対応候補。
    /// 
    /// RANSACで求めた変換を使って Mea を Des座標系へ変換した後、
    /// Des点との距離がしきい値以内の場合に対応候補として登録する。
    /// </summary>
    private class PairCandidate
    {
        /// <summary>
        /// Mea側の点インデックス。
        /// </summary>
        public int MeaIndex;

        /// <summary>
        /// Des側の点インデックス。
        /// </summary>
        public int DesIndex;

        /// <summary>
        /// 変換後Mea点とDes点の距離の二乗。
        /// 距離そのものではなく二乗を使うことで、sqrt計算を省略している。
        /// </summary>
        public double Dist2;
    }

    /// <summary>
    /// 1つの変換R,tを評価した結果。
    /// 
    /// RANSAC中で、候補変換ごとにこの結果を作る。
    /// </summary>
    private class EvaluateResult
    {
        /// <summary>
        /// しきい値以内で対応できた点数。
        /// </summary>
        public int InlierCount;

        /// <summary>
        /// 対応点のRMS誤差。
        /// </summary>
        public double RmsError;

        /// <summary>
        /// Mea側インデックス → Des側インデックスの対応表。
        /// 未対応は -1。
        /// </summary>
        public int[] MeaToDesIndex;

        /// <summary>
        /// Des側インデックス → Mea側インデックスの対応表。
        /// 未対応は -1。
        /// </summary>
        public int[] DesToMeaIndex;
    }

    /// <summary>
    /// 3点の対応順を全通り試すための配列。
    /// 
    /// Mea側からランダムに選んだ3点が、
    /// Des側の3点にどの順番で対応するかは不明。
    /// そのため、3点の並び替え 3! = 6 通りをすべて試す。
    /// </summary>
    private static readonly int[][] Permutations3 = new int[][]
    {
        new int[] { 0, 1, 2 },
        new int[] { 0, 2, 1 },
        new int[] { 1, 0, 2 },
        new int[] { 1, 2, 0 },
        new int[] { 2, 0, 1 },
        new int[] { 2, 1, 0 },
    };

    /// <summary>
    /// RANSACを使って、Mea点群をDes点群の順番へ並べ替える。
    /// 
    /// 出力される ReorderedMea は Des と同じ長さ。
    /// ReorderedMea[i] には Des[i] に対応すると判断された Mea点が入る。
    /// 
    /// 点数が異なる場合：
    /// ・Desに対応するMeaがない場合は、その要素はNaNになる
    /// ・Meaに余分な点がある場合は、どのDesにも対応しない
    /// </summary>
    /// <param name="mea">
    /// 入力点群。測定点側。
    /// この点群をDesに合うように並べ替える。
    /// </param>
    /// <param name="des">
    /// 目標点群。設計点、基準点側。
    /// 出力の順番はこのDesの順番に合わせる。
    /// </param>
    /// <param name="matchThreshold">
    /// 対応点と判定する最大距離。
    /// 
    /// 例：
    /// 座標単位がmmの場合、matchThreshold = 5.0 なら、
    /// 変換後のMea点とDes点の距離が5mm以内なら対応候補とする。
    /// </param>
    /// <param name="maxIterations">
    /// RANSACの試行回数。
    /// 大きくすると正解に当たる確率は上がるが、処理時間も長くなる。
    /// </param>
    /// <param name="desTriangleCandidateCount">
    /// Des側で使用する三角形候補数。
    /// 面積の大きい三角形から上位N個を候補として使う。
    /// </param>
    /// <param name="randomSeed">
    /// 乱数シード。
    /// 同じ値にすると毎回同じRANSAC結果になり、デバッグしやすい。
    /// </param>
    /// <returns>
    /// 並べ替え結果、対応点数、RMS誤差、回転行列、並進量などを含む結果。
    /// </returns>
    /// <summary>
    /// RANSACを使って、Mea点群をDes点群の順番へ並べ替える。
    /// </summary>
    public static RansacReorderResult ReorderMeaToDesByRansac(
        Vector3[] mea,
        Vector3[] des,
        double matchThreshold = 50.0,
        int maxIterations = 5000,
        int desTriangleCandidateCount = 20,
        int randomSeed = 0)
    {
        // ------------------------------
        // 入力チェック (输入数据检查)
        // ------------------------------

        if (mea == null) throw new ArgumentNullException(nameof(mea));
        if (des == null) throw new ArgumentNullException(nameof(des));

        // 3点から回転・並進を求めるため、最低3点必要。
        if (mea.Length < 3) throw new ArgumentException("Meaの点数は3点以上必要です。");
        if (des.Length < 3) throw new ArgumentException("Desの点数は3点以上必要です。");

        // しきい値が0以下だと対応判定ができない。
        if (matchThreshold <= 0) throw new ArgumentException("matchThresholdは正の値にしてください。");

        // ==========================================
        // [CRITICAL FIX] 乱数シードの動的生成 (动态生成随机数种子)
        // randomSeed が 0 の場合（デフォルト値）、システムのTickCountを使用して
        // 毎回異なるシード値を生成し、RANSACが同じ局所解に陥る無限ループを完全に防ぎます。
        // ==========================================
        int actualSeed = (randomSeed == 0) ? System.Environment.TickCount : randomSeed;
        System.Random rand = new System.Random(actualSeed);

        // ------------------------------
        // Des側の3点候補を作成
        // ------------------------------
        // Des側は基準になる点群なので、座標変換の基準3点として使う。
        List<TriangleIndex> desTriangles = GetStableTriangles(des, desTriangleCandidateCount);

        if (desTriangles.Count == 0)
        {
            throw new Exception("Des側で有効な3点三角形を作れません。点が一直線に近い可能性があります。");
        }

        // ------------------------------
        // RANSACで最良だった変換を保持する変数
        // ------------------------------

        Matrix4x4 bestR = Matrix4x4.identity;
        Vector3 bestT = Vector3.zero;
        EvaluateResult bestEval = null;

        // 距離比較は毎回sqrtすると遅いため、しきい値も二乗にして比較する。
        double threshold2 = matchThreshold * matchThreshold;

        // ------------------------------
        // RANSAC本体
        // ------------------------------
        //
        // 1回の試行では、
        // ・Des側から安定三角形を1つ選ぶ
        // ・Mea側からランダムに3点選ぶ
        // ・対応順6通りを試す
        // ・それぞれのR,tを全点で評価する
        //
        // これをmaxIterations回繰り返し、
        // 最も対応点数が多く、誤差が小さいものを採用する。
        for (int iter = 0; iter < maxIterations; iter++)
        {
            // Des側は面積の大きい三角形候補からランダムに1つ選択。
            // 常に最大面積だけを使うと、その3点に外れ点が含まれている場合に失敗しやすいため、
            // 上位候補からランダムに選ぶ。
            TriangleIndex desTri = desTriangles[rand.Next(desTriangles.Count)];

            // Mea側は対応が不明なので、ランダムに3点を選ぶ。
            int[] meaIdx = GetRandom3Indices(mea.Length, rand);

            // Mea側3点がDes側3点にどの順番で対応するか不明なので、
            // 6通りすべて試す。
            foreach (int[] perm in Permutations3)
            {
                int m0 = meaIdx[perm[0]];
                int m1 = meaIdx[perm[1]];
                int m2 = meaIdx[perm[2]];

                Matrix4x4 R;
                Vector3 t;

                try
                {
                    // 既存の3点変換計算メソッドを呼び出す。
                    //
                    // 入力：
                    //   mea[m0], mea[m1], mea[m2]  → 変換元の3点
                    //   des[desTri.I0], des[desTri.I1], des[desTri.I2] → 変換先の3点
                    //
                    // 出力：
                    //   R : 回転行列
                    //   t : 並進量
                    //
                    // 前提：
                    //   Rは回転のみ
                    //   tは別の並進量
                    Compute3(
                        mea[m0], mea[m1], mea[m2],
                        des[desTri.I0], des[desTri.I1], des[desTri.I2],
                        out R, out t);
                }
                catch
                {
                    // 3点が不安定な場合や、Compute3内部で例外が出た場合は、
                    // この候補変換を捨てて次へ進む。
                    continue;
                }

                // RまたはtにNaN/Infinityが含まれていれば無効。
                if (!IsValidMatrix(R) || !IsValidVector(t))
                {
                    continue;
                }

                // 求めたR,tで全Mea点をDes座標系へ変換し、
                // Des点とどれだけ対応するかを評価する。
                EvaluateResult eval = EvaluateTransform(
                    mea,
                    des,
                    R,
                    t,
                    threshold2);

                // ------------------------------
                // 最良解の更新判定
                // ------------------------------
                //
                // 優先順位：
                // 1. 対応点数が多い方
                // 2. 対応点数が同じならRMS誤差が小さい方
                if (bestEval == null ||
                    eval.InlierCount > bestEval.InlierCount ||
                    (eval.InlierCount == bestEval.InlierCount && eval.RmsError < bestEval.RmsError))
                {
                    bestEval = eval;
                    bestR = R;
                    bestT = t;
                }
            }
        }

        if (bestEval == null)
        {
            throw new Exception("有効な変換が見つかりませんでした。matchThresholdを大きくするか、点群を確認してください。");
        }

        // ------------------------------
        // 最良変換の対応表を使って、Des順にMeaを並べ替える
        // ------------------------------

        // 出力配列はDesと同じ長さにする。
        // ReorderedMea[i] が Des[i] に対応するMea点。
        Vector3[] reordered = new Vector3[des.Length];

        // Matched[i] は Des[i] に対応点があったかどうか。
        bool[] matched = new bool[des.Length];

        // 初期値として、未対応点はNaNにしておく。
        // 後で見たときに「未対応」と分かりやすくするため。
        for (int i = 0; i < des.Length; i++)
        {
            reordered[i] = new Vector3(float.NaN, float.NaN, float.NaN);
            matched[i] = false;
        }

        // DesToMeaIndex を使って、Des順のMea配列を作る。
        for (int desIndex = 0; desIndex < des.Length; desIndex++)
        {
            int meaIndex = bestEval.DesToMeaIndex[desIndex];

            if (meaIndex >= 0)
            {
                reordered[desIndex] = mea[meaIndex];
                matched[desIndex] = true;
            }
        }

        // 結果を返す。
        return new RansacReorderResult
        {
            ReorderedMea = reordered,
            Matched = matched,
            InlierCount = bestEval.InlierCount,
            RmsError = bestEval.RmsError,
            Rotation = bestR,
            Translation = bestT,
            MeaToDesIndex = bestEval.MeaToDesIndex,
            DesToMeaIndex = bestEval.DesToMeaIndex
        };
    }

    /// <summary>
    /// 点群から、三角形面積が大きい3点組を選び出す。
    /// 
    /// なぜ面積を見るか：
    /// ・3点が近いと、少しのノイズで回転推定が大きく変わる
    /// ・3点が一直線に近いと、3次元姿勢が安定しない
    /// ・広がりのある3点を使うと、変換推定が安定しやすい
    /// 
    /// このメソッドでは、全3点組み合わせを調べ、
    /// 三角形面積が大きい順に maxCount 個だけ返す。
    /// </summary>
    private static List<TriangleIndex> GetStableTriangles(Vector3[] points, int maxCount)
    {
        List<TriangleIndex> list = new List<TriangleIndex>();

        // 全ての3点組み合わせを作る。
        // i < j < k とすることで、同じ組み合わせの重複を避ける。
        for (int i = 0; i < points.Length - 2; i++)
        {
            for (int j = i + 1; j < points.Length - 1; j++)
            {
                for (int k = j + 1; k < points.Length; k++)
                {
                    double area = TriangleArea(points[i], points[j], points[k]);

                    // 面積がほぼ0の三角形は使わない。
                    // これは3点がほぼ一直線、または重なっている可能性があるため。
                    if (area > 1.0e-9)
                    {
                        list.Add(new TriangleIndex
                        {
                            I0 = i,
                            I1 = j,
                            I2 = k,
                            Area = area
                        });
                    }
                }
            }
        }

        // 面積の大きい順に並べ、上位maxCount個だけ返す。
        return list
            .OrderByDescending(x => x.Area)
            .Take(maxCount)
            .ToList();
    }

    /// <summary>
    /// 3点で作る三角形の面積を計算する。
    /// 
    /// 三角形面積 = |(b - a) × (c - a)| / 2
    /// 
    /// 外積の大きさは、2つのベクトルが作る平行四辺形の面積。
    /// 三角形はその半分。
    /// </summary>
    private static double TriangleArea(Vector3 a, Vector3 b, Vector3 c)
    {
        Vector3 ab = b - a;
        Vector3 ac = c - a;
        Vector3 cross = Vector3.Cross(ab, ac);

        return 0.5 * cross.magnitude;
    }

    /// <summary>
    /// 0 ～ count-1 の中から、重複しない3つのインデックスをランダムに選ぶ。
    /// 
    /// Mea側の対応点は不明なので、RANSACではランダムに3点を選んで試す。
    /// </summary>
    private static int[] GetRandom3Indices(int count, System.Random rand)
    {
        int a = rand.Next(count);
        int b;
        int c;

        do
        {
            b = rand.Next(count);
        }
        while (b == a);

        do
        {
            c = rand.Next(count);
        }
        while (c == a || c == b);

        return new int[] { a, b, c };
    }

    /// <summary>
    /// 指定したR,tでMea点群をDes座標系へ変換し、
    /// Des点群との対応点数とRMS誤差を評価する。
    /// 
    /// 処理内容：
    /// 1. 各Mea点を R * p + t で変換する
    /// 2. 各Des点との距離を計算する
    /// 3. 距離がしきい値以内の組み合わせを対応候補にする
    /// 4. 距離が短い順に対応を採用する
    /// 5. 1つのMea点、1つのDes点が複数対応しないようにする
    /// 6. 対応点数とRMS誤差を返す
    /// </summary>
    private static EvaluateResult EvaluateTransform(
        Vector3[] mea,
        Vector3[] des,
        Matrix4x4 R,
        Vector3 t,
        double threshold2)
    {
        List<PairCandidate> candidates = new List<PairCandidate>();

        // ------------------------------
        // 全Mea点と全Des点の距離を計算
        // ------------------------------
        for (int mi = 0; mi < mea.Length; mi++)
        {
            // Mea点をDes座標系へ変換する。
            // 前提：
            // Rは回転のみ、tは並進量。
            Vector3 transformed = TransformPoint(mea[mi], R, t);

            for (int di = 0; di < des.Length; di++)
            {
                // 変換後Mea点とDes点の距離二乗を計算。
                double d2 = DistanceSquared(transformed, des[di]);

                // しきい値以内なら対応候補として登録。
                if (d2 <= threshold2)
                {
                    candidates.Add(new PairCandidate
                    {
                        MeaIndex = mi,
                        DesIndex = di,
                        Dist2 = d2
                    });
                }
            }
        }

        // ------------------------------
        // 距離が短い順に並べる
        // ------------------------------
        //
        // 近い点ほど対応として信頼しやすいので、
        // 小さい誤差の候補から採用していく。
        candidates.Sort((a, b) => a.Dist2.CompareTo(b.Dist2));

        // ------------------------------
        // 対応表を初期化
        // ------------------------------

        int[] meaToDes = new int[mea.Length];
        int[] desToMea = new int[des.Length];

        // -1 は未対応を表す。
        for (int i = 0; i < meaToDes.Length; i++)
        {
            meaToDes[i] = -1;
        }

        for (int i = 0; i < desToMea.Length; i++)
        {
            desToMea[i] = -1;
        }

        double sum2 = 0.0;
        int count = 0;

        // ------------------------------
        // 1対1対応になるように対応候補を採用
        // ------------------------------
        //
        // 例えば、
        // ・1つのMea点が複数のDes点に対応する
        // ・1つのDes点に複数のMea点が対応する
        //
        // という状態は避けたい。
        //
        // そのため、距離が短い候補から順に見て、
        // まだ未使用のMea点・Des点同士だけを対応として採用する。
        foreach (PairCandidate p in candidates)
        {
            // このMea点がすでに別のDes点に対応済みなら使わない。
            if (meaToDes[p.MeaIndex] >= 0) continue;

            // このDes点がすでに別のMea点に対応済みなら使わない。
            if (desToMea[p.DesIndex] >= 0) continue;

            // 対応として採用。
            meaToDes[p.MeaIndex] = p.DesIndex;
            desToMea[p.DesIndex] = p.MeaIndex;

            // RMS計算用に距離二乗を加算。
            sum2 += p.Dist2;
            count++;
        }

        // RMS誤差を計算。
        // 対応点が0の場合は、最悪値として double.MaxValue にする。
        double rms = count > 0 ? Math.Sqrt(sum2 / count) : double.MaxValue;

        return new EvaluateResult
        {
            InlierCount = count,
            RmsError = rms,
            MeaToDesIndex = meaToDes,
            DesToMeaIndex = desToMea
        };
    }

    /// <summary>
    /// Unity用の点変換。
    /// 
    /// 前提：
    /// ・Rは回転のみのMatrix4x4
    /// ・tは別で返される並進量
    /// 
    /// 変換式：
    /// p' = R * p + t
    /// 
    /// 注意：
    /// Rの中にすでに平行移動成分が入っている場合は、
    /// + t をすると平行移動が二重にかかる。
    /// 今回は「Rは回転のみ、tは別」という前提なので、この実装でよい。
    /// </summary>
    private static Vector3 TransformPoint(Vector3 p, Matrix4x4 R, Vector3 t)
    {
        return R.MultiplyPoint3x4(p) + t;
    }

    /// <summary>
    /// 2点間距離の二乗を計算する。
    /// 
    /// 距離そのものは sqrt(dx^2 + dy^2 + dz^2) だが、
    /// しきい値比較では平方根を取らなくても大小比較できる。
    /// そのため、処理速度のために距離二乗を使う。
    /// </summary>
    private static double DistanceSquared(Vector3 a, Vector3 b)
    {
        double dx = a.x - b.x;
        double dy = a.y - b.y;
        double dz = a.z - b.z;

        return dx * dx + dy * dy + dz * dz;
    }

    /// <summary>
    /// Vector3が有効な数値か確認する。
    /// NaNやInfinityが含まれている場合はfalse。
    /// </summary>
    private static bool IsValidVector(Vector3 v)
    {
        return IsFinite(v.x) && IsFinite(v.y) && IsFinite(v.z);
    }

    /// <summary>
    /// Matrix4x4が有効な数値か確認する。
    /// NaNやInfinityが含まれている場合はfalse。
    /// 
    /// UnityのMatrix4x4は m00, m01, ..., m33 で各要素にアクセスする。
    /// </summary>
    private static bool IsValidMatrix(Matrix4x4 m)
    {
        return
            IsFinite(m.m00) && IsFinite(m.m01) && IsFinite(m.m02) && IsFinite(m.m03) &&
            IsFinite(m.m10) && IsFinite(m.m11) && IsFinite(m.m12) && IsFinite(m.m13) &&
            IsFinite(m.m20) && IsFinite(m.m21) && IsFinite(m.m22) && IsFinite(m.m23) &&
            IsFinite(m.m30) && IsFinite(m.m31) && IsFinite(m.m32) && IsFinite(m.m33);
    }

    /// <summary>
    /// float値が通常の有限値か確認する。
    /// </summary>
    private static bool IsFinite(float v)
    {
        return !float.IsNaN(v) && !float.IsInfinity(v);
    }

    /// <summary>
    /// 既存の3点変換計算メソッドを呼び出すためのラッパー。
    /// 
    /// このメソッドを用意しておくことで、
    /// RANSAC側のコードは Compute3(...) を呼ぶだけで済む。
    /// 
    /// 前提：
    /// RigidTransformUnity.Compute3() は、
    /// ・Mea側3点 p1, p2, p3
    /// ・Des側3点 q1, q2, q3
    /// から、
    /// ・Mea → Des の回転行列 R
    /// ・Mea → Des の並進量 t
    /// を求める。
    /// 
    /// 今回の前提：
    /// ・Rは回転のみ
    /// ・tは別で返る並進量
    /// </summary>
    public static void Compute3(
        Vector3 p1, Vector3 p2, Vector3 p3,
        Vector3 q1, Vector3 q2, Vector3 q3,
        out Matrix4x4 R, out Vector3 t)
    {
        RigidTransformUnity.Compute3(
            p1, p2, p3,
            q1, q2, q3,
            out R, out t);
    }
}
```

### File: `Scripts\Math\RigidTransformUnity.cs`
```csharp
using UnityEngine;
using MathNet.Numerics.LinearAlgebra;

public static class RigidTransformUnity
{
    // Rodrigues ��]�iUnity�Łj
    private static Quaternion Rodrigues(Vector3 axis, float angleRad)
    {
        if (axis.sqrMagnitude < 1e-12f)
            return Quaternion.identity;

        return Quaternion.AngleAxis(angleRad * Mathf.Rad2Deg, axis.normalized);
    }

    // ============================================================
    // 1. Compute3 : 3�_�Ή��E�X�P�[���Ȃ��i�����A���S���Y���j
    // ============================================================
    public static void Compute3(
        Vector3 p1, Vector3 p2, Vector3 p3,
        Vector3 q1, Vector3 q2, Vector3 q3,
        out Matrix4x4 R, out Vector3 t)
    {
        Vector3 a = (p2 - p1).normalized;
        Vector3 b = (q2 - q1).normalized;

        Vector3 np = Vector3.Cross(p2 - p1, p3 - p1).normalized;
        Vector3 nq = Vector3.Cross(q2 - q1, q3 - q1).normalized;

        Vector3 k = Vector3.Cross(np, nq);
        float s = k.magnitude;
        float c = Vector3.Dot(np, nq);

        Quaternion qn = Quaternion.identity;

        if (s > 1e-8f)
        {
            float alpha = Mathf.Atan2(s, c);
            qn = Rodrigues(k, alpha);
        }
        else if (c < 0)
        {
            Vector3 axis = (p2 - p1).normalized;
            qn = Rodrigues(axis, Mathf.PI);
        }

        Vector3 aPrime = qn * a;
        aPrime = (aPrime - Vector3.Dot(aPrime, nq) * nq).normalized;

        float phi = Mathf.Atan2(
            Vector3.Dot(nq, Vector3.Cross(aPrime, b)),
            Vector3.Dot(aPrime, b)
        );

        Quaternion qPlane = Rodrigues(nq, phi);

        Quaternion qFinal = qPlane * qn;
        R = Matrix4x4.Rotate(qFinal);

        Vector3 p1Rot = R.MultiplyPoint3x4(p1);
        t = q1 - p1Rot;
    }

    // ============================================================
    // 2. ComputeKabschSVD : N�_�Ή��E�X�P�[���Ȃ��i�ŏ����j
    // ============================================================
    public static void ComputeKabschSVD(
        Vector3[] P, Vector3[] Q,
        out Matrix4x4 R, out Vector3 t)
    {
        int n = P.Length;

        // �d�S
        Vector3 pCentroid = Vector3.zero;
        Vector3 qCentroid = Vector3.zero;

        for (int i = 0; i < n; i++)
        {
            pCentroid += P[i];
            qCentroid += Q[i];
        }
        pCentroid /= n;
        qCentroid /= n;

        // �����U�s�� H�i3x3�j
        var H = Matrix<double>.Build.Dense(3, 3);

        for (int i = 0; i < n; i++)
        {
            Vector3 p = P[i] - pCentroid;
            Vector3 q = Q[i] - qCentroid;

            H[0, 0] += p.x * q.x; H[0, 1] += p.x * q.y; H[0, 2] += p.x * q.z;
            H[1, 0] += p.y * q.x; H[1, 1] += p.y * q.y; H[1, 2] += p.y * q.z;
            H[2, 0] += p.z * q.x; H[2, 1] += p.z * q.y; H[2, 2] += p.z * q.z;
        }

        // SVD
        var svd = H.Svd();
        var U = svd.U;
        var Vt = svd.VT;

        // ��]�s�� R = V * U^T
        var Rmat = Vt.TransposeThisAndMultiply(U.Transpose());

        // Unity Matrix4x4 �ɕϊ�
        R = Matrix4x4.identity;
        R.m00 = (float)Rmat[0, 0]; R.m01 = (float)Rmat[0, 1]; R.m02 = (float)Rmat[0, 2];
        R.m10 = (float)Rmat[1, 0]; R.m11 = (float)Rmat[1, 1]; R.m12 = (float)Rmat[1, 2];
        R.m20 = (float)Rmat[2, 0]; R.m21 = (float)Rmat[2, 1]; R.m22 = (float)Rmat[2, 2];

        // ���i
        t = qCentroid - R.MultiplyPoint3x4(pCentroid);
    }

    // ============================================================
    // 3. ComputeUmeyamaSVD : N�_�Ή��E�X�P�[������i�ŏ����j
    // ============================================================
    public static void ComputeUmeyamaSVD(
        Vector3[] P, Vector3[] Q,
        out Matrix4x4 R, out Vector3 t, out float scale)
    {
        int n = P.Length;

        // �d�S
        Vector3 pCentroid = Vector3.zero;
        Vector3 qCentroid = Vector3.zero;

        for (int i = 0; i < n; i++)
        {
            pCentroid += P[i];
            qCentroid += Q[i];
        }
        pCentroid /= n;
        qCentroid /= n;

        // �����U�s�� C�i3x3�j
        var C = Matrix<double>.Build.Dense(3, 3);

        for (int i = 0; i < n; i++)
        {
            Vector3 p = P[i] - pCentroid;
            Vector3 q = Q[i] - qCentroid;

            C[0, 0] += p.x * q.x; C[0, 1] += p.x * q.y; C[0, 2] += p.x * q.z;
            C[1, 0] += p.y * q.x; C[1, 1] += p.y * q.y; C[1, 2] += p.y * q.z;
            C[2, 0] += p.z * q.x; C[2, 1] += p.z * q.y; C[2, 2] += p.z * q.z;
        }
        C /= n;

        // SVD
        var svd = C.Svd();
        var U = svd.U;
        var Vt = svd.VT;

        // ��]
        var Rmat = Vt.TransposeThisAndMultiply(U.Transpose());

        // Unity Matrix4x4 �ɕϊ�
        R = Matrix4x4.identity;
        R.m00 = (float)Rmat[0, 0]; R.m01 = (float)Rmat[0, 1]; R.m02 = (float)Rmat[0, 2];
        R.m10 = (float)Rmat[1, 0]; R.m11 = (float)Rmat[1, 1]; R.m12 = (float)Rmat[1, 2];
        R.m20 = (float)Rmat[2, 0]; R.m21 = (float)Rmat[2, 1]; R.m22 = (float)Rmat[2, 2];

        // �X�P�[��
        float sigmaP = 0f;
        for (int i = 0; i < n; i++)
        {
            Vector3 p = P[i] - pCentroid;
            sigmaP += Vector3.Dot(p, p);
        }
        sigmaP /= n;

        scale = 0f;
        for (int i = 0; i < n; i++)
        {
            Vector3 p = P[i] - pCentroid;
            Vector3 q = Q[i] - qCentroid;
            scale += Vector3.Dot(q, R.MultiplyVector(p));
        }
        scale /= (n * sigmaP);

        // ���i
        t = qCentroid - scale * R.MultiplyPoint3x4(pCentroid);
    }
    // ============================================================
    // 4. Compute3many : 3�_�Ή��E�X�P�[���Ȃ��i�����f�[�^����I���j
    // ============================================================

    public static bool Compute3FromMany(
        Vector3[] P, Vector3[] Q,
        int trials,
        out Matrix4x4 bestR, out Vector3 bestT)
    {
        bestR = Matrix4x4.identity;
        bestT = Vector3.zero;

        if (P == null || Q == null || P.Length != Q.Length || P.Length < 3)
        {
            Debug.LogWarning("Compute3FromMany: ���͓_�����s���ł��B");
            return false;
        }

        int n = P.Length;
        float bestError = float.MaxValue;
        bool found = false;
        float eps = 1e-6f;

        for (int iter = 0; iter < trials; iter++)
        {
            // �����_����3�_�C���f�b�N�X��I�ԁi�S�ĈقȂ�悤�Ɂj
            int i1 = Random.Range(0, n);
            int i2, i3;
            do { i2 = Random.Range(0, n); } while (i2 == i1);
            do { i3 = Random.Range(0, n); } while (i3 == i1 || i3 == i2);

            Vector3 p1 = P[i1];
            Vector3 p2 = P[i2];
            Vector3 p3 = P[i3];

            Vector3 q1 = Q[i1];
            Vector3 q2 = Q[i2];
            Vector3 q3 = Q[i3];

            // �����`�F�b�N�iP���EQ���j
            Vector3 v1 = p2 - p1;
            Vector3 v2 = p3 - p1;
            Vector3 w1 = q2 - q1;
            Vector3 w2 = q3 - q1;

            if (Vector3.Cross(v1, v2).sqrMagnitude < eps) continue;
            if (Vector3.Cross(w1, w2).sqrMagnitude < eps) continue;

            // 3�_�� Compute3 ��K�p
            Matrix4x4 R;
            Vector3 t;
            Compute3(p1, p2, p3, q1, q2, q3, out R, out t);

            // �S�_�ɑ΂��� RMSE ���v�Z
            float sumSq = 0f;
            for (int i = 0; i < n; i++)
            {
                Vector3 pTrans = R.MultiplyPoint3x4(P[i]) + t;
                Vector3 diff = pTrans - Q[i];
                sumSq += diff.sqrMagnitude;
            }
            float rmse = Mathf.Sqrt(sumSq / n);

            if (rmse < bestError)
            {
                bestError = rmse;
                bestR = R;
                bestT = t;
                found = true;
            }
        }

        if (!found)
        {
            Debug.LogWarning("Compute3FromMany: �L����3�_�g��������܂���ł����B");
            bestR = Matrix4x4.identity;
            bestT = Vector3.zero;
            return false;
        }

        Debug.Log($"Compute3FromMany: best RMSE = {bestError}");
        return true;
    }

    // ============================================================
    // �� �ǉ��@�FR, t, scale �œ_�Q��ϊ�
    // ============================================================
    public static Vector3[] TransformPoints(
        Vector3[] P, Matrix4x4 R, Vector3 t, float scale = 1f)
    {
        Vector3[] result = new Vector3[P.Length];
        for (int i = 0; i < P.Length; i++)
            result[i] = scale * R.MultiplyPoint3x4(P[i]) + t;
        return result;
    }

    // ============================================================
    // �� �ǉ��A�F�덷 & RMSE ���v�Z
    // ============================================================
    public static float[] ComputeErrors(
        Vector3[] Ptrans, Vector3[] Q, out float rmse)
    {
        int n = Ptrans.Length;
        float[] errors = new float[n];
        float sumSq = 0f;

        for (int i = 0; i < n; i++)
        {
            float e = Vector3.Distance(Ptrans[i], Q[i]);
            errors[i] = e;
            sumSq += e * e;
        }

        rmse = Mathf.Sqrt(sumSq / n);
        return errors;
    }

    // ============================================================
    // �� �ǉ��B�F�ꊇ�]���p�i�ł��֗��j
    // ============================================================
    public static Vector3[] EvaluateTransform(
        Vector3[] P, Vector3[] Q,
        Matrix4x4 R, Vector3 t,
        out float[] errors, out float rmse,
        float scale = 1f)
    {
        Vector3[] Ptrans = TransformPoints(P, R, t, scale);
        errors = ComputeErrors(Ptrans, Q, out rmse);
        return Ptrans;
    }

}







```

### File: `Scripts\Math\RigitdransformTest.cs`
```csharp
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
//using static TMPro.SpriteAssetUtilities.TexturePacker_JsonArray;
#if UNITY_EDITOR
using UnityEditor;
#endif

public class RigidTransformTest : MonoBehaviour
{
    // Start is called before the first frame update
    void Start()
    {
        Debug.Log("=== RigidTransform Test ===");

        // StreamingAssets ����ǂݍ���
        string pathP = Path.Combine(Application.streamingAssetsPath, "xb2.txt");
        string pathQ = Path.Combine(Application.streamingAssetsPath, "xd2.txt");

        Vector3[] P = LoadPoints(pathP);
        Vector3[] Q = LoadPoints(pathQ);

        Debug.Log($"Loaded P: {P.Length} points");
        Debug.Log($"Loaded Q: {Q.Length} points");


        // ---------------------------------------------------------
        // matching
        // ---------------------------------------------------------

        RansacReorderResult result =
            PointRansacReorder.ReorderMeaToDesByRansac(
                P,  // Measured
                Q,  // Design
                matchThreshold: 50.0,               // �Ή��_�Ɣ��肷��ő勗��
                maxIterations: 10000,               // RANSAC�̎��s��
                desTriangleCandidateCount: 10,      // Des���Ŏg�p����O�p�`��␔�B�ʐς̑傫���O�p�`������N�����Ƃ��Ďg���B
                randomSeed: 0);                     // �����V�[�h�B�����l�ɂ���Ɩ��񓯂�RANSAC���ʂɂȂ�A�f�o�b�O���₷���B

        Debug.Log("****************************************");
        Debug.Log("************* �Ή��t������ *************");
        Debug.Log("�Ή��_�� = " + result.InlierCount);
        Debug.Log("RMS�덷 = " + result.RmsError);

        List<int> unmatchedList = new List<int>();
        for (int i = 0; i < result.ReorderedMea.Length; i++)
        {
            if (result.Matched[i])
            {
                Vector3 originalMea = result.ReorderedMea[i];
                Vector3 transformedMea =
                    result.Rotation.MultiplyPoint3x4(originalMea) + result.Translation;     // ���W�ϊ�
                float distance = Vector3.Distance(Q[i], transformedMea);    // 2�_�ԋ���
                Debug.Log("Design[" + i + "] - Measured[" + result.DesToMeaIndex[i] + "] = " + transformedMea + ", dist = " + distance);
            }
            else
            {
                //Debug.Log("Des[" + i + "] �͖��Ή�");
                unmatchedList.Add(i);
            }
        }
        if (unmatchedList.Count > 0)
        {
            string msg = "There are unsupported design values.\n\n";

            foreach (int index in unmatchedList)
            {
                msg += "Design[" + index + "] is not supported.\n";
            }

#if UNITY_EDITOR
            EditorUtility.DisplayDialog("���Ή��_", msg, "OK");
#else
    Debug.Log(msg);
#endif
//            return;
        }

        // �}�b�`���O���ʎ擾
        List<Vector3> p_list = new List<Vector3>();
        List<Vector3> q_list = new List<Vector3>();
        for (int i = 0; i < result.ReorderedMea.Length; i++)
        {
            if (result.Matched[i])
            {
                p_list.Add(result.ReorderedMea[i]); // �v���l�B���W�ϊ��O�̒l
                q_list.Add(Q[i]);   // �v��l
            }
        }
        Vector3[] P_match = p_list.ToArray();
        Vector3[] Q_match = q_list.ToArray();


        //// ---------------------------------------------------------
        //// Compute3FromMany�i�����_ �� �œK3�_�j
        //// ---------------------------------------------------------

        //UnityEngine.Matrix4x4 R3m;
        //Vector3 t3m;

        //bool ok3m = RigidTransformUnity.Compute3FromMany(P_match, Q, 50, out R3m, out t3m);

        //if (ok3m)
        //{
        //    Debug.Log("Compute3FromMany Rotation (deg): " + R3m.rotation.eulerAngles);
        //    Debug.Log("Compute3FromMany Translation: " + t3m);
        //}
        //else
        //{
        //    Debug.LogWarning("Compute3FromMany: ����Ɏ��s���܂����B");
        //}


        //float[] errors;
        //float rmse;
        //Vector3[] Pk = RigidTransformUnity.EvaluateTransform(
        //    P_match, Q, R3m, t3m,
        //    out errors, out rmse
        //);

        //Debug.Log($"Compute3FromMany RMSE = {rmse}");
        //for (int i = 0; i < errors.Length; i++)
        //    Debug.Log($"P'[{i}] = {Pk[i]}, Q[{i}] = {Q[i]}, error = {errors[i]}");


        // ---------------------------------------------------------
        // Kabsch�iSVD�j
        // ---------------------------------------------------------

        Debug.Log("****************************************");
        Debug.Log("*********** Kabsch�iSVD�j���� **********");
        float[] errors;
        float rmse;
        Matrix4x4 RK;
        Vector3 tK;
        RigidTransformUnity.ComputeKabschSVD(P_match, Q_match, out RK, out tK);
        Debug.Log("Kabsch Rotation (deg): " + RK.rotation.eulerAngles);
        Debug.Log("Kabsch Translation: " + tK);

        Vector3[] Pk = RigidTransformUnity.EvaluateTransform(P_match, Q_match, RK, tK, out errors, out rmse);
        Debug.Log($"Kabsch RMSE = {rmse}");
        for (int i = 0; i < errors.Length; i++)
            Debug.Log($"P'[{i}] = {Pk[i]}, Q[{i}] = {Q[i]}, error = {errors[i]}");




        // ---------------------------------------------------------
        // �X����e�X�g
        // ---------------------------------------------------------


        //float[] errors;
        //float rmse;

        //// ---------------------------------------------------------
        //// 0. Compute3FromMany�i�����_ �� �œK3�_�j
        //// ---------------------------------------------------------
        //UnityEngine.Matrix4x4 R3m;
        //Vector3 t3m;

        //bool ok3m = RigidTransformUnity.Compute3FromMany(P, Q, 50, out R3m, out t3m);

        //if (ok3m)
        //{
        //    Debug.Log("Compute3FromMany Rotation (deg): " + R3m.rotation.eulerAngles);
        //    Debug.Log("Compute3FromMany Translation: " + t3m);
        //}
        //else
        //{
        //    Debug.LogWarning("Compute3FromMany: ����Ɏ��s���܂����B");
        //}


        //Vector3[] Pk = RigidTransformUnity.EvaluateTransform(
        //    P, Q, R3m, t3m,
        //    out errors, out rmse
        //);

        //Debug.Log($"Compute3FromMany RMSE = {rmse}");
        //for(int i = 0;i< errors.Length;i++) 
        //    Debug.Log($"P'[{i}] = {Pk[i]}, Q[{i}] = {Q[i]}, error = {errors[i]}");



        //// ---------------------------------------------------------
        //// 1. Compute3�i3�_�@�F�擪3�_�j
        //// ---------------------------------------------------------
        //Matrix4x4 R3;
        //Vector3 t3;
        //RigidTransformUnity.Compute3(P[0], P[1], P[2], Q[0], Q[1], Q[2], out R3, out t3);
        //Debug.Log("Compute3 Rotation (deg): " + R3.rotation.eulerAngles);
        //Debug.Log("Compute3 Translation: " + t3);

        //Pk = RigidTransformUnity.EvaluateTransform(P, Q, R3, t3,out errors, out rmse);
        //Debug.Log($"Compute3 RMSE = {rmse}");
        //for (int i = 0; i < errors.Length; i++)
        //    Debug.Log($"P'[{i}] = {Pk[i]}, Q[{i}] = {Q[i]}, error = {errors[i]}");


        //// ---------------------------------------------------------
        //// 2. Kabsch�iSVD�j
        //// ---------------------------------------------------------
        //Matrix4x4 RK;
        //Vector3 tK;
        //RigidTransformUnity.ComputeKabschSVD(P, Q, out RK, out tK);
        //Debug.Log("Kabsch Rotation (deg): " + RK.rotation.eulerAngles);
        //Debug.Log("Kabsch Translation: " + tK);

        //Pk = RigidTransformUnity.EvaluateTransform(P, Q, RK, tK, out errors, out rmse);
        //Debug.Log($"Kabsch RMSE = {rmse}");
        //for (int i = 0; i < errors.Length; i++)
        //    Debug.Log($"P'[{i}] = {Pk[i]}, Q[{i}] = {Q[i]}, error = {errors[i]}");


        ////// ---------------------------------------------------------
        ////// 3. Umeyama�iSVD + �X�P�[���j���@���g�ł̓X�P�[�������ꂵ�Ă���B����͎g�p���Ȃ��B
        ////// ---------------------------------------------------------
        ////Matrix4x4 RU;
        ////Vector3 tU;
        ////float sU;
        ////RigidTransformUnity.ComputeUmeyamaSVD(P, Q, out RU, out tU, out sU);
        ////Debug.Log("Umeyama Rotation (deg): " + RU.rotation.eulerAngles);
        ////Debug.Log("Umeyama Translation: " + tU);
        ////Debug.Log("Umeyama Scale: " + sU);

        ////Pk = RigidTransformUnity.EvaluateTransform(P, Q, RU, tU, out errors, out rmse,sU);
        ////Debug.Log($"Kabsch RMSE = {rmse}");
        ////for (int i = 0; i < errors.Length; i++)
        ////    Debug.Log($"P'[{i}] = {Pk[i]}, Q[{i}] = {Q[i]}, error = {errors[i]}");

    }



    // ============================================
    // txt �ǂݍ��݊֐��i�J���}��؂�E�󔒋�؂�ǂ�����Ή��j
    // ============================================
    Vector3[] LoadPoints(string path)
    {
        List<Vector3> pts = new List<Vector3>();

        foreach (var line in File.ReadAllLines(path))
        {
            if (string.IsNullOrWhiteSpace(line))
                continue;

            // �J���} or �󔒂ŕ���
            var s = line.Replace(",", " ").Split(' ');

            List<float> nums = new List<float>();
            foreach (var v in s)
            {
                if (float.TryParse(v, out float f))
                    nums.Add(f);
            }

            if (nums.Count >= 3)
                pts.Add(new Vector3(nums[0], nums[1], nums[2]));
        }

        return pts.ToArray();
    }







    // Update is called once per frame
    void Update()
    {
        
    }
}

```

### File: `Scripts\Math\SymEQ.cs`
```csharp
﻿using System;

namespace SymEQ {
//{
// **************************************************************************
// *
// *    3DIMENSIONAL HIGH ACCURACY PHOTO SURVEY SYSTEM
// *             DEVELOPMENT FROM 2010 Feb,15th 
// *
// *	         MHI Power Enginnering CO., LTD.
// *	    Intellectual Production Management Department
// *	                Yokohama DIvision
// *
// *	           SYMMETRICAL EQAUTIONS MODULE
// *
// *	              2023.11.24 By N.MORI
// *
// **************************************************************************

class Sym_EQ
{

	// 変数の定義
	private long N;         // 行列サイズ
	private double[]? A;     // 行列の左辺項　対称性を利用しメモリー半分
	private long[]? bc;      // 拘束条件ビット
	public double[]? X;     // 連立方程式の解
	private double[]? B;     // 連立方程式の右辺の項
	//private double[]? pt;    // 消去時のPIVOTエリア
	private double[]? Y;     // 前進代入におけるDU×Disp
	private long[]? flg;     // PIVOTエリアのゼロを示すフラグ

	private double[]? A_b;   // 行列消去前のバックアップ領域
	private double[]? res;   // 残差確認領域

	public Sym_EQ()
    {
		InitConstract();
	}

	// コンストラクタ
	public Sym_EQ(long nf, long f)
	{
		N = nf;
		A = new double[N * (N + 1) / 2];
		B = new double[N];
		X = new double[N];
		bc = new long[N];
		flg = new long[N];
		Y = new double[N];

		if (f == 1)
		{
			A_b = new double[N * (N + 1) / 2];
			res = new double[N];
		}

	}
	/////////////////////////////////////////////////////////////////////////////
	// コンストラクタデフォルト値生成
	public bool InitConstract()
	{
		N = 0;
		A = null;       // 行列の左辺項　対称性を利用しメモリー半分
		bc = null;      // 拘束条件ビット
		X = null;       // 連立方程式の解
		B = null;       // 連立方程式の右辺の項
		A_b = null;     // 行列消去前のバックアップ領域
		//pt = null;      // 消去時のPIVOTエリア

		flg = null;     // PIVOTエリアのゼロを示すフラグ
		Y = null;

		return true;
	}
	/////////////////////////////////////////////////////////////////////////////
	// データサイズの再設定
	public void Set_Size(long nf)
	{
		N = nf;
		A = new double[N * (N + 1) / 2];
		B = new double[N];
		X = new double[N];
		bc = new long[N];
		flg = new long[N];
		Y = new double[N]; N = nf;

	}
	/////////////////////////////////////////////////////////////////////////////
	// 係数行列のアドレッシングを行う　i 行 j 列 
	long ij(long i, long j)
	{
		return (i * (2 * N - i + 1)) / 2 + j - i;
	}
	// 対称行列の下半分の係数領域を参照する場合　i 行 j 列 
	long ji(long i, long j)
	{
		return (j * (2 * N - j + 1)) / 2 + i - j;
	}
	public void Set_A(long i, long j, double dt)
	{
		if(A is not null)A[ij(i, j)] = dt;
	}
	public void Add_A(long i, long j, double dt)
	{
		if (A is not null) A[ij(i, j)] += dt;
	}
	public void Set_Bc(long i, long b)
	{
		if (bc is not null) bc[i] = b;
	}
	public void Set_B(long i, double dt)
	{
		if(B is not null)B[i] = dt;
	}
	public void Add_B(long i, double dt)
	{
		if(B is not null)B[i] += dt;
	}
	public double Get_A(long i, long j)
	{
		if (A is null) return 0.0;
			if (i <= j)
			{
				return A[ij(i, j)];
			}
			else
			{
				return A[ji(i, j)];
			}
	}
	/////////////////////////////////////////////////////////////////////////////
	// LU分解
	public bool LUDecomp()
	{
		double Pivot;
		double [] wk;
		wk = new double [N];
		for (int m = 0; m < N; m++) wk[m] = 0.0;
		//memset(wk, NULL, N * sizeof(double));   // ゼロクリアー

		long i;
		long j;
		long k;
		if (A is null) return false;
		if (bc is null) return false;

		for (i = 0; i < N; i++)
		{
			if (bc[i] == 1) continue;
			Pivot = A[ij(i, i)];// PIVOTを格納する
			if (Pivot == 0.0f) return false;
			if (bc[i] == 0)
			{
				Pivot = 1.0 / Pivot;
				for (j = i + 1; j < N; j++)
				{
					wk[j] = A[ij(i, j)];                // ワークテーブルにi行目を納める
					if (bc[j] == 0)
						A[ij(i, j)] = A[ij(i, j)] * Pivot;  // i行の対角項(1列目)でわり算する
				}
				for (j = i + 1; j < N; j++)
				{
					if ( j < N && bc[j] == 0)
					{
						for (k = j; k < N; k++)
						{
							//if (j+k >= N)  break;
							if (bc[k] == 0)
								A[ij(j, k)] -= wk[j] * A[ij(i, k)];

						}
					}
				}
			}
		}
	


		return true;
	}
	/////////////////////////////////////////////////////////////////////////////
	// 前進代入 LY=F
	public bool FowardSub()
	{
		long i;
		long j;
		if(bc is null) return false;
		if(Y is null) return false;
		if(A is null) return false;
		if(B is null) return false;

		// Y に B を代入
		for (i = 0; i < N; i++)
		{
			if (bc[i] == 0 && A[ij(i, i)] != 0.0)
			{
				Y[i] = B[i];
			}
		}

		for (i = 1; i < N; i++)
		{
			if (bc[i] == 0 && A[ij(i, i)] != 0.0)
			{
				for (j = 0; j < i; j++)
				{
					Y[i] -= Y[j] * A[ji(i, j)];

				}
			}
		}

		return true;
	}
	/////////////////////////////////////////////////////////////////////////////
	// 後退代入 UX=Y
	public bool BackSub()
	{
		long i;
		long j;
		if(A is null ) return false;
		if(bc is null) return false;
		if(X is null) return false;
		if(Y is null ) return false;

		for (i = 0; i < N; i++)
		{
			if (bc[i] == 0 && A[ij(i, i)] != 0.0)
			{
				for (j = i + 1; j < N; j++)
				{
					A[ij(i, j)] = A[ij(i, j)] * A[ij(i, i)];
				}
			}
		}

		for (i = 0; i < N; i++)
		{
			if (bc[i] == 0 && A[ij(i, i)] != 0.0)
			{
				X[i] = Y[i];

			}
		}

		for (i = N - 1; i > -1; i--)
		{
			if (bc[i] == 0 && A[ij(i, i)] != 0.0)
			{
				for (j = N - 1; j >= i; j--)
				{
					if (bc[j] == 0 && A[ij(i, i)] != 0.0)
					{
						if (i != j) X[i] -= X[j] * A[ij(i, j)];
						if (i == j) X[i] /= A[ij(i, i)];
					}
				}
			}
		}
		return true;
	}
}


}

```

### File: `Scripts\Rendering\CADQualityManager.cs`
```csharp

// ===============================================
// CADQualityManager.cs
// PRODUCTION VERSION - Enforces 8x MSAA and High SMAA
// ===============================================

using UnityEngine;
using UnityEngine.Rendering.Universal;

public class CADQualityManager : MonoBehaviour
{
    private void Awake()
    {
        EnforceCADQualitySettings();
    }

    private void EnforceCADQualitySettings()
    {
        // 1. Force 8x Hardware MSAA for crisp geometry and outline edges
        var urpAsset = UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
        if (urpAsset != null)
        {
            urpAsset.msaaSampleCount = 8;
            urpAsset.renderScale = 1.0f; // Ensure exact 1:1 native resolution scaling
            Debug.Log("<color=green>[CADQualityManager] 8x MSAA enforced via URP Asset.</color>");
        }

        // 2. Force High-Quality SMAA on the Main Camera for pixel smoothing
        Camera mainCam = Camera.main;
        if (mainCam != null)
        {
            var camData = mainCam.GetUniversalAdditionalCameraData();
            if (camData != null)
            {
                camData.renderPostProcessing = true;
                camData.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
                camData.antialiasingQuality = AntialiasingQuality.High;
                Debug.Log("<color=green>[CADQualityManager] High-Quality SMAA enforced on Main Camera.</color>");
            }
        }
    }
}
```

### File: `Scripts\Rendering\MouseOrbitCamera.cs`
```csharp
﻿// ===============================================
// MouseOrbitCamera.cs
// PRODUCTION VERSION - Orthographic CAD Zoom & Adaptive Pan
// ===============================================

using UnityEngine;
using UnityEngine.EventSystems;

[RequireComponent(typeof(Camera))]
public class MouseOrbitCamera : MonoBehaviour
{
    [Header("Target Settings")]
    public Transform target;

    [Header("=== Distance & Scale Settings ===")]
    [Tooltip("Current physical distance from target (Used heavily in Perspective mode)")]
    public float distance = 15000f;

    [Tooltip("Minimum physical distance or minimum orthographic size for extreme close-ups")]
    public float minDistance = 0.1f;   // Lowered to 0.1f to allow sub-millimeter inspection in Orthographic mode

    [Tooltip("Maximum zoom distance or maximum orthographic size")]
    public float maxDistance = 1000000f;

    [Header("=== Control Sensitivity ===")]
    [Tooltip("Left mouse rotation speed")]
    public float rotateSpeed = 5.0f;

    [Tooltip("Zoom sensitivity as a percentage of current scale (e.g., 0.1 = 10% per tick)")]
    [Range(0.01f, 0.5f)]
    public float zoomSensitivity = 0.1f;

    [Tooltip("Base right mouse pan speed. Will automatically adapt based on zoom level.")]
    public float panSpeed = 300f;

    private float x = 0.0f;
    private float y = 0.0f;
    private Vector3 panOffset = Vector3.zero;

    // Core camera reference to detect projection mode dynamically
    private Camera cam;

    // ジンバルロック回避のための制限値 (Gimbal lock prevention limits)
    private const float Y_MIN_LIMIT = -89.5f;
    private const float Y_MAX_LIMIT = 89.5f;
    private void Start()
    {
        cam = GetComponent<Camera>();
        Vector3 angles = transform.eulerAngles;
        x = angles.y;
        y = angles.x;

        // 初期化時にリジッドボディを無効化し物理演算の干渉を防ぐ (Disable Rigidbody interference)
        if (GetComponent<Rigidbody>()) GetComponent<Rigidbody>().freezeRotation = true;
    }
    private void LateUpdate()
    {
        if (target == null) return;

        // UIの上でマウス操作している場合は入力を無視 (Ignore input when interacting with UI)
        if (EventSystem.current != null && EventSystem.current.IsPointerOverGameObject()) return;

        // 1. 回転処理 (Rotation Handling - 右クリック)
        if (Input.GetMouseButton(1))
        {
            x += Input.GetAxis("Mouse X") * rotateSpeed;
            y -= Input.GetAxis("Mouse Y") * rotateSpeed;

            // [CRITICAL FIX] Y軸(ピッチ)の回転を厳密に制限し、ジンバルロックとカメラの反転を防止
            y = Mathf.Clamp(y, Y_MIN_LIMIT, Y_MAX_LIMIT);
        }

        // 2. パン処理 (Panning Handling - 中クリック)
        if (Input.GetMouseButton(2))
        {
            float currentPanSpeed = (cam.orthographic) ? (cam.orthographicSize / 500f) * panSpeed : (distance / 5000f) * panSpeed;
            currentPanSpeed = Mathf.Max(currentPanSpeed, 0.1f);

            // カメラのローカル空間における相対移動 (Relative movement in camera's local space)
            Vector3 panDelta = transform.right * (-Input.GetAxis("Mouse X") * currentPanSpeed) +
                               transform.up * (-Input.GetAxis("Mouse Y") * currentPanSpeed);
            panOffset += panDelta;
        }

        // 3. ズーム処理 (Zoom Handling - スクロールホイール)
        float scroll = Input.GetAxis("Mouse ScrollWheel");
        if (Mathf.Abs(scroll) > 0.001f)
        {
            if (cam.orthographic)
            {
                float adaptiveSizeSpeed = cam.orthographicSize * zoomSensitivity;
                cam.orthographicSize -= scroll * adaptiveSizeSpeed;
                cam.orthographicSize = Mathf.Clamp(cam.orthographicSize, minDistance, maxDistance);
            }
            else
            {
                float adaptiveSpeed = distance * zoomSensitivity;
                distance -= scroll * adaptiveSpeed;
                distance = Mathf.Clamp(distance, minDistance, maxDistance);
            }
        }

        // 4. 最終変換の適用 (Final Transform Application)
        // クランプされたy値によって安全な四元数を生成 (Generate safe Quaternion)
        Quaternion rotation = Quaternion.Euler(y, x, 0.0f);
        Vector3 position = rotation * new Vector3(0.0f, 0.0f, -distance) + target.position + panOffset;

        transform.rotation = rotation;
        transform.position = position;
    }

    public void ResetView()
    {
        x = 0.0f;
        y = 0.0f;
        distance = 15000f;
        panOffset = Vector3.zero;

        if (cam != null && cam.orthographic)
        {
            cam.orthographicSize = 5000f; // Reset to a safe CAD overview scale
        }
    }
}
```

### File: `Scripts\Rendering\OutlineRenderFeature.cs`
```csharp
﻿// ===============================================
// OutlineRenderFeature.cs
// PRODUCTION VERSION V8 - Modern URP Render Graph API
// ===============================================

using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.Rendering.RenderGraphModule; 

/// <summary>
/// Injects a custom full-screen pass into the URP pipeline to draw CAD-style outlines.
/// Upgraded to fully support the modern Unity 6 (URP 17+) Render Graph API.
/// </summary>
public class OutlineRenderFeature : ScriptableRendererFeature
{
    [System.Serializable]
    public class OutlineSettings
    {
        [Tooltip("The material utilizing the ScreenSpaceOutline_URP shader.")]
        public Material outlineMaterial;

        [Tooltip("When should the outline be drawn in the rendering pipeline?")]
        public RenderPassEvent renderPassEvent = RenderPassEvent.AfterRenderingTransparents;
    }

    public OutlineSettings settings = new OutlineSettings();
    private OutlinePass outlinePass;

    public override void Create()
    {
        if (settings.outlineMaterial != null)
        {
            outlinePass = new OutlinePass(settings.outlineMaterial, settings.renderPassEvent);
        }
    }

    public override void AddRenderPasses(ScriptableRenderer renderer, ref RenderingData renderingData)
    {
        if (settings.outlineMaterial != null && outlinePass != null)
        {
            if (renderingData.cameraData.cameraType == CameraType.Game || renderingData.cameraData.cameraType == CameraType.SceneView)
            {
                // [MODERN URP] No longer need to manually pass camera targets here.
                // Render Graph handles target acquisition automatically.
                outlinePass.ConfigureInput(ScriptableRenderPassInput.Depth | ScriptableRenderPassInput.Normal);
                renderer.EnqueuePass(outlinePass);
            }
        }
    }

    /// <summary>
    /// The Render Graph compatible pass execution class.
    /// Inherits from ScriptableRenderPass but overrides RecordRenderGraph instead of Execute.
    /// </summary>
    class OutlinePass : ScriptableRenderPass
    {
        private Material material;

        public OutlinePass(Material mat, RenderPassEvent passEvent)
        {
            this.material = mat;
            this.renderPassEvent = passEvent;
        }

        // Structure to hold data needed inside the Rasterizer context
        private class PassData
        {
            public TextureHandle sourceTexture;
            public Material material;
        }

        /// <summary>
        /// [MODERN URP] The entry point for Render Graph. Replaces OnCameraSetup and Execute.
        /// </summary>
        public override void RecordRenderGraph(RenderGraph renderGraph, ContextContainer frameData)
        {
            // Extract the universal resource and camera data from the modern frame context
            UniversalResourceData resourceData = frameData.Get<UniversalResourceData>();
            UniversalCameraData cameraData = frameData.Get<UniversalCameraData>();

            // Acquire the current active color texture from the pipeline
            TextureHandle activeCameraTarget = resourceData.activeColorTexture;
            if (!activeCameraTarget.IsValid()) return;

            // Generate a descriptor for our temporary processing texture
            RenderTextureDescriptor tempDesc = cameraData.cameraTargetDescriptor;
            tempDesc.depthBufferBits = 0; // We strictly only need the color buffer for post-processing

            // Let the Render Graph safely allocate the temporary texture
            TextureHandle tempTexture = UniversalRenderer.CreateRenderGraphTexture(renderGraph, tempDesc, "_TempOutlineTexture", false);

            // ==========================================================
            // SUB-PASS 1: Blit from Camera Target -> Temp Texture (Applying Outline Shader)
            // ==========================================================
            using (var builder = renderGraph.AddRasterRenderPass<PassData>("Outline Effect Pass", out var passData))
            {
                passData.material = this.material;
                passData.sourceTexture = activeCameraTarget;

                // Declare explicit resource dependencies for the graph memory manager
                builder.UseTexture(passData.sourceTexture, AccessFlags.Read);
                builder.SetRenderAttachment(tempTexture, 0); // Write destination

                // Execute the actual blit command within the graph context
                builder.SetRenderFunc((PassData data, RasterGraphContext context) =>
                {
                    Blitter.BlitTexture(context.cmd, data.sourceTexture, new Vector4(1, 1, 0, 0), data.material, 0);
                });
            }

            // ==========================================================
            // SUB-PASS 2: Blit from Temp Texture -> Back to Camera Target (Output)
            // ==========================================================
            using (var builder = renderGraph.AddRasterRenderPass<PassData>("Outline Copy Back Pass", out var passData))
            {
                passData.sourceTexture = tempTexture;

                builder.UseTexture(passData.sourceTexture, AccessFlags.Read);
                builder.SetRenderAttachment(activeCameraTarget, 0); // Write back to the main camera

                builder.SetRenderFunc((PassData data, RasterGraphContext context) =>
                {
                    // Blit back without a specific material (pure copy)
                    Blitter.BlitTexture(context.cmd, data.sourceTexture, new Vector4(1, 1, 0, 0), 0.0f, false);
                });
            }
        }
    }
}
```

### File: `Scripts\Rendering\PointRenderer.cs`
```csharp
﻿// ===============================================
// PointRenderer.cs
// PRODUCTION VERSION - Bulletproof Dictionary + Legacy Support
// ===============================================

using UnityEngine;
using System.Collections.Generic;

// [追加] 実行順序の引き上げ
[DefaultExecutionOrder(-90)]
public class PointRenderer : MonoBehaviour
{
    [Header("Data Reference")]
    [SerializeField] private ProjectRootBehaviour projectRoot;

    [Header("=== Industrial CAD Visual Settings ===")]
    [SerializeField, Range(0.001f, 0.2f)] private float visualScreenSizeRatio = 0.0125f;
    [SerializeField, Range(1f, 500f)] private float minPhysicalScale = 20f;
    [SerializeField, Range(100f, 20000f)] private float maxPhysicalScale = 1250f;

    [Header("URP Materials - Assign in Inspector")]
    [SerializeField] private Material designTransparentMaterial;
    [SerializeField] private Material measuredOpaqueMaterial;

    private Dictionary<string, GameObject> pointObjects = new Dictionary<string, GameObject>();
    private Camera mainCamera;

    private void Awake()
    {
        // [追加] サービスとして登録
        ServiceLocator.Register<PointRenderer>(this);

        if (projectRoot == null) ServiceLocator.TryGet(out projectRoot);
        mainCamera = Camera.main;
    }

    private void Start() => RefreshAllPoints();

    private void LateUpdate()
    {
        if (mainCamera == null || pointObjects.Count == 0) return;
        Vector3 cameraPos = mainCamera.transform.position;
        foreach (var obj in pointObjects.Values)
        {
            if (obj != null)
            {
                float distance = Vector3.Distance(cameraPos, obj.transform.position);
                float rawScale = distance * visualScreenSizeRatio;
                float dynamicScale = Mathf.Clamp(rawScale, minPhysicalScale, maxPhysicalScale);
                obj.transform.localScale = new Vector3(dynamicScale, dynamicScale, dynamicScale);
            }
        }
    }

    public void RefreshAllPoints()
    {
        if (projectRoot?.ProjectData == null) return;

        // 1. 追跡済みのキーを収集 (收集当前存在的所有 Key)
        HashSet<string> validKeys = new HashSet<string>();

        // 2. 既存の点を更新、または新規作成 (更新现有球体或创建新球体)
        foreach (var pair in projectRoot.ProjectData.Points)
        {
            Point point = pair.Value;
            if (point == null) continue;

            string uniqueKey = $"{point.ID}_{point.GroupID}";
            validKeys.Add(uniqueKey);

            if (pointObjects.TryGetValue(uniqueKey, out GameObject existingObj) && existingObj != null)
            {
                // [修正] 破壊せず、座標とマテリアルだけを安全に更新 (仅更新位置与渲染)
                existingObj.transform.position = (point.GroupID == 0) ? point.DesignPosition : point.MeasurePosition;
                existingObj.name = string.IsNullOrEmpty(point.Name) ? $"Unnamed_{point.ID}" : point.Name;
                UpdatePointVisual(existingObj, point);
            }
            else
            {
                // [修正] 新規の場合のみ生成 (仅在缺乏实体时新建)
                CreateNewPointObject(point, uniqueKey);
            }
        }

        // 3. 削除されたデータに対応する古いオブジェクトをクリーンアップ (清除已被剔除的数据对应的残留球体)
        List<string> keysToRemove = new List<string>();
        foreach (var key in pointObjects.Keys)
        {
            if (!validKeys.Contains(key)) keysToRemove.Add(key);
        }

        foreach (var key in keysToRemove)
        {
            if (pointObjects[key] != null) Destroy(pointObjects[key]);
            pointObjects.Remove(key);
        }
    }

    private void CreateNewPointObject(Point point, string uniqueKey)
    {
        GameObject pointObj = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        pointObj.name = string.IsNullOrEmpty(point.Name) ? $"Unnamed_{point.ID}" : point.Name;
        pointObj.transform.SetParent(this.transform); // 整理Hierarchy
        pointObj.transform.position = (point.GroupID == 0) ? point.DesignPosition : point.MeasurePosition;

        SphereCollider col = pointObj.GetComponent<SphereCollider>();
        col.radius = 1.5f;

        Renderer rend = pointObj.GetComponent<Renderer>();
        if (rend != null)
        {
            if (point.GroupID == 0 && designTransparentMaterial != null) rend.sharedMaterial = designTransparentMaterial;
            else if (point.GroupID == 1 && measuredOpaqueMaterial != null) rend.sharedMaterial = measuredOpaqueMaterial;
        }

        PointSelectData data = pointObj.AddComponent<PointSelectData>();
        data.point = point;

        pointObjects[uniqueKey] = pointObj;
        UpdatePointVisual(pointObj, point);
    }
    public void CreateOrUpdatePointObject(Point point)
    {
        if (point == null) return;
        string uniqueKey = $"{point.ID}_{point.GroupID}";

        if (pointObjects.TryGetValue(uniqueKey, out GameObject old) && old != null)
            DestroyImmediate(old);

        GameObject pointObj = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        pointObj.name = string.IsNullOrEmpty(point.Name) ? $"Unnamed_{point.ID}" : point.Name;
        pointObj.transform.SetParent(null);
        pointObj.transform.position = (point.GroupID == 0) ? point.DesignPosition : point.MeasurePosition;

        SphereCollider col = pointObj.GetComponent<SphereCollider>();
        col.radius = 1.5f;

        Renderer rend = pointObj.GetComponent<Renderer>();
        if (rend != null)
        {
            if (point.GroupID == 0 && designTransparentMaterial != null) rend.sharedMaterial = designTransparentMaterial;
            else if (point.GroupID == 1 && measuredOpaqueMaterial != null) rend.sharedMaterial = measuredOpaqueMaterial;
        }

        PointSelectData data = pointObj.AddComponent<PointSelectData>();
        data.point = point;

        pointObjects[uniqueKey] = pointObj;
        UpdatePointVisual(pointObj, point);
    }

    public void UpdateSinglePoint(System.Guid pointId)
    {
        if (projectRoot?.ProjectData?.Points.TryGetValue(pointId, out Point p) == true)
        {
            string uniqueKey = $"{p.ID}_{p.GroupID}";
            if (pointObjects.TryGetValue(uniqueKey, out GameObject go) && go != null)
            {

                go.transform.position = (p.GroupID == 0) ? p.DesignPosition : p.MeasurePosition;


                UpdatePointVisual(go, p);
            }
        }
    }

    private void UpdatePointVisual(GameObject obj, Point point)
    {
        if (obj == null || point == null) return;
        Renderer rend = obj.GetComponent<Renderer>();
        if (rend == null) return;

        // ========================================================
        // [CRITICAL FIX] Strict Data Mapping (厳密なデータマッピング)
        // Only use 'PointType' (Joining / Reference) for coloring logic.
        // Ignore 'PlateType' (UF / LF) to prevent visual override bugs.
        // ========================================================
        string rawType = point.PointType;
        string cleanType = rawType?.Replace("\"", "").Trim().ToLower() ?? "";

        Color finalColor;

        if (cleanType == "joining")
        {
            // Joining points get a distinct red warning color
            finalColor = Color.red;
        }
        else
        {
            // Reference points get the standard industrial blue
            finalColor = new Color(0.0f, 0.6f, 1.0f, 1.0f);
        }

        // Apply transparency: Design points (0) are ghosted, Measured points (1) are solid
        if (point.GroupID == 0) finalColor.a = 0.65f;
        else finalColor.a = 1.0f;

        // Use MaterialPropertyBlock for efficient, per-instance coloring
        MaterialPropertyBlock block = new MaterialPropertyBlock();
        rend.GetPropertyBlock(block);

        block.SetColor("_BaseColor", finalColor); // URP Lit/Simple Lit target
        block.SetColor("_Color", finalColor);     // Standard Shader fallback
        block.SetColor("_EmissionColor", Color.black);

        rend.SetPropertyBlock(block);
    }


    public void HighlightPointTemporary(System.Guid pointId, Color highlightColor, float duration = 3f)
    {
        if (projectRoot?.ProjectData?.Points.TryGetValue(pointId, out Point p) == true)
        {
            HighlightTempHelper($"{pointId}_0", highlightColor, duration, p);
            HighlightTempHelper($"{pointId}_1", highlightColor, duration, p);
        }
    }

    private void HighlightTempHelper(string uniqueKey, Color color, float duration, Point p)
    {
        if (pointObjects.TryGetValue(uniqueKey, out GameObject go) && go != null)
        {
            Renderer rend = go.GetComponent<Renderer>();
            if (rend != null)
            {
                MaterialPropertyBlock block = new MaterialPropertyBlock();
                rend.GetPropertyBlock(block);
                block.SetColor("_BaseColor", color);
                rend.SetPropertyBlock(block);
                StartCoroutine(ResetHighlightAfterDelay(go, p, duration));
            }
        }
    }

    private System.Collections.IEnumerator ResetHighlightAfterDelay(GameObject go, Point p, float delay)
    {
        yield return new WaitForSeconds(delay);
        if (go != null && go.GetComponent<Renderer>() != null)
        {
            go.GetComponent<Renderer>().SetPropertyBlock(null);
            UpdatePointVisual(go, p);
        }
    }


    public void SetPointHighlight(Point point, bool isHighlighted, Color highlightColor)
    {
        if (point == null) return;
        ApplyHighlight($"{point.ID}_{point.GroupID}", isHighlighted, highlightColor, point);
    }


    public void SetPointHighlight(System.Guid pointId, bool isHighlighted, Color highlightColor)
    {
        //if (projectRoot?.ProjectData?.Points.TryGetValue(pointId, out Point p) == true)
        //    ApplyHighlight($"{pointId}_1", isHighlighted, highlightColor, p);
    }

    private void ApplyHighlight(string uniqueKey, bool isHighlighted, Color highlightColor, Point p)
    {
        if (!pointObjects.TryGetValue(uniqueKey, out GameObject go) || go == null) return;
        Renderer rend = go.GetComponent<Renderer>();
        if (rend == null) return;

        if (isHighlighted)
        {
            MaterialPropertyBlock block = new MaterialPropertyBlock();
            rend.GetPropertyBlock(block);
            block.SetColor("_BaseColor", highlightColor);
            rend.SetPropertyBlock(block);
        }
        else
        {
            rend.SetPropertyBlock(null);
            UpdatePointVisual(go, p);
        }
    }

    public void HighlightExactObject(GameObject targetObj, Point pointData, bool isHighlighted, Color highlightColor)
    {
        if (targetObj == null) return;
        Renderer rend = targetObj.GetComponent<Renderer>();
        if (rend == null) return;

        MaterialPropertyBlock block = new MaterialPropertyBlock();
        rend.GetPropertyBlock(block);

        if (isHighlighted)
        {
            block.SetColor("_BaseColor", highlightColor);
            block.SetColor("_EmissionColor", highlightColor * 2.0f);
            rend.SetPropertyBlock(block);
        }
        else
        {
            rend.SetPropertyBlock(null);
            UpdatePointVisual(targetObj, pointData);
        }
    }

    /// <summary>
    /// Visually moves a specific measured point by its business name (Name) to match the deformed mesh.
    /// STRICTLY operates only on the rendering layer to prevent data pollution.
    /// </summary>
    /// <param name="targetName">The business name of the point (e.g., OG1_OJ1...)</param>
    /// <param name="newWorldPos">The visually exaggerated world position</param>
    public void MoveMeasuredPointByName(string targetName, Vector3 newWorldPos)
    {
        if (string.IsNullOrEmpty(targetName)) return;

        foreach (var go in pointObjects.Values)
        {
            if (go == null) continue;
            PointSelectData data = go.GetComponent<PointSelectData>();

            // Core condition: Exact name match AND GroupID == 1 (Measured Point)
            if (data != null && data.point != null && data.point.Name == targetName && data.point.GroupID == 1)
            {
                // [CRITICAL ARCHITECTURE FIX]: 
                // ONLY update the physical GameObject's Transform in the rendering layer.
                // STRICTLY DO NOT modify 'data.point.MeasurePosition'. 
                // The core data dictionary must remain pure and mathematically accurate.
                go.transform.position = newWorldPos;

                return; // Target found and visually moved. Exit loop for performance.
            }
        }
    }
    private void OnDestroy()
    {
        ServiceLocator.Unregister<PointRenderer>();

        foreach (var obj in pointObjects.Values)
            if (obj != null) Destroy(obj);
        pointObjects.Clear();
    }
}
```

### File: `Scripts\UI\UIToastNotifier.cs`
```csharp
// ===============================================
// UIToastNotifier.cs
// PRODUCTION VERSION - Global Singleton Toast Service
// ===============================================

using UnityEngine;
using TMPro;
using System.Collections;

[RequireComponent(typeof(CanvasGroup))]
public class UIToastNotifier : MonoBehaviour
{
    // ==========================================
    // GLOBAL SINGLETON ACCESS (�O���[�o���A�N�Z�X)
    // ==========================================
    public static UIToastNotifier Instance { get; private set; }

    [Header("UI References")]
    public TextMeshProUGUI messageText;

    [Header("Animation Settings")]
    public float displayDuration = 3.0f; // How long the message stays on screen
    public float fadeDuration = 0.5f;    // Time taken to fade in and fade out

    private CanvasGroup canvasGroup;
    private Coroutine currentRoutine;

    private void Awake()
    {
        // Initialize the Singleton pattern
        if (Instance == null)
        {
            Instance = this;
        }
        else
        {
            // Enforce uniqueness by destroying duplicates
            Destroy(gameObject);
            return;
        }

        canvasGroup = GetComponent<CanvasGroup>();
        canvasGroup.alpha = 0f;             // Hide initially
        canvasGroup.blocksRaycasts = false; // Ensure it doesn't block mouse clicks
    }

    /// <summary>
    /// Globally accessible API to display a Toast message.
    /// Can be called from ANY script using UIToastNotifier.Instance.ShowToast("...");
    /// </summary>
    public void ShowToast(string message)
    {
        if (messageText != null)
        {
            messageText.text = message;
        }

        // Interrupt existing toast if a new one is triggered
        if (currentRoutine != null)
        {
            StopCoroutine(currentRoutine);
        }

        currentRoutine = StartCoroutine(ToastRoutine());
    }

    private IEnumerator ToastRoutine()
    {
        // 1. Fade In
        float elapsed = 0f;
        while (elapsed < fadeDuration)
        {
            elapsed += Time.deltaTime;
            canvasGroup.alpha = Mathf.Clamp01(elapsed / fadeDuration);
            yield return null;
        }

        // 2. Hold on screen
        yield return new WaitForSeconds(displayDuration);

        // 3. Fade Out
        elapsed = 0f;
        while (elapsed < fadeDuration)
        {
            elapsed += Time.deltaTime;
            canvasGroup.alpha = Mathf.Clamp01(1f - (elapsed / fadeDuration));
            yield return null;
        }

        canvasGroup.alpha = 0f; // Ensure it becomes fully transparent
    }
}
```

### File: `Scripts\UI\Core\DraggablePanel.cs`
```csharp
﻿// ===============================================
// DraggablePanel.cs
// PRODUCTION VERSION - Universal UI Drag Handler (Target Supported)
// ===============================================

using UnityEngine;
using UnityEngine.EventSystems;

/// <summary>
/// A universal component that makes any UI element draggable.
/// Supports "Title Bar" dragging by separating the handle from the target panel.
/// </summary>
public class DraggablePanel : MonoBehaviour, IPointerDownHandler, IBeginDragHandler, IDragHandler, IEndDragHandler
{
    [Header("Drag Target Settings")]
    [Tooltip("The root RectTransform of the window to be moved. If left null, it will move the object this script is attached to.")]
    public RectTransform targetPanel;

    private Canvas parentCanvas;
    private CanvasGroup canvasGroup;

    private void Awake()
    {
        // 1.
        if (targetPanel == null)
        {
            targetPanel = GetComponent<RectTransform>();
        }

        // 2. Find the root canvas to accurately calculate drag delta based on screen scale
        parentCanvas = GetComponentInParent<Canvas>();

        // 3. Optional
        canvasGroup = targetPanel.GetComponent<CanvasGroup>();

        if (parentCanvas == null)
        {
            Debug.LogError($"[DraggablePanel] No Canvas found in parents of {gameObject.name}. Dragging will fail.");
        }
    }

    /// <summary>
    /// Triggered the moment the mouse clicks down.
    /// Used to bring the window to the front immediately.
    /// </summary>
    public void OnPointerDown(PointerEventData eventData)
    {
        if (targetPanel != null)
        {
            targetPanel.SetAsLastSibling(); 
        }
    }

    /// <summary>
    /// Triggered the exact frame the user starts dragging this UI element.
    /// </summary>
    public void OnBeginDrag(PointerEventData eventData)
    {
        // Optional: Slightly reduce alpha to indicate active dragging state
        if (canvasGroup != null)
        {
            canvasGroup.alpha = 0.8f;
            canvasGroup.blocksRaycasts = false; // Prevent blocking elements underneath during drag
        }
    }

    /// <summary>
    /// Triggered every frame while the user is holding down the mouse and moving.
    /// </summary>
    public void OnDrag(PointerEventData eventData)
    {
        if (parentCanvas == null || targetPanel == null) return;

        // Divide the mouse delta by the canvas scale factor to ensure the UI moves 
        // 1:1 with the mouse, regardless of the screen resolution or Canvas Scaler settings.
        targetPanel.anchoredPosition += eventData.delta / parentCanvas.scaleFactor;
    }

    /// <summary>
    /// Triggered the exact frame the user releases the mouse button.
    /// </summary>
    public void OnEndDrag(PointerEventData eventData)
    {
        // Restore visual state and raycast blocking
        if (canvasGroup != null)
        {
            canvasGroup.alpha = 1.0f;
            canvasGroup.blocksRaycasts = true;
        }
    }
}
```

### File: `Scripts\UI\Core\MainUIController.cs`
```csharp
﻿// ===============================================
// MainUIController.cs
// PRODUCTION VERSION V4 - Non-Exclusive Floating Panels, Auto-Cleanup & App Termination
// ===============================================

using UnityEngine;
using System.Collections.Generic;

// [CRITICAL ADDITION] Include UnityEditor namespace purely for Editor Play Mode termination.
// Wrapped in preprocessor directives to prevent build failures.
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// A completely decoupled UI manager. It does not know about specific buttons.
/// It only manages a list of panels for mutual exclusion, safely aborts background tasks,
/// and exposes public methods to be hooked up via the Unity Inspector's OnClick() events.
/// </summary>
public class MainUIController : MonoBehaviour
{
    [Header("UI Management")]
    [Tooltip("The main menu panel that contains tool navigation.")]
    public GameObject mainMenuPanel;

    [Tooltip("Drag ALL your tool panels here. The manager will manage their visibility.")]
    public List<GameObject> allManagedPanels = new List<GameObject>();

    [Header("Safety Links")]
    [Tooltip("Link to ConstraintManager to safely abort background tools when UI is closed.")]
    public ConstraintManager constraintManager;

    private void Start()
    {
        // Initialize with a clean slate: hide all tool panels and the main menu
        CloseAllPanels();
        if (mainMenuPanel != null) mainMenuPanel.SetActive(false);
    }

    /// <summary>
    /// PUBLIC API: Toggles the Main Menu visibility.
    /// Opening the menu preserves active panels. Closing the menu triggers a full screen wipe.
    /// </summary>
    public void ToggleMainMenu()
    {
        if (mainMenuPanel != null)
        {
            if (!mainMenuPanel.activeSelf)
            {
                mainMenuPanel.SetActive(true);
            }
            else
            {
                CloseAllPanels();
                mainMenuPanel.SetActive(false);
            }
        }
    }

    /// <summary>
    /// PUBLIC API: Opens a specific panel WITHOUT closing others and WITHOUT hiding the main menu.
    /// </summary>
    public void OpenPanel(GameObject panelToOpen)
    {
        if (panelToOpen != null)
        {
            panelToOpen.SetActive(true);
        }
    }

    /// <summary>
    /// PUBLIC API: Toggles a specific panel on and off.
    /// Perfect for letting users freely show/hide individual panels like PointTable.
    /// </summary>
    public void TogglePanel(GameObject panelToToggle)
    {
        if (panelToToggle != null)
        {
            panelToToggle.SetActive(!panelToToggle.activeSelf);
        }
    }

    /// <summary>
    /// PUBLIC API: Dedicated Back Button Function.
    /// Closes whatever sub-panel is open and ensures the main menu is visible.
    /// </summary>
    public void ReturnToMainMenu()
    {
        CloseAllPanels();

        if (mainMenuPanel != null)
        {
            mainMenuPanel.SetActive(true);
        }
    }

    /// <summary>
    /// PUBLIC API: Closes all panels and safely triggers state machine abortion.
    /// </summary>
    public void CloseAllPanels()
    {
        // 1. Visually hide all managed UI panels
        foreach (var panel in allManagedPanels)
        {
            if (panel != null && panel.activeSelf)
            {
                panel.SetActive(false);
            }
        }

        // 2. SAFETY HOOK: Abort any active point-picking state in the backend
        if (constraintManager != null && constraintManager.IsConstraintInputMode)
        {
            constraintManager.CancelCurrentTool();
            Debug.Log("<color=yellow>[MainUIController] Auto-canceled active tool due to panel closure.</color>");
        }
    }

    /// <summary>
    /// PUBLIC API: Hides the main menu without affecting any open tool panels.
    /// Perfect for the "X" close button on the menu itself.
    /// </summary>
    public void HideMainMenuOnly()
    {
        if (mainMenuPanel != null)
        {
            mainMenuPanel.SetActive(false);
        }
    }

    /// <summary>
    /// PUBLIC API: [NEW] Safely terminates the application (終了).
    /// Aborts any background logic before shutting down to prevent state corruption.
    /// Functions in both the Unity Editor and standalone Windows builds.
    /// </summary>
    public void QuitApplication()
    {
        Debug.Log("[MainUIController] Initiating safe application shutdown sequence...");

        // Safety protocol: Force close all panels and abort any active measurement/constraint tools
        // before shutting down to prevent hanging threads or corrupted memory states.
        CloseAllPanels();

#if UNITY_EDITOR
        // Gracefully exit Play Mode in the Editor
        EditorApplication.isPlaying = false;
#else
        // Terminate the OS process in a built executable
        Application.Quit();
#endif
    }
}
```

### File: `Scripts\UI\DataTables\BlockVisibilityController.cs`
```csharp
﻿// ===============================================
// BlockVisibilityController.cs
// PRODUCTION VERSION - Reactive Refresh & Sequence Sync
// ===============================================

using System.Collections.Generic;
using UnityEngine;

public class BlockVisibilityController : MonoBehaviour
{
    [Header("Core References")]
    public BlockManager blockManager;
    private AssemblySequenceManager sequenceManager;

    [Header("UI Settings")]
    public Transform tableContentParent;
    public GameObject blockRowPrefab;

    private List<BlockVisibilityRowUI> spawnedRows = new List<BlockVisibilityRowUI>();

    private void OnEnable()
    {
        // サービスロケーターを通じてマネージャーを安全に取得
        if (blockManager == null) ServiceLocator.TryGet(out blockManager);
        ServiceLocator.TryGet(out sequenceManager);

        // 基本データの更新イベントを購読
        if (blockManager != null) blockManager.OnBlockDataUpdated += BuildVisibilityTree;

        // 組立順序の同期イベントを監視し、基盤側でグループが変更されたら即座にUIを更新する
        if (sequenceManager != null) sequenceManager.OnSequenceDataSynchronized += BuildVisibilityTree;
    }

    private void OnDisable()
    {
        // メモリリークを防止するための登録解除
        if (blockManager != null) blockManager.OnBlockDataUpdated -= BuildVisibilityTree;
        if (sequenceManager != null) sequenceManager.OnSequenceDataSynchronized -= BuildVisibilityTree;
    }

    /// <summary>
    /// 現在のブロックデータに基づいて、UIテーブル（リスト）を再構築または再利用する。
    /// </summary>
    public void BuildVisibilityTree()
    {
        if (blockManager == null || blockManager.AllBlocks == null) return;

        int index = 0;

        foreach (var block in blockManager.AllBlocks)
        {
            BlockVisibilityRowUI rowUI;

            // オブジェクトプールからの再利用
            if (index < spawnedRows.Count)
            {
                rowUI = spawnedRows[index];
                rowUI.gameObject.SetActive(true);
            }
            // プールが足りない場合のみ新規生成
            else
            {
                GameObject rowGO = Instantiate(blockRowPrefab, tableContentParent, false);
                rowUI = rowGO.GetComponent<BlockVisibilityRowUI>();
                if (rowUI != null) spawnedRows.Add(rowUI);
            }

            if (rowUI != null)
            {
                // [変更] Blockオブジェクト全体を渡し、内部で順序とグループデータを初期化させる
                rowUI.Initialize(block, this);
            }

            index++;
        }

        // 使用されなかった余分な行要素を非表示にする
        for (int i = index; i < spawnedRows.Count; i++)
        {
            if (spawnedRows[i] != null) spawnedRows[i].gameObject.SetActive(false);
        }
    }

    /// <summary>
    /// ユーザーがUIから順序を変更した際に呼び出され、AssemblySequenceManagerに同期を依頼する。
    /// </summary>
    public void UpdateBlockOrder(int groupID, int newOrder)
    {
        if (sequenceManager != null)
        {
            // Managerを通じてグローバルな同期更新を実行する
            sequenceManager.SetAssemblyOrderForGroup(groupID, newOrder);
        }
    }

    /// <summary>
    /// 選択されたブロック以外のすべてのブロックを非表示にする（単独表示）。
    /// </summary>
    public void IsolateBlock(GameObject targetBlockToKeep)
    {
        if (targetBlockToKeep == null) return;

        foreach (var rowUI in spawnedRows)
        {
            GameObject rowBlock = rowUI.GetTargetBlock();
            if (rowBlock == null) continue;

            bool isTarget = (rowBlock == targetBlockToKeep);

            // 実際の3Dオブジェクトの表示を切り替え
            rowBlock.SetActive(isTarget);

            // UIのトグル状態も通知なしで同期する
            rowUI.SyncToggleStateWithoutNotify(isTarget);
        }
    }
}
```

### File: `Scripts\UI\DataTables\BlockVisibilityRowUI.cs`
```csharp
// ===============================================
// BlockVisibilityRowUI.cs
// PRODUCTION VERSION - Visibility, Isolate & Assembly Order Sync
// ===============================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class BlockVisibilityRowUI : MonoBehaviour
{
    [Header("UI Elements")]
    public TMP_Text blockNameText;
    public Button btnIsolate;
    public Toggle visibilityToggle;

    // [�V�K] �ǉ��t�B�[���h�F�g�������ƃO���[�v�����p
    [Header("Assembly Controls")]
    [Tooltip("���̃u���b�N��������S���O���[�v��ID��\������e�L�X�g")]
    public TMP_Text groupText;            // Group ID �̕\���p

    [Tooltip("���[�U�[���g���������蓮�œ��́E�ύX���邽�߂̓��̓t�B�[���h")]
    public TMP_InputField orderInput;     // ���[�U�[���͂ɂ��g������

    // Block�f�[�^�I�u�W�F�N�g�𒼐ڃL���b�V�����A�f�[�^�̐�������ۂ�
    private Block targetBlockData;
    private BlockVisibilityController mainController;

    /// <summary>
    /// �s�f�[�^�̏�������UI�C�x���g�̃o�C���f�B���O���s���B
    /// </summary>
    public void Initialize(Block blockData, BlockVisibilityController controller)
    {
        if (blockData == null || blockData.BlockRoot == null) return;

        targetBlockData = blockData;
        mainController = controller;

        blockNameText.text = targetBlockData.Name;

        // [�V�K] �����ƃO���[�v�f�[�^��UI�ɔ��f����
        if (groupText != null) groupText.text = targetBlockData.AssemblyGroup.ToString();
        if (orderInput != null)
        {
            // �C�x���g�̔��΂�h�����߁AWithoutNotify���g�p����
            orderInput.SetTextWithoutNotify(targetBlockData.AssemblyOrder.ToString());
            orderInput.onEndEdit.RemoveAllListeners();
            orderInput.onEndEdit.AddListener(OnOrderChanged);
        }

        visibilityToggle.SetIsOnWithoutNotify(targetBlockData.BlockRoot.gameObject.activeSelf);
        visibilityToggle.onValueChanged.RemoveAllListeners();
        visibilityToggle.onValueChanged.AddListener(OnVisibilityChanged);

        if (btnIsolate != null)
        {
            btnIsolate.onClick.RemoveAllListeners();
            btnIsolate.onClick.AddListener(OnIsolateClicked);
        }
    }

    /// <summary>
    /// ���[�U�[���g�������̓��̓t�B�[���h�̕ҏW�����������ۂɌĂ΂��B
    /// </summary>
    private void OnOrderChanged(string newValue)
    {
        if (int.TryParse(newValue, out int newOrder))
        {
            // �s���ȓ��͂�h�~���� (1�����ɂ͂��Ȃ�)
            if (newOrder < 1) newOrder = 1;

            if (mainController != null)
            {
                // ���[�U�[�̕ύX�w�߂��R���g���[���[�ɑ��M���A�R���g���[���[����Manager�֓��O���[�v������ʒm����
                mainController.UpdateBlockOrder(targetBlockData.AssemblyGroup, newOrder);
            }
        }
        else
        {
            // �p�[�X���s���i���������͂��ꂽ���j�͌��̒l�ɕ�������
            orderInput.SetTextWithoutNotify(targetBlockData.AssemblyOrder.ToString());
        }
    }

    private void OnVisibilityChanged(bool isVisible)
    {
        if (targetBlockData != null && targetBlockData.BlockRoot != null)
            targetBlockData.BlockRoot.gameObject.SetActive(isVisible);
    }

    private void OnIsolateClicked()
    {
        if (mainController != null) mainController.IsolateBlock(targetBlockData.BlockRoot.gameObject);
    }

    public void SyncToggleStateWithoutNotify(bool isVisible)
    {
        visibilityToggle.SetIsOnWithoutNotify(isVisible);
    }

    public GameObject GetTargetBlock() => targetBlockData?.BlockRoot?.gameObject;
}
```

### File: `Scripts\UI\DataTables\ClearanceTableUIController.cs`
```csharp
﻿using System.Collections.Generic;
using UnityEngine;
using TMPro;

public class ClearanceTableUIController : MonoBehaviour
{
    [Header("Table UI References")]
    public Transform tableContent;
    public GameObject clearanceRowPrefab;

    // [追加] 再利用のためのオブジェクトプール
    private List<GameObject> rowPool = new List<GameObject>();

    private void OnEnable()
    {
        ClearanceManager.OnClearanceUpdated += PopulateClearanceTable;
    }

    private void OnDisable()
    {
        ClearanceManager.OnClearanceUpdated -= PopulateClearanceTable;
    }

    private void PopulateClearanceTable(List<Point> allPoints)
    {
        int index = 0;

        foreach (var p in allPoints)
        {
            if (string.IsNullOrEmpty(p.TieID) || p.TieID == "N/A") continue;

            GameObject rowGO;

            // [変更] プールからの取得または新規生成
            if (index < rowPool.Count)
            {
                rowGO = rowPool[index];
                rowGO.SetActive(true);
            }
            else
            {
                rowGO = Instantiate(clearanceRowPrefab, tableContent);
                rowPool.Add(rowGO);
            }

            TextMeshProUGUI[] texts = rowGO.GetComponentsInChildren<TextMeshProUGUI>();

            if (texts.Length >= 5)
            {
                texts[0].text = p.Joint ?? "N/A";
                texts[1].text = p.Name;
                texts[2].text = (p.GroupID == 1) ? $"({p.MeasurePosition.x:F1}, {p.MeasurePosition.y:F1}, {p.MeasurePosition.z:F1})" : "N/A";
                texts[3].text = $"({p.DesignPosition.x:F1}, {p.DesignPosition.y:F1}, {p.DesignPosition.z:F1})";
                texts[4].text = $"({p.Delta.x:F1}, {p.Delta.y:F1}, {p.Delta.z:F1})";
            }

            index++;
        }

        // [追加] 未使用の行を非表示にする
        for (int i = index; i < rowPool.Count; i++)
        {
            rowPool[i].SetActive(false);
        }
    }
}
```

### File: `Scripts\UI\DataTables\ConstraintRowUI.cs`
```csharp
// ===============================================
// ConstraintRowUI.cs
// PRODUCTION VERSION - Smart Input & Row Deletion Support
// ===============================================

using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

public class ConstraintRowUI : MonoBehaviour
{
    [Header("UI Columns")]
    public Toggle useToggle;
    public TMP_Text leftSideText;
    public TMP_Dropdown operatorDropdown;
    public TMP_InputField rightSideInput;

    // [NEW] �A�R�[�f�B�I���W�J�p�i��͌�̎����l�\���j
    [Header("Result Display (�܂肽���ݎ����l)")]
    [Tooltip("�v�Z���ʂ�\������܂肽���݃R���e�i�i�ʏ펞�͔�A�N�e�B�u�j")]
    public GameObject resultContainer;
    public TMP_Text leftResultText;    // ���ӂ̎����l
    public TMP_Text rightResultText;   // �E�ӂ̎����l

    [Header("Row Controls")]
    [Tooltip("Button used to delete this specific constraint row")]
    public Button btnDeleteRow; // [NEW]: �폜�{�^��

    public ConstraintData boundData { get; private set; }
    private ConstraintManager manager;

    public void Initialize(ConstraintData data, ConstraintManager mgr)
    {
        boundData = data;
        manager = mgr;

        leftSideText.text = data.GetLeftEquationString();

        operatorDropdown.value = (int)data.Operator;
        operatorDropdown.onValueChanged.RemoveAllListeners();
        operatorDropdown.onValueChanged.AddListener(OnOperatorChanged);

        useToggle.isOn = data.IsEnabled;
        useToggle.onValueChanged.RemoveAllListeners();
        useToggle.onValueChanged.AddListener((isOn) => boundData.IsEnabled = isOn);

        rightSideInput.text = data.GetRightEquationString();
        rightSideInput.onEndEdit.RemoveAllListeners();
        rightSideInput.onEndEdit.AddListener(OnRightSideEndEdit);

        if (btnDeleteRow != null)
        {
            btnDeleteRow.onClick.RemoveAllListeners();
            btnDeleteRow.onClick.AddListener(() => { if (manager != null) manager.RemoveConstraint(boundData); });
        }

        EventTrigger trigger = rightSideInput.gameObject.GetComponent<EventTrigger>() ?? rightSideInput.gameObject.AddComponent<EventTrigger>();
        trigger.triggers.Clear();
        EventTrigger.Entry selectEntry = new EventTrigger.Entry { eventID = EventTriggerType.Select };
        selectEntry.callback.AddListener((eventData) => { manager.SetActiveSmartInputRow(this); });
        trigger.triggers.Add(selectEntry);

        // ������Ԃł͌��ʕ\�����B��
        if (resultContainer != null) resultContainer.SetActive(false);
    }

    private void OnOperatorChanged(int index)
    {
        boundData.Operator = (RelationalOperator)index;
    }

    private void OnRightSideEndEdit(string value)
    {
        if (float.TryParse(value, out float parsedValue))
        {
            boundData.IsRightSideEquation = false;
            boundData.RightConstant = parsedValue;
            boundData.RightPointAliases.Clear();
            rightSideInput.text = boundData.RightConstant.ToString("F3");
        }
        manager.ClearActiveSmartInputRow();
    }

    public void InjectRightSidePoints(string p1, string p2)
    {
        boundData.IsRightSideEquation = true;
        boundData.RightPointAliases = new System.Collections.Generic.List<string> { p1, p2 };
        rightSideInput.text = boundData.GetRightEquationString();
    }

    /// <summary>
    /// [NEW] ��͎��s��ɌĂяo����A���݂�3D��ԏ�̎����l���v�Z���ăA�R�[�f�B�I����W�J����
    /// </summary>
    public void UpdateResultDisplay(Matrix4x4 worldToLocal)
    {
        if (manager == null || manager.ProjectData == null || !boundData.IsEnabled) return;

        var allPoints = manager.ProjectData.Points.Values;

        // ���[�J���֐��F�G�C���A�X����Measured�|�C���g������
        Point FindPoint(string alias)
        {
            return allPoints.FirstOrDefault(p => p.GroupID == 1 && (p.DisplayID == alias || p.Name == alias));
        }

        // ���[�J���֐��F���[���h���W�����[�J�����W�ɕϊ����A�w�肳�ꂽ���̐����𒊏o
        float GetAxisValue(Vector3 worldPos)
        {
            Vector3 localPos = worldToLocal.MultiplyPoint3x4(worldPos);
            return boundData.Axis == ConstraintAxis.X ? localPos.x : (boundData.Axis == ConstraintAxis.Y ? localPos.y : localPos.z);
        }

        float leftValue = 0f;
        float rightValue = boundData.RightConstant;

        // ���ӂ̕]�� (����)
        if (boundData.Type == ConstraintType.Coordinate && boundData.LeftPointAliases.Count > 0)
        {
            Point p1 = FindPoint(boundData.LeftPointAliases[0]);
            if (p1 != null) leftValue = GetAxisValue(p1.MeasurePosition);
        }
        else if (boundData.LeftPointAliases.Count >= 2)
        {
            Point p1 = FindPoint(boundData.LeftPointAliases[0]);
            Point p2 = FindPoint(boundData.LeftPointAliases[1]);
            if (p1 != null && p2 != null)
                leftValue = Mathf.Abs(GetAxisValue(p1.MeasurePosition) - GetAxisValue(p2.MeasurePosition));
        }

        // �E�ӂ̕]�� (�E��) - ���̏ꍇ�̂ݍČv�Z
        if (boundData.IsRightSideEquation && boundData.RightPointAliases.Count >= 2)
        {
            Point r1 = FindPoint(boundData.RightPointAliases[0]);
            Point r2 = FindPoint(boundData.RightPointAliases[1]);
            if (r1 != null && r2 != null)
                rightValue = Mathf.Abs(GetAxisValue(r1.MeasurePosition) - GetAxisValue(r2.MeasurePosition));
        }

        // UI�e�L�X�g�̍X�V�ƓW�J
        if (leftResultText != null) leftResultText.text = leftValue.ToString("F3");
        if (rightResultText != null) rightResultText.text = rightValue.ToString("F3");

        if (resultContainer != null) resultContainer.SetActive(true);
    }
}
```

### File: `Scripts\UI\DataTables\ConstraintUIController.cs`
```csharp
﻿// ===============================================
// ConstraintUIController.cs
// PRODUCTION VERSION - Global Axis Selectors Integration (Radio Button Enforced)
// ===============================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Collections.Generic;

public class ConstraintUIController : MonoBehaviour
{
    [Header("Core References")]
    public ConstraintManager constraintManager;
    public ConstraintExecutor constraintExecutor;

    [Header("Global Axis Selectors (Toggle)")]
    public Toggle toggleAxisX;
    public Toggle toggleAxisY;
    public Toggle toggleAxisZ;

    [Header("Tool Buttons")]
    public Button btnToolCoordinate;
    public Button btnToolDistance;
    public Button btnToolEqualClearance;
    public Button btnCancelTool;

    [Header("Joint Controls")]
    [Tooltip("Button to setup and delete the current Joint Coordinate System")]
    public Button btnDeleteJoint;
    public Button btnSetupJoint;

    [Header("Table UI (Slide 6.6)")]
    public Transform tableContentParent;
    public GameObject tableRowPrefab;
    public Button btnExecuteOK;

    [Header("Feedback UI")]
    public TMP_Text promptText;

    private List<GameObject> spawnedRows = new List<GameObject>();

    private void Start()
    {
        // [変更] ServiceLocator経由でコアマネージャーを取得 (使用服务定位器消除场景遍历)
        if (constraintManager == null) ServiceLocator.TryGet(out constraintManager);
        if (constraintExecutor == null) ServiceLocator.TryGet(out constraintExecutor);

        // ==========================================
        // 
        // ==========================================
        ToggleGroup axisGroup = gameObject.GetComponent<ToggleGroup>();
        if (axisGroup == null) axisGroup = gameObject.AddComponent<ToggleGroup>();
        axisGroup.allowSwitchOff = false; //

        // 1. Bind Global Axis Selectors & Assign to Group
        if (toggleAxisX != null)
        {
            toggleAxisX.group = axisGroup;
            toggleAxisX.onValueChanged.AddListener((isOn) => { if (isOn) constraintManager.SetGlobalAxis(ConstraintAxis.X); });
        }
        if (toggleAxisY != null)
        {
            toggleAxisY.group = axisGroup;
            toggleAxisY.onValueChanged.AddListener((isOn) => { if (isOn) constraintManager.SetGlobalAxis(ConstraintAxis.Y); });
        }
        if (toggleAxisZ != null)
        {
            toggleAxisZ.group = axisGroup;
            toggleAxisZ.onValueChanged.AddListener((isOn) => { if (isOn) constraintManager.SetGlobalAxis(ConstraintAxis.Z); });
        }

        // 2. Bind Tool Buttons
        if (btnToolCoordinate != null) btnToolCoordinate.onClick.AddListener(() => constraintManager.ActivateConstraintTool(ConstraintType.Coordinate));
        if (btnToolDistance != null) btnToolDistance.onClick.AddListener(() => constraintManager.ActivateConstraintTool(ConstraintType.Distance));
        if (btnToolEqualClearance != null) btnToolEqualClearance.onClick.AddListener(() => constraintManager.ActivateConstraintTool(ConstraintType.EqualClearance));
        if (btnCancelTool != null) btnCancelTool.onClick.AddListener(() => constraintManager.CancelCurrentTool());

        // 3. Bind Joint Control & Execute
        if (btnSetupJoint != null) btnSetupJoint.onClick.AddListener(() =>
        {
            if (constraintManager != null && constraintManager.jointCreator != null)
                constraintManager.jointCreator.BeginSelecting();
        });

        if (btnDeleteJoint != null) btnDeleteJoint.onClick.AddListener(DeleteJointSystem);
        if (btnExecuteOK != null) btnExecuteOK.onClick.AddListener(ExecuteAllActiveConstraints);

        // 
        if (toggleAxisX != null) toggleAxisX.isOn = true;

        UpdatePromptText("Ready. Select a global axis and a tool.");
        RefreshConstraintTableUI();

        // Subscribe to Manager Events (イベント購読の登録)
        if (constraintManager != null)
        {
            constraintManager.OnStatePromptChanged += UpdatePromptText;
            constraintManager.OnConstraintAdded += RefreshConstraintTableUI;

            // [NEW]: Listen to the Joint Creator's real-time prompt updates
            if (constraintManager.jointCreator != null)
            {
                constraintManager.jointCreator.OnJointPromptChanged += UpdatePromptText;
            }
        }
        // [NEW] 追加: 拘束計算完了時に結果を展開表示するリスナーを登録
        if (constraintExecutor != null)
        {
            constraintExecutor.OnExecutionCompleted += RevealCalculationResults;
        }
    }

    // [NEW] 追加: テーブル内の全行に対して実測値を表示させるメソッド
    private void RevealCalculationResults()
    {
        if (constraintManager == null || constraintManager.jointCreator == null) return;
        if (constraintManager.jointCreator.ExtractedJointData.Count == 0) return;

        // アンカージョイントのローカル座標系行列を取得
        var jointData = constraintManager.jointCreator.ExtractedJointData[0];
        Matrix4x4 localToWorld = Matrix4x4.TRS(jointData.Translation, jointData.RotationMatrix.rotation, Vector3.one);
        Matrix4x4 worldToLocal = localToWorld.inverse;

        int rowCount = 0;
        foreach (var rowGO in spawnedRows)
        {
            if (rowGO.activeSelf)
            {
                ConstraintRowUI rowUI = rowGO.GetComponent<ConstraintRowUI>();
                if (rowUI != null)
                {
                    rowUI.UpdateResultDisplay(worldToLocal);
                    rowCount++;
                }
            }
        }
        Debug.Log($"<color=cyan>[ConstraintUI] 計算結果を展開しました。対象行数: {rowCount}</color>");
    }
    private void UpdatePromptText(string msg)
    {
        if (promptText != null) promptText.text = msg;
    }

    private void RefreshConstraintTableUI()
    {
        if (tableContentParent == null || tableRowPrefab == null) return;

        var constraints = constraintManager.ActiveConstraints;
        int index = 0;

        foreach (var data in constraints)
        {
            GameObject rowGO;
            ConstraintRowUI rowUI;

            // [変更] プールからの取得または新規生成 (从对象池获取或新建)
            if (index < spawnedRows.Count)
            {
                rowGO = spawnedRows[index];
                rowGO.SetActive(true);
                rowUI = rowGO.GetComponent<ConstraintRowUI>();
            }
            else
            {
                rowGO = Instantiate(tableRowPrefab, tableContentParent, false);
                rowUI = rowGO.GetComponent<ConstraintRowUI>();
                spawnedRows.Add(rowGO);
            }

            if (rowUI != null) rowUI.Initialize(data, constraintManager);
            index++;
        }

        // [追加] 未使用の行を非表示にする (隐藏多余的行)
        for (int i = index; i < spawnedRows.Count; i++)
        {
            spawnedRows[i].SetActive(false);
        }
    }

    private void DeleteJointSystem()
    {
        if (constraintManager != null && constraintManager.jointCreator != null)
        {
            constraintManager.jointCreator.ClearAllSystems();
            constraintManager.CancelCurrentTool();
            UpdatePromptText("Joint Coordinate System deleted. Please create a new one.");
            Debug.Log("<color=yellow>[ConstraintUI] Joint System deleted by user. Awaiting new anchor.</color>");
        }
        else
        {
            Debug.LogError("[ConstraintUI] Cannot delete joint: Missing references to ConstraintManager or JointCreator.");
        }
    }

    private void ExecuteAllActiveConstraints()
    {
        Debug.Log("<color=green>[ConstraintUI] 'OK' pressed. Executing solver...</color>");
        if (constraintExecutor != null)
        {
            constraintExecutor.ExecuteAssemblyConstraints();
        }
    }
}
```

### File: `Scripts\UI\DataTables\JointTableUIController.cs`
```csharp
﻿// ===============================================
// JointTableUIController.cs
// PRODUCTION VERSION - Dual Table Synchronization
// ===============================================

using System.Collections.Generic;
using UnityEngine;
using TMPro;

public class JointTableUIController : MonoBehaviour
{
    [Header("Dependencies")]
    public JoiningCoordinateSystemCreator jointCreator;

    [Header("Joint Table (Top)")]
    public Transform jointTableContent;
    public GameObject jointRowPrefab; // Must contain exactly 7 TMP_Text components

    [Header("Tie Point Table (Bottom)")]
    public Transform tiePointTableContent;
    public GameObject tiePointRowPrefab; // Must contain exactly 4 TMP_Text components

    // [追加] 二つのテーブル用のオブジェクトプール
    private List<GameObject> jointRowPool = new List<GameObject>();
    private List<GameObject> tiePointRowPool = new List<GameObject>();

    private void OnEnable()
    {
        if (jointCreator == null) jointCreator = FindFirstObjectByType<JoiningCoordinateSystemCreator>();
        if (jointCreator != null)
        {
            jointCreator.OnJointTableDataUpdated += RefreshTables;
        }
    }

    private void OnDisable()
    {
        if (jointCreator != null)
        {
            jointCreator.OnJointTableDataUpdated -= RefreshTables;
        }
    }

    public void RefreshTables()
    {
        if (jointCreator == null || jointCreator.ExtractedJointData == null) return;

        int jointIndex = 0;
        int tieIndex = 0;

        foreach (var jointData in jointCreator.ExtractedJointData)
        {
            // --- Build Joint Row (プール使用) ---
            GameObject jRow;
            if (jointIndex < jointRowPool.Count)
            {
                jRow = jointRowPool[jointIndex];
                jRow.SetActive(true);
            }
            else
            {
                jRow = Instantiate(jointRowPrefab, jointTableContent);
                jointRowPool.Add(jRow);
            }

            TMP_Text[] jTexts = jRow.GetComponentsInChildren<TMP_Text>();
            if (jTexts.Length >= 7)
            {
                jTexts[0].text = jointData.JointID;
                jTexts[1].text = jointData.Translation.x.ToString("F2");
                jTexts[2].text = jointData.Translation.y.ToString("F2");
                jTexts[3].text = jointData.Translation.z.ToString("F2");
                jTexts[4].text = jointData.NormalVector.x.ToString("F4");
                jTexts[5].text = jointData.NormalVector.y.ToString("F4");
                jTexts[6].text = jointData.NormalVector.z.ToString("F4");
            }
            jointIndex++;

            // --- Build Tie Point Rows (プール使用) ---
            foreach (var tieData in jointData.TiePoints)
            {
                GameObject tRow;
                if (tieIndex < tiePointRowPool.Count)
                {
                    tRow = tiePointRowPool[tieIndex];
                    tRow.SetActive(true);
                }
                else
                {
                    tRow = Instantiate(tiePointRowPrefab, tiePointTableContent);
                    tiePointRowPool.Add(tRow);
                }

                TMP_Text[] tTexts = tRow.GetComponentsInChildren<TMP_Text>();
                if (tTexts.Length >= 4)
                {
                    tTexts[0].text = tieData.JointID;
                    tTexts[1].text = tieData.TiePointID;
                    tTexts[2].text = tieData.BlockID;
                    tTexts[3].text = tieData.PointID;
                }
                tieIndex++;
            }
        }

        // [追加] 余分なUI要素の非アクティブ化
        for (int i = jointIndex; i < jointRowPool.Count; i++) jointRowPool[i].SetActive(false);
        for (int i = tieIndex; i < tiePointRowPool.Count; i++) tiePointRowPool[i].SetActive(false);
    }
}
```

### File: `Scripts\UI\DataTables\PointTableDisplay.cs`
```csharp
﻿// ===============================================
// PointTableDisplay.cs
// PRODUCTION VERSION - Event-Driven Refresh & Search State Retention
// ===============================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Collections.Generic;
using System.Linq;

/// <summary>
/// Manages the UI display of point data. 
/// Driven entirely by explicit UI events (Refresh/Save buttons) for maximum performance.
/// </summary>
public class PointTableDisplay : MonoBehaviour
{
    [Header("Top Control Bar")]
    [Tooltip("Link the InputField used for ID/Name searching.")]
    public TMP_InputField searchInput;

    [Tooltip("Link the Refresh button here.")]
    public Button refreshButton;

    [Tooltip("Link the Save button here.")]
    public Button saveButton;

    [Header("Sort Buttons")]
    public Button sortIDButton;
    public Button sortNameButton;
    public Button sortXButton;
    public Button sortYButton;
    public Button sortZButton;
    public Button sortDeltaButton;

    [Header("Table References")]
    public Transform contentParent;
    public GameObject rowPrefab;

    private List<PointTableRow> allRows = new List<PointTableRow>();
    private ProjectRootBehaviour cachedRoot;

    private void Start()
    {
        // 1. Bind UI events securely
        if (refreshButton != null) refreshButton.onClick.AddListener(RefreshTable);
        if (saveButton != null) saveButton.onClick.AddListener(SaveAllChanges);

        if (sortIDButton != null) sortIDButton.onClick.AddListener(() => SortByColumn("ID"));
        if (sortNameButton != null) sortNameButton.onClick.AddListener(() => SortByColumn("Name"));
        if (sortXButton != null) sortXButton.onClick.AddListener(() => SortByColumn("X"));
        if (sortYButton != null) sortYButton.onClick.AddListener(() => SortByColumn("Y"));
        if (sortZButton != null) sortZButton.onClick.AddListener(() => SortByColumn("Z"));
        if (sortDeltaButton != null) sortDeltaButton.onClick.AddListener(() => SortByColumn("Delta"));

        if (searchInput != null)
            searchInput.onValueChanged.AddListener(OnSearchChanged);

        // 2. Cache the root data container
        // [変更] ServiceLocatorを使用して取得
        ServiceLocator.TryGet(out cachedRoot);
    }

    /// <summary>
    /// Core method triggered by the Refresh Button.
    /// Rebuilds the UI table from the core data dictionary.
    /// </summary>
    public void RefreshTable()
    {
        if (cachedRoot == null) ServiceLocator.TryGet(out cachedRoot);

        if (cachedRoot == null || cachedRoot.ProjectData == null || cachedRoot.ProjectData.Points == null)
        {
            Debug.LogWarning("[PointTableDisplay] Core ProjectData is not ready or empty. Refresh aborted.");
            return;
        }

        int index = 0;
        foreach (var kvp in cachedRoot.ProjectData.Points)
        {
            Point point = kvp.Value;
            PointTableRow row;

            // ==========================================
            // [NEW] オブジェクトプーリング (Object Pooling)
            // ==========================================
            if (index < allRows.Count)
            {
                row = allRows[index];
                row.gameObject.SetActive(true);
            }
            else
            {
                // プールが足りない場合のみ新規生成する
                GameObject rowGO = Instantiate(rowPrefab, contentParent, false);

                RectTransform rt = rowGO.GetComponent<RectTransform>();
                rt.localScale = Vector3.one;
                rt.localRotation = Quaternion.identity;
                rt.localPosition = new Vector3(rt.localPosition.x, rt.localPosition.y, 0f);
                rt.anchoredPosition = new Vector2(0f, rt.anchoredPosition.y);

                row = rowGO.GetComponent<PointTableRow>();
                allRows.Add(row);
            }

            row.Initialize(point, index % 2 == 0, this);
            index++;
        }

        // 使用されなかった余分な行を非アクティブにする
        for (int i = index; i < allRows.Count; i++)
        {
            allRows[i].gameObject.SetActive(false);
        }

        Debug.Log($"<color=green>[PointTableDisplay] Table refreshed manually. {index} rows active.</color>");

        if (searchInput != null && !string.IsNullOrEmpty(searchInput.text))
        {
            OnSearchChanged(searchInput.text);
        }
    }

    /// <summary>
    /// Destroys all instantiated row GameObjects and clears the tracking list.
    /// </summary>
    private void ClearTable()
    {
        // [変更] 破壊(Destroy)せずに非アクティブ化し、プールとして再利用する
        foreach (var row in allRows)
        {
            if (row != null && row.gameObject != null)
                row.gameObject.SetActive(false);
        }
    }

    /// <summary>
    /// Pushes UI modifications back to the core data structure.
    /// </summary>
    public void SaveAllChanges()
    {
        if (cachedRoot == null || cachedRoot.ProjectData == null) return;

        foreach (var row in allRows)
        {
            if (row.currentPoint != null)
                cachedRoot.ProjectData.Points[row.currentPoint.ID] = row.currentPoint;
        }

        Debug.Log("<color=green>[PointTableDisplay] Point modifications manually saved to core project data.</color>");
    }

    /// <summary>
    /// Filters the visible rows based on the search keyword.
    /// </summary>
    private void OnSearchChanged(string keyword)
    {
        if (allRows == null || allRows.Count == 0) return;

        string lowerKeyword = keyword.ToLower();

        foreach (var row in allRows)
        {
            if (row.currentPoint == null) continue;

            bool match = string.IsNullOrEmpty(keyword) ||
                         (row.currentPoint.Name != null && row.currentPoint.Name.ToLower().Contains(lowerKeyword)) ||
                         (row.currentPoint.DisplayID != null && row.currentPoint.DisplayID.ToLower().Contains(lowerKeyword));

            row.gameObject.SetActive(match);
        }
    }

    /// <summary>
    /// Sorts the table rows based on the selected column and rebuilds the UI hierarchy.
    /// </summary>
    private void SortByColumn(string column)
    {
        if (allRows == null || allRows.Count == 0) return;

        if (column == "ID" || column == "Name")
        {
            allRows = allRows.OrderBy(r => column == "ID" ? r.currentPoint.DisplayID : r.currentPoint.Name).ToList();
        }
        else
        {
            // Mathematical sorting based on actual position values
            allRows = allRows.OrderBy(r => GetSortValue(r.currentPoint, column)).ToList();
        }

        ReorderRows();
    }

    private float GetSortValue(Point p, string axis)
    {
        if (axis == "Delta") return p.ErrorDistance;

        Vector3 pos = (p.GroupID == 0) ? p.DesignPosition : p.MeasurePosition;
        if (axis == "X") return pos.x;
        if (axis == "Y") return pos.y;
        return pos.z;
    }

    private void ReorderRows()
    {
        for (int i = 0; i < allRows.Count; i++)
        {
            allRows[i].transform.SetSiblingIndex(i);
        }
    }

    public void HighlightRow(Point point)
    {
        if (point == null) return;

        foreach (var row in allRows)
        {
            if (row.currentPoint != null && row.currentPoint.ID == point.ID)
            {
                row.HighlightRow();
                return;
            }
        }
    }
}
```

### File: `Scripts\UI\DataTables\PointTableRow.cs`
```csharp
﻿// ===============================================
// PointTableRow.cs
// PRODUCTION VERSION - Conditional Delta Display for Measured Points Only
// ===============================================

using UnityEngine;
using TMPro;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class PointTableRow : MonoBehaviour, IPointerClickHandler
{
    [Header("UI Components")]
    public TextMeshProUGUI idText;
    public TextMeshProUGUI nameText;
    public TMP_InputField xInput;
    public TMP_InputField yInput;
    public TMP_InputField zInput;

    [Tooltip("UI Text component to display the Delta (deviation) values.")]
    public TextMeshProUGUI deltaText;

    [HideInInspector] public Point currentPoint;

    private PointTableDisplay tableManager;
    private Image rowImage;
    private Color originalColor;
    private PointRenderer pointRenderer;

    // Extracted exact colors from Block_Design_Transparent.mat and Block_Measured_Opaque.mat
    private readonly Color designColor = new Color(0.72f, 0.42f, 0.70f, 0.80f);
    private readonly Color measuredColor = new Color(0.370f, 0.480f, 0.620f, 1.0f);

    // Optimized visual comfort color palette
    private readonly Color textNormalWhite = Color.white;
    private readonly Color textSoftWarningRed = new Color(0.95f, 0.40f, 0.40f, 1.0f);

    public void Initialize(Point point, bool isEvenRow, PointTableDisplay manager)
    {
        currentPoint = point;
        tableManager = manager;
        rowImage = GetComponent<Image>();

        idText.text = point.DisplayID;
        nameText.text = point.Name;

        // UI MATERIAL SYNCHRONIZATION
        Vector3 displayPosition;
        if (point.GroupID == 0)
        {
            // Design Point
            originalColor = designColor;
            displayPosition = point.DesignPosition;

            idText.fontStyle = FontStyles.Normal;
            nameText.fontStyle = FontStyles.Normal;
        }
        else
        {
            // Measured Point
            originalColor = measuredColor;
            displayPosition = point.MeasurePosition;

            idText.fontStyle = FontStyles.Bold;
            nameText.fontStyle = FontStyles.Bold;
        }

        rowImage.color = originalColor;

        xInput.text = displayPosition.x.ToString("F4");
        yInput.text = displayPosition.y.ToString("F4");
        zInput.text = displayPosition.z.ToString("F4");

        // DELTA DATA INJECTION & COLOR FORMATTING
        UpdateDeltaTextDisplay();

        xInput.onEndEdit.RemoveAllListeners();
        yInput.onEndEdit.RemoveAllListeners();
        zInput.onEndEdit.RemoveAllListeners();

        xInput.onEndEdit.AddListener(OnXChanged);
        yInput.onEndEdit.AddListener(OnYChanged);
        zInput.onEndEdit.AddListener(OnZChanged);

        // [変更] サービスロケーターからの取得に置換
        ServiceLocator.TryGet(out pointRenderer);
    }

    private void OnXChanged(string v) { UpdatePointInScene(); }
    private void OnYChanged(string v) { UpdatePointInScene(); }
    private void OnZChanged(string v) { UpdatePointInScene(); }

    private void UpdatePointInScene()
    {
        if (currentPoint == null) return;

        if (float.TryParse(xInput.text, out float x) &&
            float.TryParse(yInput.text, out float y) &&
            float.TryParse(zInput.text, out float z))
        {
            Vector3 newPosition = new Vector3(x, y, z);

            if (currentPoint.GroupID == 0)
                currentPoint.DesignPosition = newPosition;
            else
                currentPoint.MeasurePosition = newPosition;

            currentPoint.CalculateError();
            UpdateDeltaTextDisplay();
            pointRenderer?.UpdateSinglePoint(currentPoint.ID);
        }
    }

    /// <summary>
    /// Centralized method to update the Delta text UI content and its contextual colors safely.
    /// </summary>
    private void UpdateDeltaTextDisplay()
    {
        if (deltaText == null || currentPoint == null) return;

        // [CRITICAL FIX] Only show Delta values if it is a Measured Point (GroupID == 1)
        if (currentPoint.GroupID == 1)
        {
            deltaText.text = $"({currentPoint.Delta.x:F1}, {currentPoint.Delta.y:F1}, {currentPoint.Delta.z:F1})";

            if (currentPoint.ErrorDistance > 5.0f)
            {
                deltaText.color = textSoftWarningRed;
                deltaText.fontStyle = FontStyles.Bold;
            }
            else
            {
                deltaText.color = textNormalWhite;
                deltaText.fontStyle = FontStyles.Normal;
            }
        }
        else
        {
            // Design points are the baseline. They do not have a meaningful Delta.
            deltaText.text = "-";
            deltaText.color = textNormalWhite;
            deltaText.fontStyle = FontStyles.Normal;
        }
    }

    public void OnPointerClick(PointerEventData eventData)
    {
        if (currentPoint == null) return;
        HighlightRow();
        pointRenderer?.HighlightPointTemporary(currentPoint.ID, Color.orange, 3f);
    }

    public void HighlightRow()
    {
        rowImage.color = new Color(1.0f, 0.65f, 0.0f, 1.0f);
        Invoke(nameof(ResetRowHighlight), 3f);
    }

    private void ResetRowHighlight()
    {
        rowImage.color = originalColor;
    }
}
```

### File: `Scripts\UI\FeaturePanels\AlignmentResultHUD.cs`
```csharp
// ===============================================
// AlignmentResultHUD.cs
// PRODUCTION VERSION - Global LSE Solver Statistics HUD
// ===============================================

using UnityEngine;
using TMPro;
using LSE;

public class AlignmentResultHUD : MonoBehaviour
{
    [Header("HUD Text Elements")]
    [Tooltip("�X�e�[�^�X�\�� (����I�� or Error)")]
    public TMP_Text statusText;

    [Tooltip("������ (Iterations)")]
    public TMP_Text iterationsText;

    [Tooltip("�c���E�ő�ψ� (Max Dx)")]
    public TMP_Text maxDxText;

    [Tooltip("�S��RMS�덷 (X, Y, Z, 3D)")]
    public TMP_Text rmsText;

    [Tooltip("�ő�덷 (Max Error)")]
    public TMP_Text maxErrorText;

    [Header("UI Control")]
    [Tooltip("���ʂ���M����܂Ńp�l�����\���ɂ��邩")]
    public bool hideOnStart = true;
    public GameObject hudPanel;

    private void Awake()
    {
        if (hideOnStart && hudPanel != null) hudPanel.SetActive(false);
    }

    private void OnEnable()
    {
        // LSE�\���o�[�̊����C�x���g���w��
        MultiBlockAlignmentBridge.OnAlignmentCompleted += UpdateHUD;
    }

    private void OnDisable()
    {
        MultiBlockAlignmentBridge.OnAlignmentCompleted -= UpdateHUD;
    }

    /// <summary>
    /// �\���o�[����v�Z���ʂ��󂯎��AHUD���X�V����
    /// </summary>
    private void UpdateHUD(ConstrainedMultiBlockAlignment.SolveResult result, ConstrainedMultiBlockAlignment.RmsResult rms)
    {
        if (hudPanel != null) hudPanel.SetActive(true);

        // 1. �X�e�[�^�X����
        bool isSuccess = result.Status == ConstrainedMultiBlockAlignment.SolveStatus.Ok;
        string colorCode = isSuccess ? "#5AFF5A" : "#FF5A5A";
        string statusString = isSuccess ? "����I�� (Converged)" : $"error no: {(int)result.Status} ({result.Status})";

        if (statusText != null)
            statusText.text = $"�X�e�[�^�X: <color={colorCode}>{statusString}</color>";

        // 2. �����񐔂ƍő�ψ�
        if (iterationsText != null)
            iterationsText.text = $"������: {result.Iterations} / 30";

        if (maxDxText != null)
            maxDxText.text = $"�ő�ψ� (Max Dx): {result.MaxAbsDx:F6} mm";

        // 3. RMS�덷
        if (rmsText != null)
        {
            rmsText.text = $"RMS�덷:\n" +
                           $"  X = {rms.RmsX:F4} mm\n" +
                           $"  Y = {rms.RmsY:F4} mm\n" +
                           $"  Z = {rms.RmsZ:F4} mm\n" +
                           $"  3D = <color=yellow>{rms.Rms3D:F4}</color> mm";
        }

        // 4. �ő�덷
        if (maxErrorText != null)
        {
            maxErrorText.text = $"�덷Max: {rms.MaxAbs:F4} mm";
        }
    }
}
```

### File: `Scripts\UI\FeaturePanels\AnimationUIController.cs`
```csharp
// ===============================================
// AnimationUIController.cs
// PRODUCTION VERSION - Button Hooks for Assembly Animations
// ===============================================

using UnityEngine;
using UnityEngine.UI;

public class AnimationUIController : MonoBehaviour
{
    [Header("Core Reference")]
    public AssemblyAnimationController animationController;

    [Header("UI Buttons")]
    [Tooltip("�g���A�j���[�V�������Đ�����{�^��")]
    public Button btnPlayAssembly;

    [Tooltip("�����m�F�i�W�J�}�j���g�O������{�^��")]
    public Button btnToggleExplode;

    private void Start()
    {
        // �Q�Ƃ������蓖�Ă̏ꍇ�A�V�[�������玩���擾
        if (animationController == null)
        {
            animationController = FindFirstObjectByType<AssemblyAnimationController>();
        }

        // �g���A�j���[�V�����Đ��C�x���g�̃o�C���h
        if (btnPlayAssembly != null)
        {
            btnPlayAssembly.onClick.RemoveAllListeners();
            btnPlayAssembly.onClick.AddListener(() =>
            {
                if (animationController != null) animationController.PlayAssemblyAnimation();
            });
        }

        // �����m�F�i�����E�����j�g�O���C�x���g�̃o�C���h
        if (btnToggleExplode != null)
        {
            btnToggleExplode.onClick.RemoveAllListeners();
            btnToggleExplode.onClick.AddListener(() =>
            {
                if (animationController != null) animationController.ToggleExplodedView();
            });
        }
    }
}
```

### File: `Scripts\UI\FeaturePanels\ReconstructionUIController.cs`
```csharp
﻿// ===============================================
// ReconstructionUIController.cs
// PRODUCTION VERSION - Exact Point ID Lookup & Cleanup Optimization
// ===============================================

using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.UI;

public class ReconstructionUIController : MonoBehaviour
{
    [Header("Core References")]
    public ProjectRootBehaviour projectRoot;
    public BlockManager blockManager;
    public BlockReconstructionManager reconstructionManager;

    [Header("UI Control Panel References")]
    public Slider exaggerationSlider;
    public Toggle heatmapToggle;
    public Slider maxToleranceSlider;

    public void OnClick_Execute3DFitting()
    {
        Debug.Log("<color=cyan>[Reconstruction] Triggered: Execute 3D Fitting pipeline starting...</color>");

        if (projectRoot == null || projectRoot.ProjectData == null)
        {
            Debug.LogError("[Reconstruction] FATAL: ProjectRoot or ProjectData is null!");
            return;
        }

        // ==========================================
        // STAGE 0: SCENE CLEANUP
        // ==========================================
        GameObject[] existingObjects = FindObjectsByType<GameObject>(FindObjectsSortMode.None);
        foreach (GameObject go in existingObjects)
        {
            if (go != null && go.name.EndsWith("_Mea"))
            {
                // [CRITICAL FIX] 実行時の安全な破棄に修正 (改用安全的运行时销毁，防止底层指针崩溃)
                if (Application.isPlaying) Destroy(go);
                else DestroyImmediate(go);
            }
        }

        // ==========================================
        // STAGE 1: DIAGNOSTIC DATA GATHERING & EXACT LOOKUP
        // ==========================================
        var measuredPoints = projectRoot.ProjectData.Points.Values.Where(p => p.GroupID == 1).ToList();

        if (measuredPoints.Count == 0)
        {
            Debug.LogWarning("[Reconstruction] SKIP: No measured points found!");
            return;
        }

        var groupedByBlock = measuredPoints.GroupBy(p => p.Block).ToList();

        PointSelectData[] allSelectablePoints = FindObjectsByType<PointSelectData>(FindObjectsSortMode.None);

        foreach (var group in groupedByBlock)
        {
            string blockName = group.Key;

            if (string.IsNullOrEmpty(blockName)) continue;

            Block targetBlock = blockManager.AllBlocks.FirstOrDefault(b => b.Name == blockName || (b.MatchCode != null && b.MatchCode.Contains(blockName)));

            if (targetBlock == null || targetBlock.BlockRoot == null) continue;

            Transform blockTransform = targetBlock.BlockRoot;
            List<PointPairData> deformationData = new List<PointPairData>();

            foreach (var mPoint in group)
            {
                Point dPoint = projectRoot.ProjectData.Points.Values.FirstOrDefault(p => p.GroupID == 0 && p.Name == mPoint.Name);
                if (dPoint == null) continue;

                Vector3 localDesignBaseline = blockTransform.InverseTransformPoint(dPoint.DesignPosition);
                Vector3 localMeasurePos = blockTransform.InverseTransformPoint(mPoint.MeasurePosition);

                Transform sphereTransform = null;
                foreach (var pData in allSelectablePoints)
                {
                    if (pData.point != null && pData.point.ID == mPoint.ID)
                    {
                        sphereTransform = pData.transform;
                        break;
                    }
                }

                deformationData.Add(new PointPairData(mPoint.Name, localDesignBaseline, localMeasurePos, sphereTransform));
            }

            reconstructionManager.GenerateAndDeformBlock(
                targetBlock.Name,
                blockTransform.gameObject,
                deformationData,
                exaggerationSlider != null ? exaggerationSlider.value : 1f,
                heatmapToggle != null ? heatmapToggle.isOn : false,
                maxToleranceSlider != null ? maxToleranceSlider.value : 5f
            );
        }

        Debug.Log($"<color=green>[Reconstruction] Pipeline Completed.</color>");

        // [変更] サービスロケーターからの取得に置換 (消除场景搜索)
        if (ServiceLocator.TryGet<BlockOrganizer>(out var organizer))
        {
            organizer.OrganizeIntoBlocks();
        }
    }
}
```

### File: `Scripts\UI\FeaturePanels\SliderValueDisplay.cs`
```csharp
﻿using UnityEngine;
using TMPro;
using UnityEngine.UI;

public class SliderValueDisplay : MonoBehaviour
{
    public Slider targetSlider;
    public TextMeshProUGUI valueText;
    public string suffix = ""; // 
    public string numberFormat = "F1"; // 

    void Start()
    {
        if (targetSlider != null)
        {
            // 监听滑条的拖动事件
            targetSlider.onValueChanged.AddListener(UpdateText);
            UpdateText(targetSlider.value); // 
        }
    }

    private void UpdateText(float val)
    {
        if (valueText != null)
        {
            valueText.text = val.ToString(numberFormat) + suffix;
        }
    }
}
```

### File: `Scripts\UI\Menus\FileSubMenuController.cs`
```csharp
﻿// ===============================================
// FileSubMenuController.cs
// PRODUCTION VERSION - With Global Clear Functionality
// ===============================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.IO;

public class FileSubMenuController : MonoBehaviour
{
    [Header("Button References")]
    [SerializeField] private Button btnDesignImport;
    [SerializeField] private Button btnMeasuredImport;
    [SerializeField] private Button btnClearAll;
    [SerializeField] private Button btnExecuteSVD;

    [Header("Core System References")]
    [SerializeField] private PointCSVLoader csvLoader;
    [SerializeField] private ProjectRootBehaviour projectRoot;
    [SerializeField] private PointRenderer pointRenderer;
    [SerializeField] private MacroAlignmentOrchestrator svdOrchestrator;

    private void Awake()
    {
        btnDesignImport.GetComponentInChildren<TextMeshProUGUI>().text = "Designed";
        btnMeasuredImport.GetComponentInChildren<TextMeshProUGUI>().text = "Measured";

        if (btnClearAll != null)
            btnClearAll.GetComponentInChildren<TextMeshProUGUI>().text = "Clear All";

        btnDesignImport.onClick.AddListener(OpenDesignCSV);
        btnMeasuredImport.onClick.AddListener(OpenMeasuredCSV);

        if (btnClearAll != null)
            btnClearAll.onClick.AddListener(ClearAllData);

        if (btnExecuteSVD != null)
        {
            btnExecuteSVD.onClick.AddListener(() =>
            {
                if (svdOrchestrator != null)
                {
                    Debug.Log("[UI] SVD Alignment button clicked.");
                    svdOrchestrator.ExecuteMacroAlignment();
                }
                else
                {
                    Debug.LogError("[UI] SVD Orchestrator is missing!");
                }
            });
        }
    }

    private void OpenDesignCSV()
    {
        Debug.Log("[FileSubMenuController] Design Import button clicked");
        string path = FileDialogHelper.OpenFileDialog("Select Design CSV File");
        if (!string.IsNullOrEmpty(path) && File.Exists(path))
        {
            Debug.Log($"[FileSubMenuController] Importing Design CSV: {path}");
            csvLoader.ImportDesignCSV(path);
        }
        else
        {
            Debug.LogWarning("[FileSubMenuController] No file selected or file does not exist");
        }
    }

    private void OpenMeasuredCSV()
    {
        Debug.Log("[FileSubMenuController] Measured Import button clicked");
        string path = FileDialogHelper.OpenFileDialog("Select Measured CSV File");
        if (!string.IsNullOrEmpty(path) && File.Exists(path))
        {
            Debug.Log($"[FileSubMenuController] Importing Measured CSV: {path}");
            csvLoader.ImportMeasuredCSV(path);
        }
        else
        {
            Debug.LogWarning("[FileSubMenuController] No file selected or file does not exist");
        }
    }

    /// <summary>
    /// Executes a global wipe of all imported points across the Data, 3D Scene, and UI.
    /// </summary>
    private void ClearAllData()
    {
        Debug.Log("[FileSubMenuController] Clear All process initiated...");

        // 1. Wipe core project data dictionary
        if (projectRoot != null && projectRoot.ProjectData != null)
        {
            projectRoot.ProjectData.Clear();
        }

        // 2. Wipe importer local caches
        if (csvLoader != null)
        {
            csvLoader.ClearData();
        }

        // 3. Destroy all 3D sphere GameObjects in the scene
        if (pointRenderer != null)
        {
            pointRenderer.RefreshAllPoints();
        }

        // 4. Silently command the UI Table to refresh (will clear the table rows)
        // [変更] サービスロケーターからの取得に置換
        if (ServiceLocator.TryGet<PointTableDisplay>(out var tableDisplay))
        {
            tableDisplay.RefreshTable();
        }

        Debug.Log("<color=cyan>[FileSubMenuController] Global Clear Complete. Scene is now empty.</color>");
    }
}
```

### File: `Scripts\UI\Menus\PointSubMenuController.cs`
```csharp
﻿// ===============================================
// PointSubMenuController.cs
// PRODUCTION VERSION - Independent Panel Toggles (4 Panels)
// ===============================================

using UnityEngine;
using UnityEngine.UI;

public class PointSubMenuController : MonoBehaviour
{
    [Header("Main Menu Controls")]
    public Button btnMainPointMenu;
    public GameObject subMenuContainer;

    [Header("Sub-Menu Buttons")]
    public Button btnShowOriginalPoints;
    public Button btnShowJoints;
    public Button btnShowTiePoints;
    public Button btnShowClearance; // [NEW] Clearance Button

    [Header("Target UI Panels (Data Tables)")]
    public GameObject panelOriginalPoints;
    public GameObject panelJoints;
    public GameObject panelTiePoints;
    public GameObject panelClearance; // [NEW] Clearance Panel

    [Header("UX Settings")]
    public bool autoCloseSubMenuOnSelect = true;

    private void Start()
    {
        if (subMenuContainer != null) subMenuContainer.SetActive(false);

        if (btnMainPointMenu != null)
        {
            btnMainPointMenu.onClick.RemoveAllListeners();
            btnMainPointMenu.onClick.AddListener(ToggleSubMenu);
        }

        // Independent Routing
        if (btnShowOriginalPoints != null)
            btnShowOriginalPoints.onClick.AddListener(() => ToggleIndependentPanel(panelOriginalPoints));

        if (btnShowJoints != null)
            btnShowJoints.onClick.AddListener(() => ToggleIndependentPanel(panelJoints));

        if (btnShowTiePoints != null)
            btnShowTiePoints.onClick.AddListener(() => ToggleIndependentPanel(panelTiePoints));

        // [NEW] Bind Clearance Button
        if (btnShowClearance != null)
            btnShowClearance.onClick.AddListener(() => ToggleIndependentPanel(panelClearance));
    }

    private void ToggleSubMenu()
    {
        if (subMenuContainer != null) subMenuContainer.SetActive(!subMenuContainer.activeSelf);
    }

    private void ToggleIndependentPanel(GameObject targetPanel)
    {
        if (targetPanel != null)
        {
            targetPanel.SetActive(!targetPanel.activeSelf);
        }

        if (autoCloseSubMenuOnSelect && subMenuContainer != null)
        {
            subMenuContainer.SetActive(false);
        }
    }
}
```

### File: `Scripts\UI\Widgets\ErrorLogViewer.cs`
```csharp
using UnityEngine;
using UnityEngine.UI;
using TMPro; // TextMeshPro���g�p���邽�߂̖��O���

/// <summary>
/// �S���œK���̏ڍ׃��O����M���AUI�p�l���i�X�N���[���r���[�j�ɕ\���E�Ǘ�����N���X�B
/// ������m�ۂ��邽�߂̃p�l���J�i�ŏ����j�@�\�ƁA���O�N���A�@�\�������B
/// </summary>
public class ErrorLogViewer : MonoBehaviour
{
    [Header("UI Panel References")]
    [Tooltip("���O��\�����郁�C���p�l���i�w�i�摜��X�N���[���r���[���܂ސe�I�u�W�F�N�g�j")]
    [SerializeField] private GameObject logPanel;

    [Tooltip("��ʂ̋��ɏ풓���A�N���b�N����ƃp�l�����J���{�^��")]
    [SerializeField] private Button openLogButton;

    [Header("UI Control Buttons")]
    [Tooltip("�p�l�������i�ŏ�������j���߂̃{�^��")]
    [SerializeField] private Button minimizeButton;

    [Tooltip("���݂̃��O���������ׂď�������{�^��")]
    [SerializeField] private Button clearButton;

    [Header("Text Component")]
    [Tooltip("���O�e�L�X�g��\������TextMeshPro�R���|�[�l���g")]
    [SerializeField] private TextMeshProUGUI logContentText;

    private void Awake()
    {
        // ������Ԃ̃Z�b�g�A�b�v�F���O�e�L�X�g����ɂ��A�p�l�����\���ɂ���
        if (logContentText != null)
        {
            logContentText.text = "";
        }

        ClosePanel();
    }

    private void OnEnable()
    {
        // 1. �u���b�W�X�N���v�g����̃C�x���g��M��o�^
        MultiBlockAlignmentBridge.OnDetailedLogGenerated += AppendLog;

        // 2. UI�{�^���̃N���b�N�C�x���g��o�^
        if (openLogButton != null) openLogButton.onClick.AddListener(OpenPanel);
        if (minimizeButton != null) minimizeButton.onClick.AddListener(ClosePanel);
        if (clearButton != null) clearButton.onClick.AddListener(ClearLog);
    }

    private void OnDisable()
    {
        // ���������[�N��h�����߁A�I�u�W�F�N�g���������ɃC�x���g�o�^������
        MultiBlockAlignmentBridge.OnDetailedLogGenerated -= AppendLog;

        if (openLogButton != null) openLogButton.onClick.RemoveListener(OpenPanel);
        if (minimizeButton != null) minimizeButton.onClick.RemoveListener(ClosePanel);
        if (clearButton != null) clearButton.onClick.RemoveListener(ClearLog);
    }

    /// <summary>
    /// �u���b�W�X�N���v�g�����M�����ڍ׃��O���e�L�X�g�ɒǉ�����B
    /// </summary>
    /// <param name="newLog">��M�������O������</param>
    private void AppendLog(string newLog)
    {
        if (logContentText == null) return;

        // �����̃e�L�X�g�̉��ɐV�������O��ǉ��i���s�����ށj
        logContentText.text += newLog + "\n";

        // �V�������O���͂����ۂɁA�����I�Ƀp�l�����J���ă��[�U�[�ɒʒm�������ꍇ�͈ȉ��̃R�����g�A�E�g���O��
        // OpenPanel();
    }

    /// <summary>
    /// ���O�p�l����W�J���A�J���{�^�����B���B
    /// </summary>
    private void OpenPanel()
    {
        if (logPanel != null) logPanel.SetActive(true);
        if (openLogButton != null) openLogButton.gameObject.SetActive(false);
    }

    /// <summary>
    /// ���O�p�l�����ŏ������A�J���{�^����\������B
    /// </summary>
    private void ClosePanel()
    {
        if (logPanel != null) logPanel.SetActive(false);
        if (openLogButton != null) openLogButton.gameObject.SetActive(true);
    }

    /// <summary>
    /// ���O�e�L�X�g�̓��e�����S�ɏ�������B
    /// </summary>
    private void ClearLog()
    {
        if (logContentText != null)
        {
            logContentText.text = "";
        }
    }
}
```

### File: `Scripts\UI\WorldHUD\AxisGizmoController.cs`
```csharp
// ===============================================
// AxisGizmoController.cs
// PRODUCTION VERSION - Orthographic Gizmo Synchronization
// ===============================================

using UnityEngine;

/// <summary>
/// Synchronizes the rotation of an orthographic Gizmo Camera with the Main Camera
/// to project a distortion-free 3D coordinate axis onto a UI Render Texture.
/// </summary>
[RequireComponent(typeof(Camera))]
public class AxisGizmoController : MonoBehaviour
{
    [Header("Core References")]
    [Tooltip("The main scene camera driven by the user.")]
    public Camera mainCamera;

    [Tooltip("The root transform of the 3D axis model (X/Y/Z arrows).")]
    public Transform axisModelRoot;

    [Header("Settings")]
    [Tooltip("Distance maintained between the Gizmo Camera and the Axis Model.")]
    public float cameraDistance = 5.0f;

    private Camera gizmoCamera;

    private void Start()
    {
        gizmoCamera = GetComponent<Camera>();

        if (mainCamera == null)
        {
            mainCamera = Camera.main;
        }

        // Ensure the axis model maintains absolute world rotation identity
        if (axisModelRoot != null)
        {
            axisModelRoot.rotation = Quaternion.identity;
        }
    }

    private void LateUpdate()
    {
        if (mainCamera == null || axisModelRoot == null) return;

        // 1. Perfectly mirror the main camera's rotation
        gizmoCamera.transform.rotation = mainCamera.transform.rotation;

        // 2. Position the Gizmo Camera exactly behind the Axis Model based on the new backward vector
        // This ensures the axis always remains perfectly centered in the render texture
        gizmoCamera.transform.position = axisModelRoot.position - (gizmoCamera.transform.forward * cameraDistance);
    }
}
```

### File: `Scripts\UI\WorldHUD\BillBoard.cs`
```csharp
using UnityEngine;

/// <summary>
/// Billboard - Makes the label always face the camera
/// </summary>
public class Billboard : MonoBehaviour
{
    private Transform mainCameraTransform;

    private void Start()
    {
        mainCameraTransform = Camera.main.transform;
    }

    private void LateUpdate()
    {
        if (mainCameraTransform != null)
        {
            transform.LookAt(transform.position + mainCameraTransform.rotation * Vector3.forward,
                             mainCameraTransform.rotation * Vector3.up);
        }
    }
}
```

### File: `Scripts\UI\WorldHUD\BlockCoordinateSystemDisplay.cs`
```csharp
﻿// ===============================================
// BlockCoordinateSystemDisplay.cs
// PRODUCTION VERSION - Scope Fixed & Optimized for Merged Solids
// ===============================================

using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using TMPro;

public class BlockCoordinateSystemDisplay : MonoBehaviour
{
    [Header("Coordinate System Settings")]
    [SerializeField] private float axisLength = 2000f;
    [SerializeField] private float axisThickness = 35f;
    [SerializeField] private float labelHeightOffset = 350f;

    [Header("Label Prefab (Required)")]
    [Tooltip("Drag your TextMeshPro 3D Prefab here")]
    public GameObject labelPrefab;

    private List<GameObject> activeCoordinateSystems = new List<GameObject>();

    /// <summary>
    /// Generates local coordinate systems for specified Block roots.
    /// </summary>
    public void CreateCoordinateSystems()
    {
        if (labelPrefab == null) return;

        ClearCoordinateSystems();

        if (!ServiceLocator.TryGet<BlockManager>(out var manager)) return;

        int index = 0;

        foreach (Block block in manager.AllBlocks)
        {
            if (block.BlockRoot == null) continue;
            if (!block.Name.Contains("OB") && !block.Name.Contains("OC") && !block.Name.Contains("OG")) continue;

            Vector3 center = CalculateGeometricCenter(block);

            // [変更] 既存の座標系オブジェクト群をそのまま再配置して再利用
            if (index < activeCoordinateSystems.Count)
            {
                GameObject coordRoot = activeCoordinateSystems[index];
                coordRoot.name = $"CoordSystem_{block.Name}";
                coordRoot.transform.position = center;
                coordRoot.transform.SetParent(block.BlockRoot, true);
                coordRoot.SetActive(true);
            }
            else
            {
                CreateCoordinateSystem(block, center);
            }

            index++;
        }
    }

    /// <summary>
    /// Calculates the precise geometric center of the merged Block.
    /// Safely removed the legacy AllSolids dependency.
    /// </summary>
    private Vector3 CalculateGeometricCenter(Block block)
    {
        if (block == null || block.BlockRoot == null) return Vector3.zero;

        // Since the 3D solids are merged, the BlockRoot itself (or its immediate children) 
        // holds the complete MeshRenderer. We use its exact bounding box center.
        Renderer rend = block.BlockRoot.GetComponentInChildren<Renderer>();

        if (rend != null)
        {
            return rend.bounds.center;
        }

        // Fallback in case the mesh is missing
        return block.BlockRoot.position;
    }

    private void CreateCoordinateSystem(Block block, Vector3 center)
    {
        GameObject coordRoot = new GameObject($"CoordSystem_{block.Name}");
        coordRoot.transform.position = center;
        if (block.BlockRoot != null)
            coordRoot.transform.SetParent(block.BlockRoot, true);

        coordRoot.transform.localPosition = Vector3.zero;

        CreateAxis(coordRoot.transform, Vector3.right, Color.red, "X");
        CreateAxis(coordRoot.transform, Vector3.up, Color.green, "Y");
        CreateAxis(coordRoot.transform, Vector3.forward, Color.blue, "Z");

        activeCoordinateSystems.Add(coordRoot);
    }

    private void CreateAxis(Transform parent, Vector3 direction, Color color, string labelText)
    {
        GameObject lineObj = new GameObject($"AxisLine_{labelText}");
        lineObj.transform.SetParent(parent, false);

        LineRenderer lr = lineObj.AddComponent<LineRenderer>();

        // Fallback shader logic to ensure visibility in URP
        Material lineMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        if (lineMat.shader == null) lineMat = new Material(Shader.Find("Unlit/Color"));

        lr.material = lineMat;
        lr.material.color = color;
        lr.startWidth = axisThickness;
        lr.endWidth = axisThickness;
        lr.positionCount = 2;
        lr.useWorldSpace = false;
        lr.SetPosition(0, Vector3.zero);
        lr.SetPosition(1, direction * axisLength);

        GameObject arrowHead = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        arrowHead.transform.SetParent(lineObj.transform, false);
        arrowHead.transform.localPosition = direction * axisLength;
        arrowHead.transform.localScale = new Vector3(60f, 220f, 60f);
        arrowHead.transform.rotation = Quaternion.LookRotation(direction);
        arrowHead.GetComponent<Renderer>().material.color = color;

        StartCoroutine(CreateLabelUsingPrefab(lineObj.transform, direction, labelText, color));
    }

    private IEnumerator CreateLabelUsingPrefab(Transform parent, Vector3 direction, string text, Color color)
    {
        GameObject labelGO = Instantiate(labelPrefab, parent);
        labelGO.transform.localPosition = direction * (axisLength + labelHeightOffset);
        labelGO.transform.localScale = Vector3.one * 650f;

        TextMeshPro tmp = labelGO.GetComponent<TextMeshPro>();
        if (tmp == null) tmp = labelGO.AddComponent<TextMeshPro>();

        tmp.text = text;
        tmp.color = color;
        tmp.fontSize = 1800f;
        tmp.alignment = TextAlignmentOptions.Center;
        tmp.fontStyle = FontStyles.Bold;

        yield return null;
        tmp.ForceMeshUpdate(true);
        tmp.UpdateVertexData(TMP_VertexDataUpdateFlags.All);

        labelGO.AddComponent<Billboard>();
    }

    public void ClearCoordinateSystems()
    {
        // [変更] DestroyImmediateを排除
        foreach (var sys in activeCoordinateSystems)
            if (sys != null) sys.SetActive(false);
    }

    public void ApplyGlobalScale(float factor)
    {
        axisLength *= factor;
        labelHeightOffset *= factor;
    }
}
```

### File: `Scripts\UI\WorldHUD\BlockLabelDisplay.cs`
```csharp
﻿// BlockLabelDisplay.cs (updated - for completeness)
using UnityEngine;
using TMPro;
using System.Collections.Generic;

public class BlockLabelDisplay : MonoBehaviour
{
    [Header("Label Settings")]
    [Tooltip("Drag your TextMeshPro 3D Prefab here")]
    public GameObject labelPrefab;

    [Tooltip("Height offset above the block")]
    public float heightOffset = 3000f;

    [Tooltip("Label text color")]
    public Color labelColor = Color.yellow;

    [Tooltip("Font size")]
    public float fontSize = 2500f;

    private List<GameObject> activeLabels = new List<GameObject>();

    public void CreateLabels()
    {
        if (labelPrefab == null) return;

        ClearLabels();

        if (!ServiceLocator.TryGet<BlockManager>(out var manager)) return;

        int index = 0;
        foreach (Block block in manager.AllBlocks)
        {
            if (block.BlockRoot == null) continue;

            Vector3 pos = block.BlockRoot.position + Vector3.up * heightOffset;
            GameObject labelGO;
            TextMeshPro tmp;

            // [変更] プールからの再利用
            if (index < activeLabels.Count)
            {
                labelGO = activeLabels[index];
                labelGO.transform.position = pos;
                labelGO.SetActive(true);
                tmp = labelGO.GetComponent<TextMeshPro>();
            }
            else
            {
                labelGO = Instantiate(labelPrefab, pos, Quaternion.identity);
                labelGO.AddComponent<Billboard>();
                tmp = labelGO.GetComponent<TextMeshPro>();
                activeLabels.Add(labelGO);
            }

            labelGO.name = $"Label_{block.Name}";

            if (tmp != null)
            {
                tmp.text = $"ID: {block.BlockID}\n{block.Name}";
                tmp.color = labelColor;
                tmp.fontSize = fontSize;
                tmp.alignment = TextAlignmentOptions.Center;
            }
            index++;
        }
    }

    public void ClearLabels()
    {
        // [変更] DestroyImmediateを排除し、安全に非アクティブ化
        foreach (var label in activeLabels)
            if (label != null) label.SetActive(false);
    }

    public void ToggleLabels()
    {
        if (activeLabels.Count == 0) return;
        bool visible = !activeLabels[0].activeSelf;
        foreach (var label in activeLabels)
            if (label != null) label.SetActive(visible);
    }

    public void ApplyGlobalScale(float factor)
    {
        heightOffset *= factor;
    }
}
```

### File: `Scripts\UI\WorldHUD\GizmoTextBillboard.cs`
```csharp
﻿// ===============================================
// GizmoTextBillboard.cs
// PRODUCTION VERSION - Orthographic Text Facer
// ===============================================

using UnityEngine;

/// <summary>
/// Forces 3D text to always face the rendering camera (Billboard effect).
/// Specifically optimized for the Axis Gizmo camera setup.
/// </summary>
public class GizmoTextBillboard : MonoBehaviour
{
    private Camera targetCamera;

    private void Start()
    {
        GameObject camObj = GameObject.Find("GizmoCamera");

        if (camObj != null)
        {
            targetCamera = camObj.GetComponent<Camera>();
        }
        else
        {
            targetCamera = Camera.main;
        }
    }

    private void LateUpdate()
    {
        if (targetCamera != null)
        {
            transform.rotation = targetCamera.transform.rotation;
        }
    }
}
```

### File: `Scripts\UI\WorldHUD\PointInfoDisplay.cs`
```csharp
﻿// ===============================================
// PointInfoDisplay.cs
// PRODUCTION VERSION - Dynamic Visual Target Anchoring & Global RMS
// ===============================================

using TMPro;
using UnityEngine;
using UnityEngine.UI;
using System.Collections.Generic;
using System.Linq;

[RequireComponent(typeof(CanvasGroup))]
public class PointInfoDisplay : MonoBehaviour
{
    [Header("Single Point UI Reference")]
    [SerializeField] private TextMeshProUGUI infoText;
    [SerializeField] private Vector2 panelOffset = new Vector2(100f, 100f);

    [Header("Global Error Mode Settings (全点誤差表示)")]
    [Tooltip("Assign a UI Text element pinned to the screen (e.g., top-right) to show RMS.")]
    [SerializeField] private TextMeshProUGUI globalRmsText;
    [Tooltip("How high above the point the 3D error label should float.")]
    [SerializeField] private float labelVerticalOffset = 30f;
    [Tooltip("Font size for the 3D error labels.")]
    [SerializeField] private float labelFontSize = 100f;
    [SerializeField] private Color errorLabelColor = Color.yellow;

    private Point currentPoint;

    // [NEW] Tracks the actual physical object in the scene for UI anchoring
    private Transform currentVisualTarget;

    private CanvasGroup canvasGroup;
    private ClearanceManager clearanceManager;
    private Camera mainCamera;
    private RectTransform myRect;
    private RectTransform parentRect;
    private Canvas parentCanvas;
    private RectTransform lineRect;

    private bool isGlobalErrorMode = false;
    private List<GameObject> activeErrorLabels = new List<GameObject>();

    private void Awake()
    {
        canvasGroup = GetComponent<CanvasGroup>();

        // [変更] サービスロケーター経由でClearanceManagerを取得
        ServiceLocator.TryGet(out clearanceManager);

        mainCamera = Camera.main;

        myRect = GetComponent<RectTransform>();
        if (transform.parent != null) parentRect = transform.parent.GetComponent<RectTransform>();
        parentCanvas = GetComponentInParent<Canvas>();

        if (infoText != null)
        {
            RectTransform txtRect = infoText.rectTransform;
            txtRect.anchorMin = new Vector2(0.5f, 0.5f);
            txtRect.anchorMax = new Vector2(0.5f, 0.5f);
            txtRect.pivot = new Vector2(0f, 0.5f);
            txtRect.anchoredPosition = Vector2.zero;
        }

        if (globalRmsText != null) globalRmsText.gameObject.SetActive(false);

        SetupLeaderLine();
        Hide();
    }

    private void SetupLeaderLine()
    {
        GameObject lineObj = new GameObject("InfoLeaderLine");
        lineObj.transform.SetParent(this.transform, false);
        lineObj.transform.SetAsFirstSibling();

        Image img = lineObj.AddComponent<Image>();
        img.color = new Color(1f, 1f, 1f, 0.5f);

        lineRect = lineObj.GetComponent<RectTransform>();
        lineRect.anchorMin = new Vector2(0.5f, 0.5f);
        lineRect.anchorMax = new Vector2(0.5f, 0.5f);
        lineRect.pivot = new Vector2(0f, 0.5f);
    }

    private void OnEnable() => ClearanceManager.OnClearanceUpdated += HandleGlobalUpdate;
    private void OnDisable() => ClearanceManager.OnClearanceUpdated -= HandleGlobalUpdate;

    private void HandleGlobalUpdate(List<Point> allPoints)
    {
        if (currentPoint != null && canvasGroup.alpha > 0) RefreshInfoText();
    }

    public void ToggleGlobalErrorMode(bool isOn)
    {
        isGlobalErrorMode = isOn;

        if (globalRmsText != null) globalRmsText.gameObject.SetActive(isOn);

        if (currentPoint != null && canvasGroup.alpha > 0) RefreshInfoText();

        // [変更] 破壊(Destroy)せずに非アクティブ化し、プールとして再利用する
        if (!isOn)
        {
            foreach (var lbl in activeErrorLabels)
            {
                if (lbl != null) lbl.SetActive(false);
            }
            return;
        }

        if (!ServiceLocator.TryGet<ProjectRootBehaviour>(out var projectRoot) || projectRoot.ProjectData == null) return;

        var measuredPoints = projectRoot.ProjectData.Points.Values.Where(p => p.GroupID == 1).ToList();
        if (measuredPoints.Count == 0) return;

        float sumSquaredError = 0f;
        int validCount = 0;
        int labelIndex = 0;

        foreach (var mPoint in measuredPoints)
        {
            sumSquaredError += (mPoint.ErrorDistance * mPoint.ErrorDistance);
            validCount++;

            Vector3 spawnPos = mPoint.MeasurePosition;
            if (mainCamera != null)
            {
                Vector3 dirToCam = (mainCamera.transform.position - spawnPos).normalized;
                spawnPos += (dirToCam * 20f) + new Vector3(0, labelVerticalOffset, 0);
            }

            GameObject labelObj;
            TextMeshPro tmp;

            // [変更] プールからの再利用
            if (labelIndex < activeErrorLabels.Count)
            {
                labelObj = activeErrorLabels[labelIndex];
                labelObj.name = $"ErrorLabel_{mPoint.Name}";
                labelObj.SetActive(true);
                tmp = labelObj.GetComponent<TextMeshPro>();
            }
            else
            {
                labelObj = new GameObject($"ErrorLabel_{mPoint.Name}");
                labelObj.transform.SetParent(this.transform);
                labelObj.AddComponent<Billboard>();
                tmp = labelObj.AddComponent<TextMeshPro>();
                activeErrorLabels.Add(labelObj);
            }

            labelObj.transform.position = spawnPos;
            tmp.text = $"Δ {mPoint.ErrorDistance:F3}";
            tmp.color = errorLabelColor;
            tmp.fontSize = labelFontSize;
            tmp.alignment = TextAlignmentOptions.Center;
            tmp.fontStyle = FontStyles.Bold;

            labelIndex++;
        }

        // [追加] 未使用のラベルを非表示にする
        for (int i = labelIndex; i < activeErrorLabels.Count; i++)
        {
            activeErrorLabels[i].SetActive(false);
        }

        if (validCount > 0 && globalRmsText != null)
        {
            float rms = Mathf.Sqrt(sumSquaredError / validCount);
            globalRmsText.text = $"Global RMS: {rms:F3} mm";
        }
    }

    public void RefreshInfoText()
    {
        if (currentPoint == null || infoText == null) return;

        bool isMeasured = currentPoint.GroupID == 1;
        string titleColor = isMeasured ? "#5AFF5A" : "#FF5A5A";
        bool isUnpairedDesign = (!isMeasured && currentPoint.MeasurePosition == Vector3.zero);

        if (isGlobalErrorMode)
        {
            string title = isMeasured ? "[Measured]" : "[Design]";
            string content = $"<color={titleColor}><b>{title} {currentPoint.Name}</b></color>\n";

            if (isUnpairedDesign)
                content += "Error (Δ) : -";
            else
                content += $"Error (Δ) : {currentPoint.ErrorDistance:F3} mm";

            infoText.text = content;
        }
        else
        {
            float rootGap = clearanceManager != null ? clearanceManager.GetRootGap(currentPoint.TieID) : 0f;
            string title = isMeasured ? "[Measured Point]" : "[Design Point]";

            string content = $"<color={titleColor}><b>{title}</b></color>\n" +
                             $"ID: {currentPoint.DisplayID}\n" +
                             $"Name: {currentPoint.Name}\n" +
                             $"Joint ID: {currentPoint.Joint}\n" +
                             $"Tie point ID: {currentPoint.TieID}\n" +
                             $"Root gap : {rootGap:F3}\n" +
                             $"Design: {FormatVec(currentPoint.DesignPosition)}\n";

            if (isUnpairedDesign)
            {
                content += "Measure: -\nΔ: -\nDistance: -";
            }
            else
            {
                content += $"Measure: {FormatVec(currentPoint.MeasurePosition)}\n" +
                           $"Δ {FormatVec(currentPoint.Delta)}\n" +
                           $"Distance : {currentPoint.ErrorDistance:F3}";
            }

            infoText.text = content;
        }

        infoText.ForceMeshUpdate();
    }

    private string FormatVec(Vector3 v) => $"({v.x:F1}, {v.y:F1}, {v.z:F1})";

    // =======================================================
    // [CRITICAL FIX] Added visual target tracking parameter
    // =======================================================
    public void Show(Point p, Transform visualTarget = null)
    {
        currentPoint = p;
        currentVisualTarget = visualTarget;
        RefreshInfoText();
        canvasGroup.alpha = 1;
    }

    public void Hide()
    {
        currentPoint = null;
        currentVisualTarget = null;
        canvasGroup.alpha = 0;
    }

    private void LateUpdate()
    {
        if (currentPoint == null || canvasGroup.alpha < 0.1f || mainCamera == null || parentRect == null || parentCanvas == null) return;

        // =======================================================
        // [CRITICAL FIX] WYSIWYG UI Anchoring
        // Prioritize the actual physical visual transform over the pure math data.
        // =======================================================
        Vector3 worldPos;
        if (currentVisualTarget != null)
        {
            worldPos = currentVisualTarget.position;
        }
        else
        {
            worldPos = (currentPoint.GroupID == 1) ? currentPoint.MeasurePosition : currentPoint.DesignPosition;
        }

        Vector3 screenPos = mainCamera.WorldToScreenPoint(worldPos);

        if (screenPos.z < 0)
        {
            canvasGroup.alpha = 0;
            return;
        }

        canvasGroup.alpha = 1;

        Camera camForMapping = (parentCanvas.renderMode == RenderMode.ScreenSpaceOverlay) ? null : mainCamera;

        if (RectTransformUtility.ScreenPointToLocalPointInRectangle(parentRect, screenPos, camForMapping, out Vector2 localTargetPos))
        {
            myRect.localPosition = new Vector3(localTargetPos.x + panelOffset.x, localTargetPos.y + panelOffset.y, 0f);

            if (lineRect != null)
            {
                lineRect.localPosition = Vector3.zero;

                Vector2 dir = -panelOffset;
                float distance = dir.magnitude;
                float angle = Mathf.Atan2(dir.y, dir.x) * Mathf.Rad2Deg;

                lineRect.sizeDelta = new Vector2(distance, 2f);
                lineRect.localRotation = Quaternion.Euler(0, 0, angle);
            }
        }
    }
}
```

### File: `Scripts\UI\WorldHUD\PointSelector.cs`
```csharp
﻿// ===============================================
// PointSelector.cs
// PRODUCTION VERSION - WYSIWYG Visual Transform Raycasting
// ===============================================

using UnityEngine;
using UnityEngine.EventSystems;

public class PointSelector : MonoBehaviour
{
    [Header("Raycast Settings")]
    [SerializeField] private Camera mainCamera;
    [SerializeField, Range(10f, 500f)] private float clickToleranceRadius = 80f;
    private float maxRayDistance;

    [Header("Info Display Panels")]
    [SerializeField] private PointInfoDisplay designInfoDisplay;
    [SerializeField] private PointInfoDisplay measuredInfoDisplay;

    [Header("Constraint System Integration")]
    [SerializeField] private ConstraintManager constraintManager;

    private Point currentSelectedPoint;
    private GameObject currentSelectedObj;

    private PointRenderer pointRenderer;
    private PointTableDisplay tableDisplay;

    private void Awake()
    {
        if (mainCamera == null) mainCamera = Camera.main;
        maxRayDistance = Mathf.Max(mainCamera.farClipPlane, 200000f);
    }

    private void Start()
    {
        // [変更] サービスロケーターからの取得に置換
        ServiceLocator.TryGet(out pointRenderer);
        ServiceLocator.TryGet(out tableDisplay);

        if (constraintManager == null) ServiceLocator.TryGet(out constraintManager);
    }

    private void Update()
    {
        if (Input.GetMouseButtonDown(0))
        {
            if (EventSystem.current != null && EventSystem.current.IsPointerOverGameObject()) return;

            Ray ray = mainCamera.ScreenPointToRay(Input.mousePosition);
            RaycastHit[] hits = Physics.SphereCastAll(ray, clickToleranceRadius, maxRayDistance);

            Point bestPoint = null;
            GameObject bestObj = null;
            float bestScreenDistance = 30f;
            Vector2 mousePos = Input.mousePosition;

            foreach (RaycastHit hit in hits)
            {
                PointSelectData data = hit.collider.GetComponent<PointSelectData>();
                if (data != null && data.point != null)
                {
                    // =======================================================
                    // [CRITICAL FIX] WYSIWYG Target Tracking
                    // Read the actual physical world position of the collider we hit, 
                    // completely ignoring the underlying un-exaggerated math data.
                    // =======================================================
                    Vector3 true3DPos = hit.collider.transform.position;

                    Vector3 screenPos = mainCamera.WorldToScreenPoint(true3DPos);

                    if (screenPos.z > 0)
                    {
                        float distToMouse = Vector2.Distance(mousePos, new Vector2(screenPos.x, screenPos.y));
                        if (distToMouse < bestScreenDistance)
                        {
                            bestScreenDistance = distToMouse;
                            bestPoint = data.point;
                            bestObj = hit.collider.gameObject;
                        }
                    }
                }
            }

            if (bestPoint != null && bestObj != null)
            {
                ProcessPointClick(bestPoint, bestObj);
            }
            else
            {
                if (constraintManager == null || !constraintManager.IsConstraintInputMode)
                {
                    ClearCurrentSelection();
                }
            }
        }
    }

    private void ProcessPointClick(Point clickedPoint, GameObject clickedObj)
    {
        if (constraintManager != null && constraintManager.IsConstraintInputMode)
        {
            if (clickedPoint.GroupID != 1) return;
            constraintManager.RegisterPointForConstraint(clickedPoint);
            return;
        }

        if (currentSelectedPoint == clickedPoint)
        {
            ClearCurrentSelection();
            return;
        }

        ClearCurrentSelection();
        currentSelectedPoint = clickedPoint;
        currentSelectedObj = clickedObj;

        if (pointRenderer != null)
            pointRenderer.HighlightExactObject(currentSelectedObj, clickedPoint, true, Color.yellow);

        if (tableDisplay != null) tableDisplay.HighlightRow(clickedPoint);

        // Pass the actual visual Transform to the UI to anchor the leader line correctly
        if (clickedPoint.GroupID == 0)
        {
            designInfoDisplay?.Show(clickedPoint, currentSelectedObj.transform);
            measuredInfoDisplay?.Hide();
        }
        else
        {
            measuredInfoDisplay?.Show(clickedPoint, currentSelectedObj.transform);
            designInfoDisplay?.Hide();
        }
    }

    public void ClearCurrentSelection()
    {
        if (currentSelectedPoint != null && currentSelectedObj != null && pointRenderer != null)
            pointRenderer.HighlightExactObject(currentSelectedObj, currentSelectedPoint, false, Color.white);

        designInfoDisplay?.Hide();
        measuredInfoDisplay?.Hide();
        currentSelectedPoint = null;
        currentSelectedObj = null;
    }
}
```

### File: `Scripts\Utils\MeasuredBlockGenerator.cs`
```csharp
﻿// MeasuredBlockGenerator.cs
// PRODUCTION VERSION - No forced scaling (manual top-level scale only)
// Design blocks (GroupID=0) and Measured blocks (GroupID=1) handled separately
// All Measured clones now use Default Layer (Layer 0) as requested

using UnityEngine;
using System.Collections.Generic;

public class MeasuredBlockGenerator : MonoBehaviour
{
    [Header("Selected Design Blocks (Drag exactly 2 GameObjects here)")]
    public List<GameObject> selectedDesignBlockGameObjects = new List<GameObject>();

    [Header("Noise Settings")]
    [Range(3f, 30f)]
    [Tooltip("Sigma in MILLIMETERS - applied only to Measured clones")]
    public float sigmaInMillimeters = 5f;

    [Header("References")]
    public BlockManager blockManager;
    public Material measuredMaterial;

    private System.Random random = new System.Random();
    private List<GameObject> generatedMeasuredBlocks = new List<GameObject>();

    /// <summary>
    /// Generate Measured clones of exactly 2 selected Design blocks.
    /// No extra scaling applied - use your manual 1000x on top-level parent only.
    /// </summary>
    public void GenerateMeasuredClones()
    {
        if (selectedDesignBlockGameObjects.Count != 2)
        {
            Debug.LogError("[MeasuredGenerator] Please select exactly 2 Design Block GameObjects!");
            return;
        }

        if (measuredMaterial == null)
        {
            Debug.LogError("[MeasuredGenerator] Please assign Block_Measured_Opaque.mat!");
            return;
        }

        Debug.Log("[MeasuredGenerator] Starting generation of 2 Measured Blocks (manual scale only)...");

        foreach (GameObject designGO in selectedDesignBlockGameObjects)
        {
            if (designGO == null) continue;

            float sigmaMeters = sigmaInMillimeters / 1000f;
            GameObject measuredGO = CreateMeasuredClone(designGO, sigmaMeters);
            generatedMeasuredBlocks.Add(measuredGO);

            Debug.Log($"[MeasuredGenerator] Created Measured clone of {designGO.name} with σ = {sigmaInMillimeters} mm");
        }

        // [変更] サービスロケーター経由でPointRendererの更新をトリガー
        if (ServiceLocator.TryGet<PointRenderer>(out var renderer)) renderer.RefreshAllPoints();
    }

    private GameObject CreateMeasuredClone(GameObject designGO, float sigmaMeters)
    {
        GameObject measuredGO = Instantiate(designGO);
        measuredGO.name = designGO.name + "_Measured";
        measuredGO.SetActive(true);

        if (blockManager != null)
            measuredGO.transform.SetParent(blockManager.transform);

        measuredGO.transform.rotation = Quaternion.Euler(-90f, 0f, -180f);

        // Default Layer only (Layer 0) - no Measured layer
        measuredGO.layer = 0;

        // Apply Measured material only (opaque)
        MeshRenderer[] renderers = measuredGO.GetComponentsInChildren<MeshRenderer>();
        foreach (MeshRenderer r in renderers)
            r.material = measuredMaterial;

        // NO extra scale here - your manual top-level parent scale is used
        return measuredGO;
    }

    public void ClearAllMeasuredBlocks()
    {
        Debug.Log("[MeasuredGenerator] Clearing all Measured Blocks...");
        foreach (GameObject go in generatedMeasuredBlocks)
            if (go != null) Destroy(go);
        generatedMeasuredBlocks.Clear();

        // [変更] サービスロケーター経由でPointRendererの更新をトリガー
        if (ServiceLocator.TryGet<PointRenderer>(out var renderer)) renderer.RefreshAllPoints();
        Debug.Log("[MeasuredGenerator] All Measured Blocks cleared");
    }
}
```

### File: `Scripts\Utils\Test_ConstrainedMultiBlockAlignment.cs`
```csharp

using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using LSE;

public class Test_ConstrainedMultiBlockAlignment : MonoBehaviour
{
    public string ogDesign = "OG1.json";
    public string ogMeasured = "OG1_CASE1_Z30_X45_Y170.json";
    public string ocDesign = "OC1.json";
    public string ocMeasured = "OC1_CASE1_Z30_X45_Y170.json";

    void Start()
    {
        var ogM = LoadWithId(Path.Combine(Application.streamingAssetsPath, ogMeasured));
        var ogD = LoadWithId(Path.Combine(Application.streamingAssetsPath, ogDesign));
        var ocM = LoadWithId(Path.Combine(Application.streamingAssetsPath, ocMeasured));
        var ocD = LoadWithId(Path.Combine(Application.streamingAssetsPath, ocDesign));

        var mba = new ConstrainedMultiBlockAlignment();

        mba.AddBlock("OG1",
            ToArray(ogM), ToArray(ogD),
            new int[ogM.Count, 3],
            new[] { 0, 0, 0, 0, 0, 0, 1 },
            GetIds(ogM), GetTieIds(ogM));

        mba.AddBlock("OC1",
            ToArray(ocM), ToArray(ocD),
            new int[ocM.Count, 3],
            new[] { 0, 0, 0, 0, 0, 0, 1 },
            GetIds(ocM), GetTieIds(ocM));

        mba.AddDistanceConstraintByPointId("OG1", ogM[0].id, "OC1", ocM[14].id, 10.0);

        var r = mba.Solve();
        Debug.Log($"Solve: {r.Status}, iter={r.Iterations}, maxDx={r.MaxAbsDx}, maxC={r.MaxAbsConstraint}");

        var rmsOG = mba.GetBlockRms("OG1");
        var rmsOC = mba.GetBlockRms("OC1");
        var rmsAll = mba.GetGlobalRms();

        Debug.Log($"RMS OG1: 3D={rmsOG.Rms3D}, maxAbs={rmsOG.MaxAbs}");
        Debug.Log($"RMS OC1: 3D={rmsOC.Rms3D}, maxAbs={rmsOC.MaxAbs}");
        Debug.Log($"RMS ALL: 3D={rmsAll.Rms3D}, maxAbs={rmsAll.MaxAbs}");

        var cr = mba.GetDistanceConstraintResults();
        foreach (var c in cr)
        {
            Debug.Log($"Constraint {c.BlockA}:{c.PointIdA} - {c.BlockB}:{c.PointIdB} " +
                      $"target={c.TargetDistance}, actual={c.ActualDistance}, resid={c.Residual}");
        }


        // ----- �ŏI�����ϊ��i�v�� �� �ŏI�j�̎擾�Əo�� -----

        var tfOG = mba.GetBlockTransform("OG1");
        var tfOC = mba.GetBlockTransform("OC1");

        Debug.Log(
            $"Transform OG1:\n" +
            $"  T = ({tfOG.Tx}, {tfOG.Ty}, {tfOG.Tz})\n" +
            $"  R = ({tfOG.Rx} rad, {tfOG.Ry} rad, {tfOG.Rz} rad)\n" +
            $"  S = {tfOG.Scale}"
        );

        Debug.Log(
            $"Transform OC1:\n" +
            $"  T = ({tfOC.Tx}, {tfOC.Ty}, {tfOC.Tz})\n" +
            $"  R = ({tfOC.Rx} rad, {tfOC.Ry} rad, {tfOC.Rz} rad)\n" +
            $"  S = {tfOC.Scale}"
        );

        // ----- Unity �ɓK�p����ꍇ�̗�i�Q�l�j -----

        Vector3 posOC = new Vector3(
            (float)tfOC.Tx,
            (float)tfOC.Ty,
            (float)tfOC.Tz
        );

        // LSE_alignment �̉�]������ Unity �Ƌt�Ȃ̂� - ��t����
        Quaternion rotOC = Quaternion.Euler(
            (float)(-tfOC.Rx * Mathf.Rad2Deg),
            (float)(-tfOC.Ry * Mathf.Rad2Deg),
            (float)(-tfOC.Rz * Mathf.Rad2Deg)
        );

        Vector3 scaleOC = Vector3.one * (float)tfOC.Scale;

        Debug.Log(
            $"Unity Apply OC1:\n" +
            $"  Position = {posOC}\n" +
            $"  Rotation(Euler deg) = {rotOC.eulerAngles}\n" +
            $"  Scale = {scaleOC}"
        );


    }

    // ===============================
    // JSON loader (ID�Ή�)
    // ===============================
    class LP { public int id, tie; public Vector3 p; }

    List<LP> LoadWithId(string path)
    {
        string json = File.ReadAllText(path);
        var root = JsonUtility.FromJson<BlockRoot>(json);
        var list = new List<LP>();

        foreach (var j in root.joints)
            foreach (var p in j.points)
                if (p.id != 0)
                    list.Add(new LP
                    {
                        id = (int)p.id,
                        tie = (int)p.tieId,
                        p = new Vector3((float)p.x, (float)p.y, (float)p.z)
                    });
        return list;
    }

    double[,] ToArray(List<LP> pts)
    {
        var a = new double[pts.Count, 3];
        for (int i = 0; i < pts.Count; i++)
        {
            a[i, 0] = pts[i].p.x;
            a[i, 1] = pts[i].p.y;
            a[i, 2] = pts[i].p.z;
        }
        return a;
    }

    int[] GetIds(List<LP> pts)
    {
        var a = new int[pts.Count];
        for (int i = 0; i < pts.Count; i++) a[i] = pts[i].id;
        return a;
    }

    int[] GetTieIds(List<LP> pts)
    {
        var a = new int[pts.Count];
        for (int i = 0; i < pts.Count; i++) a[i] = pts[i].tie;
        return a;
    }

    // ===============================
    // JSON schema (LOCAL)
    // ===============================
    [Serializable]
    class BlockRoot
    {
        public JointEntry[] joints;
    }

    [Serializable]
    class JointEntry
    {
        public PointEntry[] points;
    }

    [Serializable]
    class PointEntry
    {
        public long id;
        public long tieId;
        public double x, y, z;
    }
}



```

### File: `Shader\CADBlockOutlineURP.shader`
```hlsl
﻿// ===============================================
// CAD_BlockOutline_URP.shader
// PRODUCTION VERSION V9.2 - Foolproof Heatmap Toggle (Branchless)
// ===============================================

Shader "Custom/CAD_BlockOutline_URP"
{
    Properties
    {
        [MainColor] _BaseColor("Base Color", Color) = (0.2, 0.35, 0.6, 1) // Default Industrial Blue
        _Alpha("Transparency (Alpha)", Range(0.0, 1.0)) = 1.0 
        
        // [CRITICAL FIX] Standard float toggle. Removing Macro keywords to prevent Variant sync bugs.
        [Toggle] _EnableHeatmap("Enable Heatmap (Vertex Color)", Float) = 0
        
        _AmbientBoost("Ambient Brightness", Range(0.0, 1.0)) = 0.45 
        _SpecularStrength("Specular Sharpness", Range(0.0, 1.0)) = 0.5
        _RimLightPower("Rim Edge Highlight Power", Range(0.0, 5.0)) = 2.5
        [Enum(Off, 0, On, 1)] _ZWrite("Opaque/Transparent (ZWrite)", Float) = 1
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        // --- PASS 1: Forward Lit (Color & Lighting) ---
        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }

            Blend SrcAlpha OneMinusSrcAlpha
            Cull Back
            ZWrite [_ZWrite] 
            ZTest LEqual

            HLSLPROGRAM
            #pragma target 4.5
            // Ensure essential lighting macros are compiled
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            
            #pragma vertex LitVertex
            #pragma fragment LitFragment

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            // Data structure includes vertex color [頂点カラー]
            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float4 color : COLOR; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; float3 normalWS : TEXCOORD1; float4 color : COLOR; };

            CBUFFER_START(UnityPerMaterial)
                half4 _BaseColor; 
                float _Alpha; 
                float _EnableHeatmap; // Received directly as a float (0.0 or 1.0)
                float _AmbientBoost; 
                float _SpecularStrength; 
                float _RimLightPower;
            CBUFFER_END

            Varyings LitVertex(Attributes input) {
                Varyings output = (Varyings)0;
                VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);
                output.positionCS = vertexInput.positionCS;
                output.positionWS = vertexInput.positionWS; 
                output.normalWS = GetVertexNormalInputs(input.normalOS).normalWS;
                
                // Pass vertex color to fragment stage
                output.color = input.color;
                return output;
            }

            half4 LitFragment(Varyings input) : SV_Target {
                Light mainLight = GetMainLight();
                float3 normalWS = normalize(input.normalWS);
                float3 viewDirWS = normalize(_WorldSpaceCameraPos - input.positionWS);
                
                // Fallback virtual lighting if scene lacks directional light
                float3 lightColor = mainLight.color;
                float3 lightDir = mainLight.direction;
                if (length(lightColor) < 0.01) { lightColor = float3(0.7, 0.7, 0.7); lightDir = normalize(float3(0.5, 1.0, 0.5)); }

                // Calculate diffuse, specular, and rim lighting
                float NdotL = saturate(dot(normalWS, lightDir));
                float3 diffuseLight = (lightColor * NdotL * 0.7) + float3(_AmbientBoost, _AmbientBoost, _AmbientBoost);
                float NdotH = saturate(dot(normalWS, normalize(lightDir + viewDirWS)));
                float specular = pow(NdotH, 64.0) * _SpecularStrength * (NdotL > 0.0 ? 1.0 : 0.0);
                float rimLight = pow(1.0 - saturate(dot(normalWS, viewDirWS)), _RimLightPower) * 0.3;

                // ==========================================================
                // [CRITICAL FIX] Branchless Color Selection
                // If _EnableHeatmap == 0, lerp returns _BaseColor.
                // If _EnableHeatmap == 1, lerp returns input.color (Heatmap).
                // Completely immune to Shader Variant synchronization bugs.
                // ==========================================================
                float3 finalAlbedo = lerp(_BaseColor.rgb, input.color.rgb, _EnableHeatmap);

                return half4(finalAlbedo * diffuseLight + specular + rimLight, _Alpha);
            }
            ENDHLSL
        }

        // --- PASS 2: Depth Only (For Outline System) ---
        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On ColorMask 0 Cull Back
            HLSLPROGRAM
            #pragma vertex DepthOnlyVertex
            #pragma fragment DepthOnlyFragment
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; };
            Varyings DepthOnlyVertex(Attributes input) {
                Varyings output = (Varyings)0; output.positionCS = TransformObjectToHClip(input.positionOS.xyz); return output;
            }
            half4 DepthOnlyFragment(Varyings input) : SV_Target { return 0; }
            ENDHLSL
        }

        // --- PASS 3: DepthNormals (For Outline System) ---
        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            ZWrite On Cull Back
            HLSLPROGRAM
            #pragma vertex DepthNormalsVertex
            #pragma fragment DepthNormalsFragment
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 normalWS : TEXCOORD0; };
            Varyings DepthNormalsVertex(Attributes input) {
                Varyings output = (Varyings)0; output.positionCS = TransformObjectToHClip(input.positionOS.xyz); output.normalWS = TransformObjectToWorldNormal(input.normalOS); return output;
            }
            half4 DepthNormalsFragment(Varyings input) : SV_Target {
                return half4(normalize(input.normalWS), 0.0);
            }
            ENDHLSL
        }
    }
}
```

### File: `Shader\GradientSkyboxURP.shader`
```hlsl
// ============================================================
// GradientSkyboxURP.shader
// PRODUCTION VERSION - URP Compliant Procedural Gradient Skybox
// ============================================================

Shader "Custom/Gradient_Skybox_URP"
{
    Properties
    {
        [HDR] _TopColor("Top Background Color", Color) = (0.1176, 0.1176, 0.1372, 1.0)    // Default: RGB(30, 30, 35)
        [HDR] _BottomColor("Bottom Background Color", Color) = (0.1961, 0.1961, 0.2157, 1.0) // Default: RGB(50, 50, 55)
        
        _GradientExponent("Gradient Exponential Falloff", Range(0.5, 4.0)) = 1.0
        _IntensityMultiplier("Ambient Intensity Multiplier", Range(0.5, 2.0)) = 1.0
    }

    SubShader
    {
        Tags 
        { 
            "Queue" = "Background" 
            "RenderType" = "Background" 
            "PreviewType" = "Skybox" 
        }
        
        // Disable culling and depth writing for standard background rendering
        Cull Off
        ZWrite Off

        Pass
        {
            Name "StandardGradientSkyboxPass"

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct Attributes
            {
                float4 positionOS   : POSITION; // Object space position
            };

            struct Varyings
            {
                float4 positionCS   : SV_POSITION; // Clip space position
                float3 viewDirWS    : TEXCOORD0;   // World space view direction
            };

            CBUFFER_START(UnityPerMaterial)
                half4 _TopColor;
                half4 _BottomColor;
                float _GradientExponent;
                float _IntensityMultiplier;
            CBUFFER_END

            Varyings vert(Attributes input)
            {
                Varyings output = (Varyings)0;
                
                // For skybox meshes, local coordinates naturally represent structural direction vectors
                output.viewDirWS = input.positionOS.xyz;
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                
                return output;
            }

            half4 frag(Varyings input) : SV_Target
            {
                // Normalize direction to protect vector math integrity
                float3 dir = normalize(input.viewDirWS);
                
                // Map the vertical coordinate Y from local [-1.0, 1.0] to standard [0.0, 1.0] range
                float rawLerpFactor = dir.y * 0.5 + 0.5;
                
                // Apply exponential curve manipulation to shift the horizon gradient position safely
                float customLerpFactor = pow(rawLerpFactor, _GradientExponent);

                // Linearly interpolate between bottom and top colors based on verticality
                half3 finalColor = lerp(_BottomColor.rgb, _TopColor.rgb, customLerpFactor);
                
                // Scale final output color using the explicit intensity parameter
                finalColor *= _IntensityMultiplier;

                return half4(finalColor, 1.0);
            }
            ENDHLSL
        }
    }
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
```

### File: `Shader\OutlineURP.shader`
```hlsl
// Hidden/OutlineURP.shader
Shader "Hidden/OutlineURP"
{
    Properties
    {
        _OutlineColor ("Outline Color", Color) = (1,1,0,1)
        _Thickness ("Thickness", Float) = 1.0
        _DepthThreshold ("Depth Threshold", Float) = 0.08
        _NormalThreshold ("Normal Threshold", Float) = 0.35
    }

    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" }
        Pass
        {
            Name "Outline"
            ZWrite Off
            ZTest Always
            Blend SrcAlpha OneMinusSrcAlpha

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareNormalsTexture.hlsl"

            struct appdata { float4 vertex : POSITION; };
            struct v2f { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; };

            v2f vert (appdata v)
            {
                v2f o;
                o.pos = TransformObjectToHClip(v.vertex.xyz);
                o.uv = ComputeScreenPos(o.pos).xy / o.pos.w;
                return o;
            }

            float4 _OutlineColor;
            float _Thickness;
            float _DepthThreshold;
            float _NormalThreshold;

            float4 frag (v2f i) : SV_Target
            {
                float depthCenter = SampleSceneDepth(i.uv);
                float3 normalCenter = SampleSceneNormals(i.uv);

                float edge = 0.0;

                float depthLeft = SampleSceneDepth(i.uv - float2(_Thickness / _ScreenParams.x, 0));
                float depthRight = SampleSceneDepth(i.uv + float2(_Thickness / _ScreenParams.x, 0));
                float depthUp = SampleSceneDepth(i.uv - float2(0, _Thickness / _ScreenParams.y));
                float depthDown = SampleSceneDepth(i.uv + float2(0, _Thickness / _ScreenParams.y));

                if (abs(depthCenter - depthLeft) > _DepthThreshold ||
                    abs(depthCenter - depthRight) > _DepthThreshold ||
                    abs(depthCenter - depthUp) > _DepthThreshold ||
                    abs(depthCenter - depthDown) > _DepthThreshold)
                    edge = 1.0;

                if (edge == 0.0)
                {
                    float3 nLeft = SampleSceneNormals(i.uv - float2(_Thickness / _ScreenParams.x, 0));
                    if (dot(normalCenter, nLeft) < _NormalThreshold) edge = 1.0;
                }

                return edge > 0.0 ? _OutlineColor : float4(0,0,0,0);
            }
            ENDHLSL
        }
    }
}
```

### File: `Shader\Point.shader`
```hlsl
﻿Shader "Custom/CAD_Point_XRay"
{
    Properties
    {
        _BaseColor("Base Color", Color) = (1,1,1,1)

        [HDR] _EmissionColor("Emission Color", Color) = (0,0,0,0) 
        [Enum(Off, 0, On, 1)] _ZWrite("ZWrite", Float) = 0
    }
    SubShader
    {

        Tags { "RenderType"="Transparent" "Queue"="Overlay" "RenderPipeline"="UniversalPipeline" }
        Pass
        {
            ZTest LEqual
            ZWrite [_ZWrite]
            Blend SrcAlpha OneMinusSrcAlpha
            Cull Back

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct appdata { float4 vertex : POSITION; };
            struct v2f { float4 pos : SV_POSITION; };

            CBUFFER_START(UnityPerMaterial)
                half4 _BaseColor;

                half4 _EmissionColor; 
            CBUFFER_END

            v2f vert(appdata v)
            {
                v2f o;
                o.pos = TransformObjectToHClip(v.vertex.xyz);
                return o;
            }

            half4 frag(v2f i) : SV_Target
            {

                half3 finalRGB = _BaseColor.rgb + _EmissionColor.rgb;
                return half4(finalRGB, _BaseColor.a);
            }
            ENDHLSL
        }
    }
}
```

### File: `Shader\PointDesigHologram.shader`
```hlsl
﻿// ============================================================
// PointDesignHologram.shader
// PRODUCTION VERSION V2 - HDR Emission, Animated Grid & Solid Core
// ============================================================

Shader "Custom/Point_Design_Hologram_URP"
{
    Properties
    {
        // [HDR] 
        [HDR] _BaseColor("Hologram Color (HDR)", Color) = (1.5, 0.8, 1.4, 1) 
        
        _GridDensity("Grid Density (Lines)", Range(2.0, 20.0)) = 8.0
        _GridThickness("Grid Line Thickness", Range(0.01, 0.4)) = 0.15
        _RimPower("Fresnel Rim Power", Range(0.1, 4.0)) = 1.2
        
        // ---  ---
        _EmissionStrength("Emission Glow Strength", Range(1.0, 10.0)) = 3.5
        _ScrollSpeed("Grid Animation Speed", Range(-5.0, 5.0)) = 1.0
        _CoreOpacity("Solid Core Opacity", Range(0.0, 0.5)) = 0.2
    }

    SubShader
    {
        Tags 
        { 
            "RenderType" = "Transparent" 
            "Queue" = "Transparent" 
            "RenderPipeline" = "UniversalPipeline" 
        }

        Pass
        {
            Name "HologramWireframePass"
            
            // 
            ZTest LEqual
            ZWrite On
            
            // 
            Blend SrcAlpha OneMinusSrcAlpha
            Cull Back

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct Attributes
            {
                float4 positionOS   : POSITION;
                float3 normalOS     : NORMAL;
                float2 uv           : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionCS   : SV_POSITION;
                float3 normalWS     : TEXCOORD0;
                float3 viewDirWS    : TEXCOORD1;
                float2 uv           : TEXCOORD4;
            };

            CBUFFER_START(UnityPerMaterial)
                half4 _BaseColor;
                float _GridDensity;
                float _GridThickness;
                float _RimPower;
                float _EmissionStrength;
                float _ScrollSpeed;
                float _CoreOpacity;
            CBUFFER_END

            Varyings vert(Attributes input)
            {
                Varyings output = (Varyings)0;
                VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);
                VertexNormalInputs normalInput = GetVertexNormalInputs(input.normalOS);

                output.positionCS = vertexInput.positionCS;
                output.normalWS = normalInput.normalWS;
                output.uv = input.uv;
                output.viewDirWS = GetWorldSpaceViewDir(vertexInput.positionWS);

                return output;
            }

            half4 frag(Varyings input) : SV_Target
            {
                // 1. DYNAMIC GRID ANIMATION (動的グリッドアニメーション)
                float2 scrolledUV = input.uv;
                scrolledUV.y -= _Time.y * _ScrollSpeed; 

                // [CRITICAL FIX] Prevent Division by Zero in Editor Preview
                // Force a minimum thickness of 0.0001 to guarantee GPU safety
                float safeThickness = max(_GridThickness, 0.0001); 
                
                float2 grid = abs(frac(scrolledUV * _GridDensity - 0.5) - 0.5) / safeThickness;
                float lineFactor = min(grid.x, grid.y);
                float gridMask = 1.0 - min(lineFactor, 1.0);

                // 2. FRESNEL RIM GLOW (フレネル外発光)
                float3 normal = normalize(input.normalWS);
                float3 viewDir = normalize(input.viewDirWS);
                float ndotv = saturate(dot(normal, viewDir));
                float fresnelRim = pow(1.0 - ndotv, _RimPower);

                // 3. HDR EMISSION BOOSTER (HDR発光強化)

                half3 finalColor = (_BaseColor.rgb + (fresnelRim * 0.5)) * _EmissionStrength;

                // 4. SOLID CORE PRESERVATION (半透明ソリッドコア)

                float finalAlpha = saturate(max(gridMask, fresnelRim) + _CoreOpacity) * _BaseColor.a;

                // 
                if (finalAlpha < 0.01) discard;

                return half4(finalColor, finalAlpha);
            }
            ENDHLSL
        }
    }
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
```

### File: `Shader\ScreenSpaceOutlineURP.shader`
```hlsl
﻿// ===============================================
// ScreenSpaceOutlineURP.shader
// PRODUCTION VERSION V9 - Industrial CAD Precision (Anti-Aliased)
// ===============================================

Shader "Custom/ScreenSpaceOutline_URP"
{
    Properties
    {
        [Header(Industrial CAD Style)]
        _OutlineColor ("Outline Color", Color) = (0.2, 0.2, 0.25, 0.85) // 默认深灰偏蓝，非纯黑
        _OutlineScale ("Line Thickness (Strictly 1.0 - 1.5)", Range(0.5, 3.0)) = 1.0
        
        [Header(Precision Thresholds)]
        _DepthThreshold ("Depth Sensitivity", Range(0.01, 1.0)) = 0.05
        _NormalThreshold ("Normal Sensitivity (Crease Angle)", Range(0.01, 1.0)) = 0.85
    }
    
    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline" = "UniversalPipeline" }
        Cull Off ZWrite Off ZTest Always
        
        Pass
        {
            Name "ScreenSpaceOutline"
            
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment frag
            
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.core/Runtime/Utilities/Blit.hlsl" 
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareNormalsTexture.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _OutlineColor; 
                float _OutlineScale; 
                float _DepthThreshold; 
                float _NormalThreshold;
            CBUFFER_END
            
            void GetNormalAndDepth(float2 uv, out float3 normal, out float depth) 
            {
                depth = LinearEyeDepth(SampleSceneDepth(uv), _ZBufferParams); 
                normal = SampleSceneNormals(uv);
            }

            half4 frag(Varyings input) : SV_Target 
            {
                half4 originalColor = SAMPLE_TEXTURE2D_X(_BlitTexture, sampler_LinearClamp, input.texcoord);
                
                // Use exact sub-pixel offsets for razor-sharp analytical lines
                float2 texelSize = float2(1.0 / _ScreenParams.x, 1.0 / _ScreenParams.y);
                float2 offset = texelSize * max(_OutlineScale, 0.5);
                
                float dC, dU, dD, dL, dR; 
                float3 nC, nU, nD, nL, nR;
                
                GetNormalAndDepth(input.texcoord, nC, dC);
                GetNormalAndDepth(input.texcoord + float2(0, offset.y), nU, dU);
                GetNormalAndDepth(input.texcoord + float2(0, -offset.y), nD, dD);
                GetNormalAndDepth(input.texcoord + float2(-offset.x, 0), nL, dL);
                GetNormalAndDepth(input.texcoord + float2(offset.x, 0), nR, dR);

                // --- 1. Depth Edge Detection (Continuous Soft-Masking) ---
                float depthDiff = max(max(abs(dC - dU), abs(dC - dD)), max(abs(dC - dL), abs(dC - dR)));
                float dynamicDepthThreshold = _DepthThreshold * max(dC * 0.1, 1.0); 
                
                // [CRITICAL FIX] Map depth difference to an anti-aliased gradient instead of a hard binary cut
                float depthMask = saturate((depthDiff - dynamicDepthThreshold) * (20.0 / max(dC, 1.0)));
                
                // --- 2. Normal Edge Detection (Crease Gradient) ---
                float minDot = min(min(dot(nC, nU), dot(nC, nD)), min(dot(nC, nL), dot(nC, nR)));
                
                // [CRITICAL FIX] Smoothly fade crease lines based on the angle sharpness
                float normalMask = saturate((_NormalThreshold - minDot) * 8.0);
                
                if (length(nC) < 0.5) 
                {
                    normalMask = 0.0;
                }

                // --- 3. Sub-pixel Alpha Blending ---
                float edgeStrength = max(depthMask, normalMask);

                if (edgeStrength < 0.02) return originalColor;
                
                // Blend the outline over the original color using the mathematical edge strength as an alpha multiplier
                return lerp(originalColor, _OutlineColor, edgeStrength * _OutlineColor.a);
            }
            ENDHLSL
        }
    }
}
```

### File: `TextMesh Pro\Shaders\SDFFunctions.hlsl`
```hlsl
float2 UnpackUV(float uv)
{
	float2 output;
	output.x = floor(uv / 4096.0);
	output.y = uv - 4096.0 * output.x;

	return output * 0.001953125;
}

float4 BlendARGB(float4 overlying, float4 underlying)
{
	overlying.rgb *= overlying.a;
	underlying.rgb *= underlying.a;
	float3 blended = overlying.rgb + ((1 - overlying.a) * underlying.rgb);
	float alpha = underlying.a + (1 - underlying.a) * overlying.a;
	return float4(blended / alpha, alpha);
}

float3 GetSpecular(float3 n, float3 l)
{
	float spec = pow(max(0.0, dot(n, l)), _Reflectivity);
	return _SpecularColor.rgb * spec * _SpecularPower;
}

void GetSurfaceNormal_float(texture2D atlas, float textureWidth, float textureHeight, float2 uv, bool isFront, out float3 nornmal)
{
	float3 delta = float3(1.0 / textureWidth, 1.0 / textureHeight, 0.0);

	// Read "height field"
	float4 h = float4(
		SAMPLE_TEXTURE2D(atlas, SamplerState_Linear_Clamp, uv - delta.xz).a,
		SAMPLE_TEXTURE2D(atlas, SamplerState_Linear_Clamp, uv + delta.xz).a,
		SAMPLE_TEXTURE2D(atlas, SamplerState_Linear_Clamp, uv - delta.zy).a,
		SAMPLE_TEXTURE2D(atlas, SamplerState_Linear_Clamp, uv + delta.zy).a);

	bool raisedBevel = _BevelType;

	h += _BevelOffset;

	float bevelWidth = max(.01, _BevelWidth);

	// Track outline
	h -= .5;
	h /= bevelWidth;
	h = saturate(h + .5);

	if (raisedBevel) h = 1 - abs(h * 2.0 - 1.0);
	h = lerp(h, sin(h * 3.141592 / 2.0), float4(_BevelRoundness, _BevelRoundness, _BevelRoundness, _BevelRoundness));
	h = min(h, 1.0 - float4(_BevelClamp, _BevelClamp, _BevelClamp, _BevelClamp));
	h *= _BevelAmount * bevelWidth * _GradientScale * -2.0;

	float3 va = normalize(float3(-1.0, 0.0, h.y - h.x));
	float3 vb = normalize(float3(0.0, 1.0, h.w - h.z));

	float3 f = float3(1, 1, 1);
	if (isFront) f = float3(1, 1, -1);
	nornmal = cross(va, vb) * f;
}

void EvaluateLight_float(float4 faceColor, float3 n, out float4 color)
{
	n.z = abs(n.z);
	float3 light = normalize(float3(sin(_LightAngle), cos(_LightAngle), 1.0));

	float3 col = max(faceColor.rgb, 0) + GetSpecular(n, light)* faceColor.a;
	//faceColor.rgb += col * faceColor.a;
	col *= 1 - (dot(n, light) * _Diffuse);
	col *= lerp(_Ambient, 1, n.z * n.z);

	//fixed4 reflcol = texCUBE(_Cube, reflect(input.viewDir, -n));
	//faceColor.rgb += reflcol.rgb * lerp(_ReflectFaceColor.rgb, _ReflectOutlineColor.rgb, saturate(sd + outline * 0.5)) * faceColor.a;

	color = float4(col, faceColor.a);
}

// Add custom function to handle time in HDRP


//
void GenerateUV_float(float2 inUV, float4 transform, float2 animSpeed, out float2 outUV)
{
	outUV = inUV * transform.xy + transform.zw + (animSpeed * _Time.y);
}

void ComputeUVOffset_float(float texWidth, float texHeight, float2 offset, float SDR, out float2 uvOffset)
{
	uvOffset = float2(-offset.x * SDR / texWidth, -offset.y * SDR / texHeight);
}

void ScreenSpaceRatio2_float(float4x4 projection, float4 position, float2 objectScale, float screenWidth, float screenHeight, float fontScale, out float SSR)
{
	float2 pixelSize = position.w;
	pixelSize /= (objectScale * mul((float2x2)projection, float2(screenWidth, screenHeight)));
	SSR = rsqrt(dot(pixelSize, pixelSize)*2) * fontScale;
}

// UV			: Texture coordinate of the source distance field texture
// TextureSize	: Size of the source distance field texture
// Filter		: Enable perspective filter (soften)
void ScreenSpaceRatio_float(float2 UV, float TextureSize, bool Filter, out float SSR)
{
	if(Filter)
	{
		float2 a = float2(ddx(UV.x), ddy(UV.x));
		float2 b = float2(ddx(UV.y), ddy(UV.y));
		float s = lerp(dot(a,a), dot(b,b), 0.5);
		SSR = rsqrt(s) / TextureSize;
	}
	else
	{
		float s = rsqrt(abs(ddx(UV.x) * ddy(UV.y) - ddy(UV.x) * ddx(UV.y)));
		SSR = s / TextureSize;
	}
}

// SSR : Screen Space Ratio
// SD  : Signed Distance (encoded : Distance / SDR + .5)
// SDR : Signed Distance Ratio
//
// IsoPerimeter : Dilate / Contract the shape
void ComputeSDF_float(float SSR, float SD, float SDR, float isoPerimeter, float softness, out float outAlpha)
{
	softness *= SSR * SDR;
	float d = (SD - 0.5) * SDR;																				// Signed distance to edge, in Texture space
	outAlpha = saturate((d * 2.0 * SSR + 0.5 + isoPerimeter * SDR * SSR + softness * 0.5) / (1.0 + softness));	// Screen pixel coverage (alpha)
}

void ComputeSDF2_float(float SSR, float SD, float SDR, float2 isoPerimeter, float2 softness, out float2 outAlpha)
{
	softness *= SSR * SDR;
	float d = (SD - 0.5f) * SDR;
	outAlpha = saturate((d * 2.0f * SSR + 0.5f + isoPerimeter * SDR * SSR + softness * 0.5) / (1.0 + softness));
}

void ComputeSDF4_float(float SSR, float SD, float SDR, float4 isoPerimeter, float4 softness, out float4 outAlpha)
{
	softness *= SSR * SDR;
	float d = (SD - 0.5f) * SDR;
	outAlpha = saturate((d * 2.0f * SSR + 0.5f + isoPerimeter * SDR * SSR + softness * 0.5) / (1.0 + softness));
}

void ComputeSDF44_float(float SSR, float4 SD, float SDR, float4 isoPerimeter, float4 softness, bool outline, out float4 outAlpha)
{
	softness *= SSR * SDR;
	float4 d = (SD - 0.5f) * SDR;
	if(outline) d.w = max(max(d.x, d.y), d.z);
	outAlpha = saturate((d * 2.0f * SSR + 0.5f + isoPerimeter * SDR * SSR + softness * 0.5) / (1.0 + softness));
}

void Composite_float(float4 overlying, float4 underlying, out float4 outColor)
{
	outColor = BlendARGB(overlying, underlying);
}

// Face only
void Layer1_float(float alpha, float4 color0, out float4 outColor)
{
	color0.a *= alpha;
	outColor = color0;
}

// Face + 1 Outline
void Layer2_float(float2 alpha, float4 color0, float4 color1, out float4 outColor)
{
	color1.a *= alpha.y;
	color0.rgb *= color0.a; color1.rgb *= color1.a;
	outColor = lerp(color1, color0, alpha.x);
	outColor.rgb /= outColor.a;
}

// Face + 3 Outline
void Layer4_float(float4 alpha, float4 color0, float4 color1, float4 color2, float4 color3, out float4 outColor)
{
	color3.a *= alpha.w;
	color0.rgb *= color0.a; color1.rgb *= color1.a; color2.rgb *= color2.a; color3.rgb *= color3.a;
	outColor = lerp(lerp(lerp(color3, color2, alpha.z), color1, alpha.y), color0, alpha.x);
	outColor.rgb /= outColor.a;
}

```

### File: `TextMesh Pro\Shaders\TMPro.cginc`
```hlsl
float2 UnpackUV(float uv)
{ 
	float2 output;
	output.x = floor(uv / 4096);
	output.y = uv - 4096 * output.x;

	return output * 0.001953125;
}

fixed4 GetColor(half d, fixed4 faceColor, fixed4 outlineColor, half outline, half softness)
{
	half faceAlpha = 1-saturate((d - outline * 0.5 + softness * 0.5) / (1.0 + softness));
	half outlineAlpha = saturate((d + outline * 0.5)) * sqrt(min(1.0, outline));

	faceColor.rgb *= faceColor.a;
	outlineColor.rgb *= outlineColor.a;

	faceColor = lerp(faceColor, outlineColor, outlineAlpha);

	faceColor *= faceAlpha;

	return faceColor;
}

float3 GetSurfaceNormal(float4 h, float bias)
{
	bool raisedBevel = step(1, fmod(_ShaderFlags, 2));

	h += bias+_BevelOffset;

	float bevelWidth = max(.01, _OutlineWidth+_BevelWidth);

  // Track outline
	h -= .5;
	h /= bevelWidth;
	h = saturate(h+.5);

	if(raisedBevel) h = 1 - abs(h*2.0 - 1.0);
	h = lerp(h, sin(h*3.141592/2.0), _BevelRoundness);
	h = min(h, 1.0-_BevelClamp);
	h *= _Bevel * bevelWidth * _GradientScale * -2.0;

	float3 va = normalize(float3(1.0, 0.0, h.y - h.x));
	float3 vb = normalize(float3(0.0, -1.0, h.w - h.z));

	return cross(va, vb);
}

float3 GetSurfaceNormal(float2 uv, float bias, float3 delta)
{
	// Read "height field"
  float4 h = {tex2D(_MainTex, uv - delta.xz).a,
				tex2D(_MainTex, uv + delta.xz).a,
				tex2D(_MainTex, uv - delta.zy).a,
				tex2D(_MainTex, uv + delta.zy).a};

	return GetSurfaceNormal(h, bias);
}

float3 GetSpecular(float3 n, float3 l)
{
	float spec = pow(max(0.0, dot(n, l)), _Reflectivity);
	return _SpecularColor.rgb * spec * _SpecularPower;
}

float4 GetGlowColor(float d, float scale)
{
	float glow = d - (_GlowOffset*_ScaleRatioB) * 0.5 * scale;
	float t = lerp(_GlowInner, (_GlowOuter * _ScaleRatioB), step(0.0, glow)) * 0.5 * scale;
	glow = saturate(abs(glow/(1.0 + t)));
	glow = 1.0-pow(glow, _GlowPower);
	glow *= sqrt(min(1.0, t)); // Fade off glow thinner than 1 screen pixel
	return float4(_GlowColor.rgb, saturate(_GlowColor.a * glow * 2));
}

float4 BlendARGB(float4 overlying, float4 underlying)
{
	overlying.rgb *= overlying.a;
	underlying.rgb *= underlying.a;
	float3 blended = overlying.rgb + ((1-overlying.a)*underlying.rgb);
	float alpha = underlying.a + (1-underlying.a)*overlying.a;
	return float4(blended, alpha);
}


```

### File: `TextMesh Pro\Shaders\TMPro_Mobile.cginc`
```hlsl
﻿struct vertex_t
{
    UNITY_VERTEX_INPUT_INSTANCE_ID
    float4	position		: POSITION;
    float3	normal			: NORMAL;
    float4	color			: COLOR;
    float4	texcoord0		: TEXCOORD0;
    float2	texcoord1		: TEXCOORD1;
};

struct pixel_t
{
    UNITY_VERTEX_INPUT_INSTANCE_ID
    UNITY_VERTEX_OUTPUT_STEREO
    float4	position		: SV_POSITION;
    float4	faceColor		: COLOR;
    float4	outlineColor	: COLOR1;
    float4	texcoord0		: TEXCOORD0;
    float4	param			: TEXCOORD1;		// x = weight, y = no longer used
    float2	mask			: TEXCOORD2;
    #if (UNDERLAY_ON || UNDERLAY_INNER)
    float4	texcoord2		: TEXCOORD3;
    float4	underlayColor	: COLOR2;
    #endif
};

float4 SRGBToLinear(float4 rgba)
{
    return float4(lerp(rgba.rgb / 12.92f, pow((rgba.rgb + 0.055f) / 1.055f, 2.4f), step(0.04045f, rgba.rgb)), rgba.a);
}

float _UIMaskSoftnessX;
float _UIMaskSoftnessY;

pixel_t VertShader(vertex_t input)
{
    pixel_t output;

    UNITY_INITIALIZE_OUTPUT(pixel_t, output);
    UNITY_SETUP_INSTANCE_ID(input);
    UNITY_TRANSFER_INSTANCE_ID(input, output);
    UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

    float bold = step(input.texcoord0.w, 0);

    float4 vert = input.position;
    vert.x += _VertexOffsetX;
    vert.y += _VertexOffsetY;

    float4 vPosition = UnityObjectToClipPos(vert);

    float weight = lerp(_WeightNormal, _WeightBold, bold) / 4.0;
    weight = (weight + _FaceDilate) * _ScaleRatioA * 0.5;

    // Generate UV for the Masking Texture
    float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
    float2 maskUV = (vert.xy - clampedRect.xy) / (clampedRect.zw - clampedRect.xy);

    float4 color = input.color;
    #if (FORCE_LINEAR && !UNITY_COLORSPACE_GAMMA)
    color = SRGBToLinear(input.color);
    #endif

    float opacity = color.a;
    #if (UNDERLAY_ON | UNDERLAY_INNER)
    opacity = 1.0;
    #endif

    float4 faceColor = float4(color.rgb, opacity) * _FaceColor;
    faceColor.rgb *= faceColor.a;

    float4 outlineColor = _OutlineColor;
    outlineColor.a *= opacity;
    outlineColor.rgb *= outlineColor.a;

    output.position = vPosition;
    output.faceColor = faceColor;
    output.outlineColor = outlineColor;
    output.texcoord0 = float4(input.texcoord0.xy, maskUV.xy);
    output.param = float4(0.5 - weight, 0, _OutlineWidth * _ScaleRatioA * 0.5, 0);

    float2 mask = float2(0, 0);
    #if UNITY_UI_CLIP_RECT
    mask = vert.xy * 2 - clampedRect.xy - clampedRect.zw;
    #endif
    output.mask = mask;

    #if (UNDERLAY_ON || UNDERLAY_INNER)
    float4 underlayColor = _UnderlayColor;
    underlayColor.rgb *= underlayColor.a;

    float x = -(_UnderlayOffsetX * _ScaleRatioC) * _GradientScale / _TextureWidth;
    float y = -(_UnderlayOffsetY * _ScaleRatioC) * _GradientScale / _TextureHeight;

    output.texcoord2 = float4(input.texcoord0 + float2(x, y), input.color.a, 0);
    output.underlayColor = underlayColor;
    #endif

    return output;
}

float4 PixShader(pixel_t input) : SV_Target
{
    UNITY_SETUP_INSTANCE_ID(input);

    float d = tex2D(_MainTex, input.texcoord0.xy).a;

    float pixelSize = abs(ddx(input.texcoord0.y)) + abs(ddy(input.texcoord0.y));
    pixelSize *= _TextureHeight * 0.75;
    float scale = 1 / pixelSize * _GradientScale * (_Sharpness + 1);

    #if (UNDERLAY_ON | UNDERLAY_INNER)
    float layerScale = scale;
    layerScale /= 1 + ((_UnderlaySoftness * _ScaleRatioC) * layerScale);
    float layerBias = input.param.x * layerScale - .5 - ((_UnderlayDilate * _ScaleRatioC) * .5 * layerScale);
    #endif

    scale /= 1 + (_OutlineSoftness * _ScaleRatioA * scale);

    float4 faceColor = input.faceColor * saturate((d - input.param.x) * scale + 0.5);

    #if OUTLINE_ON
    float4 outlineColor = lerp(input.faceColor, input.outlineColor, sqrt(min(1.0, input.param.z * scale * 2)));
    faceColor = lerp(outlineColor, input.faceColor, saturate((d - input.param.x - input.param.z) * scale + 0.5));
    faceColor *= saturate((d - input.param.x + input.param.z) * scale + 0.5);
    #endif

    #if UNDERLAY_ON
    d = tex2D(_MainTex, input.texcoord2.xy).a * layerScale;
    faceColor += float4(_UnderlayColor.rgb * _UnderlayColor.a, _UnderlayColor.a) * saturate(d - layerBias) * (1 - faceColor.a);
    #endif

    #if UNDERLAY_INNER
    float bias = input.param.x * scale - 0.5;
    float sd = saturate(d * scale - bias - input.param.z);
    d = tex2D(_MainTex, input.texcoord2.xy).a * layerScale;
    faceColor += float4(_UnderlayColor.rgb * _UnderlayColor.a, _UnderlayColor.a) * (1 - saturate(d - layerBias)) * sd * (1 - faceColor.a);
    #endif

    #if MASKING
    float a = abs(_MaskInverse - tex2D(_MaskTex, input.texcoord0.zw).a);
    float t = a + (1 - _MaskWipeControl) * _MaskEdgeSoftness - _MaskWipeControl;
    a = saturate(t / _MaskEdgeSoftness);
    faceColor.rgb = lerp(_MaskEdgeColor.rgb * faceColor.a, faceColor.rgb, a);
    faceColor *= a;
    #endif

    // Alternative implementation to UnityGet2DClipping with support for softness
    #if UNITY_UI_CLIP_RECT
    half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
    float2 maskZW = 0.25 / (0.25 * maskSoftness + 1 / scale);
    float2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(input.mask.xy)) * maskZW);
    faceColor *= m.x * m.y;
    #endif

    #if (UNDERLAY_ON | UNDERLAY_INNER)
    faceColor *= input.texcoord2.z;
    #endif

    #if UNITY_UI_ALPHACLIP
    clip(faceColor.a - 0.001);
    #endif

    return faceColor;
}

```

### File: `TextMesh Pro\Shaders\TMPro_Properties.cginc`
```hlsl
// UI Editable properties
uniform sampler2D	_FaceTex;					// Alpha : Signed Distance
uniform float		_FaceUVSpeedX;
uniform float		_FaceUVSpeedY;
uniform fixed4		_FaceColor;					// RGBA : Color + Opacity
uniform float		_FaceDilate;				// v[ 0, 1]
uniform float		_OutlineSoftness;			// v[ 0, 1]

uniform sampler2D	_OutlineTex;				// RGBA : Color + Opacity
uniform float		_OutlineUVSpeedX;
uniform float		_OutlineUVSpeedY;
uniform fixed4		_OutlineColor;				// RGBA : Color + Opacity
uniform float		_OutlineWidth;				// v[ 0, 1]

uniform float		_Bevel;						// v[ 0, 1]
uniform float		_BevelOffset;				// v[-1, 1]
uniform float		_BevelWidth;				// v[-1, 1]
uniform float		_BevelClamp;				// v[ 0, 1]
uniform float		_BevelRoundness;			// v[ 0, 1]

uniform sampler2D	_BumpMap;					// Normal map
uniform float		_BumpOutline;				// v[ 0, 1]
uniform float		_BumpFace;					// v[ 0, 1]

uniform samplerCUBE	_Cube;						// Cube / sphere map
uniform fixed4 		_ReflectFaceColor;			// RGB intensity
uniform fixed4		_ReflectOutlineColor;
//uniform float		_EnvTiltX;					// v[-1, 1]
//uniform float		_EnvTiltY;					// v[-1, 1]
uniform float3      _EnvMatrixRotation;
uniform float4x4	_EnvMatrix;

uniform fixed4		_SpecularColor;				// RGB intensity
uniform float		_LightAngle;				// v[ 0,Tau]
uniform float		_SpecularPower;				// v[ 0, 1]
uniform float		_Reflectivity;				// v[ 5, 15]
uniform float		_Diffuse;					// v[ 0, 1]
uniform float		_Ambient;					// v[ 0, 1]

uniform fixed4		_UnderlayColor;				// RGBA : Color + Opacity
uniform float		_UnderlayOffsetX;			// v[-1, 1]
uniform float		_UnderlayOffsetY;			// v[-1, 1]
uniform float		_UnderlayDilate;			// v[-1, 1]
uniform float		_UnderlaySoftness;			// v[ 0, 1]

uniform fixed4 		_GlowColor;					// RGBA : Color + Intesity
uniform float 		_GlowOffset;				// v[-1, 1]
uniform float 		_GlowOuter;					// v[ 0, 1]
uniform float 		_GlowInner;					// v[ 0, 1]
uniform float 		_GlowPower;					// v[ 1, 1/(1+4*4)]

// API Editable properties
uniform float 		_ShaderFlags;
uniform float		_WeightNormal;
uniform float		_WeightBold;

uniform float		_ScaleRatioA;
uniform float		_ScaleRatioB;
uniform float		_ScaleRatioC;

uniform float		_VertexOffsetX;
uniform float		_VertexOffsetY;

//uniform float		_UseClipRect;
uniform float		_MaskID;
uniform sampler2D	_MaskTex;
uniform float4		_MaskCoord;
uniform float4		_ClipRect;	// bottom left(x,y) : top right(z,w)
uniform float		_MaskSoftnessX;
uniform float		_MaskSoftnessY;

// Font Atlas properties
uniform sampler2D	_MainTex;
uniform float		_TextureWidth;
uniform float		_TextureHeight;
uniform float 		_GradientScale;
uniform float		_ScaleX;
uniform float		_ScaleY;
uniform float		_PerspectiveFilter;
uniform float		_Sharpness;

```

### File: `TextMesh Pro\Shaders\TMPro_Surface.cginc`
```hlsl
void VertShader(inout appdata_full v, out Input data)
{
	v.vertex.x += _VertexOffsetX;
	v.vertex.y += _VertexOffsetY;

	UNITY_INITIALIZE_OUTPUT(Input, data);

	float bold = step(v.texcoord.w, 0);

	// Generate normal for backface
	float3 view = ObjSpaceViewDir(v.vertex);
	v.normal *= sign(dot(v.normal, view));

#if USE_DERIVATIVE
	data.param.y = 1;
#else
	float4 vert = v.vertex;
	float4 vPosition = UnityObjectToClipPos(vert);
	float2 pixelSize = vPosition.w;

	pixelSize /= float2(_ScaleX, _ScaleY) * mul((float2x2)UNITY_MATRIX_P, _ScreenParams.xy);
	float scale = rsqrt(dot(pixelSize, pixelSize));
	scale *= abs(v.texcoord.w) * _GradientScale * (_Sharpness + 1);
	scale = lerp(scale * (1 - _PerspectiveFilter), scale, abs(dot(UnityObjectToWorldNormal(v.normal.xyz), normalize(WorldSpaceViewDir(vert)))));
	data.param.y = scale;
#endif

	data.param.x = (lerp(_WeightNormal, _WeightBold, bold) / 4.0 + _FaceDilate) * _ScaleRatioA * 0.5; //
	data.viewDirEnv = mul((float3x3)_EnvMatrix, WorldSpaceViewDir(v.vertex));
}

void PixShader(Input input, inout SurfaceOutput o)
{

#if USE_DERIVATIVE
	float2 pixelSize = float2(ddx(input.uv_MainTex.y), ddy(input.uv_MainTex.y));
	pixelSize *= _TextureWidth * .75;
	float scale = rsqrt(dot(pixelSize, pixelSize)) * _GradientScale * (_Sharpness + 1);
#else
	float scale = input.param.y;
#endif

	// Signed distance
	float c = tex2D(_MainTex, input.uv_MainTex).a;
	float sd = (.5 - c - input.param.x) * scale + .5;
	float outline = _OutlineWidth*_ScaleRatioA * scale;
	float softness = _OutlineSoftness*_ScaleRatioA * scale;

	// Color & Alpha
	float4 faceColor = _FaceColor;
	float4 outlineColor = _OutlineColor;
	faceColor *= input.color;
	outlineColor.a *= input.color.a;
	faceColor *= tex2D(_FaceTex, float2(input.uv2_FaceTex.x + _FaceUVSpeedX * _Time.y, input.uv2_FaceTex.y + _FaceUVSpeedY * _Time.y));
	outlineColor *= tex2D(_OutlineTex, float2(input.uv2_OutlineTex.x + _OutlineUVSpeedX * _Time.y, input.uv2_OutlineTex.y + _OutlineUVSpeedY * _Time.y));
	faceColor = GetColor(sd, faceColor, outlineColor, outline, softness);
	faceColor.rgb /= max(faceColor.a, 0.0001);

#if BEVEL_ON
	float3 delta = float3(1.0 / _TextureWidth, 1.0 / _TextureHeight, 0.0);

	float4 smp4x = {tex2D(_MainTex, input.uv_MainTex - delta.xz).a,
					tex2D(_MainTex, input.uv_MainTex + delta.xz).a,
					tex2D(_MainTex, input.uv_MainTex - delta.zy).a,
					tex2D(_MainTex, input.uv_MainTex + delta.zy).a };

	// Face Normal
	float3 n = GetSurfaceNormal(smp4x, input.param.x);

	// Bumpmap
	float3 bump = UnpackNormal(tex2D(_BumpMap, input.uv2_FaceTex.xy)).xyz;
	bump *= lerp(_BumpFace, _BumpOutline, saturate(sd + outline * 0.5));
	bump = lerp(float3(0, 0, 1), bump, faceColor.a);
	n = normalize(n - bump);

	// Cubemap reflection
	fixed4 reflcol = texCUBE(_Cube, reflect(input.viewDirEnv, mul((float3x3)unity_ObjectToWorld, n)));
	float3 emission = reflcol.rgb * lerp(_ReflectFaceColor.rgb, _ReflectOutlineColor.rgb, saturate(sd + outline * 0.5)) * faceColor.a;
#else
	float3 n = float3(0, 0, -1);
	float3 emission = float3(0, 0, 0);
#endif

#if GLOW_ON
	float4 glowColor = GetGlowColor(sd, scale);
	glowColor.a *= input.color.a;
	emission += glowColor.rgb*glowColor.a;
	faceColor = BlendARGB(glowColor, faceColor);
	faceColor.rgb /= max(faceColor.a, 0.0001);
#endif

	// Set Standard output structure
	o.Albedo = faceColor.rgb;
	o.Normal = -n;
	o.Emission = emission;
	o.Specular = lerp(_FaceShininess, _OutlineShininess, saturate(sd + outline * 0.5));
	o.Gloss = 1;
	o.Alpha = faceColor.a;
}

```

### File: `TextMesh Pro\Shaders\TMP_Bitmap-Custom-Atlas.shader`
```hlsl
Shader "TextMeshPro/Bitmap Custom Atlas" {

Properties {
	_MainTex		    ("Font Atlas", 2D) = "white" {}
	_FaceTex		    ("Font Texture", 2D) = "white" {}
	_FaceColor	        ("Text Color", Color) = (1,1,1,1)

	_VertexOffsetX	    ("Vertex OffsetX", float) = 0
	_VertexOffsetY	    ("Vertex OffsetY", float) = 0
	_MaskSoftnessX	    ("Mask SoftnessX", float) = 0
	_MaskSoftnessY	    ("Mask SoftnessY", float) = 0

	_ClipRect		    ("Clip Rect", vector) = (-32767, -32767, 32767, 32767)
	_Padding		    ("Padding", float) = 0

	_StencilComp        ("Stencil Comparison", Float) = 8
	_Stencil            ("Stencil ID", Float) = 0
	_StencilOp          ("Stencil Operation", Float) = 0
	_StencilWriteMask   ("Stencil Write Mask", Float) = 255
	_StencilReadMask    ("Stencil Read Mask", Float) = 255

	_CullMode           ("Cull Mode", Float) = 0
	_ColorMask          ("Color Mask", Float) = 15
}

SubShader{

	Tags { "Queue" = "Transparent" "IgnoreProjector" = "True" "RenderType" = "Transparent" }

	Stencil
	{
		Ref[_Stencil]
		Comp[_StencilComp]
		Pass[_StencilOp]
		ReadMask[_StencilReadMask]
		WriteMask[_StencilWriteMask]
	}


	Lighting Off
	Cull [_CullMode]
	ZTest [unity_GUIZTestMode]
	ZWrite Off
	Fog { Mode Off }
	Blend SrcAlpha OneMinusSrcAlpha
	ColorMask[_ColorMask]

	Pass {
		CGPROGRAM
		#pragma vertex vert
		#pragma fragment frag

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP


		#include "UnityCG.cginc"
		#include "UnityUI.cginc"

		struct appdata_t
		{
			float4 vertex		: POSITION;
			fixed4 color		: COLOR;
			float4 texcoord0	: TEXCOORD0;
			float2 texcoord1	: TEXCOORD1;
		};

		struct v2f
		{
			float4	vertex		: SV_POSITION;
			fixed4	color		: COLOR;
			float2	texcoord0	: TEXCOORD0;
			float2	texcoord1	: TEXCOORD1;
			float4	mask		: TEXCOORD2;
		};

		uniform	sampler2D 	_MainTex;
		uniform	sampler2D 	_FaceTex;
		uniform float4		_FaceTex_ST;
		uniform	fixed4		_FaceColor;

		uniform float		_VertexOffsetX;
		uniform float		_VertexOffsetY;
		uniform float4		_ClipRect;
		uniform float		_MaskSoftnessX;
		uniform float		_MaskSoftnessY;
		uniform float		_UIMaskSoftnessX;
        uniform float		_UIMaskSoftnessY;
        uniform int _UIVertexColorAlwaysGammaSpace;

		v2f vert (appdata_t v)
		{
			float4 vert = v.vertex;
			vert.x += _VertexOffsetX;
			vert.y += _VertexOffsetY;

			vert.xy += (vert.w * 0.5) / _ScreenParams.xy;

			float4 vPosition = UnityPixelSnap(UnityObjectToClipPos(vert));

            if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
            {
                v.color.rgb = UIGammaToLinear(v.color.rgb);
            }
			fixed4 faceColor = v.color;
			faceColor *= _FaceColor;

			v2f OUT;
			OUT.vertex = vPosition;
			OUT.color = faceColor;
			OUT.texcoord0 = v.texcoord0;
			OUT.texcoord1 = TRANSFORM_TEX(v.texcoord1, _FaceTex);
			float2 pixelSize = vPosition.w;
			pixelSize /= abs(float2(_ScreenParams.x * UNITY_MATRIX_P[0][0], _ScreenParams.y * UNITY_MATRIX_P[1][1]));

			// Clamp _ClipRect to 16bit.
			const float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
			const half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
			OUT.mask = float4(vert.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * maskSoftness + pixelSize.xy));

			return OUT;
		}

		fixed4 frag (v2f IN) : SV_Target
		{
			fixed4 color = tex2D(_MainTex, IN.texcoord0) * tex2D(_FaceTex, IN.texcoord1) * IN.color;

			// Alternative implementation to UnityGet2DClipping with support for softness.
			#if UNITY_UI_CLIP_RECT
				half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(IN.mask.xy)) * IN.mask.zw);
				color *= m.x * m.y;
			#endif

			#if UNITY_UI_ALPHACLIP
				clip(color.a - 0.001);
			#endif

			return color;
		}
		ENDCG
	}
}

	CustomEditor "TMPro.EditorUtilities.TMP_BitmapShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_Bitmap-Mobile.shader`
```hlsl
Shader "TextMeshPro/Mobile/Bitmap" {

Properties {
	_MainTex		    ("Font Atlas", 2D) = "white" {}
	_Color		        ("Text Color", Color) = (1,1,1,1)
	_DiffusePower	    ("Diffuse Power", Range(1.0,4.0)) = 1.0

	_VertexOffsetX      ("Vertex OffsetX", float) = 0
	_VertexOffsetY      ("Vertex OffsetY", float) = 0
	_MaskSoftnessX      ("Mask SoftnessX", float) = 0
	_MaskSoftnessY      ("Mask SoftnessY", float) = 0

	_ClipRect           ("Clip Rect", vector) = (-32767, -32767, 32767, 32767)

	_StencilComp        ("Stencil Comparison", Float) = 8
	_Stencil            ("Stencil ID", Float) = 0
	_StencilOp          ("Stencil Operation", Float) = 0
	_StencilWriteMask   ("Stencil Write Mask", Float) = 255
	_StencilReadMask    ("Stencil Read Mask", Float) = 255

	_CullMode           ("Cull Mode", Float) = 0
	_ColorMask          ("Color Mask", Float) = 15
}

SubShader {

	Tags { "Queue"="Transparent" "IgnoreProjector"="True" "RenderType"="Transparent" }

	Stencil
	{
		Ref[_Stencil]
		Comp[_StencilComp]
		Pass[_StencilOp]
		ReadMask[_StencilReadMask]
		WriteMask[_StencilWriteMask]
	}


	Lighting Off
	Cull [_CullMode]
	ZTest [unity_GUIZTestMode]
	ZWrite Off
	Fog { Mode Off }
	Blend SrcAlpha OneMinusSrcAlpha
	ColorMask[_ColorMask]

	Pass {
		CGPROGRAM
		#pragma vertex vert
		#pragma fragment frag
		#pragma fragmentoption ARB_precision_hint_fastest

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP


		#include "UnityCG.cginc"
		#include "UnityUI.cginc"

		struct appdata_t
		{
			float4 vertex : POSITION;
			fixed4 color : COLOR;
			float2 texcoord0 : TEXCOORD0;
			float2 texcoord1 : TEXCOORD1;
		};

		struct v2f
		{
			float4 vertex		: POSITION;
			fixed4 color		: COLOR;
			float2 texcoord0	: TEXCOORD0;
			float4 mask			: TEXCOORD2;
		};

		sampler2D 	_MainTex;
		fixed4		_Color;
		float		_DiffusePower;

		uniform float		_VertexOffsetX;
		uniform float		_VertexOffsetY;
		uniform float4		_ClipRect;
		uniform float		_MaskSoftnessX;
		uniform float		_MaskSoftnessY;
		uniform float		_UIMaskSoftnessX;
        uniform float		_UIMaskSoftnessY;
        uniform int _UIVertexColorAlwaysGammaSpace;

		v2f vert (appdata_t v)
		{
			v2f OUT;
			float4 vert = v.vertex;
			vert.x += _VertexOffsetX;
			vert.y += _VertexOffsetY;

			vert.xy += (vert.w * 0.5) / _ScreenParams.xy;
            if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
            {
                v.color.rgb = UIGammaToLinear(v.color.rgb);
            }
            OUT.vertex = UnityPixelSnap(UnityObjectToClipPos(vert));
			OUT.color = v.color;
			OUT.color *= _Color;
			OUT.color.rgb *= _DiffusePower;
			OUT.texcoord0 = v.texcoord0;

			float2 pixelSize = OUT.vertex.w;
			//pixelSize /= abs(float2(_ScreenParams.x * UNITY_MATRIX_P[0][0], _ScreenParams.y * UNITY_MATRIX_P[1][1]));

			// Clamp _ClipRect to 16bit.
			const float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
			const half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
			OUT.mask = float4(vert.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * maskSoftness + pixelSize.xy));

			return OUT;
		}

		fixed4 frag (v2f IN) : COLOR
		{
			fixed4 color = fixed4(IN.color.rgb, IN.color.a * tex2D(_MainTex, IN.texcoord0).a);

			// Alternative implementation to UnityGet2DClipping with support for softness.
			#if UNITY_UI_CLIP_RECT
				half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(IN.mask.xy)) * IN.mask.zw);
				color *= m.x * m.y;
			#endif

			#if UNITY_UI_ALPHACLIP
				clip(color.a - 0.001);
			#endif

			return color;
		}
		ENDCG
	}
}

SubShader {
	Tags { "Queue"="Transparent" "IgnoreProjector"="True" "RenderType"="Transparent" }
	Lighting Off Cull Off ZTest Always ZWrite Off Fog { Mode Off }
	Blend SrcAlpha OneMinusSrcAlpha
	BindChannels {
		Bind "Color", color
		Bind "Vertex", vertex
		Bind "TexCoord", texcoord0
	}
	Pass {
		SetTexture [_MainTex] {
			constantColor [_Color] combine constant * primary, constant * texture
		}
	}
}

CustomEditor "TMPro.EditorUtilities.TMP_BitmapShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_Bitmap.shader`
```hlsl
Shader "TextMeshPro/Bitmap" {

Properties {
	_MainTex		    ("Font Atlas", 2D) = "white" {}
	_FaceTex		    ("Font Texture", 2D) = "white" {}
	_FaceColor	        ("Text Color", Color) = (1,1,1,1)

	_VertexOffsetX	    ("Vertex OffsetX", float) = 0
	_VertexOffsetY	    ("Vertex OffsetY", float) = 0
	_MaskSoftnessX	    ("Mask SoftnessX", float) = 0
	_MaskSoftnessY	    ("Mask SoftnessY", float) = 0

	_ClipRect           ("Clip Rect", vector) = (-32767, -32767, 32767, 32767)

	_StencilComp        ("Stencil Comparison", Float) = 8
	_Stencil            ("Stencil ID", Float) = 0
	_StencilOp          ("Stencil Operation", Float) = 0
	_StencilWriteMask   ("Stencil Write Mask", Float) = 255
	_StencilReadMask    ("Stencil Read Mask", Float) = 255

	_CullMode           ("Cull Mode", Float) = 0
	_ColorMask          ("Color Mask", Float) = 15
}

SubShader{

	Tags { "Queue" = "Transparent" "IgnoreProjector" = "True" "RenderType" = "Transparent" }

	Stencil
	{
		Ref[_Stencil]
		Comp[_StencilComp]
		Pass[_StencilOp]
		ReadMask[_StencilReadMask]
		WriteMask[_StencilWriteMask]
	}


	Lighting Off
	Cull [_CullMode]
	ZTest [unity_GUIZTestMode]
	ZWrite Off
	Fog { Mode Off }
	Blend SrcAlpha OneMinusSrcAlpha
	ColorMask[_ColorMask]

	Pass {
		CGPROGRAM
		#pragma vertex vert
		#pragma fragment frag

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP


		#include "UnityCG.cginc"
		#include "UnityUI.cginc"

		struct appdata_t
		{
			float4 vertex		: POSITION;
			fixed4 color		: COLOR;
			float4 texcoord0	: TEXCOORD0;
			float2 texcoord1	: TEXCOORD1;
		};

		struct v2f
		{
			float4	vertex		: SV_POSITION;
			fixed4	color		: COLOR;
			float2	texcoord0	: TEXCOORD0;
			float2	texcoord1	: TEXCOORD1;
			float4	mask		: TEXCOORD2;
		};

		uniform	sampler2D 	_MainTex;
		uniform	sampler2D 	_FaceTex;
		uniform float4		_FaceTex_ST;
		uniform	fixed4		_FaceColor;

		uniform float		_VertexOffsetX;
		uniform float		_VertexOffsetY;
		uniform float4		_ClipRect;
		uniform float		_MaskSoftnessX;
		uniform float		_MaskSoftnessY;
		uniform float		_UIMaskSoftnessX;
        uniform float		_UIMaskSoftnessY;
        uniform int _UIVertexColorAlwaysGammaSpace;

		v2f vert (appdata_t v)
		{
			float4 vert = v.vertex;
			vert.x += _VertexOffsetX;
			vert.y += _VertexOffsetY;

			vert.xy += (vert.w * 0.5) / _ScreenParams.xy;

			float4 vPosition = UnityPixelSnap(UnityObjectToClipPos(vert));

            if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
            {
                v.color.rgb = UIGammaToLinear(v.color.rgb);
            }
			fixed4 faceColor = v.color;
			faceColor *= _FaceColor;

			v2f OUT;
			OUT.vertex = vPosition;
			OUT.color = faceColor;
			OUT.texcoord0 = v.texcoord0;
			OUT.texcoord1 = TRANSFORM_TEX(v.texcoord1, _FaceTex);
			float2 pixelSize = vPosition.w;
			pixelSize /= abs(float2(_ScreenParams.x * UNITY_MATRIX_P[0][0], _ScreenParams.y * UNITY_MATRIX_P[1][1]));

			// Clamp _ClipRect to 16bit.
			const float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
			const half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
			OUT.mask = float4(vert.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * maskSoftness + pixelSize.xy));

			return OUT;
		}

		fixed4 frag (v2f IN) : SV_Target
		{
			fixed4 color = tex2D(_MainTex, IN.texcoord0);
			color = fixed4 (tex2D(_FaceTex, IN.texcoord1).rgb * IN.color.rgb, IN.color.a * color.a);

			// Alternative implementation to UnityGet2DClipping with support for softness.
			#if UNITY_UI_CLIP_RECT
				half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(IN.mask.xy)) * IN.mask.zw);
				color *= m.x * m.y;
			#endif

			#if UNITY_UI_ALPHACLIP
				clip(color.a - 0.001);
			#endif

			return color;
		}
		ENDCG
	}
}

	CustomEditor "TMPro.EditorUtilities.TMP_BitmapShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_SDF Overlay.shader`
```hlsl
Shader "TextMeshPro/Distance Field Overlay" {

Properties {
	_FaceTex			("Face Texture", 2D) = "white" {}
	_FaceUVSpeedX		("Face UV Speed X", Range(-5, 5)) = 0.0
	_FaceUVSpeedY		("Face UV Speed Y", Range(-5, 5)) = 0.0
	_FaceColor		    ("Face Color", Color) = (1,1,1,1)
	_FaceDilate			("Face Dilate", Range(-1,1)) = 0

	_OutlineColor	    ("Outline Color", Color) = (0,0,0,1)
	_OutlineTex			("Outline Texture", 2D) = "white" {}
	_OutlineUVSpeedX	("Outline UV Speed X", Range(-5, 5)) = 0.0
	_OutlineUVSpeedY	("Outline UV Speed Y", Range(-5, 5)) = 0.0
	_OutlineWidth		("Outline Thickness", Range(0, 1)) = 0
	_OutlineSoftness	("Outline Softness", Range(0,1)) = 0

	_Bevel				("Bevel", Range(0,1)) = 0.5
	_BevelOffset		("Bevel Offset", Range(-0.5,0.5)) = 0
	_BevelWidth			("Bevel Width", Range(-.5,0.5)) = 0
	_BevelClamp			("Bevel Clamp", Range(0,1)) = 0
	_BevelRoundness		("Bevel Roundness", Range(0,1)) = 0

	_LightAngle			("Light Angle", Range(0.0, 6.2831853)) = 3.1416
	_SpecularColor	    ("Specular", Color) = (1,1,1,1)
	_SpecularPower		("Specular", Range(0,4)) = 2.0
	_Reflectivity		("Reflectivity", Range(5.0,15.0)) = 10
	_Diffuse			("Diffuse", Range(0,1)) = 0.5
	_Ambient			("Ambient", Range(1,0)) = 0.5

	_BumpMap 			("Normal map", 2D) = "bump" {}
	_BumpOutline		("Bump Outline", Range(0,1)) = 0
	_BumpFace			("Bump Face", Range(0,1)) = 0

	_ReflectFaceColor	("Reflection Color", Color) = (0,0,0,1)
	_ReflectOutlineColor("Reflection Color", Color) = (0,0,0,1)
	_Cube 				("Reflection Cubemap", Cube) = "black" { /* TexGen CubeReflect */ }
	_EnvMatrixRotation	("Texture Rotation", vector) = (0, 0, 0, 0)


	_UnderlayColor	    ("Border Color", Color) = (0,0,0, 0.5)
	_UnderlayOffsetX	("Border OffsetX", Range(-1,1)) = 0
	_UnderlayOffsetY	("Border OffsetY", Range(-1,1)) = 0
	_UnderlayDilate		("Border Dilate", Range(-1,1)) = 0
	_UnderlaySoftness	("Border Softness", Range(0,1)) = 0

	_GlowColor		    ("Color", Color) = (0, 1, 0, 0.5)
	_GlowOffset			("Offset", Range(-1,1)) = 0
	_GlowInner			("Inner", Range(0,1)) = 0.05
	_GlowOuter			("Outer", Range(0,1)) = 0.05
	_GlowPower			("Falloff", Range(1, 0)) = 0.75

	_WeightNormal		("Weight Normal", float) = 0
	_WeightBold			("Weight Bold", float) = 0.5

	_ShaderFlags		("Flags", float) = 0
	_ScaleRatioA		("Scale RatioA", float) = 1
	_ScaleRatioB		("Scale RatioB", float) = 1
	_ScaleRatioC		("Scale RatioC", float) = 1

	_MainTex			("Font Atlas", 2D) = "white" {}
	_TextureWidth		("Texture Width", float) = 512
	_TextureHeight		("Texture Height", float) = 512
	_GradientScale		("Gradient Scale", float) = 5.0
	_ScaleX				("Scale X", float) = 1.0
	_ScaleY				("Scale Y", float) = 1.0
	_PerspectiveFilter	("Perspective Correction", Range(0, 1)) = 0.875
	_Sharpness			("Sharpness", Range(-1,1)) = 0

	_VertexOffsetX		("Vertex OffsetX", float) = 0
	_VertexOffsetY		("Vertex OffsetY", float) = 0

	_MaskCoord			("Mask Coordinates", vector) = (0, 0, 32767, 32767)
	_ClipRect			("Clip Rect", vector) = (-32767, -32767, 32767, 32767)
	_MaskSoftnessX		("Mask SoftnessX", float) = 0
	_MaskSoftnessY		("Mask SoftnessY", float) = 0

	_StencilComp		("Stencil Comparison", Float) = 8
	_Stencil			("Stencil ID", Float) = 0
	_StencilOp			("Stencil Operation", Float) = 0
	_StencilWriteMask	("Stencil Write Mask", Float) = 255
	_StencilReadMask	("Stencil Read Mask", Float) = 255

	_CullMode			("Cull Mode", Float) = 0
	_ColorMask			("Color Mask", Float) = 15
}

SubShader {

	Tags
  {
		"Queue"="Overlay"
		"IgnoreProjector"="True"
		"RenderType"="Transparent"
	}

	Stencil
	{
		Ref [_Stencil]
		Comp [_StencilComp]
		Pass [_StencilOp]
		ReadMask [_StencilReadMask]
		WriteMask [_StencilWriteMask]
	}

	Cull [_CullMode]
	ZWrite Off
	Lighting Off
	Fog { Mode Off }
	ZTest Always
	Blend One OneMinusSrcAlpha
	ColorMask [_ColorMask]

	Pass {
		CGPROGRAM
		#pragma target 3.0
		#pragma vertex VertShader
		#pragma fragment PixShader
		#pragma shader_feature __ BEVEL_ON
		#pragma shader_feature __ UNDERLAY_ON UNDERLAY_INNER
		#pragma shader_feature __ GLOW_ON

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP

		#include "UnityCG.cginc"
		#include "UnityUI.cginc"
		#include "TMPro_Properties.cginc"
		#include "TMPro.cginc"

		struct vertex_t
		{
			UNITY_VERTEX_INPUT_INSTANCE_ID
			float4	position		: POSITION;
			float3	normal			: NORMAL;
			fixed4	color			: COLOR;
			float4	texcoord0		: TEXCOORD0;
			float2	texcoord1		: TEXCOORD1;
		};

		struct pixel_t
		{
			UNITY_VERTEX_INPUT_INSTANCE_ID
			UNITY_VERTEX_OUTPUT_STEREO
			float4	position		: SV_POSITION;
			fixed4	color			: COLOR;
			float2	atlas			: TEXCOORD0;		// Atlas
			float4	param			: TEXCOORD1;		// alphaClip, scale, bias, weight
			float4	mask			: TEXCOORD2;		// Position in object space(xy), pixel Size(zw)
			float3	viewDir			: TEXCOORD3;

		    #if (UNDERLAY_ON || UNDERLAY_INNER)
			float4	texcoord2		: TEXCOORD4;		// u,v, scale, bias
			fixed4	underlayColor	: COLOR1;
		    #endif

			float4 textures			: TEXCOORD5;
		};

		// Used by Unity internally to handle Texture Tiling and Offset.
		uniform float4	_FaceTex_ST;
		uniform float4	_OutlineTex_ST;
		uniform float	_UIMaskSoftnessX;
        uniform float	_UIMaskSoftnessY;
        uniform int     _UIVertexColorAlwaysGammaSpace;

		pixel_t VertShader(vertex_t input)
		{
			pixel_t output;

			UNITY_INITIALIZE_OUTPUT(pixel_t, output);
			UNITY_SETUP_INSTANCE_ID(input);
			UNITY_TRANSFER_INSTANCE_ID(input,output);
			UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

			float bold = step(input.texcoord0.w, 0);

			float4 vert = input.position;
			vert.x += _VertexOffsetX;
			vert.y += _VertexOffsetY;

			float4 vPosition = UnityObjectToClipPos(vert);

			float2 pixelSize = vPosition.w;
			pixelSize /= float2(_ScaleX, _ScaleY) * abs(mul((float2x2)UNITY_MATRIX_P, _ScreenParams.xy));
			float scale = rsqrt(dot(pixelSize, pixelSize));
			scale *= abs(input.texcoord0.w) * _GradientScale * (_Sharpness + 1);
			if (UNITY_MATRIX_P[3][3] == 0) scale = lerp(abs(scale) * (1 - _PerspectiveFilter), scale, abs(dot(UnityObjectToWorldNormal(input.normal.xyz), normalize(WorldSpaceViewDir(vert)))));

			float weight = lerp(_WeightNormal, _WeightBold, bold) / 4.0;
			weight = (weight + _FaceDilate) * _ScaleRatioA * 0.5;

			float bias =(.5 - weight) + (.5 / scale);

			float alphaClip = (1.0 - _OutlineWidth*_ScaleRatioA - _OutlineSoftness*_ScaleRatioA);

		    #if GLOW_ON
			alphaClip = min(alphaClip, 1.0 - _GlowOffset * _ScaleRatioB - _GlowOuter * _ScaleRatioB);
		    #endif

			alphaClip = alphaClip / 2.0 - ( .5 / scale) - weight;

		    #if (UNDERLAY_ON || UNDERLAY_INNER)
			float4 underlayColor = _UnderlayColor;
			underlayColor.rgb *= underlayColor.a;

			float bScale = scale;
			bScale /= 1 + ((_UnderlaySoftness*_ScaleRatioC) * bScale);
			float bBias = (0.5 - weight) * bScale - 0.5 - ((_UnderlayDilate * _ScaleRatioC) * 0.5 * bScale);

			float x = -(_UnderlayOffsetX * _ScaleRatioC) * _GradientScale / _TextureWidth;
			float y = -(_UnderlayOffsetY * _ScaleRatioC) * _GradientScale / _TextureHeight;
			float2 bOffset = float2(x, y);
		    #endif

			// Generate UV for the Masking Texture
			float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
			float2 maskUV = (vert.xy - clampedRect.xy) / (clampedRect.zw - clampedRect.xy);

			// Support for texture tiling and offset
			float2 textureUV = input.texcoord1;
			float2 faceUV = TRANSFORM_TEX(textureUV, _FaceTex);
			float2 outlineUV = TRANSFORM_TEX(textureUV, _OutlineTex);


            if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
            {
                input.color.rgb = UIGammaToLinear(input.color.rgb);
            }
			output.position = vPosition;
			output.color = input.color;
			output.atlas =	input.texcoord0;
			output.param =	float4(alphaClip, scale, bias, weight);
			const half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
			output.mask = half4(vert.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * maskSoftness + pixelSize.xy));
			output.viewDir =	mul((float3x3)_EnvMatrix, _WorldSpaceCameraPos.xyz - mul(unity_ObjectToWorld, vert).xyz);
			#if (UNDERLAY_ON || UNDERLAY_INNER)
			output.texcoord2 = float4(input.texcoord0 + bOffset, bScale, bBias);
			output.underlayColor =	underlayColor;
			#endif
			output.textures = float4(faceUV, outlineUV);

			return output;
		}


		fixed4 PixShader(pixel_t input) : SV_Target
		{
			UNITY_SETUP_INSTANCE_ID(input);

			float c = tex2D(_MainTex, input.atlas).a;

		    #ifndef UNDERLAY_ON
			clip(c - input.param.x);
		    #endif

			float	scale	= input.param.y;
			float	bias	= input.param.z;
			float	weight	= input.param.w;
			float	sd = (bias - c) * scale;

			float outline = (_OutlineWidth * _ScaleRatioA) * scale;
			float softness = (_OutlineSoftness * _ScaleRatioA) * scale;

			half4 faceColor = _FaceColor;
			half4 outlineColor = _OutlineColor;

			faceColor.rgb *= input.color.rgb;

			faceColor *= tex2D(_FaceTex, input.textures.xy + float2(_FaceUVSpeedX, _FaceUVSpeedY) * _Time.y);
			outlineColor *= tex2D(_OutlineTex, input.textures.zw + float2(_OutlineUVSpeedX, _OutlineUVSpeedY) * _Time.y);

			faceColor = GetColor(sd, faceColor, outlineColor, outline, softness);

		    #if BEVEL_ON
			float3 dxy = float3(0.5 / _TextureWidth, 0.5 / _TextureHeight, 0);
			float3 n = GetSurfaceNormal(input.atlas, weight, dxy);

			float3 bump = UnpackNormal(tex2D(_BumpMap, input.textures.xy + float2(_FaceUVSpeedX, _FaceUVSpeedY) * _Time.y)).xyz;
			bump *= lerp(_BumpFace, _BumpOutline, saturate(sd + outline * 0.5));
			n = normalize(n- bump);

			float3 light = normalize(float3(sin(_LightAngle), cos(_LightAngle), -1.0));

			float3 col = GetSpecular(n, light);
			faceColor.rgb += col*faceColor.a;
			faceColor.rgb *= 1-(dot(n, light)*_Diffuse);
			faceColor.rgb *= lerp(_Ambient, 1, n.z*n.z);

			fixed4 reflcol = texCUBE(_Cube, reflect(input.viewDir, -n));
			faceColor.rgb += reflcol.rgb * lerp(_ReflectFaceColor.rgb, _ReflectOutlineColor.rgb, saturate(sd + outline * 0.5)) * faceColor.a;
		    #endif

		    #if UNDERLAY_ON
			float d = tex2D(_MainTex, input.texcoord2.xy).a * input.texcoord2.z;
			faceColor += input.underlayColor * saturate(d - input.texcoord2.w) * (1 - faceColor.a);
		    #endif

		    #if UNDERLAY_INNER
			float d = tex2D(_MainTex, input.texcoord2.xy).a * input.texcoord2.z;
			faceColor += input.underlayColor * (1 - saturate(d - input.texcoord2.w)) * saturate(1 - sd) * (1 - faceColor.a);
		    #endif

		    #if GLOW_ON
			float4 glowColor = GetGlowColor(sd, scale);
			faceColor.rgb += glowColor.rgb * glowColor.a;
		    #endif

		    // Alternative implementation to UnityGet2DClipping with support for softness.
		    #if UNITY_UI_CLIP_RECT
			half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(input.mask.xy)) * input.mask.zw);
			faceColor *= m.x * m.y;
		    #endif

		    #if UNITY_UI_ALPHACLIP
			clip(faceColor.a - 0.001);
		    #endif

			return faceColor * input.color.a;
		}
		ENDCG
	}
}

Fallback "TextMeshPro/Mobile/Distance Field"
CustomEditor "TMPro.EditorUtilities.TMP_SDFShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_SDF SSD.shader`
```hlsl
﻿Shader "TextMeshPro/Distance Field SSD" {

Properties {
    _FaceTex            ("Face Texture", 2D) = "white" {}
    _FaceUVSpeedX       ("Face UV Speed X", Range(-5, 5)) = 0.0
    _FaceUVSpeedY       ("Face UV Speed Y", Range(-5, 5)) = 0.0
    _FaceColor          ("Face Color", Color) = (1,1,1,1)
    _FaceDilate         ("Face Dilate", Range(-1,1)) = 0

    _OutlineColor       ("Outline Color", Color) = (0,0,0,1)
    _OutlineTex         ("Outline Texture", 2D) = "white" {}
    _OutlineUVSpeedX    ("Outline UV Speed X", Range(-5, 5)) = 0.0
    _OutlineUVSpeedY    ("Outline UV Speed Y", Range(-5, 5)) = 0.0
    _OutlineWidth       ("Outline Thickness", Range(0, 1)) = 0
    _OutlineSoftness    ("Outline Softness", Range(0,1)) = 0

    _Bevel              ("Bevel", Range(0,1)) = 0.5
    _BevelOffset        ("Bevel Offset", Range(-0.5,0.5)) = 0
    _BevelWidth         ("Bevel Width", Range(-.5,0.5)) = 0
    _BevelClamp         ("Bevel Clamp", Range(0,1)) = 0
    _BevelRoundness     ("Bevel Roundness", Range(0,1)) = 0

    _LightAngle         ("Light Angle", Range(0.0, 6.2831853)) = 3.1416
    _SpecularColor      ("Specular", Color) = (1,1,1,1)
    _SpecularPower      ("Specular", Range(0,4)) = 2.0
    _Reflectivity       ("Reflectivity", Range(5.0,15.0)) = 10
    _Diffuse            ("Diffuse", Range(0,1)) = 0.5
    _Ambient            ("Ambient", Range(1,0)) = 0.5

    _BumpMap            ("Normal map", 2D) = "bump" {}
    _BumpOutline        ("Bump Outline", Range(0,1)) = 0
    _BumpFace           ("Bump Face", Range(0,1)) = 0

    _ReflectFaceColor   ("Reflection Color", Color) = (0,0,0,1)
    _ReflectOutlineColor("Reflection Color", Color) = (0,0,0,1)
    _Cube               ("Reflection Cubemap", Cube) = "black" { /* TexGen CubeReflect */ }
    _EnvMatrixRotation  ("Texture Rotation", vector) = (0, 0, 0, 0)


    _UnderlayColor      ("Border Color", Color) = (0,0,0, 0.5)
    _UnderlayOffsetX    ("Border OffsetX", Range(-1,1)) = 0
    _UnderlayOffsetY    ("Border OffsetY", Range(-1,1)) = 0
    _UnderlayDilate     ("Border Dilate", Range(-1,1)) = 0
    _UnderlaySoftness   ("Border Softness", Range(0,1)) = 0

    _GlowColor          ("Color", Color) = (0, 1, 0, 0.5)
    _GlowOffset         ("Offset", Range(-1,1)) = 0
    _GlowInner          ("Inner", Range(0,1)) = 0.05
    _GlowOuter          ("Outer", Range(0,1)) = 0.05
    _GlowPower          ("Falloff", Range(1, 0)) = 0.75

    _WeightNormal       ("Weight Normal", float) = 0
    _WeightBold         ("Weight Bold", float) = 0.5

    _ShaderFlags        ("Flags", float) = 0
    _ScaleRatioA        ("Scale RatioA", float) = 1
    _ScaleRatioB        ("Scale RatioB", float) = 1
    _ScaleRatioC        ("Scale RatioC", float) = 1

    _MainTex            ("Font Atlas", 2D) = "white" {}
    _TextureWidth       ("Texture Width", float) = 512
    _TextureHeight      ("Texture Height", float) = 512
    _GradientScale      ("Gradient Scale", float) = 5.0
    _ScaleX             ("Scale X", float) = 1.0
    _ScaleY             ("Scale Y", float) = 1.0
    _PerspectiveFilter  ("Perspective Correction", Range(0, 1)) = 0.875
    _Sharpness          ("Sharpness", Range(-1,1)) = 0

    _VertexOffsetX      ("Vertex OffsetX", float) = 0
    _VertexOffsetY      ("Vertex OffsetY", float) = 0

    _MaskCoord          ("Mask Coordinates", vector) = (0, 0, 32767, 32767)
    _ClipRect           ("Clip Rect", vector) = (-32767, -32767, 32767, 32767)
    _MaskSoftnessX      ("Mask SoftnessX", float) = 0
    _MaskSoftnessY      ("Mask SoftnessY", float) = 0

    _StencilComp        ("Stencil Comparison", Float) = 8
    _Stencil            ("Stencil ID", Float) = 0
    _StencilOp          ("Stencil Operation", Float) = 0
    _StencilWriteMask   ("Stencil Write Mask", Float) = 255
    _StencilReadMask    ("Stencil Read Mask", Float) = 255

    _CullMode           ("Cull Mode", Float) = 0
    _ColorMask          ("Color Mask", Float) = 15
}

SubShader {
    Tags
    {
        "Queue" = "Transparent"
        "IgnoreProjector" = "True"
        "RenderType" = "Transparent"
    }

    Stencil
    {
        Ref[_Stencil]
        Comp[_StencilComp]
        Pass[_StencilOp]
        ReadMask[_StencilReadMask]
        WriteMask[_StencilWriteMask]
    }

    Cull[_CullMode]
    ZWrite Off
    Lighting Off
    Fog { Mode Off }
    ZTest[unity_GUIZTestMode]
    Blend One OneMinusSrcAlpha
    ColorMask[_ColorMask]

    Pass
    {
        CGPROGRAM
        #pragma target 3.0
        #pragma vertex VertShader
        #pragma fragment PixShader
        #pragma shader_feature __ BEVEL_ON
        #pragma shader_feature __ UNDERLAY_ON UNDERLAY_INNER
        #pragma shader_feature __ GLOW_ON
        #pragma shader_feature __ FORCE_LINEAR

        #pragma multi_compile __ UNITY_UI_CLIP_RECT
        #pragma multi_compile __ UNITY_UI_ALPHACLIP

        #include "UnityCG.cginc"
        #include "UnityUI.cginc"
        #include "TMPro_Properties.cginc"
        #include "TMPro.cginc"

        struct vertex_t
        {
            UNITY_VERTEX_INPUT_INSTANCE_ID
            float4	position        : POSITION;
            float3	normal          : NORMAL;
            float4	color           : COLOR;
            float4	texcoord0       : TEXCOORD0;
            float2	texcoord1       : TEXCOORD1;
        };

        struct pixel_t
        {
            UNITY_VERTEX_INPUT_INSTANCE_ID
            UNITY_VERTEX_OUTPUT_STEREO
            float4	position        : SV_POSITION;
            float4	color           : COLOR;
            float2	atlas           : TEXCOORD0;
            float	weight          : TEXCOORD1;
            float2	mask            : TEXCOORD2;		// Position in object space(xy)
            float3	viewDir         : TEXCOORD3;

            #if (UNDERLAY_ON || UNDERLAY_INNER)
            float2	texcoord2       : TEXCOORD4;
            float4	underlayColor   : COLOR1;
            #endif

            float4 textures         : TEXCOORD5;
        };

        // Used by Unity internally to handle Texture Tiling and Offset.
        float4 _FaceTex_ST;
        float4 _OutlineTex_ST;
        float _UIMaskSoftnessX;
        float _UIMaskSoftnessY;
        int _UIVertexColorAlwaysGammaSpace;

        float4 SRGBToLinear(float4 rgba)
        {
            return float4(lerp(rgba.rgb / 12.92f, pow((rgba.rgb + 0.055f) / 1.055f, 2.4f), step(0.04045f, rgba.rgb)), rgba.a);
        }

        pixel_t VertShader(vertex_t input)
        {
            pixel_t output;

            UNITY_INITIALIZE_OUTPUT(pixel_t, output);
            UNITY_SETUP_INSTANCE_ID(input);
            UNITY_TRANSFER_INSTANCE_ID(input,output);
            UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

            float bold = step(input.texcoord0.w, 0);

            float4 vert = input.position;
            vert.x += _VertexOffsetX;
            vert.y += _VertexOffsetY;

            float4 vPosition = UnityObjectToClipPos(vert);

            float weight = lerp(_WeightNormal, _WeightBold, bold) / 4.0;
            weight = (weight + _FaceDilate) * _ScaleRatioA * 0.5;

            #if (UNDERLAY_ON || UNDERLAY_INNER)
            float4 underlayColor = _UnderlayColor;
            underlayColor.rgb *= underlayColor.a;

            float x = -(_UnderlayOffsetX * _ScaleRatioC) * _GradientScale / _TextureWidth;
            float y = -(_UnderlayOffsetY * _ScaleRatioC) * _GradientScale / _TextureHeight;
            float2 bOffset = float2(x, y);
            #endif

            // Generate UV for the Masking Texture
            float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);

            // Support for texture tiling and offset
            float2 textureUV = input.texcoord1;
            float2 faceUV = TRANSFORM_TEX(textureUV, _FaceTex);
            float2 outlineUV = TRANSFORM_TEX(textureUV, _OutlineTex);

            if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
            {
                input.color.rgb = UIGammaToLinear(input.color.rgb);
            }
            float4 color = input.color;
            #if (FORCE_LINEAR && !UNITY_COLORSPACE_GAMMA)
            color = SRGBToLinear(input.color);
            #endif

            output.position = vPosition;
            output.color = color;
            output.atlas = input.texcoord0;
            output.weight = weight;
            output.mask = half2(vert.xy * 2 - clampedRect.xy - clampedRect.zw);
            output.viewDir = mul((float3x3)_EnvMatrix, _WorldSpaceCameraPos.xyz - mul(unity_ObjectToWorld, vert).xyz);
            #if (UNDERLAY_ON || UNDERLAY_INNER)
            output.texcoord2 = input.texcoord0 + bOffset;
            output.underlayColor = underlayColor;
            #endif
            output.textures = float4(faceUV, outlineUV);

            return output;
        }


        fixed4 PixShader(pixel_t input) : SV_Target
        {
            UNITY_SETUP_INSTANCE_ID(input);

            float c = tex2D(_MainTex, input.atlas).a;

            float pixelSize = abs(ddx(input.atlas.y)) + abs(ddy(input.atlas.y));
            pixelSize *= _TextureHeight * 0.75;
            float scale = 1 / pixelSize * _GradientScale * (_Sharpness + 1);

            float weight = input.weight;
            float bias = (.5 - weight) + (.5 / scale);
            float sd = (bias - c) * scale;

            float outline = (_OutlineWidth * _ScaleRatioA) * scale;
            float softness = (_OutlineSoftness * _ScaleRatioA) * scale;

            half4 faceColor = _FaceColor;
            half4 outlineColor = _OutlineColor;

            faceColor.rgb *= input.color.rgb;

            faceColor *= tex2D(_FaceTex, input.textures.xy + float2(_FaceUVSpeedX, _FaceUVSpeedY) * _Time.y);
            outlineColor *= tex2D(_OutlineTex, input.textures.zw + float2(_OutlineUVSpeedX, _OutlineUVSpeedY) * _Time.y);

            faceColor = GetColor(sd, faceColor, outlineColor, outline, softness);

            #if BEVEL_ON
            float3 dxy = float3(0.5 / _TextureWidth, 0.5 / _TextureHeight, 0);
            float3 n = GetSurfaceNormal(input.atlas, weight, dxy);

            float3 bump = UnpackNormal(tex2D(_BumpMap, input.textures.xy + float2(_FaceUVSpeedX, _FaceUVSpeedY) * _Time.y)).xyz;
            bump *= lerp(_BumpFace, _BumpOutline, saturate(sd + outline * 0.5));
            n = normalize(n - bump);

            float3 light = normalize(float3(sin(_LightAngle), cos(_LightAngle), -1.0));

            float3 col = GetSpecular(n, light);
            faceColor.rgb += col * faceColor.a;
            faceColor.rgb *= 1 - (dot(n, light) * _Diffuse);
            faceColor.rgb *= lerp(_Ambient, 1, n.z * n.z);

            fixed4 reflcol = texCUBE(_Cube, reflect(input.viewDir, -n));
            faceColor.rgb += reflcol.rgb * lerp(_ReflectFaceColor.rgb, _ReflectOutlineColor.rgb, saturate(sd + outline * 0.5)) * faceColor.a;
            #endif

            #if (UNDERLAY_ON || UNDERLAY_INNER)
            float bScale = scale;
            bScale /= 1 + ((_UnderlaySoftness * _ScaleRatioC) * bScale);
            float bBias = (0.5 - weight) * bScale - 0.5 - ((_UnderlayDilate * _ScaleRatioC) * 0.5 * bScale);
            #endif

            #if UNDERLAY_ON
            float d = tex2D(_MainTex, input.texcoord2.xy).a * bScale;
            faceColor += input.underlayColor * saturate(d - bBias) * (1 - faceColor.a);
            #endif

            #if UNDERLAY_INNER
            float d = tex2D(_MainTex, input.texcoord2.xy).a * bScale;
            faceColor += input.underlayColor * (1 - saturate(d - bBias)) * saturate(1 - sd) * (1 - faceColor.a);
            #endif

            #if GLOW_ON
            float4 glowColor = GetGlowColor(sd, scale);
            faceColor.rgb += glowColor.rgb * glowColor.a;
            #endif

            // Alternative implementation to UnityGet2DClipping with support for softness.
            #if UNITY_UI_CLIP_RECT
            half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
            float2 maskZW = 0.25 / (0.25 * maskSoftness + 1 / scale);
            half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(input.mask.xy)) * maskZW);
            faceColor *= m.x * m.y;
            #endif

            #if UNITY_UI_ALPHACLIP
            clip(faceColor.a - 0.001);
            #endif

            return faceColor * input.color.a;
        }
        ENDCG
    }
}

Fallback "TextMeshPro/Mobile/Distance Field"
CustomEditor "TMPro.EditorUtilities.TMP_SDFShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_SDF-Mobile Masking.shader`
```hlsl
﻿// Simplified SDF shader:
// - No Shading Option (bevel / bump / env map)
// - No Glow Option
// - Softness is applied on both side of the outline

Shader "TextMeshPro/Mobile/Distance Field - Masking" {

Properties {
	_FaceColor		    ("Face Color", Color) = (1,1,1,1)
	_FaceDilate			("Face Dilate", Range(-1,1)) = 0

	_OutlineColor	    ("Outline Color", Color) = (0,0,0,1)
	_OutlineWidth		("Outline Thickness", Range(0,1)) = 0
	_OutlineSoftness	("Outline Softness", Range(0,1)) = 0

	_UnderlayColor	    ("Border Color", Color) = (0,0,0,.5)
	_UnderlayOffsetX 	("Border OffsetX", Range(-1,1)) = 0
	_UnderlayOffsetY 	("Border OffsetY", Range(-1,1)) = 0
	_UnderlayDilate		("Border Dilate", Range(-1,1)) = 0
	_UnderlaySoftness 	("Border Softness", Range(0,1)) = 0

	_WeightNormal		("Weight Normal", float) = 0
	_WeightBold			("Weight Bold", float) = .5

	_ShaderFlags		("Flags", float) = 0
	_ScaleRatioA		("Scale RatioA", float) = 1
	_ScaleRatioB		("Scale RatioB", float) = 1
	_ScaleRatioC		("Scale RatioC", float) = 1

	_MainTex			("Font Atlas", 2D) = "white" {}
	_TextureWidth		("Texture Width", float) = 512
	_TextureHeight		("Texture Height", float) = 512
	_GradientScale		("Gradient Scale", float) = 5
	_ScaleX				("Scale X", float) = 1
	_ScaleY				("Scale Y", float) = 1
	_PerspectiveFilter	("Perspective Correction", Range(0, 1)) = 0.875
	_Sharpness			("Sharpness", Range(-1,1)) = 0

	_VertexOffsetX		("Vertex OffsetX", float) = 0
	_VertexOffsetY		("Vertex OffsetY", float) = 0

	_ClipRect			("Clip Rect", vector) = (-32767, -32767, 32767, 32767)
	_MaskSoftnessX		("Mask SoftnessX", float) = 0
	_MaskSoftnessY		("Mask SoftnessY", float) = 0
	_MaskTex			("Mask Texture", 2D) = "white" {}
	_MaskInverse		("Inverse", float) = 0
	_MaskEdgeColor		("Edge Color", Color) = (1,1,1,1)
	_MaskEdgeSoftness	("Edge Softness", Range(0, 1)) = 0.01
	_MaskWipeControl	("Wipe Position", Range(0, 1)) = 0.5

	_StencilComp		("Stencil Comparison", Float) = 8
	_Stencil			("Stencil ID", Float) = 0
	_StencilOp			("Stencil Operation", Float) = 0
	_StencilWriteMask	("Stencil Write Mask", Float) = 255
	_StencilReadMask	("Stencil Read Mask", Float) = 255

	_CullMode			("Cull Mode", Float) = 0
	_ColorMask			("Color Mask", Float) = 15
}

SubShader {
	Tags
	{
		"Queue"="Transparent"
		"IgnoreProjector"="True"
		"RenderType"="Transparent"
	}


	Stencil
	{
		Ref [_Stencil]
		Comp [_StencilComp]
		Pass [_StencilOp]
		ReadMask [_StencilReadMask]
		WriteMask [_StencilWriteMask]
	}

	Cull [_CullMode]
	ZWrite Off
	Lighting Off
	Fog { Mode Off }
	ZTest [unity_GUIZTestMode]
	Blend One OneMinusSrcAlpha
	ColorMask [_ColorMask]

	Pass {
		CGPROGRAM
		#pragma vertex VertShader
		#pragma fragment PixShader
		#pragma shader_feature __ OUTLINE_ON
		#pragma shader_feature __ UNDERLAY_ON UNDERLAY_INNER

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP


		#include "UnityCG.cginc"
		#include "UnityUI.cginc"
		#include "TMPro_Properties.cginc"

		struct vertex_t
		{
			float4	vertex			: POSITION;
			float3	normal			: NORMAL;
			fixed4	color			: COLOR;
			float4	texcoord0		: TEXCOORD0;
			float2	texcoord1		: TEXCOORD1;
		};

		struct pixel_t
		{
			float4	vertex			: SV_POSITION;
			fixed4	faceColor		: COLOR;
			fixed4	outlineColor	: COLOR1;
			float4	texcoord0		: TEXCOORD0;			// Texture UV, Mask UV
			half4	param			: TEXCOORD1;			// Scale(x), BiasIn(y), BiasOut(z), Bias(w)
			half4	mask			: TEXCOORD2;			// Position in clip space(xy), Softness(zw)

		    #if (UNDERLAY_ON | UNDERLAY_INNER)
			float4	texcoord1		: TEXCOORD3;			// Texture UV, alpha, reserved
			half2	underlayParam	: TEXCOORD4;			// Scale(x), Bias(y)
		    #endif
		};

		float _MaskWipeControl;
		float _MaskEdgeSoftness;
		fixed4 _MaskEdgeColor;
		bool _MaskInverse;
		float _UIMaskSoftnessX;
        float _UIMaskSoftnessY;
        int _UIVertexColorAlwaysGammaSpace;

		pixel_t VertShader(vertex_t input)
		{
			float bold = step(input.texcoord0.w, 0);

			float4 vert = input.vertex;
			vert.x += _VertexOffsetX;
			vert.y += _VertexOffsetY;
			float4 vPosition = UnityObjectToClipPos(vert);

			float2 pixelSize = vPosition.w;
			pixelSize /= float2(_ScaleX, _ScaleY) * abs(mul((float2x2)UNITY_MATRIX_P, _ScreenParams.xy));

			float scale = rsqrt(dot(pixelSize, pixelSize));
			scale *= abs(input.texcoord0.w) * _GradientScale * (_Sharpness + 1);
			if(UNITY_MATRIX_P[3][3] == 0) scale = lerp(abs(scale) * (1 - _PerspectiveFilter), scale, abs(dot(UnityObjectToWorldNormal(input.normal.xyz), normalize(WorldSpaceViewDir(vert)))));

			float weight = lerp(_WeightNormal, _WeightBold, bold) / 4.0;
			weight = (weight + _FaceDilate) * _ScaleRatioA * 0.5;

			float layerScale = scale;

			scale /= 1 + (_OutlineSoftness * _ScaleRatioA * scale);
			float bias = (0.5 - weight) * scale - 0.5;
			float outline = _OutlineWidth * _ScaleRatioA * 0.5 * scale;

            if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
            {
                input.color.rgb = UIGammaToLinear(input.color.rgb);
            }
			float opacity = input.color.a;
					#if (UNDERLAY_ON | UNDERLAY_INNER)
					opacity = 1.0;
					#endif

			fixed4 faceColor = fixed4(input.color.rgb, opacity) * _FaceColor;
			faceColor.rgb *= faceColor.a;

			fixed4 outlineColor = _OutlineColor;
			outlineColor.a *= opacity;
			outlineColor.rgb *= outlineColor.a;
			outlineColor = lerp(faceColor, outlineColor, sqrt(min(1.0, (outline * 2))));

		    #if (UNDERLAY_ON | UNDERLAY_INNER)

			layerScale /= 1 + ((_UnderlaySoftness * _ScaleRatioC) * layerScale);
			float layerBias = (.5 - weight) * layerScale - .5 - ((_UnderlayDilate * _ScaleRatioC) * .5 * layerScale);

			float x = -(_UnderlayOffsetX * _ScaleRatioC) * _GradientScale / _TextureWidth;
			float y = -(_UnderlayOffsetY * _ScaleRatioC) * _GradientScale / _TextureHeight;
			float2 layerOffset = float2(x, y);
		    #endif

			// Generate UV for the Masking Texture
			float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
			float2 maskUV = (vert.xy - clampedRect.xy) / (clampedRect.zw - clampedRect.xy);
			const half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));

			// Structure for pixel shader
			pixel_t output = {
				vPosition,
				faceColor,
				outlineColor,
				float4(input.texcoord0.x, input.texcoord0.y, maskUV.x, maskUV.y),
				half4(scale, bias - outline, bias + outline, bias),
				half4(vert.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * maskSoftness + pixelSize.xy)),
			    #if (UNDERLAY_ON | UNDERLAY_INNER)
				float4(input.texcoord0 + layerOffset, input.color.a, 0),
				half2(layerScale, layerBias),
			    #endif
			};

			return output;
		}


		// PIXEL SHADER
		fixed4 PixShader(pixel_t input) : SV_Target
		{
			half d = tex2D(_MainTex, input.texcoord0.xy).a * input.param.x;
			half4 c = input.faceColor * saturate(d - input.param.w);

		    #ifdef OUTLINE_ON
			c = lerp(input.outlineColor, input.faceColor, saturate(d - input.param.z));
			c *= saturate(d - input.param.y);
		    #endif

		    #if UNDERLAY_ON
			d = tex2D(_MainTex, input.texcoord1.xy).a * input.underlayParam.x;
			c += float4(_UnderlayColor.rgb * _UnderlayColor.a, _UnderlayColor.a) * saturate(d - input.underlayParam.y) * (1 - c.a);
		    #endif

		    #if UNDERLAY_INNER
			half sd = saturate(d - input.param.z);
			d = tex2D(_MainTex, input.texcoord1.xy).a * input.underlayParam.x;
			c += float4(_UnderlayColor.rgb * _UnderlayColor.a, _UnderlayColor.a) * (1 - saturate(d - input.underlayParam.y)) * sd * (1 - c.a);
		    #endif

		    // Alternative implementation to UnityGet2DClipping with support for softness.
		    //#if UNITY_UI_CLIP_RECT
			half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(input.mask.xy)) * input.mask.zw);
			c *= m.x * m.y;
		    //#endif

		    float a = abs(_MaskInverse - tex2D(_MaskTex, input.texcoord0.zw).a);
		    float t = a + (1 - _MaskWipeControl) * _MaskEdgeSoftness - _MaskWipeControl;
		    a = saturate(t / _MaskEdgeSoftness);
		    c.rgb = lerp(_MaskEdgeColor.rgb*c.a, c.rgb, a);
		    c *= a;

		    #if (UNDERLAY_ON | UNDERLAY_INNER)
			c *= input.texcoord1.z;
		    #endif

		    #if UNITY_UI_ALPHACLIP
			clip(c.a - 0.001);
		    #endif

			return c;
		}
		ENDCG
	}
}

CustomEditor "TMPro.EditorUtilities.TMP_SDFShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_SDF-Mobile Overlay.shader`
```hlsl
// Simplified SDF shader:
// - No Shading Option (bevel / bump / env map)
// - No Glow Option
// - Softness is applied on both side of the outline

Shader "TextMeshPro/Mobile/Distance Field Overlay" {

Properties {
	_FaceColor		    ("Face Color", Color) = (1,1,1,1)
	_FaceDilate			("Face Dilate", Range(-1,1)) = 0

	_OutlineColor	    ("Outline Color", Color) = (0,0,0,1)
	_OutlineWidth		("Outline Thickness", Range(0,1)) = 0
	_OutlineSoftness	("Outline Softness", Range(0,1)) = 0

	_UnderlayColor	    ("Border Color", Color) = (0,0,0,.5)
	_UnderlayOffsetX 	("Border OffsetX", Range(-1,1)) = 0
	_UnderlayOffsetY 	("Border OffsetY", Range(-1,1)) = 0
	_UnderlayDilate		("Border Dilate", Range(-1,1)) = 0
	_UnderlaySoftness 	("Border Softness", Range(0,1)) = 0

	_WeightNormal		("Weight Normal", float) = 0
	_WeightBold			("Weight Bold", float) = .5

	_ShaderFlags		("Flags", float) = 0
	_ScaleRatioA		("Scale RatioA", float) = 1
	_ScaleRatioB		("Scale RatioB", float) = 1
	_ScaleRatioC		("Scale RatioC", float) = 1

	_MainTex			("Font Atlas", 2D) = "white" {}
	_TextureWidth		("Texture Width", float) = 512
	_TextureHeight		("Texture Height", float) = 512
	_GradientScale		("Gradient Scale", float) = 5
	_ScaleX				("Scale X", float) = 1
	_ScaleY				("Scale Y", float) = 1
	_PerspectiveFilter	("Perspective Correction", Range(0, 1)) = 0.875
	_Sharpness			("Sharpness", Range(-1,1)) = 0

	_VertexOffsetX		("Vertex OffsetX", float) = 0
	_VertexOffsetY		("Vertex OffsetY", float) = 0

	_ClipRect			("Clip Rect", vector) = (-32767, -32767, 32767, 32767)
	_MaskSoftnessX		("Mask SoftnessX", float) = 0
	_MaskSoftnessY		("Mask SoftnessY", float) = 0

	_StencilComp		("Stencil Comparison", Float) = 8
	_Stencil			("Stencil ID", Float) = 0
	_StencilOp			("Stencil Operation", Float) = 0
	_StencilWriteMask	("Stencil Write Mask", Float) = 255
	_StencilReadMask	("Stencil Read Mask", Float) = 255

	_CullMode			("Cull Mode", Float) = 0
	_ColorMask			("Color Mask", Float) = 15
}

SubShader {
	Tags
  {
		"Queue"="Overlay"
		"IgnoreProjector"="True"
		"RenderType"="Transparent"
	}


	Stencil
	{
		Ref [_Stencil]
		Comp [_StencilComp]
		Pass [_StencilOp]
		ReadMask [_StencilReadMask]
		WriteMask [_StencilWriteMask]
	}

	Cull [_CullMode]
	ZWrite Off
	Lighting Off
	Fog { Mode Off }
	ZTest Always
	Blend One OneMinusSrcAlpha
	ColorMask [_ColorMask]

	Pass {
		CGPROGRAM
		#pragma vertex VertShader
		#pragma fragment PixShader
		#pragma shader_feature __ OUTLINE_ON
		#pragma shader_feature __ UNDERLAY_ON UNDERLAY_INNER

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP

		#include "UnityCG.cginc"
		#include "UnityUI.cginc"
		#include "TMPro_Properties.cginc"

		struct vertex_t
		{
			UNITY_VERTEX_INPUT_INSTANCE_ID
			float4	vertex			: POSITION;
			float3	normal			: NORMAL;
			fixed4	color			: COLOR;
			float4	texcoord0		: TEXCOORD0;
			float2	texcoord1		: TEXCOORD1;
		};

		struct pixel_t
		{
			UNITY_VERTEX_INPUT_INSTANCE_ID
			UNITY_VERTEX_OUTPUT_STEREO
			float4	vertex			: SV_POSITION;
			fixed4	faceColor		: COLOR;
			fixed4	outlineColor	: COLOR1;
			float4	texcoord0		: TEXCOORD0;			// Texture UV, Mask UV
			half4	param			: TEXCOORD1;			// Scale(x), BiasIn(y), BiasOut(z), Bias(w)
			half4	mask			: TEXCOORD2;			// Position in clip space(xy), Softness(zw)

		    #if (UNDERLAY_ON | UNDERLAY_INNER)
			float4	texcoord1		: TEXCOORD3;			// Texture UV, alpha, reserved
			half2	underlayParam	: TEXCOORD4;			// Scale(x), Bias(y)
		    #endif
		};

		float _UIMaskSoftnessX;
        float _UIMaskSoftnessY;
        int _UIVertexColorAlwaysGammaSpace;


		pixel_t VertShader(vertex_t input)
		{
			pixel_t output;

			UNITY_INITIALIZE_OUTPUT(pixel_t, output);
			UNITY_SETUP_INSTANCE_ID(input);
			UNITY_TRANSFER_INSTANCE_ID(input, output);
			UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

			float bold = step(input.texcoord0.w, 0);

			float4 vert = input.vertex;
			vert.x += _VertexOffsetX;
			vert.y += _VertexOffsetY;
			float4 vPosition = UnityObjectToClipPos(vert);

			float2 pixelSize = vPosition.w;
			pixelSize /= float2(_ScaleX, _ScaleY) * abs(mul((float2x2)UNITY_MATRIX_P, _ScreenParams.xy));

			float scale = rsqrt(dot(pixelSize, pixelSize));
			scale *= abs(input.texcoord0.w) * _GradientScale * (_Sharpness + 1);
			if(UNITY_MATRIX_P[3][3] == 0) scale = lerp(abs(scale) * (1 - _PerspectiveFilter), scale, abs(dot(UnityObjectToWorldNormal(input.normal.xyz), normalize(WorldSpaceViewDir(vert)))));

			float weight = lerp(_WeightNormal, _WeightBold, bold) / 4.0;
			weight = (weight + _FaceDilate) * _ScaleRatioA * 0.5;

			float layerScale = scale;

			scale /= 1 + (_OutlineSoftness * _ScaleRatioA * scale);
			float bias = (0.5 - weight) * scale - 0.5;
			float outline = _OutlineWidth * _ScaleRatioA * 0.5 * scale;

            if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
            {
                input.color.rgb = UIGammaToLinear(input.color.rgb);
            }
			float opacity = input.color.a;
		    #if (UNDERLAY_ON | UNDERLAY_INNER)
				opacity = 1.0;
		    #endif

			fixed4 faceColor = fixed4(input.color.rgb, opacity) * _FaceColor;
			faceColor.rgb *= faceColor.a;

			fixed4 outlineColor = _OutlineColor;
			outlineColor.a *= opacity;
			outlineColor.rgb *= outlineColor.a;
			outlineColor = lerp(faceColor, outlineColor, sqrt(min(1.0, (outline * 2))));

		    #if (UNDERLAY_ON | UNDERLAY_INNER)
			layerScale /= 1 + ((_UnderlaySoftness * _ScaleRatioC) * layerScale);
			float layerBias = (.5 - weight) * layerScale - .5 - ((_UnderlayDilate * _ScaleRatioC) * .5 * layerScale);

			float x = -(_UnderlayOffsetX * _ScaleRatioC) * _GradientScale / _TextureWidth;
			float y = -(_UnderlayOffsetY * _ScaleRatioC) * _GradientScale / _TextureHeight;
			float2 layerOffset = float2(x, y);
		    #endif

			// Generate UV for the Masking Texture
			float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
			float2 maskUV = (vert.xy - clampedRect.xy) / (clampedRect.zw - clampedRect.xy);

			// Populate structure for pixel shader
			output.vertex = vPosition;
			output.faceColor = faceColor;
			output.outlineColor = outlineColor;
			output.texcoord0 = float4(input.texcoord0.x, input.texcoord0.y, maskUV.x, maskUV.y);
			output.param = half4(scale, bias - outline, bias + outline, bias);
			const half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
			output.mask = half4(vert.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * maskSoftness + pixelSize.xy));
			#if (UNDERLAY_ON || UNDERLAY_INNER)
			output.texcoord1 = float4(input.texcoord0 + layerOffset, input.color.a, 0);
			output.underlayParam = half2(layerScale, layerBias);
			#endif

			return output;
		}


		// PIXEL SHADER
		fixed4 PixShader(pixel_t input) : SV_Target
		{
			UNITY_SETUP_INSTANCE_ID(input);

			half d = tex2D(_MainTex, input.texcoord0.xy).a * input.param.x;
			half4 c = input.faceColor * saturate(d - input.param.w);

		    #ifdef OUTLINE_ON
			c = lerp(input.outlineColor, input.faceColor, saturate(d - input.param.z));
			c *= saturate(d - input.param.y);
		    #endif

		    #if UNDERLAY_ON
			d = tex2D(_MainTex, input.texcoord1.xy).a * input.underlayParam.x;
			c += float4(_UnderlayColor.rgb * _UnderlayColor.a, _UnderlayColor.a) * saturate(d - input.underlayParam.y) * (1 - c.a);
		    #endif

		    #if UNDERLAY_INNER
			half sd = saturate(d - input.param.z);
			d = tex2D(_MainTex, input.texcoord1.xy).a * input.underlayParam.x;
			c += float4(_UnderlayColor.rgb * _UnderlayColor.a, _UnderlayColor.a) * (1 - saturate(d - input.underlayParam.y)) * sd * (1 - c.a);
		    #endif

		    // Alternative implementation to UnityGet2DClipping with support for softness.
		    #if UNITY_UI_CLIP_RECT
			half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(input.mask.xy)) * input.mask.zw);
			c *= m.x * m.y;
		    #endif

		    #if (UNDERLAY_ON | UNDERLAY_INNER)
			c *= input.texcoord1.z;
		    #endif

            #if UNITY_UI_ALPHACLIP
			clip(c.a - 0.001);
		    #endif

			return c;
		}
		ENDCG
	}
}

CustomEditor "TMPro.EditorUtilities.TMP_SDFShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_SDF-Mobile SSD.shader`
```hlsl
﻿// Simplified SDF shader:
// - No Shading Option (bevel / bump / env map)
// - No Glow Option
// - Softness is applied on both side of the outline

Shader "TextMeshPro/Mobile/Distance Field SSD" {

Properties {
	_FaceColor		    ("Face Color", Color) = (1,1,1,1)
	_FaceDilate			("Face Dilate", Range(-1,1)) = 0

	_OutlineColor	    ("Outline Color", Color) = (0,0,0,1)
	_OutlineWidth		("Outline Thickness", Range(0,1)) = 0
	_OutlineSoftness	("Outline Softness", Range(0,1)) = 0

	_UnderlayColor		("Border Color", Color) = (0,0,0,.5)
	_UnderlayOffsetX 	("Border OffsetX", Range(-1,1)) = 0
	_UnderlayOffsetY 	("Border OffsetY", Range(-1,1)) = 0
	_UnderlayDilate		("Border Dilate", Range(-1,1)) = 0
	_UnderlaySoftness 	("Border Softness", Range(0,1)) = 0

	_WeightNormal		("Weight Normal", float) = 0
	_WeightBold			("Weight Bold", float) = .5

	_ShaderFlags		("Flags", float) = 0
	_ScaleRatioA		("Scale RatioA", float) = 1
	_ScaleRatioB		("Scale RatioB", float) = 1
	_ScaleRatioC		("Scale RatioC", float) = 1

	_MainTex			("Font Atlas", 2D) = "white" {}
	_TextureWidth		("Texture Width", float) = 512
	_TextureHeight		("Texture Height", float) = 512
	_GradientScale		("Gradient Scale", float) = 5
	_ScaleX				("Scale X", float) = 1
	_ScaleY				("Scale Y", float) = 1
	_PerspectiveFilter	("Perspective Correction", Range(0, 1)) = 0.875
	_Sharpness			("Sharpness", Range(-1,1)) = 0

	_VertexOffsetX		("Vertex OffsetX", float) = 0
	_VertexOffsetY		("Vertex OffsetY", float) = 0

	_ClipRect			("Clip Rect", vector) = (-32767, -32767, 32767, 32767)
	_MaskSoftnessX		("Mask SoftnessX", float) = 0
	_MaskSoftnessY		("Mask SoftnessY", float) = 0
	_MaskTex			("Mask Texture", 2D) = "white" {}
	_MaskInverse		("Inverse", float) = 0
	_MaskEdgeColor		("Edge Color", Color) = (1,1,1,1)
	_MaskEdgeSoftness	("Edge Softness", Range(0, 1)) = 0.01
	_MaskWipeControl	("Wipe Position", Range(0, 1)) = 0.5

	_StencilComp		("Stencil Comparison", Float) = 8
	_Stencil			("Stencil ID", Float) = 0
	_StencilOp			("Stencil Operation", Float) = 0
	_StencilWriteMask	("Stencil Write Mask", Float) = 255
	_StencilReadMask	("Stencil Read Mask", Float) = 255

    _CullMode           ("Cull Mode", Float) = 0
	_ColorMask			("Color Mask", Float) = 15
}

SubShader {
	Tags {
		"Queue"="Transparent"
		"IgnoreProjector"="True"
		"RenderType"="Transparent"
	}

	Stencil
	{
		Ref [_Stencil]
		Comp [_StencilComp]
		Pass [_StencilOp]
		ReadMask [_StencilReadMask]
		WriteMask [_StencilWriteMask]
	}

	Cull [_CullMode]
	ZWrite Off
	Lighting Off
	Fog { Mode Off }
	ZTest [unity_GUIZTestMode]
	Blend One OneMinusSrcAlpha
	ColorMask [_ColorMask]

	Pass {
		CGPROGRAM
		#pragma vertex VertShader
		#pragma fragment PixShader
		#pragma shader_feature __ OUTLINE_ON
		#pragma shader_feature __ UNDERLAY_ON UNDERLAY_INNER

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP

		#include "UnityCG.cginc"
		#include "UnityUI.cginc"
		#include "TMPro_Properties.cginc"

		#include "TMPro_Mobile.cginc"

		ENDCG
	}
}

CustomEditor "TMPro.EditorUtilities.TMP_SDFShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_SDF-Mobile-2-Pass.shader`
```hlsl
// Simplified SDF shader:
// - No Shading Option (bevel / bump / env map)
// - No Glow Option
// - Softness is applied on both side of the outline

Shader "TextMeshPro/Mobile/Distance Field - 2 Pass" {

Properties {
	_FaceColor          ("Face Color", Color) = (1,1,1,1)
	_FaceDilate			("Face Dilate", Range(-1,1)) = 0

	_OutlineColor	    ("Outline Color", Color) = (0,0,0,1)
	_OutlineWidth		("Outline Thickness", Range(0,1)) = 0
	_OutlineSoftness	("Outline Softness", Range(0,1)) = 0

	_UnderlayColor	    ("Border Color", Color) = (0,0,0,.5)
	_UnderlayOffsetX 	("Border OffsetX", Range(-1,1)) = 0
	_UnderlayOffsetY 	("Border OffsetY", Range(-1,1)) = 0
	_UnderlayDilate		("Border Dilate", Range(-1,1)) = 0
	_UnderlaySoftness 	("Border Softness", Range(0,1)) = 0

	_WeightNormal		("Weight Normal", float) = 0
	_WeightBold			("Weight Bold", float) = .5

	_ShaderFlags		("Flags", float) = 0
	_ScaleRatioA		("Scale RatioA", float) = 1
	_ScaleRatioB		("Scale RatioB", float) = 1
	_ScaleRatioC		("Scale RatioC", float) = 1

	_MainTex			("Font Atlas", 2D) = "white" {}
	_TextureWidth		("Texture Width", float) = 512
	_TextureHeight		("Texture Height", float) = 512
	_GradientScale		("Gradient Scale", float) = 5
	_ScaleX				("Scale X", float) = 1
	_ScaleY				("Scale Y", float) = 1
	_PerspectiveFilter	("Perspective Correction", Range(0, 1)) = 0.875
	_Sharpness			("Sharpness", Range(-1,1)) = 0

	_VertexOffsetX		("Vertex OffsetX", float) = 0
	_VertexOffsetY		("Vertex OffsetY", float) = 0

	_ClipRect			("Clip Rect", vector) = (-32767, -32767, 32767, 32767)
	_MaskSoftnessX		("Mask SoftnessX", float) = 0
	_MaskSoftnessY		("Mask SoftnessY", float) = 0

	_StencilComp		("Stencil Comparison", Float) = 8
	_Stencil			("Stencil ID", Float) = 0
	_StencilOp			("Stencil Operation", Float) = 0
	_StencilWriteMask	("Stencil Write Mask", Float) = 255
	_StencilReadMask	("Stencil Read Mask", Float) = 255

	_CullMode			("Cull Mode", Float) = 0
	_ColorMask			("Color Mask", Float) = 15
}

SubShader {

	// Draw Outline and Underlay
	Name "Outline"

	Tags
	{
		"Queue"="Transparent"
		"IgnoreProjector"="True"
		"RenderType"="Transparent"
	}

	Stencil
	{
		Ref [_Stencil]
		Comp [_StencilComp]
		Pass [_StencilOp]
		ReadMask [_StencilReadMask]
		WriteMask [_StencilWriteMask]
	}

	Cull [_CullMode]
	ZWrite Off
	Lighting Off
	Fog { Mode Off }
	ZTest [unity_GUIZTestMode]
	Blend One OneMinusSrcAlpha
	ColorMask [_ColorMask]

	Pass {
		CGPROGRAM
		#pragma vertex VertShader
		#pragma fragment PixShader
		#pragma shader_feature __ OUTLINE_ON
		#pragma shader_feature __ UNDERLAY_ON UNDERLAY_INNER

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP

		#include "UnityCG.cginc"
		#include "UnityUI.cginc"
		#include "TMPro_Properties.cginc"

		struct vertex_t {
			UNITY_VERTEX_INPUT_INSTANCE_ID
			float4	vertex			: POSITION;
			float3	normal			: NORMAL;
			fixed4	color			: COLOR;
			float4	texcoord0		: TEXCOORD0;
			float2	texcoord1		: TEXCOORD1;
		};

		struct pixel_t {
			UNITY_VERTEX_INPUT_INSTANCE_ID
			UNITY_VERTEX_OUTPUT_STEREO
			float4	vertex			: SV_POSITION;
			fixed4	faceColor		: COLOR;
			fixed4	outlineColor	: COLOR1;
			float4	texcoord0		: TEXCOORD0;			// Texture UV, Mask UV
			half4	param			: TEXCOORD1;			// Scale(x), BiasIn(y), BiasOut(z), Bias(w)
			half4	mask			: TEXCOORD2;			// Position in clip space(xy), Softness(zw)
			#if (UNDERLAY_ON | UNDERLAY_INNER)
			float4	texcoord1		: TEXCOORD3;			// Texture UV, alpha, reserved
			half2	underlayParam	: TEXCOORD4;			// Scale(x), Bias(y)
			#endif
		};

		float _UIMaskSoftnessX;
        float _UIMaskSoftnessY;

		pixel_t VertShader(vertex_t input)
		{
			pixel_t output;

			UNITY_INITIALIZE_OUTPUT(pixel_t, output);
			UNITY_SETUP_INSTANCE_ID(input);
			UNITY_TRANSFER_INSTANCE_ID(input, output);
			UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

			const float bold = step(input.texcoord0.w, 0);

			float4 vert = input.vertex;
			vert.x += _VertexOffsetX;
			vert.y += _VertexOffsetY;
			float4 vPosition = UnityObjectToClipPos(vert);

			float2 pixelSize = vPosition.w;
			pixelSize /= float2(_ScaleX, _ScaleY) * abs(mul((float2x2)UNITY_MATRIX_P, _ScreenParams.xy));

			float scale = rsqrt(dot(pixelSize, pixelSize));
			scale *= abs(input.texcoord0.w) * _GradientScale * (_Sharpness + 1);
			if(UNITY_MATRIX_P[3][3] == 0) scale = lerp(abs(scale) * (1 - _PerspectiveFilter), scale, abs(dot(UnityObjectToWorldNormal(input.normal.xyz), normalize(WorldSpaceViewDir(vert)))));

			float weight = lerp(_WeightNormal, _WeightBold, bold) / 4.0;
			weight = (weight + _FaceDilate) * _ScaleRatioA * 0.5;

			float layerScale = scale;

			scale /= 1 + (_OutlineSoftness * _ScaleRatioA * scale);
			float bias = (0.5 - weight) * scale - 0.5;
			const float outline = _OutlineWidth * _ScaleRatioA * 0.5 * scale;

			float opacity = input.color.a;
			#if (UNDERLAY_ON | UNDERLAY_INNER)
			opacity = 1.0;
			#endif

			fixed4 faceColor = fixed4(input.color.rgb, opacity) * _FaceColor;
			faceColor.rgb *= faceColor.a;

			fixed4 outlineColor = _OutlineColor;
			outlineColor.a *= opacity;
			outlineColor.rgb *= outlineColor.a;
			//outlineColor = lerp(faceColor, outlineColor, sqrt(min(1.0, outline * 2)));

			#if (UNDERLAY_ON | UNDERLAY_INNER)
			layerScale /= 1 + ((_UnderlaySoftness * _ScaleRatioC) * layerScale);
			float layerBias = (.5 - weight) * layerScale - .5 - ((_UnderlayDilate * _ScaleRatioC) * .5 * layerScale);

			float x = -(_UnderlayOffsetX * _ScaleRatioC) * _GradientScale / _TextureWidth;
			float y = -(_UnderlayOffsetY * _ScaleRatioC) * _GradientScale / _TextureHeight;
			float2 layerOffset = float2(x, y);
			#endif

			// Generate UV for the Masking Texture
			float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
			float2 maskUV = (vert.xy - clampedRect.xy) / (clampedRect.zw - clampedRect.xy);

			// Populate structure for pixel shader
			output.vertex = vPosition;
			output.faceColor = faceColor;
			output.outlineColor = outlineColor;
			output.texcoord0 = float4(input.texcoord0.x, input.texcoord0.y, maskUV.x, maskUV.y);
			output.param = half4(scale, bias - outline, bias + outline, bias);

			const half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
			output.mask = half4(vert.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * maskSoftness + pixelSize.xy));
			#if (UNDERLAY_ON || UNDERLAY_INNER)
			output.texcoord1 = float4(input.texcoord0 + layerOffset, input.color.a, 0);
			output.underlayParam = half2(layerScale, layerBias);
			#endif

			return output;
		}


		// PIXEL SHADER
		fixed4 PixShader(pixel_t input) : SV_Target
		{
			UNITY_SETUP_INSTANCE_ID(input);

			half d = tex2D(_MainTex, input.texcoord0.xy).a * input.param.x;
			half4 c = half4(0, 0, 0, 0);

			#if OUTLINE_ON
			c = input.outlineColor * saturate(d - input.param.y);
			#endif

			#if UNDERLAY_ON
			d = tex2D(_MainTex, input.texcoord1.xy).a * input.underlayParam.x;
			c += float4(_UnderlayColor.rgb * _UnderlayColor.a, _UnderlayColor.a) * saturate(d - input.underlayParam.y) * (1 - c.a);
			#endif

			#if UNDERLAY_INNER
			half sd = saturate(d - input.param.z);
			d = tex2D(_MainTex, input.texcoord1.xy).a * input.underlayParam.x;
			c += float4(_UnderlayColor.rgb * _UnderlayColor.a, _UnderlayColor.a) * (1 - saturate(d - input.underlayParam.y)) * sd * (1 - c.a);
			#endif

			// Alternative implementation to UnityGet2DClipping with support for softness.
			#if UNITY_UI_CLIP_RECT
			half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(input.mask.xy)) * input.mask.zw);
			c *= m.x * m.y;
			#endif

			#if (UNDERLAY_ON | UNDERLAY_INNER)
			c *= input.texcoord1.z;
		    #endif

		    #if UNITY_UI_ALPHACLIP
			clip(c.a - 0.001);
		    #endif

			return c;
		}
		ENDCG
	}


	// Draw face
	Name "Face"

	Tags
	{
		"Queue"="Transparent"
		"IgnoreProjector"="True"
		"RenderType"="Transparent"
	}

	Stencil
	{
		Ref [_Stencil]
		Comp [_StencilComp]
		Pass [_StencilOp]
		ReadMask [_StencilReadMask]
		WriteMask [_StencilWriteMask]
	}

	Cull [_CullMode]
	ZWrite Off
	Lighting Off
	Fog { Mode Off }
	ZTest [unity_GUIZTestMode]
	Blend One OneMinusSrcAlpha
	ColorMask [_ColorMask]

	Pass {
		CGPROGRAM
		#pragma vertex VertShader
		#pragma fragment PixShader

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP

		#include "UnityCG.cginc"
		#include "UnityUI.cginc"
		#include "TMPro_Properties.cginc"

		struct vertex_t {
			UNITY_VERTEX_INPUT_INSTANCE_ID
            float4	vertex			: POSITION;
			float3	normal			: NORMAL;
			fixed4	color			: COLOR;
			float4	texcoord0		: TEXCOORD0;
			float2	texcoord1		: TEXCOORD1;
		};

		struct pixel_t {
			UNITY_VERTEX_INPUT_INSTANCE_ID
			UNITY_VERTEX_OUTPUT_STEREO
            float4	vertex			: SV_POSITION;
			fixed4	faceColor		: COLOR;
			float4	texcoord0		: TEXCOORD0;			// Texture UV, Mask UV
			half2	param			: TEXCOORD1;			// Scale(x), BiasIn(y), BiasOut(z), Bias(w)
			half4	mask			: TEXCOORD2;			// Position in clip space(xy), Softness(zw)
		};

		float _UIMaskSoftnessX;
        float _UIMaskSoftnessY;
        int _UIVertexColorAlwaysGammaSpace;


		pixel_t VertShader(vertex_t input)
		{
			pixel_t output;

			UNITY_INITIALIZE_OUTPUT(pixel_t, output);
			UNITY_SETUP_INSTANCE_ID(input);
			UNITY_TRANSFER_INSTANCE_ID(input, output);
			UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

			const float bold = step(input.texcoord0.w, 0);

			float4 vert = input.vertex;
			vert.x += _VertexOffsetX;
			vert.y += _VertexOffsetY;
			float4 vPosition = UnityObjectToClipPos(vert);

			float2 pixelSize = vPosition.w;
			pixelSize /= float2(_ScaleX, _ScaleY) * abs(mul((float2x2)UNITY_MATRIX_P, _ScreenParams.xy));

			float scale = rsqrt(dot(pixelSize, pixelSize));
			scale *= abs(input.texcoord0.w) * _GradientScale * (_Sharpness + 1);
			if(UNITY_MATRIX_P[3][3] == 0) scale = lerp(abs(scale) * (1 - _PerspectiveFilter), scale, abs(dot(UnityObjectToWorldNormal(input.normal.xyz), normalize(WorldSpaceViewDir(vert)))));

			float weight = lerp(_WeightNormal, _WeightBold, bold) / 4.0;
			weight = (weight + _FaceDilate) * _ScaleRatioA * 0.5;

			scale /= 1 + (_OutlineSoftness * _ScaleRatioA * scale);
			float bias = (0.5 - weight) * scale - 0.5;

            if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
            {
                input.color.rgb = UIGammaToLinear(input.color.rgb);
            }
			float opacity = input.color.a;

			fixed4 faceColor = fixed4(input.color.rgb, opacity) * _FaceColor;
			faceColor.rgb *= faceColor.a;

			// Generate UV for the Masking Texture
			float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
			float2 maskUV = (vert.xy - clampedRect.xy) / (clampedRect.zw - clampedRect.xy);

			// Populate structure for pixel shader
			output.vertex = vPosition;
			output.faceColor = faceColor;
			output.texcoord0 = float4(input.texcoord0.x, input.texcoord0.y, maskUV.x, maskUV.y);
			output.param = half2(scale, bias);

			const half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
			output.mask = half4(vert.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * maskSoftness + pixelSize.xy));

			return output;
		}


		// PIXEL SHADER
		fixed4 PixShader(pixel_t input) : SV_Target
		{
			UNITY_SETUP_INSTANCE_ID(input);

			half d = tex2D(_MainTex, input.texcoord0.xy).a * input.param.x;
			half4 c = input.faceColor * saturate(d - input.param.y);

		    // Alternative implementation to UnityGet2DClipping with support for softness.
			#if UNITY_UI_CLIP_RECT
			half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(input.mask.xy)) * input.mask.zw);
			c *= m.x * m.y;
			#endif

		    #if UNITY_UI_ALPHACLIP
			clip(c.a - 0.001);
		    #endif

			return c;
		}
		ENDCG
	}

}

CustomEditor "TMPro.EditorUtilities.TMP_SDFShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_SDF-Mobile.shader`
```hlsl
﻿// Simplified SDF shader:
// - No Shading Option (bevel / bump / env map)
// - No Glow Option
// - Softness is applied on both side of the outline

Shader "TextMeshPro/Mobile/Distance Field" {

Properties {
	_FaceColor          ("Face Color", Color) = (1,1,1,1)
	_FaceDilate			("Face Dilate", Range(-1,1)) = 0

	_OutlineColor	    ("Outline Color", Color) = (0,0,0,1)
	_OutlineWidth		("Outline Thickness", Range(0,1)) = 0
	_OutlineSoftness	("Outline Softness", Range(0,1)) = 0

	_UnderlayColor	    ("Border Color", Color) = (0,0,0,.5)
	_UnderlayOffsetX 	("Border OffsetX", Range(-1,1)) = 0
	_UnderlayOffsetY 	("Border OffsetY", Range(-1,1)) = 0
	_UnderlayDilate		("Border Dilate", Range(-1,1)) = 0
	_UnderlaySoftness 	("Border Softness", Range(0,1)) = 0

	_WeightNormal		("Weight Normal", float) = 0
	_WeightBold			("Weight Bold", float) = .5

	_ShaderFlags		("Flags", float) = 0
	_ScaleRatioA		("Scale RatioA", float) = 1
	_ScaleRatioB		("Scale RatioB", float) = 1
	_ScaleRatioC		("Scale RatioC", float) = 1

	_MainTex			("Font Atlas", 2D) = "white" {}
	_TextureWidth		("Texture Width", float) = 512
	_TextureHeight		("Texture Height", float) = 512
	_GradientScale		("Gradient Scale", float) = 5
	_ScaleX				("Scale X", float) = 1
	_ScaleY				("Scale Y", float) = 1
	_PerspectiveFilter	("Perspective Correction", Range(0, 1)) = 0.875
	_Sharpness			("Sharpness", Range(-1,1)) = 0

	_VertexOffsetX		("Vertex OffsetX", float) = 0
	_VertexOffsetY		("Vertex OffsetY", float) = 0

	_ClipRect			("Clip Rect", vector) = (-32767, -32767, 32767, 32767)
	_MaskSoftnessX		("Mask SoftnessX", float) = 0
	_MaskSoftnessY		("Mask SoftnessY", float) = 0

	_StencilComp		("Stencil Comparison", Float) = 8
	_Stencil			("Stencil ID", Float) = 0
	_StencilOp			("Stencil Operation", Float) = 0
	_StencilWriteMask	("Stencil Write Mask", Float) = 255
	_StencilReadMask	("Stencil Read Mask", Float) = 255

	_CullMode			("Cull Mode", Float) = 0
	_ColorMask			("Color Mask", Float) = 15
}

SubShader {
	Tags
	{
		"Queue"="Transparent"
		"IgnoreProjector"="True"
		"RenderType"="Transparent"
	}


	Stencil
	{
		Ref [_Stencil]
		Comp [_StencilComp]
		Pass [_StencilOp]
		ReadMask [_StencilReadMask]
		WriteMask [_StencilWriteMask]
	}

	Cull [_CullMode]
	ZWrite Off
	Lighting Off
	Fog { Mode Off }
	ZTest [unity_GUIZTestMode]
	Blend One OneMinusSrcAlpha
	ColorMask [_ColorMask]

	Pass {
		CGPROGRAM
		#pragma enable_d3d11_debug_symbols
		#pragma vertex VertShader
		#pragma fragment PixShader
		#pragma shader_feature __ OUTLINE_ON
		#pragma shader_feature __ UNDERLAY_ON UNDERLAY_INNER

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP

		#include "UnityCG.cginc"
		#include "UnityUI.cginc"
		#include "TMPro_Properties.cginc"

		struct vertex_t {
			UNITY_VERTEX_INPUT_INSTANCE_ID
			float4	vertex			: POSITION;
			float3	normal			: NORMAL;
			fixed4	color			: COLOR;
			float4	texcoord0		: TEXCOORD0;
			float2	texcoord1		: TEXCOORD1;
		};

		struct pixel_t {
			UNITY_VERTEX_INPUT_INSTANCE_ID
			UNITY_VERTEX_OUTPUT_STEREO
			float4	vertex			: SV_POSITION;
			fixed4	faceColor		: COLOR;
			fixed4	outlineColor	: COLOR1;
			float4	texcoord0		: TEXCOORD0;			// Texture UV, Mask UV
			half4	param			: TEXCOORD1;			// Scale(x), BiasIn(y), BiasOut(z), Bias(w)
			half4	mask			: TEXCOORD2;			// Position in clip space(xy), Softness(zw)
			#if (UNDERLAY_ON | UNDERLAY_INNER)
			float4	texcoord1		: TEXCOORD3;			// Texture UV, alpha, reserved
			half2	underlayParam	: TEXCOORD4;			// Scale(x), Bias(y)
			#endif
		};

		float _UIMaskSoftnessX;
        float _UIMaskSoftnessY;
        int _UIVertexColorAlwaysGammaSpace;

		pixel_t VertShader(vertex_t input)
		{
			pixel_t output;

			UNITY_INITIALIZE_OUTPUT(pixel_t, output);
			UNITY_SETUP_INSTANCE_ID(input);
			UNITY_TRANSFER_INSTANCE_ID(input, output);
			UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

			float bold = step(input.texcoord0.w, 0);

			float4 vert = input.vertex;
			vert.x += _VertexOffsetX;
			vert.y += _VertexOffsetY;
			float4 vPosition = UnityObjectToClipPos(vert);

			float2 pixelSize = vPosition.w;
			pixelSize /= float2(_ScaleX, _ScaleY) * abs(mul((float2x2)UNITY_MATRIX_P, _ScreenParams.xy));

			float scale = rsqrt(dot(pixelSize, pixelSize));
			scale *= abs(input.texcoord0.w) * _GradientScale * (_Sharpness + 1);
			if(UNITY_MATRIX_P[3][3] == 0) scale = lerp(abs(scale) * (1 - _PerspectiveFilter), scale, abs(dot(UnityObjectToWorldNormal(input.normal.xyz), normalize(WorldSpaceViewDir(vert)))));

			float weight = lerp(_WeightNormal, _WeightBold, bold) / 4.0;
			weight = (weight + _FaceDilate) * _ScaleRatioA * 0.5;

			float layerScale = scale;

			scale /= 1 + (_OutlineSoftness * _ScaleRatioA * scale);
			float bias = (0.5 - weight) * scale - 0.5;
			float outline = _OutlineWidth * _ScaleRatioA * 0.5 * scale;

            if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
            {
                input.color.rgb = UIGammaToLinear(input.color.rgb);
            }
            float opacity = input.color.a;
			#if (UNDERLAY_ON | UNDERLAY_INNER)
			opacity = 1.0;
			#endif

			fixed4 faceColor = fixed4(input.color.rgb, opacity) * _FaceColor;
			faceColor.rgb *= faceColor.a;

			fixed4 outlineColor = _OutlineColor;
			outlineColor.a *= opacity;
			outlineColor.rgb *= outlineColor.a;
			outlineColor = lerp(faceColor, outlineColor, sqrt(min(1.0, (outline * 2))));

			#if (UNDERLAY_ON | UNDERLAY_INNER)
			layerScale /= 1 + ((_UnderlaySoftness * _ScaleRatioC) * layerScale);
			float layerBias = (.5 - weight) * layerScale - .5 - ((_UnderlayDilate * _ScaleRatioC) * .5 * layerScale);

			float x = -(_UnderlayOffsetX * _ScaleRatioC) * _GradientScale / _TextureWidth;
			float y = -(_UnderlayOffsetY * _ScaleRatioC) * _GradientScale / _TextureHeight;
			float2 layerOffset = float2(x, y);
			#endif

			// Generate UV for the Masking Texture
			float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
			float2 maskUV = (vert.xy - clampedRect.xy) / (clampedRect.zw - clampedRect.xy);

			// Populate structure for pixel shader
			output.vertex = vPosition;
			output.faceColor = faceColor;
			output.outlineColor = outlineColor;
			output.texcoord0 = float4(input.texcoord0.x, input.texcoord0.y, maskUV.x, maskUV.y);
			output.param = half4(scale, bias - outline, bias + outline, bias);

			const half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
			output.mask = half4(vert.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * maskSoftness + pixelSize.xy));
			#if (UNDERLAY_ON || UNDERLAY_INNER)
			output.texcoord1 = float4(input.texcoord0 + layerOffset, input.color.a, 0);
			output.underlayParam = half2(layerScale, layerBias);
			#endif

			return output;
		}


		// PIXEL SHADER
		fixed4 PixShader(pixel_t input) : SV_Target
		{
			UNITY_SETUP_INSTANCE_ID(input);

			half d = tex2D(_MainTex, input.texcoord0.xy).a * input.param.x;
			half4 c = input.faceColor * saturate(d - input.param.w);

			#ifdef OUTLINE_ON
			c = lerp(input.outlineColor, input.faceColor, saturate(d - input.param.z));
			c *= saturate(d - input.param.y);
			#endif

			#if UNDERLAY_ON
			d = tex2D(_MainTex, input.texcoord1.xy).a * input.underlayParam.x;
			c += float4(_UnderlayColor.rgb * _UnderlayColor.a, _UnderlayColor.a) * saturate(d - input.underlayParam.y) * (1 - c.a);
			#endif

			#if UNDERLAY_INNER
			half sd = saturate(d - input.param.z);
			d = tex2D(_MainTex, input.texcoord1.xy).a * input.underlayParam.x;
			c += float4(_UnderlayColor.rgb * _UnderlayColor.a, _UnderlayColor.a) * (1 - saturate(d - input.underlayParam.y)) * sd * (1 - c.a);
			#endif

			// Alternative implementation to UnityGet2DClipping with support for softness.
			#if UNITY_UI_CLIP_RECT
			half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(input.mask.xy)) * input.mask.zw);
			c *= m.x * m.y;
			#endif

			#if (UNDERLAY_ON | UNDERLAY_INNER)
			c *= input.texcoord1.z;
			#endif

			#if UNITY_UI_ALPHACLIP
			clip(c.a - 0.001);
			#endif

			return c;
		}
		ENDCG
	}
}

CustomEditor "TMPro.EditorUtilities.TMP_SDFShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_SDF-Surface-Mobile.shader`
```hlsl
// Simplified version of the SDF Surface shader :
// - No support for Bevel, Bump or envmap
// - Diffuse only lighting
// - Fully supports only 1 directional light. Other lights can affect it, but it will be per-vertex/SH.

Shader "TextMeshPro/Mobile/Distance Field (Surface)" {

Properties {
	_FaceTex			("Fill Texture", 2D) = "white" {}
	_FaceColor		    ("Fill Color", Color) = (1,1,1,1)
	_FaceDilate			("Face Dilate", Range(-1,1)) = 0

	_OutlineColor	    ("Outline Color", Color) = (0,0,0,1)
	_OutlineTex			("Outline Texture", 2D) = "white" {}
	_OutlineWidth		("Outline Thickness", Range(0, 1)) = 0
	_OutlineSoftness	("Outline Softness", Range(0,1)) = 0

	_GlowColor		    ("Color", Color) = (0, 1, 0, 0.5)
	_GlowOffset			("Offset", Range(-1,1)) = 0
	_GlowInner			("Inner", Range(0,1)) = 0.05
	_GlowOuter			("Outer", Range(0,1)) = 0.05
	_GlowPower			("Falloff", Range(1, 0)) = 0.75

	_WeightNormal		("Weight Normal", float) = 0
	_WeightBold			("Weight Bold", float) = 0.5

	// Should not be directly exposed to the user
	_ShaderFlags		("Flags", float) = 0
	_ScaleRatioA		("Scale RatioA", float) = 1
	_ScaleRatioB		("Scale RatioB", float) = 1
	_ScaleRatioC		("Scale RatioC", float) = 1

	_MainTex			("Font Atlas", 2D) = "white" {}
	_TextureWidth		("Texture Width", float) = 512
	_TextureHeight		("Texture Height", float) = 512
	_GradientScale		("Gradient Scale", float) = 5.0
	_ScaleX				("Scale X", float) = 1.0
	_ScaleY				("Scale Y", float) = 1.0
	_PerspectiveFilter	("Perspective Correction", Range(0, 1)) = 0.875
	_Sharpness			("Sharpness", Range(-1,1)) = 0

	_VertexOffsetX		("Vertex OffsetX", float) = 0
	_VertexOffsetY		("Vertex OffsetY", float) = 0

	_CullMode			("Cull Mode", Float) = 0
	//_MaskCoord		("Mask Coords", vector) = (0,0,0,0)
	//_MaskSoftness		("Mask Softness", float) = 0
}

SubShader {

	Tags {
		"Queue"="Transparent"
		"IgnoreProjector"="True"
		"RenderType"="Transparent"
	}

	LOD 300
	Cull [_CullMode]

	CGPROGRAM
	#pragma surface PixShader Lambert alpha:blend vertex:VertShader noforwardadd nolightmap nodirlightmap
	#pragma target 3.0
	#pragma shader_feature __ GLOW_ON

	#include "TMPro_Properties.cginc"
	#include "TMPro.cginc"

	half _FaceShininess;
	half _OutlineShininess;

	struct Input
	{
		fixed4	color		: COLOR;
		float2	uv_MainTex;
		float2	uv2_FaceTex;
		float2  uv2_OutlineTex;
		float2	param;					// Weight, Scale
		float3	viewDirEnv;
	};

	#include "TMPro_Surface.cginc"

	ENDCG

	// Pass to render object as a shadow caster
	Pass
	{
		Name "Caster"
		Tags { "LightMode" = "ShadowCaster" }
		Offset 1, 1

		Fog {Mode Off}
		ZWrite On ZTest LEqual Cull Off

		CGPROGRAM
		#pragma vertex vert
		#pragma fragment frag
		#pragma multi_compile_shadowcaster
		#include "UnityCG.cginc"

		struct v2f
		{
			V2F_SHADOW_CASTER;
			float2	uv			: TEXCOORD1;
			float2	uv2			: TEXCOORD3;
			float	alphaClip	: TEXCOORD2;
		};

		uniform float4 _MainTex_ST;
		uniform float4 _OutlineTex_ST;
		float _OutlineWidth;
		float _FaceDilate;
		float _ScaleRatioA;

		v2f vert( appdata_base v )
		{
			v2f o;
			TRANSFER_SHADOW_CASTER(o)
			o.uv = TRANSFORM_TEX(v.texcoord, _MainTex);
			o.uv2 = TRANSFORM_TEX(v.texcoord, _OutlineTex);
			o.alphaClip = o.alphaClip = (1.0 - _OutlineWidth * _ScaleRatioA - _FaceDilate * _ScaleRatioA) / 2;
			return o;
		}

		uniform sampler2D _MainTex;

		float4 frag(v2f i) : COLOR
		{
			fixed4 texcol = tex2D(_MainTex, i.uv).a;
			clip(texcol.a - i.alphaClip);
			SHADOW_CASTER_FRAGMENT(i)
		}
		ENDCG
	}
}

CustomEditor "TMPro.EditorUtilities.TMP_SDFShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_SDF-Surface.shader`
```hlsl
Shader "TextMeshPro/Distance Field (Surface)" {

Properties {
	_FaceTex			("Fill Texture", 2D) = "white" {}
	_FaceUVSpeedX		("Face UV Speed X", Range(-5, 5)) = 0.0
	_FaceUVSpeedY		("Face UV Speed Y", Range(-5, 5)) = 0.0
	_FaceColor		    ("Fill Color", Color) = (1,1,1,1)
	_FaceDilate			("Face Dilate", Range(-1,1)) = 0

	_OutlineColor	    ("Outline Color", Color) = (0,0,0,1)
	_OutlineTex			("Outline Texture", 2D) = "white" {}
	_OutlineUVSpeedX	("Outline UV Speed X", Range(-5, 5)) = 0.0
	_OutlineUVSpeedY	("Outline UV Speed Y", Range(-5, 5)) = 0.0
	_OutlineWidth		("Outline Thickness", Range(0, 1)) = 0
	_OutlineSoftness	("Outline Softness", Range(0,1)) = 0

	_Bevel				("Bevel", Range(0,1)) = 0.5
	_BevelOffset		("Bevel Offset", Range(-0.5,0.5)) = 0
	_BevelWidth			("Bevel Width", Range(-.5,0.5)) = 0
	_BevelClamp			("Bevel Clamp", Range(0,1)) = 0
	_BevelRoundness		("Bevel Roundness", Range(0,1)) = 0

	_BumpMap 			("Normalmap", 2D) = "bump" {}
	_BumpOutline		("Bump Outline", Range(0,1)) = 0.5
	_BumpFace			("Bump Face", Range(0,1)) = 0.5

	_ReflectFaceColor	    ("Face Color", Color) = (0,0,0,1)
	_ReflectOutlineColor	("Outline Color", Color) = (0,0,0,1)
	_Cube 					("Reflection Cubemap", Cube) = "black" { /* TexGen CubeReflect */ }
	_EnvMatrixRotation  	("Texture Rotation", vector) = (0, 0, 0, 0)
	_SpecColor		        ("Specular Color", Color) = (0,0,0,1)

	_FaceShininess		("Face Shininess", Range(0,1)) = 0
	_OutlineShininess	("Outline Shininess", Range(0,1)) = 0

	_GlowColor		    ("Color", Color) = (0, 1, 0, 0.5)
	_GlowOffset			("Offset", Range(-1,1)) = 0
	_GlowInner			("Inner", Range(0,1)) = 0.05
	_GlowOuter			("Outer", Range(0,1)) = 0.05
	_GlowPower			("Falloff", Range(1, 0)) = 0.75

	_WeightNormal		("Weight Normal", float) = 0
	_WeightBold			("Weight Bold", float) = 0.5

	// Should not be directly exposed to the user
	_ShaderFlags		("Flags", float) = 0
	_ScaleRatioA		("Scale RatioA", float) = 1
	_ScaleRatioB		("Scale RatioB", float) = 1
	_ScaleRatioC		("Scale RatioC", float) = 1

	_MainTex			("Font Atlas", 2D) = "white" {}
	_TextureWidth		("Texture Width", float) = 512
	_TextureHeight		("Texture Height", float) = 512
	_GradientScale		("Gradient Scale", float) = 5.0
	_ScaleX				("Scale X", float) = 1.0
	_ScaleY				("Scale Y", float) = 1.0
	_PerspectiveFilter	("Perspective Correction", Range(0, 1)) = 0.875
	_Sharpness			("Sharpness", Range(-1,1)) = 0

	_VertexOffsetX		("Vertex OffsetX", float) = 0
	_VertexOffsetY		("Vertex OffsetY", float) = 0

	_CullMode			("Cull Mode", Float) = 0
	//_MaskCoord		("Mask Coords", vector) = (0,0,0,0)
	//_MaskSoftness		("Mask Softness", float) = 0
}

SubShader {

	Tags { "Queue"="Transparent" "IgnoreProjector"="True" "RenderType"="Transparent" }

	LOD 300
	Cull [_CullMode]

	CGPROGRAM
	#pragma surface PixShader BlinnPhong alpha:blend vertex:VertShader nolightmap nodirlightmap
	#pragma target 3.0
	#pragma shader_feature __ GLOW_ON
	#pragma glsl

	#include "TMPro_Properties.cginc"
	#include "TMPro.cginc"

	half _FaceShininess;
	half _OutlineShininess;

	struct Input
	{
		fixed4	color			: COLOR;
		float2	uv_MainTex;
		float2	uv2_FaceTex;
		float2  uv2_OutlineTex;
		float2	param;						// Weight, Scale
		float3	viewDirEnv;
	};


	#define BEVEL_ON 1
	#include "TMPro_Surface.cginc"

	ENDCG

	// Pass to render object as a shadow caster
	Pass
	{
		Name "Caster"
		Tags { "LightMode" = "ShadowCaster" }
		Offset 1, 1

		Fog {Mode Off}
		ZWrite On
		ZTest LEqual
		Cull Off

		CGPROGRAM
		#pragma vertex vert
		#pragma fragment frag
		#pragma multi_compile_shadowcaster
		#include "UnityCG.cginc"

		struct v2f
		{
			V2F_SHADOW_CASTER;
			float2	uv			: TEXCOORD1;
			float2	uv2			: TEXCOORD3;
			float	alphaClip	: TEXCOORD2;
		};

		uniform float4 _MainTex_ST;
		uniform float4 _OutlineTex_ST;
		float _OutlineWidth;
		float _FaceDilate;
		float _ScaleRatioA;

		v2f vert( appdata_base v )
		{
			v2f o;
			TRANSFER_SHADOW_CASTER(o)
			o.uv = TRANSFORM_TEX(v.texcoord, _MainTex);
			o.uv2 = TRANSFORM_TEX(v.texcoord, _OutlineTex);
			o.alphaClip = (1.0 - _OutlineWidth * _ScaleRatioA - _FaceDilate * _ScaleRatioA) / 2;
			return o;
		}

		uniform sampler2D _MainTex;

		float4 frag(v2f i) : COLOR
		{
			fixed4 texcol = tex2D(_MainTex, i.uv).a;
			clip(texcol.a - i.alphaClip);
			SHADOW_CASTER_FRAGMENT(i)
		}
		ENDCG
	}
}

CustomEditor "TMPro.EditorUtilities.TMP_SDFShaderGUI"
}


```

### File: `TextMesh Pro\Shaders\TMP_SDF.shader`
```hlsl
Shader "TextMeshPro/Distance Field" {

Properties {
	_FaceTex			("Face Texture", 2D) = "white" {}
	_FaceUVSpeedX		("Face UV Speed X", Range(-5, 5)) = 0.0
	_FaceUVSpeedY		("Face UV Speed Y", Range(-5, 5)) = 0.0
	_FaceColor		    ("Face Color", Color) = (1,1,1,1)
	_FaceDilate			("Face Dilate", Range(-1,1)) = 0

	_OutlineColor	    ("Outline Color", Color) = (0,0,0,1)
	_OutlineTex			("Outline Texture", 2D) = "white" {}
	_OutlineUVSpeedX	("Outline UV Speed X", Range(-5, 5)) = 0.0
	_OutlineUVSpeedY	("Outline UV Speed Y", Range(-5, 5)) = 0.0
	_OutlineWidth		("Outline Thickness", Range(0, 1)) = 0
	_OutlineSoftness	("Outline Softness", Range(0,1)) = 0

	_Bevel				("Bevel", Range(0,1)) = 0.5
	_BevelOffset		("Bevel Offset", Range(-0.5,0.5)) = 0
	_BevelWidth			("Bevel Width", Range(-.5,0.5)) = 0
	_BevelClamp			("Bevel Clamp", Range(0,1)) = 0
	_BevelRoundness		("Bevel Roundness", Range(0,1)) = 0

	_LightAngle			("Light Angle", Range(0.0, 6.2831853)) = 3.1416
	_SpecularColor	    ("Specular", Color) = (1,1,1,1)
	_SpecularPower		("Specular", Range(0,4)) = 2.0
	_Reflectivity		("Reflectivity", Range(5.0,15.0)) = 10
	_Diffuse			("Diffuse", Range(0,1)) = 0.5
	_Ambient			("Ambient", Range(1,0)) = 0.5

	_BumpMap 			("Normal map", 2D) = "bump" {}
	_BumpOutline		("Bump Outline", Range(0,1)) = 0
	_BumpFace			("Bump Face", Range(0,1)) = 0

	_ReflectFaceColor	("Reflection Color", Color) = (0,0,0,1)
	_ReflectOutlineColor("Reflection Color", Color) = (0,0,0,1)
	_Cube 				("Reflection Cubemap", Cube) = "black" { /* TexGen CubeReflect */ }
	_EnvMatrixRotation	("Texture Rotation", vector) = (0, 0, 0, 0)


	_UnderlayColor	    ("Border Color", Color) = (0,0,0, 0.5)
	_UnderlayOffsetX	("Border OffsetX", Range(-1,1)) = 0
	_UnderlayOffsetY	("Border OffsetY", Range(-1,1)) = 0
	_UnderlayDilate		("Border Dilate", Range(-1,1)) = 0
	_UnderlaySoftness	("Border Softness", Range(0,1)) = 0

	_GlowColor		    ("Color", Color) = (0, 1, 0, 0.5)
	_GlowOffset			("Offset", Range(-1,1)) = 0
	_GlowInner			("Inner", Range(0,1)) = 0.05
	_GlowOuter			("Outer", Range(0,1)) = 0.05
	_GlowPower			("Falloff", Range(1, 0)) = 0.75

	_WeightNormal		("Weight Normal", float) = 0
	_WeightBold			("Weight Bold", float) = 0.5

	_ShaderFlags		("Flags", float) = 0
	_ScaleRatioA		("Scale RatioA", float) = 1
	_ScaleRatioB		("Scale RatioB", float) = 1
	_ScaleRatioC		("Scale RatioC", float) = 1

	_MainTex			("Font Atlas", 2D) = "white" {}
	_TextureWidth		("Texture Width", float) = 512
	_TextureHeight		("Texture Height", float) = 512
	_GradientScale		("Gradient Scale", float) = 5.0
	_ScaleX				("Scale X", float) = 1.0
	_ScaleY				("Scale Y", float) = 1.0
	_PerspectiveFilter	("Perspective Correction", Range(0, 1)) = 0.875
	_Sharpness			("Sharpness", Range(-1,1)) = 0

	_VertexOffsetX		("Vertex OffsetX", float) = 0
	_VertexOffsetY		("Vertex OffsetY", float) = 0

	_MaskCoord			("Mask Coordinates", vector) = (0, 0, 32767, 32767)
	_ClipRect			("Clip Rect", vector) = (-32767, -32767, 32767, 32767)
	_MaskSoftnessX		("Mask SoftnessX", float) = 0
	_MaskSoftnessY		("Mask SoftnessY", float) = 0

	_StencilComp		("Stencil Comparison", Float) = 8
	_Stencil			("Stencil ID", Float) = 0
	_StencilOp			("Stencil Operation", Float) = 0
	_StencilWriteMask	("Stencil Write Mask", Float) = 255
	_StencilReadMask	("Stencil Read Mask", Float) = 255

	_CullMode			("Cull Mode", Float) = 0
	_ColorMask			("Color Mask", Float) = 15
}

SubShader {

	Tags
	{
		"Queue"="Transparent"
		"IgnoreProjector"="True"
		"RenderType"="Transparent"
	}

	Stencil
	{
		Ref [_Stencil]
		Comp [_StencilComp]
		Pass [_StencilOp]
		ReadMask [_StencilReadMask]
		WriteMask [_StencilWriteMask]
	}

	Cull [_CullMode]
	ZWrite Off
	Lighting Off
	Fog { Mode Off }
	ZTest [unity_GUIZTestMode]
	Blend One OneMinusSrcAlpha
	ColorMask [_ColorMask]

	Pass {
		CGPROGRAM
		#pragma target 3.0
		#pragma vertex VertShader
		#pragma fragment PixShader
		#pragma shader_feature __ BEVEL_ON
		#pragma shader_feature __ UNDERLAY_ON UNDERLAY_INNER
		#pragma shader_feature __ GLOW_ON

		#pragma multi_compile __ UNITY_UI_CLIP_RECT
		#pragma multi_compile __ UNITY_UI_ALPHACLIP

		#include "UnityCG.cginc"
		#include "UnityUI.cginc"
		#include "TMPro_Properties.cginc"
		#include "TMPro.cginc"

		struct vertex_t
		{
			UNITY_VERTEX_INPUT_INSTANCE_ID
			float4	position		: POSITION;
			float3	normal			: NORMAL;
			fixed4	color			: COLOR;
			float4	texcoord0		: TEXCOORD0;
			float2	texcoord1		: TEXCOORD1;
		};

		struct pixel_t
		{
			UNITY_VERTEX_INPUT_INSTANCE_ID
			UNITY_VERTEX_OUTPUT_STEREO
			float4	position		: SV_POSITION;
			fixed4	color			: COLOR;
			float2	atlas			: TEXCOORD0;		// Atlas
			float4	param			: TEXCOORD1;		// alphaClip, scale, bias, weight
			float4	mask			: TEXCOORD2;		// Position in object space(xy), pixel Size(zw)
			float3	viewDir			: TEXCOORD3;

		    #if (UNDERLAY_ON || UNDERLAY_INNER)
			float4	texcoord2		: TEXCOORD4;		// u,v, scale, bias
			fixed4	underlayColor	: COLOR1;
		    #endif

		    float4 textures			: TEXCOORD5;
		};

		// Used by Unity internally to handle Texture Tiling and Offset.
		float4 _FaceTex_ST;
		float4 _OutlineTex_ST;
		float _UIMaskSoftnessX;
        float _UIMaskSoftnessY;
        int _UIVertexColorAlwaysGammaSpace;

		pixel_t VertShader(vertex_t input)
		{
			pixel_t output;

			UNITY_INITIALIZE_OUTPUT(pixel_t, output);
			UNITY_SETUP_INSTANCE_ID(input);
			UNITY_TRANSFER_INSTANCE_ID(input,output);
			UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

			float bold = step(input.texcoord0.w, 0);

			float4 vert = input.position;
			vert.x += _VertexOffsetX;
			vert.y += _VertexOffsetY;

			float4 vPosition = UnityObjectToClipPos(vert);

			float2 pixelSize = vPosition.w;
			pixelSize /= float2(_ScaleX, _ScaleY) * abs(mul((float2x2)UNITY_MATRIX_P, _ScreenParams.xy));
			float scale = rsqrt(dot(pixelSize, pixelSize));
			scale *= abs(input.texcoord0.w) * _GradientScale * (_Sharpness + 1);
			if (UNITY_MATRIX_P[3][3] == 0) scale = lerp(abs(scale) * (1 - _PerspectiveFilter), scale, abs(dot(UnityObjectToWorldNormal(input.normal.xyz), normalize(WorldSpaceViewDir(vert)))));

			float weight = lerp(_WeightNormal, _WeightBold, bold) / 4.0;
			weight = (weight + _FaceDilate) * _ScaleRatioA * 0.5;

			float bias =(.5 - weight) + (.5 / scale);

			float alphaClip = (1.0 - _OutlineWidth * _ScaleRatioA - _OutlineSoftness * _ScaleRatioA);

		    #if GLOW_ON
			alphaClip = min(alphaClip, 1.0 - _GlowOffset * _ScaleRatioB - _GlowOuter * _ScaleRatioB);
		    #endif

			alphaClip = alphaClip / 2.0 - ( .5 / scale) - weight;

		    #if (UNDERLAY_ON || UNDERLAY_INNER)
			float4 underlayColor = _UnderlayColor;
			underlayColor.rgb *= underlayColor.a;

			float bScale = scale;
			bScale /= 1 + ((_UnderlaySoftness*_ScaleRatioC) * bScale);
			float bBias = (0.5 - weight) * bScale - 0.5 - ((_UnderlayDilate * _ScaleRatioC) * 0.5 * bScale);

			float x = -(_UnderlayOffsetX * _ScaleRatioC) * _GradientScale / _TextureWidth;
			float y = -(_UnderlayOffsetY * _ScaleRatioC) * _GradientScale / _TextureHeight;
			float2 bOffset = float2(x, y);
		    #endif

			// Generate UV for the Masking Texture
			float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
			float2 maskUV = (vert.xy - clampedRect.xy) / (clampedRect.zw - clampedRect.xy);

			// Support for texture tiling and offset
			float2 textureUV = input.texcoord1;
			float2 faceUV = TRANSFORM_TEX(textureUV, _FaceTex);
			float2 outlineUV = TRANSFORM_TEX(textureUV, _OutlineTex);


            if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
            {
                input.color.rgb = UIGammaToLinear(input.color.rgb);
            }
			output.position = vPosition;
			output.color = input.color;
			output.atlas =	input.texcoord0;
			output.param =	float4(alphaClip, scale, bias, weight);
			const half2 maskSoftness = half2(max(_UIMaskSoftnessX, _MaskSoftnessX), max(_UIMaskSoftnessY, _MaskSoftnessY));
			output.mask = half4(vert.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * maskSoftness + pixelSize.xy));
			output.viewDir =	mul((float3x3)_EnvMatrix, _WorldSpaceCameraPos.xyz - mul(unity_ObjectToWorld, vert).xyz);
			#if (UNDERLAY_ON || UNDERLAY_INNER)
			output.texcoord2 = float4(input.texcoord0 + bOffset, bScale, bBias);
			output.underlayColor =	underlayColor;
			#endif
			output.textures = float4(faceUV, outlineUV);

			return output;
		}


		fixed4 PixShader(pixel_t input) : SV_Target
		{
			UNITY_SETUP_INSTANCE_ID(input);

			float c = tex2D(_MainTex, input.atlas).a;

		    #ifndef UNDERLAY_ON
			clip(c - input.param.x);
		    #endif

			float	scale	= input.param.y;
			float	bias	= input.param.z;
			float	weight	= input.param.w;
			float	sd = (bias - c) * scale;

			float outline = (_OutlineWidth * _ScaleRatioA) * scale;
			float softness = (_OutlineSoftness * _ScaleRatioA) * scale;

			half4 faceColor = _FaceColor;
			half4 outlineColor = _OutlineColor;

			faceColor.rgb *= input.color.rgb;

			faceColor *= tex2D(_FaceTex, input.textures.xy + float2(_FaceUVSpeedX, _FaceUVSpeedY) * _Time.y);
			outlineColor *= tex2D(_OutlineTex, input.textures.zw + float2(_OutlineUVSpeedX, _OutlineUVSpeedY) * _Time.y);

			faceColor = GetColor(sd, faceColor, outlineColor, outline, softness);

		    #if BEVEL_ON
			float3 dxy = float3(0.5 / _TextureWidth, 0.5 / _TextureHeight, 0);
			float3 n = GetSurfaceNormal(input.atlas, weight, dxy);

			float3 bump = UnpackNormal(tex2D(_BumpMap, input.textures.xy + float2(_FaceUVSpeedX, _FaceUVSpeedY) * _Time.y)).xyz;
			bump *= lerp(_BumpFace, _BumpOutline, saturate(sd + outline * 0.5));
			n = normalize(n- bump);

			float3 light = normalize(float3(sin(_LightAngle), cos(_LightAngle), -1.0));

			float3 col = GetSpecular(n, light);
			faceColor.rgb += col*faceColor.a;
			faceColor.rgb *= 1-(dot(n, light)*_Diffuse);
			faceColor.rgb *= lerp(_Ambient, 1, n.z*n.z);

			fixed4 reflcol = texCUBE(_Cube, reflect(input.viewDir, -n));
			faceColor.rgb += reflcol.rgb * lerp(_ReflectFaceColor.rgb, _ReflectOutlineColor.rgb, saturate(sd + outline * 0.5)) * faceColor.a;
		    #endif

		    #if UNDERLAY_ON
			float d = tex2D(_MainTex, input.texcoord2.xy).a * input.texcoord2.z;
			faceColor += input.underlayColor * saturate(d - input.texcoord2.w) * (1 - faceColor.a);
		    #endif

		    #if UNDERLAY_INNER
			float d = tex2D(_MainTex, input.texcoord2.xy).a * input.texcoord2.z;
			faceColor += input.underlayColor * (1 - saturate(d - input.texcoord2.w)) * saturate(1 - sd) * (1 - faceColor.a);
		    #endif

		    #if GLOW_ON
			float4 glowColor = GetGlowColor(sd, scale);
			faceColor.rgb += glowColor.rgb * glowColor.a;
		    #endif

		// Alternative implementation to UnityGet2DClipping with support for softness.
		    #if UNITY_UI_CLIP_RECT
			half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(input.mask.xy)) * input.mask.zw);
			faceColor *= m.x * m.y;
		    #endif

		    #if UNITY_UI_ALPHACLIP
			clip(faceColor.a - 0.001);
		    #endif

  		    return faceColor * input.color.a;
		}
		ENDCG
	}
}

Fallback "TextMeshPro/Mobile/Distance Field"
CustomEditor "TMPro.EditorUtilities.TMP_SDFShaderGUI"
}

```

### File: `TextMesh Pro\Shaders\TMP_Sprite.shader`
```hlsl
Shader "TextMeshPro/Sprite"
{
	Properties
	{
        _MainTex            ("Sprite Texture", 2D) = "white" {}
		_Color              ("Tint", Color) = (1,1,1,1)

		_StencilComp        ("Stencil Comparison", Float) = 8
		_Stencil            ("Stencil ID", Float) = 0
		_StencilOp          ("Stencil Operation", Float) = 0
		_StencilWriteMask   ("Stencil Write Mask", Float) = 255
		_StencilReadMask    ("Stencil Read Mask", Float) = 255

		_CullMode           ("Cull Mode", Float) = 0
		_ColorMask          ("Color Mask", Float) = 15
		_ClipRect           ("Clip Rect", vector) = (-32767, -32767, 32767, 32767)

		[Toggle(UNITY_UI_ALPHACLIP)] _UseUIAlphaClip ("Use Alpha Clip", Float) = 0
	}

	SubShader
	{
		Tags
		{
			"Queue"="Transparent"
			"IgnoreProjector"="True"
			"RenderType"="Transparent"
			"PreviewType"="Plane"
			"CanUseSpriteAtlas"="True"
		}

		Stencil
		{
			Ref [_Stencil]
			Comp [_StencilComp]
			Pass [_StencilOp]
			ReadMask [_StencilReadMask]
			WriteMask [_StencilWriteMask]
		}

		Cull [_CullMode]
		Lighting Off
		ZWrite Off
		ZTest [unity_GUIZTestMode]
		Blend SrcAlpha OneMinusSrcAlpha
		ColorMask [_ColorMask]

		Pass
		{
            Name "Default"
		CGPROGRAM
			#pragma vertex vert
			#pragma fragment frag
            #pragma target 2.0

			#include "UnityCG.cginc"
			#include "UnityUI.cginc"

            #pragma multi_compile __ UNITY_UI_CLIP_RECT
            #pragma multi_compile __ UNITY_UI_ALPHACLIP

			struct appdata_t
			{
				float4 vertex   : POSITION;
				float4 color    : COLOR;
				float2 texcoord : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
			};

			struct v2f
			{
				float4 vertex			: SV_POSITION;
				fixed4 color			: COLOR;
                float2 texcoord			: TEXCOORD0;
				float4 worldPosition	: TEXCOORD1;
				float4 mask				: TEXCOORD2;
                UNITY_VERTEX_OUTPUT_STEREO
			};

            sampler2D _MainTex;
			fixed4 _Color;
			fixed4 _TextureSampleAdd;
			float4 _ClipRect;
            float4 _MainTex_ST;
		    float _UIMaskSoftnessX;
            float _UIMaskSoftnessY;
            int _UIVertexColorAlwaysGammaSpace;

            v2f vert(appdata_t v)
			{
				v2f OUT;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(OUT);
				float4 vPosition = UnityObjectToClipPos(v.vertex);
            	OUT.worldPosition = v.vertex;
				OUT.vertex = vPosition;

            	float2 pixelSize = vPosition.w;
                pixelSize /= abs(mul((float2x2)UNITY_MATRIX_P, _ScreenParams.xy));

				float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
                OUT.texcoord = TRANSFORM_TEX(v.texcoord, _MainTex);
                OUT.mask = half4(v.vertex.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * half2(_UIMaskSoftnessX, _UIMaskSoftnessY) + abs(pixelSize.xy)));

                if (_UIVertexColorAlwaysGammaSpace && !IsGammaSpace())
                {
                    v.color.rgb = UIGammaToLinear(v.color.rgb);
                }
                OUT.color = v.color * _Color;
				return OUT;
			}

			fixed4 frag(v2f IN) : SV_Target
			{
				half4 color = (tex2D(_MainTex, IN.texcoord) + _TextureSampleAdd) * IN.color;

                #if UNITY_UI_CLIP_RECT
				half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(IN.mask.xy)) * IN.mask.zw);
				color *= m.x * m.y;
				#endif

				#ifdef UNITY_UI_ALPHACLIP
					clip (color.a - 0.001);
				#endif

				return color;
			}
		    ENDCG
		}
	}
}

```

### Prefab/Scene Data: `DefaultVolumeProfile.asset`
<!-- Relational YAML Analysis: DefaultVolumeProfile.asset -->

### Prefab/Scene Data: `OutlineVolume.asset`
<!-- Relational YAML Analysis: OutlineVolume.asset -->

### Prefab/Scene Data: `URP-Windows.asset`
<!-- Relational YAML Analysis: URP-Windows.asset -->

### Prefab/Scene Data: `URP-Windows_Renderer.asset`
<!-- Relational YAML Analysis: URP-Windows_Renderer.asset -->

### Prefab/Scene Data: `prefabs\DataTables\BlockVisibilityRowPrefab.prefab`
<!-- Relational YAML Analysis: BlockVisibilityRowPrefab.prefab -->
**Hierarchy Tree:**
▼ BlockVisibilityRowPrefab [RectTransform, UnknownScript_30649d3a, BlockVisibilityRowUI]
   {fileID: 11500000, guid: 30649d3a9faa99c48a7b1166b86bf2a0, type: 3}
    m_Name:
    m_Padding:
      m_Left: 0
      m_Right: 0
      m_Top: 0
      m_Bottom: 0
    m_ChildAlignment: 4
    m_Spacing: 0
    m_ChildForceExpandWidth: 0
    m_ChildForceExpandHeight: 1
    m_ChildControlWidth: 1
    m_ChildControlHeight: 1
    m_ChildScaleWidth: 0
    m_ChildScaleHeight: 0
    m_ReverseArrangement: 0
   {fileID: 11500000, guid: b87156b3243000a45bbfb32c47c39f76, type: 3}
    m_Name:
    blockNameText: [Ref -> BlockName]
    btnIsolate: [Ref -> Isolate]
    visibilityToggle: [Ref -> Visible]
    groupText: [Ref -> Text_Group]
    orderInput: [Ref -> Input_Order]
  ▼ Text_Group [RectTransform, Native_222, UnknownScript_f4688fdb]
     {fileID: 11500000, guid: f4688fdb7df04437aeb418b961361dc5, type: 3}
      m_Name:
      m_Material: None
      m_Color: {r: 1, g: 1, b: 1, a: 1}
      m_RaycastTarget: 1
      m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}
      m_Maskable: 1
      m_OnCullStateChanged:
        m_PersistentCalls:
          m_Calls: []
      m_text: New Text
      m_isRightToLeft: 0
      m_fontAsset: {fileID: 11400000, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
      m_sharedMaterial: {fileID: 2180264, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
      m_fontSharedMaterials: []
      m_fontMaterial: None
      m_fontMaterials: []
      m_fontColor32:
        serializedVersion: 2
        rgba: 4294967295
      m_fontColor: {r: 1, g: 1, b: 1, a: 1}
      m_enableVertexGradient: 0
      m_colorMode: 3
      m_fontColorGradient:
        topLeft: {r: 1, g: 1, b: 1, a: 1}
        topRight: {r: 1, g: 1, b: 1, a: 1}
        bottomLeft: {r: 1, g: 1, b: 1, a: 1}
        bottomRight: {r: 1, g: 1, b: 1, a: 1}
      m_fontColorGradientPreset: None
      m_spriteAsset: None
      m_tintAllSprites: 0
      m_StyleSheet: None
      m_TextStyleHashCode: -1183493901
      m_overrideHtmlColors: 0
      m_faceColor:
        serializedVersion: 2
        rgba: 4294967295
      m_fontSize: 36
      m_fontSizeBase: 36
      m_fontWeight: 400
      m_enableAutoSizing: 0
      m_fontSizeMin: 18
      m_fontSizeMax: 72
      m_fontStyle: 0
      m_HorizontalAlignment: 1
      m_VerticalAlignment: 256
      m_textAlignment: 65535
      m_characterSpacing: 0
      m_wordSpacing: 0
      m_lineSpacing: 0
      m_lineSpacingMax: 0
      m_paragraphSpacing: 0
      m_charWidthMaxAdj: 0
      m_TextWrappingMode: 1
      m_wordWrappingRatios: 0.4
      m_overflowMode: 0
      m_linkedTextComponent: None
      parentLinkedComponent: None
      m_enableKerning: 0
      m_ActiveFontFeatures: 6e72656b
      m_enableExtraPadding: 0
      checkPaddingRequired: 0
      m_isRichText: 1
      m_EmojiFallbackSupport: 1
      m_parseCtrlCharacters: 1
      m_isOrthographic: 1
      m_isCullingEnabled: 0
      m_horizontalMapping: 0
      m_verticalMapping: 0
      m_uvLineOffset: 0
      m_geometrySortingOrder: 0
      m_IsTextObjectScaleStatic: 0
      m_VertexBufferAutoSizeReduction: 0
      m_useMaxVisibleDescender: 1
      m_pageToDisplay: 1
      m_margin: {x: 0, y: 0, z: 0, w: 0}
      m_isUsingLegacyAnimationComponent: 0
      m_isVolumetricText: 0
      m_hasFontAssetChanged: 0
      m_baseMaterial: None
      m_maskOffset: {x: 0, y: 0, z: 0, w: 0}
  ▼ Isolate [RectTransform, Native_222, UnknownScript_fe87c0e1, UnknownScript_4e29b1a8, UnknownScript_306cc8c2]
     {fileID: 11500000, guid: fe87c0e1cc204ed48ad3b37840f39efc, type: 3}
      m_Name:
      m_Material: None
      m_Color: {r: 1, g: 1, b: 1, a: 1}
      m_RaycastTarget: 1
      m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}
      m_Maskable: 1
      m_OnCullStateChanged:
        m_PersistentCalls:
          m_Calls: []
      m_Sprite: {fileID: 10905, guid: 0000000000000000f000000000000000, type: 0}
      m_Type: 1
      m_PreserveAspect: 0
      m_FillCenter: 1
      m_FillMethod: 4
      m_FillAmount: 1
      m_FillClockwise: 1
      m_FillOrigin: 0
      m_UseSpriteMesh: 0
      m_PixelsPerUnitMultiplier: 1
     {fileID: 11500000, guid: 4e29b1a8efbd4b44bb3f3716e73f07ff, type: 3}
      m_Name:
      m_Navigation:
        m_Mode: 3
        m_WrapAround: 0
        m_SelectOnUp: None
        m_SelectOnDown: None
        m_SelectOnLeft: None
        m_SelectOnRight: None
      m_Transition: 1
      m_Colors:
        m_NormalColor: {r: 1, g: 1, b: 1, a: 1}
        m_HighlightedColor: {r: 0.9607843, g: 0.9607843, b: 0.9607843, a: 1}
        m_PressedColor: {r: 0.78431374, g: 0.78431374, b: 0.78431374, a: 1}
        m_SelectedColor: {r: 0.9607843, g: 0.9607843, b: 0.9607843, a: 1}
        m_DisabledColor: {r: 0.78431374, g: 0.78431374, b: 0.78431374, a: 0.5019608}
        m_ColorMultiplier: 1
        m_FadeDuration: 0.1
      m_SpriteState:
        m_HighlightedSprite: None
        m_PressedSprite: None
        m_SelectedSprite: None
        m_DisabledSprite: None
      m_AnimationTriggers:
        m_NormalTrigger: Normal
        m_HighlightedTrigger: Highlighted
        m_PressedTrigger: Pressed
        m_SelectedTrigger: Selected
        m_DisabledTrigger: Disabled
      m_Interactable: 1
      m_TargetGraphic: [Ref -> Isolate]
      m_OnClick:
        m_PersistentCalls:
          m_Calls: []
     {fileID: 11500000, guid: 306cc8c2b49d7114eaa3623786fc2126, type: 3}
      m_Name:
      m_IgnoreLayout: 0
      m_MinWidth: -1
      m_MinHeight: -1
      m_PreferredWidth: 120
      m_PreferredHeight: -1
      m_FlexibleWidth: -1
      m_FlexibleHeight: -1
      m_LayoutPriority: 1
    ▼ Text (TMP) [RectTransform, Native_222, UnknownScript_f4688fdb]
       {fileID: 11500000, guid: f4688fdb7df04437aeb418b961361dc5, type: 3}
        m_Name:
        m_Material: None
        m_Color: {r: 1, g: 1, b: 1, a: 1}
        m_RaycastTarget: 1
        m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}
        m_Maskable: 1
        m_OnCullStateChanged:
          m_PersistentCalls:
            m_Calls: []
        m_text: Iso
        m_isRightToLeft: 0
        m_fontAsset: {fileID: 11400000, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
        m_sharedMaterial: {fileID: 2180264, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
        m_fontSharedMaterials: []
        m_fontMaterial: None
        m_fontMaterials: []
        m_fontColor32:
          serializedVersion: 2
          rgba: 4279900698
        m_fontColor: {r: 0.1, g: 0.1, b: 0.1, a: 1}
        m_enableVertexGradient: 0
        m_colorMode: 3
        m_fontColorGradient:
          topLeft: {r: 1, g: 1, b: 1, a: 1}
          topRight: {r: 1, g: 1, b: 1, a: 1}
          bottomLeft: {r: 1, g: 1, b: 1, a: 1}
          bottomRight: {r: 1, g: 1, b: 1, a: 1}
        m_fontColorGradientPreset: None
        m_spriteAsset: None
        m_tintAllSprites: 0
        m_StyleSheet: None
        m_TextStyleHashCode: -1183493901
        m_overrideHtmlColors: 0
        m_faceColor:
          serializedVersion: 2
          rgba: 4294967295
        m_fontSize: 24
        m_fontSizeBase: 24
        m_fontWeight: 400
        m_enableAutoSizing: 0
        m_fontSizeMin: 18
        m_fontSizeMax: 72
        m_fontStyle: 0
        m_HorizontalAlignment: 2
        m_VerticalAlignment: 512
        m_textAlignment: 65535
        m_characterSpacing: 0
        m_wordSpacing: 0
        m_lineSpacing: 0
        m_lineSpacingMax: 0
        m_paragraphSpacing: 0
        m_charWidthMaxAdj: 0
        m_TextWrappingMode: 1
        m_wordWrappingRatios: 0.4
        m_overflowMode: 0
        m_linkedTextComponent: None
        parentLinkedComponent: None
        m_enableKerning: 0
        m_ActiveFontFeatures: 6e72656b
        m_enableExtraPadding: 0
        checkPaddingRequired: 0
        m_isRichText: 1
        m_EmojiFallbackSupport: 1
        m_parseCtrlCharacters: 1
        m_isOrthographic: 1
        m_isCullingEnabled: 0
        m_horizontalMapping: 0
        m_verticalMapping: 0
        m_uvLineOffset: 0
        m_geometrySortingOrder: 0
        m_IsTextObjectScaleStatic: 0
        m_VertexBufferAutoSizeReduction: 0
        m_useMaxVisibleDescender: 1
        m_pageToDisplay: 1
        m_margin: {x: 0, y: 0, z: 0, w: 0}
        m_isUsingLegacyAnimationComponent: 0
        m_isVolumetricText: 0
        m_hasFontAssetChanged: 0
        m_baseMaterial: None
        m_maskOffset: {x: 0, y: 0, z: 0, w: 0}
  ▼ Input_Order [RectTransform, Native_222, UnknownScript_fe87c0e1, UnknownScript_2da0c512]
     {fileID: 11500000, guid: fe87c0e1cc204ed48ad3b37840f39efc, type: 3}
      m_Name:
      m_Material: None
      m_Color: {r: 1, g: 1, b: 1, a: 1}
      m_RaycastTarget: 1
      m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}
      m_Maskable: 1
      m_OnCullStateChanged:
        m_PersistentCalls:
          m_Calls: []
      m_Sprite: {fileID: 10911, guid: 0000000000000000f000000000000000, type: 0}
      m_Type: 1
      m_PreserveAspect: 0
      m_FillCenter: 1
      m_FillMethod: 4
      m_FillAmount: 1
      m_FillClockwise: 1
      m_FillOrigin: 0
      m_UseSpriteMesh: 0
      m_PixelsPerUnitMultiplier: 1
     {fileID: 11500000, guid: 2da0c512f12947e489f739169773d7ca, type: 3}
      m_Name:
      m_Navigation:
        m_Mode: 3
        m_WrapAround: 0
        m_SelectOnUp: None
        m_SelectOnDown: None
        m_SelectOnLeft: None
        m_SelectOnRight: None
      m_Transition: 1
      m_Colors:
        m_NormalColor: {r: 1, g: 1, b: 1, a: 1}
        m_HighlightedColor: {r: 0.9607843, g: 0.9607843, b: 0.9607843, a: 1}
        m_PressedColor: {r: 0.78431374, g: 0.78431374, b: 0.78431374, a: 1}
        m_SelectedColor: {r: 0.9607843, g: 0.9607843, b: 0.9607843, a: 1}
        m_DisabledColor: {r: 0.78431374, g: 0.78431374, b: 0.78431374, a: 0.5019608}
        m_ColorMultiplier: 1
        m_FadeDuration: 0.1
      m_SpriteState:
        m_HighlightedSprite: None
        m_PressedSprite: None
        m_SelectedSprite: None
        m_DisabledSprite: None
      m_AnimationTriggers:
        m_NormalTrigger: Normal
        m_HighlightedTrigger: Highlighted
        m_PressedTrigger: Pressed
        m_SelectedTrigger: Selected
        m_DisabledTrigger: Disabled
      m_Interactable: 1
      m_TargetGraphic: [Ref -> Input_Order]
      m_TextViewport: [Ref -> Text Area]
      m_TextComponent: [Ref -> Text]
      m_Placeholder: [Ref -> Placeholder]
      m_VerticalScrollbar: None
      m_VerticalScrollbarEventHandler: None
      m_LayoutGroup: None
      m_ScrollSensitivity: 1
      m_ContentType: 0
      m_InputType: 0
      m_AsteriskChar: 42
      m_KeyboardType: 0
      m_LineType: 0
      m_HideMobileInput: 0
      m_HideSoftKeyboard: 0
      m_CharacterValidation: 0
      m_RegexValue:
      m_GlobalPointSize: 14
      m_CharacterLimit: 0
      m_OnEndEdit:
        m_PersistentCalls:
          m_Calls: []
      m_OnSubmit:
        m_PersistentCalls:
          m_Calls: []
      m_OnSelect:
        m_PersistentCalls:
          m_Calls: []
      m_OnDeselect:
        m_PersistentCalls:
          m_Calls: []
      m_OnTextSelection:
        m_PersistentCalls:
          m_Calls: []
      m_OnEndTextSelection:
        m_PersistentCalls:
          m_Calls: []
      m_OnValueChanged:
        m_PersistentCalls:
          m_Calls: []
      m_OnTouchScreenKeyboardStatusChanged:
        m_PersistentCalls:
          m_Calls: []
      m_CaretColor: {r: 0.19607843, g: 0.19607843, b: 0.19607843, a: 1}
      m_CustomCaretColor: 0
      m_SelectionColor: {r: 0.65882355, g: 0.80784315, b: 1, a: 0.7529412}
      m_Text:
      m_CaretBlinkRate: 0.85
      m_CaretWidth: 1
      m_ReadOnly: 0
      m_RichText: 1
      m_GlobalFontAsset: {fileID: 11400000, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
      m_OnFocusSelectAll: 1
      m_ResetOnDeActivation: 1
      m_KeepTextSelectionVisible: 0
      m_RestoreOriginalTextOnEscape: 1
      m_isRichTextEditingAllowed: 0
      m_LineLimit: 0
      isAlert: 0
      m_InputValidator: None
      m_ShouldActivateOnSelect: 1
    ▼ Text Area [RectTransform, UnknownScript_3312d773]
       {fileID: 11500000, guid: 3312d7739989d2b4e91e6319e9a96d76, type: 3}
        m_Name:
        m_Padding: {x: -8, y: -5, z: -8, w: -5}
        m_Softness: {x: 0, y: 0}
      ▼ Text [RectTransform, Native_222, UnknownScript_f4688fdb]
         {fileID: 11500000, guid: f4688fdb7df04437aeb418b961361dc5, type: 3}
          m_Name:
          m_Material: None
          m_Color: {r: 1, g: 1, b: 1, a: 1}
          m_RaycastTarget: 1
          m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}
          m_Maskable: 1
          m_OnCullStateChanged:
            m_PersistentCalls:
              m_Calls: []
          m_text: "\u200B"
          m_isRightToLeft: 0
          m_fontAsset: {fileID: 11400000, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
          m_sharedMaterial: {fileID: 2180264, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
          m_fontSharedMaterials: []
          m_fontMaterial: None
          m_fontMaterials: []
          m_fontColor32:
            serializedVersion: 2
            rgba: 4281479730
          m_fontColor: {r: 0.19607843, g: 0.19607843, b: 0.19607843, a: 1}
          m_enableVertexGradient: 0
          m_colorMode: 3
          m_fontColorGradient:
            topLeft: {r: 1, g: 1, b: 1, a: 1}
            topRight: {r: 1, g: 1, b: 1, a: 1}
            bottomLeft: {r: 1, g: 1, b: 1, a: 1}
            bottomRight: {r: 1, g: 1, b: 1, a: 1}
          m_fontColorGradientPreset: None
          m_spriteAsset: None
          m_tintAllSprites: 0
          m_StyleSheet: None
          m_TextStyleHashCode: -1183493901
          m_overrideHtmlColors: 0
          m_faceColor:
            serializedVersion: 2
            rgba: 4294967295
          m_fontSize: 14
          m_fontSizeBase: 14
          m_fontWeight: 400
          m_enableAutoSizing: 0
          m_fontSizeMin: 18
          m_fontSizeMax: 72
          m_fontStyle: 0
          m_HorizontalAlignment: 1
          m_VerticalAlignment: 256
          m_textAlignment: 65535
          m_characterSpacing: 0
          m_wordSpacing: 0
          m_lineSpacing: 0
          m_lineSpacingMax: 0
          m_paragraphSpacing: 0
          m_charWidthMaxAdj: 0
          m_TextWrappingMode: 3
          m_wordWrappingRatios: 0.4
          m_overflowMode: 0
          m_linkedTextComponent: None
          parentLinkedComponent: None
          m_enableKerning: 0
          m_ActiveFontFeatures: 6e72656b
          m_enableExtraPadding: 1
          checkPaddingRequired: 0
          m_isRichText: 1
          m_EmojiFallbackSupport: 1
          m_parseCtrlCharacters: 1
          m_isOrthographic: 1
          m_isCullingEnabled: 0
          m_horizontalMapping: 0
          m_verticalMapping: 0
          m_uvLineOffset: 0
          m_geometrySortingOrder: 0
          m_IsTextObjectScaleStatic: 0
          m_VertexBufferAutoSizeReduction: 0
          m_useMaxVisibleDescender: 1
          m_pageToDisplay: 1
          m_margin: {x: 0, y: 0, z: 0, w: 0}
          m_isUsingLegacyAnimationComponent: 0
          m_isVolumetricText: 0
          m_hasFontAssetChanged: 0
          m_baseMaterial: None
          m_maskOffset: {x: 0, y: 0, z: 0, w: 0}
      ▼ Placeholder [RectTransform, Native_222, UnknownScript_f4688fdb, UnknownScript_306cc8c2]
         {fileID: 11500000, guid: f4688fdb7df04437aeb418b961361dc5, type: 3}
          m_Name:
          m_Material: None
          m_Color: {r: 1, g: 1, b: 1, a: 1}
          m_RaycastTarget: 1
          m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}
          m_Maskable: 1
          m_OnCullStateChanged:
            m_PersistentCalls:
              m_Calls: []
          m_text: Enter text...
          m_isRightToLeft: 0
          m_fontAsset: {fileID: 11400000, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
          m_sharedMaterial: {fileID: 2180264, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
          m_fontSharedMaterials: []
          m_fontMaterial: None
          m_fontMaterials: []
          m_fontColor32:
            serializedVersion: 2
            rgba: 2150773298
          m_fontColor: {r: 0.19607843, g: 0.19607843, b: 0.19607843, a: 0.5}
          m_enableVertexGradient: 0
          m_colorMode: 3
          m_fontColorGradient:
            topLeft: {r: 1, g: 1, b: 1, a: 1}
            topRight: {r: 1, g: 1, b: 1, a: 1}
            bottomLeft: {r: 1, g: 1, b: 1, a: 1}
            bottomRight: {r: 1, g: 1, b: 1, a: 1}
          m_fontColorGradientPreset: None
          m_spriteAsset: None
          m_tintAllSprites: 0
          m_StyleSheet: None
          m_TextStyleHashCode: -1183493901
          m_overrideHtmlColors: 0
          m_faceColor:
            serializedVersion: 2
            rgba: 4294967295
          m_fontSize: 14
          m_fontSizeBase: 14
          m_fontWeight: 400
          m_enableAutoSizing: 0
          m_fontSizeMin: 18
          m_fontSizeMax: 72
          m_fontStyle: 2
          m_HorizontalAlignment: 1
          m_VerticalAlignment: 256
          m_textAlignment: 65535
          m_characterSpacing: 0
          m_wordSpacing: 0
          m_lineSpacing: 0
          m_lineSpacingMax: 0
          m_paragraphSpacing: 0
          m_charWidthMaxAdj: 0
          m_TextWrappingMode: 0
          m_wordWrappingRatios: 0.4
          m_overflowMode: 0
          m_linkedTextComponent: None
          parentLinkedComponent: None
          m_enableKerning: 0
          m_ActiveFontFeatures: 6e72656b
          m_enableExtraPadding: 1
          checkPaddingRequired: 0
          m_isRichText: 1
          m_EmojiFallbackSupport: 1
          m_parseCtrlCharacters: 1
          m_isOrthographic: 1
          m_isCullingEnabled: 0
          m_horizontalMapping: 0
          m_verticalMapping: 0
          m_uvLineOffset: 0
          m_geometrySortingOrder: 0
          m_IsTextObjectScaleStatic: 0
          m_VertexBufferAutoSizeReduction: 0
          m_useMaxVisibleDescender: 1
          m_pageToDisplay: 1
          m_margin: {x: 0, y: 0, z: 0, w: 0}
          m_isUsingLegacyAnimationComponent: 0
          m_isVolumetricText: 0
          m_hasFontAssetChanged: 0
          m_baseMaterial: None
          m_maskOffset: {x: 0, y: 0, z: 0, w: 0}
         {fileID: 11500000, guid: 306cc8c2b49d7114eaa3623786fc2126, type: 3}
          m_Name:
          m_IgnoreLayout: 1
          m_MinWidth: -1
          m_MinHeight: -1
          m_PreferredWidth: -1
          m_PreferredHeight: -1
          m_FlexibleWidth: -1
          m_FlexibleHeight: -1
          m_LayoutPriority: 1
  ▼ BlockName [RectTransform, Native_222, UnknownScript_f4688fdb, UnknownScript_306cc8c2]
     {fileID: 11500000, guid: f4688fdb7df04437aeb418b961361dc5, type: 3}
      m_Name:
      m_Material: None
      m_Color: {r: 1, g: 1, b: 1, a: 1}
      m_RaycastTarget: 1
      m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}
      m_Maskable: 1
      m_OnCullStateChanged:
        m_PersistentCalls:
          m_Calls: []
      m_text: New Text
      m_isRightToLeft: 0
      m_fontAsset: {fileID: 11400000, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
      m_sharedMaterial: {fileID: 2180264, guid: 8f586378b4e144a9851e7b34d9b748ee, type: 2}
      m_fontSharedMaterials: []
      m_fontMaterial: None
      m_fontMaterials: []
      m_fontColor32:
        serializedVersion: 2
        rgba: 4279900698
      m_fontColor: {r: 0.1, g: 0.1, b: 0.1, a: 1}
      m_enableVertexGradient: 0
      m_colorMode: 3
      m_fontColorGradient:
        topLeft: {r: 1, g: 1, b: 1, a: 1}
        topRight: {r: 1, g: 1, b: 1, a: 1}
        bottomLeft: {r: 1, g: 1, b: 1, a: 1}
        bottomRight: {r: 1, g: 1, b: 1, a: 1}
      m_fontColorGradientPreset: None
      m_spriteAsset: None
      m_tintAllSprites: 0
      m_StyleSheet: None
      m_TextStyleHashCode: -1183493901
      m_overrideHtmlColors: 0
      m_faceColor:
        serializedVersion: 2
        rgba: 4294967295
      m_fontSize: 24
      m_fontSizeBase: 24
      m_fontWeight: 400
      m_enableAutoSizing: 0
      m_fontSizeMin: 18
      m_fontSizeMax: 72
      m_fontStyle: 0
      m_HorizontalAlignment: 2
      m_VerticalAlignment: 512
      m_textAlignment: 65535
      m_characterSpacing: 0
      m_wordSpacing: 0
      m_lineSpacing: 0
      m_lineSpacingMax: 0
      m_paragraphSpacing: 0
      m_charWidthMaxAdj: 0
      m_TextWrappingMode: 1
      m_wordWrappingRatios: 0.4
      m_overflowMode: 0
      m_linkedTextComponent: None
      parentLinkedComponent: None
      m_enableKerning: 0
      m_ActiveFontFeatures: 6e72656b
      m_enableExtraPadding: 0
      checkPaddingRequired: 0
      m_isRichText: 1
      m_EmojiFallbackSupport: 1
      m_parseCtrlCharacters: 1
      m_isOrthographic: 1
      m_isCullingEnabled: 0
      m_horizontalMapping: 0
      m_verticalMapping: 0
      m_uvLineOffset: 0
      m_geometrySortingOrder: 0
      m_IsTextObjectScaleStatic: 0
      m_VertexBufferAutoSizeReduction: 0
      m_useMaxVisibleDescender: 1
      m_pageToDisplay: 1
      m_margin: {x: 0, y: 0, z: 0, w: 0}
      m_isUsingLegacyAnimationComponent: 0
      m_isVolumetricText: 0
      m_hasFontAssetChanged: 0
      m_baseMaterial: None
      m_maskOffset: {x: 0, y: 0, z: 0, w: 0}
     {fileID: 11500000, guid: 306cc8c2b49d7114eaa3623786fc2126, type: 3}
      m_Name:
      m_IgnoreLayout: 0
      m_MinWidth: -1
      m_MinHeight: -1
      m_PreferredWidth: -1
      m_PreferredHeight: -1
      m_FlexibleWidth: 1
      m_FlexibleHeight: -1
      m_LayoutPriority: 1
  ▼ Visible [RectTransform, UnknownScript_9085046f, UnknownScript_306cc8c2]
     {fileID: 11500000, guid: 9085046f02f69544eb97fd06b6048fe2, type: 3}
      m_Name:
      m_Navigation:
        m_Mode: 3
        m_WrapAround: 0
        m_SelectOnUp: None
        m_SelectOnDown: None
        m_SelectOnLeft: None
        m_SelectOnRight: None
      m_Transition: 1
      m_Colors:
        m_NormalColor: {r: 1, g: 1, b: 1, a: 1}
        m_HighlightedColor: {r: 0.9607843, g: 0.9607843, b: 0.9607843, a: 1}
        m_PressedColor: {r: 0.78431374, g: 0.78431374, b: 0.78431374, a: 1}
        m_SelectedColor: {r: 0.9607843, g: 0.9607843, b: 0.9607843, a: 1}
        m_DisabledColor: {r: 0.78431374, g: 0.78431374, b: 0.78431374, a: 0.5019608}
        m_ColorMultiplier: 1
        m_FadeDuration: 0.1
      m_SpriteState:
        m_HighlightedSprite: None
        m_PressedSprite: None
        m_SelectedSprite: None
        m_DisabledSprite: None
      m_AnimationTriggers:
        m_NormalTrigger: Normal
        m_HighlightedTrigger: Highlighted
        m_PressedTrigger: Pressed
        m_SelectedTrigger: Selected
        m_DisabledTrigger: Disabled
      m_Interactable: 1
      m_TargetGraphic: [Ref -> Background]
      toggleTransition: 1
      graphic: [Ref -> Checkmark]
      m_Group: None
      onValueChanged:
        m_PersistentCalls:
          m_Calls: []
      m_IsOn: 1
     {fileID: 11500000, guid: 306cc8c2b49d7114eaa3623786fc2126, type: 3}
      m_Name:
      m_IgnoreLayout: 0
      m_MinWidth: -1
      m_MinHeight: -1
      m_PreferredWidth: 80
      m_PreferredHeight: -1
      m_FlexibleWidth: -1
      m_FlexibleHeight: -1
      m_LayoutPriority: 1
    ▼ Background [RectTransform, Native_222, UnknownScript_fe87c0e1]
       {fileID: 11500000, guid: fe87c0e1cc204ed48ad3b37840f39efc, type: 3}
        m_Name:
        m_Material: None
        m_Color: {r: 1, g: 1, b: 1, a: 1}
        m_RaycastTarget: 1
        m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}
        m_Maskable: 1
        m_OnCullStateChanged:
          m_PersistentCalls:
            m_Calls: []
        m_Sprite: {fileID: 10905, guid: 0000000000000000f000000000000000, type: 0}
        m_Type: 1
        m_PreserveAspect: 0
        m_FillCenter: 1
        m_FillMethod: 4
        m_FillAmount: 1
        m_FillClockwise: 1
        m_FillOrigin: 0
        m_UseSpriteMesh: 0
        m_PixelsPerUnitMultiplier: 1
      ▼ Checkmark [RectTransform, Native_222, UnknownScript_fe87c0e1]
         {fileID: 11500000, guid: fe87c0e1cc204ed48ad3b37840f39efc, type: 3}
          m_Name:
          m_Material: None
          m_Color: {r: 1, g: 1, b: 1, a: 1}
          m_RaycastTarget: 1
          m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}
          m_Maskable: 1
          m_OnCullStateChanged:
            m_PersistentCalls:
              m_Calls: []
          m_Sprite: {fileID: 10901, guid: 0000000000000000f000000000000000, type: 0}
          m_Type: 0
          m_PreserveAspect: 0
          m_FillCenter: 1
          m_FillMethod: 4
          m_FillAmount: 1
          m_FillClockwise: 1
          m_FillOrigin: 0
          m_UseSpriteMesh: 0
          m_PixelsPerUnitMultiplier: 1

