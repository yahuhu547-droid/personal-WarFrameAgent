# Warframe Bilibili Guide Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Warframe/战甲 Bilibili video-link library so questions like “伏特配卡”“但丁攻略”“Mesa 怎么配卡视频” return suitable current or high-confidence guide videos.

**Architecture:** Reuse the existing Bilibili recommendation pipeline. Playwright gathers Bilibili search metadata into `Extra Resource/exports/bilibili_metadata/`; `tools/build_bilibili_recommendations.py` converts confirmed warframe video metadata into `category: warframe` records in `data/bilibili_recommendations.json`; `warframe_agent/bilibili_recommendations.py` performs deterministic matching and ranking. Only video metadata is trusted; MODs, builds, helminth choices, archon shards, and playstyle claims remain out of scope unless manually confirmed later.

**Tech Stack:** Python, pytest, Playwright/browser metadata collection, local JSON files, existing `BilibiliRecommendationService`.

---

## File Map

- Modify: `tools/build_bilibili_recommendations.py`
  - Add warframe-title extraction similar to the existing companion import branch.
  - Generate `warframes`, `aliases`, `category: warframe`, `priority`, `updated_at`, `source`, and `collection_category`.
- Modify: `warframe_agent/bilibili_recommendations.py`
  - Keep specific-warframe matching strict, like companion matching: specific queries must hit `warframes` or concrete aliases, not only `category: warframe`.
  - Preserve generic “战甲攻略视频” category recommendations.
- Modify: `tests/test_build_bilibili_recommendations.py`
  - Cover final warframe search-result import and priority ordering.
- Modify: `tests/test_bilibili_recommendations.py`
  - Cover specific warframe matching, generic warframe category queries, and no cross-category pollution.
- Modify: `tests/test_chat.py`
  - Cover direct chat answers for warframe build-video questions.
- Create: `Extra Resource/exports/bilibili_metadata/warframe_search_results.json`
  - Raw Playwright/Bilibili search metadata.
- Create: `Extra Resource/exports/bilibili_metadata/warframe_build_links_curated.json`
  - Human/pragmatic filtered candidate list.
- Create: `Extra Resource/exports/bilibili_metadata/warframe_build_links_final.json`
  - Final approved video metadata list to import.
- Create: `Extra Resource/exports/bilibili_metadata/warframe_build_import_report.json`
  - Import report.
- Create: `Extra Resource/exports/bilibili_metadata/warframe_build_recommendation_candidates.json`
  - Generated records for inspection.
- Create: `Extra Resource/exports/bilibili_metadata/warframe_build_recommendation_review_summary.json`
  - Review summary.
- Update: `md/rebuilt/02-feature-scope.md`, `md/rebuilt/05-data-memory.md`, `md/rebuilt/06-tools-models-safety.md`, `md/rebuilt/07-operations-testing.md`
  - Document warframe video metadata collection/import boundaries.

## Search Scope

Use Bilibili search through Playwright. Do not scrape or infer actual mod configurations. Collect only:

- `query`
- `bvid`
- `url`
- `title`
- optional `author`, `view_count`, `publish_text`, `duration` if easily available from the search page

Start with high-value/common warframe queries instead of all warframes at once:

- Generic: `Warframe 战甲 配卡`, `星际战甲 战甲 攻略`, `Warframe 战甲 build`
- Common frames: `伏特 配卡`, `但丁 配卡`, `Mesa 配卡`, `Saryn 配卡`, `Wisp 配卡`, `Revenant 配卡`, `Nekros 配卡`, `Khora 配卡`, `Gauss 配卡`, `Nova 配卡`, `Rhino 配卡`, `Octavia 配卡`, `Protea 配卡`, `Xaku 配卡`, `Citrine 配卡`, `Kullervo 配卡`, `Jade 配卡`, `Qorvex 配卡`, `Lavos 配卡`, `Titania 配卡`, `Mirage 配卡`, `Hildryn 配卡`, `Baruuk 配卡`, `Mag 配卡`, `Excalibur 配卡`, `Limbo 配卡`
- Chinese aliases should be included when known: `电男`, `毒妈`, `奶妈`, `女枪`, `猴子`, `龙甲`, `摸尸`, `牛`, `高斯`, `弥撒`, `伏特`, `蛆甲`, `沙甲`

Stop condition for the first pass:

- At least 40-80 high-confidence warframe guide links.
- At least one useful result for the most common user-facing aliases.
- No `needs_review: true` records loaded into user answers.

## Task 1: Add Warframe Import Tests

**Files:**
- Modify: `tests/test_build_bilibili_recommendations.py`

- [ ] **Step 1: Write failing test for final warframe links import**

Add a test with a temporary `warframe_build_links_final.json` containing records like:

```python
{
    "query": "Warframe 伏特 配卡",
    "bvid": "BVVOLT2025",
    "url": "https://www.bilibili.com/video/BVVOLT2025/",
    "title": "【星际战甲】2025伏特Volt最新配卡攻略，日常/速刷/圣殿",
}
```

Expected:

- `append_approved=True` appends the record.
- Loaded record has `category == "warframe"`.
- `warframes` contains `["Volt", "伏特", "电男"]` or the chosen canonical list.
- `aliases` contains `伏特配卡`, `Volt build`, `电男攻略`.
- `needs_review is False`.

- [ ] **Step 2: Run red test**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests\test_build_bilibili_recommendations.py::test_append_approved_imports_warframe_final_links -q
```

Expected: FAIL because warframe final-link import does not exist yet.

## Task 2: Implement Warframe Metadata Extraction

**Files:**
- Modify: `tools/build_bilibili_recommendations.py`

- [ ] **Step 1: Add a warframe alias map**

Add a conservative `KNOWN_WARFRAME_ALIASES` dictionary. Include canonical English, common Chinese name, and common nicknames. Keep it editable and small for the first pass.

Initial entries:

```python
KNOWN_WARFRAME_ALIASES = {
    "Volt": ["Volt", "伏特", "电男"],
    "Dante": ["Dante", "但丁"],
    "Mesa": ["Mesa", "弥撒", "女枪"],
    "Saryn": ["Saryn", "毒妈"],
    "Wisp": ["Wisp", "花妹"],
    "Revenant": ["Revenant", "吸血鬼"],
    "Nekros": ["Nekros", "摸尸", "摸尸甲"],
    "Khora": ["Khora", "猫甲"],
    "Gauss": ["Gauss", "高斯"],
    "Nova": ["Nova", "诺娃"],
    "Rhino": ["Rhino", "牛", "牛甲"],
    "Octavia": ["Octavia", "DJ"],
    "Protea": ["Protea", "普洛忒娅"],
    "Xaku": ["Xaku"],
    "Citrine": ["Citrine"],
    "Kullervo": ["Kullervo"],
    "Jade": ["Jade"],
    "Qorvex": ["Qorvex"],
    "Lavos": ["Lavos"],
    "Titania": ["Titania", "蝶妹"],
    "Mirage": ["Mirage", "小丑"],
    "Hildryn": ["Hildryn", "盾娘"],
    "Baruuk": ["Baruuk"],
    "Mag": ["Mag", "磁妹"],
    "Excalibur": ["Excalibur", "咖喱"],
    "Limbo": ["Limbo"],
}
```

- [ ] **Step 2: Add `_extract_warframe_mapping(item, source_category)`**

Rules:

- If `_source_category == "warframe"` or query/title contains `战甲`, `甲`, `Warframe`, `配卡`, `攻略`, inspect title/query for alias hits.
- If one or more concrete warframes match, return `{"category": "warframe", "warframes": [...]}`.
- If only generic “战甲攻略/战甲配卡” is present and no concrete frame matches, return `{"category": "warframe", "warframes": ["战甲"]}` only for final curated source files, not broad unreviewed candidate files.
- Do not infer mod names, subsume builds, archon shards, or helminth.

- [ ] **Step 3: Add `_aliases_for_warframes(warframes)`**

For each known alias:

- `<alias>`
- `<alias>配卡`
- `<alias>攻略`
- `<alias>教程`
- `<alias> build` for ASCII aliases

Only add generic `战甲配卡` / `战甲攻略` when `warframes == ["战甲"]`.

- [ ] **Step 4: Update `_make_record`**

Add `warframes = list(metadata.get("warframes") or [])`.

Output record must include:

```python
"warframes": warframes,
"weapons": weapons,
"companions": companions,
"category": category,
"summary": "...战甲配卡/攻略参考视频。",
```

Priority rule:

- Base 50.
- `+20` for title containing `2025`, `最新`, `现版本`, `新版本`, `当前版本`, `T0`, `详细`, `教程详解`.
- `+10` for specific single-warframe videos.
- `-10` for `合集`, `排行`, `梯度`.

- [ ] **Step 5: Run green test**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests\test_build_bilibili_recommendations.py::test_append_approved_imports_warframe_final_links -q
```

Expected: PASS.

## Task 3: Tighten Recommendation Matching for Warframes

**Files:**
- Modify: `tests/test_bilibili_recommendations.py`
- Modify: `warframe_agent/bilibili_recommendations.py`

- [ ] **Step 1: Add tests**

Add tests for:

- `伏特配卡` returns Volt record.
- `电男攻略` returns Volt record.
- `推荐战甲攻略视频` returns only `category: warframe` records.
- `伏特配卡` does not return a generic `战甲` record above a concrete Volt record.
- `Mesa 配卡` does not return Saryn just because both are warframes.

- [ ] **Step 2: Run red tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests\test_bilibili_recommendations.py -q
```

Expected: New warframe-specific tests fail until service and data format are aligned.

- [ ] **Step 3: Update scoring if needed**

Keep current rule:

- If query has concrete item terms, require an entity match from `aliases`, `weapons`, `warframes`, or `companions`.
- Category-only match is allowed only for generic queries after removing guide/category/request tokens.

Extend generic token handling if `推荐战甲攻略视频` is misclassified as a specific query.

- [ ] **Step 4: Run green tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests\test_bilibili_recommendations.py -q
```

Expected: PASS.

## Task 4: Gather Bilibili Warframe Search Metadata with Playwright

**Files:**
- Create: `Extra Resource/exports/bilibili_metadata/warframe_search_results.json`

- [ ] **Step 1: Start from a disposable Playwright script or REPL**

Use the existing browser profile only if login/cookies are required and safe. Keep output to JSON.

Suggested extraction schema:

```json
[
  {
    "query": "Warframe 伏特 配卡",
    "bvid": "BV...",
    "url": "https://www.bilibili.com/video/BV.../",
    "title": "...",
    "author": "...",
    "view_text": "...",
    "publish_text": "..."
  }
]
```

- [ ] **Step 2: Search each query**

For each query, capture the top 5-10 results from Bilibili search.

Search query pattern:

```text
Warframe <name_or_alias> 配卡
星际战甲 <name_or_alias> 攻略
<name_or_alias> 最新配卡
```

- [ ] **Step 3: Deduplicate by BVID**

Write a stable JSON array sorted by first-seen order. Preserve all search queries that found the video if feasible.

- [ ] **Step 4: Manual sanity filter**

Remove:

- Non-Warframe videos.
- Pure news, memes, giveaways, patch note discussion without build/guide value.
- Videos where title clearly belongs to weapons, companions, market, or unrelated tasks.
- Records with no BVID or invalid Bilibili video URL.

Save filtered output as:

```text
Extra Resource/exports/bilibili_metadata/warframe_build_links_curated.json
```

- [ ] **Step 5: Final selection**

From curated output, keep the best links per frame:

- Prefer title containing `最新`, `2025`, `现版本`, `详细`, `T0`, `攻略`, `配卡`.
- Prefer specific single-frame videos over generic合集 for specific frame names.
- Keep a few high-quality合集 for generic “战甲攻略视频”.

Save as:

```text
Extra Resource/exports/bilibili_metadata/warframe_build_links_final.json
```

## Task 5: Import Final Warframe Links

**Files:**
- Modify: `data/bilibili_recommendations.json`
- Create: `Extra Resource/exports/bilibili_metadata/warframe_build_import_report.json`
- Create: `Extra Resource/exports/bilibili_metadata/warframe_build_recommendation_candidates.json`
- Create: `Extra Resource/exports/bilibili_metadata/warframe_build_recommendation_review_summary.json`

- [ ] **Step 1: Run import**

```bash
.\.venv\Scripts\python.exe tools\build_bilibili_recommendations.py `
  --source "Extra Resource\exports\bilibili_metadata\warframe_build_links_final.json" `
  --report "Extra Resource\exports\bilibili_metadata\warframe_build_import_report.json" `
  --candidates "Extra Resource\exports\bilibili_metadata\warframe_build_recommendation_candidates.json" `
  --review-summary "Extra Resource\exports\bilibili_metadata\warframe_build_recommendation_review_summary.json" `
  --append-approved
```

Expected:

- `source_candidate_count` equals final source count.
- `auto_approved_new_count` equals final source count minus already-approved BVIDs.
- `needs_review_new_count == 0` for the final hand-curated file.

- [ ] **Step 2: Inspect imported records**

Run:

```bash
python -c "import json; data=json.load(open('data/bilibili_recommendations.json',encoding='utf-8')); rows=[x for x in data if x.get('category')=='warframe']; print(len(rows)); [print(x.get('bvid'), x.get('warframes'), x.get('priority'), x.get('title')[:60]) for x in rows[-30:]]"
```

Expected:

- New records have non-empty `warframes`.
- Specific records do not use generic `战甲配卡` aliases unless they are truly generic warframe records.

## Task 6: Chat-Level Verification

**Files:**
- Modify: `tests/test_chat.py`

- [ ] **Step 1: Add chat tests**

Cover:

- `伏特配卡` returns Volt Bilibili links.
- `电男攻略视频` returns Volt Bilibili links.
- `推荐战甲攻略视频` returns generic warframe/category results.
- Price/market questions do not append warframe videos.

- [ ] **Step 2: Run tests**

```bash
.\.venv\Scripts\python.exe -m pytest tests\test_chat.py tests\test_bilibili_recommendations.py tests\test_build_bilibili_recommendations.py -q
```

Expected: PASS.

## Task 7: Documentation Update

**Files:**
- Modify: `md/rebuilt/02-feature-scope.md`
- Modify: `md/rebuilt/05-data-memory.md`
- Modify: `md/rebuilt/06-tools-models-safety.md`
- Modify: `md/rebuilt/07-operations-testing.md`

- [ ] **Step 1: Update feature scope**

Mention warframe-specific Bilibili recommendation support:

- specific warframe names/aliases
- generic warframe category questions
- strict metadata-only trust boundary

- [ ] **Step 2: Update data/memory docs**

Add:

- `warframe_build_links_final.json`
- `warframe_build_import_report.json`
- generated candidate/review files
- `warframes` field semantics

- [ ] **Step 3: Update operations/testing docs**

Add the exact import command and verification command.

## Final Verification Checklist

- [ ] `warframe_build_links_final.json` exists and contains only Bilibili video metadata.
- [ ] Import report says `needs_review_new_count == 0`.
- [ ] `data/bilibili_recommendations.json` contains new `category: warframe` records.
- [ ] Query `伏特配卡` returns a specific Volt/伏特 result above generic warframe合集.
- [ ] Query `电男攻略视频` returns a specific Volt/伏特 result.
- [ ] Query `推荐战甲攻略视频` returns warframe category videos.
- [ ] Query `铁甲狐配卡` still returns companion results, not warframe results.
- [ ] Query `托里德配卡` still returns weapon results.
- [ ] Tests pass:

```bash
.\.venv\Scripts\python.exe -m pytest tests\test_bilibili_recommendations.py tests\test_build_bilibili_recommendations.py tests\test_chat.py -q
```
