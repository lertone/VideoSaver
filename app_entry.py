# -*- coding: utf-8 -*-
"""macOS / Linux 的打包入口：直接起服务并开应用窗口（不经过 Windows 专用的 launch.py）。"""
import sys

if "--window" not in sys.argv:
    sys.argv.append("--window")

import server  # noqa: E402

if __name__ == "__main__":
    server.main()
