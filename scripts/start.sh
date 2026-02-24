#!/bin/bash
# =============================================================
# Gemini Web Proxy - 启动服务
# =============================================================

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$SKILL_DIR/venv"
PID_FILE="$SKILL_DIR/data/server.pid"
LOG_FILE="$SKILL_DIR/data/logs/server.log"

# 检查虚拟环境是否存在
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ 虚拟环境不存在，请先运行安装脚本："
    echo "   bash $SKILL_DIR/scripts/setup.sh"
    exit 1
fi

# 检查是否已在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⚡ 服务已在运行 (PID: $OLD_PID)"
        echo "   API 地址: http://127.0.0.1:8766/v1"
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# 检查登录状态
if [ ! -d "$SKILL_DIR/data/chrome-profile" ] || [ -z "$(ls -A "$SKILL_DIR/data/chrome-profile" 2>/dev/null)" ]; then
    echo "❌ 尚未登录 Google 账号！"
    echo "   请先执行: bash $SKILL_DIR/scripts/login.sh"
    exit 1
fi

# 确保日志目录存在
mkdir -p "$SKILL_DIR/data/logs"

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

echo "🚀 启动 Gemini Web Proxy 服务..."

# 后台启动服务
nohup python3 "$SKILL_DIR/server/gemini_proxy.py" \
    --port 8766 \
    --profile-dir "$SKILL_DIR/data/chrome-profile" \
    > "$LOG_FILE" 2>&1 &

SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

# 等待服务启动
echo "   等待服务就绪（首次启动约需 10-20 秒）..."
for i in $(seq 1 40); do
    # 先检查进程是否还活着
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo ""
        echo "❌ 服务启动失败！进程已退出。"
        echo "   请查看日志: cat $LOG_FILE"
        echo ""
        echo "   常见原因:"
        echo "   1. Google 登录已过期 → 执行 bash $SKILL_DIR/scripts/login.sh"
        echo "   2. Chromium 系统依赖缺失 → 执行 sudo playwright install-deps chromium"
        rm -f "$PID_FILE"
        exit 1
    fi

    if curl -s http://127.0.0.1:8766/v1/models > /dev/null 2>&1; then
        echo ""
        echo "✅ 服务已启动！"
        echo "   PID: $SERVER_PID"
        echo "   API 地址: http://127.0.0.1:8766/v1"
        echo "   日志文件: $LOG_FILE"
        echo ""
        echo "   测试命令:"
        echo "   curl http://127.0.0.1:8766/health"
        exit 0
    fi
    sleep 2
    echo -n "."
done

echo ""
echo "⚠️ 服务启动超时（但进程仍在运行 PID: $SERVER_PID）"
echo "   请检查日志: tail -f $LOG_FILE"
echo "   进程可能仍在加载 Gemini 网页，请稍后重试"
