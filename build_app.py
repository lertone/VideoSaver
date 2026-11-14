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


def make_icns() -> str:
    """把 app.ico 转成 .icns（macOS 图标）。"""
    src = os.path.join(ROOT, "app.ico")
    out = os.path.join(ROOT, "app.icns")
    try:
        from PIL import Image
        Image.open(src).save(out, format="ICNS")
        return out
    except Exception as e:
        print("生成 app.icns 失败：%s" % e)
        return ""


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
    if IS_MAC:
        args += ["--osx-bundle-identifier", "com.lertone.videosaver"]
        icns = make_icns()
        if icns:
            args += ["--icon", icns]
    if IS_WIN:
        args += ["--hidden-import", "pystray",
                 "--hidden-import", "pystray._win32",
                 "--collect-all", "clr_loader",
                 "--collect-submodules", "clr",
                 "--hidden-import", "clr",
                 "--icon", os.path.join(ROOT, "app.ico")]
    for item in ("index.html", "app.ico", "favicon.png", "logo.png", "donate.png", "donate-alipay.png", "donate-wechat.png", "bin"):
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
        for name in ("index.html", "logo.png", "favicon.png", "app.ico", "donate.png", "donate-alipay.png", "donate-wechat.png"):
            src = os.path.join(ROOT, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(root, name))
    print("bin/ 与静态资源已放到运行时目录")


def make_dmg(version: str, tag: str) -> str:
    """macOS 安装包：.app + /Applications 快捷方式，ad-hoc 签名。"""
    app = os.path.join(DIST, "VideoSaver.app")
    if not os.path.isdir(app):
        sys.exit("没有生成 .app，检查 PyInstaller 输出")
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", app],
                   check=False, capture_output=True)
    stage = os.path.join(BUILD, "dmg")
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)
    shutil.copytree(app, os.path.join(stage, "VideoSaver.app"), symlinks=True)
    os.symlink("/Applications", os.path.join(stage, "Applications"))
    out = os.path.join(RELEASE, "VideoSaver-%s-%s.dmg" % (version, tag))
    subprocess.check_call([
        "hdiutil", "create", "-volname", "VideoSaver",
        "-srcfolder", stage, "-ov", "-format", "UDZO", out,
    ])
    return out


def make_deb(version: str, tag: str) -> str:
    """Ubuntu/Debian 安装包：/usr/lib + 菜单项 + 图标。"""
    root = os.path.join(BUILD, "deb")
    if os.path.isdir(root):
        shutil.rmtree(root)
    appdir = os.path.join(root, "usr", "lib", "videosaver")
    shutil.copytree(os.path.join(DIST, "VideoSaver"), appdir, symlinks=True)

    bindir = os.path.join(root, "usr", "bin")
    os.makedirs(bindir, exist_ok=True)
    wrapper = os.path.join(bindir, "videosaver")
    with open(wrapper, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\nexec /usr/lib/videosaver/VideoSaver \"$@\"\n")
    os.chmod(wrapper, 0o755)

    apps = os.path.join(root, "usr", "share", "applications")
    os.makedirs(apps, exist_ok=True)
    with open(os.path.join(apps, "videosaver.desktop"), "w", encoding="utf-8") as f:
        f.write(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=VideoSaver\n"
            "Comment=本地优先的视频下载器\n"
            "Exec=videosaver\n"
            "Icon=videosaver\n"
            "Terminal=false\n"
            "Categories=AudioVideo;Video;Network;\n"
        )

    icon_dir = os.path.join(root, "usr", "share", "icons", "hicolor", "256x256", "apps")
    os.makedirs(icon_dir, exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "logo.png"), os.path.join(icon_dir, "videosaver.png"))

    control_dir = os.path.join(root, "DEBIAN")
    os.makedirs(control_dir, exist_ok=True)
    arch = "arm64" if platform.machine() in ("aarch64", "arm64") else "amd64"
    with open(os.path.join(control_dir, "control"), "w", encoding="utf-8") as f:
        f.write(
            "Package: videosaver\n"
            "Version: %s\n"
            "Section: video\n"
            "Priority: optional\n"
            "Architecture: %s\n"
            "Depends: python3-gi, gir1.2-webkit2-4.0 | gir1.2-webkit2-4.1\n"
            "Maintainer: lertone <lertone@users.noreply.github.com>\n"
            "Description: 本地优先的桌面视频下载器\n"
            " yt-dlp + AI 助手 + 媒体嗅探 + 文件管理。\n" % (version, arch)
        )
    out = os.path.join(RELEASE, "VideoSaver-%s-%s.deb" % (version, tag))
    subprocess.check_call(["dpkg-deb", "--build", "--root-owner-group", root, out])
    return out


def zip_dir(src: str, out: str, arc_root: str = "VideoSaver", extra: dict | None = None) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for r, ds, fs in os.walk(src):
            ds[:] = [d for d in ds if ".old-" not in d and ".new-" not in d]
            for f in fs:
                p = os.path.join(r, f)
                z.write(p, os.path.join(arc_root, os.path.relpath(p, src)))
        for name, data in (extra or {}).items():
            z.writestr(os.path.join(arc_root, name), data)


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
        web_bat = ("@echo off\ncd /d \"%~dp0\"\nstart \"\" \"VideoSaver.exe\" --browser\n")
        zip_dir(os.path.join(DIST, "VideoSaver"), out,
                extra={"启动-网页版.bat": web_bat})
    elif IS_MAC:
        z = os.path.join(RELEASE, "VideoSaver-%s-%s.zip" % (version, tag))
        zip_dir(os.path.join(DIST, "VideoSaver.app"), z, "VideoSaver.app")
        out = make_dmg(version, tag)
    else:
        out = os.path.join(RELEASE, "VideoSaver-%s-%s.tar.gz" % (version, tag))
        with tarfile.open(out, "w:gz") as t:
            t.add(os.path.join(DIST, "VideoSaver"), arcname="VideoSaver")
        make_deb(version, tag)
    print("完成：" + out)


if __name__ == "__main__":
    main()
