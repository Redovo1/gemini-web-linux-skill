# Gemini Web Linux Skill for OpenClaw 🦞

> 在 Linux 上将 Gemini 网页版变成 OpenAI 兼容 API，给 OpenClaw 免费使用！

## 这是什么？

这个技能把 [Quicker + Gemini 网页转 API](https://getquicker.net/Sharedaction?code=54037596-7003-47cb-dca5-08de3bb54158) 的功能移植到了 Linux 上：

- 使用 **Playwright**（浏览器自动化工具）代替 Windows 专用的 **Quicker + Webview2**
- 使用 **Flask** 提供 OpenAI 兼容的 HTTP API
- 完全在 Linux 上运行，无需 Windows

## 工作原理

```
OpenClaw 发送消息
       │
       ▼
  Flask HTTP 服务 (端口 8766)
       │
       ▼
  Playwright 无头 Chromium 浏览器
  （保持 Google 登录态）
       │
       ▼
  Gemini 网页 (gemini.google.com)
       │
       ▼
  提取回复 → 转换为 OpenAI 格式 → 返回给 OpenClaw
```

## 快速开始（3 步搞定）

### 1️⃣ 安装

```bash
# 把这个文件夹复制到 OpenClaw 技能目录
cp -r gemini-web-skill ~/.openclaw/workspace/skills/gemini-web-linux

# 运行安装脚本
cd ~/.openclaw/workspace/skills/gemini-web-linux
bash scripts/setup.sh
```

### 2️⃣ 登录 Google 账号（只需一次）

```bash
bash scripts/login.sh
```

### 3️⃣ 启动服务

```bash
bash scripts/start.sh
```

搞定！现在 OpenClaw 就学会了使用 Gemini 网页版了。

## 目录结构

```
gemini-web-skill/
├── SKILL.md                    # OpenClaw 技能说明（核心）
├── README.md                   # 你正在看的文件
├── scripts/
│   ├── setup.sh                # 一键安装
│   ├── login.sh                # Google 登录
│   ├── start.sh                # 启动服务
│   └── stop.sh                 # 停止服务
├── server/
│   ├── gemini_proxy.py         # 核心代理服务器
│   └── login_helper.py         # 登录辅助工具
└── data/                       # 运行时数据（自动创建）
    ├── chrome-profile/         # 浏览器登录态
    └── logs/                   # 运行日志
```

## 常见问题

**Q: 需要翻墙吗？**
A: 需要。你的 Linux 机器必须能访问 gemini.google.com。

**Q: 登录过期了怎么办？**
A: 重新执行 `bash scripts/login.sh`。

**Q: 没有桌面环境怎么登录？**
A: 使用 SSH X11 转发 (`ssh -X`)，或在有桌面的电脑上登录后拷贝 `data/chrome-profile/` 目录。

**Q: 和 Quicker 版有什么区别？**
A: 功能一样，但用 Python + Playwright 实现，所以能在 Linux/macOS 上运行。

## 致谢

- [gemini-web-quicker-skill](https://github.com/luoluoluo22/gemini-web-quicker-skill) - 原始 Quicker 技能
- [gemini-web-proxy](https://github.com/00bx/gemini-web-proxy) - Linux Playwright 方案参考
- [Quicker Gemini 网页转 API 动作](https://getquicker.net/Sharedaction?code=54037596-7003-47cb-dca5-08de3bb54158) - 原始思路来源
