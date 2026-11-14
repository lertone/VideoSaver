# Security

## 报告问题

请通过 GitHub 的 **Security → Report a vulnerability** 私密报告，不要开公开 issue。

## 密钥

- 仓库里不应出现任何 SMTP 授权码、API Key、管理员 token、Cookie、下载记录。
- 反馈中继配置放在 `private_config.py`（已 gitignore）或服务器 `.env`。
- 如果你不小心提交了密钥：立即轮换，再清理历史提交（`git filter-repo`），只删文件不够。

## 支持范围

只维护 `main` 分支的最新版本。
