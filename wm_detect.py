#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Guess the position of a static overlay using multi-frame differencing.

Pure stdlib + ffmpeg. Idea borrowed from static-ghost's ``detect`` and
notebooklm-watermark-remover's universal mode: a fixed logo stays identical
while the background moves, so low temporal variance + high spatial gradient
is a good hint. The result is only a *suggestion* for the user to confirm.
"""

import os
import re
import subprocess

SAMPLE_WIDTH = 320
SAMPLE_FRAMES = 8
BLOCK = 16
TEMP_TOLERANCE = 14      # max per-pixel change across sampled frames
GRAD_MIN = 16            # spatial gradient of the first frame
MIN_HITS_PER_BLOCK = 10  # a block needs this many hint pixels
MAX_AREA_RATIO = 0.25    # reject "whole picture is static" false positives


def _no_window():
    return {"creationflags": 0x08000000} if os.name == "nt" else {}


def _size_from_ffmpeg(video, ffmpeg):
    """没有 ffprobe 时用 ffmpeg -i 的 stderr 反推分辨率。

    ffmpeg 只给输入不给输出时会以退出码 1 结束，真正的信息在 stderr 里，
    形如 `Stream #0:0: Video: h264 ..., 1920x1080 [SAR 1:1 DAR 16:9]`。
    """
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-i", video],
                             capture_output=True, timeout=20, **_no_window())
        text = (out.stderr or b"").decode("utf-8", "replace")
        m = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", text, re.S)
        if not m:
            m = re.search(r"Stream #\d+:\d+.*?Video.*?(\d{2,5})x(\d{2,5})", text, re.S)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return None


def probe_size(video, ffprobe=None, ffmpeg=None):
    """优先 ffprobe；没装 ffprobe 就退回 ffmpeg（分发版可以只带 ffmpeg）。"""
    if ffprobe:
        try:
            out = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0", video],
                capture_output=True, text=True, timeout=15, **_no_window())
            parts = (out.stdout or "").strip().split(",")
            return int(parts[0]), int(parts[1])
        except Exception:
            pass
    if ffmpeg:
        return _size_from_ffmpeg(video, ffmpeg)
    return None


def sample_gray_frames(video, ffmpeg, width, height, count, timeout=45):
    cmd = [
        ffmpeg, "-v", "error", "-i", video,
        "-vf", "fps=1,scale=%d:%d,format=gray" % (width, height),
        "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout, **_no_window())
    except Exception:
        return b"", 0
    data = out.stdout or b""
    frame_size = width * height
    frames = len(data) // frame_size
    return data[:frames * frame_size], frames


def _cluster(scores, bw, bh):
    """4-neighbour BFS from the strongest block; return its bounding box."""
    best, best_pos = 0, None
    for by in range(bh):
        for bx in range(bw):
            if scores[by][bx] > best:
                best, best_pos = scores[by][bx], (bx, by)
    if best_pos is None or best < MIN_HITS_PER_BLOCK:
        return None
    seen = {best_pos}
    stack = [best_pos]
    while stack:
        bx, by = stack.pop()
        for nx, ny in ((bx - 1, by), (bx + 1, by), (bx, by - 1), (bx, by + 1)):
            if 0 <= nx < bw and 0 <= ny < bh and (nx, ny) not in seen:
                if scores[ny][nx] >= MIN_HITS_PER_BLOCK:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
    xs = [p[0] for p in seen]
    ys = [p[1] for p in seen]
    return min(xs), min(ys), max(xs), max(ys), sum(scores[y][x] for x, y in seen)


def detect_region(video, ffmpeg, ffprobe, timeout=45):
    """Return a suggested bbox dict, or None when confidence is too low."""
    size = probe_size(video, ffprobe, ffmpeg)
    if not size:
        return None
    ow, oh = size
    if ow < 64 or oh < 64:
        return None
    width = min(SAMPLE_WIDTH, ow)
    height = max(2, int(oh * width / ow))
    height -= height % 2
    frame_size = width * height
    data, n = sample_gray_frames(video, ffmpeg, width, height, SAMPLE_FRAMES, timeout)
    if n < 3 or len(data) < frame_size * 3:
        return None

    # Temporal: largest deviation of each pixel from the first sampled frame.
    maxdiff = bytearray(frame_size)
    first = data[:frame_size]
    for k in range(1, n):
        off = k * frame_size
        for i in range(frame_size):
            d = first[i] - data[off + i]
            if d < 0:
                d = -d
            if d > maxdiff[i]:
                maxdiff[i] = 255 if d > 255 else d

    # Spatial: horizontal + vertical gradient of the first frame.
    grad = bytearray(frame_size)
    for y in range(height - 1):
        row = y * width
        below = row + width
        for x in range(width - 1):
            d = abs(first[row + x] - first[row + x + 1]) + abs(first[row + x] - first[below + x])
            grad[row + x] = 255 if d > 255 else d

    bw = (width + BLOCK - 1) // BLOCK
    bh = (height + BLOCK - 1) // BLOCK
    scores = [[0] * bw for _ in range(bh)]
    hits = 0
    for i in range(frame_size):
        if maxdiff[i] < TEMP_TOLERANCE and grad[i] > GRAD_MIN:
            x, y = i % width, i // width
            scores[y // BLOCK][x // BLOCK] += 1
            hits += 1
    if hits < 20:
        return None

    cluster = _cluster(scores, bw, bh)
    if cluster is None:
        return None
    min_bx, min_by, max_bx, max_by, cluster_hits = cluster
    sx, sy = ow / width, oh / height
    x = int(min_bx * BLOCK * sx)
    y = int(min_by * BLOCK * sy)
    w = int((max_bx - min_bx + 1) * BLOCK * sx)
    h = int((max_by - min_by + 1) * BLOCK * sy)
    w = min(w, ow - x - 2)
    h = min(h, oh - y - 2)
    x, y, w, h = (v - v % 2 for v in (x, y, w, h))
    if w < 8 or h < 8:
        return None
    area_ratio = (w * h) / float(ow * oh)
    if area_ratio > MAX_AREA_RATIO:
        return None
    confidence = min(1.0, cluster_hits / float(max(1, (w / sx) * (h / sy))))
    return {
        "x": x, "y": y, "w": w, "h": h,
        "frames": n, "confidence": round(confidence, 2),
        "area_ratio": round(area_ratio, 3),
        "hint": "仅供参考，请确认黄色框是否盖住水印，必要时手动拖动调整。",
    }
