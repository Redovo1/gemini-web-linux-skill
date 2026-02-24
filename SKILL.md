---
name: gemini-web-linux
description: >
  通过 Playwright 浏览器自动化访问 Gemini 网页版，在 Linux 上提供免费的 OpenAI 兼容 API。
  支持对话、思维链推理和图片生成（图片自动保存为本地文件并提供下载URL）。无需 API Key。
homepage: https://github.com/Redovo1/gemini-web-linux-skill
---

# Gemini Web Linux 技能

## 这个技能是什么

本技能在你的 Linux 机器上运行一个 **Gemini 网页版的代理服务**，通过 Playwright 浏览器自动化技术，将 Gemini 网页版的能力转化为标准的 OpenAI 兼容 API。

**完全免费** — 使用你自己的 Google 账号登录，无需任何 API Key。

## 支持的能力

- **智能对话**：使用 Gemini 模型进行问答和代码分析
- **深度推理**：利用 Gemini Thinking 模式处理复杂逻辑
- **图片生成**：让 Gemini 画图，图片自动保存为本地文件并返回下载 URL

## 前置条件

- Linux 系统（有或无桌面环境均可）
- Python 3.8+
- Google 账号（能访问 gemini.google.com）
- 网络能访问 Google 服务（支持代理）

## 首次安装步骤（只需做一次）

```bash
cd {baseDir}
bash scripts/setup.sh
```

## 首次登录 Google 账号（只需做一次）

```bash
cd {baseDir}
bash scripts/login.sh
# 如果需要代理:
# bash scripts/login.sh --proxy http://127.0.0.1:10808
```

这会打开一个 Chromium 浏览器窗口，请在其中：
1. 登录你的 Google 账号
2. 确保进入了 gemini.google.com 页面并能看到对话界面
3. 完成后**关闭浏览器窗口**或按 Ctrl+C，登录状态会自动保存

> ⚠️ 如果你的 Linux 没有桌面环境，请使用 SSH X11 转发：`ssh -X user@server`

## 启动服务

```bash
cd {baseDir}
bash scripts/start.sh
# 如果需要代理:
# bash scripts/start.sh --proxy http://127.0.0.1:10808
# 或者设置环境变量:
# export HTTP_PROXY=http://127.0.0.1:10808 && bash scripts/start.sh
```

服务启动后，会在 `http://127.0.0.1:8766/v1` 提供 OpenAI 兼容 API。

## 停止服务

```bash
cd {baseDir}
bash scripts/stop.sh
```

## 如何在对话中使用

当用户请求需要 Gemini 网页版模型的能力时，请使用 bash 工具执行以下命令：

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

### 请求生成图片
```bash
curl -s http://127.0.0.1:8766/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-web",
    "messages": [{"role": "user", "content": "请画一只穿宇航服的猫咪"}],
    "stream": false
  }'
```

当 Gemini 生成图片后，回复中会包含图片的下载链接，格式为：
`![image](http://127.0.0.1:8766/media/gemini_xxx.png)`

你可以用 `curl` 或 `wget` 下载这个图片到本地：
```bash
# 下载图片（URL 从上一步的回复中获取）
curl -o /tmp/generated_image.png "http://127.0.0.1:8766/media/gemini_xxx.png"
```

图片也会自动保存在 `{baseDir}/data/media/` 目录中。

### 检查服务状态
```bash
curl -s http://127.0.0.1:8766/health
```

## 故障排查

1. **服务没有运行**：执行 `bash {baseDir}/scripts/start.sh`
2. **登录过期**：执行 `bash {baseDir}/scripts/login.sh` 重新登录
3. **网络不通**：确认代理配置正确，用 `--proxy` 参数或 `HTTP_PROXY` 环境变量指定
4. **无法启动浏览器**：确保已执行安装脚本且 `playwright install-deps chromium` 已完成
5. **图片提取失败**：图片仍然可以在 Gemini 网页端查看，回复中会有提示
