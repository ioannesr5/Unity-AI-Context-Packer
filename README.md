# 📦 Unity2Context (scriptpacker)

> **Transform raw Unity Prefabs, Scenes, and Codebases into structured, LLM-optimized Markdown with 1 Click.**  
> **Unity プレハブ（Prefab）・シーンデータおよびソースコードを AI（ChatGPT / Claude / Gemini）に最適な構造化 Markdown へ一括変換する極小 GUI ツール。**  
> **一键将 Unity 预制体（Prefab）、场景（Scene）数据与源代码转换为适合大语言模型（LLM）理解的结构化 Markdown 上下文（Context）。**

[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/ioannesr5/scriptpacker?style=social)](https://github.com/ioannesr5/scriptpacker)

---

## 🌟 Why Unity2Context? / なぜこのツールが必要なのか？ / 为什么需要本工具？

When feeding Unity projects into AI models (ChatGPT, Claude, Gemini), raw `.prefab` or `.unity` serialized files (シリアライズデータ) usually cause heavy issues: **unreadable GUID references, infinite binary/mesh array noise, and blown-out context limits (コンテキストウィンドウの限界オーバー)**.

`scriptpacker` solves this by intelligently parsing Unity YAML references, reconstructing hierarchy structures (階層構造), and cleanly packing source code into auto-chunked (自動分割 / チャンク化) Markdown files.

- **English**: Parses complex Unity YAML serialized files, resolves GUIDs back to C# script names, extracts object hierarchy with event flows, and splits outputs safely before reaching LLM context boundaries.
- **日本語**: Unity の複雑なシリアライズデータを解析し、GUID を実際の C# スクリプト名へ逆引き補正。Hierarchy（階層構造）やイベントフローを抽出した上で、LLM のコンテキスト上限を超えないよう安全に自動分割（チャンク化）出力します。
- **中文**: 深度解析 Unity YAML 序列化数据，自动将 `.meta` 中的 GUID 还原为真实的 C# 脚本名；解析层级树（Hierarchy Tree）与事件回调（Event Flow），并针对大模型上下文限制（Context Window）提供安全线级的自动分块（Auto-Chunking）与防爆截断。

---

## 🔥 Key Features / 主要機能 / 核心特性

- 🔍 **Relational Unity YAML Parser (リレーショナル YAML 解析)**
  - **GUID-to-Script Resolution**: Scans `.meta` files to map `guid: xxx` directly to actual C# class names (`guid: 89a...` $\rightarrow$ `GameManager.cs`).
  - **Hierarchy Tree Reconstruction (階層構造の再構築)**: Reconstructs parent-child GameObject relationships into readable trees.
  - **Event Callback Extraction**: Captures UnityEvents (e.g., `Button.onClick` $\rightarrow$ `[Event Callback] ➔ GameManager.OnStartButtonClicked()`).
  - **Prefab Overrides**: Highlights modified properties while discarding RectTransform / Position clutter.
- 🛡️ **Bulletproof Guard & Auto-Chunking (自動分割 & 完全防爆)**
  - **350k Character Split**: Automatically cuts output into safe file chunks (`output_part1.md`, `output_part2.md`) to prevent token overflows.
  - **Binary/Hex Isolation**: Automatically truncates lines exceeding 250 characters (mesh data, array dumps) to prevent AI context pollution and rendering slowdowns.
- ⚡ **Multi-Language Source Packing (多言語ソースコードパッキング)**
  - Packs C# (`.cs`), Python (`.py`), Shaders (`.shader`, `.cginc`, `.hlsl`), and custom text formats with syntax highlighting headers.
- 🧵 **Non-blocking Multithreaded GUI (マルチスレッド GUI)**
  - Smooth Tkinter user interface with real-time progress bar and log stream without interface freezing.

---

## 🛠️ Prerequisites / 動作環境 / 环境要求

- **Python**: `3.8` or higher
- **Tkinter**: Built-in on Windows / macOS.  
  *(Linux users may need: `sudo apt-get install python3-tk`)*

---

## 🚀 Quick Start / クイックスタート / 快速开始

### 1. Clone the repository (リポジトリの取得)
```bash
git clone https://github.com/ioannesr5/scriptpacker.git
cd scriptpacker
```

### 2. Launch the application (アプリケーションの起動)
```bash
python UnitySystemPackerchunk.py
```
*(Note: You can rename `UnitySystemPackerchunk.py` to `main.py` as an entry point (エントリーポイント) if preferred.)*

### 3. Usage (使用方法)
1. Select your target directory (ターゲットディレクトリ) containing code and `.meta` files.
2. Specify the output path (e.g., `output.md`).
3. Adjust code and Unity file extensions if needed.
4. Click **パック開始 (自動分割)** / **Start Packing**.

---

## 📄 Output Sample / 解析結果イメージ / 解析输出样例

Instead of unreadable raw YAML, AI receives structured Markdown like this:

```markdown
# 📁 ディレクトリコード & プレハブ 解析結果 (Part 1)

### File: `Assets/Scripts/GameManager.cs`
```csharp
public class GameManager : MonoBehaviour { ... }
```

### Prefab/Scene Data: `Assets/Scenes/MainScene.unity`
<!-- Relational YAML Analysis: MainScene.unity -->
**Hierarchy Tree:**
▼ Main Canvas [RectTransform, CanvasScaler]
  ▼ StartButton [RectTransform, Image, Button]
    ⚡ [Event Callback] ➔ [Ref -> GameManager].OnStartButtonClicked()
    ▼ Text [RectTransform, Text]
▼ Managers [Transform]
  ▼ GameManager [GameManager]
```

---

## ⚙️ Configuration / 設定項目

| Field (項目) | Default (デフォルト) | Description (説明) |
| :--- | :--- | :--- |
| **Code Extensions** | `.cs, .py, .shader, .cginc, .hlsl` | File types packed as raw source code blocks. |
| **Unity Extensions** | `.prefab, .unity, .asset` | Files parsed via Relational YAML Engine. |
| **Chunk Limit** | `350,000 chars` | Auto-splits Markdown when reached to respect AI Context Windows (コンテキストウィンドウ). |
| **Line Guard Limit** | `250 chars` | Hard-cuts binary/hex data lines to avoid token waste. |

---

## 💬 Community & Feedback / コミュニティ & フィードバック

If you encounter any issues with specific Unity YAML configurations, please feel free to open an [Issue](https://github.com/ioannesr5/scriptpacker/issues) or submit a [Pull Request](https://github.com/ioannesr5/scriptpacker/pulls).

⭐ **If this tool saves your time when working with AI, please give it a Star!**  
⭐ **AI 開発の効率化に役立った場合は、ぜひ GitHub で Star ⭐️ をお願いします！**  
⭐ **如果这个工具在 AI 辅助开发中帮到了你，欢迎点个 ⭐️ Star 支持一下！**
