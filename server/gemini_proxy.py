"""
Gemini Web Proxy Server
=======================
使用 Playwright 自动化 Gemini 网页，提供 OpenAI 兼容的 HTTP API。

核心原理：
1. 用 Playwright 启动无头 Chromium，加载已保存的 Google 登录态
2. 在 Gemini 网页中注入/提取对话内容
3. 通过 Flask HTTP 服务器对外提供 OpenAI Chat Completions 兼容接口

使用方法：
    python gemini_proxy.py --port 8766 --profile-dir /path/to/chrome-profile
"""

import argparse
import json
import time
import uuid
import threading
import sys
import signal
import os
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# 全局浏览器实例
browser_context = None
browser_page = None
browser_lock = threading.Lock()
playwright_instance = None
profile_dir_global = None

# 对话计数器，用于自动新建对话
message_count = 0
MAX_MESSAGES_PER_CHAT = 10  # 每 10 条消息自动新建对话，防止上下文过长


def cleanup_browser():
    """清理浏览器资源"""
    global browser_context, browser_page, playwright_instance
    try:
        if browser_context:
            browser_context.close()
    except Exception:
        pass
    try:
        if playwright_instance:
            playwright_instance.stop()
    except Exception:
        pass
    browser_context = None
    browser_page = None
    playwright_instance = None


def signal_handler(sig, frame):
    """优雅退出"""
    print("\n🛑 收到退出信号，正在清理...")
    cleanup_browser()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def init_browser(profile_dir):
    """初始化 Playwright 浏览器（无头模式）"""
    global browser_context, browser_page, playwright_instance, profile_dir_global

    profile_dir_global = profile_dir

    # 先清理旧实例
    cleanup_browser()

    from playwright.sync_api import sync_playwright

    playwright_instance = sync_playwright().start()

    # 注意：不要使用 channel="chromium"
    # playwright install chromium 安装的是 bundled 版本
    # 指定 channel 会去找系统安装的浏览器，可能找不到
    browser_context = playwright_instance.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-software-rasterizer",
        ],
        ignore_default_args=["--enable-automation"],
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )

    browser_page = browser_context.pages[0] if browser_context.pages else browser_context.new_page()

    # 导航到 Gemini
    print("🌐 正在加载 Gemini 网页...")
    browser_page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=60000)

    # 等待页面加载完成
    time.sleep(5)

    # 检查是否成功进入 Gemini
    title = browser_page.title()
    url = browser_page.url
    print(f"   页面标题: {title}")
    print(f"   页面 URL: {url}")

    if "sign in" in title.lower() or "login" in title.lower() or "accounts.google.com" in url:
        print("❌ Google 登录已过期！请重新运行 login.sh 登录")
        cleanup_browser()
        sys.exit(1)

    # 等待输入框出现，确认页面完全加载
    try:
        browser_page.wait_for_selector(
            'rich-textarea .ql-editor, div.ql-editor, [aria-label*="prompt"], [aria-label*="输入提示"]',
            timeout=15000,
        )
        print("✅ Gemini 网页加载完成，输入框已就绪")
    except Exception:
        print("⚠️ 未检测到输入框，可能需要检查登录状态")
        print("   继续尝试运行，如果请求失败请重新登录")

    print("✅ 浏览器就绪")


def ensure_browser():
    """确保浏览器处于可用状态，如果崩溃则自动重启"""
    global browser_page
    try:
        # 简单检查：尝试获取页面标题
        browser_page.title()
        return True
    except Exception:
        print("⚠️ 浏览器已断开，正在重新初始化...")
        try:
            init_browser(profile_dir_global)
            return True
        except Exception as e:
            print(f"❌ 浏览器重启失败: {e}")
            return False


def find_input_element():
    """
    查找 Gemini 的输入框。
    Gemini 使用 Quill 富文本编辑器，输入框是:
      <rich-textarea>
        <div class="ql-editor textarea" contenteditable="true" aria-label="为 Gemini 输入提示">
    """
    global browser_page

    # 按优先级尝试，最精确的在前面
    selectors = [
        'rich-textarea .ql-editor',                    # 最精确：Quill 编辑器
        'div.ql-editor.textarea',                      # 带 textarea class 的 Quill 编辑器
        'div.ql-editor',                               # 通用 Quill 编辑器
        '[aria-label*="输入提示"]',                      # 中文 aria-label
        '[aria-label*="Enter a prompt"]',               # 英文 aria-label
        '[aria-label*="prompt"]',                       # 通用 prompt
        'div[contenteditable="true"][role="textbox"]',  # 通用 contenteditable textbox
    ]

    for selector in selectors:
        try:
            element = browser_page.wait_for_selector(selector, timeout=3000)
            if element and element.is_visible():
                return element
        except Exception:
            continue

    return None


def find_send_button():
    """
    查找发送按钮。
    Gemini 的发送按钮:
      <button class="send-button" aria-label="发送">
    注意: 按钮在输入内容后才变为可点击状态。
    """
    global browser_page

    selectors = [
        'button.send-button',                          # 最精确
        'button[aria-label="发送"]',                    # 中文发送
        'button[aria-label="Send message"]',            # 英文发送
        'button[aria-label*="Send"]',                   # 通用英文
        'button[aria-label*="发送"]',                    # 通用中文
    ]

    for selector in selectors:
        try:
            btn = browser_page.query_selector(selector)
            if btn and btn.is_visible():
                return btn
        except Exception:
            continue

    return None


def wait_for_response_complete(existing_count, max_wait=120):
    """
    等待 Gemini 回复完成。

    策略（三重检测）：
    1. 检测新回复 DOM 元素出现（数量 > existing_count）
    2. 检测"停止生成"按钮出现然后消失
    3. 检测回复文本长度稳定（连续 3 秒不变化）
    """
    global browser_page

    waited = 0
    generation_started = False
    last_text_length = 0
    stable_count = 0

    while waited < max_wait:
        time.sleep(1)
        waited += 1

        # 检测1: 新回复元素是否出现
        current_count = count_existing_responses()
        if current_count > existing_count:
            generation_started = True

        # 检测2: "停止生成"按钮是否存在（说明正在生成）
        stop_btn = None
        for sel in ['button[aria-label*="Stop"]', 'button[aria-label*="停止"]']:
            try:
                btn = browser_page.query_selector(sel)
                if btn and btn.is_visible():
                    stop_btn = btn
                    break
            except Exception:
                continue

        if stop_btn:
            generation_started = True
            stable_count = 0
            continue

        # 检测3: 文本长度稳定性
        if generation_started or waited > 5:
            try:
                current_text = get_latest_response_text()
                current_length = len(current_text) if current_text else 0

                if current_length > 0:
                    if current_length == last_text_length:
                        stable_count += 1
                        if stable_count >= 3:
                            # 文本已稳定 3 秒
                            return True
                    else:
                        stable_count = 0
                    last_text_length = current_length
            except Exception:
                pass

        # 如果等了 30 秒但没有任何回复迹象
        if waited > 30 and not generation_started and last_text_length == 0:
            print("   ⚠️ 等待 30 秒仍无回复，可能发送失败")
            return False

    print("   ⚠️ 等待回复超时")
    return True


def get_latest_response_text():
    """
    提取最新的 Gemini 回复文本。
    Gemini 回复的 DOM 结构:
      <div id="model-response-message-content-xxxx">
        <p>回复文本...</p>
        <pre><code>代码块...</code></pre>
      </div>
    """
    global browser_page

    try:
        response_text = browser_page.evaluate("""
            () => {
                // 方法1: 通过 ID 前缀查找（最可靠）
                const responseEls = document.querySelectorAll('div[id^="model-response-message-content"]');
                if (responseEls.length > 0) {
                    const lastEl = responseEls[responseEls.length - 1];
                    return lastEl.innerText.trim();
                }

                // 方法2: 通过 data attribute 查找
                const modelMsgs = document.querySelectorAll('[data-message-author-role="model"]');
                if (modelMsgs.length > 0) {
                    const lastMsg = modelMsgs[modelMsgs.length - 1];
                    // 尝试获取其中的 markdown 内容
                    const markdown = lastMsg.querySelector('.markdown, .model-response-text');
                    if (markdown) return markdown.innerText.trim();
                    return lastMsg.innerText.trim();
                }

                // 方法3: 通过 message-content 自定义元素查找
                const msgContents = document.querySelectorAll('message-content');
                if (msgContents.length > 0) {
                    const lastContent = msgContents[msgContents.length - 1];
                    return lastContent.innerText.trim();
                }

                // 方法4: 通过 model-response 自定义元素查找
                const modelResponses = document.querySelectorAll('model-response');
                if (modelResponses.length > 0) {
                    const lastResp = modelResponses[modelResponses.length - 1];
                    return lastResp.innerText.trim();
                }

                return '';
            }
        """)
        return response_text
    except Exception:
        return ""


def count_existing_responses():
    """计算当前页面上已有的回复数量"""
    global browser_page
    try:
        count = browser_page.evaluate("""
            () => {
                const els = document.querySelectorAll('div[id^="model-response-message-content"]');
                return els.length;
            }
        """)
        return count
    except Exception:
        return 0


def send_message_to_gemini(message_text):
    """
    向 Gemini 网页发送消息并获取回复。
    """
    global browser_page, message_count

    with browser_lock:
        try:
            # 确保浏览器可用
            if not ensure_browser():
                return {"error": "浏览器不可用，请检查服务状态"}

            # 自动新建对话（防止上下文过长）
            if message_count >= MAX_MESSAGES_PER_CHAT:
                print("🔄 对话轮次已达上限，自动新建对话...")
                create_new_chat_internal()
                message_count = 0

            # 1. 查找输入框
            input_element = find_input_element()

            if not input_element:
                # 刷新页面重试
                print("⚠️ 未找到输入框，尝试刷新页面...")
                browser_page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
                time.sleep(5)
                input_element = find_input_element()

            if not input_element:
                return {"error": "无法找到 Gemini 输入框，请检查登录状态或执行 login.sh 重新登录"}

            # 2. 记录已有回复数量
            existing_count = count_existing_responses()

            # 3. 聚焦输入框并清空
            input_element.click()
            time.sleep(0.3)

            # 对于 Quill 编辑器，用 JS 清空更可靠
            try:
                browser_page.evaluate("""
                    () => {
                        const editor = document.querySelector('rich-textarea .ql-editor, div.ql-editor');
                        if (editor) {
                            editor.innerHTML = '<p><br></p>';
                        }
                    }
                """)
            except Exception:
                # 如果 JS 清空失败，用 Ctrl+A + Delete
                try:
                    input_element.press("Control+a")
                    time.sleep(0.1)
                    input_element.press("Delete")
                except Exception:
                    pass

            time.sleep(0.3)

            # 4. 输入内容
            # 对于长文本，逐字 type() 太慢（1000字=5秒）
            # 改用 JS 直接注入文本到 Quill 编辑器，然后触发 input 事件
            input_element.click()
            time.sleep(0.2)

            # 转义文本中的特殊字符用于 JS
            escaped_text = message_text.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

            try:
                browser_page.evaluate(f"""
                    () => {{
                        const editor = document.querySelector('rich-textarea .ql-editor, div.ql-editor');
                        if (editor) {{
                            // 直接设置文本内容
                            editor.innerHTML = '<p>' + `{escaped_text}`.replace(/\n/g, '</p><p>') + '</p>';
                            // 触发 input 事件，让 Gemini 前端感知到内容变化
                            editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            editor.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }}
                """)
                time.sleep(0.5)
            except Exception:
                # JS 注入失败，降级为逐字输入
                print("   ⚠️ JS 注入失败，降级为逐字输入（可能较慢）")
                input_element.type(message_text, delay=5)

            time.sleep(0.8)

            # 5. 点击发送按钮
            send_btn = find_send_button()
            if send_btn:
                try:
                    send_btn.click()
                except Exception:
                    # 按钮点击失败，用 Enter
                    input_element.press("Enter")
            else:
                # 没找到发送按钮，用 Enter 键
                input_element.press("Enter")

            # 6. 等待回复完成
            print(f"   📨 已发送消息（{len(message_text)} 字）, 等待回复...")
            time.sleep(3)  # 先等 3 秒让请求发出

            response_complete = wait_for_response_complete(existing_count)

            # 7. 提取回复
            time.sleep(1)
            response_text = get_latest_response_text()

            if not response_text:
                # 再等几秒重试
                time.sleep(3)
                response_text = get_latest_response_text()

            if not response_text:
                return {"error": "Gemini 回复提取失败。可能原因：1) 登录过期 2) Gemini 网页结构已更新 3) 网络问题。请检查日志。"}

            message_count += 1
            print(f"   ✅ 收到回复（{len(response_text)} 字）")
            return {"content": response_text}

        except Exception as e:
            print(f"   ❌ 发送消息失败: {e}")
            return {"error": f"发送消息失败: {str(e)}"}


def create_new_chat_internal():
    """内部方法: 创建新对话（不加锁，由调用者负责）"""
    global browser_page
    try:
        # 最可靠的方式：直接导航到新对话页面
        browser_page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
        time.sleep(3)

        # 确认输入框出现
        find_input_element()
        return True
    except Exception as e:
        print(f"   ⚠️ 新建对话失败: {e}")
        return False


def create_new_chat():
    """创建新对话（带锁）"""
    global message_count
    with browser_lock:
        success = create_new_chat_internal()
        if success:
            message_count = 0
        return success


# ============================================================
# OpenAI 兼容 API 路由
# ============================================================

@app.route("/v1/models", methods=["GET"])
def list_models():
    """列出可用模型"""
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": "gemini-web",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "google-web",
            },
            {
                "id": "gemini-web-thinking",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "google-web",
            },
        ]
    })


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """OpenAI Chat Completions 兼容接口"""
    try:
        data = request.get_json()

        if not data or "messages" not in data:
            return jsonify({"error": {"message": "messages 字段是必须的", "type": "invalid_request_error"}}), 400

        messages = data["messages"]
        model = data.get("model", "gemini-web")
        stream = data.get("stream", False)

        # 提取最后一条用户消息
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    # 支持多模态消息格式
                    text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                    user_message = " ".join(text_parts)
                else:
                    user_message = content
                break

        if not user_message:
            return jsonify({"error": {"message": "未找到用户消息", "type": "invalid_request_error"}}), 400

        print(f"📨 收到请求 [{model}]: {user_message[:100]}...")

        # 发送到 Gemini
        result = send_message_to_gemini(user_message)

        if "error" in result:
            return jsonify({"error": {"message": result["error"], "type": "server_error"}}), 500

        response_text = result["content"]
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        if stream:
            # SSE 流式输出
            def generate():
                # 第一个 chunk: role
                role_chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant"},
                        "finish_reason": None,
                    }]
                }
                yield f"data: {json.dumps(role_chunk, ensure_ascii=False)}\n\n"

                # 分块发送内容（模拟真实流式）
                chunk_size = 50
                for i in range(0, len(response_text), chunk_size):
                    text_chunk = response_text[i:i + chunk_size]
                    chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": text_chunk},
                            "finish_reason": None,
                        }]
                    }
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

                # 结束标记
                done_chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }]
                }
                yield f"data: {json.dumps(done_chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(generate(), content_type="text/event-stream")

        else:
            # 非流式输出
            return jsonify({
                "id": response_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text,
                    },
                    "finish_reason": "stop",
                }],
                "usage": {
                    "prompt_tokens": len(user_message),
                    "completion_tokens": len(response_text),
                    "total_tokens": len(user_message) + len(response_text),
                }
            })

    except Exception as e:
        print(f"❌ 请求处理失败: {e}")
        return jsonify({"error": {"message": str(e), "type": "server_error"}}), 500


@app.route("/v1/chat/completions/new", methods=["POST"])
def new_chat():
    """开始新对话"""
    success = create_new_chat()
    if success:
        return jsonify({"status": "ok", "message": "已创建新对话"})
    else:
        return jsonify({"error": "创建新对话失败"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """健康检查"""
    browser_ok = False
    try:
        if browser_page:
            browser_page.title()
            browser_ok = True
    except Exception:
        pass

    return jsonify({
        "status": "ok" if browser_ok else "degraded",
        "browser": "connected" if browser_ok else "disconnected",
        "service": "gemini-web-proxy",
        "message_count": message_count,
        "timestamp": int(time.time()),
    })


@app.route("/", methods=["GET"])
def index():
    """首页"""
    return jsonify({
        "service": "Gemini Web Proxy",
        "version": "1.1.0",
        "endpoints": {
            "chat": "/v1/chat/completions",
            "models": "/v1/models",
            "new_chat": "/v1/chat/completions/new",
            "health": "/health",
        },
        "description": "Gemini 网页版 → OpenAI 兼容 API 代理 (Linux 版)",
    })


def main():
    parser = argparse.ArgumentParser(description="Gemini Web Proxy Server")
    parser.add_argument("--port", type=int, default=8766, help="HTTP 服务端口 (默认: 8766)")
    parser.add_argument("--profile-dir", required=True, help="Chrome profile 目录路径")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址 (默认: 127.0.0.1)")
    args = parser.parse_args()

    # 初始化浏览器
    init_browser(args.profile_dir)

    print(f"\n🚀 Gemini Web Proxy 服务已启动！")
    print(f"   API 地址: http://{args.host}:{args.port}/v1")
    print(f"   健康检查: http://{args.host}:{args.port}/health")
    print(f"   模型列表: http://{args.host}:{args.port}/v1/models")
    print(f"\n   按 Ctrl+C 停止服务\n")

    try:
        # 启动 Flask 服务
        app.run(host=args.host, port=args.port, debug=False, threaded=True)
    finally:
        cleanup_browser()


if __name__ == "__main__":
    main()
