# 📁 ディレクトリコード & プレハブ 解析結果 (Part 1)

- **ターゲットディレクトリ:** `C:/盧/Karigumi6.2/Assets`
- **生成日時:** `2026-07-29 14:10:41`

---

### File: `Editor\BlockCoordinateSystemDisplayEditor.cs`
```csharp
// ===============================================
// BlockCoordinateSystemDisplayEditor.cs
// Editor Extension for Coordinate System Creation
// ===============================================

using UnityEngine;
using UnityEditor;

[CustomEditor(typeof(BlockCoordinateSystemDisplay))]
public class BlockCoordinateSystemDisplayEditor : Editor
{
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        GUILayout.Space(15);

        if (GUILayout.Button("Create Coordinate Systems (OB/OC/OG Blocks)", GUILayout.Height(40)))
        {
            ((BlockCoordinateSystemDisplay)target).CreateCoordinateSystems();
        }

        if (GUILayout.Button("Clear All Coordinate Systems", GUILayout.Height(30)))
        {
            ((BlockCoordinateSystemDisplay)target).ClearCoordinateSystems();
        }
    }
}

```

### File: `Editor\BlockLabelDisplayEditor.cs`
```csharp
using UnityEngine;
using UnityEditor;

[CustomEditor(typeof(BlockLabelDisplay))]
public class BlockLabelDisplayEditor : Editor
{
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        GUILayout.Space(15);

        if (GUILayout.Button("Create Block Labels (ID + Name)", GUILayout.Height(40)))
        {
            ((BlockLabelDisplay)target).CreateLabels();
        }

        if (GUILayout.Button("Clear All Labels", GUILayout.Height(30)))
        {
            ((BlockLabelDisplay)target).ClearLabels();
        }

        if (GUILayout.Button("Toggle Labels Visibility", GUILayout.Height(30)))
        {
            ((BlockLabelDisplay)target).ToggleLabels();
        }
    }
}
```

### File: `Editor\BlockOrganizerEditor.cs`
```csharp
using UnityEngine;
using UnityEditor;

[CustomEditor(typeof(BlockOrganizer))]
public class BlockOrganizerEditor : Editor
{
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        GUILayout.Space(10);
        if (GUILayout.Button("Organize Model into Design & Measured Blocks", GUILayout.Height(40)))
        {
            ((BlockOrganizer)target).OrganizeIntoBlocks();
        }
    }
}

```

### File: `Editor\CADBlockMerger.cs`
```csharp
// ===============================================
// CADBlockMerger.cs
// PRODUCTION VERSION V3 - With Vertex Color Stripping
// ===============================================

using UnityEngine;
using UnityEditor;
using System.Collections.Generic;

public class CADBlockMerger : MonoBehaviour
{
    [MenuItem("GameObject/CAD Tools/Merge Selected Block (Solids)", false, 0)]
    static void MergeSelectedBlock()
    {
        GameObject selectedObj = Selection.activeGameObject;

        if (selectedObj == null)
        {
            EditorUtility.DisplayDialog("Selection Error",
                "Please select a Block parent node (e.g., '020 OB1') in the Hierarchy first.", "OK");
            return;
        }

        MeshFilter[] childMeshFilters = selectedObj.GetComponentsInChildren<MeshFilter>(true);
        List<CombineInstance> combineList = new List<CombineInstance>();
        Material sharedMaterial = null;

        Matrix4x4 parentInverseMatrix = selectedObj.transform.worldToLocalMatrix;

        foreach (MeshFilter mf in childMeshFilters)
        {
            if (mf.gameObject == selectedObj) continue;

            // Strict Visibility Filtering (Ignore hidden proxies)
            if (!mf.gameObject.activeInHierarchy) continue;

            MeshRenderer mr = mf.GetComponent<MeshRenderer>();
            if (mr == null || !mr.enabled) continue;

            if (sharedMaterial == null) sharedMaterial = mr.sharedMaterial;

            CombineInstance ci = new CombineInstance();
            ci.mesh = mf.sharedMesh;
            ci.transform = parentInverseMatrix * mf.transform.localToWorldMatrix;
            combineList.Add(ci);
        }

        if (combineList.Count == 0) return;

        Mesh finalMesh = new Mesh();
        finalMesh.name = "MergedMesh_" + selectedObj.name;
        finalMesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;

        finalMesh.CombineMeshes(combineList.ToArray(), true, true);
        finalMesh.RecalculateBounds();

        // ==========================================
        // CRITICAL FIX 3: Strip Vertex Colors
        // ==========================================
        // Industrial CAD often contains corrupted or partial vertex colors.
        // Stripping them forces the shader to use the pure Material Albedo, 
        // completely eliminating black spots and rendering artifacts.
        finalMesh.colors32 = null;

        // Keep tangets and normals untouched for CAD data
        // finalMesh.RecalculateNormals(); 
        // finalMesh.RecalculateTangents(); 

        MeshFilter parentFilter = selectedObj.GetComponent<MeshFilter>();
        if (parentFilter == null) parentFilter = selectedObj.AddComponent<MeshFilter>();
        parentFilter.sharedMesh = finalMesh;

        MeshRenderer parentRenderer = selectedObj.GetComponent<MeshRenderer>();
        if (parentRenderer == null) parentRenderer = selectedObj.AddComponent<MeshRenderer>();
        if (sharedMaterial != null) parentRenderer.sharedMaterial = sharedMaterial;

        MeshCollider collider = selectedObj.GetComponent<MeshCollider>();
        if (collider == null) collider = selectedObj.AddComponent<MeshCollider>();
        collider.sharedMesh = finalMesh;

        List<GameObject> childrenToDestroy = new List<GameObject>();
        foreach (Transform child in selectedObj.transform)
        {
            childrenToDestroy.Add(child.gameObject);
        }

        foreach (GameObject child in childrenToDestroy)
        {
            Undo.DestroyObjectImmediate(child);
        }

        Debug.Log($"<color=green>[CAD Tools] V3 Merge Complete: {combineList.Count} Solids merged, Vertex Colors stripped!</color>");
    }
}
```

### File: `Editor\CADMaterialOptimizer.cs`
```csharp
// ===============================================
// CADMaterialOptimizer.cs
// PRODUCTION EDITOR TOOL - Forces CAD-style soft lighting on custom URP materials
// Place this inside an "Editor" folder.
// ===============================================

using UnityEngine;
using UnityEditor;

public class CADMaterialOptimizer : EditorWindow
{
    [MenuItem("Tools/Optimize CAD Materials (Soft Look)")]
    public static void OptimizeMaterials()
    {
        // Find all materials in the project
        string[] materialGuids = AssetDatabase.FindAssets("t:Material");
        int updatedCount = 0;

        foreach (string guid in materialGuids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            Material mat = AssetDatabase.LoadAssetAtPath<Material>(path);

            if (mat == null) continue;

            // Target specifically our block and point materials
            bool isTargetMaterial = mat.name.Contains("Block_Design") ||
                                    mat.name.Contains("Block_Measured") ||
                                    mat.name.Contains("Point");

            if (isTargetMaterial)
            {
                // Force properties even if they are hidden in the custom Shader UI

                // 1. Remove metallicness to keep base color pure
                if (mat.HasProperty("_Metallic"))
                    mat.SetFloat("_Metallic", 0.0f);

                // 2. Lower smoothness to create a matte/soft plastic CAD look
                if (mat.HasProperty("_Smoothness"))
                    mat.SetFloat("_Smoothness", 0.15f);

                // Fallback for some URP lit variants
                if (mat.HasProperty("_Glossiness"))
                    mat.SetFloat("_Glossiness", 0.15f);

                // Mark the asset as changed so Unity saves it
                EditorUtility.SetDirty(mat);
                updatedCount++;

                Debug.Log($"<color=cyan>[CADMaterialOptimizer] Optimized material: {mat.name}</color>");
            }
        }

        // Save all changes to disk
        AssetDatabase.SaveAssets();
        Debug.Log($"<color=green>[CADMaterialOptimizer] SUCCESS: {updatedCount} materials updated to soft CAD visuals.</color>");
    }
}
```

### File: `Editor\JoiningCoordinateSystemCreatorEditor.cs`
```csharp
// ===============================================
// JoiningCoordinateSystemCreatorEditor.cs
// Custom Editor for JoiningCoordinateSystemCreator
// ===============================================
// PRODUCTION EDITOR 2026-03-05:
//   - Big green/red buttons for quick actions
//   - Auto-shows new planeScale field
//   - Full English comments + HelpBox for production use

using UnityEngine;
using UnityEditor;

[CustomEditor(typeof(JoiningCoordinateSystemCreator))]
public class JoiningCoordinateSystemCreatorEditor : Editor
{
    public override void OnInspectorGUI()
    {
        // Draw all public fields (including planeScale)
        DrawDefaultInspector();

        EditorGUILayout.Space(10);
        EditorGUILayout.LabelField("=== Quick Actions ===", EditorStyles.boldLabel);

        // Big green Begin Selecting button
        GUI.backgroundColor = new Color(0.0f, 0.8f, 0.0f);
        if (GUILayout.Button("Begin Selecting 3 Joining Points", GUILayout.Height(45)))
        {
            ((JoiningCoordinateSystemCreator)target).BeginSelecting();
        }
        GUI.backgroundColor = Color.white;

        // Big red Clear button
        GUI.backgroundColor = new Color(0.8f, 0.0f, 0.0f);
        if (GUILayout.Button("Clear All Joint Coordinate Systems", GUILayout.Height(35)))
        {
            ((JoiningCoordinateSystemCreator)target).ClearAllSystems();
        }
        GUI.backgroundColor = Color.white;

        EditorGUILayout.HelpBox(
            "1. Enter Play Mode first\n" +
            "2. Click the green button\n" +
            "3. Click any 3 Joining points\n" +
            "planeScale controls Mesh size (0.7 = 30% smaller)",
            MessageType.Info);
    }
}
```

### File: `Editor\UILayoutOptimizer.cs`
```csharp
﻿#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

/// <summary>
/// 汎用的なUIレイアウト最適化ツール。
/// 特定のオブジェクト名に依存せず、選択したUIノードに標準的なレイアウトパターンを自動注入する。
/// </summary>
public class UILayoutOptimizer
{
    // ==========================================
    // 1. 水平ツールバーモード (Horizontal Toolbar)
    // ==========================================
    [MenuItem("GameObject/UI Tools/排版: 设为水平工具栏 (自适应横排)", false, 20)]
    public static void SetupHorizontalToolbar(MenuCommand menuCommand)
    {
        GameObject selectedGO = menuCommand.context as GameObject;
        if (!IsValidUI(selectedGO)) return;

        Undo.RegisterFullObjectHierarchyUndo(selectedGO, "Setup Horizontal Toolbar");

        HorizontalLayoutGroup hLayout = GetOrAddComponent<HorizontalLayoutGroup>(selectedGO);
        hLayout.childControlWidth = true;
        hLayout.childControlHeight = true;
        hLayout.childForceExpandWidth = false;
        hLayout.childForceExpandHeight = true;
        hLayout.spacing = 10f;
        hLayout.padding = new RectOffset(10, 10, 5, 5);

        foreach (Transform child in selectedGO.transform)
        {
            LayoutElement layoutElem = GetOrAddComponent<LayoutElement>(child.gameObject);

            if (child.GetComponent<TextMeshProUGUI>() != null || child.GetComponent<Text>() != null)
            {
                layoutElem.flexibleWidth = 1f;
            }
            else
            {
                RectTransform rect = child.GetComponent<RectTransform>();
                layoutElem.minWidth = rect.rect.width > 0 ? rect.rect.width : 60f;
                layoutElem.flexibleWidth = 0f;
            }
        }

        Debug.Log($"<color=#00E5FF>[UI Optimizer]</color> '{selectedGO.name}' に水平ツールバーレイアウトを適用しました。");
    }

    // ==========================================
    // 2. 垂直リストモード (Vertical List)
    // ==========================================
    [MenuItem("GameObject/UI Tools/排版: 设为垂直自适应列表 (向下延展)", false, 21)]
    public static void SetupVerticalList(MenuCommand menuCommand)
    {
        GameObject selectedGO = menuCommand.context as GameObject;
        if (!IsValidUI(selectedGO)) return;

        Undo.RegisterFullObjectHierarchyUndo(selectedGO, "Setup Vertical List");

        VerticalLayoutGroup vLayout = GetOrAddComponent<VerticalLayoutGroup>(selectedGO);
        vLayout.childControlWidth = true;
        vLayout.childControlHeight = true;
        vLayout.childForceExpandWidth = true;
        vLayout.childForceExpandHeight = false;
        vLayout.spacing = 5f;

        ContentSizeFitter fitter = GetOrAddComponent<ContentSizeFitter>(selectedGO);
        fitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
        fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

        Debug.Log($"<color=#00E5FF>[UI Optimizer]</color> '{selectedGO.name}' に垂直自适应リストレイアウトを適用しました。");
    }

    // ==========================================
    // 3. アンカー自動スナップ (Smart Anchor Snap)
    // ==========================================
    [MenuItem("GameObject/UI Tools/排版: 锚点智能吸附边界 (适配多分辨率)", false, 22)]
    public static void SnapAnchors(MenuCommand menuCommand)
    {
        GameObject selectedGO = menuCommand.context as GameObject;
        if (!IsValidUI(selectedGO)) return;

        Undo.RecordObject(selectedGO.GetComponent<RectTransform>(), "Snap Anchors");

        RectTransform rect = selectedGO.GetComponent<RectTransform>();
        RectTransform parentRect = selectedGO.transform.parent?.GetComponent<RectTransform>();

        if (parentRect == null) return;

        Vector2 offsetMin = rect.offsetMin;
        Vector2 offsetMax = rect.offsetMax;
        Vector2 anchorMin = rect.anchorMin;
        Vector2 anchorMax = rect.anchorMax;

        float parentWidth = parentRect.rect.width;
        float parentHeight = parentRect.rect.height;

        if (parentWidth == 0 || parentHeight == 0) return;

        Vector2 newAnchorMin = new Vector2(
            anchorMin.x + (offsetMin.x / parentWidth),
            anchorMin.y + (offsetMin.y / parentHeight)
        );
        Vector2 newAnchorMax = new Vector2(
            anchorMax.x + (offsetMax.x / parentWidth),
            anchorMax.y + (offsetMax.y / parentHeight)
        );

        rect.anchorMin = newAnchorMin;
        rect.anchorMax = newAnchorMax;
        rect.offsetMin = Vector2.zero;
        rect.offsetMax = Vector2.zero;

        Debug.Log($"<color=#00E5FF>[UI Optimizer]</color> '{selectedGO.name}' のアンカーを現在の境界にスナップしました。");
    }

    // ==========================================
    // 4. グリッドレイアウトモード (Grid Layout) - 新規追加
    // ==========================================
    [MenuItem("GameObject/UI Tools/排版: 设为标准网格布局 (等比矩阵)", false, 23)]
    public static void SetupGridLayout(MenuCommand menuCommand)
    {
        GameObject selectedGO = menuCommand.context as GameObject;
        if (!IsValidUI(selectedGO)) return;

        Undo.RegisterFullObjectHierarchyUndo(selectedGO, "Setup Grid Layout");

        GridLayoutGroup gLayout = GetOrAddComponent<GridLayoutGroup>(selectedGO);

        // デフォルト設定：100x100のセル、間隔10
        gLayout.cellSize = new Vector2(100f, 100f);
        gLayout.spacing = new Vector2(10f, 10f);
        gLayout.padding = new RectOffset(10, 10, 10, 10);

        gLayout.startCorner = GridLayoutGroup.Corner.UpperLeft;
        gLayout.startAxis = GridLayoutGroup.Axis.Horizontal;
        gLayout.childAlignment = TextAnchor.UpperLeft;

        // 列数や行数を制限せずに、親の幅に応じて自動で折り返す
        gLayout.constraint = GridLayoutGroup.Constraint.Flexible;

        Debug.Log($"<color=#00E5FF>[UI Optimizer]</color> '{selectedGO.name}' にグリッドレイアウトを適用しました。");
    }

    // --- 補助メソッド (Helper Methods) ---

    private static bool IsValidUI(GameObject go)
    {
        if (go == null) return false;
        if (go.GetComponent<RectTransform>() == null)
        {
            Debug.LogWarning("[UI Optimizer] 選択されたオブジェクトはUI要素（RectTransform）ではありません。");
            return false;
        }
        return true;
    }

    private static T GetOrAddComponent<T>(GameObject target) where T : Component
    {
        T component = target.GetComponent<T>();
        if (component == null)
        {
            component = Undo.AddComponent<T>(target);
        }
        return component;
    }
}
#endif
```

### File: `Editor\UIThemeStylizer.cs`
```csharp
﻿#if UNITY_EDITOR
// ===============================================
// UIThemeStylizer.cs
// PRODUCTION VERSION - 高コントラスト・ダークテーマ (High Contrast Dark)
// ===============================================

using UnityEditor;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

/// <summary>
/// 選択したUI要素に「高コントラスト・ダークテーマ」を適用するツール。
/// 黒つぶれを防ぐための中深灰色ベース、およびスクロールバーの完全なスタイリングを含みます。
/// </summary>
public class UIThemeStylizer
{
    [MenuItem("GameObject/UI Tools/应用高对比度深色主题 (局部)", false, 10)]
    public static void StylizeSelectedUI(MenuCommand menuCommand)
    {
        GameObject selectedGO = menuCommand.context as GameObject;
        if (selectedGO == null || selectedGO.GetComponent<RectTransform>() == null)
        {
            Debug.LogWarning("[UI Stylizer] 有効なUI要素が選択されていません。");
            return;
        }

        Undo.RegisterFullObjectHierarchyUndo(selectedGO, "Apply High Contrast Dark Theme");

        // ==========================================
        // 🎨 高对比度工业深色调色板 (高コントラストパレット)
        // ==========================================
        // 提高整体亮度，避免“死黑”。带有微弱蓝灰色调以增加现代感。
        ColorUtility.TryParseHtmlString("#2A2A30", out Color baseBgColor);
        baseBgColor.a = 0.95f;

        // 标题栏使用更深的颜色进行物理区分
        ColorUtility.TryParseHtmlString("#1A1A1E", out Color headerBgColor);
        headerBgColor.a = 0.98f;

        // 强调色：保持工业青色，用于标题和激活状态
        ColorUtility.TryParseHtmlString("#00E5FF", out Color accentColor);

        // 文本：纯白，确保在灰色底板上的绝对可读性
        ColorUtility.TryParseHtmlString("#FFFFFF", out Color textColor);

        // 边框色：明亮的浅灰色，用于勾勒控件的物理边界
        ColorUtility.TryParseHtmlString("#5A5A65", out Color borderColor);

        // 交互控件（按钮/滚动条滑块）的基础色
        ColorUtility.TryParseHtmlString("#3D3D46", out Color elementNormalColor);
        ColorUtility.TryParseHtmlString("#4D4D58", out Color elementHoverColor);

        // 滚动条轨道底色：极深色，形成凹陷感
        ColorUtility.TryParseHtmlString("#121215", out Color trackBgColor);

        int panelCount = 0, btnCount = 0, textCount = 0, scrollbarCount = 0;

        // --- 1. 面板层级处理 (パネルの処理) ---
        Image[] allImages = selectedGO.GetComponentsInChildren<Image>(true);
        foreach (Image img in allImages)
        {
            string objName = img.gameObject.name.ToLower();
            bool isInteractive = img.GetComponent<Button>() != null ||
                                 img.GetComponent<Toggle>() != null ||
                                 img.GetComponent<Scrollbar>() != null;

            if (!isInteractive && (objName.Contains("panel") || objName.Contains("bg") || objName.Contains("header") || objName.Contains("viewport")))
            {
                img.sprite = null;
                img.color = objName.Contains("header") ? headerBgColor : baseBgColor;

                Outline outline = img.gameObject.GetComponent<Outline>();
                if (outline == null) outline = img.gameObject.AddComponent<Outline>();
                outline.effectColor = borderColor;
                // 边框向外扩展，形成硬朗的切边效果
                outline.effectDistance = new Vector2(1, -1);

                panelCount++;
            }
        }

        // --- 2. 交互按钮处理 (ボタンの処理) ---
        Button[] allButtons = selectedGO.GetComponentsInChildren<Button>(true);
        foreach (Button btn in allButtons)
        {
            btn.transition = Selectable.Transition.ColorTint;
            ColorBlock cb = btn.colors;
            cb.normalColor = elementNormalColor;
            cb.highlightedColor = elementHoverColor;
            cb.pressedColor = accentColor;
            cb.selectedColor = elementNormalColor;
            cb.colorMultiplier = 1f;
            btn.colors = cb;

            if (btn.TryGetComponent(out Image img))
            {
                img.sprite = null;
                img.color = Color.white;

                Outline outline = img.gameObject.GetComponent<Outline>();
                if (outline == null) outline = img.gameObject.AddComponent<Outline>();
                // 按钮使用较暗的边框，以突出按钮本体
                outline.effectColor = new Color(0, 0, 0, 0.6f);
                outline.effectDistance = new Vector2(1, -1);
            }
            btnCount++;
        }

        // --- 3. 滚动条处理 (スクロールバーの処理) ---
        Scrollbar[] allScrollbars = selectedGO.GetComponentsInChildren<Scrollbar>(true);
        foreach (Scrollbar sb in allScrollbars)
        {
            sb.transition = Selectable.Transition.ColorTint;
            ColorBlock cb = sb.colors;
            cb.normalColor = elementNormalColor;
            cb.highlightedColor = elementHoverColor;
            cb.pressedColor = accentColor;
            cb.selectedColor = elementNormalColor;
            cb.colorMultiplier = 1f;
            sb.colors = cb;

            // 軌道（背景）の処理：凹んだ印象を与える深い色
            if (sb.TryGetComponent(out Image bgImg))
            {
                bgImg.sprite = null;
                bgImg.color = trackBgColor;
            }

            // ハンドル（つまみ）の処理：明るい要素色
            if (sb.handleRect != null && sb.handleRect.TryGetComponent(out Image handleImg))
            {
                handleImg.sprite = null;
                handleImg.color = Color.white; // ベースを白にし、ColorBlockで染める
            }
            scrollbarCount++;
        }

        // --- 4. 字体高对比度处理 (テキストの処理) ---
        TextMeshProUGUI[] allTexts = selectedGO.GetComponentsInChildren<TextMeshProUGUI>(true);
        foreach (TextMeshProUGUI txt in allTexts)
        {
            string txtName = txt.gameObject.name.ToLower();
            if (txtName.Contains("title") || txtName.Contains("header"))
            {
                txt.color = accentColor;
            }
            else
            {
                // 正文使用绝对纯白，保证在高频次阅读时的无障碍体验
                txt.color = textColor;
            }
            textCount++;
        }

        Debug.Log($"<color=#00E5FF>[UI Stylizer]</color> 高对比度深色主题应用完成！面板: {panelCount}, 按钮: {btnCount}, 滚动条: {scrollbarCount}, 文本: {textCount}");
    }
}
#endif
```

### File: `Editor\GeminiAgent\ドメインハンドラー\FileSystemCommandHandler.cs`
```csharp
﻿using System;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// ファイルシステムおよびディレクトリ操作を処理するハンドラー
/// (处理文件系统及目录操作的处理器)
/// </summary>
public class FileSystemCommandHandler : IUnityCommandHandler
{
    public string[] SupportedActionTypes => new[] { "EXPLORE_DIRECTORY", "SEARCH_ASSETS", "READ_FILE", "MOVE_ASSET", "MOVE_FILE", "CREATE_FOLDER" };

    public string Execute(DeveloperCommandData command)
    {
        switch (command.actionType)
        {
            case "EXPLORE_DIRECTORY": return ExecuteExploreDirectory(command);
            case "SEARCH_ASSETS": return ExecuteSearchAssets(command);
            case "READ_FILE": return ExecuteReadFile(command);
            case "MOVE_ASSET":
            case "MOVE_FILE": return ExecuteMoveFile(command);
            case "CREATE_FOLDER": return ExecuteCreateFolder(command);
            default: return "⚠️ 未知のファイルシステムコマンド";
        }
    }

    private static string ExecuteExploreDirectory(DeveloperCommandData command)
    {
        string targetPath = string.IsNullOrEmpty(command.directoryPath) ? "Assets" : command.directoryPath;
        if (!Directory.Exists(targetPath)) return $"⚠️ 指定フォルダが存在しません: '{targetPath}'";

        StringBuilder sb = new StringBuilder();
        sb.AppendLine($"📂 <b>ディレクトリ探索結果 [{targetPath}]:</b>");

        foreach (string dir in Directory.GetDirectories(targetPath))
            sb.AppendLine($"  📁 {Path.GetFileName(dir)}/");

        foreach (string file in Directory.GetFiles(targetPath))
        {
            if (!file.EndsWith(".meta")) sb.AppendLine($"  📄 {Path.GetFileName(file)}");
        }

        return sb.ToString().TrimEnd();
    }

    private static string ExecuteSearchAssets(DeveloperCommandData command)
    {
        if (string.IsNullOrEmpty(command.searchFilter)) return "⚠️ 検索フィルター (searchFilter) が指定されていません。";

        string[] guids = AssetDatabase.FindAssets(command.searchFilter);
        if (guids == null || guids.Length == 0) return $"🔍 フィルター '{command.searchFilter}' に一致するアセットなし。";

        StringBuilder sb = new StringBuilder();
        sb.AppendLine($"🔍 <b>アセット検索結果 ('{command.searchFilter}'):</b>");

        int displayCount = Mathf.Min(guids.Length, 15);
        for (int i = 0; i < displayCount; i++)
        {
            sb.AppendLine($"  • <color=cyan>{AssetDatabase.GUIDToAssetPath(guids[i])}</color>");
        }

        return sb.ToString().TrimEnd();
    }

    private static string ExecuteReadFile(DeveloperCommandData command)
    {
        if (string.IsNullOrEmpty(command.sourceFilePath) || !File.Exists(command.sourceFilePath))
            return $"⚠️ ファイルが存在しません: '{command.sourceFilePath}'";

        try
        {
            string content = File.ReadAllText(command.sourceFilePath, Encoding.UTF8);
            return $"📖 <b>ファイル内容 [{command.sourceFilePath}]:</b>\n```\n{content}\n```";
        }
        catch (Exception ex)
        {
            return $"❌ 読み込み失敗 ({command.sourceFilePath}): {ex.Message}";
        }
    }

    private static string ExecuteMoveFile(DeveloperCommandData command)
    {
        if (string.IsNullOrEmpty(command.sourceFilePath) || string.IsNullOrEmpty(command.targetFilePath))
            return "⚠️ 移動元または移動先のパスが不足しています。";

        string targetDir = Path.GetDirectoryName(command.targetFilePath);
        if (!Directory.Exists(targetDir)) Directory.CreateDirectory(targetDir);

        string errorMsg = AssetDatabase.MoveAsset(command.sourceFilePath, command.targetFilePath);
        if (string.IsNullOrEmpty(errorMsg))
        {
            AssetDatabase.Refresh();
            return $"📁 <b>スクリプト移動完了:</b> <color=cyan>{command.sourceFilePath}</color> ➔ <color=green>{command.targetFilePath}</color>";
        }
        return $"❌ 移動エラー ({command.sourceFilePath}): {errorMsg}";
    }

    private static string ExecuteCreateFolder(DeveloperCommandData command)
    {
        if (string.IsNullOrEmpty(command.targetFilePath))
            return "[CREATE_FOLDER] ❌ エラー: targetFilePath が未指定です。(未指定目标路径)";

        string pathSuffix = command.targetFilePath.StartsWith("Assets/") ? command.targetFilePath.Substring(7) : command.targetFilePath;
        string fullDirectoryPath = System.IO.Path.Combine(UnityEngine.Application.dataPath, pathSuffix);

        if (!System.IO.Directory.Exists(fullDirectoryPath))
        {
            System.IO.Directory.CreateDirectory(fullDirectoryPath);
            UnityEditor.AssetDatabase.Refresh();
            return $"[CREATE_FOLDER] ✅ 成功: フォルダを作成しました ➔ {command.targetFilePath}";
        }
        else
        {
            return $"[CREATE_FOLDER] ⚠️ スキップ: フォルダは既に存在します (文件夹已存在) ➔ {command.targetFilePath}";
        }
    }
}
```

### File: `Editor\GeminiAgent\ドメインハンドラー\GameObjectCommandhandler.cs`
```csharp
﻿using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

/// <summary>
/// 標準的なGameObjectおよびプレハブ、UIコンポーネントの操作を処理するハンドラー
/// (处理标准 GameObject 及预制体、UI 组件生成与修改的处理器)
/// </summary>
public class GameObjectCommandHandler : IUnityCommandHandler
{
    private const string MATERIAL_SAVE_PATH = "Assets/Materials/Generated/";

    public string[] SupportedActionTypes => new[] {
        "UNPACK_PREFAB", "CREATE_PREFAB_VARIANT", "SET_PROPERTY",
        "CREATE_UI_ELEMENT", "CREATE_MATERIAL", "INSTANTIATE_PREFAB",
        "DELETE_OBJECT", "CREATE_OBJECT", "MODIFY_TRANSFORM", "ADD_COMPONENT"
    };

    public string Execute(DeveloperCommandData command)
    {
        switch (command.actionType)
        {
            case "UNPACK_PREFAB": return ExecuteUnpackPrefab(command);
            case "CREATE_PREFAB_VARIANT": return ExecuteCreatePrefabVariant(command);
            case "SET_PROPERTY": return ExecuteSetSerializedProperty(command);
            case "CREATE_UI_ELEMENT": return ExecuteCreateUIElement(command);
            case "CREATE_MATERIAL": return ExecuteCreateMaterial(command);
            case "INSTANTIATE_PREFAB": return ExecuteInstantiatePrefab(command);
            case "DELETE_OBJECT": return ExecuteDeleteObject(command);
            case "CREATE_OBJECT":
            case "MODIFY_TRANSFORM":
            case "ADD_COMPONENT":
            default: return ExecuteStandardGameObjectOperation(command);
        }
    }

    private static string ExecuteUnpackPrefab(DeveloperCommandData command)
    {
        GameObject targetObj = GeminiCommandUtils.ResolveTargetGameObject(command.targetObjectName, command.childPath);
        if (targetObj == null) return $"⚠️ 対象なし (Target not found): {command.targetObjectName}";

        if (!PrefabUtility.IsAnyPrefabInstanceRoot(targetObj))
            return $"⚠️ 対象はプレハブルー卜ではありません (Target is not a prefab root): {targetObj.name}";

        PrefabUnpackMode mode = command.unpackMode == "Completely" ? PrefabUnpackMode.Completely : PrefabUnpackMode.OutermostRoot;

        Undo.RegisterFullObjectHierarchyUndo(targetObj, "Unpack Prefab");
        PrefabUtility.UnpackPrefabInstance(targetObj, mode, InteractionMode.AutomatedAction);

        return $"📦 <b>プレハブ解体 (Unpack Prefab):</b> {targetObj.name} [{mode}]";
    }

    private static string ExecuteCreatePrefabVariant(DeveloperCommandData command)
    {
        if (string.IsNullOrEmpty(command.prefabAssetPath) || string.IsNullOrEmpty(command.variantSavePath))
            return "⚠️ 元プレハブのパスまたはバリアント保存パスが不足しています。";

        GameObject basePrefab = AssetDatabase.LoadAssetAtPath<GameObject>(command.prefabAssetPath);
        if (basePrefab == null) return $"⚠️ 元プレハブが見つかりません: {command.prefabAssetPath}";

        string targetDir = Path.GetDirectoryName(command.variantSavePath);
        if (!Directory.Exists(targetDir)) Directory.CreateDirectory(targetDir);

        GameObject instance = (GameObject)PrefabUtility.InstantiatePrefab(basePrefab);
        GameObject variant = PrefabUtility.SaveAsPrefabAssetAndConnect(instance, command.variantSavePath, InteractionMode.AutomatedAction, out bool success);

        if (success)
        {
            Selection.activeGameObject = instance;
            return $"🧬 <b>バリアント作成 (Create Prefab Variant):</b> <color=cyan>{command.variantSavePath}</color>";
        }
        else
        {
            Undo.DestroyObjectImmediate(instance);
            return $"❌ バリアントの作成に失敗しました (Failed to create variant): {command.variantSavePath}";
        }
    }

    private static string ExecuteCreateUIElement(DeveloperCommandData command)
    {
        System.Text.StringBuilder log = new System.Text.StringBuilder();

        Canvas targetCanvas = UnityEngine.Object.FindAnyObjectByType<Canvas>();
        if (targetCanvas == null)
        {
            GameObject canvasObj = new GameObject("Canvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            targetCanvas = canvasObj.GetComponent<Canvas>();
            targetCanvas.renderMode = RenderMode.ScreenSpaceOverlay;
            Undo.RegisterCreatedObjectUndo(canvasObj, "Create Canvas");
            log.AppendLine("🖥️ Canvas 自動生成");
        }

        if (UnityEngine.Object.FindAnyObjectByType<EventSystem>() == null)
        {
            GameObject eventSystemObj = new GameObject("EventSystem", typeof(EventSystem), typeof(StandaloneInputModule));
            Undo.RegisterCreatedObjectUndo(eventSystemObj, "Create EventSystem");
            log.AppendLine("⚡ EventSystem 自動生成");
        }

        Transform parentTransform = GeminiCommandUtils.ResolveParentTransform(command.parentName, targetCanvas.transform);
        Font defaultFont = Resources.GetBuiltinResource<Font>("Arial.ttf") ?? Font.CreateDynamicFontFromOSFont("Arial", 14);

        GameObject uiObj = new GameObject(string.IsNullOrEmpty(command.targetObjectName) ? "UI_Element" : command.targetObjectName);
        Undo.RegisterCreatedObjectUndo(uiObj, "Create UI Element");
        Undo.SetTransformParent(uiObj.transform, parentTransform, "Set Parent");

        RectTransform rectTransform = uiObj.AddComponent<RectTransform>();

        switch (command.uiElementType)
        {
            case "Panel":
                Image panelImage = uiObj.AddComponent<Image>();
                panelImage.color = new Color(0.15f, 0.15f, 0.15f, 0.85f);
                break;
            case "Button":
                uiObj.AddComponent<Image>();
                uiObj.AddComponent<Button>();
                GameObject btnTextObj = new GameObject("Text", typeof(RectTransform), typeof(Text));
                Undo.SetTransformParent(btnTextObj.transform, uiObj.transform, "Set Text Parent");
                Text btnText = btnTextObj.GetComponent<Text>();
                btnText.font = defaultFont;
                btnText.text = string.IsNullOrEmpty(command.uiTextContent) ? "Button" : command.uiTextContent;
                btnText.alignment = TextAnchor.MiddleCenter;
                btnText.color = Color.black;
                RectTransform btnTextRect = btnTextObj.GetComponent<RectTransform>();
                btnTextRect.anchorMin = Vector2.zero;
                btnTextRect.anchorMax = Vector2.one;
                btnTextRect.sizeDelta = Vector2.zero;
                break;
            case "Text":
                Text textComp = uiObj.AddComponent<Text>();
                textComp.font = defaultFont;
                textComp.text = string.IsNullOrEmpty(command.uiTextContent) ? "New Text" : command.uiTextContent;
                textComp.color = Color.white;
                textComp.fontSize = 14;
                textComp.alignment = TextAnchor.MiddleLeft;
                break;
            case "Image": uiObj.AddComponent<Image>(); break;
            case "Slider": uiObj.AddComponent<Slider>(); break;
            case "Toggle": uiObj.AddComponent<Toggle>(); break;
        }

        if (command.rectTransform != null)
        {
            if (command.rectTransform.anchorMin != null) rectTransform.anchorMin = command.rectTransform.anchorMin.ToVector2();
            if (command.rectTransform.anchorMax != null) rectTransform.anchorMax = command.rectTransform.anchorMax.ToVector2();
            if (command.rectTransform.anchoredPosition != null) rectTransform.anchoredPosition = command.rectTransform.anchoredPosition.ToVector2();
            if (command.rectTransform.sizeDelta != null) rectTransform.sizeDelta = command.rectTransform.sizeDelta.ToVector2();
            if (command.rectTransform.pivot != null) rectTransform.pivot = command.rectTransform.pivot.ToVector2();
        }

        Selection.activeGameObject = uiObj;
        log.AppendLine($"🎨 UGUI要素 <b>'{uiObj.name}'</b> ({command.uiElementType}) 構築 (親: '{parentTransform.name}')");
        return log.ToString().TrimEnd();
    }

    private static string ExecuteCreateMaterial(DeveloperCommandData command)
    {
        if (string.IsNullOrEmpty(command.materialName)) command.materialName = "New_Material";
        if (!Directory.Exists(MATERIAL_SAVE_PATH)) Directory.CreateDirectory(MATERIAL_SAVE_PATH);

        string matPath = Path.Combine(MATERIAL_SAVE_PATH, $"{command.materialName}.mat");
        Material newMat = new Material(Shader.Find("Standard"));

        if (ColorUtility.TryParseHtmlString(command.materialColorHex, out Color parsedColor)) newMat.color = parsedColor;

        AssetDatabase.CreateAsset(newMat, matPath);
        AssetDatabase.SaveAssets();

        GameObject targetObj = GeminiCommandUtils.ResolveTargetGameObject(command.targetObjectName, command.childPath);
        if (targetObj != null && targetObj.TryGetComponent<Renderer>(out var renderer))
        {
            Undo.RecordObject(renderer, "Assign Material");
            renderer.sharedMaterial = newMat;
        }

        return $"🎨 <b>マテリアル作成:</b> {matPath}";
    }

    private static string ExecuteInstantiatePrefab(DeveloperCommandData command)
    {
        if (string.IsNullOrEmpty(command.prefabAssetPath)) return "⚠️ プレハブパスが指定されていません。";

        GameObject prefabAsset = AssetDatabase.LoadAssetAtPath<GameObject>(command.prefabAssetPath);
        if (prefabAsset == null) return $"⚠️ プレハブが見つかりません: '{command.prefabAssetPath}'";

        GameObject spawnedObj = (GameObject)PrefabUtility.InstantiatePrefab(prefabAsset);
        Undo.RegisterCreatedObjectUndo(spawnedObj, "Instantiate Prefab");

        if (command.position != null) spawnedObj.transform.position = command.position.ToVector3();

        Transform parentTransform = GeminiCommandUtils.ResolveParentTransform(command.parentName);
        if (parentTransform != null) Undo.SetTransformParent(spawnedObj.transform, parentTransform, "Set Parent");

        Selection.activeGameObject = spawnedObj;
        return $"📦 <b>プレハブ生成:</b> '{prefabAsset.name}'";
    }

    private static string ExecuteSetSerializedProperty(DeveloperCommandData command)
    {
        GameObject targetObj = GeminiCommandUtils.ResolveTargetGameObject(command.targetObjectName, command.childPath);
        if (targetObj == null) return $"⚠️ 対象オブジェクト '{command.targetObjectName}' なし。";

        if (string.IsNullOrEmpty(command.propertyTargetComponent) || string.IsNullOrEmpty(command.propertyName))
            return "⚠️ コンポーネント名、またはプロパティ名が不足しています。";

        Component comp = targetObj.GetComponent(command.propertyTargetComponent);
        if (comp == null) return $"⚠️ コンポーネント '{command.propertyTargetComponent}' なし。";

        SerializedObject serializedComp = new SerializedObject(comp);
        SerializedProperty prop = serializedComp.FindProperty(command.propertyName);
        if (prop == null) return $"⚠️ プロパティ '{command.propertyName}' なし。";

        bool isParsed = false;
        try
        {
            switch (prop.propertyType)
            {
                case SerializedPropertyType.Float:
                    if (float.TryParse(command.propertyValueString, out float fVal)) { prop.floatValue = fVal; isParsed = true; }
                    break;
                case SerializedPropertyType.Integer:
                    if (int.TryParse(command.propertyValueString, out int iVal)) { prop.intValue = iVal; isParsed = true; }
                    break;
                case SerializedPropertyType.Boolean:
                    if (bool.TryParse(command.propertyValueString, out bool bVal)) { prop.boolValue = bVal; isParsed = true; }
                    break;
                case SerializedPropertyType.String:
                    prop.stringValue = command.propertyValueString; isParsed = true;
                    break;
                case SerializedPropertyType.Color:
                    if (ColorUtility.TryParseHtmlString(command.propertyValueString, out Color cVal)) { prop.colorValue = cVal; isParsed = true; }
                    break;
                case SerializedPropertyType.Vector2:
                    string[] v2 = command.propertyValueString.Split(',');
                    if (v2.Length == 2 && float.TryParse(v2[0], out float v2x) && float.TryParse(v2[1], out float v2y))
                    {
                        prop.vector2Value = new Vector2(v2x, v2y); isParsed = true;
                    }
                    break;
                case SerializedPropertyType.Vector3:
                    string[] v3 = command.propertyValueString.Split(',');
                    if (v3.Length >= 3 && float.TryParse(v3[0], out float v3x) && float.TryParse(v3[1], out float v3y) && float.TryParse(v3[2], out float v3z))
                    {
                        prop.vector3Value = new Vector3(v3x, v3y, v3z); isParsed = true;
                    }
                    break;
                case SerializedPropertyType.Enum:
                    if (int.TryParse(command.propertyValueString, out int eIdx))
                    {
                        prop.enumValueIndex = eIdx; isParsed = true;
                    }
                    else
                    {
                        int index = Array.IndexOf(prop.enumNames, command.propertyValueString);
                        if (index >= 0) { prop.enumValueIndex = index; isParsed = true; }
                    }
                    break;
                default:
                    return $"⚠️ プロパティ '{command.propertyName}' の型 ({prop.propertyType}) は現在サポートされていません。";
            }
        }
        catch (Exception ex)
        {
            return $"❌ プロパティ '{command.propertyName}' の解析エラー: {ex.Message}";
        }

        if (isParsed)
        {
            serializedComp.ApplyModifiedProperties();
            if (PrefabUtility.IsPartOfPrefabInstance(targetObj)) PrefabUtility.RecordPrefabInstancePropertyModifications(comp);
            return $"⚙️ <b>{targetObj.name}.{command.propertyTargetComponent}.{command.propertyName}</b> ➔ '{command.propertyValueString}'";
        }

        return $"⚠️ プロパティ '{command.propertyName}' の値 '{command.propertyValueString}' を正しい型にパースできませんでした。";
    }

    private static string ExecuteDeleteObject(DeveloperCommandData command)
    {
        GameObject targetObj = GeminiCommandUtils.ResolveTargetGameObject(command.targetObjectName, command.childPath);
        if (targetObj != null)
        {
            string objName = targetObj.name;
            Undo.DestroyObjectImmediate(targetObj);
            return $"🗑️ <b>オブジェクト削除:</b> '{objName}'";
        }
        return $"⚠️ 削除対象 '{command.targetObjectName}' なし。";
    }

    private static string ExecuteStandardGameObjectOperation(DeveloperCommandData command)
    {
        System.Text.StringBuilder log = new System.Text.StringBuilder();
        GameObject targetObj = GeminiCommandUtils.ResolveTargetGameObject(command.targetObjectName, command.childPath);

        if (targetObj == null)
        {
            PrimitiveType pType = PrimitiveType.Cube;
            bool isPrimitive = Enum.TryParse(command.primitiveType, true, out pType) && command.primitiveType != "Empty";

            targetObj = isPrimitive ? GameObject.CreatePrimitive(pType) : new GameObject();
            targetObj.name = command.targetObjectName.Equals("SELECTED_OBJECT", StringComparison.OrdinalIgnoreCase) ? "NewObject" : command.targetObjectName;
            Undo.RegisterCreatedObjectUndo(targetObj, "Create GameObject");
            log.AppendLine($"✅ オブジェクト <b>'{targetObj.name}'</b> 作成");
        }

        Transform parentTransform = GeminiCommandUtils.ResolveParentTransform(command.parentName);
        if (parentTransform != null) Undo.SetTransformParent(targetObj.transform, parentTransform, "Set Parent");

        Undo.RecordObject(targetObj.transform, "Modify Transform");
        if (command.position != null) targetObj.transform.localPosition = command.position.ToVector3();
        if (command.rotation != null) targetObj.transform.localEulerAngles = command.rotation.ToVector3();
        if (command.scale != null && command.scale.ToVector3() != Vector3.zero) targetObj.transform.localScale = command.scale.ToVector3();

        if (!string.IsNullOrEmpty(command.addComponent))
        {
            Type componentType = System.Type.GetType($"UnityEngine.{command.addComponent}, UnityEngine") ?? System.Type.GetType(command.addComponent);
            if (componentType != null && targetObj.GetComponent(componentType) == null) Undo.AddComponent(targetObj, componentType);
        }

        Selection.activeGameObject = targetObj;
        return log.ToString().TrimEnd();
    }
}
```

### File: `Editor\GeminiAgent\ドメインハンドラー\ScriptCommandHandler.cs`
```csharp
﻿using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using System;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.Callbacks;
using UnityEngine;

/// <summary>
/// C#スクリプトの作成、AST(抽象構文木)を用いた編集処理を担当するハンドラー
/// (负责创建 C# 脚本及利用 AST(抽象语法树) 进行代码修改的处理器)
/// </summary>
public class ScriptCommandHandler : IUnityCommandHandler
{
    private const string SCRIPT_SAVE_PATH = "Assets/Scripts/Generated/";

    public string[] SupportedActionTypes => new[] { "EDIT_SCRIPT", "CREATE_SCRIPT" };

    public string Execute(DeveloperCommandData command)
    {
        if (command.actionType == "EDIT_SCRIPT") return ExecuteEditScript(command);
        if (command.actionType == "CREATE_SCRIPT") return ExecuteCreateScript(command);
        return "⚠️ 未知のスクリプトコマンド";
    }

    private static string ExecuteCreateScript(DeveloperCommandData command)
    {
        if (string.IsNullOrEmpty(command.scriptClassName) || string.IsNullOrEmpty(command.scriptContent))
            return "⚠️ C# クラス名またはコード本文が不足しています。";

        if (!Directory.Exists(SCRIPT_SAVE_PATH)) Directory.CreateDirectory(SCRIPT_SAVE_PATH);

        string fullPath = Path.Combine(SCRIPT_SAVE_PATH, $"{command.scriptClassName}.cs");
        File.WriteAllText(fullPath, command.scriptContent, Encoding.UTF8);

        GameObject targetObj = GeminiCommandUtils.ResolveTargetGameObject(command.targetObjectName, command.childPath);
        if (targetObj != null)
        {
            EditorPrefs.SetString("GeminiAgent_PendingAttach_Obj", targetObj.name);
            EditorPrefs.SetString("GeminiAgent_PendingAttach_Class", command.scriptClassName);
        }

        AssetDatabase.Refresh();
        return $"📝 <b>C# スクリプト生成:</b> <color=cyan>{fullPath}</color>";
    }

    [DidReloadScripts]
    private static void OnScriptsReloaded()
    {
        string targetObjName = EditorPrefs.GetString("GeminiAgent_PendingAttach_Obj", "");
        string className = EditorPrefs.GetString("GeminiAgent_PendingAttach_Class", "");

        if (!string.IsNullOrEmpty(targetObjName) && !string.IsNullOrEmpty(className))
        {
            EditorPrefs.DeleteKey("GeminiAgent_PendingAttach_Obj");
            EditorPrefs.DeleteKey("GeminiAgent_PendingAttach_Class");

            GameObject targetObj = GameObject.Find(targetObjName);
            if (targetObj != null)
            {
                Type scriptType = Type.GetType($"{className}, Assembly-CSharp");
                if (scriptType == null)
                {
                    foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                    {
                        scriptType = asm.GetType(className);
                        if (scriptType != null) break;
                    }
                }

                if (scriptType != null && targetObj.GetComponent(scriptType) == null)
                {
                    Undo.AddComponent(targetObj, scriptType);
                    Debug.Log($"[Gemini Agent] ✅ 自動アタッチ成功 (Auto-attach succeeded): '{targetObj.name}' ➔ '{className}'");
                }
            }
        }
    }

    private static string ExecuteEditScript(DeveloperCommandData command)
    {
        string filePath = !string.IsNullOrEmpty(command.targetFilePath) ? command.targetFilePath : command.sourceFilePath;
        if (string.IsNullOrEmpty(filePath) || !File.Exists(filePath))
        {
            return $"⚠️ 改修対象のスクリプトファイルが存在しません: '{filePath}'";
        }

        string originalCode = File.ReadAllText(filePath, Encoding.UTF8);
        string modifiedCode = originalCode;
        string mode = string.IsNullOrEmpty(command.editMode) ? "FULL_REWRITE" : command.editMode.ToUpper();

        try
        {
            if (mode == "FULL_REWRITE")
            {
                if (string.IsNullOrEmpty(command.scriptContent)) return "⚠️ 全体リファクタリング用のコード本文 (scriptContent) が指定されていません。";
                modifiedCode = command.scriptContent;
            }
            else
            {
                Microsoft.CodeAnalysis.SyntaxTree tree = Microsoft.CodeAnalysis.CSharp.CSharpSyntaxTree.ParseText(originalCode);
                Microsoft.CodeAnalysis.CSharp.Syntax.CompilationUnitSyntax root = tree.GetCompilationUnitRoot();

                if (mode == "APPEND_METHOD")
                {
                    var classDecl = root.DescendantNodes().OfType<Microsoft.CodeAnalysis.CSharp.Syntax.ClassDeclarationSyntax>().FirstOrDefault();
                    if (classDecl != null)
                    {
                        var newMethod = Microsoft.CodeAnalysis.CSharp.SyntaxFactory.ParseMemberDeclaration(
                            $"\n    // --- Added by Gemini Agent [{DateTime.Now:HH:mm:ss}] ---\n{command.replacementCode}\n"
                        );

                        if (newMethod != null)
                        {
                            var newClassDecl = classDecl.AddMembers(newMethod);
                            root = root.ReplaceNode(classDecl, newClassDecl);
                            modifiedCode = root.NormalizeWhitespace().ToFullString();
                        }
                        else return "❌ 追加コードのASTパースに失敗しました。(追加代码的AST解析失败)";
                    }
                    else return $"❌ ファイル '{filePath}' 内にクラス宣言が見つかりませんでした。";
                }
                else if (mode == "REPLACE_SNIPPET")
                {
                    if (string.IsNullOrEmpty(command.searchPattern) || string.IsNullOrEmpty(command.replacementCode))
                        return "⚠️ 置換対象の検索パターンまたは置換コードが指定されていません。";

                    GeminiRoslynRewriter rewriter = new GeminiRoslynRewriter(command.searchPattern, command.replacementCode);
                    Microsoft.CodeAnalysis.SyntaxNode newRoot = rewriter.Visit(root);

                    // 🚨 修正: 失敗時に明確なエラーメッセージを返す (返回明确的解析错误以便 AI 进行修复)
                    if (rewriter.IsParseFailed)
                    {
                        return $"❌ 置換コードの構文が不正です。(Replacement code syntax is invalid.)\n提供されたコードが完全なメソッド構造を持っているか確認してください。";
                    }

                    if (rewriter.IsReplaced) modifiedCode = newRoot.NormalizeWhitespace().ToFullString();
                    else return $"⚠️ 検索パターン '{command.searchPattern}' に一致する構文ノードが見つかりませんでした。";
                }
            }
        }
        catch (Exception ex)
        {
            return $"❌ AST構文解析エラー (AST语法解析错误): {ex.Message}";
        }

        // Diff Viewer ウィンドウの呼び出し (呼叫差异查看器窗口)
        EditorApplication.delayCall += () =>
        {
            GeminiDiffViewerWindow.ShowWindow(filePath, originalCode, modifiedCode);
        };

        return $"⏳ <b>C#コード増量改修 [{mode}]:</b>\n<color=yellow>開発者の承認待ちです (Waiting for developer approval)...</color>\n対象: {filePath}";
    }

    public class GeminiRoslynRewriter : Microsoft.CodeAnalysis.CSharp.CSharpSyntaxRewriter
    {
        private readonly string _searchPattern;
        private readonly string _replacementCode;
        public bool IsReplaced { get; private set; }

        // 🚨 修正: パース失敗フラグを追加 (新增：解析失败标志)
        public bool IsParseFailed { get; private set; }

        public GeminiRoslynRewriter(string searchPattern, string replacementCode)
        {
            _searchPattern = searchPattern;
            _replacementCode = replacementCode;
            IsReplaced = false;
            IsParseFailed = false;
        }

        public override Microsoft.CodeAnalysis.SyntaxNode VisitMethodDeclaration(Microsoft.CodeAnalysis.CSharp.Syntax.MethodDeclarationSyntax node)
        {
            if (IsReplaced || IsParseFailed) return base.VisitMethodDeclaration(node);

            string nodeText = node.ToFullString();

            if (System.Text.RegularExpressions.Regex.IsMatch(nodeText, _searchPattern) || nodeText.Contains(_searchPattern))
            {
                var newMember = Microsoft.CodeAnalysis.CSharp.SyntaxFactory.ParseMemberDeclaration(_replacementCode);

                if (newMember != null)
                {
                    IsReplaced = true;
                    return newMember.WithLeadingTrivia(node.GetLeadingTrivia());
                }
                else
                {
                    // パースに失敗した場合はフラグを立ててログを出力
                    IsParseFailed = true;
                    Debug.LogWarning("[Gemini Agent] ASTメンバー直接解析に失敗しました。構文の破壊を防ぐため、置換操作を中断します。(AST parsing failed. Aborting to prevent syntax corruption.)");
                }
            }

            return base.VisitMethodDeclaration(node);
        }
    }
}
```

### File: `Editor\GeminiAgent\ドメインハンドラー\TransformCommandHandler.cs`
```csharp
﻿using UnityEngine;
using UnityEditor;

/// <summary>
/// 空間行列・トランスフォーム関連のコマンドを処理するハンドラー
/// (处理空间矩阵与变换相关命令的处理器)
/// </summary>
public class TransformCommandHandler : IUnityCommandHandler
{
    public string[] SupportedActionTypes => new[] { "MATH_TRANSFORM", "ALIGN_OBJECT" };

    public string Execute(DeveloperCommandData command)
    {
        if (command.actionType == "MATH_TRANSFORM") return ExecuteMathTransform(command);
        if (command.actionType == "ALIGN_OBJECT") return ExecuteAlignObject(command);
        return "⚠️ 未知のトランスフォームコマンド (Unknown transform command)";
    }

    private static string ExecuteMathTransform(DeveloperCommandData command)
    {
        GameObject targetObj = GeminiCommandUtils.ResolveTargetGameObject(command.targetObjectName, command.childPath);
        if (targetObj == null) return $"⚠️ 対象なし (Target not found): {command.targetObjectName}";

        Undo.RecordObject(targetObj.transform, "Math Transform");
        Transform t = targetObj.transform;
        bool isWorld = command.transformSpace == "World";

        if (command.isRelativeTransform)
        {
            // 相対変換 (Relative Matrix Transform)
            Vector3 deltaPos = command.position != null ? command.position.ToVector3() : Vector3.zero;
            Quaternion deltaRot = command.quaternionRotation != null ? command.quaternionRotation.ToQuaternion() :
                                 (command.rotation != null ? Quaternion.Euler(command.rotation.ToVector3()) : Quaternion.identity);

            if (isWorld)
            {
                t.position += deltaPos;
                t.rotation = deltaRot * t.rotation; // World space rotation accumulation
            }
            else
            {
                // ローカル座標系での行列計算 (Local Matrix multiplication)
                Matrix4x4 localDeltaMat = Matrix4x4.TRS(deltaPos, deltaRot, Vector3.one);
                Matrix4x4 currentLocalMat = Matrix4x4.TRS(t.localPosition, t.localRotation, t.localScale);
                Matrix4x4 newLocalMat = currentLocalMat * localDeltaMat;

                t.localPosition = newLocalMat.GetColumn(3);
                t.localRotation = newLocalMat.rotation;
            }
        }
        else
        {
            // 絶対設定 (Absolute Assignment)
            if (command.position != null)
            {
                if (isWorld) t.position = command.position.ToVector3();
                else t.localPosition = command.position.ToVector3();
            }

            if (command.quaternionRotation != null)
            {
                if (isWorld) t.rotation = command.quaternionRotation.ToQuaternion();
                else t.localRotation = command.quaternionRotation.ToQuaternion();
            }
            else if (command.rotation != null)
            {
                if (isWorld) t.eulerAngles = command.rotation.ToVector3();
                else t.localEulerAngles = command.rotation.ToVector3();
            }

            if (command.scale != null) t.localScale = command.scale.ToVector3();
        }

        return $"📐 <b>空間変換 (Math Transform):</b> {targetObj.name} [Space: {command.transformSpace}, Relative: {command.isRelativeTransform}]";
    }

    private static string ExecuteAlignObject(DeveloperCommandData command)
    {
        GameObject sourceObj = GeminiCommandUtils.ResolveTargetGameObject(command.targetObjectName, command.childPath);
        GameObject targetObj = GeminiCommandUtils.ResolveTargetGameObject(command.alignTargetName);

        if (sourceObj == null || targetObj == null)
            return $"⚠️ 整列対象またはターゲットが見つかりません (Source or Target not found).";

        Renderer sourceRenderer = sourceObj.GetComponentInChildren<Renderer>();
        Renderer targetRenderer = targetObj.GetComponentInChildren<Renderer>();

        if (sourceRenderer == null || targetRenderer == null)
            return $"⚠️ バウンディングボックス取得失敗: 双方にRendererコンポーネントが必要です。";

        Undo.RecordObject(sourceObj.transform, "Align Object");

        Bounds targetBounds = targetRenderer.bounds;
        Bounds sourceBounds = sourceRenderer.bounds;
        Vector3 offset = Vector3.zero;

        // 指定された基準点 (Min, Center, Max) に基づいてオフセットを計算
        if (command.alignPoint == "Center") offset = targetBounds.center - sourceBounds.center;
        else if (command.alignPoint == "Min") offset = targetBounds.min - sourceBounds.min;
        else if (command.alignPoint == "Max") offset = targetBounds.max - sourceBounds.max;

        sourceObj.transform.position += offset;
        return $"🧲 <b>バウンディングボックス整列 (Align Bounding Box):</b> {sourceObj.name} ➔ {targetObj.name} [Point: {command.alignPoint}]";
    }
}
```

### File: `Editor\GeminiAgent\ビュー層\GeminiDiffViewerWindow.cs`
```csharp
﻿using System;
using System.IO;
using UnityEditor;
using UnityEngine;

/// <summary>
/// コードの変更内容をプレビューし、開発者が承認または破棄を選択できる差分確認ウィンドウ
/// (用于预览代码修改内容，允许开发者选择批准或放弃的差异确认窗口)
/// </summary>
public class GeminiDiffViewerWindow : EditorWindow
{
    private string targetFilePath;
    private string originalCode;
    private string modifiedCode;
    private Vector2 scrollPosOriginal;
    private Vector2 scrollPosModified;

    /// <summary>
    /// 差分確認ウィンドウを表示するメソッド
    /// (显示差异确认窗口的方法)
    /// </summary>
    public static void ShowWindow(string filePath, string oldCode, string newCode)
    {
        // 确保窗口具有焦点且不可忽视 (Ensure window gets focus)
        GeminiDiffViewerWindow window = GetWindow<GeminiDiffViewerWindow>("Code Diff Viewer", true);
        window.targetFilePath = filePath;
        window.originalCode = oldCode;
        window.modifiedCode = newCode;
        window.minSize = new Vector2(900, 600);
        window.ShowUtility();
    }

    private void OnGUI()
    {
        GUILayout.Label($"変更対象ファイル (Target File): {targetFilePath}", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        EditorGUILayout.BeginHorizontal();

        // 左側：元のコード (Left: Original Code)
        EditorGUILayout.BeginVertical(GUILayout.Width(position.width / 2f - 10f));
        GUILayout.Label("変更前 (Original)", EditorStyles.boldLabel);
        scrollPosOriginal = EditorGUILayout.BeginScrollView(scrollPosOriginal, "box");
        EditorGUILayout.TextArea(originalCode, GUILayout.ExpandHeight(true));
        EditorGUILayout.EndScrollView();
        EditorGUILayout.EndVertical();

        // 右側：変更後のコード (Right: Modified Code)
        EditorGUILayout.BeginVertical(GUILayout.Width(position.width / 2f - 10f));
        GUILayout.Label("変更後 (Modified)", EditorStyles.boldLabel);
        scrollPosModified = EditorGUILayout.BeginScrollView(scrollPosModified, "box");
        EditorGUILayout.TextArea(modifiedCode, GUILayout.ExpandHeight(true));
        EditorGUILayout.EndScrollView();
        EditorGUILayout.EndVertical();

        EditorGUILayout.EndHorizontal();

        EditorGUILayout.Space();

        // 承認と破棄ボタン (Approve and Reject Buttons)
        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("破棄 (Reject)", GUILayout.Height(40)))
        {
            Debug.Log($"[Gemini Agent] 変更が破棄されました (Modification rejected): {targetFilePath}");
            Close();
        }

        GUI.backgroundColor = Color.green;
        if (GUILayout.Button("承認して適用 (Approve & Apply)", GUILayout.Height(40)))
        {
            ApplyChanges();
            Close();
        }
        GUI.backgroundColor = Color.white;
        EditorGUILayout.EndHorizontal();
    }

    /// <summary>
    /// 承認された変更をファイルに書き込み、バックアップを作成してAssetDatabaseを更新する
    /// (将批准的更改写入文件，创建备份并更新AssetDatabase)
    /// </summary>
    private void ApplyChanges()
    {
        try
        {
            // バックアップの作成 (Create Backup)
            string backupPath = targetFilePath + ".bak";
            File.WriteAllText(backupPath, originalCode, System.Text.Encoding.UTF8);

            // 新しいコードの書き込み (Write new code)
            File.WriteAllText(targetFilePath, modifiedCode, System.Text.Encoding.UTF8);
            AssetDatabase.Refresh();
            Debug.Log($"[Gemini Agent] ✅ コードが適用されました (Code applied): {targetFilePath} \n(Backup saved at: {backupPath})");
        }
        catch (Exception ex)
        {
            Debug.LogError($"[Gemini Agent] ファイルの保存に失敗しました (Failed to save file): {ex.Message}");
        }
    }
}
```

### File: `Editor\GeminiAgent\ビュー層\GeminiUnityAgentWindow.cs`
```csharp
﻿using System;
using System.Collections.Generic;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// ユーザーインターフェースの描画とユーザー操作の受付のみを担当する軽量化されたウィンドウ
/// </summary>
public class GeminiUnityAgentWindow : EditorWindow
{
    private GeminiModelRouter _modelRouter = new GeminiModelRouter();
    private GeminiCacheManager _cacheManager = new GeminiCacheManager();

    private string apiKey = "";
    private string proxyUrl = "";
    private string userPrompt = "";
    private string statusMessage = "準備完了";
    private bool isProcessing = false;

    private bool enableAutoRouting = true;
    private int selectedModelIndex = 0;

    private bool autoIncludeSelectionContext = true;
    private bool autoIncludeDirectoryContext = true;
    private bool autoIncludeSceneContext = true;
    private bool autoIncludeScriptContext = true;
    private string scriptScanFolderPath = "Assets/Scripts";

    private List<ChatLogItem> chatHistory = new List<ChatLogItem>();
    private Vector2 scrollPosition = Vector2.zero;
    private bool scrollToBottom = false;
    private const string CHAT_HISTORY_PREF_KEY = "GeminiAgent_ChatHistory";

    [MenuItem("Tools/Gemini Unity Agent (Refactored)")]
    public static void ShowWindow()
    {
        GeminiUnityAgentWindow window = GetWindow<GeminiUnityAgentWindow>("Gemini Agent");
        window.minSize = new Vector2(500, 750);
    }

    private void OnEnable()
    {
        apiKey = EditorPrefs.GetString("GeminiAgent_APIKey", "");
        proxyUrl = EditorPrefs.GetString("GeminiAgent_ProxyURL", "");
        enableAutoRouting = EditorPrefs.GetBool("GeminiAgent_AutoRouting", true);
        selectedModelIndex = EditorPrefs.GetInt("GeminiAgent_ModelIndex", 0);
        scriptScanFolderPath = EditorPrefs.GetString("GeminiAgent_ScanPath", "Assets/Scripts");

        LoadChatHistory();

        if (!string.IsNullOrEmpty(apiKey))
        {
            _ = UpdateModelListAsync();
        }
    }

    private async System.Threading.Tasks.Task UpdateModelListAsync()
    {
        isProcessing = true;
        statusMessage = "モデル一覧を取得中...";
        Repaint();

        bool success = await _modelRouter.FetchModelsAsync(apiKey, proxyUrl);
        statusMessage = success ? "モデル一覧の更新完了" : "モデル取得失敗";

        isProcessing = false;
        Repaint();
    }

    private void OnGUI()
    {
        GUILayout.Label("🤖 Gemini Developer Agent (Modular Architecture)", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        EditorGUI.BeginChangeCheck();
        apiKey = EditorGUILayout.PasswordField("Gemini API Key:", apiKey);
        if (EditorGUI.EndChangeCheck()) EditorPrefs.SetString("GeminiAgent_APIKey", apiKey);

        EditorGUI.BeginChangeCheck();
        proxyUrl = EditorGUILayout.TextField("Proxy URL (任意):", proxyUrl);
        if (EditorGUI.EndChangeCheck()) EditorPrefs.SetString("GeminiAgent_ProxyURL", proxyUrl);

        EditorGUILayout.Space();

        EditorGUILayout.LabelField("モデル設定 (Model Configuration):", EditorStyles.boldLabel);
        EditorGUI.BeginChangeCheck();
        enableAutoRouting = EditorGUILayout.Toggle("自動モデルルーティング", enableAutoRouting);
        if (EditorGUI.EndChangeCheck()) EditorPrefs.SetBool("GeminiAgent_AutoRouting", enableAutoRouting);

        EditorGUILayout.BeginHorizontal();
        EditorGUI.BeginDisabledGroup(enableAutoRouting || isProcessing || _modelRouter.ModelOptions.Count == 0);
        EditorGUI.BeginChangeCheck();
        if (selectedModelIndex >= _modelRouter.ModelOptions.Count) selectedModelIndex = 0;
        selectedModelIndex = EditorGUILayout.Popup("手動選択モデル:", selectedModelIndex, _modelRouter.ModelOptions.ToArray());
        if (EditorGUI.EndChangeCheck()) EditorPrefs.SetInt("GeminiAgent_ModelIndex", selectedModelIndex);
        EditorGUI.EndDisabledGroup();

        if (GUILayout.Button("🔄 モデル更新", GUILayout.Width(90)))
        {
            _ = UpdateModelListAsync();
        }
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.Space();

        EditorGUILayout.LabelField("プロジェクト文脈・解析設定:", EditorStyles.boldLabel);
        autoIncludeSelectionContext = EditorGUILayout.Toggle("現在選択中のオブジェクト情報を送信", autoIncludeSelectionContext);
        autoIncludeDirectoryContext = EditorGUILayout.Toggle("Assets フォルダ構造を送信", autoIncludeDirectoryContext);
        autoIncludeSceneContext = EditorGUILayout.Toggle("現在のUI/シーン構造を送信", autoIncludeSceneContext);
        autoIncludeScriptContext = EditorGUILayout.Toggle("既存C#スクリプト型情報を送信", autoIncludeScriptContext);

        if (autoIncludeScriptContext)
        {
            EditorGUI.BeginChangeCheck();
            scriptScanFolderPath = EditorGUILayout.TextField("解析対象フォルダ:", scriptScanFolderPath);
            if (EditorGUI.EndChangeCheck()) EditorPrefs.SetString("GeminiAgent_ScanPath", scriptScanFolderPath);
        }

        EditorGUILayout.Space();

        DrawCacheMonitorUI();
        DrawChatHistoryArea();

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("新しい指示 (Prompt):");
        userPrompt = EditorGUILayout.TextArea(userPrompt, GUILayout.Height(50));

        EditorGUILayout.BeginHorizontal();
        EditorGUI.BeginDisabledGroup(isProcessing || string.IsNullOrEmpty(apiKey) || string.IsNullOrEmpty(userPrompt.Trim()));

        if (GUILayout.Button("開発指示を送信 (Send Dev Command)", GUILayout.Height(30)))
        {
            string targetModel = enableAutoRouting
                ? _modelRouter.FindBestMatchingModel("pro", "flash", "gemini-3.5-flash")
                : (_modelRouter.ModelApiNames.Count > selectedModelIndex ? _modelRouter.ModelApiNames[selectedModelIndex] : "gemini-3.5-flash");

            SendAgentRequestAsync(userPrompt.Trim(), targetModel);
        }

        EditorGUI.EndDisabledGroup();

        if (GUILayout.Button("履歴クリア", GUILayout.Width(80), GUILayout.Height(30)))
        {
            chatHistory.Clear();
            SaveChatHistory();
        }
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.Space();
        string selectedObjName = Selection.activeGameObject != null ? Selection.activeGameObject.name : "なし";
        EditorGUILayout.HelpBox($"ステータス: {statusMessage} | 選択中: {selectedObjName}", MessageType.Info);
    }

    private void DrawCacheMonitorUI()
    {
        EditorGUILayout.BeginVertical("box");
        EditorGUILayout.LabelField("コンテキストキャッシュ監視 (Context Caching Monitor)", EditorStyles.boldLabel);

        bool isValid = _cacheManager.IsCacheValid;
        string statusIcon = isValid ? "🟢 有効 (Active / 命中)" : "🟡 フォールバック (Fallback / 降級)";
        EditorGUILayout.LabelField("ステータス (Status):", statusIcon);

        if (isValid)
        {
            EditorGUILayout.LabelField("キャッシュ識別子:", _cacheManager.CurrentCacheName);
            EditorGUILayout.LabelField("有効期限 (Expires):", _cacheManager.GetExpireTime().ToLocalTime().ToString("HH:mm:ss"));
        }

        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("🔄 キャッシュを手動更新 (Force Update Cache)"))
        {
            _cacheManager.ClearCache();
            statusMessage = "🔄 キャッシュを破棄しました。次回の送信時に再構築されます。";
        }
        if (GUILayout.Button("🗑️ キャッシュを破棄して降級 (Clear & Fallback)"))
        {
            _cacheManager.ClearCache();
        }
        EditorGUILayout.EndHorizontal();
        EditorGUILayout.EndVertical();
        EditorGUILayout.Space();
    }

    private void DrawChatHistoryArea()
    {
        GUIStyle historyBoxStyle = new GUIStyle(GUI.skin.box) { padding = new RectOffset(10, 10, 10, 10) };
        scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition, historyBoxStyle, GUILayout.Height(200));

        foreach (var item in chatHistory)
        {
            bool isUser = item.role == "user";
            GUIStyle bubbleStyle = new GUIStyle(GUI.skin.button) { wordWrap = true, alignment = TextAnchor.MiddleLeft, richText = true };

            EditorGUILayout.BeginVertical();
            EditorGUILayout.LabelField(isUser ? $"👤 User [{item.timestamp}]" : $"🤖 Agent [{item.timestamp}]", EditorStyles.miniLabel);
            GUILayout.Box(item.displayText, bubbleStyle);

            if (item.isPendingExecution)
            {
                EditorGUILayout.BeginHorizontal();
                GUI.backgroundColor = new Color(0.9f, 0.4f, 0.4f);
                if (GUILayout.Button("破棄 (Reject)"))
                {
                    item.isPendingExecution = false;
                    item.isRejected = true;
                    item.displayText = "❌ コマンドは破棄されました";
                    SaveChatHistory();
                }

                GUI.backgroundColor = new Color(0.4f, 0.9f, 0.4f);
                if (GUILayout.Button("承認して実行 (Approve & Execute)"))
                {
                    OnExecuteApprovedCommand(item);
                    SaveChatHistory();
                }
                GUI.backgroundColor = Color.white;
                EditorGUILayout.EndHorizontal();
            }
            EditorGUILayout.EndVertical();
            EditorGUILayout.Space(5);
        }

        if (scrollToBottom) { scrollPosition.y = float.MaxValue; scrollToBottom = false; }
        EditorGUILayout.EndScrollView();
    }

    private async void SendAgentRequestAsync(string prompt, string targetModelName)
    {
        isProcessing = true;
        statusMessage = $"{targetModelName} が処理中 (Processing)...";

        string timeNow = DateTime.Now.ToString("HH:mm:ss");
        chatHistory.Add(new ChatLogItem { role = "user", apiText = prompt, displayText = prompt, timestamp = timeNow });
        userPrompt = "";
        scrollToBottom = true;
        Repaint();

        StringBuilder contextBuilder = new StringBuilder();
        if (autoIncludeSelectionContext) contextBuilder.AppendLine(GeminiContextScanner.CaptureSelectionContext());
        if (autoIncludeDirectoryContext) contextBuilder.AppendLine(GeminiContextScanner.CaptureDirectoryStructure("Assets", 0, 3));
        if (autoIncludeSceneContext) contextBuilder.AppendLine(GeminiContextScanner.CaptureSceneContextJson());
        if (autoIncludeScriptContext) contextBuilder.AppendLine(GeminiContextScanner.CaptureProjectScriptsSummary(scriptScanFolderPath, prompt, Selection.activeGameObject));

        string fullContext = contextBuilder.ToString();

        string jsonPayload = $@"{{
            ""contents"": [
                {{""role"": ""user"", ""parts"": [{{""text"": ""{prompt}\n\n{fullContext}""}}]}}
            ]
        }}";

        string url = $"https://generativelanguage.googleapis.com/v1beta/models/{targetModelName}:generateContent?key={apiKey}";

        GeminiNetworkResult result = await GeminiNetworkService.SendPostRequestAsync(url, jsonPayload, proxyUrl);

        if (result.IsSuccess)
        {
            string trimmedCommand = result.ResponseText != null ? result.ResponseText.Trim() : "";
            bool isJsonCommand = trimmedCommand.StartsWith("{") || trimmedCommand.StartsWith("[");
            bool hasCommand = isJsonCommand && trimmedCommand != "{}" && trimmedCommand != "[]";

            string initialDisplay = hasCommand ? "⚠️ 実行待機中のコマンドがあります (Commands pending execution)" : trimmedCommand;

            chatHistory.Add(new ChatLogItem
            {
                role = "model",
                apiText = trimmedCommand,
                displayText = initialDisplay,
                timestamp = DateTime.Now.ToString("HH:mm:ss"),
                usedModel = targetModelName,
                isPendingExecution = hasCommand,
                pendingCommandJson = hasCommand ? trimmedCommand : ""
            });
            statusMessage = hasCommand ? "コマンド生成完了 (承認待ち)" : "テキスト応答を受信";
        }
        else
        {
            statusMessage = $"通信エラー (HTTP {result.StatusCode})";
            chatHistory.Add(new ChatLogItem { role = "model", displayText = $"❌ <b>エラー:</b>\n{result.ErrorMessage}", timestamp = DateTime.Now.ToString("HH:mm:ss") });
        }

        SaveChatHistory();
        isProcessing = false;
        scrollToBottom = true;
        Repaint();
    }

    private void OnExecuteApprovedCommand(ChatLogItem item)
    {
        item.isPendingExecution = false;
        string executionResult = GeminiCommandExecutorCore.ExecuteBatchCommands(item.pendingCommandJson);
        item.displayText = executionResult;
    }

    private void SaveChatHistory()
    {
        ChatHistoryWrapper wrapper = new ChatHistoryWrapper { history = this.chatHistory };
        EditorPrefs.SetString(CHAT_HISTORY_PREF_KEY, JsonUtility.ToJson(wrapper));
    }

    private void LoadChatHistory()
    {
        string json = EditorPrefs.GetString(CHAT_HISTORY_PREF_KEY, "");
        if (!string.IsNullOrEmpty(json))
        {
            try
            {
                ChatHistoryWrapper wrapper = JsonUtility.FromJson<ChatHistoryWrapper>(json);
                if (wrapper != null && wrapper.history != null)
                {
                    chatHistory = wrapper.history;
                    scrollToBottom = true;
                }
            }
            catch { chatHistory = new List<ChatLogItem>(); }
        }
    }
}
```

### File: `Editor\GeminiAgent\基盤・通信層\GeminiAgentDTOs.cs`
```csharp
﻿using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Agent通信とコマンド実行に使用される構造化データ定義群(DTO)
/// (Agent 通信与命令执行所使用的结构化数据传输对象集合)
/// </summary>

[Serializable]
public class ChatLogItem
{
    public string role;
    public string apiText;
    public string displayText;
    public string timestamp;
    public string usedModel;

    // Human-in-the-Loop 用の保留状態 (用于 Human-in-the-Loop 的挂起状态)
    public bool isPendingExecution;
    public string pendingCommandJson;
    public bool isRejected;
}

[Serializable]
public class DeveloperCommandBatch
{
    public List<DeveloperCommandData> actions = new List<DeveloperCommandData>();
}

[Serializable]
public class DeveloperCommandData
{
    public string actionType;
    public string targetObjectName;
    public string parentName;
    public string primitiveType = "Cube";

    public Vector3Data position;
    public Vector3Data rotation;
    public Vector3Data scale;
    public string addComponent;

    public Vector4Data quaternionRotation;
    public string transformSpace;
    public bool isRelativeTransform;
    public string alignPoint;
    public string alignTargetName;

    public string directoryPath;
    public string searchFilter;
    public string sourceFilePath;
    public string targetFilePath;

    public string editMode;
    public string searchPattern;
    public string replacementCode;

    public string uiElementType;
    public string uiTextContent;
    public RectTransformData rectTransform;

    public string scriptClassName;
    public string scriptContent;
    public string materialName;
    public string materialColorHex;
    public string propertyTargetComponent;
    public string propertyName;
    public string propertyValueString;

    public string prefabAssetPath;
    public string childPath;
    public string unpackMode;
    public string variantSavePath;
}

[Serializable]
public class RectTransformData
{
    public Vector2Data anchorMin;
    public Vector2Data anchorMax;
    public Vector2Data anchoredPosition;
    public Vector2Data sizeDelta;
    public Vector2Data pivot;
}

[Serializable]
public class Vector2Data { public float x, y; public Vector2 ToVector2() => new Vector2(x, y); }

[Serializable]
public class Vector3Data { public float x, y, z; public Vector3 ToVector3() => new Vector3(x, y, z); }

[Serializable]
public class Vector4Data { public float x, y, z, w; public Quaternion ToQuaternion() => new Quaternion(x, y, z, w); }

[Serializable]
public class GeminiCacheResponse { public string name; public string expireTime; }

[Serializable]
public class GeminiRequestWithCache
{
    public string cachedContent;
    public GeminiRequestMessage[] contents;
}

#region Gemini API JSON Response Wrappers
[Serializable]
public class GeminiResponseWrapper { public Candidate[] candidates; }
[Serializable]
public class Candidate { public Content content; }
[Serializable]
public class Content { public Part[] parts; }
[Serializable]
public class Part
{
    public string text;
    public FunctionCallData functionCall;
}
[Serializable]
public class FunctionCallData
{
    public string name;
    public DeveloperCommandBatch args;
}

[Serializable]
public class GeminiRequestMessage
{
    public string role;
    public GeminiRequestPart[] parts;
}

[Serializable]
public class GeminiRequestPart { public string text; }

[Serializable]
public class ChatHistoryWrapper { public List<ChatLogItem> history = new List<ChatLogItem>(); }

// モデル一覧取得用のDTO (用于获取模型列表的数据结构)
[Serializable]
public class ModelListResponse { public List<ModelInfo> models; }

[Serializable]
public class ModelInfo
{
    public string name;
    public string displayName;
    public string description;
    public List<string> supportedGenerationMethods;
}
#endregion
```

### File: `Editor\GeminiAgent\基盤・通信層\GeminiCacheManager.cs`
```csharp
﻿using UnityEngine;
using UnityEditor;
using System.Threading.Tasks;
using UnityEngine.Networking;
using System.Text;
using System;

/// <summary>
/// コンテキストキャッシュ (Context Caching) のライフサイクルを管理するクラス。
/// トークン計算、APIへの登録、EditorPrefsを介した永続化(Persistence)を担当します。
/// </summary>
public class GeminiCacheManager
{
    private const string PREF_CACHE_NAME = "GeminiAgent_CacheName";
    private const string PREF_CACHE_EXPIRE = "GeminiAgent_CacheExpireTime";

    // 最低限必要なトークン数の閾値（APIの制限: 32768）(API硬性规定的最低 Token 门槛)
    private const int MIN_TOKEN_THRESHOLD = 32768;
    // デフォルトのTTL設定 (300秒 = 5分) (默认生存时间)
    private const string DEFAULT_TTL = "300s";

    public string CurrentCacheName => EditorPrefs.GetString(PREF_CACHE_NAME, string.Empty);
    public bool IsCacheValid => !string.IsNullOrEmpty(CurrentCacheName) && DateTime.UtcNow < GetExpireTime();

    public DateTime GetExpireTime()
    {
        string expireStr = EditorPrefs.GetString(PREF_CACHE_EXPIRE, string.Empty);
        if (DateTime.TryParse(expireStr, out DateTime expireTime)) return expireTime;
        return DateTime.MinValue;
    }

    /// <summary>
    /// コンテキストキャッシュの構築を試みます (尝试构建上下文缓存)
    /// 既存のDTO依存を避け、直接JSON文字列を構築して通信します。
    /// </summary>
    public async Task<bool> TryBuildCacheAsync(string apiKey, string modelName, string sysInstructionJson, string staticContextText, string toolsJsonArray)
    {
        // 簡易的なトークン推測 (Heuristic Token Estimation: 4文字 ≒ 1トークン)
        int estimatedTokens = staticContextText.Length / 4;
        if (estimatedTokens < MIN_TOKEN_THRESHOLD)
        {
            Debug.Log($"[Gemini Cache] トークン数が少なすぎます({estimatedTokens} < 32k)。APIの制限によりキャッシュ構築をスキップします。(Token amount too low, skipping cache build)");
            ClearCache();
            return false;
        }

        string cleanModelName = modelName.StartsWith("models/") ? modelName : $"models/{modelName}";
        string escapedContext = EscapeJsonString(staticContextText);

        // キャッシュ構築用のペイロード (Cache Payload) を手動で組み立てる
        string jsonPayload = $@"
        {{
            ""model"": ""{cleanModelName}"",
            ""systemInstruction"": {sysInstructionJson},
            ""tools"": {toolsJsonArray},
            ""contents"": [
                {{
                    ""role"": ""user"",
                    ""parts"": [{{ ""text"": ""{escapedContext}"" }}]
                }}
            ],
            ""ttl"": ""{DEFAULT_TTL}""
        }}";

        string url = $"https://generativelanguage.googleapis.com/v1beta/cachedContents?key={apiKey}";

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            var operation = request.SendWebRequest();
            while (!operation.isDone) await Task.Yield();

            if (request.result == UnityWebRequest.Result.Success)
            {
                var response = JsonUtility.FromJson<GeminiCacheResponse>(request.downloadHandler.text);
                EditorPrefs.SetString(PREF_CACHE_NAME, response.name);
                EditorPrefs.SetString(PREF_CACHE_EXPIRE, response.expireTime);
                Debug.Log($"[Gemini Cache] ✅ キャッシュ生成成功 (Cache created successfully): {response.name}");
                return true;
            }
            else
            {
                Debug.LogWarning($"[Gemini Cache] ❌ キャッシュの作成に失敗しました (Cache creation failed): {request.error}\nResponse: {request.downloadHandler.text}");
                ClearCache();
                return false;
            }
        }
    }

    public void ClearCache()
    {
        EditorPrefs.DeleteKey(PREF_CACHE_NAME);
        EditorPrefs.DeleteKey(PREF_CACHE_EXPIRE);
    }

    private string EscapeJsonString(string str)
    {
        if (string.IsNullOrEmpty(str)) return "";
        return str.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "");
    }
}
```

### File: `Editor\GeminiAgent\基盤・通信層\GeminiModelRouter.cs`
```csharp
﻿using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;

/// <summary>
/// 利用可能なモデルの取得、フィルタリング、およびタスク複雑度に基づく動的ルーティングを担当するクラス
/// (负责获取可用模型、过滤以及基于任务复杂度进行动态路由的类)
/// </summary>
public class GeminiModelRouter
{
    public List<string> ModelApiNames { get; private set; } = new List<string>();
    public List<string> ModelOptions { get; private set; } = new List<string>();

    /// <summary>
    /// 利用可能なモデル一覧を非同期で取得・フィルタリングする
    /// </summary>
    public async Task<bool> FetchModelsAsync(string apiKey, string proxyUrl)
    {
        if (string.IsNullOrEmpty(apiKey)) return false;

        string url = $"[https://generativelanguage.googleapis.com/v1beta/models?key=](https://generativelanguage.googleapis.com/v1beta/models?key=){apiKey}";

        GeminiNetworkResult result = await GeminiNetworkService.SendGetRequestAsync(url, proxyUrl);

        if (result.IsSuccess)
        {
            ParseModelsFromJson(result.ResponseText);
            return ModelApiNames.Count > 0;
        }
        else
        {
            SetFallbackModels();
            return false;
        }
    }

    private void ParseModelsFromJson(string json)
    {
        ModelApiNames.Clear();
        ModelOptions.Clear();

        try
        {
            ModelListResponse response = JsonUtility.FromJson<ModelListResponse>(json);
            if (response != null && response.models != null)
            {
                // 特定ドメインモデルやプレビュー版を除外 (排除特定领域模型和预览版)
                string[] excludedKeywords = new string[]
                {
                    "embedding", "aqa", "tts", "image", "vision",
                    "robotics", "computer-use", "customtools",
                    "preview", "latest", "experimental"
                };

                System.Text.RegularExpressions.Regex iterationRegex = new System.Text.RegularExpressions.Regex(@"-\d{3}$");

                foreach (var model in response.models)
                {
                    bool supportsGenerate = false;
                    if (model.supportedGenerationMethods != null)
                    {
                        foreach (var method in model.supportedGenerationMethods)
                        {
                            if (method == "generateContent") { supportsGenerate = true; break; }
                        }
                    }

                    if (supportsGenerate && model.name.StartsWith("models/gemini"))
                    {
                        string cleanName = model.name.Replace("models/", "");
                        string lowerName = cleanName.ToLower();
                        bool isExcluded = false;

                        foreach (var keyword in excludedKeywords)
                        {
                            if (lowerName.Contains(keyword)) { isExcluded = true; break; }
                        }

                        if (!isExcluded && iterationRegex.IsMatch(lowerName)) isExcluded = true;

                        if (!isExcluded)
                        {
                            ModelApiNames.Add(cleanName);
                            ModelOptions.Add($"{cleanName} ({model.displayName})");
                        }
                    }
                }
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"[Gemini Router] JSONパース失敗 (JSON parsing failed): {ex.Message}");
        }

        if (ModelApiNames.Count == 0) SetFallbackModels();
    }

    private void SetFallbackModels()
    {
        ModelApiNames = new List<string> { "gemini-3.5-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite", "gemini-2.5-pro" };
        ModelOptions = new List<string>
        {
            "gemini-3.5-flash (Fallback)",
            "gemini-3.1-pro (Fallback)",
            "gemini-3.1-flash-lite (Fallback)",
            "gemini-2.5-pro (Fallback)"
        };
    }

    /// <summary>
    /// パターンマッチングにより最適なモデルを検索する
    /// </summary>
    public string FindBestMatchingModel(string primaryKeyword, string secondaryKeyword, string fallback)
    {
        foreach (var name in ModelApiNames)
            if (name.ToLower().Contains(primaryKeyword.ToLower())) return name;

        if (!string.IsNullOrEmpty(secondaryKeyword))
            foreach (var name in ModelApiNames)
                if (name.ToLower().Contains(secondaryKeyword.ToLower())) return name;

        return ModelApiNames.Count > 0 ? ModelApiNames[0] : fallback;
    }
}
```

### File: `Editor\GeminiAgent\基盤・通信層\GeminiNetworkService.cs`
```csharp
﻿using System;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;

/// <summary>
/// API通信の結果をカプセル化するDTO (封装 API 通信结果的数据传输对象)
/// </summary>
public class GeminiNetworkResult
{
    public bool IsSuccess;
    public string ResponseText; // APIからの生テキストまたはJSON (API 返回的原始文本或命令 JSON)
    public string ErrorMessage;
    public int StatusCode;
}

/// <summary>
/// Gemini API とのHTTP通信を専任する純粋なネットワークサービスクラス
/// (专职负责与 Gemini API 进行 HTTP 通信的纯净网络服务类)
/// </summary>
public static class GeminiNetworkService
{
    /// <summary>
    /// POSTリクエストを送信する (发送 POST 请求，主要用于生成内容)
    /// </summary>
    public static async Task<GeminiNetworkResult> SendPostRequestAsync(string url, string jsonPayload, string proxyUrl, int timeoutSeconds = 60, bool extractFunctionCall = true)
    {
        GeminiNetworkResult result = new GeminiNetworkResult();

        try
        {
            var handler = new HttpClientHandler { ServerCertificateCustomValidationCallback = (m, c, ch, e) => true };
            if (!string.IsNullOrEmpty(proxyUrl?.Trim()))
            {
                handler.Proxy = new WebProxy(proxyUrl.Trim());
                handler.UseProxy = true;
            }

            using (HttpClient client = new HttpClient(handler))
            {
                client.Timeout = TimeSpan.FromSeconds(timeoutSeconds);
                var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

                HttpResponseMessage response = await client.PostAsync(url, content);
                string responseBody = await response.Content.ReadAsStringAsync();

                result.StatusCode = (int)response.StatusCode;
                result.IsSuccess = response.IsSuccessStatusCode;

                if (result.IsSuccess)
                {
                    result.ResponseText = extractFunctionCall ? ExtractTextFromResponse(responseBody, true) : responseBody;
                }
                else
                {
                    result.ErrorMessage = responseBody;
                }
            }
        }
        catch (Exception ex)
        {
            result.IsSuccess = false;
            result.ErrorMessage = ex.Message;
        }

        return result;
    }

    /// <summary>
    /// GETリクエストを送信する (发送 GET 请求，主要用于获取模型列表)
    /// </summary>
    public static async Task<GeminiNetworkResult> SendGetRequestAsync(string url, string proxyUrl, int timeoutSeconds = 15)
    {
        GeminiNetworkResult result = new GeminiNetworkResult();

        try
        {
            var handler = new HttpClientHandler { ServerCertificateCustomValidationCallback = (m, c, ch, e) => true };
            if (!string.IsNullOrEmpty(proxyUrl?.Trim()))
            {
                handler.Proxy = new WebProxy(proxyUrl.Trim());
                handler.UseProxy = true;
            }

            using (HttpClient client = new HttpClient(handler))
            {
                client.Timeout = TimeSpan.FromSeconds(timeoutSeconds);
                HttpResponseMessage response = await client.GetAsync(url);
                string responseBody = await response.Content.ReadAsStringAsync();

                result.StatusCode = (int)response.StatusCode;
                result.IsSuccess = response.IsSuccessStatusCode;
                result.ResponseText = responseBody;
                if (!result.IsSuccess) result.ErrorMessage = responseBody;
            }
        }
        catch (Exception ex)
        {
            result.IsSuccess = false;
            result.ErrorMessage = ex.Message;
        }

        return result;
    }

    private static string ExtractTextFromResponse(string rawApiResponse, bool checkFunctionCall)
    {
        GeminiResponseWrapper wrapper = JsonUtility.FromJson<GeminiResponseWrapper>(rawApiResponse);
        if (wrapper != null && wrapper.candidates != null && wrapper.candidates.Length > 0)
        {
            var part = wrapper.candidates[0].content.parts[0];

            if (checkFunctionCall && part.functionCall != null && !string.IsNullOrEmpty(part.functionCall.name))
            {
                return JsonUtility.ToJson(part.functionCall.args);
            }

            string text = part.text;
            if (!string.IsNullOrEmpty(text))
            {
                if (text.Contains("```json"))
                {
                    int start = text.IndexOf("```json") + 7;
                    int end = text.LastIndexOf("```");
                    if (end > start) text = text.Substring(start, end - start);
                }
                return text.Trim();
            }
        }
        return checkFunctionCall ? "{}" : "ERROR";
    }
}
```

### File: `Editor\GeminiAgent\実行エンジン層\GeminiCommandExcutorCore.cs`
```csharp
﻿using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;

/// <summary>
/// AIから返却されたJSONコマンドを解析し、適切なハンドラーにルーティングするコアエンジン
/// (负责解析 AI 返回的 JSON 指令包，并将其路由给对应处理器的核心引擎)
/// </summary>
public static class GeminiCommandExecutorCore
{
    // 登録されたすべてのハンドラー (所有已注册的处理器)
    private static readonly List<IUnityCommandHandler> _handlers = new List<IUnityCommandHandler>
    {
        new TransformCommandHandler(),
        new FileSystemCommandHandler(),
        new ScriptCommandHandler(),
        new GameObjectCommandHandler()
    };

    /// <summary>
    /// 複数アクション(Action Array)のチェーン実行・結果ログ集約
    /// (支持多 Action 链式顺序执行并汇总日志)
    /// </summary>
    public static string ExecuteBatchCommands(string jsonText)
    {
        try
        {
            DeveloperCommandBatch batch = JsonUtility.FromJson<DeveloperCommandBatch>(jsonText);

            // 単一コマンドへのフォールバック (单命令降级兼容)
            if (batch == null || batch.actions == null || batch.actions.Count == 0)
            {
                DeveloperCommandData singleCmd = JsonUtility.FromJson<DeveloperCommandData>(jsonText);
                if (singleCmd != null && !string.IsNullOrEmpty(singleCmd.actionType))
                {
                    batch = new DeveloperCommandBatch();
                    batch.actions.Add(singleCmd);
                }
                else return "⚠️ コマンドデータを解析できませんでした。(JSON Format Mismatch)";
            }

            StringBuilder batchLog = new StringBuilder();
            batchLog.AppendLine($"⚡ <b>一括コマンド実行開始 (全 {batch.actions.Count} 件のアクション):</b>");

            for (int i = 0; i < batch.actions.Count; i++)
            {
                var cmd = batch.actions[i];
                // 適切なハンドラーを検索 (查找对应的处理器)
                var handler = _handlers.FirstOrDefault(h => h.SupportedActionTypes.Contains(cmd.actionType));

                if (handler != null)
                {
                    string resultMsg = handler.Execute(cmd);
                    batchLog.AppendLine($"<b>[{i + 1}/{batch.actions.Count}]</b> {resultMsg}");
                }
                else
                {
                    batchLog.AppendLine($"<b>[{i + 1}/{batch.actions.Count}]</b> ⚠️ 未対応のアクション (Unsupported action): {cmd.actionType}");
                }
            }
            return batchLog.ToString().TrimEnd();
        }
        catch (Exception ex)
        {
            return $"❌ 操作実行例外 (Execution Exception): {ex.Message}";
        }
    }
}
```

### File: `Editor\GeminiAgent\実行エンジン層\GeminiCommandUtils.cs`
```csharp
﻿using System;
using UnityEditor;
using UnityEngine;

/// <summary>
/// 各コマンドハンドラー(Strategy)が共通で利用するユーティリティクラス
/// (各个命令处理器共同使用的共享工具类，解决寻找目标和父节点的问题)
/// </summary>
public static class GeminiCommandUtils
{
    /// <summary>
    /// アクティブ・非アクティブを問わず、対象のGameObjectを解決する
    /// (解析目标游戏对象，支持查找未激活的节点)
    /// </summary>
    public static GameObject ResolveTargetGameObject(string objectName, string childPath = null)
    {
        GameObject rootObj = null;
        if (string.IsNullOrEmpty(objectName)) return null;

        if (objectName.Equals("SELECTED_OBJECT", StringComparison.OrdinalIgnoreCase) ||
            objectName.Equals("SELECTED", StringComparison.OrdinalIgnoreCase))
        {
            rootObj = Selection.activeGameObject;
        }
        else
        {
            // 非アクティブなオブジェクトも含めて検索 (检索所有对象，包含未激活)
            var allObjects = Resources.FindObjectsOfTypeAll<GameObject>();
            foreach (var go in allObjects)
            {
                if (go.hideFlags == HideFlags.None && go.scene.IsValid() && go.name == objectName)
                {
                    rootObj = go;
                    break;
                }
            }
        }

        // 子オブジェクトのパスが指定されている場合は、Transformから検索 (深度寻址)
        if (rootObj != null && !string.IsNullOrEmpty(childPath))
        {
            Transform child = rootObj.transform.Find(childPath);
            return child != null ? child.gameObject : null;
        }
        return rootObj;
    }

    /// <summary>
    /// SELECTED_OBJECT キーワードを判定し、親 Transform を解体取得
    /// (解析 SELECTED_OBJECT 关键字，获取实际的父 Transform)
    /// </summary>
    public static Transform ResolveParentTransform(string parentName, Transform fallbackCanvasTransform = null)
    {
        if (string.IsNullOrEmpty(parentName)) return fallbackCanvasTransform;

        if (parentName.Equals("SELECTED_OBJECT", StringComparison.OrdinalIgnoreCase) ||
            parentName.Equals("SELECTED", StringComparison.OrdinalIgnoreCase))
            return Selection.activeTransform ?? fallbackCanvasTransform;

        GameObject parentObj = GameObject.Find(parentName);
        return parentObj != null ? parentObj.transform : fallbackCanvasTransform;
    }
}
```

### File: `Editor\GeminiAgent\実行エンジン層\GeminiCompileErrorWatcher.cs`
```csharp
﻿using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.Compilation;
using UnityEngine;

/// <summary>
/// Unityのコンパイルパイプライン(CompilationPipeline)を監視し、C#コンパイルエラーを自動検知するクラス
/// (监听 Unity 编译管线，自动拦截 C# 编译错误日志并触发回调的组件)
/// </summary>
[InitializeOnLoad]
public static class GeminiCompileErrorWatcher
{
    public static event Action<string> OnCompileErrorDetected;
    public static event Action OnCompileSuccessDetected;

    private const string IS_MONITORING_KEY = "GeminiAgent_CompileWatcher_IsMonitoring";
    private const string MONITOR_START_TIME_KEY = "GeminiAgent_CompileWatcher_StartTime"; // 新規追加: タイムスタンプキー
    public static bool IsMonitoring
    {
        get
        {
            bool isMon = EditorPrefs.GetBool(IS_MONITORING_KEY, false);
            if (!isMon) return false;

            // --- 新規追加: デッドロック回避のためのタイムアウト(30秒)判定 ---
            // (新增：为了避免域重载失败导致的状态锁死，引入 30 秒超时强制解锁机制)
            string timeStr = EditorPrefs.GetString(MONITOR_START_TIME_KEY, "0");
            if (long.TryParse(timeStr, out long startTimeTicks))
            {
                if (DateTime.UtcNow.Ticks - startTimeTicks > TimeSpan.FromSeconds(30).Ticks)
                {
                    Debug.LogWarning("[Gemini Agent] コンパイル監視がタイムアウトしました。状態をリセットします。(Compile watcher timed out. Resetting state.)");
                    EditorPrefs.SetBool(IS_MONITORING_KEY, false);
                    return false;
                }
            }
            return true;
        }
        set
        {
            EditorPrefs.SetBool(IS_MONITORING_KEY, value);
            if (value)
            {
                // 監視開始時に現在のUTCティック数を記録 (开始监控时记录当前时间戳)
                EditorPrefs.SetString(MONITOR_START_TIME_KEY, DateTime.UtcNow.Ticks.ToString());
            }
        }
    }

    static GeminiCompileErrorWatcher()
    {
        // 既存のイベント登録を一旦解除し、重複登録を防止する (先解除已有的事件订阅，防止域重载导致的重复订阅)
        CompilationPipeline.assemblyCompilationFinished -= OnAssemblyCompilationFinished;
        CompilationPipeline.assemblyCompilationFinished += OnAssemblyCompilationFinished;
    }

    private static void OnAssemblyCompilationFinished(string assemblyPath, CompilerMessage[] messages)
    {
        List<string> errorLogList = new List<string>();

        foreach (var msg in messages)
        {
            if (msg.type == CompilerMessageType.Error)
            {
                string formattedError = $"• {msg.file}({msg.line},{msg.column}): {msg.message}";
                errorLogList.Add(formattedError);
            }
        }

        if (errorLogList.Count > 0)
        {
            IsMonitoring = false;
            string combinedErrors = string.Join("\n", errorLogList);
            OnCompileErrorDetected?.Invoke(combinedErrors);
        }
        else if (IsMonitoring)
        {
            IsMonitoring = false;
            OnCompileSuccessDetected?.Invoke();
        }
    }
}
```

### File: `Editor\GeminiAgent\実行エンジン層\GeminiContextScanner.cs`
```csharp
﻿using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis;

/// <summary>
/// Unityプロジェクトの文脈(フォルダ構造、C# API、シーン階層、選択オブジェクト)をスキャン・抽出するアナライザークラス
/// (负责扫描与提取 Unity 项目上下文信息：目录树、按需提取的 C# API 签名、场景层级树与当前选中物体的分析器)
/// </summary>
public static class GeminiContextScanner
{
    // ... [保留原有代码] CaptureSelectionContext, GetGameObjectPath, CaptureDirectoryStructure, CaptureSceneContextJson, DumpGameObjectHierarchy ...

    /// <summary>
    /// 現在ヒエラルキー上で選択されているGameObjectのコンテキスト情報(階層パス、コンポーネント、Transform)をキャプチャ
    /// (抓取当前在 Hierarchy 中选中的 GameObject 上下文信息：全路径、挂载组件、Transform/RectTransform)
    /// </summary>
    public static string CaptureSelectionContext()
    {
        GameObject activeObj = Selection.activeGameObject;
        if (activeObj == null)
        {
            return "[選択オブジェクト: なし (No Object Selected)]";
        }

        StringBuilder sb = new StringBuilder();
        sb.AppendLine($"[選択中メインオブジェクト: '{activeObj.name}']");
        sb.AppendLine($"  ・階層フルパス (Hierarchy Path): {GetGameObjectPath(activeObj.transform)}");

        var components = activeObj.GetComponents<Component>();
        var compNames = new System.Collections.Generic.List<string>();
        foreach (var c in components)
        {
            if (c != null) compNames.Add(c.GetType().Name);
        }
        sb.AppendLine($"  ・アタッチ済みコンポーネント: [{string.Join(", ", compNames)}]");

        if (activeObj.TryGetComponent<RectTransform>(out var rectTransform))
        {
            sb.AppendLine($"  ・RectTransform -> pos: {rectTransform.anchoredPosition}, size: {rectTransform.sizeDelta}, anchorMin: {rectTransform.anchorMin}, anchorMax: {rectTransform.anchorMax}");
        }
        else
        {
            sb.AppendLine($"  ・Transform -> localPos: {activeObj.transform.localPosition}, localRot: {activeObj.transform.localEulerAngles}, localScale: {activeObj.transform.localScale}");
        }

        if (Selection.gameObjects.Length > 1)
        {
            sb.AppendLine($"  ・他選択オブジェクト数: {Selection.gameObjects.Length - 1} 件");
        }

        return sb.ToString();
    }

    /// <summary>
    /// Transformからルートまでの階層フルパスを取得 (例: Canvas/MainPanel/ConfirmButton)
    /// (获取从 Root 到当前物体的完整层级路径)
    /// </summary>
    public static string GetGameObjectPath(Transform transform)
    {
        string path = transform.name;
        while (transform.parent != null)
        {
            transform = transform.parent;
            path = transform.name + "/" + path;
        }
        return path;
    }

    /// <summary>
    /// Assetsフォルダ配下のディレクトリ構造(木構造)を再帰的にキャプチャ
    /// (递归抓取 Assets 目录下的树状文件夹与文件结构)
    /// </summary>
    public static string CaptureDirectoryStructure(string rootPath, int currentDepth = 0, int maxDepth = 3)
    {
        if (!Directory.Exists(rootPath)) return $"[Directory Not Found: {rootPath}]";

        StringBuilder sb = new StringBuilder();
        string indent = new string(' ', currentDepth * 2);

        try
        {
            string[] directories = Directory.GetDirectories(rootPath);
            foreach (string dir in directories)
            {
                string dirName = Path.GetFileName(dir);
                if (dirName.StartsWith(".") || dirName == "Library" || dirName == "Temp") continue;

                sb.AppendLine($"{indent}📁 {dirName}/");

                if (currentDepth < maxDepth)
                {
                    sb.Append(CaptureDirectoryStructure(dir, currentDepth + 1, maxDepth));
                }
            }

            string[] files = Directory.GetFiles(rootPath);
            foreach (string file in files)
            {
                if (file.EndsWith(".meta")) continue;
                string fileName = Path.GetFileName(file);
                sb.AppendLine($"{indent}  📄 {fileName}");
            }
        }
        catch (System.Exception ex)
        {
            sb.AppendLine($"{indent}[Error scanning {rootPath}: {ex.Message}]");
        }

        return sb.ToString();
    }

    /// <summary>
    /// アクティブシーンの全GameObject階層構造をキャプチャ
    /// (抓取当前激活 Scene 的全部 GameObject 节点与组件挂载结构)
    /// </summary>
    public static string CaptureSceneContextJson()
    {
        StringBuilder contextBuilder = new StringBuilder();
        var rootObjects = UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects();

        contextBuilder.AppendLine("Root GameObjects:");
        foreach (var root in rootObjects)
        {
            DumpGameObjectHierarchy(root.transform, contextBuilder, 1);
        }

        return contextBuilder.ToString();
    }

    private static void DumpGameObjectHierarchy(Transform current, StringBuilder builder, int indentLevel)
    {
        string indent = new string(' ', indentLevel * 2);

        var components = current.GetComponents<Component>();
        var compNames = new System.Collections.Generic.List<string>();
        foreach (var c in components)
        {
            if (c != null) compNames.Add(c.GetType().Name);
        }
        string componentsStr = $" [{string.Join(", ", compNames)}]";

        builder.AppendLine($"{indent}- {current.name}{componentsStr}");

        if (indentLevel < 4)
        {
            foreach (Transform child in current)
            {
                DumpGameObjectHierarchy(child, builder, indentLevel + 1);
            }
        }
    }

    /// <summary>
    /// 指定フォルダ内のC#スクリプトを解析し、グローバルシンボル一覧と、文脈に関連するクラスの詳細APIをオンデマンド抽出する
    /// (利用 Roslyn 解析指定目录下的 C# 脚本。引入增量扫描与预过滤机制，避免在超大工程中引发内存与主线程卡顿)
    /// </summary>
    public static string CaptureProjectScriptsSummary(string folderPath, string userPrompt, GameObject activeObject)
    {
        if (!Directory.Exists(folderPath))
        {
            return $"[Scan Path Not Found: {folderPath}]";
        }

        // 1. 文脈キーワードの抽出 (提取上下文关键词，包括用户提示词的单词和选中物体的组件名)
        HashSet<string> contextKeywords = new HashSet<string>();
        if (!string.IsNullOrEmpty(userPrompt))
        {
            var words = Regex.Split(userPrompt, @"\W+").Where(w => w.Length > 2);
            foreach (var w in words) contextKeywords.Add(w);
        }

        if (activeObject != null)
        {
            foreach (var comp in activeObject.GetComponents<Component>())
            {
                if (comp != null) contextKeywords.Add(comp.GetType().Name);
            }
        }

        StringBuilder globalIndexBuilder = new StringBuilder();
        StringBuilder detailedApiBuilder = new StringBuilder();

        globalIndexBuilder.AppendLine("【Global Symbol Index (グローバルクラス一覧)】");
        detailedApiBuilder.AppendLine("【Relevant API Details (関連API詳細)】");

        string[] scriptFiles = Directory.GetFiles(folderPath, "*.cs", SearchOption.AllDirectories);

        foreach (string file in scriptFiles)
        {
            if (file.Contains("Editor") || file.Contains("Generated")) continue;

            // --- 新規追加: ファイルサイズ制限 (新增：跳过大于 500KB 的超大文件，防止内存溢出) ---
            if (new FileInfo(file).Length > 500 * 1024) continue;

            string relativePath = file.Replace("\\", "/");
            int assetsIndex = relativePath.IndexOf("Assets/");
            if (assetsIndex >= 0) relativePath = relativePath.Substring(assetsIndex);

            string codeText = File.ReadAllText(file);

            // --- 新規追加: 事前テキストマッチング (新增：纯文本预匹配，只有命中关键词才进行昂贵的 AST 解析) ---
            bool requiresDeepScan = contextKeywords.Count == 0 || contextKeywords.Any(k => codeText.Contains(k));

            // グローバルインデックス構築のための簡易正規表現マッチ (为全局索引进行快速正则匹配类名，不构建 AST)
            Match classMatch = Regex.Match(codeText, @"class\s+([A-Za-z0-9_]+)");
            if (classMatch.Success)
            {
                globalIndexBuilder.AppendLine($" - {classMatch.Groups[1].Value} ({relativePath})");
            }

            if (!requiresDeepScan) continue; // 関連性がなければAST解析をスキップ (无关文件直接跳过)

            // ここから下は関連ファイルのみASTを構築 (仅对强相关文件进行 Roslyn AST 解析)
            SyntaxTree tree = CSharpSyntaxTree.ParseText(codeText);
            CompilationUnitSyntax root = tree.GetCompilationUnitRoot();

            var classDeclarations = root.DescendantNodes().OfType<ClassDeclarationSyntax>();
            foreach (var classDecl in classDeclarations)
            {
                string className = classDecl.Identifier.Text;
                if (contextKeywords.Contains(className) || contextKeywords.Any(k => codeText.Contains(k)))
                {
                    detailedApiBuilder.AppendLine($"\n--- Script: {className} ({relativePath}) ---");
                    detailedApiBuilder.AppendLine($"  {classDecl.Modifiers} class {className}");

                    var fields = classDecl.DescendantNodes().OfType<FieldDeclarationSyntax>()
                        .Where(f => f.Modifiers.Any(m => m.IsKind(SyntaxKind.PublicKeyword) || f.AttributeLists.ToString().Contains("SerializeField")));
                    foreach (var f in fields) detailedApiBuilder.AppendLine($"    Field: {f.Declaration}");

                    var methods = classDecl.DescendantNodes().OfType<MethodDeclarationSyntax>()
                        .Where(m => m.Modifiers.Any(mod => mod.IsKind(SyntaxKind.PublicKeyword)));
                    foreach (var m in methods)
                    {
                        detailedApiBuilder.AppendLine($"    Method: {m.Modifiers} {m.ReturnType} {m.Identifier}{m.ParameterList}");
                        var trivia = m.GetLeadingTrivia().Select(i => i.GetStructure()).OfType<DocumentationCommentTriviaSyntax>().FirstOrDefault();
                        if (trivia != null)
                        {
                            string summary = trivia.Content.ToString().Replace("///", "").Replace("\n", " ").Trim();
                            detailedApiBuilder.AppendLine($"      Summary: {summary}");
                        }
                    }
                }
            }
        }
        return globalIndexBuilder.ToString() + "\n" + detailedApiBuilder.ToString();
    }
}
```

### File: `Editor\GeminiAgent\実行エンジン層\IUnityCommandHandler.cs`
```csharp
﻿/// <summary>
/// 実行器(Executor)の各コマンド処理を抽象化するインターフェース
/// (抽象化执行器各个命令处理逻辑的接口)
/// </summary>
public interface IUnityCommandHandler
{
    /// <summary>
    /// このハンドラーが処理できるアクションタイプの配列 (该处理器支持的 ActionType 数组)
    /// </summary>
    string[] SupportedActionTypes { get; }

    /// <summary>
    /// コマンドを実行し、結果のログ文字列を返す (执行命令并返回结果日志)
    /// </summary>
    string Execute(DeveloperCommandData command);
}
```

### File: `Scripts\Core\BlockManager.cs`
```csharp
﻿using UnityEngine;
using System;
using System.Collections.Generic;

// [追加] スクリプトの実行順序を最優先にする (-100に設定)
// これにより、他のコンポーネントがStart()を呼ぶ前に確実に登録が完了する
[DefaultExecutionOrder(-100)]
public class BlockManager : MonoBehaviour
{
    [Header("All Blocks in the Scene")]
    [SerializeField] private List<Block> allBlocks = new List<Block>();

    private Dictionary<int, Block> blockDictionary = new Dictionary<int, Block>();

    public List<Block> AllBlocks => allBlocks;

    public event Action OnBlockDataUpdated;

    // [追加] サービスロケーターへの登録・解除
    private void Awake()
    {
        ServiceLocator.Register<BlockManager>(this);
    }

    private void OnDestroy()
    {
        ServiceLocator.Unregister<BlockManager>();
    }

    public void NotifyBlockDataUpdated()
    {
        OnBlockDataUpdated?.Invoke();
    }

    // RegisterBlock method
    public void RegisterBlock(Block block)
    {
        if (block == null || block.BlockRoot == null) return;

        allBlocks.Add(block);
        blockDictionary[block.BlockID] = block;

        if (block.BlockRoot.GetComponent<BlockReference>() == null)
        {
            var reference = block.BlockRoot.gameObject.AddComponent<BlockReference>();
            reference.LinkedBlock = block;
        }
    }

    public Block GetBlockByID(int blockID)
    {
        blockDictionary.TryGetValue(blockID, out Block block);
        return block;
    }
}
```

### File: `Scripts\Core\ProjectData.cs`
```csharp
// ProjectData.cs
// PRODUCTION VERSION - Auto-clear cache every time Play Mode starts
// 1 Unity unit = 1 mm exactly (no mm-to-m conversion)
// Design points (GroupID=0) and Measured points (GroupID=1) handled separately

using System;
using System.Collections.Generic;
using UnityEngine;

[DefaultExecutionOrder(-100)] // [�ǉ�] ���s�����̈����グ
public class ProjectData : MonoBehaviour
{

    [SerializeField]
    private Dictionary<Guid, Point> points = new Dictionary<Guid, Point>();

    [SerializeField]
    private List<Point> joiningPoints = new List<Point>();

    public Dictionary<Guid, Point> Points => points;
    public List<Point> JoiningPoints => joiningPoints;

    private void Awake()
    {
        // Auto-clear ALL cache every time Play Mode starts
        // This prevents any old serialized small values (7.911) from loading
        Clear();
    }

    public void AddPoint(Point point)
    {
        if (point == null) return;
        points[point.ID] = point;

        if (point.PointType == "Joining")
        {
            if (!joiningPoints.Contains(point))
                joiningPoints.Add(point);
        }

        Debug.Log($"Point added: {point.Name} (Type: {point.PointType})");
    }

    public Point GetPoint(Guid id)
    {
        points.TryGetValue(id, out Point p);
        return p;
    }

    public void Clear()
    {
        points.Clear();
        joiningPoints.Clear();
        Debug.Log("<color=green>[ProjectData] Auto-cleared ALL cached points and JoiningPoints on Play Mode start.</color>");
    }
    /// <summary>
    /// Completely removes a specific point from the core data dictionary and lists. [�f�[�^���S�폜]
    /// </summary>
    /// <param name="id">The Guid of the point to remove.</param>
    public void RemovePoint(Guid id)
    {
        if (points.TryGetValue(id, out Point p))
        {
            points.Remove(id);

            // Safely remove from the auxiliary list if it exists
            if (p.PointType == "Joining")
            {
                joiningPoints.Remove(p);
            }
        }
    }
}
```

### File: `Scripts\Core\ProjectRootBehaviour.cs`
```csharp
using UnityEngine;

// [�ǉ�] ���s�����̈����グ
[DefaultExecutionOrder(-100)]
public class ProjectRootBehaviour : MonoBehaviour
{
    [Header("ProjectData")]
    [SerializeField] private ProjectData projectData;

    public ProjectData ProjectData => projectData;

    private void Awake()
    {
        if (projectData == null)
        {
            projectData = GetComponent<ProjectData>();
            if (projectData == null)
                projectData = gameObject.AddComponent<ProjectData>();
        }

        // [�ǉ�] ���[�g���g��ProjectData���T�[�r�X�Ƃ��ēo�^
        ServiceLocator.Register<ProjectRootBehaviour>(this);
        ServiceLocator.Register<ProjectData>(projectData);
    }

    private void OnDestroy()
    {
        ServiceLocator.Unregister<ProjectRootBehaviour>();
        ServiceLocator.Unregister<ProjectData>();
    }
}
```

### File: `Scripts\Core\ServiceLocator.cs`
```csharp
﻿// ===============================================
// ServiceLocator.cs
// PRODUCTION VERSION - Pure C# Static Registry
// ===============================================

using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// グローバルサービスロケーター (Global Service Locator)
/// 純粋なC#静的クラスとして実装。MonoBehaviourのオーバーヘッドを完全に排除。
/// (实现为纯C#静态类，完全消除 MonoBehaviour 的开销)
/// </summary>
public static class ServiceLocator
{
    private static readonly Dictionary<Type, object> _services = new Dictionary<Type, object>();

    /// <summary>
    /// サービスの登録 (Register a service)
    /// </summary>
    /// <typeparam name="T">インターフェースまたはクラス型 (接口或类类型)</typeparam>
    /// <param name="service">サービスのインスタンス (服务实例)</param>
    public static void Register<T>(T service)
    {
        var type = typeof(T);
        if (_services.ContainsKey(type))
        {
            Debug.LogWarning($"[ServiceLocator] サービス {type.Name} は既に登録されています。上書きします。(Service already registered. Overwriting.)");
        }
        _services[type] = service;
        // Debug.Log($"<color=cyan>[ServiceLocator] Registered: {type.Name}</color>");
    }

    /// <summary>
    /// サービスの登録解除 (Unregister a service)
    /// オブジェクト破棄時に呼び出す。(在对象销毁时调用)
    /// </summary>
    public static void Unregister<T>()
    {
        var type = typeof(T);
        if (_services.ContainsKey(type))
        {
            _services.Remove(type);
        }
    }

    /// <summary>
    /// サービスの取得 (Get a service - Fail-Fast)
    /// 見つからない場合は即座に例外をスローし、潜在的なバグを早期発見する。
    /// (找不到时立即抛出异常，快速失败以暴露潜在 Bug)
    /// </summary>
    public static T Get<T>()
    {
        var type = typeof(T);
        if (_services.TryGetValue(type, out var service))
        {
            return (T)service;
        }
        throw new Exception($"[ServiceLocator] 致命的エラー: サービス {type.Name} が見つかりません。アクセス前にRegister()が呼ばれているか確認してください。(Fatal: Service not found.)");
    }

    /// <summary>
    /// サービスの安全な取得 (Try get a service)
    /// 存在しなくても例外を出さず、boolを返す。
    /// </summary>
    public static bool TryGet<T>(out T service)
    {
        var type = typeof(T);
        if (_services.TryGetValue(type, out var obj))
        {
            service = (T)obj;
            return true;
        }
        service = default;
        return false;
    }

    /// <summary>
    /// キャッシュの完全クリア (Clear all caches)
    /// Unity Editorの高速再生設定(Enter Play Mode Options)でのドメインリロード対策。
    /// (防御 Unity Editor 快速播放模式下的静态变量污染)
    /// </summary>
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
    public static void ClearAll()
    {
        _services.Clear();
    }
}
```

### File: `Scripts\Data\Block.cs`
```csharp
// ===============================================
// Block.cs
// PRODUCTION VERSION - Pruned Redundant 3D Solids
// ===============================================

using UnityEngine;

/// <summary>
/// Core Block Data Entity. 
/// Streamlined: 3D Solids are now natively merged into the BlockRoot.
/// </summary>
[System.Serializable]
public class Block
{
    [Header("=== Core Identity ===")]
    public int BlockID;
    public string Name;          // Restored to prevent breaking existing UI labels
    public string MatchCode;     // The sanitized, uppercase code used for CSV matching (e.g., "OC1")

    [Header("=== Assembly Sequence (�g�������ݒ�) ===")]
    [Tooltip("���̃u���b�N�̑g�ݗ��Ă��鏇�Ԃ������܂�")]
    public int AssemblyOrder = 1;  // �g������ (�f�t�H���g��1)

    [Tooltip("�S�������ɂ���Ď����I�ɃO���[�v�����ꂽ�ۂ�ID�ł�")]
    public int AssemblyGroup = 1;  // �S�������ɂ�鎩���O���[�v��ID (�f�t�H���g��1)

    [Header("=== Scene Reference ===")]
    public Transform BlockRoot;
    public bool IsMeasured;

    [Header("=== Original Attributes ===")]
    public int Type1;
    public int Type2;
    public int Type3;
    public bool HasMeasurementValue;
    public bool DisplayFlag;
    public bool SelectFlag;
    public int[] IntAttributes = new int[10];
    public double[] DoubleAttributes = new double[10];

    public Block(int id, string name, Transform root = null)
    {
        BlockID = id;
        Name = name;
        MatchCode = name.Trim().ToUpper();
        BlockRoot = root;
    }
}
```

### File: `Scripts\Data\BlockReference.cs`
```csharp
using UnityEngine;

/// <summary>
/// Attached to each Block root GameObject for easy reverse lookup (Scene Object to Block Data)
/// </summary>
public class BlockReference : MonoBehaviour
{
    [HideInInspector]
    public Block LinkedBlock;
}
```

### File: `Scripts\Data\Entity.cs`
```csharp
public interface IEntity
{
    int ID { get; set; }
    string Name { get; set; }
    void Update();
}
```

### File: `Scripts\Data\EntityBase.cs`
```csharp
using System;
using System.Security.Principal;
using UnityEngine;

[System.Serializable]
public abstract class EntityBase : IEntity
{
    [SerializeField] private int id;
    [SerializeField] private string name;

    public int ID
    {
        get => id;
        set => id = value;
    }

    public string Name
    {
        get => name;
        set => name = value;
    }

    public abstract void Update(); 
}
```

### File: `Scripts\Data\Point.cs`
```csharp
﻿// ===============================================
// Point.cs
// Production-Ready Point Data Structure (Updated)
// ===============================================

using UnityEngine;

[System.Serializable]
public class Point
{
    [SerializeField] private System.Guid id = System.Guid.NewGuid();
    public System.Guid ID => id;

    // 
    public string Block;       // 
    public string Joint;       // 
    public string PlateType;   // 
    public string PointPlace;  // 
    public string TieID;       // 

    public string DisplayID;
    public string Name;
    public string PointType = "Reference";
    public float RootGap;

    public Vector3 DesignPosition;
    public Vector3 MeasurePosition;
    public Vector3 Delta;
    public float ErrorDistance;

    public float Radius = 0.025f;
    public Color Color = new Color(0.25f, 0.75f, 1.0f, 1.0f);
    public int GroupID;

    public Point()
    {
        Block = string.Empty;
        Joint = string.Empty;
        PlateType = string.Empty;
        PointPlace = string.Empty;
        TieID = string.Empty;

        DesignPosition = Vector3.zero;
        MeasurePosition = Vector3.zero;
        Delta = Vector3.zero;
        ErrorDistance = 0f;
        Radius = 0.025f;
        PointType = "Reference";
        RootGap = 0f;
    }

    public void CalculateError()
    {
        Delta = MeasurePosition - DesignPosition;
        ErrorDistance = Delta.magnitude;
    }
}
```

### File: `Scripts\Data\PointSelectData.cs`
```csharp
using UnityEngine;

public class PointSelectData : MonoBehaviour
{
    [Header("Selected Point Data")]
    public Point point;

    // Returns the design position (alternative to old Position property)
    public Vector3 GetPosition()
    {
        return point != null ? point.DesignPosition : Vector3.zero;
    }
}
```

### File: `Scripts\Features\AssemblyAnimationController.cs`
```csharp
// ===============================================
// AssemblyAnimationController.cs
// PRODUCTION VERSION - Sequence Playback & Exploded View
// ===============================================

using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// BlockManager������ɏ����������悤������ݒ�
[DefaultExecutionOrder(-70)]
public class AssemblyAnimationController : MonoBehaviour
{
    [Header("Animation Settings (�A�j���[�V�����ݒ�)")]
    [Tooltip("�e�g���X�e�b�v�Ԃ̑ҋ@���ԁi�b�j")]
    public float stepInterval = 1.5f;

    [Header("Exploded View Settings (����}�ݒ�)")]
    [Tooltip("����}�Ŋe�u���b�N���ړ����鋗�� (mm)")]
    public float explodeDistance = 3000f;
    [Tooltip("�����A�j���[�V�����̏��v���ԁi�b�j")]
    public float explodeDuration = 0.5f;

    private BlockManager blockManager;
    private Coroutine currentAnimCoroutine;
    private Coroutine explodeCoroutine;

    private bool isExploded = false;

    // ����}���s�O�̌��̍��W�����S�ɕێ����鎫��
    private Dictionary<int, Vector3> originalPositions = new Dictionary<int, Vector3>();

    private void Start()
    {
        // �T�[�r�X���P�[�^�[���g�p���ăR�A�}�l�[�W���[���擾
        ServiceLocator.TryGet(out blockManager);
    }

    /// <summary>
    /// �g������ (AssemblyOrder) �ɏ]���āA��莞�ԊԊu�Ńu���b�N��\�����Ă����A�j���[�V���������s
    /// </summary>
    public void PlayAssemblyAnimation()
    {
        if (blockManager == null || blockManager.AllBlocks.Count == 0) return;

        // ���ɕ���}(Exploded)��ԂȂ猳�̈ʒu�ɖ߂�
        if (isExploded) ToggleExplodedView();

        // ���s���̃A�j���[�V����������Β�~
        if (currentAnimCoroutine != null) StopCoroutine(currentAnimCoroutine);

        currentAnimCoroutine = StartCoroutine(AssemblyRoutine());
    }

    private IEnumerator AssemblyRoutine()
    {
        Debug.Log("<color=cyan>[Animation] �g���A�j���[�V�����J�n</color>");

        // 1. �S�u���b�N����U��\���ɂ���
        foreach (var block in blockManager.AllBlocks)
        {
            if (block.BlockRoot != null) block.BlockRoot.gameObject.SetActive(false);
        }

        yield return new WaitForSeconds(0.5f);

        // 2. �g������(AssemblyOrder)�ŃO���[�v�����ď����i1,2,3...�j�Ń\�[�g
        var orderedGroups = blockManager.AllBlocks
            .GroupBy(b => b.AssemblyOrder)
            .OrderBy(g => g.Key)
            .ToList();

        // 3. ���Ԃɕ\�����Ă���
        foreach (var group in orderedGroups)
        {
            Debug.Log($"<color=cyan>[Animation] Step {group.Key} ��\��</color>");
            foreach (var block in group)
            {
                if (block.BlockRoot != null) block.BlockRoot.gameObject.SetActive(true);
            }

            // �w�莞�ԑҋ@
            yield return new WaitForSeconds(stepInterval);
        }

        Debug.Log("<color=green>[Animation] �g���A�j���[�V��������</color>");
    }

    /// <summary>
    /// ���f���̕����m�F�i����}�j�ƕ������g�O������
    /// </summary>
    public void ToggleExplodedView()
    {
        if (blockManager == null || blockManager.AllBlocks.Count == 0) return;

        // �g���A�j���[�V���������s���ł���΋�����~���A�S�\����Ԃɂ���
        if (currentAnimCoroutine != null)
        {
            StopCoroutine(currentAnimCoroutine);
            foreach (var b in blockManager.AllBlocks)
                if (b.BlockRoot != null) b.BlockRoot.gameObject.SetActive(true);
        }

        if (explodeCoroutine != null) StopCoroutine(explodeCoroutine);

        if (!isExploded)
        {
            // --- �����iExplode�j���� ---
            originalPositions.Clear();

            // 1. �S�u���b�N�̕��Ϗd�S���v�Z
            Vector3 globalCentroid = Vector3.zero;
            int validCount = 0;
            foreach (var block in blockManager.AllBlocks)
            {
                if (block.BlockRoot != null && block.BlockRoot.gameObject.activeSelf)
                {
                    Vector3 center = CalculateBlockCentroid(block.BlockRoot);
                    globalCentroid += center;
                    validCount++;
                    // ���݂̍��W���L�^
                    originalPositions[block.BlockID] = block.BlockRoot.position;
                }
            }
            if (validCount > 0) globalCentroid /= validCount;

            // 2. �e�u���b�N�̖ڕW���ˍ��W���v�Z
            Dictionary<Transform, Vector3> targetPositions = new Dictionary<Transform, Vector3>();
            foreach (var block in blockManager.AllBlocks)
            {
                if (block.BlockRoot != null && block.BlockRoot.gameObject.activeSelf)
                {
                    Vector3 center = CalculateBlockCentroid(block.BlockRoot);
                    Vector3 direction = (center - globalCentroid).normalized;
                    if (direction == Vector3.zero) direction = Vector3.up; // �d�S�����S�Ɉ�v����ꍇ�̃t�F�[���Z�[�t

                    targetPositions[block.BlockRoot] = originalPositions[block.BlockID] + (direction * explodeDistance);
                }
            }

            explodeCoroutine = StartCoroutine(LerpPositions(targetPositions, explodeDuration));
            isExploded = true;
            Debug.Log("<color=yellow>[Animation] �����m�F�iExploded View�j�W�J</color>");
        }
        else
        {
            // --- �����iRestore�j���� ---
            Dictionary<Transform, Vector3> targetPositions = new Dictionary<Transform, Vector3>();
            foreach (var block in blockManager.AllBlocks)
            {
                if (block.BlockRoot != null && originalPositions.ContainsKey(block.BlockID))
                {
                    targetPositions[block.BlockRoot] = originalPositions[block.BlockID];
                }
            }

            explodeCoroutine = StartCoroutine(LerpPositions(targetPositions, explodeDuration));
            isExploded = false;
            Debug.Log("<color=yellow>[Animation] �����m�F�iExploded View�j����</color>");
        }
    }

    /// <summary>
    /// �C�[�Y�C���E�A�E�g�𔺂����炩�ȍ��W��ԁiTween�j
    /// </summary>
    private IEnumerator LerpPositions(Dictionary<Transform, Vector3> targets, float duration)
    {
        float elapsed = 0f;
        // ���݂̍��W���X�i�b�v�V���b�g
        Dictionary<Transform, Vector3> startPositions = new Dictionary<Transform, Vector3>();
        foreach (var kvp in targets)
        {
            startPositions[kvp.Key] = kvp.Key.position;
        }

        while (elapsed < duration)
        {
            elapsed += Time.deltaTime;
            // ���炩�ȃJ�[�u�iSmoothStep�j��K�p
            float t = Mathf.SmoothStep(0f, 1f, elapsed / duration);

            foreach (var kvp in targets)
            {
                if (kvp.Key != null)
                {
                    kvp.Key.position = Vector3.Lerp(startPositions[kvp.Key], kvp.Value, t);
                }
            }
            yield return null;
        }

        // �ŏI�t���[���ŃY����␳�����m�ȍ��W��K�p
        foreach (var kvp in targets)
        {
            if (kvp.Key != null) kvp.Key.position = kvp.Value;
        }
    }

    /// <summary>
    /// ���b�V���̋��E���琳�m�ȏd�S���v�Z����
    /// </summary>
    private Vector3 CalculateBlockCentroid(Transform root)
    {
        Renderer rend = root.GetComponentInChildren<Renderer>();
        if (rend != null) return rend.bounds.center;
        return root.position;
    }
}
```

### File: `Scripts\Features\AssemblySequenceManager.cs`
```csharp
// ===============================================
// AssemblySequenceManager.cs
// PRODUCTION VERSION - Union-Find Graph Sync for Assembly Orders
// ===============================================

using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// ���s�����������グ�A���̈ˑ��֌W��葁�������������悤�ɂ���
[DefaultExecutionOrder(-80)]
public class AssemblySequenceManager : MonoBehaviour
{
    private BlockManager blockManager;
    private ConstraintManager constraintManager;

    // �O���[�v�⏇���������I�ɍČv�Z���ꂽ�ۂɃg���K�[�����C�x���g
    public event Action OnSequenceDataSynchronized;

    private void Start()
    {
        // �T�[�r�X���P�[�^�[���g�p���ăR�A�}�l�[�W���[�����S�Ɏ擾
        ServiceLocator.TryGet(out blockManager);
        ServiceLocator.TryGet(out constraintManager);

        if (constraintManager != null)
        {
            // �S�������̒ǉ��E�폜���Ď����A�ˑ��֌W�O���t�����A���^�C���ōč\�z����
            constraintManager.OnConstraintAdded += RecalculateAssemblyGroups;
        }
    }

    private void OnDestroy()
    {
        if (constraintManager != null)
        {
            // ���������[�N��h�����߂̓o�^����
            constraintManager.OnConstraintAdded -= RecalculateAssemblyGroups;
        }
    }

    /// <summary>
    /// ���[�U�[��UI��œ���̃u���b�N�̑g���������蓮�ŕύX�����ۂɌĂяo�����B
    /// ����̃O���[�v(Group)�ɑ����邷�ׂẴu���b�N�́A���̐V���������ɋ����I�ɓ��������B
    /// </summary>
    /// <param name="groupID">�ΏۂƂȂ�O���[�vID</param>
    /// <param name="newOrder">�V�����ݒ肳�ꂽ�g������</param>
    public void SetAssemblyOrderForGroup(int groupID, int newOrder)
    {
        if (blockManager == null) return;
        bool changed = false;

        foreach (var block in blockManager.AllBlocks)
        {
            // �ΏۃO���[�v�ɑ����Ă���A���������قȂ�ꍇ�̂ݍX�V
            if (block.AssemblyGroup == groupID && block.AssemblyOrder != newOrder)
            {
                block.AssemblyOrder = newOrder;
                changed = true;
            }
        }

        if (changed)
        {
            Debug.Log($"<color=cyan>[AssemblySequence] �g�������̓���: Group {groupID} �͏��� {newOrder} �ɓ��ꂳ��܂����B</color>");
            OnSequenceDataSynchronized?.Invoke(); // UI�ւ̍X�V�ʒm
        }
    }

    /// <summary>
    /// �R�A�A���S���Y���F�f�W���f�[�^�\�� (Union-Find) �𗘗p����
    /// ���ׂẴA�N�e�B�u�ȍS�����X�L�������A�ڑ����ꂽ�u���b�N�𓯈��Group�ɓ�������B
    /// </summary>
    public void RecalculateAssemblyGroups()
    {
        if (blockManager == null || constraintManager == null) return;

        var allBlocks = blockManager.AllBlocks;
        Dictionary<string, string> parentMap = new Dictionary<string, string>();

        // 1. Union-Find�i�f�W���f�[�^�\���j�̏������F�ŏ��͎������g��e�Ƃ���
        foreach (var block in allBlocks)
        {
            parentMap[block.MatchCode] = block.MatchCode;
        }

        // ���[�g�m�[�h�̌����p���[�J���֐�
        string Find(string i)
        {
            if (parentMap[i] == i) return i;
            // �o�H���k (Path Compression) ��p���Č�����������
            return parentMap[i] = Find(parentMap[i]);
        }

        // 2�̏W���𓝍����郍�[�J���֐�
        void Union(string i, string j)
        {
            string rootI = Find(i);
            string rootJ = Find(j);
            if (rootI != rootJ) parentMap[rootI] = rootJ;
        }

        // 2. �S�Ă̍S���𔽕��������A�u���b�N�̊֘A���i�G�b�W�j�𒊏o����
        foreach (var constraint in constraintManager.ActiveConstraints)
        {
            if (!constraint.IsEnabled || constraint.LeftPointAliases.Count < 2) continue;

            string point1 = constraint.LeftPointAliases[0];
            string point2 = constraint.LeftPointAliases[1];

            // �|�C���g������Ή�����u���b�N��MatchCode���t��������
            string block1 = GetBlockCodeFromPoint(point1);
            string block2 = GetBlockCodeFromPoint(point2);

            // �����̃u���b�N�����݂���ꍇ�A�����𓯂��O���t�ɓ�������
            if (!string.IsNullOrEmpty(block1) && !string.IsNullOrEmpty(block2) && parentMap.ContainsKey(block1) && parentMap.ContainsKey(block2))
            {
                Union(block1, block2);
            }
        }

        // 3. �Ɨ������e�W���ɑ΂��āA�A���������l�� Group ID �����蓖�Ă�
        Dictionary<string, int> rootToGroupId = new Dictionary<string, int>();
        int nextGroupId = 1;

        foreach (var block in allBlocks)
        {
            string root = Find(block.MatchCode);
            if (!rootToGroupId.ContainsKey(root))
            {
                rootToGroupId[root] = nextGroupId++;
            }

            block.AssemblyGroup = rootToGroupId[root];
        }

        // 4. ���� Group ���� AssemblyOrder �������I�Ɉ�v������ (�O���[�v���̍ŏ������l��K�p����)
        var groupedBlocks = allBlocks.GroupBy(b => b.AssemblyGroup);
        foreach (var group in groupedBlocks)
        {
            int minOrder = group.Min(b => b.AssemblyOrder);
            foreach (var block in group)
            {
                block.AssemblyOrder = minOrder;
            }
        }

        Debug.Log("<color=green>[AssemblySequence] �S���O���t�̃g�|���W�[��͂��������܂����BGroup �� Order ���Ċ��蓖�Ă���܂����B</color>");
        OnSequenceDataSynchronized?.Invoke();
    }

    /// <summary>
    /// �G�C���A�X���i�܂��͕\��ID�j����A���̃|�C���g��������u���b�N�R�[�h���擾����B
    /// </summary>
    private string GetBlockCodeFromPoint(string pointAlias)
    {
        if (constraintManager.ProjectData == null) return "";

        // ProjectData ����|�C���g�f�[�^���������A�����u���b�N��Ԃ�
        foreach (var p in constraintManager.ProjectData.Points.Values)
        {
            if (p.DisplayID == pointAlias || p.Name == pointAlias) return p.Block;
        }
        return "";
    }
}
```

### File: `Scripts\Features\BlockOrganizer.cs`
```csharp
﻿// ===============================================
// BlockOrganizer.cs
// PRODUCTION VERSION V4 - Enhanced Word-Boundary Regular Expression Engine
// ===============================================

using UnityEngine;
using System.Text.RegularExpressions;

/// <summary>
/// Scans the hierarchy under the 'World/' node to automatically classify 
/// game objects into structural Design and Measured blocks using advanced token boundaries.
/// </summary>
public class BlockOrganizer : MonoBehaviour
{
    [Header("Dependencies")]
    [Tooltip("Reference to the central BlockManager handling scene data tracking.")]
    public BlockManager blockManager;

    private void Start()
    {
        // Automatically trigger the hierarchy identification layer at startup [自動スキャン]
        OrganizeIntoBlocks();
    }

    /// <summary>
    /// Performs a top-down isolated scan of the 'World/' node hierarchy to rebuild block references.
    /// </summary>
    public void OrganizeIntoBlocks()
    {
        // [変更] サービスロケーター経由で取得 (利用O(1)复杂度的服务定位器)
        if (blockManager == null) ServiceLocator.TryGet(out blockManager);

        if (blockManager == null)
        {
            Debug.LogError("[BlockOrganizer] Fatal: Active BlockManager cannot be located in the current scene context.");
            return;
        }

        // Wipe obsolete runtime cache arrays to avoid layout phantom overlaps
        blockManager.AllBlocks.Clear();

        Debug.Log("[BlockOrganizer] Re-initiating automated structural scene scanning under 'World/' anchor...");

        // Isolate search scope strictly under the top-level CAD 'World/' transform branch [ノードのスコープ制限]
        GameObject worldNode = GameObject.Find("World/");

        if (worldNode != null)
        {
            foreach (Transform child in worldNode.transform)
            {
                ScanRecursively(child);
            }

            // Broadcast successful data state mutations to update synchronized UI tables
            blockManager.NotifyBlockDataUpdated();
            Debug.Log($"[BlockOrganizer] Scene scan finished. Successfully mapped {blockManager.AllBlocks.Count} top-level blocks.");
        }
        else
        {
            Debug.LogWarning("[BlockOrganizer] Aborting scan execution: A root-level GameObject named 'World/' was not detected.");
        }
    }

    /// <summary>
    /// Depth-first recursive tree traversal traversal to register top-level block bounds.
    /// </summary>
    private void ScanRecursively(Transform current)
    {
        if (current == null) return;

        if (IsTargetBlock(current.gameObject))
        {
            string blockName = current.name;
            bool isMeasured = blockName.ToUpper().Contains("MEASURED");

            // Reconstruct a unique functional hash code id based on instance transforms
            int blockID = current.gameObject.GetInstanceID();

            Block newBlock = new Block(blockID, blockName, current)
            {
                IsMeasured = isMeasured
            };

            // Register the validated block metadata profile into the central system memory layer
            blockManager.RegisterBlock(newBlock);

            // PRUNING OPTIMIZATION: Stop down-tree scanning on this branch.
            // Sub-solids are natively bundled under this block root, avoiding asset duplicate pollution.
            return;
        }

        // Continue tree iteration if the current structural layer is not a block root
        foreach (Transform child in current)
        {
            ScanRecursively(child);
        }
    }

    /// <summary>
    /// High-precision token evaluation block validator utilizing word-boundary constraints.
    /// Defends against false-positive matching of ordinary words like 'BASE', 'BOLT', etc.
    /// </summary>
    private bool IsTargetBlock(GameObject go)
    {
        if (go == null) return false;
        string upperName = go.name.ToUpper();

        // =========================================================================
        // REGEX BOUNDARY CONFIGURATION [高精度な正規表現の設計]
        // \b(OG|OB1|OC) -> Matches standard pre-existing structural tags.
        // \bB\d*\b     -> Captures isolated 'B' or 'B' with trailing numbers (e.g., '050-B', 'B4').
        //                 Strictly rejects multi-letter component tokens like 'BASE' or 'BRACKET'.
        // =========================================================================
        bool isMatch = Regex.IsMatch(upperName, @"\b(OG|OB1|OC)|\bB\d*\b");

        if (isMatch)
        {
            // NESTING DEFENSE LAYER [入れ子防御機制]: 
            // Intercept child components to ensure only the highest ancestor block root gets registered.
            Transform parent = go.transform.parent;
            while (parent != null)
            {
                if (parent.name == "World") break;

                string pName = parent.name.ToUpper();
                if (Regex.IsMatch(pName, @"\b(OG|OB1|OC)|\bB\d*\b"))
                {
                    // An ancestor has already claimed block status. Decline this internal sub-node.
                    return false;
                }
                parent = parent.parent;
            }

            return true;
        }

        return false;
    }
}
```

### File: `Scripts\Features\BlockReconstructionManager.cs`
```csharp
﻿// ===============================================
// BlockReconstructionManager.cs
// PRODUCTION VERSION V21 - Greedy Iterative Relaxation (Ultimate Corner/Edge Fix)
// ===============================================

using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;

// ==========================================
// DATA STRUCTURE
// ==========================================
public struct PointPairData
{
    public string PointName;
    public Vector3 DesignPosition;
    public Vector3 MeasurePosition;
    public Transform PointTransform;

    public PointPairData(string name, Vector3 designPos, Vector3 measurePos, Transform pointTransform)
    {
        PointName = name;
        DesignPosition = designPos;
        MeasurePosition = measurePos;
        PointTransform = pointTransform;
    }
}

public class BlockReconstructionManager : MonoBehaviour
{
    [Header("IDW Engine Settings")]
    [Tooltip("Power parameter for Inverse Distance Weighting (Smoothness)")]
    public float idwFalloff = 2.0f;

    [Tooltip("Maximum distance of influence in mm")]
    public float influenceRadius = 250.0f;

    [Header("Materials")]
    [Tooltip("Material to apply after deformation (e.g., Transparent Pink)")]
    public Material measuredMaterial;

    /// <summary>
    /// Executes the full 3D reconstruction pipeline.
    /// </summary>
    public GameObject GenerateAndDeformBlock(
        string blockName,
        GameObject originalBlock,
        List<PointPairData> deformationData,
        float exaggerationFactor = 1f,
        bool enableHeatmap = false,
        float maxTolerance = 5f)
    {
        if (originalBlock == null || deformationData == null || deformationData.Count == 0) return null;

        // --- STAGE 1: Clone and Lock ---
        GameObject instance = Instantiate(originalBlock);
        instance.SetActive(true);
        instance.name = $"{blockName}_Mea";

        string targetRootName = "3D 010 TMダンパ全体組立.nwc_Measured";
        GameObject measuredRoot = GameObject.Find(targetRootName);

        if (measuredRoot == null)
        {
            measuredRoot = new GameObject(targetRootName);
            GameObject worldNode = GameObject.Find("World");
            if (worldNode != null)
            {
                measuredRoot.transform.SetParent(worldNode.transform, false);
            }

            if (originalBlock.transform.parent != null)
            {
                Transform originalParent = originalBlock.transform.parent;
                measuredRoot.transform.position = originalParent.position;
                measuredRoot.transform.rotation = originalParent.rotation;
                measuredRoot.transform.localScale = originalParent.localScale;
            }
        }

        instance.transform.SetParent(measuredRoot.transform, false);
        instance.transform.localPosition = originalBlock.transform.localPosition;
        instance.transform.localRotation = originalBlock.transform.localRotation;
        instance.transform.localScale = originalBlock.transform.localScale;

        List<Vector3> designLocalPts = new List<Vector3>();
        List<Vector3> measuredLocalPts = new List<Vector3>();

        foreach (var data in deformationData)
        {
            designLocalPts.Add(data.DesignPosition);
            measuredLocalPts.Add(data.MeasurePosition);
        }

        // --- STAGE 2: Kabsch Alignment ---
        MeshFilter meshFilter = instance.GetComponent<MeshFilter>();
        if (meshFilter != null && meshFilter.sharedMesh != null)
        {
            Mesh instancedMesh = Instantiate(meshFilter.sharedMesh);
            instancedMesh.name = $"{meshFilter.sharedMesh.name}_Deformed";

            Matrix4x4 alignmentMatrix = DeformationMathCore.CalculateBestFitTransform(designLocalPts, measuredLocalPts);

            Vector3[] vertices = instancedMesh.vertices;
            List<Vector3> alignedDesignPts = new List<Vector3>(designLocalPts.Count);

            for (int i = 0; i < vertices.Length; i++)
            {
                vertices[i] = alignmentMatrix.MultiplyPoint3x4(vertices[i]);
            }
            for (int i = 0; i < designLocalPts.Count; i++)
            {
                alignedDesignPts.Add(alignmentMatrix.MultiplyPoint3x4(designLocalPts[i]));
            }

            instancedMesh.vertices = vertices;

            // --- STAGE 3: Localized Exact Interpolation (IDW) ---
            MeshDeformationEngine.DeformMesh(
                instancedMesh,
                alignedDesignPts,
                measuredLocalPts,
                idwFalloff,
                influenceRadius,
                exaggerationFactor,
                enableHeatmap,
                maxTolerance
            );

            meshFilter.sharedMesh = instancedMesh;
            MeshCollider collider = instance.GetComponent<MeshCollider>();
            if (collider != null) collider.sharedMesh = instancedMesh;

            // ========================================================
            // STAGE 4: GREEDY ITERATIVE RELAXATION (V21 ROBUST FIX)
            // Completely solves multi-face corner/edge embedding.
            // ========================================================
            Vector3[] defVerts = instancedMesh.vertices;
            Vector3[] defNormals = instancedMesh.normals;
            int[] defTris = instancedMesh.triangles;

            // Convert to World Space to completely immunize against CAD transform scales
            Vector3[] worldVerts = new Vector3[defVerts.Length];
            for (int v = 0; v < defVerts.Length; v++)
            {
                worldVerts[v] = instance.transform.TransformPoint(defVerts[v]);
            }
            Vector3[] worldNormals = new Vector3[defNormals.Length];
            for (int v = 0; v < defNormals.Length; v++)
            {
                worldNormals[v] = instance.transform.TransformDirection(defNormals[v]).normalized;
            }

            float visualRadius = 15.0f; // Exact sphere radius to prevent embedding

            for (int i = 0; i < deformationData.Count; i++)
            {
                Transform ptTransform = deformationData[i].PointTransform;
                if (ptTransform == null) continue;

                Vector3 residualDelta = measuredLocalPts[i] - alignedDesignPts[i];
                Vector3 theoreticalLocalPos = alignedDesignPts[i] + (residualDelta * exaggerationFactor);
                Vector3 theoreticalWorldPos = instance.transform.TransformPoint(theoreticalLocalPos);

                // --- STEP 1: Find Initial Surface Anchor ---
                Vector3 anchorWorldPoint = Vector3.zero;
                float minDistAnchorSq = float.MaxValue;
                int anchorIdx1 = 0, anchorIdx2 = 0, anchorIdx3 = 0;

                for (int t = 0; t < defTris.Length; t += 3)
                {
                    int idx1 = defTris[t], idx2 = defTris[t + 1], idx3 = defTris[t + 2];
                    Vector3 closestOnTri = ClosestPointOnTriangle(theoreticalWorldPos, worldVerts[idx1], worldVerts[idx2], worldVerts[idx3]);
                    float distSq = (theoreticalWorldPos - closestOnTri).sqrMagnitude;

                    if (distSq < minDistAnchorSq)
                    {
                        minDistAnchorSq = distSq;
                        anchorWorldPoint = closestOnTri;
                        anchorIdx1 = idx1; anchorIdx2 = idx2; anchorIdx3 = idx3;
                    }
                }

                Vector3 anchorWorldNormal = (worldNormals[anchorIdx1] + worldNormals[anchorIdx2] + worldNormals[anchorIdx3]).normalized;
                if (anchorWorldNormal.sqrMagnitude < 0.001f) anchorWorldNormal = Vector3.up;

                // Set initial position pushed out from the primary face
                Vector3 sphereCenter = anchorWorldPoint + anchorWorldNormal * visualRadius;

                // --- STEP 2: Multi-Pass Greedy Penetration Resolution ---
                // Iteratively push the sphere out of the absolute deepest penetration until clear.
                int maxIterations = 10;
                for (int iter = 0; iter < maxIterations; iter++)
                {
                    Vector3 deepestPenetrationPoint = Vector3.zero;
                    float minCenterDistSq = float.MaxValue;
                    bool isPenetrating = false;

                    // Find the single closest geometric point to the CURRENT sphere center
                    for (int t = 0; t < defTris.Length; t += 3)
                    {
                        Vector3 v1 = worldVerts[defTris[t]], v2 = worldVerts[defTris[t + 1]], v3 = worldVerts[defTris[t + 2]];

                        // Ultra-fast AABB culling
                        float cx = sphereCenter.x, cy = sphereCenter.y, cz = sphereCenter.z;
                        if (cx < Mathf.Min(v1.x, Mathf.Min(v2.x, v3.x)) - visualRadius || cx > Mathf.Max(v1.x, Mathf.Max(v2.x, v3.x)) + visualRadius ||
                            cy < Mathf.Min(v1.y, Mathf.Min(v2.y, v3.y)) - visualRadius || cy > Mathf.Max(v1.y, Mathf.Max(v2.y, v3.y)) + visualRadius ||
                            cz < Mathf.Min(v1.z, Mathf.Min(v2.z, v3.z)) - visualRadius || cz > Mathf.Max(v1.z, Mathf.Max(v2.z, v3.z)) + visualRadius)
                        {
                            continue;
                        }

                        Vector3 closestOnTri = ClosestPointOnTriangle(sphereCenter, v1, v2, v3);
                        float dSq = (sphereCenter - closestOnTri).sqrMagnitude;

                        // Track the absolute closest geometry to the center
                        if (dSq < minCenterDistSq)
                        {
                            minCenterDistSq = dSq;
                            deepestPenetrationPoint = closestOnTri;
                        }
                    }

                    // If the closest point is inside the sphere's radius, we are clipping into a corner/edge!
                    if (minCenterDistSq < (visualRadius * visualRadius) - 0.01f)
                    {
                        isPenetrating = true;
                        float currentDist = Mathf.Sqrt(minCenterDistSq);
                        Vector3 pushDirection;

                        if (currentDist > 0.001f)
                        {
                            // Push away from the penetrating geometry
                            pushDirection = (sphereCenter - deepestPenetrationPoint) / currentDist;
                        }
                        else
                        {
                            // Failsafe: if exactly on geometry, push along the initial anchor normal
                            pushDirection = anchorWorldNormal;
                        }

                        // Resolve this specific penetration, plus a tiny 0.05mm buffer to prevent infinite micro-loops
                        float penetrationDepth = visualRadius - currentDist;
                        sphereCenter += pushDirection * (penetrationDepth + 0.05f);
                    }

                    // If no penetration was found in this pass, the sphere is perfectly safe! Break early.
                    if (!isPenetrating) break;
                }

                // --- STAGE 5: The Ultimate NaN & Infinity Guard ---
                if (float.IsNaN(sphereCenter.x) || float.IsInfinity(sphereCenter.x) ||
                    float.IsNaN(sphereCenter.y) || float.IsInfinity(sphereCenter.y) ||
                    float.IsNaN(sphereCenter.z) || float.IsInfinity(sphereCenter.z))
                {
                    Debug.LogError($"[Reconstruction] Infinity/NaN prevented for point {deformationData[i].PointName}! Reverting to safe anchor.");
                    sphereCenter = anchorWorldPoint + Vector3.up * visualRadius;
                }

                ptTransform.position = sphereCenter;

                SphereCollider col = ptTransform.GetComponent<SphereCollider>();
                if (col != null) col.radius = Mathf.Max(col.radius, 15f);
            }

            // --- STAGE 6: Apply Materials ---
            if (measuredMaterial != null)
            {
                Renderer rend = instance.GetComponent<Renderer>();
                if (rend != null)
                {
                    rend.sharedMaterial = measuredMaterial;
                    MaterialPropertyBlock mpb = new MaterialPropertyBlock();
                    rend.GetPropertyBlock(mpb);
                    mpb.SetFloat("_EnableHeatmap", enableHeatmap ? 1.0f : 0.0f);
                    rend.SetPropertyBlock(mpb);
                }
            }
        }

        return instance;
    }

    // ========================================================
    // MATHEMATICAL CORE: Ericson's Real-Time Triangle Projection
    // ========================================================
    private static Vector3 ClosestPointOnTriangle(Vector3 p, Vector3 a, Vector3 b, Vector3 c)
    {
        Vector3 ab = b - a;
        Vector3 ac = c - a;
        Vector3 ap = p - a;

        float d1 = Vector3.Dot(ab, ap);
        float d2 = Vector3.Dot(ac, ap);
        if (d1 <= 0f && d2 <= 0f) return a;

        Vector3 bp = p - b;
        float d3 = Vector3.Dot(ab, bp);
        float d4 = Vector3.Dot(ac, bp);
        if (d3 >= 0f && d4 <= d3) return b;

        float vc = d1 * d4 - d3 * d2;
        if (vc <= 0f && d1 >= 0f && d3 <= 0f)
        {
            float v = d1 / (d1 - d3);
            return a + v * ab;
        }

        Vector3 cp = p - c;
        float d5 = Vector3.Dot(ab, cp);
        float d6 = Vector3.Dot(ac, cp);
        if (d6 >= 0f && d5 <= d6) return c;

        float vb = d5 * d2 - d1 * d6;
        if (vb <= 0f && d2 >= 0f && d6 <= 0f)
        {
            float w = d2 / (d2 - d6);
            return a + w * ac;
        }

        float va = d3 * d6 - d5 * d4;
        if (va <= 0f && (d4 - d3) >= 0f && (d5 - d6) >= 0f)
        {
            float w = (d4 - d3) / ((d4 - d3) + (d5 - d6));
            return b + w * (c - b);
        }

        float areaSum = va + vb + vc;
        if (Mathf.Abs(areaSum) < 1e-8f) return a;

        float denom = 1f / areaSum;
        float vNorm = vb * denom;
        float wNorm = vc * denom;
        return a + ab * vNorm + ac * wNorm;
    }
}
```

### File: `Scripts\Features\ClearanceManager.cs`
```csharp
﻿// ===============================================
// ClearanceManager.cs
// PRODUCTION VERSION V12 - Fully Consolidated & Optimized X-Ray Callouts
// ===============================================

using System;
using System.Collections.Generic;
using UnityEngine;
using TMPro;

/// <summary>
/// Manages industrial-grade clearance inspection loops. Pairs corresponding cross-block 
/// reference points, calculates spatial deviations, and renders interactive high-visibility X-Ray indicators.
/// </summary>
public class ClearanceManager : MonoBehaviour
{
    // Global event to notify all UI components and data providers that clearance calculations have refreshed
    public static event Action<List<Point>> OnClearanceUpdated;

    [Header("=== Connection Line Settings ===")]
    [Tooltip("Thickness of the absolute connection line. Rendered in World Space.")]
    public float lineWidth = 3f;
    [Tooltip("The signature color of the structural gap line.")]
    public Color lineColor = Color.cyan;

    [Header("=== Floating Label Settings ===")]
    [Tooltip("Vertical height shift above the absolute physical midpoint (mm).")]
    public float labelVerticalOffset = 30f;
    [Tooltip("Distance the text is pulled towards the Camera view plane to prevent clipping inside structural gaps (mm).")]
    public float pullTowardsCameraDistance = 60f;
    [Tooltip("Scale factor for the 3D text. Adjust based on the structural size of the CAD block.")]
    public float labelFontSize = 120f;
    [Tooltip("High-contrast text color recommendation: Yellow matches optimally against Cyan and Industrial Blue.")]
    public Color labelColor = Color.yellow;

    // ==========================================
    // [NEW] 追加: オブジェクトプール (Object Pool)
    // ==========================================
    private List<GameObject> activeClearanceLines = new List<GameObject>();
    private Queue<GameObject> clearanceLinePool = new Queue<GameObject>();
    private Dictionary<string, float> tieIdToRootGap = new Dictionary<string, float>();

    /// <summary>
    /// CORE ENTRY POINT: Filters measured reference points, executes cross-block dynamic pairing, 
    /// draws透視絶対接続(X-Ray Lines), and updates global UI registers.
    /// </summary>
    /// <param name="allPoints">The unpurified global point list injected from core memory.</param>
    public void GenerateClearanceVisuals(List<Point> allPoints)
    {
        ClearVisuals(); // [修正] Destroyではなく、プールに返却(非アクティブ化)する
        tieIdToRootGap.Clear();

        if (allPoints == null || allPoints.Count == 0) return;

        // STAGE 1: Data Isolation and Tokenization 
        Dictionary<string, List<Point>> groupedPoints = new Dictionary<string, List<Point>>();
        foreach (var p in allPoints)
        {
            if (p == null) continue;

            // 1. Core Constraint: Only Measured Points (GroupID == 1) have valid physical locations post-displacement
            if (p.GroupID != 1) continue;

            // 2. Core Constraint: Isolate functional reference markers, ignore geometric structural data
            if (p.PointType?.Trim() != "Reference") continue;

            // 3. Validation: Evict corrupted or unassigned tracking identities
            if (string.IsNullOrEmpty(p.TieID) || p.TieID == "N/A") continue;

            string key = $"{p.Joint?.Trim()}_{p.TieID?.Trim()}";

            if (!groupedPoints.ContainsKey(key))
                groupedPoints[key] = new List<Point>();

            groupedPoints[key].Add(p);
        }

        // STAGE 2: Combinatorial Evaluation & Topology Matching 
        foreach (var kvp in groupedPoints)
        {
            List<Point> points = kvp.Value;
            Point p1 = null;
            Point p2 = null;

            // Double loop checks all internal variants within the token group to find a cross-block pair
            for (int i = 0; i < points.Count; i++)
            {
                for (int j = i + 1; j < points.Count; j++)
                {
                    if (points[i].Block != points[j].Block)
                    {
                        p1 = points[i];
                        p2 = points[j];
                        break;
                    }
                }
                if (p1 != null) break; // Pair successfully established. Escape early.
            }

            // STAGE 3: Metric Calculation & Visual Injection
            if (p1 != null && p2 != null)
            {
                float gap = Vector3.Distance(p1.MeasurePosition, p2.MeasurePosition);
                tieIdToRootGap[p1.TieID.Trim()] = gap;

                CreateXRayConnection(p1.MeasurePosition, p2.MeasurePosition, gap, kvp.Key);
            }
        }

        // STAGE 4: Cascade Broadcast Link 
        OnClearanceUpdated?.Invoke(allPoints);
    }

    /// <summary>
    /// Generates the decoupled 3D geometric primitives and TextMeshPro instances safely encapsulated under a master group.
    /// </summary>
    private void CreateXRayConnection(Vector3 start, Vector3 end, float gapDistance, string key)
    {
        GameObject visualGroup;
        LineRenderer lr;
        TextMeshPro tmp;
        GameObject textObj;

        // [修正] プールから取得するか、新規作成する (从对象池获取或新建)
        if (clearanceLinePool.Count > 0)
        {
            visualGroup = clearanceLinePool.Dequeue();
            visualGroup.name = $"ClearanceConnection_{key}";
            visualGroup.SetActive(true);

            lr = visualGroup.GetComponentInChildren<LineRenderer>();
            textObj = visualGroup.transform.Find("ClearanceLabel").gameObject;
            tmp = textObj.GetComponent<TextMeshPro>();
        }
        else
        {
            visualGroup = new GameObject($"ClearanceConnection_{key}");
            visualGroup.transform.SetParent(this.transform);

            GameObject lineObj = new GameObject("AbsoluteLine");
            lineObj.transform.SetParent(visualGroup.transform);
            lr = lineObj.AddComponent<LineRenderer>();
            Material xRayMat = new Material(Shader.Find("Sprites/Default"));
            xRayMat.color = lineColor;
            lr.material = xRayMat;

            textObj = new GameObject("ClearanceLabel");
            textObj.transform.SetParent(visualGroup.transform);
            tmp = textObj.AddComponent<TextMeshPro>();
            textObj.AddComponent<ClearanceLabelFacer>();
        }

        activeClearanceLines.Add(visualGroup);

        // --- SUB-PASS A: Update Line Renderer ---
        lr.startWidth = lineWidth;
        lr.endWidth = lineWidth;
        lr.positionCount = 2;
        lr.SetPosition(0, start);
        lr.SetPosition(1, end);
        lr.useWorldSpace = true;

        // --- SUB-PASS B & C: Position & Text Update ---
        Vector3 exactMidpoint = (start + end) / 2f;
        Vector3 textPosition = exactMidpoint + new Vector3(0f, labelVerticalOffset, 0f);

        Camera mainCam = Camera.main;
        if (mainCam != null)
        {
            Vector3 dirToCamera = (mainCam.transform.position - textPosition).normalized;
            textPosition += dirToCamera * pullTowardsCameraDistance;
        }

        textObj.transform.position = textPosition;
        tmp.text = $"Δ {gapDistance:F3}";
        tmp.color = labelColor;
        tmp.fontSize = labelFontSize;
        tmp.alignment = TextAlignmentOptions.Center;
        tmp.fontStyle = FontStyles.Bold;
    }

    /// <summary>
    /// Public query API for downstream UI tables and PointInfo hover managers.
    /// </summary>
    public float GetRootGap(string tieID)
    {
        if (string.IsNullOrEmpty(tieID)) return 0f;
        string cleanID = tieID.Trim();
        return tieIdToRootGap.TryGetValue(cleanID, out float gap) ? gap : 0f;
    }

    /// <summary>
    /// Explicitly cleans up scene assets to avoid frame-over-frame memory leaks.
    /// </summary>
    private void ClearVisuals()
    {
        // [修正] オブジェクトを破壊せず、非アクティブにしてプールに戻す
        foreach (var obj in activeClearanceLines)
        {
            if (obj != null)
            {
                obj.SetActive(false);
                clearanceLinePool.Enqueue(obj);
            }
        }
        activeClearanceLines.Clear();
    }
}

// ========================================================
// REUSABLE SUB-COMPONENT: Dynamic Billboard Facing Engine
// ========================================================
public class ClearanceLabelFacer : MonoBehaviour
{
    private Camera cam;

    private void Start()
    {
        cam = Camera.main;
    }

    private void LateUpdate()
    {
        if (cam != null)
        {
            // Lock the local transform forward axis exactly to the main view matrix orientation
            transform.forward = cam.transform.forward;
        }
    }
}
```

### File: `Scripts\Features\ConstraintDefinitions.cs`
```csharp
﻿// ===============================================
// ConstraintDefinitions.cs
// PRODUCTION VERSION - Global Axis & Decoupled Tools
// ===============================================

using System.Collections.Generic;


public enum ConstraintType
{
    Fixed, Coordinate, Distance, EqualClearance
}


public enum ConstraintAxis
{
    X, Y, Z
}

public enum RelationalOperator
{
    Equal,          // =
    GreaterOrEqual, // >=
    LessOrEqual     // <=
}

[System.Serializable]
public class ConstraintData
{
    public ConstraintType Type;
    public ConstraintAxis Axis = ConstraintAxis.X; 
    public bool IsEnabled = true;

    // --- Left Side ---
    public List<string> LeftPointAliases = new List<string>();

    // --- Operator  ---
    public RelationalOperator Operator = RelationalOperator.Equal;

    // --- Right Side ---
    public bool IsRightSideEquation = false;
    public List<string> RightPointAliases = new List<string>();
    public float RightConstant = 0f;

    public ConstraintData() { }

    
    private string GetAxisSuffix()
    {
        return Axis == ConstraintAxis.X ? "_x" : (Axis == ConstraintAxis.Y ? "_y" : "_z");
    }

    public string GetLeftEquationString()
    {
        if (LeftPointAliases.Count == 0) return "Invalid";

        string suffix = GetAxisSuffix();

        // 座標拘束
        if (Type == ConstraintType.Coordinate) return $"{LeftPointAliases[0]}{suffix}";

        // (ブロッククリアランス & 均等クリアランス)
        if (LeftPointAliases.Count >= 2)
            return $"| {LeftPointAliases[0]}{suffix} - {LeftPointAliases[1]}{suffix} |";

        return "Invalid";
    }

    public string GetRightEquationString()
    {
        if (IsRightSideEquation && RightPointAliases.Count >= 2)
            return $"| {RightPointAliases[0]}{GetAxisSuffix()} - {RightPointAliases[1]}{GetAxisSuffix()} |";

        return RightConstant.ToString("F3");
    }
}
```

### File: `Scripts\Features\ConstraintExecutor.cs`
```csharp
﻿// ===============================================
// ConstraintExecutor.cs
// PRODUCTION VERSION - Complete Execution Engine
// ===============================================
using System; // <--- 🚨 ここにこれを追加してください
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// This class acts as the execution engine. It gathers purely mathematical data 
/// from the Point classes, feeds it into the RPSSolverMiddleware, and applies 
/// the calculated shift vectors to the 3D GameObjects.
/// </summary>
public class ConstraintExecutor : MonoBehaviour
{
    [Header("Core Dependencies")]
    [Tooltip("Reference to the manager holding active constraints.")]
    public ConstraintManager constraintManager;

    [Tooltip("Reference to the creator holding the local joint coordinate systems.")]
    public JoiningCoordinateSystemCreator jointCreator;

    [Header("Execution Settings")]
    [Tooltip("If true, the executor will attempt to find dependencies automatically on Start.")]
    public bool autoBindDependencies = true;

    // [NEW] 追加: 拘束計算が完了したことをUIに通知するイベント
    public event Action OnExecutionCompleted;

    private void Start()
    {
        if (autoBindDependencies)
        {
            // [変更] ServiceLocatorを使用してコアサービスを取得 (使用ServiceLocator获取核心服务，避免Find的性能开销)
            if (constraintManager == null) ServiceLocator.TryGet(out constraintManager);
            if (jointCreator == null) ServiceLocator.TryGet(out jointCreator);
        }
    }

    /// <summary>
    /// MAIN ENTRY POINT: Executes the solver and applies physical movements.
    /// </summary>
    public void ExecuteAssemblyConstraints()
    {
        if (!ValidatePrerequisites()) return;

        // 1. Extract Joint Base (R, t)
        JointTransformData primaryJointData = jointCreator.ExtractedJointData[0];

        // ==========================================
        // [CRITICAL FIX] Mathematical Robustness Upgrade
        // We do NOT use EulerAngles or a single NormalVector here.
        // A single vector loses 1 degree of freedom (roll around the axis).
        // Instead, we extract the exact absolute Quaternion directly from the 
        // orthogonal RotationMatrix we built in the Creator script.
        // ==========================================
        Matrix4x4 jointLocalToWorld = Matrix4x4.TRS(
            primaryJointData.Translation,
            primaryJointData.RotationMatrix.rotation, // Safely extracts full 3D orientation
            Vector3.one
        );

        // 2. Trace the Base Block
        string jointOriginDesignPointName = primaryJointData.PointName;
        string anchorBlockName = "";
        Dictionary<string, string> aliasToNameMap = new Dictionary<string, string>();

        foreach (var kvp in constraintManager.ProjectData.Points)
        {
            Point pt = kvp.Value;

            // Find which Block owns the Design Joint Origin
            if (pt.Name == jointOriginDesignPointName && pt.GroupID == 0)
            {
                anchorBlockName = pt.Block;
            }

            // Map 5-digit Aliases to actual Point Names for the Solver
            if (pt.GroupID == 1)
            {
                string alias = !string.IsNullOrEmpty(pt.DisplayID) ? pt.DisplayID : pt.ID.ToString().Substring(0, 5);
                aliasToNameMap[alias] = pt.Name;
            }
        }

        // 3. Gather Scene Data
        List<PointPairData> originalPairs = GatherSceneData(out Dictionary<string, string> pointToBlockMap, out Dictionary<string, Transform> blockTransforms);

        if (originalPairs.Count == 0)
        {
            Debug.LogWarning("[ConstraintExecutor] No measured points found to execute constraints.");
            return;
        }

        // 4. Pass data to Middleware for mathematical solving
        List<PointPairData> solvedPairs = RPSSolverMiddleware.ApplyRPSConstraints(
            originalPairs,
            constraintManager.ActiveConstraints,
            jointLocalToWorld,
            pointToBlockMap,
            anchorBlockName,
            aliasToNameMap
        );

        // 5. Apply results to physical GameObjects
        ApplyCalculatedShifts(originalPairs, solvedPairs, pointToBlockMap, blockTransforms);

        // 6. Trigger UI Refresh safely outside the scope
        // [変更] サービスロケーターからの取得に置換 (利用TryGet平滑替换)
        if (ServiceLocator.TryGet<BlockOrganizer>(out var organizer))
        {
            organizer.OrganizeIntoBlocks();
        }

        // ==========================================
        // [NEW] 7. Clearance 
        // ==========================================
        // [変更] サービスロケーターからの取得に置換
        if (ServiceLocator.TryGet<PointCSVLoader>(out var loader))
        {
            List<Point> allPoints = new List<Point>(loader.GetDesignPoints());
            allPoints.AddRange(loader.GetMeasuredPoints());

            if (ServiceLocator.TryGet<ClearanceManager>(out var cManager))
            {
                cManager.GenerateClearanceVisuals(allPoints);
                Debug.Log("<color=cyan>[ConstraintExecutor] Clearance UI updated based on new shifted positions.</color>");
            }
        }

        Debug.Log("<color=green>[ConstraintExecutor] Assembly Execution Completed Successfully!</color>");

        // [NEW] 追加: 計算完了をブロードキャストし、UIテーブルの実測値（折りたたみ）を展開させる
        OnExecutionCompleted?.Invoke();

    }

    /// <summary>
    /// Gathers all Measured Points and maps them to their respective 3D Block GameObjects.
    /// STRICTLY prevents Design Blocks from being included in the physical shift.
    /// </summary>
    private List<PointPairData> GatherSceneData(out Dictionary<string, string> pointToBlockMap, out Dictionary<string, Transform> blockTransforms)
    {
        List<PointPairData> pairs = new List<PointPairData>();
        pointToBlockMap = new Dictionary<string, string>();
        blockTransforms = new Dictionary<string, Transform>();

        if (constraintManager == null || constraintManager.ProjectData == null) return pairs;

        foreach (var kvp in constraintManager.ProjectData.Points)
        {
            Point pt = kvp.Value;

            // Only process Measured points (GroupID = 1) for constraints
            if (pt.GroupID == 1)
            {
                string alias = !string.IsNullOrEmpty(pt.DisplayID) ? pt.DisplayID : pt.ID.ToString().Substring(0, 5);

                PointPairData data = new PointPairData
                {
                    PointName = pt.Name,
                    MeasurePosition = pt.MeasurePosition
                };
                pairs.Add(data);

                if (!string.IsNullOrEmpty(pt.Block))
                {
                    pointToBlockMap[pt.Name] = pt.Block;

                    if (!blockTransforms.ContainsKey(pt.Block))
                    {
                        GameObject measuredBlockObj = null;
                        string expectedMeasuredName = pt.Block + "_Measured_Reconstructed";
                        measuredBlockObj = GameObject.Find(expectedMeasuredName);

                        if (measuredBlockObj == null)
                        {
                            // [変更] サービスロケーター経由でBlockManagerを取得
                            if (ServiceLocator.TryGet<BlockManager>(out var bm))
                            {
                                foreach (var b in bm.AllBlocks)
                                {
                                    if (b.IsMeasured && b.MatchCode == pt.Block.ToUpper())
                                    {
                                        measuredBlockObj = b.BlockRoot.gameObject;
                                        break;
                                    }
                                }
                            }
                        }

                        if (measuredBlockObj != null)
                        {
                            blockTransforms[pt.Block] = measuredBlockObj.transform;
                        }
                        else
                        {
                            Debug.LogWarning($"[ConstraintExecutor] Measured Mesh for '{pt.Block}' not found. Design Block is protected; applying mathematical shift to Point data only.");
                        }
                    }
                }
            }
        }
        return pairs;
    }

    /// <summary>
    /// Applies the computed shift deltas to both the 3D Meshes and the underlying Point Data.
    /// </summary>
    private void ApplyCalculatedShifts(List<PointPairData> original, List<PointPairData> solved, Dictionary<string, string> pointToBlockMap, Dictionary<string, Transform> blockTransforms)
    {
        HashSet<string> processedBlocks = new HashSet<string>();
        bool pointsMoved = false;

        for (int i = 0; i < original.Count; i++)
        {
            if (!pointToBlockMap.ContainsKey(original[i].PointName)) continue;

            string blockName = pointToBlockMap[original[i].PointName];

            // Prevent shifting the same block multiple times
            if (processedBlocks.Contains(blockName)) continue;

            // Calculate the required physical shift
            Vector3 shiftDelta = solved[i].MeasurePosition - original[i].MeasurePosition;

            if (shiftDelta.sqrMagnitude > 1e-6f)
            {
                // 1. Physically move the 3D CAD Mesh
                if (blockTransforms.TryGetValue(blockName, out Transform blockTransform))
                {
                    blockTransform.position += shiftDelta;
                    Debug.Log($"<color=magenta>[ConstraintExecutor] Block '{blockName}' physically shifted by vector: {shiftDelta.ToString("F4")}</color>");
                }

                // 2. Update the underlying ProjectData to reflect the new coordinates
                foreach (var kvp in constraintManager.ProjectData.Points)
                {
                    if (kvp.Value.GroupID == 1 && kvp.Value.Block == blockName)
                    {
                        kvp.Value.MeasurePosition += shiftDelta;
                    }
                }
                pointsMoved = true;
            }

            processedBlocks.Add(blockName);
        }

        // 3. Refresh the rendered spheres (PointRenderer) so they match the new positions
        if (pointsMoved)
        {
            // A. Refresh physical spheres to their new optimized coordinates
            // [変更] サービスロケーター経由でPointRendererとClearanceManagerを取得
            if (ServiceLocator.TryGet<PointRenderer>(out var renderer))
            {
                renderer.RefreshAllPoints();
            }

            // B. Auto-trigger Clearance Manager to recalculate and redraw all X-Ray lines and Delta text labels based on the NEW positions
            if (ServiceLocator.TryGet<ClearanceManager>(out var clearanceManager) && constraintManager.ProjectData != null)
            {
                // Pass the fresh runtime dictionary points into the visual generator
                clearanceManager.GenerateClearanceVisuals(new List<Point>(constraintManager.ProjectData.Points.Values));
                Debug.Log("<color=cyan>[ConstraintExecutor] Auto-triggered Clearance Manager to redraw X-Ray lines and update labels.</color>");
            }
        }

        Debug.Log("<color=green>[ConstraintExecutor] Assembly Execution Completed Successfully!</color>");
    }

    /// <summary>
    /// Ensures all required data exists before attempting execution.
    /// </summary>
    private bool ValidatePrerequisites()
    {
        if (constraintManager == null || jointCreator == null)
        {
            Debug.LogError("[ConstraintExecutor] Missing critical dependencies.");
            return false;
        }

        if (constraintManager.ActiveConstraints == null || constraintManager.ActiveConstraints.Count == 0)
        {
            Debug.LogWarning("[ConstraintExecutor] No active constraints to apply.");
            return false;
        }

        if (jointCreator.ExtractedJointData == null || jointCreator.ExtractedJointData.Count == 0)
        {
            Debug.LogError("[ConstraintExecutor] No Joint Coordinate System extracted. Please create a joint first.");
            return false;
        }

        return true;
    }
}
```

### File: `Scripts\Features\ConstraintManager.cs`
```csharp
﻿// ===============================================
// ConstraintManager.cs 
// PRODUCTION VERSION - Advanced UX Prompts & Row Deletion
// ===============================================

using System;
using System.Collections.Generic;
using UnityEngine;

// [追加] 実行順序の引き上げ
[DefaultExecutionOrder(-90)]
public class ConstraintManager : MonoBehaviour
{
    [Header("Dependencies")]
    [SerializeField] private PointRenderer pointRenderer;
    public JoiningCoordinateSystemCreator jointCreator;
    public ProjectData ProjectData;
    public ConstraintAxis GlobalAxis { get; private set; } = ConstraintAxis.X;

    public event Action<string> OnStatePromptChanged;
    public event Action OnConstraintAdded; // Used to refresh the UI table

    public bool IsConstraintInputMode { get; private set; } = false;
    private ConstraintType currentActiveTool;

    private List<string> collectedIDs = new List<string>();
    private List<ConstraintData> activeConstraints = new List<ConstraintData>();
    public IReadOnlyList<ConstraintData> ActiveConstraints => activeConstraints;

    // Smart Input State
    private ConstraintRowUI activeSmartInputRow = null;
    private List<string> rightSideBuffer = new List<string>();

    private void Awake()
    {
        // [追加] サービスとして登録
        ServiceLocator.Register<ConstraintManager>(this);
    }

    private void Start()
    {
        // [変更] サービスロケーター経由で取得し、パフォーマンスを改善
        if (jointCreator == null) ServiceLocator.TryGet(out jointCreator);
        if (ProjectData == null) ServiceLocator.TryGet(out ProjectData);
    }

    private void OnDestroy()
    {
        ServiceLocator.Unregister<ConstraintManager>();
    }

    public void ActivateConstraintTool(ConstraintType toolType)
    {
        IsConstraintInputMode = true;
        currentActiveTool = toolType;
        ClearBuffers();
        ClearActiveSmartInputRow();

        // [UX UPDATE]: Clear instructions based on tool type
        int requiredPoints = (toolType == ConstraintType.Coordinate) ? 1 : 2;
        OnStatePromptChanged?.Invoke($"[{toolType}] Tool ACTIVE. Click {requiredPoints} point(s) in 3D to set LHS (左辺).");
    }

    public void SetActiveSmartInputRow(ConstraintRowUI row)
    {
        activeSmartInputRow = row;
        rightSideBuffer.Clear();

        // [UX UPDATE]: Clear instructions for Smart Input
        OnStatePromptChanged?.Invoke("Smart Input ACTIVE: Click 2 points in 3D to measure RHS (右辺) value.");
    }

    public void ClearActiveSmartInputRow()
    {
        activeSmartInputRow = null;
        rightSideBuffer.Clear();
    }

    public void CancelCurrentTool()
    {
        IsConstraintInputMode = false;
        ClearBuffers();
        ClearActiveSmartInputRow();

        // [UX UPDATE]: Guidance for default state
        OnStatePromptChanged?.Invoke("Ready. Select a Constraint Tool (拘束ツール) or setup Joint System.");
    }

    public void SetGlobalAxis(ConstraintAxis newAxis)
    {
        GlobalAxis = newAxis;
        OnStatePromptChanged?.Invoke($"Global Axis Set: {GlobalAxis}-Axis. Continue clicking to add rows.");
    }

    // ==========================================
    // [NEW CORE FEATURE]: Delete a specific constraint row (行の削除)
    // ==========================================
    public void RemoveConstraint(ConstraintData data)
    {
        if (activeConstraints.Contains(data))
        {
            activeConstraints.Remove(data);
            OnConstraintAdded?.Invoke(); // Triggers UI to rebuild the table
            OnStatePromptChanged?.Invoke("Constraint row deleted. You can continue current operations.");
        }
    }

    public void RegisterPointForConstraint(Point clickedPoint)
    {
        if (!IsConstraintInputMode || clickedPoint == null || clickedPoint.GroupID != 1) return;

        string pointID = !string.IsNullOrEmpty(clickedPoint.DisplayID) ? clickedPoint.DisplayID : clickedPoint.ID.ToString().Substring(0, 5);

        // ROUTE A: Injecting into the Right Side (右辺入力)
        if (activeSmartInputRow != null)
        {
            if (!rightSideBuffer.Contains(pointID))
            {
                rightSideBuffer.Add(pointID);

                pointRenderer?.SetPointHighlight(clickedPoint, true, Color.cyan);

                if (rightSideBuffer.Count == 2)
                {
                    activeSmartInputRow.InjectRightSidePoints(rightSideBuffer[0], rightSideBuffer[1]);
                    ClearActiveSmartInputRow();

                    // [UX UPDATE]: Guide user to next possible actions after RHS is filled
                    OnStatePromptChanged?.Invoke("RHS (右辺) injected. Adjust table, or keep clicking to add new rows.");
                }
                else
                {
                    OnStatePromptChanged?.Invoke("Smart Input: Point 1 selected. Click 1 more point.");
                }
            }
            return;
        }

        // ROUTE B: Building the Left Side (左辺構築)
        if (!collectedIDs.Contains(pointID))
        {
            collectedIDs.Add(pointID);

            pointRenderer?.SetPointHighlight(clickedPoint, true, Color.green);

            int requiredPoints = (currentActiveTool == ConstraintType.Coordinate) ? 1 : 2;

            if (collectedIDs.Count == requiredPoints)
            {
                ConstraintData newData = new ConstraintData();
                newData.Type = currentActiveTool;
                newData.Axis = GlobalAxis;
                newData.LeftPointAliases = new List<string>(collectedIDs);
                activeConstraints.Add(newData);

                ClearBuffers();
                OnConstraintAdded?.Invoke();

                // [UX UPDATE]: Explicitly tell the user they can keep clicking
                OnStatePromptChanged?.Invoke($"Row added. Set RHS in table, or keep clicking to add another [{currentActiveTool}] row.");
            }
            else
            {
                OnStatePromptChanged?.Invoke($"[{currentActiveTool}]: Point 1 selected. Click 1 more point.");
            }
        }
    }

    private void ClearBuffers()
    {
        collectedIDs.Clear();
    }
}
```

### File: `Scripts\Features\JoiningCoordinateSystemCreator.cs`
```csharp
﻿// ===============================================
// JoiningCoordinateSystemCreator.cs
// PRODUCTION VERSION - Dual Table Data & CSV Tie ID Integration
// ===============================================

using System;
using UnityEngine;
using System.Collections.Generic;
using TMPro;

// ==========================================
// [NEW] Data Structures for Table Visualization
// ==========================================
[System.Serializable]
public class TiePointRecord
{
    public string JointID;
    public string TiePointID;   // Read directly from CSV (e.g., "11")
    public string BlockID;
    public string PointID;
}

[System.Serializable]
public class JointTransformData
{
    public string JointID;      // Auto-generated Joint ID (e.g., "001")
    public string PointName;
    public Vector3 Translation;
    public Vector3 NormalVector;
    public Matrix4x4 RotationMatrix;

    // Relational data for the Tie Point Table (タイポイント表)
    public List<TiePointRecord> TiePoints = new List<TiePointRecord>();
}

public class JoiningCoordinateSystemCreator : MonoBehaviour
{
    [Header("Label Settings")]
    [Tooltip("Drag AxisLabelPrefab here")]
    public GameObject labelPrefab;

    [Header("Visual Settings (1 Unit = 1 mm)")]
    [Range(10f, 10000f)]
    public float axisLength = 500f;

    [Range(1f, 100f)]
    public float axisThickness = 8f;

    public Color planeColor = new Color(0.0f, 1.0f, 1.0f, 0.95f);

    public List<GameObject> ActiveCoordinateSystems => activeSystems;
    public List<JointTransformData> ExtractedJointData => jointDataList;

    // ==========================================
    // [NEW] Event & Counter for Data Tables 
    // ==========================================
    public event Action OnJointTableDataUpdated;
    public event Action<string> OnJointPromptChanged;

    private List<GameObject> activeSystems = new List<GameObject>();
    private List<JointTransformData> jointDataList = new List<JointTransformData>();
    private List<Point> selectedJoiningPoints = new List<Point>();

    private bool isSelecting = false;
    private Camera mainCamera;

    private void Awake()
    {
        Debug.Log("<color=red>[JoiningCreator] Script initialized.</color>");
    }

    private void Start()
    {
        mainCamera = Camera.main;
    }

    private void Update()
    {
        if (!isSelecting || !Input.GetMouseButtonDown(0)) return;

        if (UnityEngine.EventSystems.EventSystem.current != null &&
            UnityEngine.EventSystems.EventSystem.current.IsPointerOverGameObject()) return;

        Ray ray = mainCamera.ScreenPointToRay(Input.mousePosition);
        RaycastHit[] hits = Physics.SphereCastAll(ray, 80f, 200000f);

        Point bestPoint = null;
        float bestScreenDistance = 30f;
        Vector2 mousePos = Input.mousePosition;
        bool hitSomething = false;

        foreach (RaycastHit hit in hits)
        {
            PointSelectData data = hit.collider.GetComponent<PointSelectData>();
            if (data != null && data.point != null)
            {
                hitSomething = true;
                Point p = data.point;

                if (selectedJoiningPoints.Contains(p)) continue;
                if (p.PointType != "Joining" && p.PointType != "Reference") continue;

                Vector3 true3DPos = (p.GroupID == 0) ? p.DesignPosition : p.MeasurePosition;
                Vector3 screenPos = mainCamera.WorldToScreenPoint(true3DPos);

                if (screenPos.z > 0)
                {
                    float distToMouse = Vector2.Distance(mousePos, new Vector2(screenPos.x, screenPos.y));
                    if (distToMouse < bestScreenDistance)
                    {
                        bestScreenDistance = distToMouse;
                        bestPoint = p;
                    }
                }
            }
        }

        if (bestPoint != null)
        {
            selectedJoiningPoints.Add(bestPoint);
            Debug.Log($"<color=green>[JoiningCreator] Selected: {bestPoint.Name} ({selectedJoiningPoints.Count}/3) - Type: {bestPoint.PointType}</color>");

            OnJointPromptChanged?.Invoke($"Joint Setup: Selected {bestPoint.Name} ({selectedJoiningPoints.Count}/3).");
            FindFirstObjectByType<PointRenderer>()?.HighlightPointTemporary(bestPoint.ID, Color.magenta, 2f);

            if (selectedJoiningPoints.Count == 3)
            {
                CreateJointCoordinateSystem();
                isSelecting = false;
            }
        }
        else if (hitSomething)
        {
            OnJointPromptChanged?.Invoke("Invalid selection. Please click a valid 'Joining' or 'Reference' point.");
        }
    }

    public void BeginSelecting()
    {
        if (isSelecting) return;
        selectedJoiningPoints.Clear();
        isSelecting = true;

        OnJointPromptChanged?.Invoke("Joint Setup: Select Point 1/3 (Origin).");
        Debug.Log("<color=green>[JoiningCreator] Selection Mode ACTIVE</color>");
    }

    private void CreateJointCoordinateSystem()
    {
        if (selectedJoiningPoints.Count != 3) return;

        Vector3 p0 = selectedJoiningPoints[0].DesignPosition;
        Vector3 p1 = selectedJoiningPoints[1].DesignPosition;
        Vector3 p2 = selectedJoiningPoints[2].DesignPosition;

        Vector3 v1 = p1 - p0;
        Vector3 v2 = p2 - p0;

        if (v1.sqrMagnitude < 0.1f || v2.sqrMagnitude < 0.1f)
        {
            Debug.LogWarning("[JoiningCreator] Selection rejected: Points are too close.");
            OnJointPromptChanged?.Invoke("Error: Points too close. Selection reset. Select Point 1/3.");
            selectedJoiningPoints.Clear();
            return;
        }

        Vector3 zDir = v1.normalized;
        Vector3 v2Dir = v2.normalized;
        Vector3 crossNormal = Vector3.Cross(zDir, v2Dir);

        if (crossNormal.sqrMagnitude < 0.0001f)
        {
            Debug.LogWarning("[JoiningCreator] Selection rejected: Points are collinear (on the same line).");
            OnJointPromptChanged?.Invoke("Error: Points collinear! Selection reset. Select Point 1/3.");
            selectedJoiningPoints.Clear();
            return;
        }

        Vector3 xDir = crossNormal.normalized;
        Vector3 yDir = Vector3.Cross(zDir, xDir).normalized;

        // ==========================================
        // [MODIFIED] 
        // ==========================================
        string currentJointID = selectedJoiningPoints[0].Joint;
        if (string.IsNullOrEmpty(currentJointID))
        {
            currentJointID = "Unknown_Joint"; // 
        }

        Vector3 centerPoint = (p1 + p2) / 2f;

        GameObject systemRoot = new GameObject($"JointCoordSystem_{currentJointID}_{selectedJoiningPoints[0].Name}");
        systemRoot.transform.position = centerPoint;
        systemRoot.transform.rotation = Quaternion.LookRotation(zDir, yDir);

        activeSystems.Add(systemRoot);

        // ==========================================
        // [MODIFIED] (Normal Vector)
        // ==========================================
        JointTransformData data = new JointTransformData
        {
            JointID = currentJointID,
            PointName = selectedJoiningPoints[0].Name,
            Translation = centerPoint,
            NormalVector = crossNormal.normalized, // a, b, c
            RotationMatrix = new Matrix4x4(
                new Vector4(xDir.x, xDir.y, xDir.z, 0),
                new Vector4(yDir.x, yDir.y, yDir.z, 0),
                new Vector4(zDir.x, zDir.y, zDir.z, 0),
                new Vector4(0, 0, 0, 1)
            )
        };

        // Extract Tie Point data directly from the Point objects
        for (int i = 0; i < selectedJoiningPoints.Count; i++)
        {
            Point pt = selectedJoiningPoints[i];
            data.TiePoints.Add(new TiePointRecord
            {
                JointID = currentJointID,
                TiePointID = string.IsNullOrEmpty(pt.TieID) ? "N/A" : pt.TieID,
                BlockID = string.IsNullOrEmpty(pt.Block) ? "N/A" : pt.Block,
                PointID = pt.Name
            });
        }

        jointDataList.Add(data);

        CreateAxisLocal(systemRoot.transform, Vector3.right, Color.red, "X");
        CreateAxisLocal(systemRoot.transform, Vector3.up, Color.green, "Y");
        CreateAxisLocal(systemRoot.transform, Vector3.forward, Color.blue, "Z");
        CreatePlaneVisual(systemRoot.transform, p0, p1, p2);

        // ==========================================
        // Fire UI Update Events (イベントの発火)
        // ==========================================
        OnJointTableDataUpdated?.Invoke();
        OnJointPromptChanged?.Invoke($"Joint Coordinate System '{currentJointID}' Created.");

        isSelecting = false;
    }

    private void CreateAxisLocal(Transform parent, Vector3 localDirection, Color color, string labelText)
    {
        GameObject lineObj = new GameObject($"Axis_{labelText}");
        lineObj.transform.SetParent(parent, false);

        LineRenderer lr = lineObj.AddComponent<LineRenderer>();
        lr.material = new Material(Shader.Find("Unlit/Color"));
        lr.material.color = color;
        lr.startWidth = axisThickness;
        lr.endWidth = axisThickness;
        lr.positionCount = 2;
        lr.useWorldSpace = false;
        lr.material.renderQueue = 4000;

        lr.SetPosition(0, Vector3.zero);
        lr.SetPosition(1, localDirection * axisLength);

        if (labelPrefab != null)
        {
            GameObject labelGO = Instantiate(labelPrefab, lineObj.transform);
            labelGO.transform.localPosition = localDirection * (axisLength + (axisLength * 0.15f));
            labelGO.transform.localScale = Vector3.one;

            TextMeshPro tmp = labelGO.GetComponent<TextMeshPro>();
            if (tmp != null)
            {
                tmp.text = labelText;
                tmp.color = color;
                tmp.fontSize = axisLength * 0.5f;
                tmp.alignment = TextAlignmentOptions.Center;
            }
            if (labelGO.GetComponent<Billboard>() == null) labelGO.AddComponent<Billboard>();
        }
    }

    private void CreatePlaneVisual(Transform parentCoord, Vector3 p0World, Vector3 p1World, Vector3 p2World)
    {
        GameObject planeObj = new GameObject("JointPlaneVisual");
        planeObj.transform.SetParent(parentCoord, false);

        Vector3 originalP0 = parentCoord.InverseTransformPoint(p0World);
        Vector3 originalP1 = parentCoord.InverseTransformPoint(p1World);
        Vector3 originalP2 = parentCoord.InverseTransformPoint(p2World);
        Vector3 originalP3 = originalP1 + originalP2 - originalP0;

        float expandScale = 2.0f;
        Vector3 center = (originalP0 + originalP1 + originalP2 + originalP3) / 4f;

        Vector3 locP0 = center + (originalP0 - center) * expandScale;
        Vector3 locP1 = center + (originalP1 - center) * expandScale;
        Vector3 locP2 = center + (originalP2 - center) * expandScale;
        Vector3 locP3 = center + (originalP3 - center) * expandScale;

        LineRenderer lr = planeObj.AddComponent<LineRenderer>();
        lr.material = new Material(Shader.Find("Unlit/Color"));
        lr.material.color = planeColor;
        lr.startWidth = axisThickness;
        lr.endWidth = axisThickness;
        lr.positionCount = 5;
        lr.loop = true;
        lr.useWorldSpace = false;
        lr.material.renderQueue = 2500;

        lr.SetPosition(0, locP0);
        lr.SetPosition(1, locP1);
        lr.SetPosition(2, locP3);
        lr.SetPosition(3, locP2);
        lr.SetPosition(4, locP0);

        MeshFilter mf = planeObj.AddComponent<MeshFilter>();
        MeshRenderer mr = planeObj.AddComponent<MeshRenderer>();

        Mesh mesh = new Mesh();
        mesh.vertices = new Vector3[] { locP0, locP1, locP3, locP2 };
        mesh.triangles = new int[] { 0, 1, 2, 0, 2, 3, 0, 2, 1, 0, 3, 2 };
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        mf.mesh = mesh;

        Material faceMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        Color faceColor = planeColor;
        faceColor.a = 0.15f;
        faceMat.SetColor("_BaseColor", faceColor);
        faceMat.SetFloat("_Surface", 1);
        faceMat.SetFloat("_Blend", 0);
        faceMat.SetFloat("_ZWrite", 0);
        faceMat.renderQueue = 2900;
        mr.material = faceMat;
    }

    public void CreateSystemFromUI(Point p1, Point p2, Point p3)
    {
        if (p1 == null || p2 == null || p3 == null) return;

        selectedJoiningPoints.Clear();
        selectedJoiningPoints.Add(p1);
        selectedJoiningPoints.Add(p2);
        selectedJoiningPoints.Add(p3);

        CreateJointCoordinateSystem();

        isSelecting = false;
        selectedJoiningPoints.Clear();
    }

    public void ClearAllSystems()
    {
        foreach (var sys in activeSystems)
            if (sys != null) Destroy(sys);
        activeSystems.Clear();
        jointDataList.Clear();
        selectedJoiningPoints.Clear();
        isSelecting = false;

        OnJointTableDataUpdated?.Invoke(); // Refresh UI to clear table
        OnJointPromptChanged?.Invoke("Joint Coordinate System Cleared.");
    }
}
```

### File: `Scripts\Features\MacroAlignmentOrchestrator.cs`
```csharp
﻿// ===============================================
// MacroAlignmentOrchestrator.cs
// PRODUCTION VERSION V17 - Alignment Stats & Toast Broadcast
// ===============================================

using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class MacroAlignmentOrchestrator : MonoBehaviour
{
    [Header("Core Dependencies")]
    public ProjectRootBehaviour projectRoot;
    public BlockManager blockManager;

    [Header("Alignment Settings")]
    public string targetBlockCode = "B4";

    [Header("RANSAC Settings")]
    public float ransacThreshold = 50.0f;
    public int ransacIterations = 5000;

    public void ExecuteMacroAlignment()
    {
        if (projectRoot == null || projectRoot.ProjectData == null || blockManager == null) return;

        var allPoints = projectRoot.ProjectData.Points.Values.ToList();
        var designPoints = allPoints.Where(p => p.GroupID == 0).ToList();
        var measuredPoints = allPoints.Where(p => p.GroupID == 1).ToList();

        if (designPoints.Count == 0 || measuredPoints.Count == 0)
        {
            Debug.LogError("[MacroAlignment] Data missing. Load both CSV layers first.");
            return;
        }

        Vector3 designCentroid = Vector3.zero;
        foreach (var p in designPoints) designCentroid += p.DesignPosition;
        designCentroid /= designPoints.Count;

        Vector3 measuredCentroid = Vector3.zero;
        foreach (var p in measuredPoints) measuredCentroid += p.MeasurePosition;
        measuredCentroid /= measuredPoints.Count;

        Vector3[] designCloudLocal = designPoints.Select(p => p.DesignPosition - designCentroid).ToArray();
        Vector3[] measuredCloudLocal = measuredPoints.Select(p => p.MeasurePosition - measuredCentroid).ToArray();

        var joiningDesignLocal = designPoints
            .Select((p, idx) => new { Point = p, LocalPos = designCloudLocal[idx] })
            .Where(x => x.Point.PointType.ToUpper().Contains("JOINING"))
            .ToList();

        var joiningMeasuredLocal = measuredPoints
            .Select((p, idx) => new { Point = p, LocalPos = measuredCloudLocal[idx] })
            .Where(x => x.Point.PointType.ToUpper().Contains("JOINING"))
            .ToList();

        if (joiningDesignLocal.Count < 3 || joiningMeasuredLocal.Count < 3)
        {
            Debug.LogError($"[MacroAlignment] Insufficient local Joining points. Design: {joiningDesignLocal.Count}, Measured: {joiningMeasuredLocal.Count}");
            return;
        }

        Vector3[] P_RansacSource = joiningMeasuredLocal.Select(x => x.LocalPos).ToArray();
        Vector3[] Q_RansacTarget = joiningDesignLocal.Select(x => x.LocalPos).ToArray();

        RansacReorderResult ransacResult = PointRansacReorder.ReorderMeaToDesByRansac(
            P_RansacSource,
            Q_RansacTarget,
            ransacThreshold,
            ransacIterations
        );

        if (ransacResult == null || ransacResult.InlierCount < 3)
        {
            Debug.LogError($"[MacroAlignment] RANSAC Math Exception. Inliers: {ransacResult?.InlierCount}. Check Handedness Or Threshold.");
            return;
        }

        List<Vector3> P_SvdSource = new List<Vector3>();
        List<Vector3> Q_SvdTarget = new List<Vector3>();

        for (int i = 0; i < ransacResult.ReorderedMea.Length; i++)
        {
            if (ransacResult.Matched[i])
            {
                P_SvdSource.Add(ransacResult.ReorderedMea[i]);
                Q_SvdTarget.Add(Q_RansacTarget[i]);
            }
        }

        Matrix4x4 rotationMatrix;
        Vector3 localTranslation;
        float scale;

        RigidTransformUnity.ComputeUmeyamaSVD(P_SvdSource.ToArray(), Q_SvdTarget.ToArray(), out rotationMatrix, out localTranslation, out scale);

        Vector3 rotatedMeasuredCentroid = rotationMatrix.MultiplyPoint3x4(measuredCentroid);
        Vector3 globalTranslation = designCentroid - rotatedMeasuredCentroid + localTranslation;

        ApplyTransformationAndRemapNames(targetBlockCode, rotationMatrix, globalTranslation, designPoints, measuredPoints);

        Debug.Log($"[MacroAlignment] Success! Dynamic Spatial Remapping Complete. Inliers: {ransacResult.InlierCount}");
    }

    private void ApplyTransformationAndRemapNames(string matchCode, Matrix4x4 rotMatrix, Vector3 translation, List<Point> designPoints, List<Point> measuredPoints)
    {
        string upperMatch = matchCode.Trim().ToUpper();
        Block targetBlock = blockManager.AllBlocks.FirstOrDefault(b => b.IsMeasured && b.MatchCode.Contains(upperMatch));

        if (targetBlock != null && targetBlock.BlockRoot != null)
        {
            Transform blockRoot = targetBlock.BlockRoot;
            blockRoot.position = rotMatrix.MultiplyPoint3x4(blockRoot.position) + translation;
            blockRoot.rotation = rotMatrix.rotation * blockRoot.rotation;
        }

        var targetDesignBlockPoints = designPoints
            .Where(dp => dp.Block.ToUpper().Contains(upperMatch) || dp.Name.ToUpper().Contains(upperMatch))
            .ToList();

        if (targetDesignBlockPoints.Count == 0)
        {
            Debug.LogWarning($"[MacroAlignment] Failsafe triggered: No CAD points strictly matching '{upperMatch}'. Searching globally.");
            targetDesignBlockPoints = designPoints;
        }

        List<System.Guid> outlierTrashBin = new List<System.Guid>();
        float inheritanceThreshold = 100.0f;

        // Lists to store final valid paired points for statistical evaluation
        List<Vector3> finalTransformedPositions = new List<Vector3>();
        List<Vector3> finalTargetPositions = new List<Vector3>();

        foreach (var mPoint in measuredPoints)
        {
            // 1. Physically move the point in data space
            mPoint.MeasurePosition = rotMatrix.MultiplyPoint3x4(mPoint.MeasurePosition) + translation;

            // 2. Spatial Nearest Neighbor Search
            Point closestDesignPoint = null;
            float minDistance = float.MaxValue;

            foreach (var dPoint in targetDesignBlockPoints)
            {
                float currentDistance = Vector3.Distance(mPoint.MeasurePosition, dPoint.DesignPosition);
                if (currentDistance < minDistance)
                {
                    minDistance = currentDistance;
                    closestDesignPoint = dPoint;
                }
            }

            // 3. Complete Identity and Math Synchronization
            if (closestDesignPoint != null && minDistance <= inheritanceThreshold)
            {
                mPoint.Name = closestDesignPoint.Name;
                mPoint.DisplayID = closestDesignPoint.DisplayID;
                mPoint.Block = closestDesignPoint.Block;
                mPoint.Joint = closestDesignPoint.Joint;
                mPoint.PlateType = closestDesignPoint.PlateType;
                mPoint.PointPlace = closestDesignPoint.PointPlace;
                mPoint.TieID = closestDesignPoint.TieID;
                mPoint.PointType = closestDesignPoint.PointType;
                mPoint.DesignPosition = closestDesignPoint.DesignPosition;

                closestDesignPoint.MeasurePosition = mPoint.MeasurePosition;
                closestDesignPoint.CalculateError();
                mPoint.CalculateError();

                // Add to final evaluation lists
                finalTransformedPositions.Add(mPoint.MeasurePosition);
                finalTargetPositions.Add(mPoint.DesignPosition);
            }
            else
            {
                outlierTrashBin.Add(mPoint.ID);
            }
        }

        // ==========================================
        // Execute Outlier Purge 
        // ==========================================
        if (outlierTrashBin.Count > 0)
        {
            foreach (var trashId in outlierTrashBin)
            {
                projectRoot.ProjectData.RemovePoint(trashId);
            }
            Debug.LogWarning($"<color=orange>[MacroAlignment] Data Purge: Destroyed {outlierTrashBin.Count} outlier points.</color>");
        }

        // ==========================================
        // Calculate & Broadcast Final Statistics
        // ==========================================
        CalculateAndReportAlignmentStats(finalTransformedPositions, finalTargetPositions);

        // [変更] サービスロケーターを使用してUIとレンダリングの更新を安全に呼び出す (安全解包触发UI连动)
        if (ServiceLocator.TryGet<PointRenderer>(out var renderer)) renderer.RefreshAllPoints();
        if (ServiceLocator.TryGet<PointTableDisplay>(out var tableDisplay)) tableDisplay.RefreshTable();
    }

    /// <summary>
    /// Calculates and broadcasts the alignment statistics including Max, Min, and RMS errors.
    /// Turns text red if RMS exceeds the tolerance limit.
    /// </summary>
    private void CalculateAndReportAlignmentStats(List<Vector3> transformedPoints, List<Vector3> targetPoints)
    {
        if (transformedPoints == null || targetPoints == null || transformedPoints.Count != targetPoints.Count || transformedPoints.Count == 0) return;

        int matchCount = transformedPoints.Count;
        float maxError = float.MinValue;
        float minError = float.MaxValue;
        float sumSquaredError = 0f;

        for (int i = 0; i < matchCount; i++)
        {
            float distance = Vector3.Distance(transformedPoints[i], targetPoints[i]);
            if (distance > maxError) maxError = distance;
            if (distance < minError) minError = distance;
            sumSquaredError += (distance * distance);
        }

        float rmsError = Mathf.Sqrt(sumSquaredError / matchCount);

        // Determine if text should be red based on an RMS tolerance (e.g., > 5.0mm)
        bool exceedsTolerance = rmsError > 5.0f;
        string colorPrefix = exceedsTolerance ? "<color=red>" : "";
        string colorSuffix = exceedsTolerance ? "</color>" : "";

        string statsMessage = $"{colorPrefix}Alignment Complete\n" +
                              $"Matched Points: {matchCount}\n" +
                              $"Max Error: {maxError:F3} mm\n" +
                              $"Min Error: {minError:F3} mm\n" +
                              $"RMS: {rmsError:F3} mm{colorSuffix}";

        Debug.Log($"<color=cyan>[AlignmentStats]</color> {statsMessage.Replace("\n", " | ").Replace("<color=red>", "").Replace("</color>", "")}");

        if (UIToastNotifier.Instance != null)
        {
            UIToastNotifier.Instance.ShowToast(statsMessage);
        }
    }
}
```

### File: `Scripts\Features\MeshDeformationEngine.cs`
```csharp
﻿// ===============================================
// MeshDeformationEngine.cs
// PRODUCTION VERSION V8 - Cosine Falloff (100% Power, Anti-Spike, Anti-Rubber)
// ===============================================

using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;

public static class MeshDeformationEngine
{
    public static void DeformMesh(
        Mesh mesh,
        List<Vector3> designLocalPts,
        List<Vector3> measuredLocalPts,
        float p,
        float influenceRadius,
        float exaggerationFactor = 1f,
        bool enableHeatmap = false,
        float maxTolerance = 5f)
    {
        Vector3[] vertices = mesh.vertices;
        Vector3[] deformedVertices = new Vector3[vertices.Length];
        Color[] vertexColors = new Color[vertices.Length];

        int count = designLocalPts.Count;
        Vector3[] dPts = designLocalPts.ToArray();
        Vector3[] mPts = measuredLocalPts.ToArray();

        // 1. Dynamic Auto-Ranging for Heatmap
        float dynamicMaxError = 0.001f;
        for (int i = 0; i < count; i++)
        {
            float dev = (mPts[i] - dPts[i]).magnitude;
            if (dev > dynamicMaxError) dynamicMaxError = dev;
        }

        Color colorPass = Color.green;
        Color colorWarn = Color.yellow;
        Color colorFail = Color.red;

        Parallel.For(0, vertices.Length, v =>
        {
            Vector3 vertex = vertices[v];
            float minDist = float.MaxValue;

            // 2. 
            for (int i = 0; i < count; i++)
            {
                float d = (vertex - dPts[i]).magnitude;
                if (d < minDist) minDist = d;
            }

            // 3. 
            if (minDist >= influenceRadius)
            {
                deformedVertices[v] = vertex;
                vertexColors[v] = colorPass;
                return;
            }

            Vector3 idwDelta = Vector3.zero;
            float totalWeight = 0f;

            // 4. 
            for (int i = 0; i < count; i++)
            {
                float dist = (vertex - dPts[i]).magnitude;

                dist = Mathf.Max(0.0001f, dist);

                float weight = 1.0f / Mathf.Pow(dist, p);
                idwDelta += (mPts[i] - dPts[i]) * weight;
                totalWeight += weight;
            }

            // ========================================================
            // 5. [CRITICAL FIX] Cosine Interpolation Curve 
            // ========================================================
            float t = Mathf.Clamp01(minDist / influenceRadius);
            float blendFactor = Mathf.Cos(t * Mathf.PI * 0.5f);

            Vector3 realDeviation = (idwDelta / totalWeight) * blendFactor;

            // 6. 
            deformedVertices[v] = vertex + (realDeviation * exaggerationFactor);

            // 7. 
            if (enableHeatmap)
            {
                float errorDistance = realDeviation.magnitude;
                float linearError = errorDistance / dynamicMaxError;
                float normalizedError = Mathf.Clamp01(linearError);

                if (normalizedError < 0.5f)
                {
                    vertexColors[v] = Color.Lerp(colorPass, colorWarn, normalizedError * 2f);
                }
                else
                {
                    vertexColors[v] = Color.Lerp(colorWarn, colorFail, (normalizedError - 0.5f) * 2f);
                }
            }
            else
            {
                vertexColors[v] = Color.white;
            }
        });

        mesh.vertices = deformedVertices;
        if (enableHeatmap) mesh.colors = vertexColors;

        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
    }
}
```

### File: `Scripts\Features\MultiBlockAlignmentBridge.cs`
```csharp
﻿using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using LSE;

/// <summary>
/// 複数ブロックの剛体最適化計算を管理し、算出された座標変換をUnityのTransformに直接適用するブリッジスクリプト。
/// Point.cs の実データ構造に基づき、共通のTieIDや設計・計測点データを用いてアライメント調整（アライメント調整）を行います。
/// </summary>
public class MultiBlockAlignmentBridge : MonoBehaviour
{
    /// <summary>
    /// エラーログビューワー等に詳細な計算プロセスのログを渡すための静的イベント
    /// </summary>
    public static event Action<string> OnDetailedLogGenerated;

    // [NEW] 追加: HUDへ結果を送信するためのグローバルイベント
    public static event Action<ConstrainedMultiBlockAlignment.SolveResult, ConstrainedMultiBlockAlignment.RmsResult> OnAlignmentCompleted;

    [SerializeField]
    private ProjectData projectData;

    /// <summary>
    /// 最適化アライメント（マルチブロック位置合わせ）を実行し、結果を各ブロックのTransformに反映します。
    /// </summary>
    public void ExecuteAlignment()
    {
        // [変更] サービスロケーターからの取得に置換 (消除场景搜索警告)
        if (projectData == null)
        {
            ServiceLocator.TryGet(out projectData);
            if (projectData == null)
            {
                string err = "[MultiBlockAlignmentBridge] ProjectData が見つかりません。計算を中断します。";
                Debug.LogError(err);
                LogToViewer(err);
                return;
            }
        }

        // [変更] サービスロケーターからの取得に置換
        ServiceLocator.TryGet<UIToastNotifier>(out var toast);
        if (toast != null)
        {
            toast.ShowToast("マルチブロック剛体アライメント計算を開始します...");
        }

        LogToViewer("===============================================");
        LogToViewer("マルチブロック剛体アライメント計算プロセスを開始します。");

        try
        {
            // 最適化ソルバー（ConstrainedMultiBlockAlignment）の初期化
            ConstrainedMultiBlockAlignment alignmentSolver = new ConstrainedMultiBlockAlignment();

            // ProjectDataから全ポイントを取得
            var allPoints = projectData.Points.Values.ToList();

            if (allPoints.Count == 0)
            {
                string warn = "警告: ProjectData にポイントデータが存在しません。";
                Debug.LogWarning(warn);
                LogToViewer(warn);
                return;
            }

            // 1. ブロック名（Block）ごとにデータをグループ化
            // Nullまたは空のブロック名を持つポイントは除外します
            var pointsByBlock = allPoints
                .Where(p => !string.IsNullOrEmpty(p.Block))
                .GroupBy(p => p.Block)
                .ToList();

            foreach (var blockGroup in pointsByBlock)
            {
                string blockName = blockGroup.Key;
                var blockPoints = blockGroup.ToList();

                // 2. GroupIDによる設計点（0）と計測点（1）の分離
                var designPoints = blockPoints.Where(p => p.GroupID == 0).ToList();
                var measuredPoints = blockPoints.Where(p => p.GroupID == 1).ToList();

                List<Point> matchedMeasured = new List<Point>();
                List<Point> matchedDesign = new List<Point>();

                // 3. TieIDを用いた設計点と計測点のペアリング（ペアリング）
                // ==========================================
                // [CRITICAL FIX] O(N^2) の FirstOrDefault ループを排除し、
                // O(N) の辞書ルックアップに変更してパフォーマンスを最適化
                // (消除 O(N^2) 的嵌套查找，改用 O(N) 的字典映射以优化性能并防止崩溃)
                // ==========================================
                Dictionary<string, Point> designTieMap = new Dictionary<string, Point>(System.StringComparer.Ordinal);

                // 事前に設計点(Design)のハッシュマップを構築
                foreach (var d in designPoints)
                {
                    if (!string.IsNullOrEmpty(d.TieID) && !designTieMap.ContainsKey(d.TieID))
                    {
                        designTieMap.Add(d.TieID, d);
                    }
                }

                // O(1)で実測点(Measured)と高速マッチング
                foreach (var mPoint in measuredPoints)
                {
                    if (string.IsNullOrEmpty(mPoint.TieID)) continue;

                    if (designTieMap.TryGetValue(mPoint.TieID, out Point dPoint))
                    {
                        matchedMeasured.Add(mPoint);
                        matchedDesign.Add(dPoint);
                    }
                }

                int pointCount = matchedMeasured.Count;
                if (pointCount == 0)
                {
                    LogToViewer($"ブロック [{blockName}] には一致するTieIDのペアがありません。スキップします。");
                    continue;
                }

                double[,] xb = new double[pointCount, 3]; // 計測点座標（Measured points）
                double[,] xd = new double[pointCount, 3]; // 設計点座標（Design points）
                int[] pointIds = new int[pointCount];
                int[] tieIds = new int[pointCount];

                // 4. ソルバー用の配列データ構築
                for (int i = 0; i < pointCount; i++)
                {
                    var mPoint = matchedMeasured[i];
                    var dPoint = matchedDesign[i];

                    // 安全策: MeasurePositionがゼロベクトルの場合、DesignPositionにフォールバックします
                    Vector3 mPos = (mPoint.MeasurePosition != Vector3.zero) ? mPoint.MeasurePosition : mPoint.DesignPosition;
                    Vector3 dPos = dPoint.DesignPosition;

                    xb[i, 0] = mPos.x; xb[i, 1] = mPos.y; xb[i, 2] = mPos.z;
                    xd[i, 0] = dPos.x; xd[i, 1] = dPos.y; xd[i, 2] = dPos.z;

                    // Guidをハッシュ値に変換して整数IDとして利用します
                    pointIds[i] = ConvertGuidToInt(mPoint.ID);
                    tieIds[i] = ConvertTieIdToInt(mPoint.TieID);
                }

                // スケール固定(1)の標準自由度フラグ
                int[] flg7 = new int[] { 0, 0, 0, 0, 0, 0, 1 };

                // ブロックをソルバーに登録
                alignmentSolver.AddBlock(blockName, xb, xd, null, flg7, pointIds, tieIds);
                LogToViewer($"ブロック [{blockName}] を登録しました。有効ポイント対: {pointCount}");
            }

            // 5. 結合点（JoiningPoints）から距離拘束条件（拘束条件）を抽出して追加
            var joiningPoints = projectData.JoiningPoints;

            // TieIDでグループ化し、異なるブロック間にまたがる拘束を特定します
            var joiningGroups = joiningPoints
                .Where(p => !string.IsNullOrEmpty(p.TieID))
                .GroupBy(p => p.TieID)
                .Where(g => g.Count() >= 2)
                .ToList();

            foreach (var group in joiningGroups)
            {
                var list = group.ToList();
                var pA = list[0];
                var pB = list[1];

                // 同一ブロック内の拘束は無効とするため除外します
                if (pA.Block != pB.Block)
                {
                    // RootGapを目標距離（ターゲット距離）として使用します
                    double targetLength = pA.RootGap;

                    alignmentSolver.AddDistanceConstraintByPointId(
                        pA.Block, ConvertGuidToInt(pA.ID),
                        pB.Block, ConvertGuidToInt(pB.ID),
                        targetLength
                    );

                    LogToViewer($"距離拘束を追加: {pA.Block} と {pB.Block} (TieID: {pA.TieID}, 距離: {targetLength})");
                }
            }

            // 6. アライメント計算実行
            var solveResult = alignmentSolver.Solve();
            var rmsAll = alignmentSolver.GetGlobalRms(); // [NEW] 全体RMSを取得

            if (solveResult.Status == ConstrainedMultiBlockAlignment.SolveStatus.Ok)
            {
                string okMsg = $"アライメント収束成功: 反復回数={solveResult.Iterations}, 最大変位={solveResult.MaxAbsDx:F6}";
                Debug.Log(okMsg);
                LogToViewer(okMsg);

                // 7. 計算結果を実際のGameObject(Transform)に適用
                foreach (var blockGroup in pointsByBlock)
                {
                    string blockName = blockGroup.Key;

                    // ゲームオブジェクト名がBlock名と一致すると仮定しています
                    GameObject blockObj = GameObject.Find(blockName);
                    if (blockObj == null)
                    {
                        LogToViewer($"警告: Transform適用対象のGameObject [{blockName}] が見つかりません。");
                        continue;
                    }

                    var tf = alignmentSolver.GetBlockTransform(blockName);

                    // 位置（Translation）の適用
                    blockObj.transform.position = new Vector3((float)tf.Tx, (float)tf.Ty, (float)tf.Tz);

                    // 回転（Rotation）の適用: LSE_alignmentの回転符号がUnityと逆なため、マイナスを付与します
                    blockObj.transform.rotation = Quaternion.Euler(
                        (float)(-tf.Rx * Mathf.Rad2Deg),
                        (float)(-tf.Ry * Mathf.Rad2Deg),
                        (float)(-tf.Rz * Mathf.Rad2Deg)
                    );

                    // スケール（Scale）の適用: LSEのScaleは差分sなので、1.0を加算します
                    float scaleFactor = 1.0f + (float)tf.Scale;
                    blockObj.transform.localScale = new Vector3(scaleFactor, scaleFactor, scaleFactor);

                    LogToViewer($"[{blockName}] Transform更新完了: Pos={blockObj.transform.position}, Rot={blockObj.transform.rotation.eulerAngles}");
                }

                if (toast != null) toast.ShowToast("アライメント計算が正常に完了しました。");
            }
            else
            {
                string failMsg = $"アライメント収束失敗: {solveResult.Status} - {solveResult.Message}";
                Debug.LogError(failMsg);
                LogToViewer(failMsg);
                if (toast != null) toast.ShowToast($"エラー: {solveResult.Status}");
            }
            // [NEW] 追加: 計算完了後にHUDへ結果をブロードキャストする
            OnAlignmentCompleted?.Invoke(solveResult, rmsAll);
        }
        catch (Exception ex)
        {
            string errMsg = $"[MultiBlockAlignmentBridge] アライメント実行中に例外が発生しました: {ex.Message}\n{ex.StackTrace}";
            Debug.LogError(errMsg);
            LogToViewer(errMsg);
            if (toast != null)
            {
                toast.ShowToast("エラー: アライメント計算に例外が発生しました。");
            }
        }
    }

    /// <summary>
    /// ログビューワーへメッセージを送信します。
    /// </summary>
    private void LogToViewer(string message)
    {
        OnDetailedLogGenerated?.Invoke($"[{DateTime.Now:HH:mm:ss}] {message}\n");
    }

    /// <summary>
    /// Guidを最適化用のユニークな整数型に安全に変換します。
    /// </summary>
    private int ConvertGuidToInt(Guid guid)
    {
        return guid.GetHashCode();
    }

    /// <summary>
    /// 共通のTieIDを最適化用の整数型に安全に変換します。
    /// </summary>
    private int ConvertTieIdToInt(string tieId)
    {
        if (string.IsNullOrEmpty(tieId))
            return -1;
        return tieId.GetHashCode();
    }
}
```

### File: `Scripts\Features\PointDataProcessor.cs`
```csharp
﻿// ===============================================
// PointDataProcessor.cs
// PRODUCTION VERSION - Zero-Inference Automatic Pairing
// ===============================================

using UnityEngine;
using System.Linq;
using System.Collections.Generic;

public class PointDataProcessor : MonoBehaviour
{
    [Header("Project Reference")]
    [SerializeField] private ProjectRootBehaviour projectRoot;

    // Preserving original color definitions
    private readonly Color referenceColor = new Color(1.0f, 0.0f, 0.0f, 1.0f); // Pure Red
    private readonly Color joiningColor = new Color(0.25f, 0.75f, 1.0f, 1.0f);   // Blue

    public void ProcessImportedPoints(int groupID)
    {
        if (projectRoot == null || projectRoot.ProjectData == null) return;

        // 1. Original Visual Processing & Initial Calculation
        int processedCount = 0;
        var allPointsList = projectRoot.ProjectData.Points.Values.ToList();

        foreach (var point in allPointsList)
        {
            if (point.GroupID == groupID)
            {
                point.Color = (point.PointType == "Joining") ? joiningColor : referenceColor;
                point.CalculateError();
                processedCount++;
            }
        }

        // 2. Execute Deterministic Pairing
        PerformAutomaticPairing(allPointsList);

        // 3. Trigger Render Refresh
        // [変更] ServiceLocatorを使用して取得
        if (ServiceLocator.TryGet<PointRenderer>(out var renderer))
        {
            renderer.RefreshAllPoints();
        }
    }

    /// <summary>
    /// Binds Global Design positions to Measured points by matching Name.
    /// (名前の一致に基づいて、設計座標と実測座標をバインディングする)
    /// </summary>
    private void PerformAutomaticPairing(List<Point> allPoints)
    {
        // ==========================================
        // [CRITICAL FIX] LINQの排除と安全な辞書構築 (消除LINQ并构建安全的字典)
        // GC(ガベージコレクション)の発生を防ぎ、CADデータ内の名前重複による
        // 例外(Key Collision)クラッシュを回避します。
        // ==========================================
        Dictionary<string, Point> designMap = new Dictionary<string, Point>(System.StringComparer.Ordinal);

        // 1. 設計点(Design: GroupID=0)のマップを安全に構築
        for (int i = 0; i < allPoints.Count; i++)
        {
            Point p = allPoints[i];
            if (p.GroupID == 0 && !string.IsNullOrEmpty(p.Name))
            {
                if (!designMap.ContainsKey(p.Name))
                {
                    designMap.Add(p.Name, p);
                }
                else
                {
                    // 既存の機能は維持しつつ、重複の警告のみ出力 (保留首个匹配点，仅输出重复警告)
                    Debug.LogWarning($"[PointDataProcessor] 警告: 同一のName '{p.Name}' を持つ設計点が複数存在します。最初のポイントのみがマッピングされます。");
                }
            }
        }

        // 2. 実測点(Measured: GroupID=1)のペアリングと双方向バインディング
        for (int i = 0; i < allPoints.Count; i++)
        {
            Point mPoint = allPoints[i];
            if (mPoint.GroupID == 1 && !string.IsNullOrEmpty(mPoint.Name))
            {
                // マップから対応する設計点を検索
                if (designMap.TryGetValue(mPoint.Name, out Point dPoint))
                {
                    // Inject the true Design baseline into the Measured point
                    mPoint.DesignPosition = dPoint.DesignPosition;
                    mPoint.CalculateError();

                    // Two-Way Binding: Inject Measure position back into Design point for UI
                    dPoint.MeasurePosition = mPoint.MeasurePosition;
                    dPoint.CalculateError();
                }
            }
        }
    }
}
```

### File: `Scripts\Features\RPSSloverMiddleware.cs`
```csharp
﻿// ===============================================
// RPSSolverMiddleware.cs
// PRODUCTION VERSION - Global Axis & Inequality Solver
// ===============================================

using System.Collections.Generic;
using UnityEngine;

public static class RPSSolverMiddleware
{
    public static List<PointPairData> ApplyRPSConstraints(
            List<PointPairData> originalPairs,
            IReadOnlyList<ConstraintData> constraints,
            Matrix4x4 jointLocalToWorld,
            Dictionary<string, string> pointToBlockMap,
            string jointOriginBlockName,
            Dictionary<string, string> aliasToNameMap // Matches the 5-digit alias to the actual PointName
        )
    {
        List<PointPairData> processedPairs = new List<PointPairData>(originalPairs);
        Matrix4x4 worldToLocal = jointLocalToWorld.inverse;

        // ==========================================
        // [CRITICAL FIX] 安全な辞書構築 (安全的字典构建)
        // 辞書への登録時に重複をチェックし、静默な上書きによる計算エラーを防ぐ
        // ==========================================
        Dictionary<string, PointPairData> nameMap = new Dictionary<string, PointPairData>(System.StringComparer.Ordinal);
        foreach (var p in processedPairs)
        {
            if (!nameMap.ContainsKey(p.PointName))
            {
                nameMap.Add(p.PointName, p);
            }
            else
            {
                // 既存の機能は維持しつつ、重複の警告のみ出力 (保留首个点，仅输出警告保证不崩溃)
                Debug.LogWarning($"[RPSSolver] 警告: 重複するポイント名 '{p.PointName}' を検出しました。最初のポイントのみを使用します。");
            }
        }

        foreach (var constraint in constraints)
        {
            if (!constraint.IsEnabled || constraint.LeftPointAliases.Count == 0) continue;

            string blockToMove = "";

            // ==========================================
            // BRANCH 1: Absolute Coordinate Constraints (座標拘束)
            // ==========================================
            if (constraint.Type == ConstraintType.Coordinate)
            {
                string p1_Alias = constraint.LeftPointAliases[0];
                if (!aliasToNameMap.TryGetValue(p1_Alias, out string p1_Name) || !nameMap.ContainsKey(p1_Name)) continue;

                Vector3 localPos = worldToLocal.MultiplyPoint3x4(nameMap[p1_Name].MeasurePosition);

                // Dynamically extract the target axis value based on Global Axis selection
                float currentValue = constraint.Axis == ConstraintAxis.X ? localPos.x :
                                     (constraint.Axis == ConstraintAxis.Y ? localPos.y : localPos.z);

                float targetValue = constraint.RightConstant;

                if (Mathf.Abs(currentValue - targetValue) > 1e-4f)
                {
                    float delta = targetValue - currentValue;

                    // Dynamically build the shift vector
                    Vector3 shiftVector = new Vector3(
                        constraint.Axis == ConstraintAxis.X ? delta : 0,
                        constraint.Axis == ConstraintAxis.Y ? delta : 0,
                        constraint.Axis == ConstraintAxis.Z ? delta : 0
                    );

                    blockToMove = pointToBlockMap[p1_Name];
                    ShiftEntireBlock(processedPairs, pointToBlockMap, blockToMove, shiftVector, worldToLocal, jointLocalToWorld);
                }
                continue; // Move to the next constraint
            }

            // ==========================================
            // BRANCH 2: Relative Gap Constraints (相対間隙拘束)
            // ==========================================
            if (constraint.Type == ConstraintType.Distance || constraint.Type == ConstraintType.EqualClearance)
            {
                if (constraint.LeftPointAliases.Count < 2) continue;

                string leftP1_Alias = constraint.LeftPointAliases[0];
                string leftP2_Alias = constraint.LeftPointAliases[1];

                if (!aliasToNameMap.TryGetValue(leftP1_Alias, out string leftP1_Name) ||
                    !aliasToNameMap.TryGetValue(leftP2_Alias, out string leftP2_Name) ||
                    !nameMap.ContainsKey(leftP1_Name) || !nameMap.ContainsKey(leftP2_Name)) continue;

                Vector3 localPos1 = worldToLocal.MultiplyPoint3x4(nameMap[leftP1_Name].MeasurePosition);
                Vector3 localPos2 = worldToLocal.MultiplyPoint3x4(nameMap[leftP2_Name].MeasurePosition);

                // Dynamically extract the specific axis for gap calculation
                float leftV1 = constraint.Axis == ConstraintAxis.X ? localPos1.x : (constraint.Axis == ConstraintAxis.Y ? localPos1.y : localPos1.z);
                float leftV2 = constraint.Axis == ConstraintAxis.X ? localPos2.x : (constraint.Axis == ConstraintAxis.Y ? localPos2.y : localPos2.z);
                float currentLeftDistance = Mathf.Abs(leftV1 - leftV2);

                float targetRightDistance = constraint.RightConstant;

                // If RHS is an equation, calculate dynamic gap for RHS
                if (constraint.IsRightSideEquation && constraint.RightPointAliases.Count >= 2)
                {
                    string rightP1_Alias = constraint.RightPointAliases[0];
                    string rightP2_Alias = constraint.RightPointAliases[1];

                    if (aliasToNameMap.TryGetValue(rightP1_Alias, out string rightP1_Name) &&
                        aliasToNameMap.TryGetValue(rightP2_Alias, out string rightP2_Name) &&
                        nameMap.ContainsKey(rightP1_Name) && nameMap.ContainsKey(rightP2_Name))
                    {
                        Vector3 rLocalPos1 = worldToLocal.MultiplyPoint3x4(nameMap[rightP1_Name].MeasurePosition);
                        Vector3 rLocalPos2 = worldToLocal.MultiplyPoint3x4(nameMap[rightP2_Name].MeasurePosition);

                        float rightV1 = constraint.Axis == ConstraintAxis.X ? rLocalPos1.x : (constraint.Axis == ConstraintAxis.Y ? rLocalPos1.y : rLocalPos1.z);
                        float rightV2 = constraint.Axis == ConstraintAxis.X ? rLocalPos2.x : (constraint.Axis == ConstraintAxis.Y ? rLocalPos2.y : rLocalPos2.z);
                        targetRightDistance = Mathf.Abs(rightV1 - rightV2);
                    }
                }

                // Operator evaluation (演算子の判定)
                bool isSatisfied = false;
                switch (constraint.Operator)
                {
                    case RelationalOperator.Equal: isSatisfied = Mathf.Abs(currentLeftDistance - targetRightDistance) < 1e-4f; break;
                    case RelationalOperator.GreaterOrEqual: isSatisfied = currentLeftDistance >= targetRightDistance; break;
                    case RelationalOperator.LessOrEqual: isSatisfied = currentLeftDistance <= targetRightDistance; break;
                }

                if (isSatisfied) continue;

                // Identify Base Block locking (アンカーブロックの固定)
                float requiredShiftDelta = targetRightDistance - currentLeftDistance;
                string block1 = pointToBlockMap[leftP1_Name];
                string block2 = pointToBlockMap[leftP2_Name];

                blockToMove = block2;
                float moveDirection = Mathf.Sign(leftV2 - leftV1);

                if (block2 == jointOriginBlockName)
                {
                    blockToMove = block1;
                    moveDirection = Mathf.Sign(leftV1 - leftV2);
                }

                // Build localized shift vector applying only to the target axis
                Vector3 localShiftVector = new Vector3(
                    constraint.Axis == ConstraintAxis.X ? requiredShiftDelta * moveDirection : 0,
                    constraint.Axis == ConstraintAxis.Y ? requiredShiftDelta * moveDirection : 0,
                    constraint.Axis == ConstraintAxis.Z ? requiredShiftDelta * moveDirection : 0
                );

                ShiftEntireBlock(processedPairs, pointToBlockMap, blockToMove, localShiftVector, worldToLocal, jointLocalToWorld);
            }
        }

        return processedPairs;
    }

    /// <summary>
    /// Translates the specified 3D Block and updates its mapped point coordinates.
    /// </summary>
    private static void ShiftEntireBlock(List<PointPairData> pairs, Dictionary<string, string> blockMap, string targetBlockName, Vector3 localShiftVector, Matrix4x4 worldToLocal, Matrix4x4 localToWorld)
    {
        if (localShiftVector.sqrMagnitude < 1e-6f) return;

        for (int i = 0; i < pairs.Count; i++)
        {
            if (blockMap[pairs[i].PointName] == targetBlockName)
            {
                PointPairData blockPoint = pairs[i];
                Vector3 pLocal = worldToLocal.MultiplyPoint3x4(blockPoint.MeasurePosition);
                pLocal += localShiftVector;
                blockPoint.MeasurePosition = localToWorld.MultiplyPoint3x4(pLocal);
                pairs[i] = blockPoint;
            }
        }
    }
}
```

### File: `Scripts\IO\FileDialogHelper.cs`
```csharp
﻿// ===============================================
// FileDialogHelper.cs
// Production-Ready File Dialog Helper for Unity
// ===============================================
// Purpose:
//   - Provides a unified, cross-platform file selection dialog for CSV import.
//   - In UNITY_EDITOR: Uses Unity's built-in EditorUtility.OpenFilePanel (instant popup, no Win32 issues).
//   - In Standalone Windows Build: Falls back to native Win32 GetOpenFileName (keeps original UI style).
//   - Fixes the exact issue: "No file dialog pops up when clicking Designed/Measured buttons in Editor".
//   - Zero dependencies on other scripts. Fully compatible with design/measured point workflow.
//
// Author: Grok (based on your original code)
// Last Updated: March 2026
// ===============================================

using System;
using System.Runtime.InteropServices;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;   // Only compiled in Editor - no runtime overhead
#endif

public static class FileDialogHelper
{
    /// <summary>
    /// Win32 OpenFileName structure (only used in Standalone Build).
    /// Mirrors the original implementation you provided.
    /// </summary>
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    public class OpenFileName
    {
        public int structSize = Marshal.SizeOf(typeof(OpenFileName));
        public IntPtr dlgOwner = IntPtr.Zero;
        public IntPtr instance = IntPtr.Zero;
        public string filter = null;
        public string customFilter = null;
        public int maxCustFilter = 0;
        public int filterIndex = 0;
        public string file = null;
        public int maxFile = 260;
        public string fileTitle = null;
        public int maxFileTitle = 64;
        public string initialDir = null;
        public string title = null;
        public int flags = 0x00080000 | 0x00001000 | 0x00000800; // OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST
        public ushort fileOffset = 0;
        public ushort fileExtension = 0;
        public string defExt = null;
        public IntPtr custData = IntPtr.Zero;
        public IntPtr hook = IntPtr.Zero;
        public string templateName = null;
        public IntPtr reservedPtr = IntPtr.Zero;
        public int reservedInt = 0;
        public int flagsEx = 0;
    }

#if !UNITY_EDITOR
    /// <summary>
    /// Native Win32 API - only compiled in Standalone Build.
    /// </summary>
    [DllImport("Comdlg32.dll", CharSet = CharSet.Auto)]
    private static extern bool GetOpenFileName([In, Out] OpenFileName ofn);

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();
#endif

    /// <summary>
    /// Opens a native-looking file dialog and returns the full path to the selected CSV file.
    /// 
    /// Behavior:
    ///   - UNITY_EDITOR: Immediate, reliable popup using EditorUtility (fixes your current issue).
    ///   - Standalone Build: Original Win32 dialog (no change to user experience).
    /// 
    /// Parameters:
    ///   title      - Dialog window title (default: "Select CSV File")
    ///   initialDir - Starting folder (default: empty = last used or Documents)
    ///   filter     - File filter string (default: CSV only)
    /// 
    /// Returns:
    ///   Full absolute path to selected file, or empty string if cancelled.
    /// </summary>
    public static string OpenFileDialog(
        string title = "Select CSV File",
        string initialDir = "",
        string filter = "CSV Files (*.csv)|*.csv")
    {
        // Unified debug log for both Editor and Build
        Debug.Log($"[FileDialogHelper] Opening dialog → Title: \"{title}\" | Mode: {(Application.isEditor ? "EDITOR (EditorUtility)" : "STANDALONE BUILD (Win32)")}");

#if UNITY_EDITOR
        // ==================== UNITY EDITOR PATH (RECOMMENDED & STABLE) ====================
        // EditorUtility.OpenFilePanel is the official Unity way - always works in Editor.
        // No DLL issues, no focus problems, instant popup.
        string selectedPath = EditorUtility.OpenFilePanel(title, initialDir, "csv");

        if (!string.IsNullOrEmpty(selectedPath))
        {
            Debug.Log($"<color=green>[FileDialogHelper] SUCCESS: EditorUtility selected → {selectedPath}</color>");
            return selectedPath;
        }
        else
        {
            Debug.LogWarning("[FileDialogHelper] User cancelled or no file selected (EditorUtility).");
            return string.Empty;
        }
#else
        // ==================== STANDALONE WINDOWS BUILD PATH (ORIGINAL NATIVE) ====================
        OpenFileName ofn = new OpenFileName
        {
            title = title,
            initialDir = initialDir,
            filter = filter.Replace("|", "\0") + "\0\0",   // Win32 requires double-null termination
            file = new string(new char[260]),
            maxFile = 260,
            flags = 0x00080000 | 0x00001000 | 0x00000800
        };

        ofn.structSize = Marshal.SizeOf(ofn);
        ofn.dlgOwner = GetForegroundWindow();

        bool success = GetOpenFileName(ofn);

        Debug.Log($"[FileDialogHelper] Win32 result: {(success ? "SUCCESS" : "CANCELLED or FAILED")}");

        if (success)
        {
            string selectedPath = ofn.file;
            Debug.Log($"<color=green>[FileDialogHelper] SUCCESS: Win32 selected → {selectedPath}</color>");
            return selectedPath;
        }

        Debug.LogWarning("[FileDialogHelper] Win32 user cancelled or dialog failed.");
        return string.Empty;
#endif
    }
}
```

### File: `Scripts\IO\PointCSVLoader.cs`
```csharp
﻿// ===============================================
// PointCSVLoader.cs
// PRODUCTION VERSION - Dual Format Pipeline + Block Incremental Isolation
// ===============================================

using UnityEngine;
using System.Collections.Generic;
using System.IO;
using System.Globalization;

/// <summary>
/// Robust CSV loader handling Standard CAD data and PIXXIS raw target scanning data.
/// Features Block-level incremental loading, Overwrite Soft-Lock, and Defensive I/O.
/// </summary>
public class PointCSVLoader : MonoBehaviour
{
    [Header("Core System Dependencies")]
    [SerializeField] private ProjectRootBehaviour projectRoot;
    [SerializeField] private PointDataProcessor dataProcessor;

    [Header("Import Scaling Settings")]
    [Tooltip("Coordinate multiplier. 1.0f means raw file values match Unity units (mm).")]
    public float coordinateScale = 1.0f;

    [Header("=== PIXXIS Reconstruction Overrides ===")]
    [Tooltip("Target block identifier (e.g., 'OC1') to map PIXXIS points to for RPS Solver execution.")]
    public string pixxisDefaultBlock = "OC1";

    [Tooltip("Target joint name designation for tracking clearance topologies.")]
    public string pixxisDefaultJoint = "WJ1-Test";

    private List<Point> designPointsCache = new List<Point>();
    private List<Point> measuredPointsCache = new List<Point>();

    public List<Point> GetDesignPoints() => designPointsCache;
    public List<Point> GetMeasuredPoints() => measuredPointsCache;

    private enum CSVFormatType
    {
        StandardCAD,
        PIXXIS
    }

    // ==========================================
    // OVERWRITE PROTECTION STATE (上書き保護ステート)
    // ==========================================
    private string pendingOverwriteBlock = "";
    private float overwriteTimeout = 0f;

    private void Awake()
    {
        // [変更] ServiceLocator経由で取得
        if (projectRoot == null) ServiceLocator.TryGet(out projectRoot);
    }

    // Public Entry Points for UI Buttons
    public void ImportDesignCSV(string filePath) { ImportSingleCSV(filePath, 0); }
    public void ImportMeasuredCSV(string filePath) { ImportSingleCSV(filePath, 1); }

    public void ClearData()
    {
        designPointsCache.Clear();
        measuredPointsCache.Clear();
        Debug.Log("<color=green>[PointCSVLoader] Internal linear caches cleared safely.</color>");
    }

    /// <summary>
    /// Peeks into the file to identify the Block ID and CSV Format without full memory allocation.
    /// </summary>
    private string PeekBlockID(string filePath, out CSVFormatType detectedFormat)
    {
        detectedFormat = CSVFormatType.StandardCAD;
        try
        {
            using (FileStream fs = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            using (StreamReader reader = new StreamReader(fs))
            {
                string firstLine = reader.ReadLine();
                if (string.IsNullOrEmpty(firstLine)) return string.Empty;

                // Sniff for PIXXIS Format
                if (firstLine.StartsWith("#3D POINT") || firstLine.Contains("TARGET"))
                {
                    detectedFormat = CSVFormatType.PIXXIS;
                    return pixxisDefaultBlock.ToUpper(); // PIXXIS doesn't have internal block IDs, use override
                }

                // Standard CAD Format: Skip header if exists
                string secondLine = firstLine.StartsWith("#") || firstLine.ToLower().StartsWith("block") ? reader.ReadLine() : firstLine;
                if (string.IsNullOrEmpty(secondLine)) return string.Empty;

                string[] columns = secondLine.Split(',');
                if (columns.Length > 0) return columns[0].Trim();
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[PointCSVLoader] Peek failed: {e.Message}");
        }
        return string.Empty;
    }

    private bool IsBlockLoaded(string targetBlockID, int groupID)
    {
        var targetCache = groupID == 0 ? designPointsCache : measuredPointsCache;
        foreach (var p in targetCache)
        {
            if (p.Block == targetBlockID) return true;
        }
        return false;
    }

    /// <summary>
    /// Performs a surgical memory purge [メモリ解放], eradicating ONLY the points 
    /// associated with the conflicting Block ID, leaving other blocks intact.
    /// </summary>
    private void PurgeBlockData(string blockID, int groupID)
    {
        // 1. Scrub the global ProjectData dictionary safely (Fixed: Using System.Guid for dictionary keys)
        if (projectRoot != null && projectRoot.ProjectData != null)
        {
            // Use System.Guid instead of string to match the core dictionary definition
            List<System.Guid> keysToRemove = new List<System.Guid>();

            foreach (var kvp in projectRoot.ProjectData.Points)
            {
                if (kvp.Value.GroupID == groupID && kvp.Value.Block == blockID)
                {
                    keysToRemove.Add(kvp.Key);
                }
            }

            foreach (var key in keysToRemove)
            {
                projectRoot.ProjectData.Points.Remove(key);
            }
        }

        // 2. Remove strictly from local caches using Predicate match
        if (groupID == 0)
            designPointsCache.RemoveAll(p => p.Block == blockID);
        else if (groupID == 1)
            measuredPointsCache.RemoveAll(p => p.Block == blockID);

        // 3. Force 3D Renderers to destroy old spheres and redraw
        // [変更] ServiceLocator経由で取得
        if (ServiceLocator.TryGet<PointRenderer>(out var renderer))
        {
            renderer.RefreshAllPoints();
        }

        // 4. Force Clearance Manager to snap any broken X-Ray lines
        // [変更] ServiceLocator経由で取得
        if (ServiceLocator.TryGet<ClearanceManager>(out var clearanceManager) && projectRoot != null && projectRoot.ProjectData != null)
        {
            clearanceManager.GenerateClearanceVisuals(new List<Point>(projectRoot.ProjectData.Points.Values));
        }
    }

    /// <summary>
    /// Master loading engine using defensive I/O streams and collision detection.
    /// </summary>
    private void ImportSingleCSV(string filePath, int groupID)
    {
        if (!File.Exists(filePath)) return;

        // --------------------------------------------------------
        // 1. FILE PEEK & COLLISION DETECTION (衝突検知)
        // --------------------------------------------------------
        CSVFormatType formatType;
        string incomingBlockID = PeekBlockID(filePath, out formatType);

        if (string.IsNullOrEmpty(incomingBlockID))
        {
            if (UIToastNotifier.Instance != null) UIToastNotifier.Instance.ShowToast("Load Failed: Unable to identify Block ID from file.");
            return;
        }

        if (IsBlockLoaded(incomingBlockID, groupID))
        {
            if (pendingOverwriteBlock == incomingBlockID && Time.time < overwriteTimeout)
            {
                Debug.Log($"<color=yellow>[PointCSVLoader] User authorized overwrite for Block [{incomingBlockID}]. Purging existing data...</color>");
                PurgeBlockData(incomingBlockID, groupID);
                pendingOverwriteBlock = ""; // Reset state
            }
            else
            {
                pendingOverwriteBlock = incomingBlockID;
                overwriteTimeout = Time.time + 5.0f;
                string groupName = groupID == 0 ? "Design" : "Measured";
                string warningMsg = $"Warning: {groupName} Block [{incomingBlockID}] already exists. Click Load again within 5 seconds to overwrite.";

                if (UIToastNotifier.Instance != null) UIToastNotifier.Instance.ShowToast(warningMsg);
                return; // Soft-Lock Intercept
            }
        }

        // --------------------------------------------------------
        // 2. DEFENSIVE FILE I/O & PARSING (ファイルロック防御)
        // --------------------------------------------------------
        try
        {
            int importedCount = 0;
            int rowCount = 0;

            // Stream approach avoids memory bloat and respects Windows FileShare locks
            using (FileStream fs = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            using (StreamReader reader = new StreamReader(fs))
            {
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    rowCount++;
                    if (string.IsNullOrWhiteSpace(line)) continue;

                    // Skip headers flexibly
                    if (rowCount == 1 && (line.StartsWith("#") || line.ToLower().StartsWith("block"))) continue;

                    string[] parts = line.Split(',');
                    Point point = new Point();
                    Vector3 position = Vector3.zero;
                    bool success = false;

                    // ==========================================
                    // PIPELINE A: PIXXIS RECONSTRUCTION
                    // ==========================================
                    if (formatType == CSVFormatType.PIXXIS)
                    {
                        if (parts.Length < 5) continue;
                        string rawIndex = parts[0].Trim();
                        string rawName = parts[1].Trim();

                        if (rawName.ToUpper().Contains("CODE") || !rawName.ToUpper().Contains("TARGET")) continue;

                        point.Name = rawName;
                        point.DisplayID = rawIndex;
                        point.PointType = "Joining";
                        point.PlateType = "A";
                        point.PointPlace = "Target";
                        point.Block = pixxisDefaultBlock.ToUpper();
                        point.Joint = pixxisDefaultJoint;
                        point.TieID = rawIndex;

                        if (!float.TryParse(parts[2], NumberStyles.Float, CultureInfo.InvariantCulture, out float x) ||
                            !float.TryParse(parts[3], NumberStyles.Float, CultureInfo.InvariantCulture, out float y) ||
                            !float.TryParse(parts[4], NumberStyles.Float, CultureInfo.InvariantCulture, out float z))
                        {
                            continue;
                        }
                        position = new Vector3(x, y, z) * coordinateScale;
                        success = true;
                    }
                    // ==========================================
                    // PIPELINE B: STANDARD CAD
                    // ==========================================
                    else
                    {
                        if (parts.Length < 11) continue;
                        point.Block = parts[0].Trim();
                        point.Joint = parts[1].Trim();
                        point.PointType = string.IsNullOrEmpty(parts[2].Trim()) ? "Reference" : parts[2].Trim();
                        point.PlateType = parts[3].Trim();
                        point.PointPlace = parts[4].Trim();
                        point.DisplayID = parts[5].Trim();
                        point.TieID = parts[6].Trim();
                        point.Name = parts[7].Trim();

                        if (!float.TryParse(parts[8], NumberStyles.Float, CultureInfo.InvariantCulture, out float x) ||
                            !float.TryParse(parts[9], NumberStyles.Float, CultureInfo.InvariantCulture, out float y) ||
                            !float.TryParse(parts[10], NumberStyles.Float, CultureInfo.InvariantCulture, out float z))
                        {
                            continue;
                        }
                        position = new Vector3(x, y, z) * coordinateScale;
                        success = true;
                    }

                    if (!success) continue;

                    point.GroupID = groupID;

                    if (groupID == 0)
                    {
                        point.DesignPosition = position;
                        designPointsCache.Add(point);
                    }
                    else
                    {
                        point.MeasurePosition = position;
                        point.DesignPosition = position;
                        measuredPointsCache.Add(point);
                    }

                    if (!projectRoot.ProjectData.Points.ContainsKey(point.ID))
                    {
                        projectRoot.ProjectData.Points.Add(point.ID, point);
                        importedCount++;
                    }
                }
            }

            // --------------------------------------------------------
            // 3. CASCADE EVENT TRIGGERS (連動コンポーネント更新)
            // --------------------------------------------------------
            if (groupID == 1)
            {
                var allPoints = new List<Point>(designPointsCache);
                allPoints.AddRange(measuredPointsCache);

                // [変更] ServiceLocator経由で取得
                if (ServiceLocator.TryGet<ClearanceManager>(out var clearanceManager))
                {
                    clearanceManager.GenerateClearanceVisuals(allPoints);
                }
            }

            if (dataProcessor != null) dataProcessor.ProcessImportedPoints(groupID);

            Debug.Log($"<color=green>[PointCSVLoader] Success: Loaded {importedCount} elements into Block [{incomingBlockID}] ({formatType}).</color>");
        }
        catch (IOException e)
        {
            if (e.HResult == unchecked((int)0x80070020))
            {
                string msg = "Load Failed: The CSV file is currently in use by Excel. Please close it and try again.";
                if (UIToastNotifier.Instance != null) UIToastNotifier.Instance.ShowToast(msg);
            }
            else
            {
                string msg = $"Load Failed: Unknown IO error - {e.Message}";
                if (UIToastNotifier.Instance != null) UIToastNotifier.Instance.ShowToast(msg);
            }
        }
        catch (System.Exception e)
        {
            string msg = "Load Failed: The CSV file format is corrupted.";
            Debug.LogError($"{msg} Details: {e.Message}");
            if (UIToastNotifier.Instance != null) UIToastNotifier.Instance.ShowToast(msg);
        }
    }
}
```

### File: `Scripts\Math\ConstrainedMultiAlignment_unity.cs`
```csharp
﻿

using System;
using System.Collections.Generic;
using SymEQ;   // Sym_EQ の namespace
using LSE;     // LSE_alignment / Constants の namespace（同一アセンブリ想定）

namespace LSE
{
    public class ConstrainedMultiBlockAlignment
    {
        // =========================================
        // SolveResult（収束情報）
        // =========================================
        public enum SolveStatus
        {
            Ok,
            NoBlocks,
            BlockInitFailed,
            BlockInitNotConverged,
            NoActiveUnknowns,
            PointIdNotFound,
            TieIdNotFound,
            ConstraintInvalid,
            LinearSolveFailed,
            NotConverged
        }

        public enum SolvePhase
        {
            None,
            PreSolveBlocks,
            AssembleNormal,
            AssembleConstraints,
            LinearSolve,
            ApplyUpdate,
            ConvergenceCheck
        }

        public sealed class SolveResult
        {
            public SolveStatus Status = SolveStatus.NotConverged;
            public SolvePhase Phase = SolvePhase.None;
            public int Iterations = 0;
            public double MaxAbsDx = double.PositiveInfinity;
            public double MaxAbsConstraint = double.PositiveInfinity;
            public string Message = "";
        }

        public struct BlockTransform
        {
            public string BlockName;

            // Translation
            public double Tx;
            public double Ty;
            public double Tz;

            // Rotation（LSE_alignment の定義のまま）
            // ※ Unityに渡すときに符号・順序を変換する
            public double Rx;
            public double Ry;
            public double Rz;

            // Scale
            public double Scale;
        }

        // =========================================
        // RMS（観測残差 v のみ）
        // =========================================
        public struct RmsResult
        {
            public int UsedComponentCount;  // swで有効な成分数（X/Y/Zの合計）
            public int PointCount;          // 点数
            public double Rms3D;            // sqrt( sum(v^2) / UsedComponentCount )
            public double RmsX;             // sqrt( sum(vx^2) / usedX )
            public double RmsY;
            public double RmsZ;
            public double MaxAbs;           // 有効成分の最大絶対値
        }

        // =========================================
        // 拘束の最終結果（距離拘束）
        // =========================================
        public struct DistanceConstraintResult
        {
            public string BlockA;
            public int PointIdA;
            public int IndexA;
            public double Ax, Ay, Az;

            public string BlockB;
            public int PointIdB;
            public int IndexB;
            public double Bx, By, Bz;

            public double TargetDistance;
            public double ActualDistance;
            public double Residual;  // Actual - Target
        }

        // =========================================
        // 設定
        // =========================================
        public bool EnablePreSolveBlocks = true;
        public int MaxIterations = 30;
        public double StepTolerance = 1e-8;
        public double ConstraintTolerance = 1e-8;
        public double Beta = 1.0;

        // =========================================
        // 線形ソルバ（対称半格納）: Sym_EQ
        // =========================================
        interface ILinearSolver
        {
            void Reset(int n);
            void AddA(int i, int j, double v); // 対称上三角へ加算（i<=j）
            void SetB(int i, double v);
            void AddB(int i, double v);
            bool Solve(out double[] x);
        }

        sealed class SymEqLinearSolver : ILinearSolver
        {
            Sym_EQ eq = new Sym_EQ();
            int n;

            public void Reset(int n_)
            {
                n = n_;
                eq = new Sym_EQ();
                eq.Set_Size(n);
                for (int i = 0; i < n; i++) eq.Set_Bc(i, 0);
            }

            public void AddA(int i, int j, double v)
            {
                if (i > j) (i, j) = (j, i);
                eq.Add_A(i, j, v);
            }

            public void SetB(int i, double v) => eq.Set_B(i, v);
            public void AddB(int i, double v) => eq.Add_B(i, v);

            public bool Solve(out double[] x)
            {
                if (!eq.LUDecomp() || !eq.FowardSub() || !eq.BackSub())
                {
                    x = Array.Empty<double>();
                    return false;
                }
                x = eq.X ?? Array.Empty<double>();
                return x.Length == n;
            }
        }

        // =========================================
        // Block（LSE_alignment保持 + ID/tieId対応）
        // =========================================
        sealed class Block
        {
            public string Name;
            public LSE_alignment Lse;

            public int PointCount;
            public int[,] Sw;        // [N,3] 0:使用 1:無視（RMS集計にも使用）
            public int[] Flg7;       // 0:推定 1:固定（全体Solve用）

            public int[] ActiveMap = new int[7]; // active -> global index, fixed -> -1
            public int ActiveCount;

            public int[] PointIds;   // index -> pointId
            public int[] TieIds;     // index -> tieId
            public Dictionary<int, int> IdToIndex = new Dictionary<int, int>();
            public Dictionary<int, int> TieToIndex = new Dictionary<int, int>();

            public Block(string name, LSE_alignment lse, int pointCount, int[,] sw, int[] flg7, int[] pointIds, int[] tieIds)
            {
                Name = name;
                Lse = lse;

                PointCount = pointCount;
                Sw = sw;
                Flg7 = (int[])flg7.Clone();

                // active map（後で RebuildActiveMaps で再割当）
                for (int i = 0; i < 7; i++)
                    ActiveMap[i] = (Flg7[i] == 1) ? -1 : 0;

                PointIds = pointIds;
                TieIds = tieIds;

                // dict
                for (int i = 0; i < pointCount; i++)
                {
                    int pid = pointIds[i];
                    if (pid != 0 && !IdToIndex.ContainsKey(pid))
                        IdToIndex.Add(pid, i);

                    int tid = tieIds[i];
                    if (tid != 0 && !TieToIndex.ContainsKey(tid))
                        TieToIndex.Add(tid, i);
                }
            }
        }

        readonly List<Block> blocks = new List<Block>();
        readonly Dictionary<string, int> blockNameToId = new Dictionary<string, int>();

        // =========================================
        // 距離拘束（内部保持）
        // =========================================
        sealed class DistanceConstraint
        {
            public int BlockA;
            public int IndexA;
            public int PointIdA;

            public int BlockB;
            public int IndexB;
            public int PointIdB;

            public double L;
        }

        readonly List<DistanceConstraint> distConstraints = new List<DistanceConstraint>();

        readonly ILinearSolver solver = new SymEqLinearSolver();

        // =========================================
        // ブロック追加（ID/tieId を渡す）
        // =========================================
        public int AddBlock(
            string blockName,
            double[,] xb,
            double[,] xd,
            int[,] sw,
            int[] flg7,
            int[] pointIds,
            int[] tieIds
        )
        {
            if (xb == null || xd == null) throw new ArgumentNullException("xb/xd");
            int n = xb.GetLength(0);

            if (xd.GetLength(0) != n || xb.GetLength(1) != 3 || xd.GetLength(1) != 3)
                throw new ArgumentException("xb/xd shape must be [N,3] and counts must match.");

            if (sw == null) sw = new int[n, 3]; // 全使用
            if (flg7 == null || flg7.Length != 7) flg7 = new int[7]; // 全自由

            if (pointIds == null || pointIds.Length != n) pointIds = new int[n];
            if (tieIds == null || tieIds.Length != n) tieIds = new int[n];

            var lse = new LSE_alignment(n);
            lse.Set_Xb(xb);
            lse.Set_Xd(xd);
            lse.Set_sw(sw);
            lse.Set_flg(flg7);

            var blk = new Block(blockName, lse, n, sw, flg7, pointIds, tieIds);

            int id = blocks.Count;
            blocks.Add(blk);
            blockNameToId[blockName] = id;

            RebuildActiveMaps();
            return id;
        }

        // =========================================
        // 拘束追加（ブロック名 + pointId）
        // =========================================
        public SolveResult AddDistanceConstraintByPointId(
            string blockNameA, int pointIdA,
            string blockNameB, int pointIdB,
            double length)
        {
            var res = new SolveResult { Status = SolveStatus.Ok, Phase = SolvePhase.None, Message = "OK" };

            if (!blockNameToId.TryGetValue(blockNameA, out int a) ||
                !blockNameToId.TryGetValue(blockNameB, out int b))
            {
                res.Status = SolveStatus.NoBlocks;
                res.Message = "Block name not found.";
                return res;
            }

            if (!blocks[a].IdToIndex.TryGetValue(pointIdA, out int ia) ||
                !blocks[b].IdToIndex.TryGetValue(pointIdB, out int ib))
            {
                res.Status = SolveStatus.PointIdNotFound;
                res.Message = "PointId not found in one of blocks.";
                return res;
            }

            distConstraints.Add(new DistanceConstraint
            {
                BlockA = a,
                IndexA = ia,
                PointIdA = pointIdA,
                BlockB = b,
                IndexB = ib,
                PointIdB = pointIdB,
                L = length
            });

            res.Message = "Distance constraint added.";
            return res;
        }

        // tieId版（同じtieIdの点を拘束）
        public SolveResult AddDistanceConstraintByTieId(
            string blockNameA, int tieId,
            string blockNameB,
            double length)
        {
            var res = new SolveResult { Status = SolveStatus.Ok, Phase = SolvePhase.None, Message = "OK" };

            if (!blockNameToId.TryGetValue(blockNameA, out int a) ||
                !blockNameToId.TryGetValue(blockNameB, out int b))
            {
                res.Status = SolveStatus.NoBlocks;
                res.Message = "Block name not found.";
                return res;
            }

            if (!blocks[a].TieToIndex.TryGetValue(tieId, out int ia) ||
                !blocks[b].TieToIndex.TryGetValue(tieId, out int ib))
            {
                res.Status = SolveStatus.TieIdNotFound;
                res.Message = "TieId not found in one of blocks.";
                return res;
            }

            int pidA = blocks[a].PointIds[ia];
            int pidB = blocks[b].PointIds[ib];

            distConstraints.Add(new DistanceConstraint
            {
                BlockA = a,
                IndexA = ia,
                PointIdA = pidA,
                BlockB = b,
                IndexB = ib,
                PointIdB = pidB,
                L = length
            });

            res.Message = "Distance constraint added by tieId.";
            return res;
        }

        // =========================================
        // Solve（PreSolveは flg 無視で必ず Cal）
        // =========================================
        public SolveResult Solve()
        {
            var res = new SolveResult();

            if (blocks.Count == 0)
            {
                res.Status = SolveStatus.NoBlocks;
                res.Message = "No blocks registered.";
                return res;
            }

            // -------- Phase 0: 単独LSE（flg無視で必ず解く）
            if (EnablePreSolveBlocks)
            {
                res.Phase = SolvePhase.PreSolveBlocks;

                for (int bi = 0; bi < blocks.Count; bi++)
                {
                    var blk = blocks[bi];

                    int[] backup = (int[])blk.Flg7.Clone();
                    int[] flgFree = new int[7]; // 全自由度（全部0）
                    blk.Lse.Set_flg(flgFree);

                    int r = blk.Lse.Cal();

                    blk.Lse.Set_flg(backup);

                    if (r == Constants.OTHER_ERROR)
                    {
                        res.Status = SolveStatus.BlockInitFailed;
                        res.Message = $"Block {blk.Name}: PreSolve failed (OTHER_ERROR).";
                        return res;
                    }
                    if (r == Constants.LOOP_OVER)
                    {
                        res.Status = SolveStatus.BlockInitNotConverged;
                        res.Message = $"Block {blk.Name}: PreSolve not converged (LOOP_OVER).";
                        return res;
                    }
                }
            }

            // unknown count
            RebuildActiveMaps();
            int nx = TotalUnknowns();
            if (nx == 0)
            {
                res.Status = SolveStatus.NoActiveUnknowns;
                res.Message = "No active unknowns (all DoFs fixed).";
                return res;
            }

            int nc = distConstraints.Count;
            int N = nx + nc;

            for (int iter = 0; iter < MaxIterations; iter++)
            {
                res.Iterations = iter;

                // -------- 1) 正規方程式集約
                res.Phase = SolvePhase.AssembleNormal;
                solver.Reset(N);

                for (int bi = 0; bi < blocks.Count; bi++)
                {
                    var blk = blocks[bi];
                    blk.Lse.BuildNormalEq(out var H, out var g);

                    for (int i = 0; i < 7; i++)
                    {
                        int gi = blk.ActiveMap[i];
                        if (gi < 0) continue;

                        solver.AddB(gi, g[i]);

                        for (int j = i; j < 7; j++)
                        {
                            int gj = blk.ActiveMap[j];
                            if (gj < 0) continue;
                            solver.AddA(gi, gj, H[i, j]);
                        }
                    }
                }

                // -------- 2) 距離拘束追加（KKT）
                res.Phase = SolvePhase.AssembleConstraints;

                int row = nx;
                double maxC = 0.0;

                for (int k = 0; k < distConstraints.Count; k++)
                {
                    var dc = distConstraints[k];
                    var A = blocks[dc.BlockA];
                    var B = blocks[dc.BlockB];

                    // c = ||pA - pB|| - L
                    A.Lse.GetTransformedPoint(dc.IndexA, out double ax, out double ay, out double az);
                    B.Lse.GetTransformedPoint(dc.IndexB, out double bx, out double by, out double bz);

                    double dx = ax - bx, dy = ay - by, dz = az - bz;
                    double dist = Math.Sqrt(dx * dx + dy * dy + dz * dz);
                    double c = dist - dc.L;

                    solver.SetB(row, -c);
                    maxC = Math.Max(maxC, Math.Abs(c));

                    // Jacobian: u^T * JpA  - u^T * JpB
                    double inv = (dist < 1e-12) ? 1e12 : 1.0 / dist;
                    double ux = dx * inv, uy = dy * inv, uz = dz * inv;

                    A.Lse.GetPointJacobian(dc.IndexA, out var JpA); // 3x7
                    B.Lse.GetPointJacobian(dc.IndexB, out var JpB); // 3x7

                    for (int p = 0; p < 7; p++)
                    {
                        int colA = A.ActiveMap[p];
                        if (colA >= 0)
                        {
                            double v = ux * JpA[0, p] + uy * JpA[1, p] + uz * JpA[2, p];
                            if (v != 0.0) solver.AddA(colA, row, v);
                        }

                        int colB = B.ActiveMap[p];
                        if (colB >= 0)
                        {
                            double v = -(ux * JpB[0, p] + uy * JpB[1, p] + uz * JpB[2, p]);
                            if (v != 0.0) solver.AddA(colB, row, v);
                        }
                    }

                    row++;
                }

                res.MaxAbsConstraint = maxC;

                // -------- 3) 解く
                res.Phase = SolvePhase.LinearSolve;

                if (!solver.Solve(out var sol))
                {
                    res.Status = SolveStatus.LinearSolveFailed;
                    res.Message = "Linear solve failed (singular / pivot zero).";
                    return res;
                }

                // -------- 4) 適用
                res.Phase = SolvePhase.ApplyUpdate;

                double maxDx = 0.0;

                for (int bi = 0; bi < blocks.Count; bi++)
                {
                    var blk = blocks[bi];
                    double[] dX7 = new double[7];

                    for (int i = 0; i < 7; i++)
                    {
                        int gi = blk.ActiveMap[i];
                        dX7[i] = (gi >= 0) ? sol[gi] : 0.0;
                        maxDx = Math.Max(maxDx, Math.Abs(dX7[i]));
                    }

                    blk.Lse.ApplyDelta(dX7, Beta);
                }

                res.MaxAbsDx = maxDx;

                // -------- 5) 収束判定
                res.Phase = SolvePhase.ConvergenceCheck;

                bool stepOk = maxDx < StepTolerance;
                bool conOk = (distConstraints.Count == 0) || (maxC < ConstraintTolerance);

                if (stepOk && conOk)
                {
                    res.Status = SolveStatus.Ok;
                    res.Message = "Converged.";
                    return res;
                }
            }

            res.Status = SolveStatus.NotConverged;
            res.Message = "MaxIterations reached.";
            return res;
        }

        // =========================================
        // RMS API（必須）
        // =========================================

        public RmsResult GetBlockRms(string blockName)
        {
            if (!blockNameToId.TryGetValue(blockName, out int id))
                return new RmsResult { UsedComponentCount = 0, PointCount = 0, MaxAbs = double.NaN };

            return ComputeRmsForBlock(blocks[id]);
        }

        public RmsResult GetGlobalRms()
        {
            double sx2 = 0, sy2 = 0, sz2 = 0, sAll = 0;
            double maxAbs = 0;
            int usedX = 0, usedY = 0, usedZ = 0, usedAll = 0;
            int pointCount = 0;

            for (int bi = 0; bi < blocks.Count; bi++)
            {
                var r = ComputeRmsRaw(blocks[bi], out var raw);
                // raw: sums/counts を合算
                sx2 += raw.sx2; sy2 += raw.sy2; sz2 += raw.sz2; sAll += raw.sAll;
                usedX += raw.usedX; usedY += raw.usedY; usedZ += raw.usedZ; usedAll += raw.usedAll;
                maxAbs = Math.Max(maxAbs, raw.maxAbs);
                pointCount += blocks[bi].PointCount;
            }

            return new RmsResult
            {
                PointCount = pointCount,
                UsedComponentCount = usedAll,
                RmsX = (usedX > 0) ? Math.Sqrt(sx2 / usedX) : 0,
                RmsY = (usedY > 0) ? Math.Sqrt(sy2 / usedY) : 0,
                RmsZ = (usedZ > 0) ? Math.Sqrt(sz2 / usedZ) : 0,
                Rms3D = (usedAll > 0) ? Math.Sqrt(sAll / usedAll) : 0,
                MaxAbs = maxAbs
            };
        }

        // =========================================
        // 拘束結果（最終座標＆実距離）
        // =========================================
        public List<DistanceConstraintResult> GetDistanceConstraintResults()
        {
            var list = new List<DistanceConstraintResult>(distConstraints.Count);

            for (int k = 0; k < distConstraints.Count; k++)
            {
                var dc = distConstraints[k];
                var A = blocks[dc.BlockA];
                var B = blocks[dc.BlockB];

                A.Lse.GetTransformedPoint(dc.IndexA, out double ax, out double ay, out double az);
                B.Lse.GetTransformedPoint(dc.IndexB, out double bx, out double by, out double bz);

                double dx = ax - bx, dy = ay - by, dz = az - bz;
                double dist = Math.Sqrt(dx * dx + dy * dy + dz * dz);

                list.Add(new DistanceConstraintResult
                {
                    BlockA = A.Name,
                    PointIdA = dc.PointIdA,
                    IndexA = dc.IndexA,
                    Ax = ax,
                    Ay = ay,
                    Az = az,

                    BlockB = B.Name,
                    PointIdB = dc.PointIdB,
                    IndexB = dc.IndexB,
                    Bx = bx,
                    By = by,
                    Bz = bz,

                    TargetDistance = dc.L,
                    ActualDistance = dist,
                    Residual = dist - dc.L
                });
            }

            return list;
        }

        // =========================================
        // internal helpers
        // =========================================
        void RebuildActiveMaps()
        {
            // block毎に global index を割り当て直す
            int off = 0;
            for (int bi = 0; bi < blocks.Count; bi++)
            {
                var blk = blocks[bi];
                int c = 0;
                for (int i = 0; i < 7; i++)
                {
                    if (blk.Flg7[i] == 0)
                        blk.ActiveMap[i] = off + c++;
                    else
                        blk.ActiveMap[i] = -1;
                }
                blk.ActiveCount = c;
                off += c;
            }
        }

        int TotalUnknowns()
        {
            int s = 0;
            for (int bi = 0; bi < blocks.Count; bi++)
                s += blocks[bi].ActiveCount;
            return s;
        }

        // RMS内部計算：swで有効な成分だけ使う
        RmsResult ComputeRmsForBlock(Block blk)
        {
            ComputeRmsRaw(blk, out var raw);

            return new RmsResult
            {
                PointCount = blk.PointCount,
                UsedComponentCount = raw.usedAll,
                RmsX = (raw.usedX > 0) ? Math.Sqrt(raw.sx2 / raw.usedX) : 0,
                RmsY = (raw.usedY > 0) ? Math.Sqrt(raw.sy2 / raw.usedY) : 0,
                RmsZ = (raw.usedZ > 0) ? Math.Sqrt(raw.sz2 / raw.usedZ) : 0,
                Rms3D = (raw.usedAll > 0) ? Math.Sqrt(raw.sAll / raw.usedAll) : 0,
                MaxAbs = raw.maxAbs
            };
        }

        // raw sums
        struct RmsRaw
        {
            public double sx2, sy2, sz2, sAll;
            public int usedX, usedY, usedZ, usedAll;
            public double maxAbs;
        }

        // v取得 -> swでマスク -> 二乗和集計
        bool ComputeRmsRaw(Block blk, out RmsRaw raw)
        {
            raw = new RmsRaw();

            int n = blk.PointCount;
            var v = new double[n, 3];
            blk.Lse.Get_v(ref v);  // 既存API（Program.csで使用されている）前提

            for (int i = 0; i < n; i++)
            {
                // sw==0 の成分のみ使用（swがnullのときは全使用）
                bool useX = (blk.Sw == null) ? true : (blk.Sw[i, 0] == 0);
                bool useY = (blk.Sw == null) ? true : (blk.Sw[i, 1] == 0);
                bool useZ = (blk.Sw == null) ? true : (blk.Sw[i, 2] == 0);

                if (useX)
                {
                    double vx = v[i, 0];
                    raw.sx2 += vx * vx;
                    raw.sAll += vx * vx;
                    raw.usedX++;
                    raw.usedAll++;
                    raw.maxAbs = Math.Max(raw.maxAbs, Math.Abs(vx));
                }
                if (useY)
                {
                    double vy = v[i, 1];
                    raw.sy2 += vy * vy;
                    raw.sAll += vy * vy;
                    raw.usedY++;
                    raw.usedAll++;
                    raw.maxAbs = Math.Max(raw.maxAbs, Math.Abs(vy));
                }
                if (useZ)
                {
                    double vz = v[i, 2];
                    raw.sz2 += vz * vz;
                    raw.sAll += vz * vz;
                    raw.usedZ++;
                    raw.usedAll++;
                    raw.maxAbs = Math.Max(raw.maxAbs, Math.Abs(vz));
                }
            }

            return true;
        }
        public BlockTransform GetBlockTransform(string blockName)
        {
            // ブロック名 → blockId
            if (!blockNameToId.TryGetValue(blockName, out int blockId))
            {
                throw new ArgumentException($"Block '{blockName}' not found.");
            }

            var blk = blocks[blockId];

            // LSE_alignment が保持している最終状態量 X を取得
            // X = [tx, ty, tz, rx, ry, rz, scale]
            double[] X = new double[7];
            blk.Lse.Get_X(ref X);

            // そのまま返す（Unity依存変換は一切しない）
            return new BlockTransform
            {
                BlockName = blk.Name,

                Tx = X[0],
                Ty = X[1],
                Tz = X[2],

                Rx = X[3],
                Ry = X[4],
                Rz = X[5],

                Scale = X[6]
            };
        }
    }
}



```

### File: `Scripts\Math\DeformationMathCore.cs`
```csharp
﻿// ===============================================
// DeformationMathCore.cs
// PRODUCTION VERSION - N-Point Coplanarity Detection & Kabsch-Horn (idx0 Fixed)
// ===============================================

using System.Collections.Generic;
using UnityEngine;

public static class DeformationMathCore
{
    // Tolerance for coplanarity detection. 
    private const float COPLANAR_TOLERANCE = 1e-2f;

    /// <summary>
    /// Calculates the optimal Rigid Body transformation matrix.
    /// </summary>
    public static Matrix4x4 CalculateBestFitTransform(List<Vector3> designPoints, List<Vector3> measuredPoints)
    {
        if (designPoints.Count != measuredPoints.Count || designPoints.Count < 3)
        {
            Debug.LogError("[MathCore] Invalid point sets. Must have at least 3 matching points.");
            return Matrix4x4.identity;
        }

        List<Vector3> dPts = new List<Vector3>(designPoints);
        List<Vector3> mPts = new List<Vector3>(measuredPoints);

        // 1. Critical Defense: N-Point Coplanarity Detection
        Ensure3DVolume(dPts, mPts);

        // 2. Calculate Centroids
        Vector3 dCentroid = GetCentroid(dPts);
        Vector3 mCentroid = GetCentroid(mPts);

        // 3. Build the Cross-Covariance Matrix
        float[,] H = new float[3, 3];
        for (int i = 0; i < dPts.Count; i++)
        {
            Vector3 dA = dPts[i] - dCentroid;
            Vector3 mA = mPts[i] - mCentroid;

            H[0, 0] += dA.x * mA.x; H[0, 1] += dA.x * mA.y; H[0, 2] += dA.x * mA.z;
            H[1, 0] += dA.y * mA.x; H[1, 1] += dA.y * mA.y; H[1, 2] += dA.y * mA.z;
            H[2, 0] += dA.z * mA.x; H[2, 1] += dA.z * mA.y; H[2, 2] += dA.z * mA.z;
        }

        // 4. Extract Optimal Rotation
        Quaternion optimalRotation = ExtractRotationFromCovariance(H);

        // 5. Calculate Translation
        Vector3 translation = mCentroid - (optimalRotation * dCentroid);

        // 6. Construct Matrix
        return Matrix4x4.TRS(translation, optimalRotation, Vector3.one);
    }

    /// <summary>
    /// Dynamically detects if N points are coplanar and injects a virtual anchor.
    /// </summary>
    private static void Ensure3DVolume(List<Vector3> dPts, List<Vector3> mPts)
    {
        int count = dPts.Count;

        int idx0 = 0;
        int idx1 = -1;
        float maxDistSq = 0f;

        for (int i = 0; i < count; i++)
        {
            if (i == idx0) continue;
            float distSq = (dPts[i] - dPts[idx0]).sqrMagnitude;
            if (distSq > maxDistSq)
            {
                maxDistSq = distSq;
                idx1 = i;
            }
        }

        if (idx1 == -1 || maxDistSq < 1e-6f) return;

        int idx2 = -1;
        float maxCrossSq = 0f;
        Vector3 dNormal = Vector3.zero;
        Vector3 dir1 = dPts[idx1] - dPts[idx0];

        for (int i = 0; i < count; i++)
        {
            if (i == idx0 || i == idx1) continue;
            Vector3 dir2 = dPts[i] - dPts[idx0];
            Vector3 cross = Vector3.Cross(dir1, dir2);
            float crossSq = cross.sqrMagnitude;

            if (crossSq > maxCrossSq)
            {
                maxCrossSq = crossSq;
                idx2 = i;
                dNormal = cross;
            }
        }

        if (idx2 == -1 || maxCrossSq < 1e-6f) return;

        dNormal = dNormal.normalized;

        bool isCoplanar = true;
        for (int i = 0; i < count; i++)
        {
            if (i == idx0 || i == idx1 || i == idx2) continue;

            float distanceToPlane = Mathf.Abs(Vector3.Dot(dPts[i] - dPts[idx0], dNormal));
            if (distanceToPlane > COPLANAR_TOLERANCE)
            {
                isCoplanar = false;
                break;
            }
        }

        if (isCoplanar)
        {
            Vector3 mDir1 = mPts[idx1] - mPts[idx0];
            Vector3 mDir2 = mPts[idx2] - mPts[idx0];
            Vector3 mNormal = Vector3.Cross(mDir1, mDir2).normalized;

            float offsetDist = Mathf.Sqrt(maxDistSq);

            dPts.Add(dPts[idx0] + dNormal * offsetDist);
            mPts.Add(mPts[idx0] + mNormal * offsetDist);

            Debug.LogWarning($"[MathCore] Detected {count} coplanar points. Injected Virtual Anchor to enforce 3D volume.");
        }
    }

    private static Vector3 GetCentroid(List<Vector3> points)
    {
        Vector3 sum = Vector3.zero;
        foreach (Vector3 p in points) sum += p;
        return sum / points.Count;
    }

    private static Quaternion ExtractRotationFromCovariance(float[,] H)
    {
        float[,] K = new float[4, 4];
        K[0, 0] = H[0, 0] + H[1, 1] + H[2, 2];
        K[0, 1] = H[1, 2] - H[2, 1];
        K[0, 2] = H[2, 0] - H[0, 2];
        K[0, 3] = H[0, 1] - H[1, 0];

        K[1, 0] = K[0, 1];
        K[1, 1] = H[0, 0] - H[1, 1] - H[2, 2];
        K[1, 2] = H[0, 1] + H[1, 0];
        K[1, 3] = H[0, 2] + H[2, 0];

        K[2, 0] = K[0, 2];
        K[2, 1] = K[1, 2];
        K[2, 2] = -H[0, 0] + H[1, 1] - H[2, 2];
        K[2, 3] = H[1, 2] + H[2, 1];

        K[3, 0] = K[0, 3];
        K[3, 1] = K[1, 3];
        K[3, 2] = K[2, 3];
        K[3, 3] = -H[0, 0] - H[1, 1] + H[2, 2];

        Vector4 q = new Vector4(1, 0, 0, 0);
        for (int i = 0; i < 20; i++)
        {
            float q0 = K[0, 0] * q.x + K[0, 1] * q.y + K[0, 2] * q.z + K[0, 3] * q.w;
            float q1 = K[1, 0] * q.x + K[1, 1] * q.y + K[1, 2] * q.z + K[1, 3] * q.w;
            float q2 = K[2, 0] * q.x + K[2, 1] * q.y + K[2, 2] * q.z + K[2, 3] * q.w;
            float q3 = K[3, 0] * q.x + K[3, 1] * q.y + K[3, 2] * q.z + K[3, 3] * q.w;

            q = new Vector4(q0, q1, q2, q3);
            q.Normalize();
        }

        return new Quaternion(q.y, q.z, q.w, q.x);
    }
}
```

### File: `Scripts\Math\LSE_alignment.cs`
```csharp
﻿using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

namespace LSE
{
    static class Constants
    {
        public const int LEFT_HAND_SYSTEM = 1;   // =1:Left Hand System for Unity  ≠1:Right Hand sysytem for close Photgrammetry   
        public const double Pi = 3.14159;
        public const int NORMAL_END = 0;
        public const int LOOP_OVER = 1;
        public const int OTHER_ERROR = 2;
        public const double BIG_NUM = 1.0e+30;
    }
    /// <summary>
    /// 3次元ベクトルを表す構造体。X, Y, Z の各成分を持ち、
    /// ベクトル演算（加算、減算、スカラー倍、正規化、外積、内積）を提供する。
    /// Unityの Vector3 に類似するが、依存せずに汎用C#で実装。
    /// </summary>
    public struct Vec3
    {
        public double X, Y, Z;

        public Vec3(double x, double y, double z) { X = x; Y = y; Z = z; }

        /// <summary>ベクトルの減算（a - b）</summary>
        public static Vec3 operator -(Vec3 a, Vec3 b) => new Vec3(a.X - b.X, a.Y - b.Y, a.Z - b.Z);

        /// <summary>ベクトルの加算（a + b）</summary>
        public static Vec3 operator +(Vec3 a, Vec3 b) => new Vec3(a.X + b.X, a.Y + b.Y, a.Z + b.Z);

        /// <summary>スカラー倍（s * v）</summary>
        public static Vec3 operator *(double s, Vec3 v) => new Vec3(s * v.X, s * v.Y, s * v.Z);

        /// <summary>ベクトルのノルム（長さ）を計算</summary>
        public double Norm() => Math.Sqrt(X * X + Y * Y + Z * Z);

        /// <summary>ベクトルを正規化（単位ベクトル化）</summary>
        public Vec3 Normalize() => (Norm() > 1e-12) ? (1.0 / Norm()) * this : new Vec3(0, 0, 0);

        /// <summary>
        /// 外積（クロス積）を計算。
        /// 左手座標系（Unity準拠）で使用する場合、順序に注意：
        /// Vec3.Cross(P3 - P1, P2 - P1) のように、右手系とは逆順で法線ベクトルを構成。
        /// </summary>
        public static Vec3 Cross(Vec3 a, Vec3 b) =>
            new Vec3(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X);

        /// <summary>内積（ドット積）を計算</summary>
        public static double Dot(Vec3 a, Vec3 b) => a.X * b.X + a.Y * b.Y + a.Z * b.Z;
    }
    public static class RigidTransformEulerLSE
    {
        // LSE_alignment の回転順序（Ry * Rx * Rz）に対応した Euler 分解
        // 戻り値は (X, Y, Z) [rad]
        public static Vector3 ExtractEuler_LSE_RyRxRz(Matrix4x4 R)
        {
            // 行列要素（LSE_alignment の RR と対応）
            double r00 = R.m00, r01 = R.m01, r02 = R.m02;
            double r10 = R.m10, r11 = R.m11, r12 = R.m12;
            double r20 = R.m20, r21 = R.m21, r22 = R.m22;

            // --- X の計算 ---
            // RR[1,2] = r12 = sx
            double sx = r12;
            double X = Math.Asin(sx);
            double cx = Math.Cos(X);

            double Y, Z;

            // gimbal lock 対策
            if (Math.Abs(cx) < 1e-6)
            {
                // cx ≈ 0 → X ≈ ±90°
                // この場合、Y と Z は一意に決まらないので、
                // ここでは簡易的に Z = 0 として Y を決める
                // RR[2,0], RR[0,0] などから Y を近似的に求める
                Y = Math.Atan2(r20, r00);
                Z = 0.0;
            }
            else
            {
                // --- Y の計算 ---
                // RR[0,2] = r02 = -sy * cx
                // RR[2,2] = r22 =  cy * cx
                double sy = -r02 / cx;
                double cy = r22 / cx;
                Y = Math.Atan2(sy, cy);

                // --- Z の計算 ---
                // RR[1,0] = r10 = -cx * sz
                // RR[1,1] = r11 =  cx * cz
                double sz = -r10 / cx;
                double cz = r11 / cx;
                Z = Math.Atan2(sz, cz);
            }

            return new Vector3((float)X, (float)Y, (float)Z);
        }
    }


    public static class RigidTransform
    {
        /// <summary>
        /// 3点からローカル座標系の基底ベクトル（X, Y, Z）を構築する。
        /// 左手座標系（Unity準拠）に従い、Z軸は (P3 - P1) × (P2 - P1) で定義。
        /// </summary>
        public static void BuildBasis(Vec3 p1, Vec3 p2, Vec3 p3, out Vec3 x, out Vec3 y, out Vec3 z)
        {
            x = (p2 - p1).Normalize(); // X軸：P1→P2方向
            z = Vec3.Cross(p3 - p1, p2 - p1).Normalize(); // Z軸：左手系の外積順序
            y = Vec3.Cross(z, x); // Y軸：Z × X（左手系でも右手系でも同様）
        }

        /// <summary>
        /// 基底ベクトル（X, Y, Z）を列ベクトルとして並べた3×3回転行列を構築。
        /// 列ベクトル形式（右掛け）を前提とし、UnityやOpenGLと同様の構成。
        /// </summary>
        public static double[,] MakeRotationMatrix(Vec3 x, Vec3 y, Vec3 z)
        {
            return new double[3, 3] {
            { x.X, y.X, z.X },
            { x.Y, y.Y, z.Y },
            { x.Z, y.Z, z.Z }
        };
        }

        /// <summary>
        /// 回転行列からZ→X→Y順（ZXY順）のオイラー角（ラジアン）を抽出。
        /// UnityのTransform.eulerAnglesと同じ順序で回転を分解。
        /// </summary>
        public static Vec3 RotationMatrixToEulerZXY(double[,] R)
        {
            // X軸回転（Pitch）
            double pitch = Math.Asin(-R[2, 1]);

            // Z軸回転（Roll）
            double roll = Math.Atan2(R[1, 1], R[0, 1]);

            // Y軸回転（Yaw）
            double yaw = Math.Atan2(R[2, 0], R[2, 2]);

            return new Vec3(roll, pitch, yaw); // Z→X→Y順
        }

        /// <summary>
        /// 計測点群Pと設計点群Qの3点対応から、回転行列と並進ベクトルを推定。
        /// 回転は左手座標系（Unity準拠）で構築し、ZXY順オイラー角に変換。
        /// </summary>
        public static void EstimatePose(Vec3[] P, Vec3[] Q, out Vec3 translation, out Vec3 eulerZXY)
        {
            // 各点群からローカル座標系を構築
            BuildBasis(P[0], P[1], P[2], out Vec3 xP, out Vec3 yP, out Vec3 zP);
            BuildBasis(Q[0], Q[1], Q[2], out Vec3 xQ, out Vec3 yQ, out Vec3 zQ);

            // 回転行列を構築（R = R_Q * R_P^T）
            double[,] RP = MakeRotationMatrix(xP, yP, zP);
            double[,] RQ = MakeRotationMatrix(xQ, yQ, zQ);
            double[,] R = new double[3, 3];
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    R[i, j] = RQ[i, 0] * RP[j, 0] + RQ[i, 1] * RP[j, 1] + RQ[i, 2] * RP[j, 2];

            // 回転行列からZXY順オイラー角を抽出
            eulerZXY = RotationMatrixToEulerZXY(R);

            // 並進ベクトル T = Q1 - R * P1
            Vec3 Rp0 = new Vec3(
                R[0, 0] * P[0].X + R[0, 1] * P[0].Y + R[0, 2] * P[0].Z,
                R[1, 0] * P[0].X + R[1, 1] * P[0].Y + R[1, 2] * P[0].Z,
                R[2, 0] * P[0].X + R[2, 1] * P[0].Y + R[2, 2] * P[0].Z
            );
            translation = Q[0] - Rp0;
        }
    }

    class LSE_alignment
    {
        private int Ver;        // Version 
        private int Sub_ver;    // Sub-Version
        private int Nv;         // Degree of freedom Nv = 7
        private int Np;         // Number of nodal point
        private double[,] Xd;   // plan Coordinate
        private double[,] Xb;   // measure Coordinate of spatial
        private double[,] v;    // residuals v[Np,3];
        private int[,] sw;      // switch flag use or not  0:use   1: no use 
        private int[] sw1;      //
        private double[,] P_inp;// weight factor of Least Square Evaluation ( Input weight) for P & pp
        private double[,] P;    // weight factor of Least Square Evaluation ( Only Diagonal)
        private double [] pp;   // weight factor of Least Square Evaluation ( Only Diagonal) same pp
        private double[,] N;    // matrix of normal equation
        private double[] d;     // Observation vector
        private double[] R;     // absolute term
        private double[,] A;    // Jacobian matrix
        private double[] x;     // unknown factor
        private int[] flg;      // switch flag of normal equation (0:use 1:no use)
        private double[,] Rx;   // Rotation matrix of X axis
        private double[,] Ry;   // Rotation matrix of Y axis
        private double[,] Rz;   // Rotation matrix of Z axis
        private double[,] RR;   // Rotation matrix RR = Rx Ry Rz
        private double[] X;     // unknown factor after convergence 。未知数は「並進量XYZ,オイラー角XYZ,スケール」の計7個
        private double[,] Xbb;  // corrected measurement coordinate
        private int N_max;      // maximum number of calculations
        private int N_loop;     // Number of calculation
        private double err;     // calculation censoring error
        private double con_err; // calculation error
        private double Beta;    // Relaxation factor

        private double RMS_x;
        private double RMS_y;
        private double RMS_z;

        private int Ret;        // return value

        public LSE_alignment(int np){ // Constructor
            // latest version  2024.8.16 Version 1.1
            Ver = 2;
            Sub_ver = 1;
            Nv = 7;
            Np = np;
            Xd = new double[Np,3];
            Xb = new double[Np,3];
            v = new double[Np,3];
            sw = new int[Np,3];
            sw1 = new int[3*Np];
            P_inp = new double[Np,3];
            P = new double[Np,3];
            pp = new double[3*Np];
            N = new double[Nv,Nv];
            d = new double[3*Np];
            R = new double[Nv];
            A = new double[3*Np,Nv];
            x = new double[Nv];
            flg = new int[Nv];
            Rx = new double[3,3];
            Ry = new double[3,3];
            Rz = new double[3,3];
            RR = new double[3,3];
            X = new double[Nv];
            Xbb = new double[Np,3];
            Beta = 1.0;

            // Initial Value Set
            int cnt=0;
            for (int i=0; i < Np; i++) {
                for (int j=0; j < 3; j++){
                    P_inp[i, j] = 1.0;
                    P[i, j] = 1.0;
                    pp[cnt] = 1.0;
                    cnt++;
                }
            }
            // initial set of flg
            for (int i = 0; i < Nv; i++) flg[i] = 0;
            //flg[0] = 1; flg[1] = 1; flg[2] = 1;
            flg[6] = 1;

            // initial set of er
            this.err = 1.0e-5;
            //N_max = 50;
            N_max = 100;
        }
        //最小二乗法のベストマッチ実行　戻り値 0:正常 1:LoopOver
        public int Cal()
        {
           bool status=true;

           if (!approximate()) return Constants.OTHER_ERROR;

           Update_Xbb();

            DebugPrintX("Initial");   // ★ 初期値を確認

            N_loop = 0;

            while(status)
            {
                //Set_A();
                Set_A(1);
                Set_N();
                Set_d();
                Set_R();
                gauss(); // Caluclation normal equartion by Gauss Elimination
                update();
                status = Check_convergence(ref Ret);
            }
            residuals();

            return Ret;
        }
        private void Set_d()
        {
            int cnt;
            cnt = 0;
            for(int i = 0; i < Np; i++)
            {
                for(int j = 0; j < 3; j++)
                {
                    d[cnt] = Xd[i, j] - Xbb[i, j];
                    cnt++;
                }
            }
        }
        public void DebugPrintX(string label)
        {
            double rxDeg = X[3] * 180.0 / Math.PI;
            double ryDeg = X[4] * 180.0 / Math.PI;
            double rzDeg = X[5] * 180.0 / Math.PI;

            Debug.Log($"{label} X (deg): {rxDeg}, {ryDeg}, {rzDeg}");
            Debug.Log($"{label} T: {X[0]}, {X[1]}, {X[2]}");
            Debug.Log($"{label} Scale: {X[6]}");
        }


        // Gauss
        private void gauss()
        {

            //Nv = 4;
            //N[0,0] = 1.0; N[0, 1] = 1.0;N[0, 2] = -1.0;N[0, 3] = 0.0;
            //N[1, 0] = 1.0; N[1, 1] =-1.0; N[1, 2] = 2.0;N[1, 3] = 0.0;
            //N[2, 0] = 2.0; N[2, 1] = 1.0; N[2, 2] = 1.0;N[2, 3] = 0.0;
            //N[3, 0] = 0.0; N[3, 1] = 0.0; N[3, 2] = 0.0; N[3, 3] = 0.0;

            //flg[0] = 0;flg[1] = 0; flg[2] = 0;flg[3] = 1;
            
            //d[0] = 7.0;d[1] = 3.0;d[2] = 9.0;d[3] = 0.0;

            // 前進消去
            for (int i = 0; i < Nv - 1; i++)
            {
                if (flg[i] == 1) continue;
                for (int j = i + 1; j < Nv; j++)
                {
                    //if (flg[j] == 1) continue;
                    double s = N[j, i] / N[i, i];
                    for (int k = i; k < Nv; k++)
                    {
                        if (flg[k] == 1) continue;
                        N[j, k] -= N[i, k] * s;
                    }
                    R[j] -= R[i] * s;
                }
            }
            // 後退代入
            for (int i = Nv - 1; i >= 0; i--)
            {
                if (flg[i] == 1) continue;
                double s = R[i];
                for (int j = i + 1; j < Nv; j++)
                {
                    if (flg[j] == 1) continue;
                    s -= N[i, j] * x[j];
                }
                x[i] = s / N[i, i];
            }
        }
        // residuals
        private void residuals()
        {
            for (int i = 0; i < Np; i++)
            {
                for (int j = 0; j < 3; j++)
                {
                    v[i, j] = Xd[i, j] - Xbb[i, j];
                }
            }
        }
        private void update()
        {
            // N_loop に応じた Beta の段階的制御
            if (N_loop < 10)
                Beta = 0.1;
            else if (N_loop < 20)
                Beta = 0.3;
            else if (N_loop < 30)
                Beta = 0.5;
            else
                Beta = 1.0;

            for (int i = 0; i < Nv; i++)
            {
                if (flg[i] == 0) // 自由度が有効な場合のみ更新
                {
                    X[i] += Beta * x[i];
                }
            }

            Update_Xbb(); // 新しいパラメータで再計算
        }
        // update
        //private void update()
        //{
        //    for (int i = 0; i < Nv; i++)
        //    {
        //        X[i] += Beta * x[i];
        //    }
        //    Update_Xbb();
        //}

        //// 回転行列の掛け算
        private void R_Malti(ref double [,]rr,double [,] r1,double [,] r2)
        {
            double w;
            
            for (int i = 0; i < 3; i++)
            {
                for (int j = 0; j < 3; j++)
                {
                    w=0.0;
                    for (int k = 0; k < 3; k++)
                    {
                        w += r1[i, k] * r2[k, j];
                    }
                    rr[i, j] = w;
                }
            }
        }
        // 回転行列のベクトル
        private void R_Vct(ref double [] v2,double [,] r,double [] v1)
        {
            double w;
 
            for (int i = 0; i < 3; i++)
            {
                w=0.0;
                for (int j = 0; j < 3; j++)
                {
                    w += r[i,j] * v1[j];
                }
                v2[i]=w;
            }
        }       
        // Update Xbb
        private void Update_Xbb()
        {
            double [,] rr;
            rr = new double[3, 3];


            rr[0,0]=1.0;rr[0,1]=0.0;rr[0,2]=0.0;
            rr[1,0]=0.0;rr[1,1]=1.0;rr[1,2]=0.0;
            rr[2,0]=0.0;rr[2,1]=0.0;rr[2,2]=1.0;

            double cx,sx;
            double cy, sy;
            double cz, sz;
            double s;

            cx = Math.Cos(X[3]);
            sx = Math.Sin(X[3]);
            cy = Math.Cos(X[4]);
            sy = Math.Sin(X[4]);
            cz = Math.Cos(X[5]);
            sz = Math.Sin(X[5]);
            s = X[6];

            //cx = Math.Cos(x[3]);
            //sx = Math.Sin(x[3]);
            //cy = Math.Cos(x[4]);
            //sy = Math.Sin(x[4]);
            //cz = Math.Cos(x[5]);
            //sz = Math.Sin(x[5]);

            int r= Constants.LEFT_HAND_SYSTEM;

            switch(r){
                case 1: // LEFT HAND SYSTEM for Unity

                    Rx[0, 0] = 1.0; Rx[0, 1] = 0.0; Rx[0, 2] = 0.0;
                    Rx[1, 0] = 0.0; Rx[1, 1] =  cx; Rx[1, 2] =  sx;
                    Rx[2, 0] = 0.0; Rx[2, 1] = -sx; Rx[2, 2] =  cx;

                    Ry[0, 0] = cy; Ry[0, 1] = 0.0; Ry[0, 2] = -sy;
                    Ry[1, 0] = 0.0; Ry[1, 1] = 1.0; Ry[1, 2] = 0.0;
                    Ry[2, 0] =  sy; Ry[2, 1] = 0.0; Ry[2, 2] = cy;

                    Rz[0, 0] =  cz; Rz[0, 1] =  sz; Rz[0, 2] = 0.0;
                    Rz[1, 0] = -sz; Rz[1, 1] = cz; Rz[1, 2] = 0.0;
                    Rz[2, 0] = 0.0; Rz[2, 1] = 0.0; Rz[2, 2] = 1.0;

                    R_Malti(ref rr, Rx, Rz);
                    R_Malti(ref RR, Ry, rr);
                    break;

                default: // RIHGT HAND SYSYTEM for CloseRangePhotogrammetry
                    Rx[0, 0] = 1.0; Rx[0, 1] = 0.0; Rx[0, 2] = 0.0;
                    Rx[1, 0] = 0.0; Rx[1, 1] =  cx; Rx[1, 2] = -sx;
                    Rx[2, 0] = 0.0; Rx[2, 1] =  sx; Rx[2, 2] =  cx;

                    Ry[0, 0] = cy; Ry[0, 1] = 0.0; Ry[0, 2] = sy;
                    Ry[1, 0] = 0.0; Ry[1, 1] = 1.0; Ry[1, 2] = 0.0;
                    Ry[2, 0] = -sy; Ry[2, 1] = 0.0; Ry[2, 2] = cy;

                    Rz[0, 0] = cz; Rz[0, 1] = -sz; Rz[0, 2] = 0.0;
                    Rz[1, 0] = sz; Rz[1, 1] = cz; Rz[1, 2] = 0.0;
                    Rz[2, 0] = 0.0; Rz[2, 1] = 0.0; Rz[2, 2] = 1.0;

                    R_Malti(ref rr, Ry, Rz);
                    R_Malti(ref RR, Rx, rr);
                    break;

            }

            double x0, y0, z0;
            x0 = X[0];
            y0 = X[1];
            z0 = X[2];

            double [] v1,v2;
            v1 = new double [3];
            v2 = new double [3];

            double w1,w2,w3;
            w1 = 0.0; w2 = 0.0; w3 = 0.0;
            for (int i = 0; i < Np; i++)
            {
                v1[0] = Xb[i, 0]; v1[1] = Xb[i, 1]; v1[2] = Xb[i, 2];
                R_Vct(ref v2, RR, v1);
                Xbb[i, 0] = (1.0+s) * v2[0] + x0;
                Xbb[i, 1] = (1.0+s) * v2[1] + y0;
                Xbb[i, 2] = (1.0+s) *v2[2] + z0;
                v[i, 0] = Xd[i, 0] - Xbb[i, 0];
                v[i, 1] = Xd[i, 1] - Xbb[i, 1];
                v[i, 2] = Xd[i, 2] - Xbb[i, 2];
                w1 += v[i, 0] * v[i, 0]; w2 += v[i, 1] * v[i, 1]; w3 += v[i, 2] * v[i, 2];
            }
            RMS_x = Math.Sqrt(w1 / Np);
            RMS_y = Math.Sqrt(w2 / Np);
            RMS_z = Math.Sqrt(w3 / Np);
        }
        // 外部の変数を座標変換して返す
        public void Transform(double [,] in_x,ref double [,] out_x)
        {

            if( in_x.GetLength(0) > out_x.GetLength(0))
            {
                out_x = new double[in_x.GetLength(0), in_x.GetLength(1)];
            }

            double[,] rr;
            rr = new double[3, 3];

            rr[0, 0] = 1.0; rr[0, 1] = 0.0; rr[0, 2] = 0.0;
            rr[1, 0] = 0.0; rr[1, 1] = 1.0; rr[1, 2] = 0.0;
            rr[2, 0] = 0.0; rr[2, 1] = 0.0; rr[2, 2] = 1.0;

            double cx, sx;
            double cy, sy;
            double cz, sz;
            double s;

            cx = Math.Cos(X[3]);
            sx = Math.Sin(X[3]);
            cy = Math.Cos(X[4]);
            sy = Math.Sin(X[4]);
            cz = Math.Cos(X[5]);
            sz = Math.Sin(X[5]);
            s = X[6];

            int r = Constants.LEFT_HAND_SYSTEM;

            switch (r)
            {
                case 1: // LEFT HAND SYSTEM for Unity

                    Rx[0, 0] = 1.0; Rx[0, 1] = 0.0; Rx[0, 2] = 0.0;
                    Rx[1, 0] = 0.0; Rx[1, 1] = cx; Rx[1, 2] = sx;
                    Rx[2, 0] = 0.0; Rx[2, 1] = -sx; Rx[2, 2] = cx;

                    Ry[0, 0] = cy; Ry[0, 1] = 0.0; Ry[0, 2] = -sy;
                    Ry[1, 0] = 0.0; Ry[1, 1] = 1.0; Ry[1, 2] = 0.0;
                    Ry[2, 0] = sy; Ry[2, 1] = 0.0; Ry[2, 2] = cy;

                    Rz[0, 0] = cz; Rz[0, 1] = sz; Rz[0, 2] = 0.0;
                    Rz[1, 0] = -sz; Rz[1, 1] = cz; Rz[1, 2] = 0.0;
                    Rz[2, 0] = 0.0; Rz[2, 1] = 0.0; Rz[2, 2] = 1.0;

                    R_Malti(ref rr, Rx, Rz);
                    R_Malti(ref RR, Ry, rr);
                    break;

                default: // RIHGT HAND SYSYTEM for CloseRangePhotogrammetry
                    Rx[0, 0] = 1.0; Rx[0, 1] = 0.0; Rx[0, 2] = 0.0;
                    Rx[1, 0] = 0.0; Rx[1, 1] = cx; Rx[1, 2] = -sx;
                    Rx[2, 0] = 0.0; Rx[2, 1] = sx; Rx[2, 2] = cx;

                    Ry[0, 0] = cy; Ry[0, 1] = 0.0; Ry[0, 2] = sy;
                    Ry[1, 0] = 0.0; Ry[1, 1] = 1.0; Ry[1, 2] = 0.0;
                    Ry[2, 0] = -sy; Ry[2, 1] = 0.0; Ry[2, 2] = cy;

                    Rz[0, 0] = cz; Rz[0, 1] = -sz; Rz[0, 2] = 0.0;
                    Rz[1, 0] = sz; Rz[1, 1] = cz; Rz[1, 2] = 0.0;
                    Rz[2, 0] = 0.0; Rz[2, 1] = 0.0; Rz[2, 2] = 1.0;

                    R_Malti(ref rr, Ry, Rz);
                    R_Malti(ref RR, Rx, rr);
                    break;

            }

            double x0, y0, z0;
            x0 = X[0];
            y0 = X[1];
            z0 = X[2];

            double[] v1, v2;
            v1 = new double[3];
            v2 = new double[3];

            //double w1, w2, w3;
            //w1 = 0.0; w2 = 0.0; w3 = 0.0;
            for (int i = 0; i < in_x.GetLength(0); i++)
            {
                v1[0] = in_x[i, 0]; v1[1] = in_x[i, 1]; v1[2] = in_x[i, 2];
                R_Vct(ref v2, RR, v1);
                out_x[i, 0] = (1.0 + s) * v2[0] + x0;
                out_x[i, 1] = (1.0 + s) * v2[1] + y0;
                out_x[i, 2] = (1.0 + s) * v2[2] + z0;
            }
        }
        // check convergence;
        private bool Check_convergence(ref int r)
        {
            //double e;

            N_loop++;   // counter increment
            con_err = x[0];
            for (int i = 1; i < Nv; i++) con_err = Math.Max(con_err, Math.Abs(x[i]));
            if (con_err < err)
            {
                r = Constants.NORMAL_END;
                return false;
            }
            if (N_loop > N_max)
            {
                r = Constants.LOOP_OVER;
                return false;
            }

            // clear x
           // for (int i = 0; i < Nv; i++) x[i] = 0.0;
            return true;
        }
        // Set matrix of normal equation
        private void Set_N(){
            double w;
            for (int i = 0; i < Nv; i++)
            {
                for (int j = 0; j < Nv; j++)
                {
                    w = 0.0;
                    for (int k = 0; k < 3*Np; k++)
                    {
                        //if (sw1[i] == 1 || sw1[j] == 1) continue;
                        if (sw1[k] == 1) continue;
                        w += A[k, i] * pp[k] * A[k, j];
                    }
                    N[i, j] = w;
                }
            }
        }
        // Set absolute term
        private void Set_R()
        {
            double w;
            for (int i = 0; i < Nv; i++)
            {
                w = 0.0;
                for (int k = 0; k < 3 * Np; k++)
                {
                    if (sw1[k] == 1) continue;
                    w += A[k, i] * pp[k] * d[k];
                }
                R[i] = w;
            }
        }
        // Set jacobian matrix
        private void Set_A()
        {
            int r;
            r = Constants.LEFT_HAND_SYSTEM;
            switch(r){

                case 1: // LEFT HAND SYSTEM
                    for (int i = 0; i < Np; i++)
                    {
                        A[3 * i, 0] = 1.0;
                        A[3 * i, 1] = 0.0;
                        A[3 * i, 2] = 0.0;
                        A[3 * i, 3] = 0.0;
                        A[3 * i, 4] = -Xbb[i, 2];
                        A[3 * i, 5] = Xbb[i, 1];
                        A[3 * i, 6] = Xbb[i, 0];

                        A[3 * i + 1, 0] = 0.0;
                        A[3 * i + 1, 1] = 1.0;
                        A[3 * i + 1, 2] = 0.0;
                        A[3 * i + 1, 3] = Xbb[i, 2];
                        A[3 * i + 1, 4] = 0.0;
                        A[3 * i + 1, 5] = -Xbb[i, 0];
                        A[3 * i + 1, 6] = Xbb[i, 1];

                        A[3 * i + 2, 0] = 0.0;
                        A[3 * i + 2, 1] = 0.0;
                        A[3 * i + 2, 2] = 1.0;
                        A[3 * i + 2, 3] = -Xbb[i, 1];
                        A[3 * i + 2, 4] = Xbb[i, 0];
                        A[3 * i + 2, 5] = 0.0;
                        A[3 * i + 2, 6] = Xbb[i, 2];
                    }
                    break;
                default: // RIGHT HAND SYSTEM

                    for (int i = 0; i < Np; i++)
                    {
                        A[3 * i, 0] = 1.0;
                        A[3 * i, 1] = 0.0;
                        A[3 * i, 2] = 0.0;
                        A[3 * i, 3] = 0.0;
                        A[3 * i, 4] = Xbb[i, 2];
                        A[3 * i, 5] = -Xbb[i, 1];
                        A[3 * i, 6] = Xbb[i, 0];

                        A[3 * i + 1, 0] = 0.0;
                        A[3 * i + 1, 1] = 1.0;
                        A[3 * i + 1, 2] = 0.0;
                        A[3 * i + 1, 3] = -Xbb[i, 2];
                        A[3 * i + 1, 4] = 0.0;
                        A[3 * i + 1, 5] = Xbb[i, 0];
                        A[3 * i + 1, 6] = Xbb[i, 1];

                        A[3 * i + 2, 0] = 0.0;
                        A[3 * i + 2, 1] = 0.0;
                        A[3 * i + 2, 2] = 1.0;
                        A[3 * i + 2, 3] = Xbb[i, 1];
                        A[3 * i + 2, 4] = -Xbb[i, 0];
                        A[3 * i + 2, 5] = 0.0;
                        A[3 * i + 2, 6] = Xbb[i, 2];
                    }
                    break;
            }

        }
        // Set jacobian matrix
        private void Set_A(int flg)
        {
            double cx, sx;
            double cy, sy;
            double cz, sz;

            cx = Math.Cos(X[3]);
            sx = Math.Sin(X[3]);
            cy = Math.Cos(X[4]);
            sy = Math.Sin(X[4]);
            cz = Math.Cos(X[5]);
            sz = Math.Sin(X[5]);

            double a11, a12, a13, a21, a22, a23, a31, a32, a33;
            a11 = -sy * cx * sz; a12 = sy * cx * cz; a13 = sy * sx;
            a21 = -sy * cz - cy * sx * sz; a22 = -sy * sz + cy * sx * cz; a23 = -cy * cx;
            a31 = -cy * sz - sy * sx * cz; a32 = cy * cz - sy * sx * sz; a33 = 0.0;

            double b11, b12, b13, b21, b22, b23, b31, b32, b33;
            b11 = sx*sz; b12 = -sx*cz; b13 = cx;
            b21 = 0.0; b22 = 0.0; b23 = 0.0;
            b31 = -cx * cz; b32 = -cz * sz;b33 = 0.0;

            double c11, c12, c13, c21, c22, c23, c31, c32, c33;
            c11 = cy*cx*sz; c12 = -cy*cx*cz; c13 = -cy*sx;
            c21 = cy*cz-sy*sx*sz; c22 = cy*sz+sy*sx*cz; c23 = -sy*cx;
            c31 = -sy*sz+cy*sx*cz; c32 = sy*cz+cy*sx*sz; c33 = 0.0;


            double [,] rr;
            rr = new double[3, 3];


            rr[0,0]=1.0;rr[0,1]=0.0;rr[0,2]=0.0;
            rr[1,0]=0.0;rr[1,1]=1.0;rr[1,2]=0.0;
            rr[2,0]=0.0;rr[2,1]=0.0;rr[2,2]=1.0;

            Rx[0, 0] = 1.0; Rx[0, 1] = 0.0; Rx[0, 2] = 0.0;
            Rx[1, 0] = 0.0; Rx[1, 1] =  cx; Rx[1, 2] =  sx;
            Rx[2, 0] = 0.0; Rx[2, 1] = -sx; Rx[2, 2] =  cx;

            Ry[0, 0] = cy; Ry[0, 1] = 0.0; Ry[0, 2] = -sy;
            Ry[1, 0] = 0.0; Ry[1, 1] = 1.0; Ry[1, 2] = 0.0;
            Ry[2, 0] =  sy; Ry[2, 1] = 0.0; Ry[2, 2] = cy;

            Rz[0, 0] =  cz; Rz[0, 1] =  sz; Rz[0, 2] = 0.0;
            Rz[1, 0] = -sz; Rz[1, 1] = cz; Rz[1, 2] = 0.0;
            Rz[2, 0] = 0.0; Rz[2, 1] = 0.0; Rz[2, 2] = 1.0;

            R_Malti(ref rr, Rx, Rz);
            R_Malti(ref RR, Ry, rr);


            int r;
            r = Constants.LEFT_HAND_SYSTEM;
            switch (r)
            {

                case 1: // LEFT HAND SYSTEM
                    double [] v1,v2;
                    v1 = new double [3];
                    v2 = new double [3];
                    for (int i = 0; i < Np; i++)
                    {
                        for (int j = 0; j < 3; j++) v1[j] = Xb[i, j];
                        R_Vct(ref v2, RR, v1);
                        A[3 * i, 0] = 1.0;
                        A[3 * i, 1] = 0.0;
                        A[3 * i, 2] = 0.0;
                        //A[3 * i, 0] = RR[0, 0];
                        //A[3 * i, 1] = RR[0,1];
                        //A[3 * i, 2] = RR[0,2];
                        A[3 * i, 3] = a11 * Xb[i, 0] + a12 * Xb[i, 1] + a13 * Xb[i, 2];
                        A[3 * i, 4] = a21 * Xb[i, 0] + a22 * Xb[i, 1] + a23 * Xb[i, 2];
                        A[3 * i, 5] = a31 * Xb[i, 0] + a32 * Xb[i, 1] + a33 * Xb[i, 2];
                        //A[3 * i, 6] = Xb[i, 0];
                        A[3 * i, 6] = v2[0];

                        A[3 * i + 1, 0] = 0.0;
                        A[3 * i + 1, 1] = 1.0;
                        A[3 * i + 1, 2] = 0.0;
                        //A[3 * i + 1, 0] = RR[1,0];
                        //A[3 * i + 1, 1] = RR[1,1];
                        //A[3 * i + 1, 2] = RR[1,2];
                        A[3 * i + 1, 3] = b11 * Xb[i, 0] + b12 * Xb[i, 1] + b13 * Xb[i, 2];
                        A[3 * i + 1, 4] = b21 * Xb[i, 0] + b22 * Xb[i, 1] + b23 * Xb[i, 2];
                        A[3 * i + 1, 5] = b31 * Xb[i, 0] + b32 * Xb[i, 1] + b33 * Xb[i, 2];
                        //A[3 * i + 1, 6] = Xb[i, 1];
                        A[3 * i + 1, 6] = v2[1];

                        A[3 * i + 2, 0] = 0.0;
                        A[3 * i + 2, 1] = 0.0;
                        A[3 * i + 2, 2] = 1.0;
                        //A[3 * i + 2, 0] = RR[2, 0];
                        //A[3 * i + 2, 1] = RR[2,1];
                        //A[3 * i + 2, 2] = RR[2,2];
                        A[3 * i + 2, 3] = c11 * Xb[i, 0] + c12 * Xb[i, 1] + c13 * Xb[i, 2];
                        A[3 * i + 2, 4] = c21 * Xb[i, 0] + c22 * Xb[i, 1] + c23 * Xb[i, 2];
                        A[3 * i + 2, 5] = c31 * Xb[i, 0] + c32 * Xb[i, 1] + c33 * Xb[i, 2];
                        //A[3 * i + 2, 6] = Xb[i, 2];
                        A[3 * i + 2, 6] = v2[2];
                    }
                    break;
                default: // RIGHT HAND SYSTEM

                    //for (int i = 0; i < Np; i++)
                    //{
                    //    A[3 * i, 0] = 1.0;
                    //    A[3 * i, 1] = 0.0;
                    //    A[3 * i, 2] = 0.0;
                    //    A[3 * i, 3] = 0.0;
                    //    A[3 * i, 4] = Xbb[i, 2];
                    //    A[3 * i, 5] = -Xbb[i, 1];
                    //    A[3 * i, 6] = Xbb[i, 0];

                    //    A[3 * i + 1, 0] = 0.0;
                    //    A[3 * i + 1, 1] = 1.0;
                    //    A[3 * i + 1, 2] = 0.0;
                    //    A[3 * i + 1, 3] = -Xbb[i, 2];
                    //    A[3 * i + 1, 4] = 0.0;
                    //    A[3 * i + 1, 5] = Xbb[i, 0];
                    //    A[3 * i + 1, 6] = Xbb[i, 1];

                    //    A[3 * i + 2, 0] = 0.0;
                    //    A[3 * i + 2, 1] = 0.0;
                    //    A[3 * i + 2, 2] = 1.0;
                    //    A[3 * i + 2, 3] = Xbb[i, 1];
                    //    A[3 * i + 2, 4] = -Xbb[i, 0];
                    //    A[3 * i + 2, 5] = 0.0;
                    //    A[3 * i + 2, 6] = Xbb[i, 2];
                    //}
                    break;
            }

        }
        // 初期値求解
        private bool approximate()
        {
            // 自由度フラグ（0:使用, 1:固定）
            int[] flag = flg;

            // 使用する自由度をカウント
            bool useTx = flag[0] == 0, useTy = flag[1] == 0, useTz = flag[2] == 0;
            bool useRx = flag[3] == 0, useRy = flag[4] == 0, useRz = flag[5] == 0;
            bool useScale = flag[6] == 0;

            // --- ① 並進のみ（回転・スケール固定） → 1点で整合 ---
            if (!useRx && !useRy && !useRz && !useScale)
            {
                X[0] = Xd[0, 0] - Xb[0, 0];
                X[1] = Xd[0, 1] - Xb[0, 1];
                X[2] = Xd[0, 2] - Xb[0, 2];
                X[3] = 0.0; X[4] = 0.0; X[5] = 0.0; X[6] = 0.0;
                return true;
            }

            // --- ② 並進＋スケール（回転なし） → 2点でスケールと位置合わせ ---
            if (!useRx && !useRy && !useRz && useScale)
            {
                int pt1 = 0, pt2 = 1;
                double dx = Xb[pt2, 0] - Xb[pt1, 0];
                double dy = Xb[pt2, 1] - Xb[pt1, 1];
                double dz = Xb[pt2, 2] - Xb[pt1, 2];
                double dl = Math.Sqrt(dx * dx + dy * dy + dz * dz);

                double dX = Xd[pt2, 0] - Xd[pt1, 0];
                double dY = Xd[pt2, 1] - Xd[pt1, 1];
                double dZ = Xd[pt2, 2] - Xd[pt1, 2];
                double dL = Math.Sqrt(dX * dX + dY * dY + dZ * dZ);

                double s = (dL != 0.0) ? dL / dl - 1.0 : 0.0;

                X[0] = Xd[pt1, 0] - (1.0 + s) * Xb[pt1, 0];
                X[1] = Xd[pt1, 1] - (1.0 + s) * Xb[pt1, 1];
                X[2] = Xd[pt1, 2] - (1.0 + s) * Xb[pt1, 2];
                X[3] = 0.0; X[4] = 0.0; X[5] = 0.0; X[6] = s;
                return true;
            }

            // --- ③ X-Z平面問題（Y軸回転のみ） → 既存の2点推定を使用 ---
            if (!useRx && useRy && !useRz)
            {
                return approximate_XZ(); // 既存の2点推定関数（改名して分離）
            }

            // --- ④ 一般3次元回転（ZXY）＋並進＋スケール → 3点から座標系構築 ---
            //return approximate_3pt(); // 新規関数（下で定義）
            // --- ④ 一般3次元回転（ZXY）＋並進＋スケール → Kabsch/Umeyama に置き換え ---
            return approximate_kabsch_umeyama();

        }
        // ============================================================
        // Kabsch / Umeyama による初期値推定（完全版）
        // flg[6] = 1 → スケール固定 → Kabsch
        // flg[6] = 0 → スケール推定 → Umeyama
        // ============================================================
        private bool approximate_kabsch_umeyama()
        {
            Vector3[] P = new Vector3[Np];
            Vector3[] Q = new Vector3[Np];

            for (int i = 0; i < Np; i++)
            {
                P[i] = new Vector3((float)Xb[i, 0], (float)Xb[i, 1], (float)Xb[i, 2]);
                Q[i] = new Vector3((float)Xd[i, 0], (float)Xd[i, 1], (float)Xd[i, 2]);
            }

            Matrix4x4 Rmat;
            Vector3 tvec;
            float scaleAbs = 1.0f;

            if (flg[6] == 1)
            {
                RigidTransformUnity.ComputeKabschSVD(P, Q, out Rmat, out tvec);
                X[6] = 0.0;
            }
            else
            {
                RigidTransformUnity.ComputeUmeyamaSVD(P, Q, out Rmat, out tvec, out scaleAbs);
                X[6] = scaleAbs - 1.0;
            }

            // ★ LSE_alignment の回転順序に合わせて Euler 分解
            Vector3 eulerLSE = RigidTransformEulerLSE.ExtractEuler_LSE_RyRxRz(Rmat);

            X[3] = eulerLSE.x;  // rad
            X[4] = eulerLSE.y;  // rad
            X[5] = eulerLSE.z;  // rad

            // 並進
            X[0] = tvec.x;
            X[1] = tvec.y;
            X[2] = tvec.z;

            return true;
        }





        // LSE_alignment の回転順序（Ry * Rx * Rz）に合わせた Euler 分解
        // Rmat は Unity の Matrix4x4（Kabsch/Umeyama の結果）
        // 戻り値は (X, Y, Z) すべて rad
        public static Vector3 ExtractEuler_LSE_RyRxRz(Matrix4x4 R)
        {
            // 行列要素
            double r00 = R.m00, r01 = R.m01, r02 = R.m02;
            double r10 = R.m10, r11 = R.m11, r12 = R.m12;
            double r20 = R.m20, r21 = R.m21, r22 = R.m22;

            // --- Y の計算 ---
            // R = Ry * Rx * Rz の場合、r20 = sin(Y)
            double Y = Math.Asin(r20);

            // cos(Y) が 0 に近い場合（特異点）
            double cosY = Math.Cos(Y);
            double X, Z;

            if (Math.Abs(cosY) < 1e-6)
            {
                // 特異点：Y = ±90°
                // Z は 0 として扱い、X を決める
                Z = 0.0;
                X = Math.Atan2(-r01, r11);
            }
            else
            {
                // --- X の計算 ---
                // r21 = -sin(X)*cos(Y)
                // r22 =  cos(X)*cos(Y)
                X = Math.Atan2(-r21, r22);

                // --- Z の計算 ---
                // r10 = -cos(Y)*sin(Z)
                // r00 =  cos(Y)*cos(Z)
                Z = Math.Atan2(-r10, r00);
            }

            return new Vector3((float)X, (float)Y, (float)Z);
        }




        // 3点より近似値求解
        private bool approximate_3pt()
        {
            // 代表的な3点を選択（例：最大距離ペア＋第3点）
            int i1, i2, i3;
            if (!Select_3pt_MaxArea(out i1, out i2, out i3)) return false;

            // 計測点群の基底構築（左手系）
            Vec3 p1 = new Vec3(Xb[i1, 0], Xb[i1, 1], Xb[i1, 2]);
            Vec3 p2 = new Vec3(Xb[i2, 0], Xb[i2, 1], Xb[i2, 2]);
            Vec3 p3 = new Vec3(Xb[i3, 0], Xb[i3, 1], Xb[i3, 2]);

            Vec3 q1 = new Vec3(Xd[i1, 0], Xd[i1, 1], Xd[i1, 2]);
            Vec3 q2 = new Vec3(Xd[i2, 0], Xd[i2, 1], Xd[i2, 2]);
            Vec3 q3 = new Vec3(Xd[i3, 0], Xd[i3, 1], Xd[i3, 2]);

            RigidTransform.BuildBasis(p1, p2, p3, out Vec3 xP, out Vec3 yP, out Vec3 zP);
            RigidTransform.BuildBasis(q1, q2, q3, out Vec3 xQ, out Vec3 yQ, out Vec3 zQ);

            double[,] RP = RigidTransform.MakeRotationMatrix(xP, yP, zP);
            double[,] RQ = RigidTransform.MakeRotationMatrix(xQ, yQ, zQ);

            double[,] R = new double[3, 3];
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    R[i, j] = RQ[i, 0] * RP[j, 0] + RQ[i, 1] * RP[j, 1] + RQ[i, 2] * RP[j, 2];

            Vec3 euler = RigidTransform.RotationMatrixToEulerZXY(R);
            Vec3 Rp1 = new Vec3(
                R[0, 0] * p1.X + R[0, 1] * p1.Y + R[0, 2] * p1.Z,
                R[1, 0] * p1.X + R[1, 1] * p1.Y + R[1, 2] * p1.Z,
                R[2, 0] * p1.X + R[2, 1] * p1.Y + R[2, 2] * p1.Z
            );
            Vec3 T = q1 - Rp1;

            // スケール推定（任意）
            double s = 0.0;
            if (flg[6] == 0)
            {
                double dp = (p2 - p1).Norm();
                double dq = (q2 - q1).Norm();
                s = (dq / dp) - 1.0;
            }

            X[0] = T.X; X[1] = T.Y; X[2] = T.Z;
            X[3] = euler.X; X[4] = euler.Y; X[5] = euler.Z;
            X[6] = s;

            Update_Xbb();

            return true;
        }
        // 最低な３点求解
        private bool Select_3pt_MaxArea(out int i1, out int i2, out int i3)
        {
            double maxArea = -1.0;
            i1 = i2 = i3 = 0;

            for (int a = 0; a < Np - 2; a++)
            {
                for (int b = a + 1; b < Np - 1; b++)
                {
                    for (int c = b + 1; c < Np; c++)
                    {
                        Vec3 p1 = new Vec3(Xb[a, 0], Xb[a, 1], Xb[a, 2]);
                        Vec3 p2 = new Vec3(Xb[b, 0], Xb[b, 1], Xb[b, 2]);
                        Vec3 p3 = new Vec3(Xb[c, 0], Xb[c, 1], Xb[c, 2]);

                        Vec3 v1 = p2 - p1;
                        Vec3 v2 = p3 - p1;
                        Vec3 cross = Vec3.Cross(v1, v2);
                        double area = cross.Norm(); // 面積 = 外積のノルム

                        if (area > maxArea)
                        {
                            maxArea = area;
                            i1 = a; i2 = b; i3 = c;
                        }
                    }
                }
            }

            return maxArea > 1e-8; // 面積が十分大きい場合のみ有効
        }
        // approximate value 近似値の求解
        private bool approximate_XZ()
        {
            int ptmax=0;
            int ptmin=0;

            if(!Select_2pt(ref ptmax, ref ptmin)) return false;

            double dX,dZ, dx,dz,dL,dl,s;
            dx = Xb[ptmax, 0] - Xb[ptmin, 0];
            dz = Xb[ptmax, 2] - Xb[ptmin, 2];
            dl = Math.Sqrt(dx * dx + dz * dz);
            dX = Xd[ptmax, 0] - Xd[ptmin, 0];
            dZ = Xd[ptmax, 2] - Xd[ptmin, 2];
            dL = Math.Sqrt(dX * dX + dZ * dZ);
            if (dL != 0.0) { s = dL / dl - 1.0; } else { s = 0.0; }

            double th, th1, th2;
            th1 = Math.Atan2(dx, dz);
            th2 = Math.Atan2(dX, dZ);
            th = th1 - th2;
            double cy, sy;
            cy = Math.Cos(th);
            sy = Math.Sin(th);
            Rx[0, 0] = 1.0; Rx[0, 1] = 0.0; Rx[0, 2] = 0.0;
            Rx[1, 0] = 0.0; Rx[1, 1] = 1.0; Rx[1, 2] = 0.0;
            Rx[2, 0] = 0.0; Rx[2, 1] = 0.0; Rx[2, 2] = 1.0;

            Ry[0, 0] =  cy; Ry[0, 1] = 0.0; Ry[0, 2] = -sy;
            Ry[1, 0] = 0.0; Ry[1, 1] = 1.0; Ry[1, 2] = 0.0;
            Ry[2, 0] =  sy; Ry[2, 1] = 0.0; Ry[2, 2] =  cy;

            Rz[0, 0] = 1.0; Rz[0, 1] = 0.0; Rz[0, 2] = 0.0;
            Rz[1, 0] = 0.0; Rz[1, 1] = 1.0; Rz[1, 2] = 0.0;
            Rz[2, 0] = 0.0; Rz[2, 1] = 0.0; Rz[2, 2] = 1.0;

            for (int i=0; i < 3; i++) for (int j = 0; j < 3; j++) RR[i, j] = Ry[i, j];

            double[] v1, v2;
            v1 = new double[3];
            v2 = new double[3];

            for (int i = 0; i < Np; i++)
            {
                v1[0] = Xb[i, 0]; v1[1] = Xb[i, 1]; v1[2] = Xb[i, 2];
                R_Vct(ref v2, RR, v1);
                Xbb[i, 0] = (1.0+s)*v2[0];
                Xbb[i, 1] = (1.0+s)*v2[1];
                Xbb[i, 2] = (1.0+s)*v2[2];
           }
            
            double x0, y0, z0;
            x0 = -(Xbb[ptmin, 0] - Xd[ptmin,0]);
            y0 = -(Xbb[ptmin, 1] - Xd[ptmin, 1]);
            z0 = -(Xbb[ptmin, 2] - Xd[ptmin, 2]);
            for (int i = 0; i < Np; i++)
            {
                Xbb[i, 0] += x0;
                Xbb[i, 1] += y0;
                Xbb[i, 2] += z0;
            }

            X[0] = x0; X[1] = y0; X[2] = z0;
            X[3] = 0.0; X[4] = th; X[5] = 0.0;
            X[6] = s;


            return true;
        }

        // 近似値を求めるための２点を選出する for Unity Virtical -Y
        private bool Select_2pt(ref int ptmax, ref int ptmin)
        {
            double maxDist = 0.0;
            ptmax = ptmin = 0;

            for (int i = 0; i < Np - 1; i++)
            {
                for (int j = i + 1; j < Np; j++)
                {
                    double dx = Xd[i, 0] - Xd[j, 0];
                    double dz = Xd[i, 2] - Xd[j, 2];
                    double dist = dx * dx + dz * dz; // √は不要、比較だけなら2乗距離で十分

                    if (dist > maxDist)
                    {
                        maxDist = dist;
                        ptmax = i;
                        ptmin = j;
                    }
                }
            }

            // 距離が十分あるか確認（ゼロ距離は不適）
            if (maxDist < 1e-12)
            {
                // Debug.LogError("Select_2pt failed: 全ての点がほぼ同一位置です。");
                return false;
            }

            return true;
        }
        // 近似値を求めるための２点を選出する for Unity Virtical -Y
        //private bool Select_2pt(ref int ptmax,ref int ptmin)
        //{
        //    //double xmax;
        //    //double xmin;
        //    //xmax = xmin = Xd[0, 0];
        //    //ptmax = ptmin = 0;
        //    //for (int i = 1; i < Np; i++)
        //    //{
        //    //    if (xmax < Xd[i, 0]) { ptmax = i; xmax = Xd[i, 0]; }
        //    //    if (xmin > Xd[i, 0]) { ptmin = i; xmin = Xd[i, 0]; }
        //    //}
        //    //if (ptmax == ptmin) return false;

        //    if (check_comp(0, ref ptmax, ref ptmin)) return true;
        //    if (check_comp(1, ref ptmax, ref ptmin)) return true;
        //    if (check_comp(2, ref ptmax, ref ptmin)) return true;

        //    return true;
        //}

        private bool check_comp(int icomp, ref int ptmax, ref int ptmin)
        {
            double dmax;
            double dmin;
            dmax = dmin = Xd[0, icomp];
            ptmax = ptmin = 0;
            for (int i = 1; i < Np; i++)
            {
                if (dmax < Xd[i, icomp]) { ptmax = i; dmax = Xd[i, icomp]; }
                if (dmin > Xd[i, icomp]) { ptmin = i; dmin = Xd[i, icomp]; }
            }
            if (ptmax == ptmin) return false;

            return true;
        }

        //扱うデータ数をコンストラクタ呼び出し変更となる場合に使用
        public void Set_Np(int np)
        {
            // 変数配列の変更定義を行う必要があるが未記載
            Nv = 7;
            Np = np;
            Xd = new double[Np, 3];
            Xb = new double[Np, 3];
            v = new double[Np, 3];
            sw = new int[Np, 3];
            sw1 = new int[3 * Np];
            P_inp = new double[Np, 3];
            P = new double[Np, 3];
            pp = new double[3 * Np];
            N = new double[Nv, Nv];
            d = new double[3 * Np];
            R = new double[Nv];
            A = new double[3 * Np, Nv];
            x = new double[Nv];
            flg = new int[Nv];
            Rx = new double[3, 3];
            Ry = new double[3, 3];
            Rz = new double[3, 3];
            RR = new double[3, 3];
            X = new double[Nv];
            Xbb = new double[Np, 3];
            Beta = 1.0;

            // Initial Value Set
            int cnt = 0;
            for (int i = 0; i < Np; i++)
            {
                for (int j = 0; j < 3; j++)
                {
                    P_inp[i, j] = 1.0;
                    P[i, j] = 1.0;
                    pp[cnt] = 1.0;
                    cnt++;
                }
            }
            // initial set of flg
            for (int i = 0; i < Nv; i++) flg[i] = 0;
            //flg[0] = 1; flg[1] = 1; flg[2] = 1;
            flg[6] = 1;

            // initial set of er
            this.err = 1.0e-5;
            N_max = 50;
        }
        //計測データをセットxb[3,np]
        public void Set_Xb(double [,] xb){
            for (int i = 0; i < Np; i++){
                for (int j = 0; j < 3; j++){
                    Xb[i, j] = xb[i, j];
                    Xbb[i, j] = Xb[i, j];
                }
            }
        }
        //計画データをセットxd[3,np]
        public void Set_Xd(double [,] xd){
            for (int i = 0; i < Np; i++){
                for (int j = 0; j < 3; j++){
                    Xd[i, j] = xd[i, j];
                }
            }        
        }
        //オイラー角の取得x={X0,Y0,Z0,θx,θy,θz,S}Sはスケールパラメータ※Ｓは通常使用しない
        public void Get_X(ref double [] x){
            for(int i=0;i<7;i++) x[i]=X[i];
        }
        //回転行列取得 3×3 st=0:R  st=1:Rx st=2:Ry st=3:Rz
        public void Get_R(int st,ref double [,] r){
            for(int i=0;i<3;i++){
                for(int j=0;j<3;j++){
                    switch(st){
                        case 0:
                            r[i,j]=RR[i,j];
                            break;
                        case 1:
                            r[i,j]=Rx[i,j];
                            break;
                        case 2:
                            r[i,j]=Ry[i,j];
                            break;
                        case 3:
                            r[i,j]=Rz[i,j];
                            break;
                        default:
                            r[i,j]=RR[i,j];
                            break;
                    }
                }
            }
        }
        //残差ベクトルの取得　{v}={Xd}-{Xb}
        public void Get_v(ref double [,] vv){
            for(int i=0;i<Np;i++){
                for(int j=0;j<3;j++){
                    vv[i,j] = v[i,j];
                }
            }
        }
        //sw[3,np];  0:計算に使用　1:計算より削除（デフォルト 0）。未知数は「並進量XYZ,オイラー角XYZ,スケール」の計7個
        public void Set_sw(int [,] Sw){
            int cnt;
            cnt = 0;
            for (int i = 0; i < Np; i++){
                for (int j = 0; j < 3; j++){
                    this.sw[i, j] = Sw[i, j];
                    sw1[cnt] = this.sw[i, j];
                    cnt++;
                }
            }
        }
        //flg[7] 0:計算で使用　1:計算で使用しない。 デフォルト 添え字0～５は0, 6は1。 未知数は「並進量XYZ,オイラー角XYZ,スケール」の計7個
        public void Set_flg(int [] Flg){
            for(int i=0;i<7;i++) flg[i]=Flg[i];
        }
        //重み係数　（デフォルト全て1.0)
        public void Set_P(double[,] p){
            int cnt = 0;
            for(int i=0;i<Np;i++){
                for (int j = 0; j < 3; j++)
                {
                    P_inp[i, j] = p[i, j];
                    P[i, j] = p[i, j];
                    pp[cnt] = p[i, j];
                    cnt++;
                }
            }

        }
        //収束条件セット最大収束回数　nmax （デフォルト 30）収束打ち切り	er（デフォルト 1.0e-5）緩和係数 beta（デフォルト 1.0）
        public void Set_err(int nmax,double er,double beta){
            N_max=nmax;
            err=er;
            Beta=beta;
        }
        // Beta値のセット
        public void Set_Beta(double beta) {  Beta = beta; }
        // 収束回数	n 収束解誤差	err 残差ベクトルのRMS  rmsx,rmsy,rmsz
        public void Get_st(ref int n,ref double er,ref double rmsx,ref double rmsy,ref double rmsz){
            n = N_loop;
            er = con_err;
            rmsx = RMS_x;
            rmsy = RMS_y;
            rmsz = RMS_z;
        }

        //重み自動計算
        public void Set_Auto_P(double x, double y, double z){
        
             // VRの自分の位置のに最も近い最小二乗法の重み係数を100とする
             // 入力 x,y,z はIPadの位置

            double w,ww,xx,yy,zz;
            int ii;

            ii = 0;
            xx = Xd[0, 0] - x;
            yy = Xd[0, 1] - y;
            zz = Xd[0, 2] - z;
            w = xx * xx + yy * yy + zz * zz;
            for (int i = 1; i < Np; i++)
            {
                xx = Xd[i, 0] - x;
                yy = Xd[i, 1] - y;
                zz = Xd[i, 2] - z;
                ww = xx * xx + yy * yy + zz * zz;
                if (w > ww) { w = ww; ii = i; }
            }

            int cnt = 0;
            for(int i=0;i<Np;i++){
                for (int j = 0; j < 3; j++)
                {
                    if (i == ii)
                    {
                        P[i, j] = 100.0*P_inp[i,j];
                        pp[cnt] = 100.0*P_inp[i,j];
                        cnt++;

                    }
                    else
                    {
                        P[i, j] = P_inp[i,j];
                        pp[cnt] = P_inp[i,j];
                        cnt++;
                    }
                }
            }


        }

        //重み自動計算（デフォルトP=1.0全て戻す）
        public void Set_Auto_P()
        {
            int cnt = 0;
            for (int i = 0; i < Np; i++)
            {
                for (int j = 0; j < 3; j++)
                {
                        P[i, j] = 1.0;
                        pp[cnt] = 1.0;
                        cnt++;
                }
            }
        }
        //重み自動計算
        public void Set_Auto_P(int flg)
        {
            int cnt;
            switch (flg)
            {
                case 0:     // flg=0　全て1.0にセットする
                    Set_Auto_P();
                    break;
                case 1:     // flg=1 　入力した重みに戻す
                    cnt = 0;
                    for (int i = 0; i < Np; i++)
                    {
                        for (int j = 0; j < 3; j++)
                        {
                            P[i, j] = P_inp[i, j];
                            pp[cnt] = P_inp[i,j];
                            cnt++;
                        }
                    }
                    break;
                default:    //
                    Set_Auto_P();
                    break;

            }

        }
        // スケールファクターSの有効化 2024.8.16 追加
        public void Set_Enable_Scale() { flg[6] = 0; }
        public void Get_verrion(ref int ver, ref int sub_ver) { ver = Ver;sub_ver = Sub_ver; }



        // LSE_alignment class の末尾付近に追加（namespace LSE 内）

        public void BuildNormalEq(out double[,] H, out double[] g)
        {
            // 1回分の正規方程式を構築（現状パラメータXに対して）
            Set_A(1);
            Set_N();
            Set_d();
            Set_R();

            // N=H, R=g として外に出す
            H = (double[,])N.Clone();
            g = (double[])R.Clone();
        }

        public void GetTransformedPoint(int i, out double x, out double y, out double z)
        {
            x = Xbb[i, 0];
            y = Xbb[i, 1];
            z = Xbb[i, 2];
        }

        /// <summary>
        /// 点 i の変換座標 p = Xbb[i] に対するヤコビアン Jp = ∂p/∂X（3x7）
        /// ※ Set_A(1) の該当 3 行を使う
        /// </summary>
        public void GetPointJacobian(int i, out double[,] Jp) // 3x7
        {
            Set_A(1);
            Jp = new double[3, 7];
            for (int k = 0; k < 7; k++)
            {
                Jp[0, k] = A[3 * i + 0, k];
                Jp[1, k] = A[3 * i + 1, k];
                Jp[2, k] = A[3 * i + 2, k];
            }
        }

        /// <summary>
        /// 上位クラスから ΔX を適用して Xbb を更新
        /// flg[i]==1 の自由度は更新しない（固定）
        /// </summary>
        public void ApplyDelta(double[] dX, double beta = 1.0)
        {
            for (int i = 0; i < 7; i++)
            {
                if (flg[i] == 0) X[i] += beta * dX[i];
            }
            Update_Xbb();
        }


    }
}

```

