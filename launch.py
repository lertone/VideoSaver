#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动器：起服务 + 自动打开浏览器。

双击 start.bat 或直接 `python launch.py` 都能用。
退出码：0 = 正常；1 = 失败（start.bat 会 pause 并显示原因）。

设计要点：
- 不再 fork 子进程，直接在同一个进程里跑服务：Ctrl+C 能干净退出，
  也不会留下「关了窗口但后台还在跑」的幽灵进程；
- 启动前先看 runtime.json，服务已经在跑就只开浏览器，不会起第二个实例；
- 端口交给 server.py 自己挑（8765 被占会顺延），这里只负责等它定下来。
"""
import io
import json
import os
import sys
import time
import signal
import subprocess
import urllib.request
import webbrowser

# 防非 UTF-8 控制台（GBK）打印中文抛 UnicodeEncodeError 导致闪退
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

_LOG_FH = None


def setup_logging():
    """打包成窗口程序后没有控制台，sys.stdout 是 None。

    这种情况下任何一个 print 都会把程序直接干崩，所以先把输出接到日志文件；
    连日志都开不了就用黑洞兜底，总之不能因为「打日志」而启动失败。
    """
    global _LOG_FH
    # 只有打包成 exe（窗口程序）才落日志。源码运行时控制台就在眼前，不需要。
    # 注意不能靠 `sys.stdout is None` 判断：PyInstaller 的窗口模式有时把标准输出
    # 接到空设备而不是 None，那样判断会漏，结果就是「出问题查不到任何线索」。
    if not getattr(sys, "frozen", False):
        return None

    path = ""
    try:
        logs = os.path.join(data_dir(), "logs")
        os.makedirs(logs, exist_ok=True)
        path = os.path.join(logs, "app.log")
        try:
            if os.path.getsize(path) > 2 * 1024 * 1024:      # 超过 2MB 轮转一次
                os.replace(path, path + ".1")
        except OSError:
            pass
        _LOG_FH = open(path, "a", encoding="utf-8", buffering=1)
        _LOG_FH.write("\n===== %s =====\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        sys.stdout = _LOG_FH
        sys.stderr = _LOG_FH
        return path
    except Exception:
        class _Null(io.TextIOBase):
            def write(self, s):
                return len(s)

            def flush(self):
                pass
        sys.stdout = sys.stderr = _Null()
        return None


def fatal_box(text, log_path=""):
    """无控制台时唯一的告知方式：弹个系统对话框，别让用户面对「双击没反应」。"""
    msg = text
    if log_path:
        msg += "\n\n日志文件：\n" + log_path
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "VideoSaver - 启动失败", 0x10)
    except Exception:
        pass


def app_dir():
    """程序所在目录。

    打包成 exe 后 __file__ 指向 _internal/launch.py，直接用它会算错目录，
    必须改看 sys.executable（= exe 自身路径）。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = app_dir()
SERVER = os.path.join(APP_DIR, "server.py")
FROZEN = getattr(sys, "frozen", False)


def data_dir():
    """必须和 server.py 的规则保持一致，否则读不到 runtime.json。"""
    env = (os.environ.get("VIDEO_SAVER_HOME") or "").strip()
    if env:
        return os.path.abspath(env)
    if os.path.exists(os.path.join(APP_DIR, "portable.txt")):
        return APP_DIR
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return os.path.join(base, "VideoSaver")
    return os.path.join(os.path.expanduser("~"), ".video-saver")


RUNTIME = os.path.join(data_dir(), "runtime.json")

# 版本号与构建指纹都只以 server.py 为准，不在启动器里再硬编码一份，
# 避免改版本号时两处不同步。之前这里漏定义 APP_VERSION，旧版本检测分支会直接闪退。
FALLBACK_VERSION = "1.0.0"


def build_info():
    """返回 (版本号, 本份程序指纹)，用于判断端口上跑的是不是「我这一份」。"""
    try:
        sys.path.insert(0, APP_DIR)
        import server
        return (str(getattr(server, "APP_VERSION", FALLBACK_VERSION)),
                str(getattr(server, "EXE_ID", "")))
    except Exception:
        return FALLBACK_VERSION, ""


APP_VERSION, EXE_ID = build_info()


def say(msg=""):
    print(msg, flush=True)


def runtime_port():
    try:
        with open(RUNTIME, "r", encoding="utf-8") as f:
            return int(json.load(f).get("port") or 0)
    except Exception:
        return 0


# 本机探测必须绕过系统代理：机器上开着 Clash / 公司代理时，http_proxy 会把
# 127.0.0.1:8765 也发给代理，结果「服务明明没开却 ping 得通」，
# 于是被判成「旧进程还占着端口」，新版本怎么点都起不来。
_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def probe(port, timeout=1.5):
    """返回 /api/ping 的 JSON，连不上返回 None。"""
    try:
        with _LOCAL_OPENER.open(
                "http://127.0.0.1:%d/api/ping" % port, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def ping(port, timeout=1.5):
    info = probe(port, timeout)
    return bool(info and info.get("ok"))


def is_busy(port, timeout=1.2):
    """端口上的实例是否正在下载。空闲时换新版本不必打扰用户。"""
    try:
        with _LOCAL_OPENER.open(
                "http://127.0.0.1:%d/api/status" % int(port), timeout=timeout) as r:
            return bool(json.loads(r.read().decode("utf-8", "replace")).get("downloading"))
    except Exception:
        return False


def kill_old(pid):
    try:
        os.kill(int(pid), signal.SIGTERM)
        return True
    except Exception:
        pass
    try:
        subprocess.run(["taskkill", "/PID", str(int(pid)), "/F"],
                       capture_output=True, timeout=10,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


def kill_all():
    """按镜像名收掉其它实例（含看门狗）。

    必须跳过自己：启动器本身就叫 VideoSaver.exe，直接 taskkill /IM 会把自己也干掉，
    用户看到的就是「点了没反应」。
    """
    me = os.getpid()
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq VideoSaver.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout or ""
    except Exception:
        return False
    killed = False
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) < 2 or parts[0].strip('"').lower() != "videosaver.exe":
            continue
        try:
            pid = int(parts[1].strip('"'))
        except ValueError:
            continue
        if pid == me:
            continue
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                           capture_output=True, timeout=8,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            killed = True
        except Exception:
            pass
    return killed


# ---------------- 看门狗：服务挂了自动拉起来 ----------------
WATCHDOG_PID = os.path.join(data_dir(), "watchdog.pid")
STOP_FLAG = os.path.join(data_dir(), "watchdog.stop")
DETACHED = 0x00000008
CREATE_NO_WINDOW = 0x08000000


def _pid_alive(pid):
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "PID eq %d" % int(pid), "/NH"],
            capture_output=True, text=True, timeout=8,
            creationflags=CREATE_NO_WINDOW).stdout or ""
        return str(pid) in out
    except Exception:
        return False


def _self_cmd(*extra):
    if getattr(sys, "frozen", False):
        return [sys.executable] + list(extra)
    return [sys.executable, os.path.abspath(__file__)] + list(extra)


def ensure_watchdog():
    """起一个独立小进程盯着服务；主程序意外退出后自动拉回来。"""
    try:
        with open(WATCHDOG_PID, "r", encoding="utf-8") as f:
            pid = int((f.read() or "0").strip() or 0)
        if pid and pid != os.getpid() and _pid_alive(pid):
            return
    except Exception:
        pass
    try:
        subprocess.Popen(_self_cmd("--watchdog"), cwd=APP_DIR, close_fds=True,
                         creationflags=DETACHED | CREATE_NO_WINDOW,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        say("看门狗没起来（%s），服务异常时不会自动重启。" % e)


def watchdog_main():
    """--watchdog：每 5 秒探一次；连续 3 次探不到就重启主程序，然后自己退出。"""
    try:
        with open(WATCHDOG_PID, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    fails = 0
    while True:
        if os.path.exists(STOP_FLAG):        # 用户主动退出，别再拉起来
            try:
                os.remove(STOP_FLAG)
            except Exception:
                pass
            return 0
        port = runtime_port()
        if port and ping(port):
            fails = 0
        else:
            fails += 1
            # 连续 30 秒（6 次 × 5 秒）没响应才认定真挂了。以前 15 秒就动手，
            # 碰上合并 4K 分片、杀软全盘扫描这类瞬时卡顿，会把正常服务误判成崩溃，
            # 结果就是「后台老是掉」的观感——其实是被自己人重启的。
            if fails >= 6:
                # 动手前用更宽松的超时再确认一次，别冤枉一个正在忙的服务
                if port and ping(port, timeout=3.5):
                    fails = 0
                    time.sleep(5)
                    continue
                try:
                    subprocess.Popen(_self_cmd(), cwd=APP_DIR, close_fds=True,
                                     creationflags=DETACHED | CREATE_NO_WINDOW,
                                     stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                except Exception:
                    pass
                try:
                    logs = os.path.join(data_dir(), "logs")
                    os.makedirs(logs, exist_ok=True)
                    with open(os.path.join(logs, "app.log"), "a", encoding="utf-8") as f:
                        f.write("\n[看门狗] %s 连续 30 秒无响应，已自动重启主程序\n"
                                % time.strftime("%Y-%m-%d %H:%M:%S"))
                except Exception:
                    pass
                return 0
        time.sleep(5)


def open_url(port):

    url = "http://localhost:%d/" % port
    try:
        ok = webbrowser.open(url)
    except Exception:
        ok = False
    if not ok:
        say("自动打开浏览器失败，请手动访问：" + url)
    return ok


def main():
    """默认开应用窗口；--browser 用浏览器；--no-browser 只起服务。"""
    if "--watchdog" in sys.argv:
        return watchdog_main()
    want_window = "--browser" not in sys.argv and "--no-browser" not in sys.argv
    headless = "--no-browser" in sys.argv
    # 安装完点「立即运行」时带 --fresh：就是要用刚装的这份，别管旧实例在不在
    fresh = "--fresh" in sys.argv

    # 1) 已经在跑
    port = runtime_port()
    info = probe(port) if port else None
    if info and info.get("ok"):
        running = str(info.get("version") or "")
        running_exe = str(info.get("exe") or "")
        # 版本号相同还不够：重装/覆盖安装后仍是 1.0.0，但内容已经变了。
        # 只有指纹也一致，才认为是「同一个程序已经在跑」。
        same_build = (running == APP_VERSION) and (
            not EXE_ID or running_exe == EXE_ID)
        if same_build and not fresh:
            # 同一份程序：不重复起实例，只把界面打开
            if headless:
                return 0
            url = "http://localhost:%d/" % port
            if "--doc" in sys.argv:
                url += "#doc"
            say("服务已在运行：http://localhost:%d/" % port)
            if want_window:
                try:
                    sys.path.insert(0, APP_DIR)
                    import server
                    if server.run_app_window(url):
                        return 0
                except Exception as e:
                    say("窗口打不开（%s），改用浏览器。" % e)
            open_url(port)
            return 0

        # 端口上跑的是另一份程序（老版本 / 旧安装目录 / 旧构建）。
        # 绝不静默杀掉——用户可能正在下载。窗口模式下弹框询问，
        # 无窗口模式（被其它程序/脚本调用）直接沿用旧服务。
        if headless:
            say("旧版本（%s）正在运行，本次直接沿用它的服务，不做任何中断。" % (running or "未知"))
            return 0
        busy = (not fresh) and is_busy(port)
        choice = 6
        if busy:
            # 只有正在下载才值得问一句；空闲时直接换新，否则「立即运行」像没反应
            try:
                import ctypes
                choice = ctypes.windll.user32.MessageBoxW(
                    None,
                    "检测到旧版本（%s）还在运行，而且正在下载。\n\n"
                    "点「是」：结束旧版本并启动新版本 %s（下载会中断）。\n"
                    "点「否」：先继续用旧版本，等下载完再换。"
                    % (running or "未知", APP_VERSION),
                    APP_TITLE, 0x00000004 | 0x00000020 | 0x00040000)  # YESNO|问号|置顶
            except Exception:
                choice = 7
        else:
            say("检测到旧版本（%s），直接换成 %s。" % (running or "未知", APP_VERSION))
        if choice != 6:
            say("继续使用正在运行的旧版本。")
            url = "http://localhost:%d/" % port
            try:
                sys.path.insert(0, APP_DIR)
                import server
                if server.run_app_window(url):
                    return 0
            except Exception as e:
                say("窗口打不开（%s），改用浏览器。" % e)
            open_url(port)
            return 0

        old_pid = 0
        try:
            with open(RUNTIME, "r", encoding="utf-8") as f:
                old_pid = int(json.load(f).get("pid") or 0)
        except Exception:
            pass
        # 看门狗不杀干净的话，它会在 15 秒内把旧版本又拉起来，
        # 用户看到的就是「点了没反应，过一会儿旧界面自己冒出来」。
        wd_pid = 0
        try:
            with open(WATCHDOG_PID, "r", encoding="utf-8") as f:
                wd_pid = int((f.read() or "0").strip() or 0)
        except Exception:
            pass
        if wd_pid and wd_pid != os.getpid():
            kill_old(wd_pid)
        if old_pid:
            kill_old(old_pid)
        for _ in range(24):
            time.sleep(0.25)
            if not ping(port):
                break
        if ping(port):
            # runtime.json 里的 pid 可能已经过期（重装/重启后 pid 会变），按镜像名再来一遍
            say("按 pid 没结束掉，改用镜像名收掉其它 VideoSaver 进程。")
            kill_all()
            for _ in range(12):
                time.sleep(0.25)
                if not ping(port):
                    break
        if ping(port):
            info2 = probe(port)
            if info2 and info2.get("ok"):
                say("旧进程还占着端口 %d，先把旧界面打开；要换新版请右键托盘退出后重开。" % port)
                url = "http://localhost:%d/" % port
                try:
                    sys.path.insert(0, APP_DIR)
                    import server
                    if server.run_app_window(url):
                        return 0
                except Exception as e:
                    say("窗口打不开（%s），改用浏览器。" % e)
                open_url(port)
                return 0
            # 端口上是别的程序：交给 server.py 顺延到下一个端口，不必拦着用户
            say("端口 %d 被其它程序占用，将自动换一个端口启动。" % port)
        say("旧版本已退出，接着启动新版本。")

    if not FROZEN and not os.path.isfile(SERVER):
        say("错误：同目录下找不到 server.py")
        say("  期望位置：" + SERVER)
        return 1

    # 2) 交给 server.py：它自己挑端口、写 runtime.json、开窗口或开浏览器
    if want_window and "--window" not in sys.argv:
        sys.argv.append("--window")
    elif not want_window and not headless and "--open" not in sys.argv:
        sys.argv.append("--open")

    sys.path.insert(0, APP_DIR)
    try:
        import server
    except Exception as e:
        say("载入 server.py 失败：%s" % e)
        return 1

    try:
        # 服务跑起来之前先安排好看门狗：以后进程被意外结束时能自动恢复
        try:
            os.remove(STOP_FLAG)
        except Exception:
            pass
        ensure_watchdog()
        server.main()
    except KeyboardInterrupt:
        say("\n已停止")
    return 0


if __name__ == "__main__":
    log_path = setup_logging()
    try:
        _code = main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        _tb = traceback.format_exc()
        try:
            sys.stderr.write(_tb)
        except Exception:
            pass
        _last = (_tb.strip().splitlines() or ["未知错误"])[-1]
        fatal_box("程序没能启动。\n\n" + _last, log_path)
        _code = 1
    sys.exit(_code)
