# -*- coding: utf-8 -*-
"""给当前系统下载 yt-dlp / ffmpeg / N_m3u8DL-RE 到 bin/。

CI 里在 build_app.py 之前跑一次即可；本地也可以手动跑。
"""
from __future__ import annotations

import io
import json
import os
import platform
import re
import shutil
import stat
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
ARCH = platform.machine().lower()

UA = {"User-Agent": "VideoSaver-build/1.0"}
TOKEN = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()


def get(url: str, timeout=120) -> bytes:
    headers = dict(UA)
    if TOKEN and ("github.com" in url or "githubusercontent.com" in url):
        headers["Authorization"] = "Bearer " + TOKEN
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429) and attempt < 2:
                time.sleep(8 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last = e
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    raise last


def chmod_x(path: str) -> None:
    if not IS_WIN:
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def fetch_ytdlp() -> None:
    name = "yt-dlp.exe" if IS_WIN else "yt-dlp"
    dst = os.path.join(BIN, name)
    if os.path.isfile(dst):
        print("已有", name)
        return
    if IS_WIN:
        asset = "yt-dlp.exe"
    elif IS_MAC:
        asset = "yt-dlp_macos"
    else:
        asset = "yt-dlp_linux_aarch64" if ARCH in ("aarch64", "arm64") else "yt-dlp_linux"
    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/" + asset
    print("下载", url)
    data = get(url)
    with open(dst, "wb") as f:
        f.write(data)
    chmod_x(dst)


def fetch_ffmpeg() -> None:
    name = "ffmpeg.exe" if IS_WIN else "ffmpeg"
    dst = os.path.join(BIN, name)
    if os.path.isfile(dst):
        print("已有", name)
        return
    try:
        import imageio_ffmpeg
        src = imageio_ffmpeg.get_ffmpeg_exe()
        shutil.copy2(src, dst)
        chmod_x(dst)
        print("从 imageio-ffmpeg 复制 ffmpeg")
        return
    except Exception as e:
        print("imageio-ffmpeg 不可用：%s" % e)
    if IS_WIN:
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        print("下载", url)
        raw = get(url, timeout=600)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for n in z.namelist():
                if n.endswith("/bin/ffmpeg.exe"):
                    with z.open(n) as src, open(dst, "wb") as out:
                        shutil.copyfileobj(src, out)
                    return
    raise SystemExit("ffmpeg 下载失败，请手动放到 bin/" + name)


def fetch_nm3u8dl() -> None:
    name = "N_m3u8DL-RE.exe" if IS_WIN else "N_m3u8DL-RE"
    dst = os.path.join(BIN, name)
    if os.path.isfile(dst):
        print("已有", name)
        return
    api = "https://api.github.com/repos/nilaoda/N_m3u8DL-RE/releases/latest"
    data = json.loads(get(api, timeout=60).decode("utf-8"))
    if IS_WIN:
        pat = re.compile(r"win[-_]?x64", re.I)
    elif IS_MAC:
        pat = re.compile(r"(osx|macos)[-_]?(arm64|aarch64)", re.I) if ARCH in ("arm64", "aarch64") \
              else re.compile(r"(osx|macos)[-_]?x64", re.I)
    else:
        pat = re.compile(r"linux[-_]?(arm64|aarch64)", re.I) if ARCH in ("aarch64", "arm64") \
              else re.compile(r"linux[-_]?(x64|amd64)", re.I)
    asset = next((a for a in data.get("assets", [])
                  if pat.search(a.get("name", ""))
                  and a.get("name", "").lower().endswith((".zip", ".tar.gz", ".tgz"))), None)
    if not asset:
        names = [a.get("name", "") for a in data.get("assets", [])]
        raise SystemExit("找不到 N_m3u8DL-RE 的当前平台包；可选：\n" + "\n".join(names))
    print("下载", asset["name"])
    raw = get(asset["browser_download_url"], timeout=300)
    fname = asset["name"].lower()

    def _save(src):
        with open(dst, "wb") as out:
            shutil.copyfileobj(src, out)
        chmod_x(dst)

    if fname.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for n in z.namelist():
                if os.path.basename(n) == name:
                    with z.open(n) as src:
                        _save(src)
                    return
    else:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as t:
            for m in t.getmembers():
                if m.isfile() and os.path.basename(m.name) == name:
                    src = t.extractfile(m)
                    if src:
                        _save(src)
                        return
    raise SystemExit("压缩包里没找到可执行文件：" + asset["name"])


def main() -> None:
    os.makedirs(BIN, exist_ok=True)
    fetch_ytdlp()
    fetch_ffmpeg()
    fetch_nm3u8dl()
    print("bin/ 就绪：", sorted(os.listdir(BIN)))


if __name__ == "__main__":
    main()
