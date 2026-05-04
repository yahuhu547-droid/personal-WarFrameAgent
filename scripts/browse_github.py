"""Browse GitHub for Warframe trading projects with interesting features."""
from playwright.sync_api import sync_playwright
import json

def safe_goto(page, url, timeout=15000):
    try:
        page.goto(url, timeout=timeout, wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
    except:
        pass

def search_github(page, query):
    url = f"https://github.com/search?q={query}&type=repositories&s=stars&o=desc"
    safe_goto(page, url)
    page.screenshot(path=f"screenshots/github_search.png", full_page=False)

    results = []
    items = page.locator('a[data-testid="results-repo-url"], .search-title a, h3 a[href*="/"]').all()
    for item in items[:10]:
        try:
            href = item.get_attribute('href') or ""
            text = item.inner_text()
            if href and '/' in href and text.strip():
                results.append({"name": text.strip(), "url": f"https://github.com{href}" if not href.startswith('http') else href})
        except:
            continue
    return results

def explore_repo(page, url):
    safe_goto(page, url)
    page.screenshot(path=f"screenshots/repo_{url.split('/')[-1][:20]}.png", full_page=False)
    readme = page.locator('article, .markdown-body, [data-testid="readme"]').first
    try:
        return readme.inner_text()[:3000]
    except:
        return "Could not read README"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})

        queries = [
            "warframe+trading+tool",
            "warframe+price+checker",
            "warframe+market+discord+bot",
            "warframe+riven+calculator",
        ]

        all_repos = []
        for q in queries:
            print(f"\n=== Searching: {q} ===")
            results = search_github(page, q)
            for r in results:
                print(f"  {r['url']}")
                if r['url'] not in [x['url'] for x in all_repos]:
                    all_repos.append(r)

        # Explore top unique repos
        print(f"\n=== Exploring top {min(8, len(all_repos))} repos ===")
        detailed = []
        for repo in all_repos[:8]:
            url = repo['url']
            print(f"\n--- {url} ---")
            readme = explore_repo(page, url)
            print(readme[:400])
            detailed.append({"url": url, "name": repo['name'], "readme": readme})

        with open("screenshots/github_research.json", "w", encoding="utf-8") as f:
            json.dump(detailed, f, ensure_ascii=False, indent=2)

        browser.close()
        print("\nDone!")

if __name__ == "__main__":
    main()
