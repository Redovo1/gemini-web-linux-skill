#!/bin/bash
# =============================================================
# Gemini Web Proxy - 停止服务
# =============================================================

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$SKILL_DIR/data/server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "ℹ️  服务未在运行（无 PID 文件）"
    # 还是检查一下有没有残留进程
    REMAINING=$(pgrep -f "gemini_proxy.py" 2>/dev/null || true)
    if [ -n "$REMAINING" ]; then
        echo "⚠️ 发现残留的 gemini_proxy 进程: $REMAINING"
        echo "   正在清理..."
        kill $REMAINING 2>/dev/null
        sleep 1
        kill -9 $REMAINING 2>/dev/null || true
        echo "✅ 残留进程已清理"
    fi
    exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    echo "🛑 停止 Gemini Web Proxy (PID: $PID)..."
    kill "$PID"
    sleep 2

    # 如果还没停，强制杀
    if kill -0 "$PID" 2>/dev/null; then
        echo "   强制终止进程..."
        kill -9 "$PID" 2>/dev/null
        sleep 1
    fi

    rm -f "$PID_FILE"
    echo "✅ 服务已停止"
else
    rm -f "$PID_FILE"
    echo "ℹ️  服务进程 (PID: $PID) 已不存在，已清理 PID 文件"
fi

# 清理可能残留的 Chromium 子进程
CHROME_PROCS=$(pgrep -f "chromium.*--user-data-dir=$SKILL_DIR/data/chrome-profile" 2>/dev/null || true)
if [ -n "$CHROME_PROCS" ]; then
    echo "🧹 清理残留 Chromium 进程..."
    kill $CHROME_PROCS 2>/dev/null || true
    sleep 1
    kill -9 $CHROME_PROCS 2>/dev/null || true
    echo "✅ Chromium 进程已清理"
fi
