"""Read source code from interesting GitHub repos."""
from playwright.sync_api import sync_playwright
import json

def safe_goto(page, url, timeout=15000):
    try:
        page.goto(url, timeout=timeout, wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
    except:
        pass

def get_raw_content(page, url):
    safe_goto(page, url)
    try:
        blob = page.locator('article, .markdown-body, [data-testid="blob-viewer"], .blob-wrapper, .highlight').first
        return blob.inner_text()
    except:
        return page.locator('body').inner_text()[:5000]

FILES_TO_READ = [
    # Mod Flipper logic
    ("https://raw.githubusercontent.com/Nathan47293/warframe-toolkit/main/app.js", "toolkit_app_js"),
    # Set profit analyzer
    ("https://raw.githubusercontent.com/Engusseus/Warframe-Market-Set-Profit-Analyzer/main/wf_market_analyzer.py", "set_analyzer_py"),
    # Market trader API
    ("https://raw.githubusercontent.com/rocketjumper76/warframe-market-trader/main/src/api/warframe_market.py", "trader_api_py"),
    # Market trader models
    ("https://raw.githubusercontent.com/rocketjumper76/warframe-market-trader/main/src/models/item.py", "trader_item_py"),
]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        results = {}

        for url, label in FILES_TO_READ:
            print(f"\n=== {label} ===")
            print(f"URL: {url}")
            content = get_raw_content(page, url)
            print(content[:1500])
            results[label] = content

        with open("screenshots/source_code.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        browser.close()

if __name__ == "__main__":
    main()
