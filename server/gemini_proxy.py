"""
Gemini Web Proxy Server v1.3.0
===============================
使用 Playwright 自动化 Gemini 网页，提供 OpenAI 兼容的 HTTP API。

v1.3.0 - 修复图片保存到本地文件 + 提供下载URL + 安全的文本注入
v1.2.0 - 修复代理支持 / Flask 线程冲突 / 图片 Blob 提取

使用方法:
    python gemini_proxy.py --port 8766 --profile-dir /path/to/chrome-profile
    python gemini_proxy.py --port 8766 --profile-dir /path/to/chrome-profile --proxy http://127.0.0.1:10808
"""

import argparse
import base64
import json
import time
import uuid
import sys
import signal
import os
from flask import Flask, request, jsonify, Response, send_from_directory

app = Flask(__name__)

# 全局变量
browser_context = None
browser_page = None
playwright_instance = None
profile_dir_global = None
proxy_server_global = None
media_dir_global = None
server_host_global = "127.0.0.1"
server_port_global = 8766

message_count = 0
MAX_MESSAGES_PER_CHAT = 10


def get_proxy_server(args_proxy=None):
    """获取代理地址。优先 --proxy 参数，其次环境变量。"""
    if args_proxy:
        return args_proxy
    for env_var in ['HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy']:
        proxy = os.environ.get(env_var)
        if proxy:
            return proxy
    return None


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
    print("\n🛑 收到退出信号，正在清理...")
    cleanup_browser()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def init_browser(profile_dir, proxy_server=None):
    """初始化 Playwright 浏览器"""
    global browser_context, browser_page, playwright_instance, profile_dir_global, proxy_server_global

    profile_dir_global = profile_dir
    proxy_server_global = proxy_server

    cleanup_browser()

    from playwright.sync_api import sync_playwright
    playwright_instance = sync_playwright().start()

    launch_kwargs = dict(
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

    if proxy_server:
        launch_kwargs["proxy"] = {"server": proxy_server}
        print(f"🌐 使用代理: {proxy_server}")

    browser_context = playwright_instance.chromium.launch_persistent_context(**launch_kwargs)
    browser_page = browser_context.pages[0] if browser_context.pages else browser_context.new_page()

    print("🌐 正在加载 Gemini 网页...")
    browser_page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)

    title = browser_page.title()
    url = browser_page.url
    print(f"   页面标题: {title}")
    print(f"   页面 URL: {url}")

    if "sign in" in title.lower() or "login" in title.lower() or "accounts.google.com" in url:
        print("❌ Google 登录已过期！请重新运行 login.sh 登录")
        cleanup_browser()
        sys.exit(1)

    try:
        browser_page.wait_for_selector(
            'rich-textarea .ql-editor, div.ql-editor, [aria-label*="prompt"], [aria-label*="输入提示"]',
            timeout=15000,
        )
        print("✅ Gemini 网页加载完成，输入框已就绪")
    except Exception:
        print("⚠️ 未检测到输入框，继续尝试运行")

    print("✅ 浏览器就绪")


def ensure_browser():
    """确保浏览器可用，崩溃则自动重启"""
    global browser_page
    try:
        browser_page.title()
        return True
    except Exception:
        print("⚠️ 浏览器已断开，正在重新初始化...")
        try:
            init_browser(profile_dir_global, proxy_server_global)
            return True
        except Exception as e:
            print(f"❌ 浏览器重启失败: {e}")
            return False


def find_input_element():
    """查找 Gemini 输入框（Quill 编辑器）"""
    global browser_page
    for selector in [
        'rich-textarea .ql-editor',
        'div.ql-editor.textarea',
        'div.ql-editor',
        '[aria-label*="输入提示"]',
        '[aria-label*="Enter a prompt"]',
        '[aria-label*="prompt"]',
        'div[contenteditable="true"][role="textbox"]',
    ]:
        try:
            element = browser_page.wait_for_selector(selector, timeout=3000)
            if element and element.is_visible():
                return element
        except Exception:
            continue
    return None


def find_send_button():
    """查找发送按钮"""
    global browser_page
    for selector in [
        'button.send-button',
        'button[aria-label="发送"]',
        'button[aria-label="Send message"]',
        'button[aria-label*="Send"]',
        'button[aria-label*="发送"]',
    ]:
        try:
            btn = browser_page.query_selector(selector)
            if btn and btn.is_visible():
                return btn
        except Exception:
            continue
    return None


def wait_for_response_complete(existing_count, max_wait=120):
    """等待 Gemini 回复完成（三重检测）"""
    global browser_page
    waited = 0
    generation_started = False
    last_text_length = 0
    stable_count = 0

    while waited < max_wait:
        time.sleep(1)
        waited += 1

        current_count = count_existing_responses()
        if current_count > existing_count:
            generation_started = True

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

        if generation_started or waited > 5:
            try:
                current_text = _extract_raw_text()
                current_length = len(current_text) if current_text else 0
                if current_length > 0:
                    if current_length == last_text_length:
                        stable_count += 1
                        if stable_count >= 3:
                            return True
                    else:
                        stable_count = 0
                    last_text_length = current_length
            except Exception:
                pass

        if waited > 30 and not generation_started and last_text_length == 0:
            print("   ⚠️ 等待 30 秒仍无回复，可能发送失败")
            return False

    print("   ⚠️ 等待回复超时")
    return True


def _extract_raw_text():
    """快速提取纯文本用于稳定性检测（不处理图片）"""
    global browser_page
    try:
        return browser_page.evaluate("""
            () => {
                const els = document.querySelectorAll('div[id^="model-response-message-content"]');
                if (els.length > 0) return els[els.length - 1].innerText.trim();
                return '';
            }
        """)
    except Exception:
        return ""


def save_image_from_base64(base64_data_url, alt_text="image"):
    """
    将 Base64 data URL 保存为本地文件，返回可下载的 HTTP URL。
    """
    global media_dir_global

    try:
        # 解析 data:image/png;base64,xxxxx
        if "," not in base64_data_url:
            return None

        header, data = base64_data_url.split(",", 1)

        # 确定扩展名
        ext = "png"
        if "jpeg" in header or "jpg" in header:
            ext = "jpg"
        elif "webp" in header:
            ext = "webp"
        elif "gif" in header:
            ext = "gif"

        # 生成文件名
        filename = f"gemini_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
        filepath = os.path.join(media_dir_global, filename)

        # 写入文件
        img_bytes = base64.b64decode(data)
        with open(filepath, "wb") as f:
            f.write(img_bytes)

        print(f"   🖼️ 图片已保存: {filename} ({len(img_bytes)} bytes)")

        # 返回可访问的 URL
        return f"http://{server_host_global}:{server_port_global}/media/{filename}"

    except Exception as e:
        print(f"   ⚠️ 图片保存失败: {e}")
        return None


def get_latest_response_text():
    """
    提取 Gemini 的最新回复。

    关键改进（v1.3.0）:
    1. 精准提取可见文本，跳过 aria-hidden/display:none 的隐藏元素
    2. 图片提取: 用 fetch(blobUrl) + FileReader 代替 canvas（避免跨域污染）
    3. 图片保存为本地文件，返回 HTTP 下载 URL（而非巨大的 Base64 内联）
    """
    global browser_page

    try:
        # 第一步：提取文本和图片 blob URL 列表
        response_data = browser_page.evaluate("""
            () => {
                // 找到最后一个模型回复容器
                let container = null;
                const byId = document.querySelectorAll('div[id^="model-response-message-content"]');
                if (byId.length > 0) container = byId[byId.length - 1];
                if (!container) {
                    const byRole = document.querySelectorAll('[data-message-author-role="model"]');
                    if (byRole.length > 0) container = byRole[byRole.length - 1];
                }
                if (!container) {
                    const byTag = document.querySelectorAll('model-response');
                    if (byTag.length > 0) container = byTag[byTag.length - 1];
                }
                if (!container) return { text: '', images: [] };

                const textParts = [];
                const images = [];

                function extractVisible(el) {
                    if (!el || !el.tagName) return;

                    // 跳过隐藏元素
                    try {
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' ||
                            style.opacity === '0') return;
                    } catch(e) {}
                    if (el.getAttribute('aria-hidden') === 'true') return;

                    // 图片
                    if (el.tagName === 'IMG') {
                        const src = el.src || '';
                        if (src) images.push({ src: src, alt: el.alt || 'image' });
                        return;
                    }

                    // 代码块
                    if (el.tagName === 'PRE') {
                        const code = el.textContent.trim();
                        if (code) {
                            const codeEl = el.querySelector('code');
                            const lang = codeEl ? (codeEl.className.match(/language-(\\w+)/)?.[1] || '') : '';
                            textParts.push('```' + lang + '\\n' + code + '\\n```');
                        }
                        return;
                    }
                    if (el.tagName === 'CODE' && !el.closest('pre')) {
                        const code = el.textContent.trim();
                        if (code) textParts.push('`' + code + '`');
                        return;
                    }

                    // 块级文本元素
                    const blocks = ['P','H1','H2','H3','H4','H5','H6','LI','BLOCKQUOTE'];
                    if (blocks.includes(el.tagName)) {
                        const text = el.innerText.trim();
                        if (text) {
                            if (el.tagName === 'LI') {
                                const parent = el.parentElement;
                                const prefix = parent && parent.tagName === 'OL'
                                    ? (Array.from(parent.children).indexOf(el) + 1) + '. '
                                    : '- ';
                                textParts.push(prefix + text);
                            } else {
                                textParts.push(text);
                            }
                        }
                        return;
                    }

                    // 递归子元素
                    for (const child of el.children) extractVisible(child);
                }

                extractVisible(container);
                return { text: textParts.join('\\n\\n'), images: images };
            }
        """)

        text = response_data.get("text", "") if response_data else ""
        images = response_data.get("images", []) if response_data else []

        # 第二步：处理图片
        if images:
            for img_info in images:
                src = img_info.get("src", "")
                alt = img_info.get("alt", "image")

                if src.startswith("blob:"):
                    # 用 fetch + FileReader 提取 blob 数据（避免 canvas 跨域污染）
                    try:
                        base64_data = browser_page.evaluate("""
                            (blobUrl) => {
                                return new Promise((resolve, reject) => {
                                    fetch(blobUrl)
                                        .then(r => r.blob())
                                        .then(blob => {
                                            const reader = new FileReader();
                                            reader.onloadend = () => resolve(reader.result);
                                            reader.onerror = () => resolve('');
                                            reader.readAsDataURL(blob);
                                        })
                                        .catch(() => resolve(''));
                                });
                            }
                        """, src)

                        if base64_data and base64_data.startswith("data:"):
                            # 保存为文件，返回下载 URL
                            download_url = save_image_from_base64(base64_data, alt)
                            if download_url:
                                text += f"\n\n![{alt}]({download_url})"
                            else:
                                text += "\n\n[图片已生成，但保存失败。请在 Gemini 网页查看]"
                        else:
                            text += "\n\n[图片已生成，但提取失败。请在 Gemini 网页查看]"
                    except Exception as e:
                        print(f"   ⚠️ 图片 blob 提取异常: {e}")
                        text += "\n\n[图片已生成，但提取异常。请在 Gemini 网页查看]"

                elif src.startswith("http"):
                    text += f"\n\n![{alt}]({src})"

        return text

    except Exception as e:
        print(f"   ⚠️ 提取回复异常: {e}")
        return ""


def count_existing_responses():
    """计算当前页面上已有的回复数量"""
    global browser_page
    try:
        return browser_page.evaluate("""
            () => document.querySelectorAll('div[id^="model-response-message-content"]').length
        """)
    except Exception:
        return 0


def send_message_to_gemini(message_text):
    """向 Gemini 网页发送消息并获取回复。"""
    global browser_page, message_count

    try:
        if not ensure_browser():
            return {"error": "浏览器不可用，请检查服务状态"}

        if message_count >= MAX_MESSAGES_PER_CHAT:
            print("🔄 对话轮次已达上限，自动新建对话...")
            create_new_chat_internal()
            message_count = 0

        # 1. 查找输入框
        input_element = find_input_element()
        if not input_element:
            print("⚠️ 未找到输入框，尝试刷新页面...")
            browser_page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
            time.sleep(5)
            input_element = find_input_element()
        if not input_element:
            return {"error": "无法找到 Gemini 输入框，请检查登录状态或执行 login.sh 重新登录"}

        # 2. 记录已有回复数量
        existing_count = count_existing_responses()

        # 3. 清空输入框
        input_element.click()
        time.sleep(0.3)
        try:
            browser_page.evaluate("""
                () => {
                    const editor = document.querySelector('rich-textarea .ql-editor, div.ql-editor');
                    if (editor) editor.innerHTML = '<p><br></p>';
                }
            """)
        except Exception:
            try:
                input_element.press("Control+a")
                time.sleep(0.1)
                input_element.press("Delete")
            except Exception:
                pass
        time.sleep(0.3)

        # 4. 输入内容（安全的 JS 注入方式）
        input_element.click()
        time.sleep(0.2)

        # 用 JSON.stringify 安全传递文本，不用 f-string 模板避免转义问题
        try:
            browser_page.evaluate("""
                (text) => {
                    const editor = document.querySelector('rich-textarea .ql-editor, div.ql-editor');
                    if (editor) {
                        // 将文本按换行分段
                        const paragraphs = text.split('\\n').map(line => '<p>' + (line || '<br>') + '</p>');
                        editor.innerHTML = paragraphs.join('');
                        editor.dispatchEvent(new Event('input', { bubbles: true }));
                        editor.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            """, message_text)  # Playwright 的 evaluate 会安全地序列化参数
            time.sleep(0.5)
        except Exception:
            print("   ⚠️ JS 注入失败，降级为逐字输入")
            input_element.type(message_text, delay=5)

        time.sleep(0.8)

        # 5. 点击发送
        send_btn = find_send_button()
        if send_btn:
            try:
                send_btn.click()
            except Exception:
                input_element.press("Enter")
        else:
            input_element.press("Enter")

        # 6. 等待回复
        print(f"   📨 已发送（{len(message_text)} 字），等待回复...")
        time.sleep(3)
        wait_for_response_complete(existing_count)

        # 7. 提取回复
        time.sleep(1)
        response_text = get_latest_response_text()
        if not response_text:
            time.sleep(3)
            response_text = get_latest_response_text()
        if not response_text:
            return {"error": "Gemini 回复提取失败。可能原因：1) 登录过期 2) 网页结构已更新 3) 网络问题。"}

        message_count += 1
        print(f"   ✅ 收到回复（{len(response_text)} 字）")
        return {"content": response_text}

    except Exception as e:
        print(f"   ❌ 发送消息失败: {e}")
        return {"error": f"发送消息失败: {str(e)}"}


def create_new_chat_internal():
    global browser_page
    try:
        browser_page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
        time.sleep(3)
        find_input_element()
        return True
    except Exception as e:
        print(f"   ⚠️ 新建对话失败: {e}")
        return False


def create_new_chat():
    global message_count
    success = create_new_chat_internal()
    if success:
        message_count = 0
    return success


# ============================================================
# API 路由
# ============================================================

@app.route("/v1/models", methods=["GET"])
def list_models():
    return jsonify({
        "object": "list",
        "data": [
            {"id": "gemini-web", "object": "model", "created": int(time.time()), "owned_by": "google-web"},
            {"id": "gemini-web-thinking", "object": "model", "created": int(time.time()), "owned_by": "google-web"},
        ]
    })


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    try:
        data = request.get_json()
        if not data or "messages" not in data:
            return jsonify({"error": {"message": "messages 字段是必须的", "type": "invalid_request_error"}}), 400

        messages = data["messages"]
        model = data.get("model", "gemini-web")
        stream = data.get("stream", False)

        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                    user_message = " ".join(text_parts)
                else:
                    user_message = content
                break

        if not user_message:
            return jsonify({"error": {"message": "未找到用户消息", "type": "invalid_request_error"}}), 400

        print(f"📨 收到请求 [{model}]: {user_message[:100]}...")
        result = send_message_to_gemini(user_message)

        if "error" in result:
            return jsonify({"error": {"message": result["error"], "type": "server_error"}}), 500

        response_text = result["content"]
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        if stream:
            def generate():
                yield f"data: {json.dumps({'id': response_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"
                chunk_size = 50
                for i in range(0, len(response_text), chunk_size):
                    yield f"data: {json.dumps({'id': response_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {'content': response_text[i:i+chunk_size]}, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'id': response_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            return Response(generate(), content_type="text/event-stream")
        else:
            return jsonify({
                "id": response_id, "object": "chat.completion", "created": int(time.time()), "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(user_message), "completion_tokens": len(response_text), "total_tokens": len(user_message) + len(response_text)}
            })
    except Exception as e:
        print(f"❌ 请求处理失败: {e}")
        return jsonify({"error": {"message": str(e), "type": "server_error"}}), 500


@app.route("/v1/chat/completions/new", methods=["POST"])
def new_chat():
    success = create_new_chat()
    return jsonify({"status": "ok", "message": "已创建新对话"}) if success else (jsonify({"error": "创建新对话失败"}), 500)


@app.route("/media/<path:filename>", methods=["GET"])
def serve_media(filename):
    """提供图片文件下载"""
    return send_from_directory(media_dir_global, filename)


@app.route("/health", methods=["GET"])
def health_check():
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
        "service": "gemini-web-proxy", "version": "1.3.0",
        "message_count": message_count,
        "proxy": proxy_server_global or "none",
        "media_dir": media_dir_global,
        "timestamp": int(time.time()),
    })


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "Gemini Web Proxy", "version": "1.3.0",
        "endpoints": {
            "chat": "/v1/chat/completions", "models": "/v1/models",
            "new_chat": "/v1/chat/completions/new", "media": "/media/<filename>",
            "health": "/health",
        },
    })


def main():
    global media_dir_global, server_host_global, server_port_global

    parser = argparse.ArgumentParser(description="Gemini Web Proxy Server")
    parser.add_argument("--port", type=int, default=8766, help="HTTP 服务端口")
    parser.add_argument("--profile-dir", required=True, help="Chrome profile 目录路径")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--proxy", default=None, help="代理地址 (如: http://127.0.0.1:10808)")
    args = parser.parse_args()

    server_host_global = args.host
    server_port_global = args.port

    # 创建图片保存目录
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    media_dir_global = os.path.join(skill_dir, "data", "media")
    os.makedirs(media_dir_global, exist_ok=True)

    proxy = get_proxy_server(args.proxy)
    init_browser(args.profile_dir, proxy)

    print(f"\n🚀 Gemini Web Proxy v1.3.0 已启动！")
    print(f"   API 地址:  http://{args.host}:{args.port}/v1")
    print(f"   图片目录:  {media_dir_global}")
    print(f"   图片下载:  http://{args.host}:{args.port}/media/<filename>")
    if proxy:
        print(f"   代理地址:  {proxy}")
    print(f"\n   按 Ctrl+C 停止服务\n")

    try:
        app.run(host=args.host, port=args.port, debug=False, threaded=False)
    finally:
        cleanup_browser()


if __name__ == "__main__":
    main()
