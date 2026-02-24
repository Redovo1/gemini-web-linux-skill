---
name: gemini-web-linux
description: >
  通过 Playwright 浏览器自动化访问 Gemini 网页版，在 Linux 上提供免费的 OpenAI 兼容 API。
  支持对话、思维链推理和图片生成。无需 API Key，使用你自己的 Google 账号。
homepage: https://github.com/00bx/gemini-web-proxy
---

# Gemini Web Linux 技能

## 这个技能是什么

本技能在你的 Linux 机器上运行一个 **Gemini 网页版的反向代理服务**，通过 Playwright 浏览器自动化技术，将 Gemini 网页版的能力转化为标准的 OpenAI 兼容 API。

**完全免费** — 使用你自己的 Google 账号登录，无需任何 API Key。

## 支持的能力

- **智能对话**：使用 Gemini 模型进行问答和代码分析
- **深度推理**：利用 Gemini Thinking 模式处理复杂逻辑
- **图片生成**：通过 Gemini 生图能力生成高质量图像

## 前置条件

- Linux 系统（有或无桌面环境均可）
- Python 3.8+
- Google 账号（能访问 gemini.google.com）
- 网络能访问 Google 服务

## 首次安装步骤（只需做一次）

请依次执行以下命令完成安装：

```bash
# 第一步：进入技能目录
cd {baseDir}

# 第二步：运行一键安装脚本
bash scripts/setup.sh
```

安装脚本会自动完成：
1. 创建 Python 虚拟环境
2. 安装所有依赖（playwright、Flask 等）
3. 下载 Chromium 浏览器

## 首次登录 Google 账号（只需做一次）

```bash
cd {baseDir}
bash scripts/login.sh
```

这会打开一个 Chromium 浏览器窗口，请在其中：
1. 登录你的 Google 账号
2. 确保进入了 gemini.google.com 页面并能看到对话界面
3. 完成后**关闭浏览器窗口**或按 Ctrl+C，登录状态会自动保存

登录状态会保存在 `{baseDir}/data/chrome-profile/` 目录中，以后不需要重新登录。

> ⚠️ 如果你的 Linux 没有桌面环境，请使用以下方式之一：
> - 通过 SSH X11 转发：`ssh -X user@server` 然后执行登录脚本
> - 安装 Xvfb + VNC：`sudo apt install xvfb x11vnc`，用 `xvfb-run` 执行登录脚本，通过 VNC 查看
> - 在有桌面的电脑上完成登录，然后把 `data/chrome-profile/` 目录整个拷贝过来

## 启动服务

```bash
cd {baseDir}
bash scripts/start.sh
```

服务启动后，会在 `http://127.0.0.1:8766/v1` 提供 OpenAI 兼容 API。

## 停止服务

```bash
cd {baseDir}
bash scripts/stop.sh
```

## 如何在对话中使用

当用户请求需要 Gemini 网页版模型的能力时（比如调用最新的 Gemini 模型对话、生成图片），
请使用 bash 工具执行以下命令：

### 发送对话请求
```bash
curl -s http://127.0.0.1:8766/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-web",
    "messages": [{"role": "user", "content": "你的问题"}],
    "stream": false
  }'
```

### 检查服务状态
```bash
curl -s http://127.0.0.1:8766/v1/models
```

## 故障排查

1. **服务没有运行**：执行 `bash {baseDir}/scripts/start.sh` 启动
2. **登录过期**：执行 `bash {baseDir}/scripts/login.sh` 重新登录
3. **返回 403/500**：检查 Google 账号是否正常，Gemini 网页是否可访问
4. **无法启动浏览器**：确保已执行安装脚本且 Playwright 浏览器已下载
