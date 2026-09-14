# ChatGPT / Codex 接入边界

核实日期：2026-09-14。

## 本地 Codex

本地 Codex 可读取安装的 SKILL.md 并执行 Python/CLI。完成飞书用户授权后，流程是本机复制音频 → 官方 lark-cli 上传云空间 → 创建妙记 → 获取产物。识别由飞书完成，GPT 负责编排与后续整理，不需 OpenAI 转写 API key。

豆包的 CLI 登录和工具环境不自动传递给 Codex。当前环境需分别检查可执行文件、应用配置、user 登录和权限。官方 CLI 的创建命令要求 user 身份。

## ChatGPT 网页 / 远程环境

只有文件或 skill 文本不等于获得本机文件系统和 USB 权限。可通过支持的自定义插件/MCP 服务接入，但需要另外提供受认证的工具服务和音频传输通道。

拟议接口：`inspect_audio`、`submit_audio`、`get_transcription`。提交采用服务端持久化 job ID，读取接口轮询同一任务。远程服务应只接受用户明确上传的文件或有授权的文件标识，不能把任意本机绝对路径作为远程工具参数，也不能提供任意 shell 执行工具。

远程接入还需用户级 OAuth、租户隔离、上传限制、产物访问控制，以及实际 ChatGPT 工作区的插件权限。**本仓库当前交付本地 skill/CLI，不包含已部署的远程 MCP 服务，不声称已完成 ChatGPT 网页端或真实飞书转写验收。**

## 核实来源

- [官方 larksuite/cli](https://github.com/larksuite/cli)：CLI 安装及认证。
- [妙记上传命令](https://github.com/larksuite/cli/blob/1bd78144e890c685726bd251ef8ee7710750e538/shortcuts/minutes/minutes_upload.go)：user 身份、上传权限、异步创建接口。
- [妙记详情命令](https://github.com/larksuite/cli/blob/1bd78144e890c685726bd251ef8ee7710750e538/shortcuts/minutes/minutes_detail.go)：产物和处理中状态。
- [OpenAI 官方 MCP 构建文档](https://developers.openai.com/plugins/build/mcp-server)：ChatGPT 工具接入路线。

公开 CLI 已存在该命令不能证明所有企业账号均已开通、额度充足或网关配置相同；用真实账号小样本验证后再更新兼容性声明。
