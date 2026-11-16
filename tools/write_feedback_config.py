#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建期把反馈中继配置写进 feedback_config.json。

公开仓库里这个文件永远是空的；正式发版时由 CI 从 GitHub Secrets 注入，
打进安装包后再随程序分发。普通用户因此不用填邮箱 / SMTP。

用法（本地也适用）：
    VIDEOSAVER_FEEDBACK_RELAY=https://.../v1/feedback \
    VIDEOSAVER_FEEDBACK_TOKEN=... \
    python tools/write_feedback_config.py

不提供环境变量时会写出空配置，构建照常成功，客户端自动走
「本机待发队列 + GitHub Issue 兜底」，不会要求用户做任何配置。
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "feedback_config.json")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    url = (os.environ.get("VIDEOSAVER_FEEDBACK_RELAY") or "").strip()
    token = (os.environ.get("VIDEOSAVER_FEEDBACK_TOKEN") or "").strip()

    if url and not url.lower().startswith(("http://", "https://")):
        print("反馈中继地址不是 http/https，按未配置处理")
        url = ""
    # 地址和令牌要么都给，要么都不给，避免打出一个必然 401 的包
    if not url:
        token = ""

    data = {"relay": url, "token": token}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, OUT)

    # 只打印是否注入，绝不把令牌打到日志里
    print("feedback_config.json: relay=%s, token=%s" % (
        url or "(未注入)", "已注入" if token else "(未注入)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
