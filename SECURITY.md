# Security

## 报告问题

请通过 GitHub 的 **Security → Report a vulnerability** 私密报告，不要开公开 issue。

## 密钥

- 仓库里不应出现任何 SMTP 授权码、API Key、管理员 token、Cookie、下载记录。
- 反馈中继的地址/令牌不进仓库源码：发版时由 `tools/write_feedback_config.py`
  从仓库 Secrets（`VIDEOSAVER_FEEDBACK_RELAY` / `VIDEOSAVER_FEEDBACK_TOKEN`）
  写入 `feedback_config.json`，该文件在仓库里始终为空占位；本地覆盖可用
  `private_config.py`（已 gitignore）或同名环境变量。邮件授权码只放服务器 `.env`。
- 反馈中继的令牌是「应用令牌」，会随安装包分发，理论上可被提取；服务端必须保留
  IP 限流和内容长度限制。一旦发现被刷，直接在服务端轮换令牌并重新发版。
- 如果你不小心提交了密钥：立即轮换，再清理历史提交（`git filter-repo`），只删文件不够。

## 支持范围

只维护 `main` 分支的最新版本。
