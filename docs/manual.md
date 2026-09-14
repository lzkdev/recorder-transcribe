# Recorder Transcribe

将 USB 录音卡或本地音频送到**飞书妙记**，取回逐字稿和可用的 AI 产物。面向 Codex、豆包等具备本地命令执行能力的 Agent，也可独立使用命令行。

**状态：初始开源版。** 本地音频处理、故障恢复测试和官方 CLI 1.0.95 命令检查已验证；飞书连接及上传已验证，有效人声样本的完整转写验收仍待完成。普通 ChatGPT 网页端的远程 MCP 接入尚未实现。[接入说明](https://github.com/lzkdev/recorder-transcribe/blob/main/skills/recorder-transcribe/references/chatgpt.md)

## 做什么

- 初始化诊断：缺依赖或本地人声检测、CLI 不兼容、应用未配置、登录过期、权限不足分别提示。
- 单文件和目录批量预检/转写；USB 原文件保持不变。
- 无法解码的私有 Opus 使用同名有效 WAV；拒绝猜格式后直接上传。
- 大文件、标准 Opus/Ogg/FLAC 在临时目录转成 MP3。
- SHA-256 去重、原子状态文件和进程锁；查询失败可恢复，结果不确定时不重复创建妙记。
- 逐字稿与 AI 总结分别看待，不把“已提交”当成“已完成”。

本项目不实现蓝牙同步、不运行自己的 ASR、不保证飞书免费额度。实际上传会把音频交给登录用户的飞书云空间/妙记，并可能消耗账号额度。

## 上传前人声筛查

运行 `python3 scripts/setup.py --install-vad` 安装本地 Silero 检测器。预检同时检测人声，总人声少于 1 秒或占比低于 1% 会返回 `needs_confirm` 并停止上传。经用户核对仍需处理时，加 `--allow-low-speech`。检测器故障不允许绕过。

只有包含转写正文的逐字稿才记为完成；导出时间/时长标题不算正文，空产物为 `empty_result`。VAD 是概率筛查，不能保证零误判。

## 快速开始

支持 macOS/Linux，Python 3.9+。先安装 ffmpeg（含 ffprobe），例如 macOS `brew install ffmpeg`。

```bash
git clone https://github.com/lzkdev/recorder-transcribe.git
cd recorder-transcribe/skills/recorder-transcribe
python3 scripts/recorder.py --doctor
```

没有飞书 CLI？安装官方固定版本到用户目录，无需 sudo：

```bash
# 需要 Node.js/npm；缺失时安装器会提示，不继续上传
python3 scripts/setup.py --install-cli
export LARK_CLI="$HOME/.local/share/recorder-transcribe/tools/node_modules/.bin/lark-cli"
```

没有应用配置时运行 `"$LARK_CLI" config init`，完成飞书应用设置。已有配置不需要重新创建。用户登录：

```bash
"$LARK_CLI" auth login --scope "drive:file:upload drive:drive.metadata:readonly minutes:minutes.upload:write minutes:minutes.basic:read minutes:minutes.artifacts:read offline_access"
python3 scripts/recorder.py --doctor
```

使用已在 PATH 中的 CLI 时可直接运行 `lark-cli`。**创建妙记要求 user 身份，bot ready 不够。** 登录/权限审批由用户或管理员完成，不要把密钥发给 Agent。[完整初始化说明](https://github.com/lzkdev/recorder-transcribe/blob/main/skills/recorder-transcribe/references/setup.md)

```bash
# 只检查本地文件；不调用飞书、不消耗额度
python3 scripts/recorder.py --check-only /path/to/recording.wav
python3 scripts/recorder.py --batch --check-only /path/to/recordings

# 以下命令会上传至飞书
python3 scripts/recorder.py /path/to/recording.wav
python3 scripts/recorder.py --batch /path/to/recordings
```

也保留 `scripts/transcribe.sh` 和 `scripts/batch_transcribe.sh` 入口。带空格或单引号的路径可用正常 shell 引号传入；不要将路径拼接成可执行脚本。

## 作为 skill 使用

将 `skills/recorder-transcribe` 目录复制到 Agent 支持的个人 skill 目录。例如本地 Codex：

```bash
mkdir -p ~/.codex/skills
# 仅当目标尚不存在时执行；已有安装请先备份并核对
cp -R skills/recorder-transcribe ~/.codex/skills/
```

在项目根目录执行上面的复制命令。之后让 Agent 使用 `$recorder-transcribe` 检查环境并处理指定录音。其他宿主使用其文档规定的 skill 目录；安装文件不会自动授予飞书登录或磁盘权限。

## 输出与恢复

每个输入输出一条 JSON（初始化阻塞时输出诊断 JSON）。`done` 为逐字稿已落地；`cached` 为已有记录；`pending` 为产物未就绪。退出码 0/1/2 分别为完成或预检通过/错误/等待。

默认状态目录 `~/.recorder-transcribe-v2/<sha256>/` 包含 `state.json`、`detail.json` 及逐字稿。不提交音频、用户信息或妙记链接到 GitHub。`--state-dir` 可指定独立目录，切换账户时必须分开。文件内容重编码会改变哈希；标准 Opus 与 WAV 不做声学去重，批量前预检清单。

恢复时重跑同一命令，只查询已保存的 minute_token。上传/创建超时会停下要求核对远端，不提供 `--force` 盲目重传。[恢复说明与旧版迁移](https://github.com/lzkdev/recorder-transcribe/blob/main/skills/recorder-transcribe/references/recovery.md)

## 开发与验证

```bash
python3 -m unittest discover -s tests -v
python3 skills/recorder-transcribe/scripts/recorder.py --doctor
```

测试使用临时合成 WAV 和模拟飞书响应，覆盖去重、超时恢复、部分结果、源文件变化、损坏状态、缺 CLI、过期登录等。测试通过不代表真实语音识别效果或企业套餐可用。GitHub Actions 在 macOS/Linux 执行这些离线测试，不使用真实音频和凭据。

## 来源与许可

基于用户在豆包整理的录音卡转写 skill 重新整理实现；未包含原始录音、私人转写、登录状态或原项目业务代码。保留流程目标，替换脆弱的 shell/JSON 拼接逻辑。

MIT，见 [LICENSE](https://github.com/lzkdev/recorder-transcribe/blob/main/LICENSE)。飞书 CLI 是独立的 [larksuite/cli](https://github.com/larksuite/cli) 项目，本仓库不分发其二进制；飞书、Lark、ChatGPT、Codex 为各自权利人的名称，本项目无官方隶属关系。

English: A local Agent skill and Python CLI for sending recorder audio to Feishu Minutes. Includes dependency/auth diagnostics, persistent job recovery and offline tests. macOS/Linux; remote ChatGPT MCP support and authenticated end-to-end verification are not yet shipped.
