import datetime
import os
import re
import threading
import tkinter as tk
import tkinter.scrolledtext as st
from tkinter import filedialog, messagebox, ttk


class FilePackerApp:
    """
    AI向けスクリプトおよびUnityシリアライズデータ（Prefab/Scene）のパッキングを行うGUIアプリケーション。
    (AI向けコンテキスト生成パッキングツール)
    """

    def __init__(self, root):
        """
        GUIの初期化とレイアウト設定。
        (GUIの構築と各ウィジェットの配置を行います)
        """
        self.root = root
        self.root.title("AI Script & Prefab Packer (自動分割・完全防爆版)")
        self.root.geometry("650x620")
        self.root.resizable(False, False)

        # ターゲットディレクトリのUIコンポーネント (Target Directory UI)
        tk.Label(root, text="ターゲットディレクトリ (コード・メタ共通):").place(
            x=20, y=20
        )
        self.dir_entry = tk.Entry(root, width=55)
        self.dir_entry.place(x=20, y=45)
        tk.Button(root, text="参照...", command=self.browse_directory).place(
            x=450, y=40
        )

        # 出力ファイルのUIコンポーネント (Output File UI)
        tk.Label(root, text="出力ファイル名 (例: output.md):").place(x=20, y=80)
        self.out_entry = tk.Entry(root, width=55)
        self.out_entry.place(x=20, y=105)
        tk.Button(root, text="参照...", command=self.browse_output).place(x=450, y=100)

        # コード拡張子の設定コンポーネント (Code Extensions UI)
        tk.Label(root, text="対象のコード拡張子 (カンマ区切り):").place(x=20, y=140)
        self.code_ext_entry = tk.Entry(root, width=70)
        self.code_ext_entry.insert(0, ".cs, .py, .shader, .cginc, .hlsl")
        self.code_ext_entry.place(x=20, y=165)

        # Unityデータ拡張子の設定コンポーネント (Unity Extensions UI)
        tk.Label(root, text="解析するUnityデータ拡張子 (カンマ区切り):").place(
            x=20, y=200
        )
        self.unity_ext_entry = tk.Entry(root, width=70)
        self.unity_ext_entry.insert(0, ".prefab, .unity, .asset")
        self.unity_ext_entry.place(x=20, y=225)

        # 実行ボタン (Start Packing Button)
        self.pack_btn = tk.Button(
            root,
            text="パック開始 (自動分割)",
            command=self.start_packing,
            bg="lightblue",
            width=25,
            height=2,
        )
        self.pack_btn.place(x=225, y=265)

        # プログレスバー (Progress Bar)
        self.progress_var = tk.DoubleVar()
        self.progressbar = ttk.Progressbar(
            root, variable=self.progress_var, maximum=100, mode="determinate"
        )
        self.progressbar.place(x=20, y=325, width=610, height=20)

        # ログ表示エリア (Log Display Area)
        tk.Label(root, text="実行ログ:").place(x=20, y=355)
        self.log_area = st.ScrolledText(root, width=82, height=12, state="disabled")
        self.log_area.place(x=20, y=380)

    def log_safe(self, message):
        """
        バックグラウンドスレッドから安全にGUIログを出力するスレッドセーフなラッパーメソッド。
        (スレッドセーフなログ出力)
        """
        self.root.after(0, self._log_internal, message)

    def _log_internal(self, message):
        """
        メインUIスレッド上でログテキストエリアを更新する内部処理。
        (ログテキストエリアの更新内部処理)
        """
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def update_progress_safe(self, value):
        """
        プログレスバーの進捗率をメインUIスレッド上で安全に更新する。
        (スレッドセーフな進捗更新)
        """
        self.root.after(0, self.progress_var.set, value)

    def finish_ui_safe(self, success, title, msg):
        """
        処理完了時にメインUIスレッド上でUI状態を復元しメッセージボックスを表示する。
        (スレッドセーフな完了UIリセット)
        """
        self.root.after(0, self._finish_ui_internal, success, title, msg)

    def _finish_ui_internal(self, success, title, msg):
        """
        UI復元とメッセージボックス表示の内部処理。
        (UI復元内部処理)
        """
        self.pack_btn.config(
            state="normal", text="パック開始 (自動分割)", bg="lightblue"
        )
        if success:
            messagebox.showinfo(title, msg)
        else:
            messagebox.showerror(title, msg)

    def browse_directory(self):
        """
        ターゲットディレクトリ選択ダイアログの表示処理。
        (ディレクトリ選択ダイアログ)
        """
        directory = filedialog.askdirectory(title="対象ディレクトリを選択してください")
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)

    def browse_output(self):
        """
        出力保存先ファイル選択ダイアログの表示処理。
        (出力ファイル選択ダイアログ)
        """
        file_path = filedialog.asksaveasfilename(
            title="出力ファイルの保存先を選択してください",
            defaultextension=".md",
            filetypes=[
                ("Markdown Files", "*.md"),
                ("Text Files", "*.txt"),
                ("All Files", "*.*"),
            ],
        )
        if file_path:
            self.out_entry.delete(0, tk.END)
            self.out_entry.insert(0, file_path)

    def get_language_identifier(self, ext):
        """
        拡張子に対応するMarkdownコードブロックの言語識別子を取得する。
        (Markdown言語指定マッピング)
        """
        ext = ext.lower()
        mapping = {
            ".cs": "csharp",
            ".py": "python",
            ".json": "json",
            ".shader": "hlsl",
            ".cginc": "hlsl",
            ".hlsl": "hlsl",
            ".yaml": "yaml",
            ".prefab": "yaml",
            ".unity": "yaml",
            ".asset": "yaml",
        }
        return mapping.get(ext, "")

    def build_guid_map(self, target_dir):
        """
        .metaファイルを走査してGUIDとC#スクリプト名のマッピング辞書を構築する。
        (GUIDとスクリプト名の対応表構築)
        """
        guid_to_name = {}
        self.log_safe("GUIDマッピングの構築を開始します...")
        guid_pattern = re.compile(r"^guid:\s*([a-fA-F0-9]+)", re.MULTILINE)
        count = 0
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".meta"):
                    base_name = file[:-5]
                    if base_name.endswith(".cs"):
                        meta_path = os.path.join(root, file)
                        try:
                            with open(
                                meta_path, "r", encoding="utf-8", errors="ignore"
                            ) as f:
                                content = f.read()
                                match = guid_pattern.search(content)
                                if match:
                                    guid = match.group(1)
                                    guid_to_name[guid] = os.path.splitext(base_name)[0]
                                    count += 1
                        except OSError as e:
                            self.log_safe(
                                f"メタファイル読み込みエラー {meta_path}: {e}"
                            )
        self.log_safe(f"GUIDマッピング完了: {count} 個のスクリプトGUIDを記録しました。")
        return guid_to_name

    def parse_unity_yaml_relational(self, file_path, guid_map):
        """
        Unityシリアライズデータ（YAML）を解析し、階層構造（Hierarchy Tree）および
        イベント制御フロー（Event Flow）をセマンティックに解決する。
        (Unity YAML リレーショナル解析)
        """
        parsed_result = []
        parsed_result.append(
            f"<!-- Relational YAML Analysis: {os.path.basename(file_path)} -->"
        )

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            objects = {}
            blocks = re.split(r"^---\s*!u!(\d+)\s+&(\d+)", content, flags=re.MULTILINE)
            for i in range(1, len(blocks), 3):
                class_id = blocks[i]
                file_id = blocks[i + 1]
                block_data = blocks[i + 2]
                objects[file_id] = {"class_id": class_id, "data": block_data}

            game_objects = {}
            transforms = {}
            comp_to_go = {}

            native_class_map = {
                "4": "Transform",
                "20": "Camera",
                "23": "MeshRenderer",
                "33": "MeshFilter",
                "54": "Rigidbody",
                "65": "BoxCollider",
                "114": "MonoBehaviour",
                "136": "CapsuleCollider",
                "137": "SkinnedMeshRenderer",
                "212": "SpriteRenderer",
                "224": "RectTransform",
                "108": "Light",
                "198": "ParticleSystem",
            }

            for fid, obj in objects.items():
                if obj["class_id"] == "1":
                    name_match = re.search(r"m_Name:\s*(.*)", obj["data"])
                    name = name_match.group(1).strip() if name_match else "Unnamed"
                    game_objects[fid] = {
                        "name": name,
                        "components": [],
                        "mono_behaviours": [],
                        "children": [],
                        "is_root": True,
                        "transform_id": None,
                    }

            for fid, obj in objects.items():
                go_match = re.search(
                    r"m_GameObject:\s*\{fileID:\s*(\d+)\}", obj["data"]
                )
                if go_match:
                    go_id = go_match.group(1)
                    comp_to_go[fid] = go_id

                    if obj["class_id"] in ("4", "224"):
                        transforms[fid] = go_id
                        if go_id in game_objects:
                            game_objects[go_id]["transform_id"] = fid
                            father_match = re.search(
                                r"m_Father:\s*\{fileID:\s*(\d+)\}", obj["data"]
                            )
                            father_id = father_match.group(1) if father_match else "0"
                            if father_id != "0":
                                game_objects[go_id]["is_root"] = False
                                game_objects[go_id]["father_trans"] = father_id

            for go_id, go in game_objects.items():
                father_trans = go.get("father_trans")
                if father_trans and father_trans in transforms:
                    father_go_id = transforms[father_trans]
                    if father_go_id in game_objects:
                        game_objects[father_go_id]["children"].append(go_id)

            def resolve_reference(ref_str):
                ref_match = re.search(r"\{fileID:\s*(\d+)\}", ref_str)
                if ref_match:
                    ref_id = ref_match.group(1)
                    if ref_id == "0":
                        return "None"
                    if ref_id in comp_to_go:
                        ref_go = comp_to_go[ref_id]
                        if ref_go in game_objects:
                            return f"[Ref -> {game_objects[ref_go]['name']}]"
                    if ref_id in game_objects:
                        return f"[Ref -> {game_objects[ref_id]['name']}]"
                return ref_str

            def resolve_match(match):
                return resolve_reference(match.group(0))

            for fid, obj in objects.items():
                if obj["class_id"] == "1":
                    comp_matches = re.findall(
                        r"-\s*(?:component|114):\s*\{fileID:\s*(\d+)\}", obj["data"]
                    )
                    for c_id in comp_matches:
                        if c_id in objects:
                            c_class = objects[c_id]["class_id"]
                            if c_class != "114":
                                c_name = native_class_map.get(
                                    c_class, f"Native_{c_class}"
                                )
                                game_objects[fid]["components"].append(c_name)

                elif obj["class_id"] == "114":
                    go_id = comp_to_go.get(fid)
                    if not go_id or go_id not in game_objects:
                        continue

                    script_match = re.search(
                        r"m_Script:.*guid:\s*([a-fA-F0-9]+)", obj["data"]
                    )
                    script_name = "UnknownScript"
                    if script_match:
                        guid = script_match.group(1)
                        script_name = guid_map.get(guid, f"UnknownScript_{guid[:8]}")

                    param_section = (
                        obj["data"].split("m_Script:")[1]
                        if "m_Script:" in obj["data"]
                        else obj["data"]
                    )
                    lines = param_section.split("\n")

                    formatted_params = []
                    skip_indent_level = -1
                    noise_keys = (
                        "m_ObjectHideFlags",
                        "m_CorrespondingSourceObject",
                        "m_PrefabInstance",
                        "m_PrefabAsset",
                        "m_GameObject",
                        "m_Enabled",
                        "m_EditorHideFlags",
                        "m_EditorClassIdentifier",
                    )

                    for line in lines:
                        if not line.strip():
                            continue
                        indent = len(line) - len(line.lstrip())
                        clean_line = line.strip()

                        if skip_indent_level != -1:
                            if indent > skip_indent_level:
                                continue
                            else:
                                skip_indent_level = -1

                        key_match = re.match(r"^-?\s*([a-zA-Z0-9_]+):", clean_line)
                        if key_match:
                            key_name = key_match.group(1)
                            if key_name in noise_keys:
                                skip_indent_level = indent
                                continue

                        if len(clean_line) > 200:
                            clean_line = (
                                clean_line[:60] + " ... [Data too long, skipped.]"
                            )

                        formatted_params.append(" " * indent + clean_line)

                    raw_params_str = "\n".join(formatted_params)
                    raw_params_str = re.sub(
                        r"\{fileID:\s*(\d+)\}", resolve_match, raw_params_str
                    )

                    event_flows = []
                    calls = re.findall(
                        r"m_Target:\s*([^\n]+)\n(?:[^\n]*\n){0,3}\s*m_MethodName:\s*([a-zA-Z0-9_]+)",
                        raw_params_str,
                    )
                    for target_val, method_name in calls:
                        if method_name not in ("Invoke", "set_enabled"):
                            event_flows.append(
                                f"⚡ [Event Callback] ➔ {target_val}.{method_name}()"
                            )

                    game_objects[go_id]["mono_behaviours"].append(
                        {
                            "script": script_name,
                            "raw_params": raw_params_str,
                            "event_flows": event_flows,
                        }
                    )

            prefab_instances = []
            for fid, obj in objects.items():
                if obj["class_id"] == "1001":
                    source_match = re.search(
                        r"m_SourcePrefab:.*guid:\s*([a-fA-F0-9]+)", obj["data"]
                    )
                    parent_match = re.search(
                        r"m_TransformParent:\s*\{fileID:\s*(\d+)\}", obj["data"]
                    )

                    prefab_name = "UnknownPrefab"
                    if source_match:
                        guid = source_match.group(1)
                        prefab_name = guid_map.get(guid, f"Prefab_{guid[:8]}")

                    parent_str = "Root"
                    if parent_match:
                        parent_id = parent_match.group(1)
                        if parent_id in comp_to_go:
                            p_go = comp_to_go[parent_id]
                            if p_go in game_objects:
                                parent_str = game_objects[p_go]["name"]

                    overrides = []
                    mod_pattern = r"propertyPath:\s*([^\n]+)\n\s*value:\s*([^\n]*)\n\s*objectReference:\s*([^\n]+)"
                    for match in re.finditer(mod_pattern, obj["data"]):
                        prop = match.group(1).strip()
                        val = match.group(2).strip()
                        objRef = match.group(3).strip()

                        if prop.startswith(
                            (
                                "m_LocalPosition",
                                "m_LocalRotation",
                                "m_LocalScale",
                                "m_LocalEulerAngles",
                                "m_RootOrder",
                                "m_AnchoredPosition",
                                "m_SizeDelta",
                            )
                        ):
                            continue
                        if val == "" and "fileID: 0" in objRef:
                            continue

                        disp_val = val if val else resolve_reference(objRef)
                        overrides.append(f"    ※ [Override] {prop} = {disp_val}")

                    prefab_str = (
                        f"▼ [Prefab Instance: {prefab_name}] (Parent: {parent_str})"
                    )
                    if overrides:
                        prefab_str += "\n" + "\n".join(overrides)
                    prefab_instances.append(prefab_str)

            def print_tree(go_id, indent=""):
                go = game_objects[go_id]
                all_comps = go["components"] + [
                    mb["script"] for mb in go["mono_behaviours"]
                ]
                comp_str = f" [{', '.join(all_comps)}]" if all_comps else ""
                parsed_result.append(f"{indent}▼ {go['name']}{comp_str}")

                for mb in go["mono_behaviours"]:
                    if mb.get("event_flows"):
                        for ev in mb["event_flows"]:
                            parsed_result.append(f"{indent}  {ev}")

                    if mb["raw_params"]:
                        for p_line in mb["raw_params"].split("\n"):
                            parsed_result.append(f"{indent}  {p_line}")

                for child_id in go["children"]:
                    print_tree(child_id, indent + "  ")

            root_gos = [fid for fid, go in game_objects.items() if go["is_root"]]

            if root_gos:
                parsed_result.append("**Hierarchy Tree:**")
                for fid in root_gos:
                    print_tree(fid)

            if prefab_instances:
                parsed_result.append("\n**Prefab Instances & Overrides:**")
                # forループによる低速な順次追加を避け、extend() を使用してパフォーマンスとメモリ効率を向上
                parsed_result.extend(prefab_instances)

        except Exception as e:  # noqa: BLE001
            # 予期せぬデータ構造エラー時も全体のクラッシュを防ぎメッセージを記録
            parsed_result.append(f"Error parsing Relational YAML: {e!s}")

        raw_yaml_text = "\n".join(parsed_result)

        # --- [防弾全局截断器 / Global Long-Line Guard]: 長行バイナリのカット ---
        safe_lines = []
        for line in raw_yaml_text.split("\n"):
            if len(line) > 250:
                safe_lines.append(
                    line[:80]
                    + " ... [WARNING: Line truncated. Binary/Hex data isolated.]"
                )
            else:
                safe_lines.append(line)
        return "\n".join(safe_lines)

    def start_packing(self):
        """
        パッキング処理の開始とUI状態更新。別スレッドを生成して重い処理を実行する。
        (パック処理の起動)
        """
        target_dir = self.dir_entry.get().strip()
        output_file = self.out_entry.get().strip()
        code_ext_str = self.code_ext_entry.get().strip()
        unity_ext_str = self.unity_ext_entry.get().strip()

        if not target_dir or not os.path.isdir(target_dir):
            messagebox.showerror(
                "エラー", "有効なターゲットディレクトリを選択してください！"
            )
            return
        if not output_file:
            messagebox.showerror("エラー", "有効な出力ファイルパスを選択してください！")
            return

        code_extensions = [
            ext.strip().lower() for ext in code_ext_str.split(",") if ext.strip()
        ]
        unity_extensions = [
            ext.strip().lower() for ext in unity_ext_str.split(",") if ext.strip()
        ]

        if not code_extensions and not unity_extensions:
            messagebox.showerror("エラー", "少なくとも1つの拡張子を入力してください！")
            return

        self.pack_btn.config(state="disabled", text="処理中...", bg="lightgray")
        self.progress_var.set(0)
        self._log_internal("")

        threading.Thread(
            target=self._packing_task_thread_chunked,
            args=(target_dir, output_file, code_extensions, unity_extensions),
            daemon=True,
        ).start()

    def _packing_task_thread_chunked(
        self, target_dir, output_file, code_extensions, unity_extensions
    ):
        """
        バックグラウンドスレッドで実行されるメイン処理。
        文字数監視に基づく自動ファイル分割 (Auto-Chunking Writer) を行う。
        (マルチスレッドパック本体)
        """
        self.log_safe(f"ディレクトリのスキャンを開始します: {target_dir}")
        processed_code_count = 0
        processed_unity_count = 0

        guid_map = {}
        if unity_extensions:
            guid_map = self.build_guid_map(target_dir)

        code_files_list = []
        unity_files_list = []

        for root_dir, _, files in os.walk(target_dir):
            for file in files:
                ext_lower = os.path.splitext(file)[1].lower()
                file_path = os.path.join(root_dir, file)
                rel_path = os.path.relpath(file_path, target_dir)

                if ext_lower in code_extensions:
                    code_files_list.append((file_path, rel_path, ext_lower))
                elif ext_lower in unity_extensions:
                    unity_files_list.append((file_path, rel_path, ext_lower))

        total_files = len(code_files_list) + len(unity_files_list)
        if total_files == 0:
            self.log_safe("対象となるファイルが見つかりませんでした。")
            self.finish_ui_safe(False, "エラー", "対象ファイルがありません。")
            return

        # DTZ005 修正: タイムゾーンを明示指定した現在日時の取得
        current_time = (
            datetime.datetime.now(datetime.timezone.utc)
            .astimezone()
            .strftime("%Y-%m-%d %H:%M:%S")
        )
        files_processed_so_far = 0

        # --- 黄金安全長さ分割設定 (Chunking Configuration) ---
        MAX_CHARS_PER_FILE = 350000  # 各ファイル最大 35万文字
        part_index = 1

        base_dir = os.path.dirname(output_file)
        base_name, ext = os.path.splitext(os.path.basename(output_file))

        def get_part_filepath(idx):
            return os.path.join(base_dir, f"{base_name}_part{idx}{ext}")

        current_out_path = get_part_filepath(part_index)
        self.log_safe(
            f">> 分割出力ファイル 1 をオープン: {os.path.basename(current_out_path)}"
        )

        try:
            # SIM115 対策: ファイルオープン時の警告抑止コメントを付与 (手動でマルチパーツ管理するため)
            outfile = open(current_out_path, "w", encoding="utf-8", buffering=1)  # noqa: SIM115
            char_counter = 0

            def write_text(text):
                nonlocal outfile, part_index, char_counter
                if char_counter + len(text) > MAX_CHARS_PER_FILE:
                    outfile.close()
                    self.log_safe(
                        f"   [分块提示] 当前文件达到 {char_counter} 字符，已安全切片。"
                    )
                    part_index += 1
                    next_out_path = get_part_filepath(part_index)
                    self.log_safe(
                        f">> 创建并打开新分块文件 {part_index}: {os.path.basename(next_out_path)}"
                    )
                    outfile = open(next_out_path, "w", encoding="utf-8", buffering=1)  # noqa: SIM115
                    char_counter = 0
                    # 続篇ヘッダーの書き込み
                    header_continuation = f"# 📁 解析結果 (Part {part_index} 续篇)\n- **生成日時:** `{current_time}`\n\n---\n\n"
                    outfile.write(header_continuation)
                    char_counter += len(header_continuation)

                outfile.write(text)
                char_counter += len(text)
                outfile.flush()
                os.fsync(outfile.fileno())

            # 初期ファイルのヘッダー書き込み
            initial_header = f"# 📁 ディレクトリコード & プレハブ 解析結果 (Part {part_index})\n\n- **ターゲットディレクトリ:** `{target_dir}`\n- **生成日時:** `{current_time}`\n\n---\n\n"
            write_text(initial_header)

            # --- パス 1: コードファイル ---
            self.log_safe(">> フェーズ 1: コードファイルの抽出を開始...")
            for file_path, rel_path, ext_lower in code_files_list:
                try:
                    with open(
                        file_path, "r", encoding="utf-8", errors="replace"
                    ) as infile:
                        content = infile.read()
                    lang = self.get_language_identifier(ext_lower)

                    block_text = (
                        f"### File: `{rel_path}`\n```{lang}\n{content}\n```\n\n"
                    )
                    write_text(block_text)

                    processed_code_count += 1
                except OSError as e:
                    self.log_safe(f"読み込み失敗 {rel_path}: {e!s}")

                files_processed_so_far += 1
                self.update_progress_safe((files_processed_so_far / total_files) * 100)

            # --- パス 2: Unityデータファイル ---
            self.log_safe("\n>> フェーズ 2: Unityデータの解析を開始...")
            for file_path, rel_path, ext_lower in unity_files_list:
                try:
                    yaml_analysis = self.parse_unity_yaml_relational(
                        file_path, guid_map
                    )
                    block_text = (
                        f"### Prefab/Scene Data: `{rel_path}`\n{yaml_analysis}\n\n"
                    )
                    write_text(block_text)

                    processed_unity_count += 1
                    self.log_safe(f"Unity解析完了: {rel_path}")
                except Exception as e:  # noqa: BLE001
                    # 個別YAML解析例外は記録して後続ファイルの処理を継続する
                    self.log_safe(f"Unity解析失敗 {rel_path}: {e!s}")

                files_processed_so_far += 1
                self.update_progress_safe((files_processed_so_far / total_files) * 100)

            outfile.close()

            self.log_safe("-" * 30)
            self.log_safe(
                f"処理完了！\n生成された分塊文件数: {part_index} 个\nコードファイル: {processed_code_count} 個\nUnityデータ: {processed_unity_count} 個"
            )
            self.finish_ui_safe(
                True,
                "処理完了！",
                f"生成された分塊文件数 {part_index} 個 Markdown ファイル。",
            )

        except Exception as e:  # noqa: BLE001
            # 最外郭処理例外の安全なキャッチとログ出力
            self.log_safe(f"致命的なエラー: {e!s}")
            self.finish_ui_safe(
                False, "エラー", f"処理中にエラーが発生しました:\n{e!s}"
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = FilePackerApp(root)
    root.mainloop()
