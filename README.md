# 📦 AI Script & Prefab Packer

> **Transform raw Unity Prefabs, Scenes, and Codebases into structured, LLM-optimized Markdown with 1 Click.**  
> **Unity プレハブ・シーンデータおよびソースコードを AI（ChatGPT / Claude / Gemini）に最適な構造化 Markdown へ一括変換する極小 GUI ツール。**  
> **一键将 Unity 预制体（Prefab）、场景（Scene）数据与源代码转换为适合 AI（LLM）理解的结构化 Markdown 上下文。**

[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/ioannesr5/scriptpacker?style=social)](https://github.com/ioannesr5/scriptpacker)

---

## 🌟 Why ScriptPacker? / なぜこのツールが必要なのか？ / 为什么需要本工具？

When feeding Unity projects into AI models (ChatGPT, Claude, Gemini), raw `.prefab` or `.unity` files usually cause heavy issues: **unreadable GUID references, infinite binary/mesh array noise, and blown-out context limits (トークン上限オーバー)**.

`scriptpacker` solves this by intelligently parsing Unity YAML references and cleanly packing source code into chunked Markdown files.

- **English**: Parses complex Unity serialized files, resolves GUIDs back to C# script names, extracts object hierarchy with event flows, and splits outputs safely before reaching LLM token boundaries.
- **日本語**: Unity の複雑なシリアライズデータを解析し、GUID を実際の C# スクリプト名へ逆引き補正。Hierarchy 階層構造やイベントフローを抽出した上で、LLM のコンテキスト上限を超えないよう安全に自動分割出力します。
- **中文**: 深度解析 Unity YAML 序列化数据，自动将 `.meta` 中的 GUID 还原为真实的 C# 脚本名；解析层级树与事件回调（Event Flow），并针对大模型上下文限制（Context Window）提供安全线级的自动分块与防爆截断。

---

## 🔥 Key Features / 主要機能 / 核心特性

- 🔍 **Relational Unity YAML Parser (リレーショナル YAML 解析)**
  - **GUID-to-Script Resolution**: Scans `.meta` files to map `guid: xxx` directly to actual C# class names (`guid: 89a...` $\rightarrow$ `GameManager.cs`).
  - **Hierarchy Tree Reconstruction**: Reconstructs parent-child GameObject relationships into readable trees.
  - **Event Callback Extraction**: Captures UnityEvents (e.g., `Button.onClick` $\rightarrow$ `[Event Callback] ➔ GameManager.OnStartButtonClicked()`).
  - **Prefab Overrides**: Highlights modified properties while discarding RectTransform / Position clutter.
- 🛡️ **Bulletproof Guard & Auto-Chunking (自動分割 & 完全防爆)**
  - **350k Character Split**: Automatically cuts output into safe file chunks (`output_part1.md`, `output_part2.md`) to prevent token overflows.
  - **Binary/Hex Isolation**: Automatically truncates lines exceeding 250 characters (mesh data, array dumps) to prevent AI context pollution and rendering slowdowns.
- ⚡ **Multi-Language Source Packing (多言語ソースコードパッキング)**
  - Packs C# (`.cs`), Python (`.py`), Shaders (`.shader`, `.cginc`, `.hlsl`), and custom text formats with syntax highlighting headers.
- 🧵 **Non-blocking Multithreaded GUI (マルチスレッド GUI)**
  - Smooth Tkinter user interface with real-time progress bar and log stream without freeze.

---

## 🚀 Quick Start / クイックスタート / 快速开始

### Prerequisites / 動作環境
- Python 3.8 or higher
- `tkinter` (Built-in with standard Python installations)

### Installation & Run / 実行手順

1. **Clone the repository (リポジトリの取得):**
   ```bash
   git clone [https://github.com/ioannesr5/scriptpacker.git](https://github.com/ioannesr5/scriptpacker.git)
   cd scriptpacker
