"""
Gemini Web Proxy - Google 账号登录助手
使用 Playwright 打开浏览器，让用户手动登录 Google 账号并保存登录状态。
"""

import argparse
import sys
import signal


def main():
    parser = argparse.ArgumentParser(description="Gemini Login Helper")
    parser.add_argument("--profile-dir", required=True, help="Chrome profile 保存目录")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright 未安装，请先执行安装脚本: bash scripts/setup.sh")
        sys.exit(1)

    print("🌐 正在启动浏览器...")
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

    # 注意：不要使用 channel="chromium"
    # playwright install chromium 安装的是 bundled Chromium
    # 指定 channel 会去找系统安装的 Chrome/Chromium，在纯净 Linux 上可能找不到
    context = pw.chromium.launch_persistent_context(
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
        # 监听所有页面关闭事件
        while True:
            pages = context.pages
            if not pages:
                break
            try:
                pages[0].wait_for_event("close", timeout=5000)
                break
            except Exception:
                # 超时继续等待
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
