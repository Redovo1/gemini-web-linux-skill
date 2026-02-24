#!/bin/bash
# =============================================================
# Gemini Web Proxy - Google 账号登录脚本
# 打开浏览器让用户登录 Google，保存登录状态
# 支持 --proxy 参数或环境变量自动传递代理
# =============================================================

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$SKILL_DIR/venv"

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

echo "🔐 Gemini Web Linux - Google 账号登录"
echo "================================================"
echo ""
echo "即将打开 Chromium 浏览器，请在其中完成以下操作："
echo "  1. 登录你的 Google 账号"
echo "  2. 确保进入 gemini.google.com 页面"
echo "  3. 页面加载完毕后，关闭浏览器或按 Ctrl+C"
echo ""
echo "登录状态会自动保存，以后不需要重复登录。"
echo "================================================"
echo ""

# 构建命令参数
CMD_ARGS="--profile-dir $SKILL_DIR/data/chrome-profile"

# 传递代理：优先使用传入的 --proxy 参数，其次环境变量
if [ -n "$1" ] && [ "$1" = "--proxy" ] && [ -n "$2" ]; then
    CMD_ARGS="$CMD_ARGS --proxy $2"
    echo "🌐 使用代理: $2"
elif [ -n "$HTTPS_PROXY" ]; then
    CMD_ARGS="$CMD_ARGS --proxy $HTTPS_PROXY"
    echo "🌐 使用代理(HTTPS_PROXY): $HTTPS_PROXY"
elif [ -n "$HTTP_PROXY" ]; then
    CMD_ARGS="$CMD_ARGS --proxy $HTTP_PROXY"
    echo "🌐 使用代理(HTTP_PROXY): $HTTP_PROXY"
elif [ -n "$ALL_PROXY" ]; then
    CMD_ARGS="$CMD_ARGS --proxy $ALL_PROXY"
    echo "🌐 使用代理(ALL_PROXY): $ALL_PROXY"
fi

python3 "$SKILL_DIR/server/login_helper.py" $CMD_ARGS
