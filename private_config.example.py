# -*- coding: utf-8 -*-
# 本地调试用的反馈中继覆盖配置：复制本文件为 private_config.py 再填写。
# private_config.py 已在 .gitignore，不会被提交。
#
# 正式发版不靠这个文件：CI 从仓库 Secrets 注入 feedback_config.json，
# 三平台安装包会随包分发。本地直接跑源码时，也可以用
# VIDEOSAVER_FEEDBACK_RELAY / VIDEOSAVER_FEEDBACK_TOKEN 环境变量覆盖。
#
# 两个都留空也没关系：反馈会存到本机待发队列并自动补发，
# 用户还能点弹窗里的 GitHub Issue 链接，不需要配置邮箱或 SMTP。
FEEDBACK_RELAY_URL = ""      # 例如 https://api.example.com/v1/feedback
FEEDBACK_APP_TOKEN = ""      # 与服务端 FEEDBACK_APP_TOKEN 一致
