#!/bin/bash
# =============================================================
# Gemini Web Proxy - 一键测试脚本
# 测试 API 连通性 + 文本对话 + 图片生成
# =============================================================

API="http://127.0.0.1:8766"
PASS=0
FAIL=0

echo "🧪 Gemini Web Proxy 一键测试"
echo "================================================"
echo ""

# -------- 测试 1: 健康检查 --------
echo "📋 测试 1/4: 健康检查..."
HEALTH=$(curl -s "$API/health" 2>/dev/null)
if echo "$HEALTH" | grep -q '"status"'; then
    echo "   ✅ 服务正常运行"
    echo "   $HEALTH" | python3 -m json.tool 2>/dev/null || echo "   $HEALTH"
    PASS=$((PASS+1))
else
    echo "   ❌ 服务未启动或无法连接"
    echo "   请先执行: bash scripts/start.sh"
    echo ""
    echo "结果: 0/4 通过"
    exit 1
fi

echo ""

# -------- 测试 2: 模型列表 --------
echo "📋 测试 2/4: 获取模型列表..."
MODELS=$(curl -s "$API/v1/models" 2>/dev/null)
if echo "$MODELS" | grep -q 'gemini-web'; then
    echo "   ✅ 模型列表正常"
    PASS=$((PASS+1))
else
    echo "   ❌ 模型列表获取失败"
    FAIL=$((FAIL+1))
fi

echo ""

# -------- 测试 3: 文本对话 --------
echo "📋 测试 3/4: 文本对话测试（发送"你好，请用一句话介绍自己"）..."
echo "   ⏳ 等待回复中（可能需要 10-30 秒）..."

CHAT_RESP=$(curl -s --max-time 120 "$API/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-web",
    "messages": [{"role": "user", "content": "你好，请用一句话介绍自己"}],
    "stream": false
  }' 2>/dev/null)

if echo "$CHAT_RESP" | grep -q '"content"'; then
    CONTENT=$(echo "$CHAT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'][:200])" 2>/dev/null)
    echo "   ✅ 对话成功！"
    echo "   📝 回复: $CONTENT"
    PASS=$((PASS+1))
else
    echo "   ❌ 对话失败"
    echo "   响应: $CHAT_RESP"
    FAIL=$((FAIL+1))
fi

echo ""

# -------- 测试 4: 图片生成 --------
echo "📋 测试 4/4: 图片生成测试（请求"画一只穿宇航服的橘猫"）..."
echo "   ⏳ 图片生成中（可能需要 30-60 秒）..."

IMG_RESP=$(curl -s --max-time 180 "$API/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-web",
    "messages": [{"role": "user", "content": "请画一只穿宇航服的橘猫，背景是太空，画风是写实风格"}],
    "stream": false
  }' 2>/dev/null)

if echo "$IMG_RESP" | grep -q '/media/'; then
    IMG_URL=$(echo "$IMG_RESP" | grep -oP 'http://[^"]*?/media/[^"]*')
    echo "   ✅ 图片生成成功！"
    echo "   🖼️ 图片链接: $IMG_URL"

    # 尝试下载图片
    if [ -n "$IMG_URL" ]; then
        SAVE_PATH="/tmp/gemini_test_image.png"
        curl -s -o "$SAVE_PATH" "$IMG_URL" 2>/dev/null
        if [ -f "$SAVE_PATH" ] && [ -s "$SAVE_PATH" ]; then
            SIZE=$(stat -c%s "$SAVE_PATH" 2>/dev/null || stat -f%z "$SAVE_PATH" 2>/dev/null)
            echo "   📥 图片已下载: $SAVE_PATH ($SIZE bytes)"
        fi
    fi
    PASS=$((PASS+1))
elif echo "$IMG_RESP" | grep -q '"content"'; then
    CONTENT=$(echo "$IMG_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'][:300])" 2>/dev/null)
    echo "   ⚠️ 有回复但没检测到图片链接"
    echo "   📝 回复: $CONTENT"
    FAIL=$((FAIL+1))
else
    echo "   ❌ 图片生成失败"
    echo "   响应: $(echo $IMG_RESP | head -c 300)"
    FAIL=$((FAIL+1))
fi

echo ""
echo "================================================"
echo "🏁 测试完成: $PASS/4 通过, $FAIL/4 失败"
echo "================================================"

if [ $FAIL -eq 0 ]; then
    echo "🎉 所有测试通过！你的 Gemini Web Proxy 运行完美！"
else
    echo "⚠️ 部分测试未通过，请检查日志: cat data/logs/server.log"
fi
