# ==============================================================================
# Jupyter 環境動作確認用スクリプト
# (Jupyter Notebook 環境および PyTorch / GPU の動作を検証するためのコード)
# ==============================================================================

import sys

import torch

# Python インタープリターの実行パスと PyTorch バージョンの表示
print(f"実行中の Python パス (Python Executable Path) : {sys.executable}")
print(f"PyTorch バージョン (PyTorch Version)        : {torch.__version__}")

# GPU (ROCm / CUDA) の利用可能状態の判定
if torch.cuda.is_available():
    gpu_name: str = torch.cuda.get_device_name(0)
    print(f"GPU アクセラレーション (GPU Acceleration)    : 有効 ({gpu_name})")
else:
    print("GPU アクセラレーション (GPU Acceleration)    : 無効 (CPU モード)")
