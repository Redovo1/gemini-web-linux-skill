"""
Gemini Web Proxy - Google 账号登录助手 v1.2.0
使用 Playwright 打开浏览器，让用户手动登录 Google 账号并保存登录状态。

支持 --proxy 参数让浏览器走代理。
"""

import argparse
import sys
import signal
import os


def get_proxy_server(args_proxy=None):
    """获取代理地址。优先 --proxy 参数，其次环境变量。"""
    if args_proxy:
        return args_proxy
    for env_var in ['HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy']:
        proxy = os.environ.get(env_var)
        if proxy:
            return proxy
    return None


def main():
    parser = argparse.ArgumentParser(description="Gemini Login Helper")
    parser.add_argument("--profile-dir", required=True, help="Chrome profile 保存目录")
    parser.add_argument("--proxy", default=None, help="代理地址 (如: http://127.0.0.1:10808)")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright 未安装，请先执行安装脚本: bash scripts/setup.sh")
        sys.exit(1)

    proxy = get_proxy_server(args.proxy)

    print("🌐 正在启动浏览器...")
    if proxy:
        print(f"   使用代理: {proxy}")
    print("   请在浏览器中登录 Google 账号并进入 Gemini 页面")
    print("   完成后关闭浏览器窗口即可\n")

    pw = None
    context = None

    def cleanup(sig=None, frame=None):
        """Ctrl+C 时优雅退出"""
        print("\n\n🔐 正在保存登录状态...")
        try:
            if context:
                context.close()
        except Exception:
            pass
        try:
            if pw:
                pw.stop()
        except Exception:
            pass
        print("✅ 登录状态已保存！")
        print("   现在可以启动服务: bash scripts/start.sh")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    pw = sync_playwright().start()

    # 构建启动参数
    launch_kwargs = dict(
        user_data_dir=args.profile_dir,
        headless=False,  # 必须有界面让用户登录
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ],
        ignore_default_args=["--enable-automation"],
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )

    # 代理支持
    if proxy:
        launch_kwargs["proxy"] = {"server": proxy}

    context = pw.chromium.launch_persistent_context(**launch_kwargs)

    page = context.pages[0] if context.pages else context.new_page()

    # 导航到 Gemini
    try:
        page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"⚠️ 页面加载较慢，但浏览器已打开: {e}")

    print("=" * 50)
    print("✅ 浏览器已打开！")
    print("")
    print("请完成以下操作：")
    print("  1. 如果需要，登录你的 Google 账号")
    print("  2. 确保能看到 Gemini 的对话界面")
    print("  3. 完成后 关闭浏览器窗口 或按 Ctrl+C")
    print("")
    print("⏳ 等待你操作...")
    print("=" * 50)

    # 等待用户关闭浏览器
    try:
        while True:
            pages = context.pages
            if not pages:
                break
            try:
                pages[0].wait_for_event("close", timeout=5000)
                break
            except Exception:
                continue
    except Exception:
        pass

    # 清理
    try:
        context.close()
    except Exception:
        pass
    try:
        pw.stop()
    except Exception:
        pass

    print("\n✅ 登录状态已保存！")
    print("   现在可以启动服务: bash scripts/start.sh")


if __name__ == "__main__":
    main()
