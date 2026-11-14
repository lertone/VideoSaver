# -*- coding: utf-8 -*-
"""三平台打包入口：必须在目标系统上运行（PyInstaller 不支持交叉编译）。

Windows:  python build_app.py   -> release/VideoSaver-<ver>-windows-x64.zip
macOS:    python build_app.py   -> release/VideoSaver-<ver>-macos.zip (.app)
Linux:    python build_app.py   -> release/VideoSaver-<ver>-linux-x64.tar.gz
"""
from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
RELEASE = os.path.join(ROOT, "release")
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def read_version() -> str:
    with open(os.path.join(ROOT, "server.py"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("APP_VERSION"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.0.0"


def ensure_bin() -> None:
    need = ["yt-dlp", "ffmpeg", "N_m3u8DL-RE"]
    bin_dir = os.path.join(ROOT, "bin")
    missing = []
    for name in need:
        p = os.path.join(bin_dir, name + (".exe" if IS_WIN else ""))
        if not os.path.isfile(p):
            missing.append(os.path.basename(p))
    if missing:
        sys.exit("缺少二进制：" + ", ".join(missing) +
                 "\n先运行 python tools/fetch_bin.py（CI 会自动做）")


def pyi_args(version: str) -> list[str]:
    sep = ";" if IS_WIN else ":"
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", "VideoSaver",
        "--distpath", DIST,
        "--workpath", BUILD,
        "--specpath", BUILD,
        "--paths", ROOT,
        "--collect-all", "webview",
        "--hidden-import", "websocket",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageDraw",
        "--hidden-import", "wm_detect",
    ]
    if IS_WIN:
        args += ["--hidden-import", "pystray",
                 "--hidden-import", "pystray._win32",
                 "--collect-all", "clr_loader",
                 "--collect-submodules", "clr",
                 "--hidden-import", "clr",
                 "--icon", os.path.join(ROOT, "app.ico")]
    for item in ("index.html", "app.ico", "favicon.png", "logo.png", "bin"):
        src = os.path.join(ROOT, item)
        if os.path.exists(src):
            args += ["--add-data", src + sep + item]
    entry = os.path.join(ROOT, "launch.py") if IS_WIN else os.path.join(ROOT, "app_entry.py")
    args.append(entry)
    return args


def stage_binaries() -> None:
    """把 bin/ 放到运行时 APP_DIR/bin，并补可执行权限（mac/Linux）。"""
    if IS_MAC:
        roots = [os.path.join(DIST, "VideoSaver.app", "Contents", "MacOS")]
    else:
        roots = [os.path.join(DIST, "VideoSaver")]
    src_dir = os.path.join(ROOT, "bin")
    for root in roots:
        if not os.path.isdir(root):
            continue
        bin_dir = os.path.join(root, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        for f in os.listdir(src_dir):
            src = os.path.join(src_dir, f)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(bin_dir, f)
            shutil.copy2(src, dst)
            if not IS_WIN:
                os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        # PyInstaller 也可能把 bin 放进 _internal；一并补权限
        for r, _ds, fs in os.walk(root):
            if os.path.basename(r) != "bin":
                continue
            for f in fs:
                q = os.path.join(r, f)
                try:
                    os.chmod(q, os.stat(q).st_mode | stat.S_IXUSR)
                except OSError:
                    pass
        # 静态资源也放一份到 exe 同目录：不依赖 _MEIPASS，用户还能直接改界面
        for name in ("index.html", "logo.png", "favicon.png", "app.ico"):
            src = os.path.join(ROOT, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(root, name))
    print("bin/ 与静态资源已放到运行时目录")


def zip_dir(src: str, out: str, arc_root: str = "VideoSaver") -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for r, ds, fs in os.walk(src):
            ds[:] = [d for d in ds if ".old-" not in d and ".new-" not in d]
            for f in fs:
                p = os.path.join(r, f)
                z.write(p, os.path.join(arc_root, os.path.relpath(p, src)))


def main() -> None:
    version = read_version()
    if IS_WIN:
        tag = "windows-x64"
    elif IS_MAC:
        tag = "macos-" + ("arm64" if platform.machine() == "arm64" else "x64")
    else:
        tag = "linux-" + ("arm64" if platform.machine() in ("aarch64", "arm64") else "x64")
    print("构建 VideoSaver %s (%s)" % (version, tag))
    ensure_bin()
    os.makedirs(RELEASE, exist_ok=True)
    subprocess.check_call(pyi_args(version), cwd=ROOT)
    stage_binaries()

    if IS_WIN:
        out = os.path.join(RELEASE, "VideoSaver-%s-%s.zip" % (version, tag))
        zip_dir(os.path.join(DIST, "VideoSaver"), out)
    elif IS_MAC:
        app = os.path.join(DIST, "VideoSaver.app")
        if not os.path.isdir(app):
            sys.exit("没有生成 .app，检查 PyInstaller 输出")
        out = os.path.join(RELEASE, "VideoSaver-%s-%s.zip" % (version, tag))
        zip_dir(app, out, "VideoSaver.app")
    else:
        out = os.path.join(RELEASE, "VideoSaver-%s-%s.tar.gz" % (version, tag))
        with tarfile.open(out, "w:gz") as t:
            t.add(os.path.join(DIST, "VideoSaver"), arcname="VideoSaver")
    print("完成：" + out)


if __name__ == "__main__":
    main()
