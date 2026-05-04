"""Explore specific GitHub repos for useful features."""
from playwright.sync_api import sync_playwright
import json

def safe_goto(page, url, timeout=15000):
    try:
        page.goto(url, timeout=timeout, wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
    except:
        pass

def explore_repo_detail(page, url):
    safe_goto(page, url)
    readme = page.locator('article, .markdown-body, [data-testid="readme"]').first
    try:
        text = readme.inner_text()
    except:
        text = ""

    # Check for screenshots
    images = page.locator('.markdown-body img, article img').all()
    img_srcs = []
    for img in images[:5]:
        src = img.get_attribute('src') or ""
        if src:
            img_srcs.append(src)

    return text, img_srcs

def explore_api_endpoints(page, url):
    """Look for API endpoint definitions in source code."""
    safe_goto(page, url)
    # Try to find source files
    tree_url = url.rstrip('/') + "/find/main"
    safe_goto(page, tree_url)
    page.wait_for_timeout(1000)

    # Get file listing
    links = page.locator('a[href*=".py"], a[href*=".js"], a[href*=".ts"]').all()
    files = []
    for link in links[:20]:
        href = link.get_attribute('href') or ""
        text = link.inner_text()
        if text:
            files.append({"name": text, "href": href})
    return files

REPOS = [
    {
        "url": "https://github.com/Nathan47293/warframe-toolkit",
        "focus": "Mod Flipper - profitable Rank 10 mods to flip, arcane flipping, Cloudflare Worker CORS proxy",
        "features": ["mod_flipper", "arcane_flipper", "set_profit"]
    },
    {
        "url": "https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer",
        "focus": "Rank Prime sets by profit and 48-hour trading volume",
        "features": ["set_profit_ranking", "volume_tracking"]
    },
    {
        "url": "https://github.com/rocketjumper76/warframe-market-trader",
        "focus": "Real-time market analysis, ROI percentage, daily volume, budget filtering",
        "features": ["roi_calculation", "budget_filter", "volume_tracking"]
    },
    {
        "url": "https://github.com/GOTWIC/Riven-Sniper",
        "focus": "Riven sniping - finding underpriced rivens",
        "features": ["riven_snipe", "underpriced_detection"]
    },
    {
        "url": "https://github.com/Salil-Johri/warframe-market-discord-bot",
        "focus": "Discord bot for warframe.market - may have useful API patterns",
        "features": ["discord_integration", "api_patterns"]
    },
]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})

        all_data = []
        for repo in REPOS:
            url = repo['url']
            print(f"\n{'='*60}")
            print(f"Exploring: {url}")
            print(f"Focus: {repo['focus']}")
            print('='*60)

            text, images = explore_repo_detail(page, url)
            print(text[:800])

            # Try to find interesting source files
            files = explore_api_endpoints(page, url)
            if files:
                print(f"\nSource files found: {len(files)}")
                for f in files[:10]:
                    print(f"  - {f['name']}")

            all_data.append({
                "url": url,
                "focus": repo['focus'],
                "features": repo['features'],
                "readme": text,
                "images": images,
                "source_files": [f['name'] for f in files],
            })

        with open("screenshots/github_detailed.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

        browser.close()

if __name__ == "__main__":
    main()
