#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编译 Windows 安装包（Inno Setup）。

用法：
    python build_installer.py                          # 用 dist\\VideoSaver 打包
    python build_installer.py --src dist_new/VideoSaver # 指定别的产物目录
    python build_installer.py --version 1.0.1          # 发新版时递增版本号

产物：installer_out\\VideoSaver-Setup-<版本号>.exe

版本号会被传给 Inno Setup 的 AppVersion / AppVerName / VersionInfoVersion，
安装程序靠固定的 AppId 识别「同一个程序」执行覆盖更新，与代码签名无关。
发新版时记得同步改 server.py 里的 APP_VERSION，再重新打包 exe。

安装包会提供：许可协议页（必须接受）、安装进度条、可选桌面快捷方式、
开始菜单项、卸载程序。用户级安装，不弹 UAC。
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ISS = os.path.join(ROOT, "installer.iss")
OUT_DIR = os.path.join(ROOT, "installer_out")

ISCC_CANDIDATES = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
    r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
    r"C:\Program Files\Inno Setup 7\ISCC.exe",
]


def log(msg=""):
    print(msg, flush=True)


def find_iscc():
    for p in ISCC_CANDIDATES:
        if p and os.path.isfile(p):
            return p
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join("dist", "VideoSaver"),
                    help="打包产物目录（默认 dist\\VideoSaver）")
    ap.add_argument("--version", default="",
                    help="发布版本号，例如 1.0.1；留空用 installer.iss 里的默认值")
    args = ap.parse_args()

    if args.version and not re.match(r"^\d+\.\d+\.\d+$", args.version):
        log("版本号格式不对，应该像 1.0.1")
        return 1

    src = os.path.join(ROOT, args.src)
    if not os.path.isdir(src):
        log("找不到要打包的目录：" + src)
        log("先运行 build_exe.py（或 build.bat）生成它。")
        return 1
    exe = os.path.join(src, "VideoSaver.exe")
    if not os.path.isfile(exe):
        log("目录里没有 VideoSaver.exe：" + src)
        return 1

    for need in ("installer.iss", "LICENSE.txt", "app.ico", "ChineseSimplified.isl"):
        if not os.path.isfile(os.path.join(ROOT, need)):
            log("缺少文件：" + need + "（请确认在项目目录下运行）")
            return 1

    iscc = find_iscc()
    if not iscc:
        log("没找到 Inno Setup 编译器（ISCC.exe）。")
        log("安装命令：winget install --id JRSoftware.InnoSetup")
        log("装好后重跑本脚本即可。")
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    log("编译器：" + iscc)
    log("源目录：" + src)
    log("版本号：" + (args.version or "1.0.0（installer.iss 默认值）"))
    if args.version:
        # LICENSE.txt 的「版本 x.y.z」行随发布版本自动同步，不再手动维护
        lic = os.path.join(ROOT, "LICENSE.txt")
        try:
            with open(lic, "r", encoding="utf-8") as f:
                txt = f.read()
            txt2, n = re.subn(r"(?m)^版本 \d+\.\d+\.\d+$", "版本 " + args.version, txt)
            if n and txt2 != txt:
                with open(lic, "w", encoding="utf-8") as f:
                    f.write(txt2)
                log("LICENSE.txt 版本行已同步为 " + args.version)
        except Exception as e:
            log("LICENSE.txt 版本同步失败（不影响打包）：" + str(e))
        log("提示：正式发版请同步把 server.py 的 APP_VERSION 改成 " + args.version)
    log("开始编译安装包（LZMA2 压缩，大约 1-3 分钟）…")
    log("")

    cmd = [iscc, "/DSrcDir=" + src]
    if args.version:
        cmd.append("/DAppVersion=" + args.version)
    cmd.append(ISS)
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        log("")
        log("编译失败，退出码 %d。看上面的 Inno Setup 报错。" % rc)
        return rc

    out = ""
    for f in sorted(os.listdir(OUT_DIR), key=lambda x: os.path.getmtime(os.path.join(OUT_DIR, x)),
                    reverse=True):
        if f.lower().endswith(".exe"):
            out = os.path.join(OUT_DIR, f)
            break

    log("")
    log("=" * 60)
    if out:
        log("安装包：%s" % out)
        log("体积：%.1f MB" % (os.path.getsize(out) / 1048576.0))
        log("")
        log("用户端流程：双击 → 欢迎页 → 许可协议（必须接受）→ 选目录")
        log("            → 勾选桌面快捷方式 → 进度条 → 完成并运行")
        log("卸载：设置 → 应用，或开始菜单里的「卸载 VideoSaver」")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
