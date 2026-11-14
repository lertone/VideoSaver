# Contributing

感谢你愿意改进 VideoSaver。

## 提交之前

- 不要提交 `private_config.py`、`.env`、`cookies/`、`config.json`、`logs/`、`data/`。
- 不要提交 `bin/`、`dist/`、`build/`、`release/` 里的二进制。
- 涉及界面的改动请附一张截图（可以放在 PR 描述里）。
- 改完至少跑一遍：

```bash
python -m py_compile server.py launch.py app_entry.py build_app.py
python app_entry.py
```

## 代码风格

- Python 3.12，标准库优先，新增依赖请说明理由。
- 界面文案保持中文、简短、说人话。
- Windows 专用调用必须放在 `IS_WIN` 分支里；mac/Linux 的回退不能崩。

## 打包相关

- 改依赖后请同步 `requirements-build.txt`。
- 构建后检查 `dist/VideoSaver/_internal` 是否包含 `webview`、`pythonnet`、`clr_loader`、`PIL`；
  只看 `--version` 会漏掉半成品包。

## Pull Request

- 一个 PR 只做一件事，描述里写清楚动机和验证方式。
- 不要顺手格式化整份文件，diff 越小越好。
