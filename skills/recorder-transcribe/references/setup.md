# 初始化与认证

## 支持环境

macOS/Linux，Python 3.9+，ffmpeg/ffprobe。Windows 原生未支持（进程锁使用 fcntl）；可在 WSL 内运行，USB 文件需在 WSL 中可访问。

先检查 `python3 --version`。没有 Python：macOS `brew install python`；Debian/Ubuntu `sudo apt install python3`。没有 Homebrew 则由用户按官方安装说明配置包管理器，脚本不安装系统包管理器。

## 没有飞书 CLI

先运行诊断：

```bash
python3 scripts/recorder.py --doctor
```

安装器需要 Node.js/npm。没有 npm 时提示安装 [Node.js LTS](https://nodejs.org/)。明确安装指令：

```bash
python3 scripts/setup.py --install-cli
```

安装官方 npm 包 `@larksuite/cli@1.0.95` 到 `~/.local/share/recorder-transcribe/tools`。安装会执行官方包的二进制下载脚本，需要网络。不会安装第三方技能、改 PATH 或复制任何凭据。现有 CLI 优先，指定新版安装路径可避免旧版抢先：

```bash
export LARK_CLI="$HOME/.local/share/recorder-transcribe/tools/node_modules/.bin/lark-cli"
"$LARK_CLI" --version
```

缺 ffmpeg/ffprobe：macOS `brew install ffmpeg`；Debian/Ubuntu `sudo apt install ffmpeg`。不自动 sudo。版本不兼容时，查看 help 或用上面的固定版本，不猜命令。

## 应用配置和用户授权

`lark-cli` 指已进入 PATH 的命令；使用项目安装器时，将下列命令替换为 `"$LARK_CLI"`。

```bash
lark-cli auth status --json
# 仅没有应用配置时执行；保留已有配置
lark-cli config init
# 限定到此流程的权限，不使用 --recommend / --domain all
lark-cli auth login --scope "drive:file:upload drive:drive.metadata:readonly minutes:minutes.upload:write minutes:minutes.basic:read minutes:minutes.artifacts:read offline_access"
```

应用配置/登录可能要求管理员批准，完成授权后重跑 `--doctor`。不要让用户把 App Secret、access token、refresh token 发到对话中。创建妙记使用 `--as user`；不要看到 bot ready 就继续。

异步交互工具可用 `auth login --no-wait --json --scope "..."` 发起授权，再由用户打开验证地址；用户完成后使用 CLI 给出的 device code 继续。不要把 device code 提交到代码仓库。

## 检查结果

- 缺依赖：给出安装方法，不上传。
- 未配置：引导 config init，不覆盖配置。
- 登录过期：引导 auth login，不借用其他应用会话。
- 权限缺少：列出上述必要权限，用户/管理员批准后继续。
- 本地 ready：仅说明本地条件满足；可用 `auth status --verify --json` 检查服务器 token，有效配额/具体资源权限仍以一次授权的小样本上传结果为准。

网络/额度错误不自动换账户、提权或重新创建妙记。软件开源免费不等于飞书服务免费，额度和功能取决于实际账号/企业套餐。

## 本地人声检测（上传前必需）

```bash
python3 scripts/setup.py --install-vad
```

安装 Silero ONNX 模型及隔离环境的 ONNX Runtime/numpy，不安装 Torch。固定依赖支持 Python 3.9–3.12；安装器优先选择已有 Python 3.12，否则使用当前 Python。更高版本缺少兼容 wheel 时，先安装 Python 3.12 再运行安装器。

模型从 Silero 官方仓库的固定提交下载并校验 SHA-256。检测在本机遍历整段音频，只将明确授权处理的录音上传飞书。缺检测器或检测失败时阻止上传。

连续至少 0.25 秒且模型概率 ≥0.5 的帧计为疑似人声；总人声 <1 秒或占比 <1% 返回 `needs_confirm`，不创建云文件。阈值是保守筛查，不证明录音绝对无声，也不保证通过的录音一定能准确转写。用户确认后才可使用 `--allow-low-speech`。
