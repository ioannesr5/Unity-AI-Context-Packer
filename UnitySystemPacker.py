import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.scrolledtext as st
import datetime
import re
import threading

class FilePackerApp:
    def __init__(self, root):
        """
        GUIの初期化とレイアウト設定 (GUIの構築と各ウィジェットの配置を行います)
        """
        self.root = root
        self.root.title("AI Script & Prefab Packer (マルチスレッド・完全リレーショナル版)")
        self.root.geometry("650x620")
        self.root.resizable(False, False)

        # ターゲットディレクトリのUIコンポーネント
        tk.Label(root, text="ターゲットディレクトリ (コード・メタ共通):").place(x=20, y=20)
        self.dir_entry = tk.Entry(root, width=55)
        self.dir_entry.place(x=20, y=45)
        tk.Button(root, text="参照...", command=self.browse_directory).place(x=450, y=40)

        # 出力ファイルのUIコンポーネント
        tk.Label(root, text="出力ファイル:").place(x=20, y=80)
        self.out_entry = tk.Entry(root, width=55)
        self.out_entry.place(x=20, y=105)
        tk.Button(root, text="参照...", command=self.browse_output).place(x=450, y=100)

        # コード拡張子の設定コンポーネント
        tk.Label(root, text="対象のコード拡張子 (カンマ区切り):").place(x=20, y=140)
        self.code_ext_entry = tk.Entry(root, width=70)
        self.code_ext_entry.insert(0, ".cs, .py, .shader, .cginc, .hlsl")
        self.code_ext_entry.place(x=20, y=165)

        # Unityデータ拡張子の設定コンポーネント
        tk.Label(root, text="解析するUnityデータ拡張子 (カンマ区切り):").place(x=20, y=200)
        self.unity_ext_entry = tk.Entry(root, width=70)
        self.unity_ext_entry.insert(0, ".prefab, .unity, .asset")
        self.unity_ext_entry.place(x=20, y=225)

        # 実行ボタン (参照を変数に保存して無効化/有効化を切り替えられるようにする)
        self.pack_btn = tk.Button(root, text="パック開始", command=self.start_packing, bg="lightblue", width=25, height=2)
        self.pack_btn.place(x=225, y=265)

        # --- NEW: プログレスバー (Progress Bar) ---
        self.progress_var = tk.DoubleVar()
        self.progressbar = ttk.Progressbar(root, variable=self.progress_var, maximum=100, mode='determinate')
        self.progressbar.place(x=20, y=325, width=610, height=20)

        # ログ表示エリア
        tk.Label(root, text="実行ログ:").place(x=20, y=355)
        self.log_area = st.ScrolledText(root, width=82, height=12, state='disabled')
        self.log_area.place(x=20, y=380)

    # ========================================================
    # スレッドセーフなUI更新メソッド (Thread-safe UI Updaters)
    # ========================================================
    def log_safe(self, message):
        """バックグラウンドスレッドから安全にログを出力する"""
        self.root.after(0, self._log_internal, message)

    def _log_internal(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def update_progress_safe(self, value):
        """プログレスバーを安全に更新する"""
        self.root.after(0, self.progress_var.set, value)

    def finish_ui_safe(self, success, title, msg):
        """処理完了時のUIリセットとポップアップ"""
        self.root.after(0, self._finish_ui_internal, success, title, msg)

    def _finish_ui_internal(self, success, title, msg):
        self.pack_btn.config(state='normal', text="パック開始", bg="lightblue")
        if success:
            messagebox.showinfo(title, msg)
        else:
            messagebox.showerror(title, msg)

    # ========================================================
    # イベントハンドラ
    # ========================================================
    def browse_directory(self):
        directory = filedialog.askdirectory(title="対象ディレクトリを選択してください")
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)

    def browse_output(self):
        file_path = filedialog.asksaveasfilename(
            title="出力ファイルの保存先を選択してください",
            defaultextension=".md",
            filetypes=[("Markdown Files", "*.md"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.out_entry.delete(0, tk.END)
            self.out_entry.insert(0, file_path)

    def get_language_identifier(self, ext):
        ext = ext.lower()
        mapping = {
            ".cs": "csharp", ".py": "python", ".json": "json",
            ".shader": "hlsl", ".cginc": "hlsl", ".hlsl": "hlsl",
            ".yaml": "yaml", ".prefab": "yaml", ".unity": "yaml", ".asset": "yaml"
        }
        return mapping.get(ext, "")

    # ========================================================
    # コア解析ロジック (バックグラウンド実行可能)
    # ========================================================
    def build_guid_map(self, target_dir):
        guid_to_name = {}
        self.log_safe("GUIDマッピングの構築を開始します...")
        guid_pattern = re.compile(r'^guid:\s*([a-fA-F0-9]+)', re.MULTILINE)
        count = 0
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".meta"):
                    base_name = file[:-5]
                    if base_name.endswith(".cs"):
                        meta_path = os.path.join(root, file)
                        try:
                            with open(meta_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                match = guid_pattern.search(content)
                                if match:
                                    guid = match.group(1)
                                    guid_to_name[guid] = os.path.splitext(base_name)[0]
                                    count += 1
                        except Exception as e:
                            self.log_safe(f"メタファイル読み込みエラー {meta_path}: {e}")
        self.log_safe(f"GUIDマッピング完了: {count} 個のスクリプトGUIDを記録しました。")
        return guid_to_name

    def parse_unity_yaml_relational(self, file_path, guid_map):
        parsed_result = []
        parsed_result.append(f"<!-- Relational YAML Analysis: {os.path.basename(file_path)} -->")

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            objects = {}
            blocks = re.split(r'^---\s*!u!(\d+)\s+&(\d+)', content, flags=re.MULTILINE)
            for i in range(1, len(blocks), 3):
                class_id = blocks[i]
                file_id = blocks[i+1]
                block_data = blocks[i+2]
                objects[file_id] = {'class_id': class_id, 'data': block_data}

            game_objects = {}
            transforms = {} 
            comp_to_go = {} 

            native_class_map = {
                '4': 'Transform', '20': 'Camera', '23': 'MeshRenderer', '33': 'MeshFilter',
                '54': 'Rigidbody', '65': 'BoxCollider', '114': 'MonoBehaviour',
                '136': 'CapsuleCollider', '137': 'SkinnedMeshRenderer', '212': 'SpriteRenderer', 
                '224': 'RectTransform', '108': 'Light', '198': 'ParticleSystem'
            }

            for fid, obj in objects.items():
                if obj['class_id'] == '1':
                    name_match = re.search(r'm_Name:\s*(.*)', obj['data'])
                    name = name_match.group(1).strip() if name_match else "Unnamed"
                    game_objects[fid] = {
                        'name': name, 'components': [], 'mono_behaviours': [],
                        'children': [], 'is_root': True, 'transform_id': None
                    }

            for fid, obj in objects.items():
                go_match = re.search(r'm_GameObject:\s*\{fileID:\s*(\d+)\}', obj['data'])
                if go_match:
                    go_id = go_match.group(1)
                    comp_to_go[fid] = go_id

                    if obj['class_id'] in ('4', '224'):
                        transforms[fid] = go_id
                        if go_id in game_objects:
                            game_objects[go_id]['transform_id'] = fid
                            father_match = re.search(r'm_Father:\s*\{fileID:\s*(\d+)\}', obj['data'])
                            father_id = father_match.group(1) if father_match else "0"
                            if father_id != "0":
                                game_objects[go_id]['is_root'] = False
                                game_objects[go_id]['father_trans'] = father_id

            for go_id, go in game_objects.items():
                father_trans = go.get('father_trans')
                if father_trans and father_trans in transforms:
                    father_go_id = transforms[father_trans]
                    if father_go_id in game_objects:
                        game_objects[father_go_id]['children'].append(go_id)

            def resolve_reference(ref_str):
                ref_match = re.search(r'\{fileID:\s*(\d+)\}', ref_str)
                if ref_match:
                    ref_id = ref_match.group(1)
                    if ref_id == "0": return "None"
                    if ref_id in comp_to_go:
                        ref_go = comp_to_go[ref_id]
                        if ref_go in game_objects: return f"[Ref -> {game_objects[ref_go]['name']}]"
                    if ref_id in game_objects:
                        return f"[Ref -> {game_objects[ref_id]['name']}]"
                return ref_str

            def resolve_match(match):
                return resolve_reference(match.group(0))

            for fid, obj in objects.items():
                if obj['class_id'] == '1':
                    comp_matches = re.findall(r'-\s*(?:component|114):\s*\{fileID:\s*(\d+)\}', obj['data'])
                    for c_id in comp_matches:
                        if c_id in objects:
                            c_class = objects[c_id]['class_id']
                            if c_class != '114':
                                c_name = native_class_map.get(c_class, f"Native_{c_class}")
                                game_objects[fid]['components'].append(c_name)

                elif obj['class_id'] == '114':
                    go_id = comp_to_go.get(fid)
                    if not go_id or go_id not in game_objects: continue

                    script_match = re.search(r'm_Script:.*guid:\s*([a-fA-F0-9]+)', obj['data'])
                    script_name = "UnknownScript"
                    if script_match:
                        guid = script_match.group(1)
                        script_name = guid_map.get(guid, f"UnknownScript_{guid[:8]}")

                    param_section = obj['data'].split('m_Script:')[1] if 'm_Script:' in obj['data'] else obj['data']
                    lines = param_section.split('\n')
                    
                    formatted_params = []
                    skip_indent_level = -1
                    noise_keys = ('m_ObjectHideFlags', 'm_CorrespondingSourceObject', 'm_PrefabInstance', 
                                  'm_PrefabAsset', 'm_GameObject', 'm_Enabled', 'm_EditorHideFlags', 'm_EditorClassIdentifier')

                    for line in lines:
                        if not line.strip(): continue
                        indent = len(line) - len(line.lstrip())
                        clean_line = line.strip()
                        
                        if skip_indent_level != -1:
                            if indent > skip_indent_level: continue 
                            else: skip_indent_level = -1 
                                
                        key_match = re.match(r'^-?\s*([a-zA-Z0-9_]+):', clean_line)
                        if key_match:
                            key_name = key_match.group(1)
                            if key_name in noise_keys:
                                skip_indent_level = indent
                                continue
                                
                        if len(clean_line) > 200:
                            clean_line = clean_line[:60] + f" ... [Data too long, skipped. Length: {len(clean_line)}]"
                            
                        formatted_params.append(" " * indent + clean_line)

                    raw_params_str = "\n".join(formatted_params)
                    raw_params_str = re.sub(r'\{fileID:\s*(\d+)\}', resolve_match, raw_params_str)
                    
                    event_flows = []
                    calls = re.findall(r'm_Target:\s*([^\n]+)\n(?:[^\n]*\n){0,3}\s*m_MethodName:\s*([a-zA-Z0-9_]+)', raw_params_str)
                    for target_val, method_name in calls:
                        if method_name not in ('Invoke', 'set_enabled'): 
                            event_flows.append(f"⚡ [Event Callback] ➔ {target_val}.{method_name}()")

                    game_objects[go_id]['mono_behaviours'].append({
                        'script': script_name, 
                        'raw_params': raw_params_str,
                        'event_flows': event_flows
                    })

            prefab_instances = []
            for fid, obj in objects.items():
                if obj['class_id'] == '1001':
                    source_match = re.search(r'm_SourcePrefab:.*guid:\s*([a-fA-F0-9]+)', obj['data'])
                    parent_match = re.search(r'm_TransformParent:\s*\{fileID:\s*(\d+)\}', obj['data'])

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
                                parent_str = game_objects[p_go]['name']

                    overrides = []
                    mod_pattern = r'propertyPath:\s*([^\n]+)\n\s*value:\s*([^\n]*)\n\s*objectReference:\s*([^\n]+)'
                    for match in re.finditer(mod_pattern, obj['data']):
                        prop = match.group(1).strip()
                        val = match.group(2).strip()
                        objRef = match.group(3).strip()
                        
                        if prop.startswith(('m_LocalPosition', 'm_LocalRotation', 'm_LocalScale', 'm_LocalEulerAngles', 'm_RootOrder', 'm_AnchoredPosition', 'm_SizeDelta')):
                            continue 
                        if val == '' and 'fileID: 0' in objRef:
                            continue
                            
                        disp_val = val if val else resolve_reference(objRef)
                        overrides.append(f"    ※ [Override] {prop} = {disp_val}")

                    prefab_str = f"▼ [Prefab Instance: {prefab_name}] (Parent: {parent_str})"
                    if overrides:
                        prefab_str += "\n" + "\n".join(overrides)
                    prefab_instances.append(prefab_str)

            def print_tree(go_id, indent=""):
                go = game_objects[go_id]
                all_comps = go['components'] + [mb['script'] for mb in go['mono_behaviours']]
                comp_str = f" [{', '.join(all_comps)}]" if all_comps else ""
                parsed_result.append(f"{indent}▼ {go['name']}{comp_str}")

                for mb in go['mono_behaviours']:
                    if mb.get('event_flows'):
                        for ev in mb['event_flows']:
                            parsed_result.append(f"{indent}  {ev}")
                    
                    if mb['raw_params']:
                        for p_line in mb['raw_params'].split('\n'):
                            parsed_result.append(f"{indent}  {p_line}")

                for child_id in go['children']:
                    print_tree(child_id, indent + "  ")

            root_gos = [fid for fid, go in game_objects.items() if go['is_root']]

            if root_gos:
                parsed_result.append("**Hierarchy Tree:**")
                for fid in root_gos:
                    print_tree(fid)

            if prefab_instances:
                parsed_result.append("\n**Prefab Instances & Overrides:**")
                for p in prefab_instances:
                    parsed_result.append(p)

        except Exception as e:
            parsed_result.append(f"Error parsing Relational YAML: {str(e)}")

        final_text = "\n".join(parsed_result)
         # Global failsafe: Prevent massive binary blobs from any class ID
        safe_lines = []
        for line in final_text.split('\n'):
            if len(line) > 250:
                safe_lines.append(line[:80] + " ... [WARNING: Line truncated. Binary/Hex data isolated.]")
            else:
                safe_lines.append(line)

        return "\n".join(safe_lines)

    # ========================================================
    # スレッド制御とメインプロセス
    # ========================================================
    def start_packing(self):
        target_dir = self.dir_entry.get().strip()
        output_file = self.out_entry.get().strip()
        code_ext_str = self.code_ext_entry.get().strip()
        unity_ext_str = self.unity_ext_entry.get().strip()

        if not target_dir or not os.path.isdir(target_dir):
            messagebox.showerror("エラー", "有効なターゲットディレクトリを選択してください！")
            return
        if not output_file:
            messagebox.showerror("エラー", "有効な出力ファイルパスを選択してください！")
            return
        
        code_extensions = [ext.strip().lower() for ext in code_ext_str.split(",") if ext.strip()]
        unity_extensions = [ext.strip().lower() for ext in unity_ext_str.split(",") if ext.strip()]
        
        if not code_extensions and not unity_extensions:
            messagebox.showerror("エラー", "少なくとも1つの拡張子を入力してください！")
            return

        # UIロックと初期化
        self.pack_btn.config(state='disabled', text="処理中...", bg="lightgray")
        self.progress_var.set(0)
        self._log_internal("") # クリア
        
        # バックグラウンドスレッドで重い処理を開始
        threading.Thread(
            target=self._packing_task_thread, 
            args=(target_dir, output_file, code_extensions, unity_extensions), 
            daemon=True
        ).start()

    def _packing_task_thread(self, target_dir, output_file, code_extensions, unity_extensions):
        """
        別スレッドで実行される本体。UIをフリーズさせずに正規表現やI/Oを処理します。
        """
        self.log_safe(f"ディレクトリのスキャンを開始します: {target_dir}")
        processed_code_count = 0
        processed_unity_count = 0
        
        guid_map = {}
        if unity_extensions:
            guid_map = self.build_guid_map(target_dir)

        # 全ファイルをリストアップして総数を取得 (プログレスバー計算用)
        code_files_list = []
        unity_files_list = []
        
        for root_dir, dirs, files in os.walk(target_dir):
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

        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        files_processed_so_far = 0
        
        try:
            with open(output_file, 'w', encoding='utf-8', buffering=1) as outfile:
                outfile.write(f"# ディレクトリコード & プレハブ 解析結果\n\n")
                outfile.write(f"- **ターゲットディレクトリ:** `{target_dir}`\n")
                outfile.write(f"- **生成日時:** `{current_time}`\n\n---\n\n")
                
                # --- パス 1: コードファイル ---
                self.log_safe(">> フェーズ 1: コードファイルの抽出を開始...")
                for file_path, rel_path, ext_lower in code_files_list:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='replace') as infile:
                            content = infile.read()
                        lang = self.get_language_identifier(ext_lower)
                        outfile.write(f"### File: `{rel_path}`\n```{lang}\n{content}\n```\n\n")
                        
                        outfile.flush()
                        os.fsync(outfile.fileno())
                        
                        processed_code_count += 1
                    except Exception as e:
                        self.log_safe(f"読み込み失敗 {rel_path}: {str(e)}")
                    
                    files_processed_so_far += 1
                    self.update_progress_safe((files_processed_so_far / total_files) * 100)

                # --- パス 2: Unityデータファイル ---
                self.log_safe("\n>> フェーズ 2: Unityデータの解析を開始...")
                for file_path, rel_path, ext_lower in unity_files_list:
                    
                    # 制限解除済み: 警告のみ出し、処理は続行する
                    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    if file_size_mb > 5.0:
                        self.log_safe(f"⏳ 注意: `{rel_path}` は大容量ファイルです ({file_size_mb:.2f} MB)。")
                        self.log_safe("   バックグラウンドで解析中です。お待ちください...")
                    
                    try:
                        yaml_analysis = self.parse_unity_yaml_relational(file_path, guid_map)
                        outfile.write(f"### Prefab/Scene Data: `{rel_path}`\n{yaml_analysis}\n\n")
                        
                        outfile.flush()
                        os.fsync(outfile.fileno())
                        
                        processed_unity_count += 1
                        self.log_safe(f"Unity解析完了: {rel_path}")
                    except Exception as e:
                        self.log_safe(f"Unity解析失敗 {rel_path}: {str(e)}")
                        
                    files_processed_so_far += 1
                    self.update_progress_safe((files_processed_so_far / total_files) * 100)

            self.log_safe("-" * 30)
            self.log_safe(f"処理完了！\nコードファイル: {processed_code_count} 個\nUnityデータ: {processed_unity_count} 個")
            self.finish_ui_safe(True, "完了", "全てのエクスポートと解析が安全に完了しました。")

        except Exception as e:
            self.log_safe(f"致命的なエラー: {str(e)}")
            self.finish_ui_safe(False, "エラー", f"処理中にエラーが発生しました:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FilePackerApp(root)
    root.mainloop()