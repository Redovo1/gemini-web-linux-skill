#!/bin/bash
# =============================================================
# Gemini Web Proxy - 一键安装脚本
# 适用于 Linux 系统，安装所有依赖
# =============================================================

set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$SKILL_DIR/venv"
DATA_DIR="$SKILL_DIR/data"

echo "🦞 Gemini Web Linux 技能 - 安装中..."
echo "================================================"

# 1. 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装："
    echo "   Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "   CentOS/RHEL:   sudo yum install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python 版本: $PYTHON_VERSION"

# 检查 python3-venv 是否可用
if ! python3 -m venv --help &> /dev/null; then
    echo "❌ python3-venv 模块不可用，请安装："
    echo "   Ubuntu/Debian: sudo apt install python3-venv"
    exit 1
fi

# 2. 检查 curl（start.sh 用于健康检查）
if ! command -v curl &> /dev/null; then
    echo "⚠️ 未找到 curl，建议安装（启动脚本需要用来检测服务状态）："
    echo "   Ubuntu/Debian: sudo apt install curl"
    echo "   CentOS/RHEL:   sudo yum install curl"
fi

# 3. 创建虚拟环境
echo ""
echo "📦 创建 Python 虚拟环境..."
if [ -d "$VENV_DIR" ]; then
    echo "   虚拟环境已存在，跳过创建"
else
    python3 -m venv "$VENV_DIR"
    echo "   ✅ 虚拟环境创建完成"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 4. 安装 Python 依赖
echo ""
echo "📦 安装 Python 依赖..."
pip install --upgrade pip -q
pip install playwright flask requests -q
echo "   ✅ Python 依赖安装完成"

# 5. 安装 Playwright 浏览器
echo ""
echo "🌐 下载 Chromium 浏览器（首次下载约 150MB，请耐心等待）..."
playwright install chromium

echo ""
echo "🔧 安装 Chromium 系统依赖（可能需要 sudo 密码）..."
if command -v sudo &> /dev/null; then
    sudo playwright install-deps chromium 2>/dev/null || {
        echo "   ⚠️ 系统依赖自动安装失败"
        echo "   请手动执行: sudo $(which playwright) install-deps chromium"
        echo "   或者安装以下常见依赖:"
        echo "   Ubuntu/Debian: sudo apt install -y libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libnspr4 libnss3"
    }
else
    echo "   ⚠️ 无 sudo 权限，跳过系统依赖安装"
    echo "   如遇浏览器启动失败，请联系管理员安装系统依赖"
fi
echo "   ✅ 浏览器安装完成"

# 6. 创建数据目录
mkdir -p "$DATA_DIR/chrome-profile"
mkdir -p "$DATA_DIR/logs"

echo ""
echo "================================================"
echo "✅ 安装完成！"
echo ""
echo "下一步："
echo "  1. 首次登录: bash $SKILL_DIR/scripts/login.sh"
echo "  2. 启动服务: bash $SKILL_DIR/scripts/start.sh"
echo ""
echo "⚠️ 注意: 首次登录需要桌面环境（或 SSH X11 转发）"
echo "   ssh -X user@server  # 然后执行 login.sh"
echo "================================================"
