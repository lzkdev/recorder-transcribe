# Agent 安装指令

当用户要求安装本 skill 时，由你完成下面的安装与初始化。不要把下载仓库、复制文件、执行命令的工作交回用户；仅在需要用户登录、管理员批准或系统交互时请用户操作。

## 1. 安装 skill

来源：`https://github.com/lzkdev/recorder-transcribe`

安装目录：仓库中的 `skills/recorder-transcribe`，包括 `SKILL.md`、`scripts/` 和 `references/`。

优先使用当前 Agent 宿主提供的 skill 安装器，指定上述 GitHub 仓库与子目录。没有安装器时，由你下载仓库归档到临时目录，只将该 skill 子目录安装到宿主支持的个人 skill 目录，无需用户执行 git clone。

本地 Codex 默认目录为 `${CODEX_HOME:-$HOME/.codex}/skills/recorder-transcribe`；其他宿主先确定其支持的安装位置，不套用 Codex 路径。如果已有同名目录，检查来源和本地修改，备份后再更新，不覆盖其他来源的 skill。

安装后读取目标目录中的 `SKILL.md`，后续命令均在这个目录运行。如果当前宿主不能执行本地命令或安装 skill，说明环境限制并给出 [接入方式](https://github.com/lzkdev/recorder-transcribe/blob/main/skills/recorder-transcribe/references/chatgpt.md)，不要声称安装成功。

## 2. 完成依赖检查

检查 `python3 --version`，要求 Python 3.9+，然后运行：

```bash
python3 scripts/recorder.py --doctor
```

用户的安装请求包含准备本 skill 必要依赖的意图。在宿主允许范围内处理缺失项：

- 缺 Python：使用已有包管理器安装 Python 3.9+。
- 缺 ffmpeg/ffprobe：macOS 使用 `brew install ffmpeg`；Debian/Ubuntu 使用系统包管理器安装 ffmpeg。需要管理员密码时交给用户完成该步。
- 缺 Node.js/npm：通过已有包管理器或 Node.js 官方发行版安装，再继续。
- 缺本地人声检测：运行 `python3 scripts/setup.py --install-vad`，安装隔离运行环境及校验过的模型。检测失败时不得继续上传。
- 缺飞书 CLI：运行 `python3 scripts/setup.py --install-cli`，安装官方固定版本。不要安装不相关的 skill 或工具。

安装器把 CLI 放在用户目录。后续会话使用完整路径：

```bash
export LARK_CLI="$HOME/.local/share/recorder-transcribe/tools/node_modules/.bin/lark-cli"
```

已有可用 CLI 时保留它。完整处理规则见已安装 skill 的 `references/setup.md`。修复缺失项后重跑 doctor，不只返回一串让用户自行执行的命令。

## 3. 连接飞书

- 应用已配置就复用，不新建或覆盖。
- 尚未配置时，运行 CLI 配置流程，向用户提供它返回的设置入口。
- 未登录、登录过期或缺少权限时，按 `references/setup.md` 的必要 scope 发起登录。使用 CLI 支持的异步授权方式，将授权链接交给用户；用户完成后继续完成登录并复查。
- 用户自行完成飞书页面和管理员审批，不要求用户把密钥或 token 粘贴到对话里。

创建妙记必须具备 user 身份，不能只验证 bot 登录。不要为了方便请求全部业务权限。

## 4. 验收与交付

重跑 doctor；已登录时可用 `auth status --verify --json` 复查服务端有效性。安装阶段不自动上传录音。

简短报告安装是否成功、飞书是否连接，以及下一步可直接使用的说法：

> 把这份录音转成飞书妙记：文件路径

若仍缺授权，明确指出这一项并给出可操作的入口，保留已完成的安装。宿主需要刷新 skill 列表或新会话才能发现时，告诉用户具体操作。没有实际上传测试就不要声称真实转写验收通过。
