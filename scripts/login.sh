#!/bin/bash
# =============================================================
# Gemini Web Proxy - Google 账号登录脚本
# 打开浏览器让用户登录 Google，保存登录状态
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

python3 "$SKILL_DIR/server/login_helper.py" --profile-dir "$SKILL_DIR/data/chrome-profile"
