# 三平台适配与打包报告

## 先说结论

- **Windows**：本机可直接出包，已验证（`VideoSaver 1.5.3`，安装包 + 绿色包）。
- **macOS / Linux**：代码路径已改成按系统分支，但 **PyInstaller 不能从 Windows 交叉编译**。
  必须在 macOS / Linux 机器上，或直接用仓库里的 `.github/workflows/build-all.yml`（三平台矩阵）
  出原生包。本机无法生成、也无法真实运行验证 mac/Linux 包，这一点不糊弄。

---

## 这次改了什么

| 能力 | Windows | macOS | Linux |
|---|---|---|---|
| 应用窗口 | WebView2 | WKWebView（pywebview） | WebKitGTK（pywebview） |
| 选文件夹 / 另存为 | 原生 Win32 对话框 | tkinter | tkinter |
| 打开文件夹 / 定位文件 | `os.startfile` / `explorer /select` | `open` / `open -R` | `xdg-open` |
| 删除到回收站 | Shell API | `~/.Trash` | `gio trash`（失败则 `~/.local/share/Trash`） |
| 嗅探浏览器 | Edge/Chrome/Brave/Chromium + CDP | 同左（`/Applications/...`） | 同左（`which` 查找） |
| 无窗口标志 | `CREATE_NO_WINDOW` | 0（无此参数） | 0 |
| 托盘 | pystray | 首版关闭 | 首版关闭 |
| 复制文件到剪贴板 | CF_HDROP | 未实现（按钮会提示不支持） | 未实现 |

新增文件：

- `build_app.py`：三平台打包入口（自动判断系统、二进制、产物格式）。
- `app_entry.py`：mac/Linux 入口（直接 `server --window`，绕开 Windows 专用 `launch.py`）。
- `tools/fetch_bin.py`：按当前系统下载 `yt-dlp / ffmpeg / N_m3u8DL-RE` 到 `bin/`。
- `requirements-build.txt`：打包依赖。
- `.github/workflows/build-all.yml`：Windows / macOS / Linux 三平台矩阵构建。

---

## 怎么出包

### Windows（本机，已验证）

```powershell
python build_exe.py
python build_installer.py --version 1.5.3
```

### macOS（必须在 Mac 上）

```bash
pip install -r requirements-build.txt
python tools/fetch_bin.py
python build_app.py
# 产物：release/VideoSaver-1.5.5-macos-arm64.dmg（拖进 Applications）和 .zip（内含 VideoSaver.app）
```

未签名/未公证的 `.app` 首次打开会被 Gatekeeper 拦：右键 → 打开，或
`xattr -dr com.apple.quarantine VideoSaver.app`。要正式分发需要 Apple Developer 证书 + notarytool。

### Linux（必须在 Linux 上）

```bash
sudo apt-get install -y libgirepository1.0-dev libcairo2-dev pkg-config \
  python3-gi gir1.2-webkit2-4.0
pip install -r requirements-build.txt
python tools/fetch_bin.py
python build_app.py
# 产物：release/VideoSaver-1.5.5-linux-x64.deb（应用菜单 + 图标）和 .tar.gz
```

如果 `PyGObject` 装不上，用系统 Python 的 `python3-gi`，或改用 Qt 后端
（`pip install pywebview[qt]`，体积会大一些）。

### CI（推荐，一次出三平台）

把仓库推到 GitHub，Actions 里手动运行 **build-all**，或打 `v*` tag。
三个 artifact：`VideoSaver-windows-x64`、`macos-arm64`、`linux-x64`。

---

## 仍然是 Windows-only 的部分

1. `launch.py` 的看门狗 / `taskkill` / `MessageBoxW`：mac/Linux 走 `app_entry.py`，不用它。
2. `_pick_folder_vista` / `_save_file_win32`：只在 Windows 分支调用。
3. 剪贴板文件（CF_HDROP）：mac/Linux 未实现，点「复制」会提示不支持。
4. DPI 感知：非 Windows 自动跳过。
5. 托盘：非 Windows 首版关闭，避免 AppIndicator 依赖。
6. 安装包：Windows 是 Inno Setup；mac 是 `.dmg`（ad-hoc 签名）+ `.app` zip；Linux 是 `.deb` + tar.gz。AppImage 暂未做。

---

## 隐私与初始状态审计

已检查：

- `dist/VideoSaver` 内**没有** `config.json`、`cookies/`、`logs/`、`keys.db`、`ai_frames/`。
- 默认下载目录是 `~/Videos/VideoSaver`，**没有**写死 `C:\Users\<用户名>`、`F:\<下载目录>` 这类个人路径。
- 客户端源码里没有 SMTP 授权码、`ADMIN_TOKEN`、QQ 邮箱。
- 服务端 `.env`（含 SMTP 授权码、管理员令牌）**不在**客户端包内。

需要你知道的一件事：

- 客户端 `server.py` 里有反馈中继地址和 `FEEDBACK_APP_TOKEN`。它们会编进 exe，
  **有工具的人可以提取出来**，然后拿你的中继发垃圾反馈。目前中继有频率限制，风险可控；
  如果要公开分发，建议改成“按用户发 token”或在中继侧加 IP 限流/验证码。
- 你之前在聊天里发过 SMTP 授权码和 `ADMIN_TOKEN`，建议轮换一次。

---

## 清理记录

- 删除旧安装包 1.3.9–1.5.1、旧绿色包 1.4.5–1.5.1（保留 1.5.2/1.5.3）。
- 删除 `build/`、`dist/**/*.old-*`、`dist/**/*.new-*`。
- 删除 `video-extract-service` 的 `__pycache__`、`*.pyc`、测试用 `data/keys.db`。
