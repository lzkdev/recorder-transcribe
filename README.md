# Recorder Transcribe

让 Agent 把录音卡或本地音频转成飞书妙记，获取逐字稿、总结和待办。

## 安装

把下面这段话发给你的 Agent：

> 请读取 [INSTALL.md](https://raw.githubusercontent.com/lzkdev/recorder-transcribe/main/INSTALL.md)，按照说明安装 recorder-transcribe skill，检查并安装缺少的依赖，帮我完成飞书连接。需要我操作时，把授权链接发给我。

## 使用

安装后，直接告诉 Agent：

> 把这份录音转成飞书妙记：/path/to/recording.wav

> 录音卡已经接入，先看看有哪些录音。

> 把这个目录里的录音批量转写，已经处理过的跳过。

上传前会在本地检查有效人声，疑似空录音会先提醒你。

支持 macOS / Linux 上可执行本地命令的 Agent。首次使用需要飞书授权，转写使用飞书账号额度。

[安装指令](https://github.com/lzkdev/recorder-transcribe/blob/main/INSTALL.md) · [手动使用](https://github.com/lzkdev/recorder-transcribe/blob/main/docs/manual.md) · [ChatGPT 接入说明](https://github.com/lzkdev/recorder-transcribe/blob/main/skills/recorder-transcribe/references/chatgpt.md) · [贡献](https://github.com/lzkdev/recorder-transcribe/blob/main/CONTRIBUTING.md)

[MIT License](https://github.com/lzkdev/recorder-transcribe/blob/main/LICENSE)
