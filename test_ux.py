"""用户体验测试：用 Playwright 打开浏览器，逐个测试功能"""
import time
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        errors = []
        page.on("pageerror", lambda e: errors.append(f"[PAGE ERROR] {e}"))
        page.on("console", lambda msg: errors.append(f"[CONSOLE {msg.type}] {msg.text}") if msg.type == "error" else None)

        print("=== 1. 打开首页 ===")
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        page.screenshot(path="F:/giteeProject/warframe/screenshots/01_home.png")
        print(f"  标题: {page.title()}")

        # 关闭欢迎弹窗
        welcome_modal = page.locator("#welcome-modal.active")
        if welcome_modal.count() > 0:
            print("  检测到欢迎弹窗，点击开始按钮关闭")
            start_btn = page.locator("#start-btn")
            if start_btn.count() > 0:
                start_btn.first.click()
                time.sleep(1)
            else:
                # 直接移除 active 类
                page.evaluate("document.getElementById('welcome-modal').classList.remove('active')")
                time.sleep(0.5)
            page.screenshot(path="F:/giteeProject/warframe/screenshots/01b_after_modal.png")

        print("\n=== 2. 测试快捷按钮 - 充沛价格 ===")
        btn = page.locator("text=充沛价格")
        if btn.count() > 0:
            btn.first.click()
            time.sleep(3)
            page.screenshot(path="F:/giteeProject/warframe/screenshots/02_arcane_price.png")
            msgs = page.locator(".message.agent")
            print(f"  Agent 消息数: {msgs.count()}")
            if msgs.count() > 0:
                last = msgs.last.inner_text()[:200]
                print(f"  最后消息: {last}")
        else:
            print("  ERROR: 充沛价格按钮未找到")

        print("\n=== 3. 测试快捷按钮 - 查看记忆 ===")
        btn = page.locator("text=查看记忆")
        if btn.count() > 0:
            btn.first.click()
            time.sleep(2)
            page.screenshot(path="F:/giteeProject/warframe/screenshots/03_memory.png")
            msgs = page.locator(".message.agent")
            if msgs.count() > 0:
                last = msgs.last.inner_text()[:200]
                print(f"  最后消息: {last}")
        else:
            print("  ERROR: 查看记忆按钮未找到")

        print("\n=== 4. 测试收藏列表 - 点击查价 ===")
        fav_btn = page.locator(".favorite-item .action-btn:has-text('查价')")
        if fav_btn.count() > 0:
            fav_btn.first.click()
            time.sleep(3)
            page.screenshot(path="F:/giteeProject/warframe/screenshots/04_fav_query.png")
            msgs = page.locator(".message.agent")
            if msgs.count() > 0:
                last = msgs.last.inner_text()[:200]
                print(f"  最后消息: {last}")
        else:
            # 尝试点击整个收藏项
            fav_item = page.locator(".favorite-item")
            if fav_item.count() > 0:
                print("  查价按钮未找到，尝试点击收藏项本身")
                fav_item.first.click()
                time.sleep(3)
                page.screenshot(path="F:/giteeProject/warframe/screenshots/04_fav_click.png")
            else:
                print("  ERROR: 收藏列表为空")

        print("\n=== 5. 测试收藏仪表盘 ===")
        more_btn = page.locator("#more-menu-btn")
        if more_btn.count() > 0:
            more_btn.first.click()
            time.sleep(0.5)
            dash_btn = page.locator("#dashboard-btn")
            if dash_btn.count() > 0:
                dash_btn.first.click()
                time.sleep(3)
                page.screenshot(path="F:/giteeProject/warframe/screenshots/05_dashboard.png")
                # 检查模式切换按钮
                toggle = page.locator(".mode-toggle-btn")
                print(f"  模式切换按钮数: {toggle.count()}")
                # 检查是否有错误
                error_el = page.locator("text=加载仪表盘失败")
                if error_el.count() > 0:
                    print("  ERROR: 仪表盘加载失败")
                else:
                    items = page.locator(".dashboard-item")
                    print(f"  物品数: {items.count()}")
            else:
                print("  ERROR: dashboard-btn 未找到")
        else:
            print("  ERROR: more-menu-btn 未找到")

        print("\n=== 6. 测试仪表盘满级模式切换 ===")
        maxrank_btn = page.locator(".mode-toggle-btn:has-text('满级成本')")
        if maxrank_btn.count() > 0:
            maxrank_btn.first.click()
            time.sleep(3)
            page.screenshot(path="F:/giteeProject/warframe/screenshots/06_dashboard_maxrank.png")
            items = page.locator(".dashboard-item")
            print(f"  满级模式物品数: {items.count()}")
        else:
            print("  ERROR: 满级成本按钮未找到")

        print("\n=== 7. 测试发送消息 ===")
        chat_input = page.locator("#chat-input")
        if chat_input.count() > 0:
            chat_input.fill("充沛多少钱")
            send_btn = page.locator("#send-btn")
            send_btn.click()
            time.sleep(4)
            page.screenshot(path="F:/giteeProject/warframe/screenshots/07_chat_send.png")
            msgs = page.locator(".message.agent")
            if msgs.count() > 0:
                last = msgs.last.inner_text()[:300]
                print(f"  最后消息: {last}")
        else:
            print("  ERROR: chat-input 未找到")

        print("\n=== 8. 检查套利按钮是否已移除 ===")
        arb_btn = page.locator("#arbitrage-btn")
        if arb_btn.count() > 0:
            arb_btn.first.click()
            time.sleep(2)
            page.screenshot(path="F:/giteeProject/warframe/screenshots/08_arbitrage.png")
            # 检查是否返回 404 或错误
            error_el = page.locator("text=加载套利数据失败")
            print(f"  套利按钮仍存在, 加载失败: {error_el.count() > 0}")
        else:
            print("  OK: 套利按钮已移除")

        print("\n=== 控制台错误汇总 ===")
        for e in errors:
            print(f"  {e}")
        if not errors:
            print("  无错误")

        browser.close()

if __name__ == "__main__":
    main()
