import shutil
import subprocess
import sys
from pathlib import Path


def clean_build() -> None:
    """清理上一次构建产物与同名 spec，避免旧 spec 覆盖命令行参数。"""
    for name in ("dist", "build"):
        shutil.rmtree(name, ignore_errors=True)
    Path("RunTimeTracker.spec").unlink(missing_ok=True)
    print("清理完成")


def build_executable() -> bool:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--name",
        "RunTimeTracker",
        "--windowed",
        "--icon",
        "图标.ico",
        "--version-file",
        "version_info.txt",
        "--add-data",
        "apps.json;.",
        "--add-data",
        "图标.png;.",
        "--add-data",
        "图标.ico;.",
        "--add-data",
        "图标_通知.png;.",
        "--hidden-import",
        "PyQt5.QtChart",
        "--collect-submodules",
        "winrt",
        "main.py",
    ]

    print("开始打包...")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"打包失败: {exc}")
        return False

    print("打包完成")
    return True


if __name__ == "__main__":
    clean_build()
    sys.exit(0 if build_executable() else 1)
