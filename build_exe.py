#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把工具打包成「别人双击就能用」的 Windows 程序。

用法：
    pip install pyinstaller
    python build_exe.py                # 默认 onedir（推荐）
    python build_exe.py --onefile      # 单文件（启动慢、易被杀软误报）

产物：
    dist\\VideoSaver\\VideoSaver.exe
    dist\\VideoSaver\\_internal\\...      （运行时依赖，别删）
    dist\\VideoSaver\\bin\\ffmpeg.exe、ffprobe.exe、yt-dlp.exe
    dist\\VideoSaver\\index.html

拿到 dist\\VideoSaver 整个文件夹压缩发给别人即可。
注意：绝不会把 config.json / cookies 打进包里（见文末检查）。
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "VideoSaver"
DIST = os.path.join(ROOT, "dist", APP_NAME)   # 可用 --out 覆盖
SEP = ";" if os.name == "nt" else ":"


def log(msg=""):
    print(msg, flush=True)


def find_tool(name, local_only=False):
    """先在 项目\\bin 找；local_only=True 时不再去 PATH 里捞。

    ffprobe 必须用 local_only：本机 PATH 里那个是全功能版（两百多兆），
    一旦被捞进来，瘦身就白做了；我们已经有「用 ffmpeg 读分辨率」的兜底。
    """
    for ext in (".exe", "") if os.name == "nt" else ("",):
        p = os.path.join(ROOT, "bin", name + ext)
        if os.path.isfile(p):
            return p
    if local_only:
        return ""
    return shutil.which(name) or ""


def ensure_pyinstaller():
    """缺少 PyInstaller 时自动装一次，省得用户搞不清「打不开」到底卡在哪。"""
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        pass

    log("没检测到 PyInstaller，正在自动安装（只需一次）…")
    log("  使用解释器：" + sys.executable)
    rc = subprocess.call([sys.executable, "-m", "pip", "install",
                          "--disable-pip-version-check", "pyinstaller"])
    if rc != 0:
        log("")
        log("自动安装失败。请手动执行下面这行，再重新运行本脚本：") 
        log('    "%s" -m pip install pyinstaller' % sys.executable)
        log("如果提示 pip 不存在，先执行： python -m ensurepip --upgrade")
        return False
    return True


def make_icon():
    """生成 app.ico（深色圆角底 + 播放三角），让窗口和任务栏不像个裸 Python 程序。"""
    path = os.path.join(ROOT, "app.ico")
    # 已经有了就直接用（用户自己的 logo），不要用代码里画的那个覆盖掉
    if os.path.isfile(path) and os.path.getsize(path) > 1024:
        log("  + app.ico（使用现有图标）")
        return path
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        log("  - 没装 Pillow，跳过图标（用 PyInstaller 默认图标）")
        return ""

    size = 256
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=58, fill=(15, 17, 22, 255))
    d.polygon([(104, 74), (186, 128), (104, 182)], fill=(77, 163, 255, 255))
    d.rounded_rectangle([58, 196, 198, 216], radius=10, fill=(47, 127, 208, 255))
    im.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    log("  + app.ico")
    return path


def check_prereq():
    if not ensure_pyinstaller():
        return False
    for need in ("server.py", "launch.py", "index.html", "wm_detect.py"):
        if not os.path.isfile(os.path.join(ROOT, need)):
            log("缺少文件：%s（请在项目目录下运行本脚本）" % need)
            return False
    return True


def build(onefile=False):
    icon = make_icon()
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", APP_NAME,
        "--onefile" if onefile else "--onedir",
        # 窗口程序：不要控制台黑窗。日志由 launch.py 写进
        # %LOCALAPPDATA%\VideoSaver\logs\app.log，起不来会弹对话框。
        "--windowed",
        "--add-data", "index.html" + SEP + ".",
        "--hidden-import", "wm_detect",
        # 应用窗口（WebView2）：pythonnet + pywebview 的资源要整包收进来，
        # 漏了不会崩，但会退回浏览器打开，等于白做。
        "--collect-all", "webview",
        "--collect-all", "clr_loader",
        # 托盘图标（关窗后台运行）。pystray 只留 win32 后端，
        # float 不要 --collect-all：它会把 gtk/qt 后端也拖进来。
        "--hidden-import", "pystray",
        "--hidden-import", "pystray._win32",
        "--hidden-import", "websocket",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageDraw",
        "--collect-submodules", "clr",
        "--hidden-import", "clr",
        # 用不到的模块排除掉，减小体积。
        # 注意：email / xml 不能排除——http.client 解析响应头就依赖 email.parser。
        "--exclude-module", "tkinter",
        "--exclude-module", "unittest",
        "--exclude-module", "pydoc",
        # Pillow 会顺手把 numpy / OpenBLAS 拖进来（+23MB），这个工具根本用不到
        "--exclude-module", "numpy",
        "--exclude-module", "scipy",
        "--exclude-module", "matplotlib",
        "launch.py",
    ]
    if icon and os.path.isfile(icon):
        args += ["--icon", icon]
    out_root = os.path.dirname(DIST)
    if os.path.abspath(out_root) != os.path.abspath(os.path.join(ROOT, "dist")):
        args += ["--distpath", out_root]
    log("=" * 60)
    log("开始打包（首次会比较慢，PyInstaller 要分析依赖）")
    log("=" * 60)
    rc = subprocess.call(args, cwd=ROOT)
    return rc == 0


def stage_binaries(onefile=False):
    """把 ffmpeg / yt-dlp（以及共享版 ffmpeg 依赖的 DLL）放进产物的 bin 目录。

    ffprobe 是可选的：水印定位会退回用 ffmpeg 读分辨率。
    少带一个两百多兆的二进制，分发包能小一半，所以默认不强求。
    """
    target = DIST
    if onefile:
        target = os.path.join(ROOT, "dist")
    bin_dir = os.path.join(target, "bin")
    os.makedirs(bin_dir, exist_ok=True)

    required = {"ffmpeg", "yt-dlp"}
    missing = []
    dlls = 0
    for tool in ("ffmpeg", "ffprobe", "yt-dlp", "N_m3u8DL-RE"):
        src = find_tool(tool, local_only=(tool == "ffprobe"))
        if not src:
            if tool in required:
                missing.append(tool)
            else:
                log("  - %s 未找到，跳过（水印定位会改用 ffmpeg 兜底）" % tool)
            continue
        dst = os.path.join(bin_dir, os.path.basename(src))
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
        log("  + bin/%s  (%.1f MB)" % (os.path.basename(src),
                                      os.path.getsize(dst) / 1048576.0))
        # 共享版 ffmpeg 的 exe 只有几百 KB，真正干活的是同目录的 DLL
        if tool in ("ffmpeg", "ffprobe"):
            src_dir = os.path.dirname(os.path.abspath(src))
            for dll in glob.glob(os.path.join(src_dir, "*.dll")):
                shutil.copy2(dll, os.path.join(bin_dir, os.path.basename(dll)))
                dlls += 1
    if dlls:
        log("  + bin/*.dll  (%d 个，共享版 ffmpeg 依赖)" % dlls)
    if missing:
        log("")
        log("!! 没找到：%s" % ", ".join(sorted(missing)))
        log("   这些必须和程序一起分发，否则下载 / 合并 / 去水印会失败。")
        log("   把对应的 exe 放进项目 bin 目录后重跑本脚本即可。")
    return not missing


def stage_assets(onefile=False):
    """把页面和图标放到 exe 旁边。

    app.ico / logo.png 必须一起发：托盘图标要读 app.ico，
    缺了会导致「关窗直接退出」；logo.png 缺了启动动画就是空白。
    """
    target = DIST if not onefile else os.path.join(ROOT, "dist")
    ok = True
    for name in ("index.html", "logo.png", "favicon.png", "app.ico"):
        src = os.path.join(ROOT, name)
        dst = os.path.join(target, name)
        if not os.path.isfile(src):
            if name == "index.html":
                log("!! 缺少必需文件：%s" % name)
                ok = False
            else:
                log("  - %s 不存在，跳过" % name)
            continue
        try:
            shutil.copy2(src, dst)
            log("  + %-12s (%.1f KB)" % (name, os.path.getsize(dst) / 1024.0))
        except Exception as e:
            log("!! 复制 %s 失败：%s" % (name, e))
            ok = False
    return ok


def report_size(onefile=False):
    target = DIST if not onefile else os.path.join(ROOT, "dist")
    total = 0
    for base, _dirs, files in os.walk(target):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(base, f))
            except OSError:
                pass
    mb = total / 1048576.0
    log("")
    log("产物体积：%.0f MB" % mb)
    if mb > 200:
        log("  偏大，几乎全是 ffmpeg 的重量（当前用的是全功能静态构建，单个 200MB 上下）。")
        log("  想瘦身：换成 ffmpeg 的 shared / lgpl-shared 构建（exe 只有几百 KB，")
        log("  依赖几个 DLL），把这些文件一起放进 bin\\ 即可，通常能降到几十 MB。")
    return mb


def audit_package(onefile=False):
    """最后一道保险：确认没有把私人配置和登录信息打进包里。"""
    target = DIST if not onefile else os.path.join(ROOT, "dist")
    leaked = []
    for name in ("config.json", "cookies", "runtime.json", "logs"):
        p = os.path.join(target, name)
        if os.path.exists(p):
            leaked.append(name)
    log("")
    if leaked:
        log("!! 警告：产物里出现了不该分发的东西：%s" % ", ".join(leaked))
        log("   请删除后再打包（里面可能有你的登录信息和下载记录）。")
        return False
    log("检查通过：产物里没有 config.json / cookies / 日志。")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onefile", action="store_true", help="打成单文件 exe")
    ap.add_argument("--out", default="", help="输出目录（默认 dist，被占用时可换一个）")
    args = ap.parse_args()

    global DIST
    if args.out:
        DIST = os.path.join(ROOT, args.out, APP_NAME)

    if not check_prereq():
        return 1
    if not build(args.onefile):
        log("打包失败，看上面的 PyInstaller 报错。")
        return 1
    ok_bin = stage_binaries(args.onefile)
    ok_asset = stage_assets(args.onefile)
    report_size(args.onefile)
    ok_clean = audit_package(args.onefile)

    log("")
    log("=" * 60)
    log("完成。产物目录：%s" % DIST)
    log("")
    log("分发方法：把整个 %s 文件夹压缩成 zip 发给对方，" % APP_NAME)
    log("          对方解压后双击 %s.exe 即可（不需要装 Python）。" % APP_NAME)
    log("")
    log("可选：在 exe 同目录放一个空文件 portable.txt，")
    log("      配置和登录信息就会存到程序目录（绿色版 / U 盘携带）；")
    log("      不放则存到 %%LOCALAPPDATA%%\\VideoSaver。")
    log("=" * 60)
    return 0 if (ok_bin and ok_asset and ok_clean) else 0


if __name__ == "__main__":
    sys.exit(main())
