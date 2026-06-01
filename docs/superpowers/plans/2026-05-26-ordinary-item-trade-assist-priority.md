# Step 15: Ordinary Item Trade Assist Priority

## Goal

Finish the remaining ordinary-item trade assist learning task by making direct market intents deterministic across normal and streaming chat paths, even when the user mixes market terms with Bilibili/video words.

## Borrowed Learning Points

- Intent priority should favor the most actionable user request. A trade request with "market link", "cheapest seller", or "bargain" should not be stolen by adjacent guide/video keywords.
- The streaming path should be covered by tests whenever it mirrors the normal chat path.
- Direct market link responses should avoid order fetching; cheapest seller and bargain responses may fetch orders and should include seller, whisper, and market URL.

## TDD Plan

1. Add failing tests in `tests/test_chat.py`.
   - `test_direct_market_intent_takes_precedence_over_bilibili_video_words_when_market_requested`
   - `test_generic_cheapest_seller_intent_wins_when_link_is_also_requested`
   - `test_answer_stream_generic_market_link_intent_returns_url_without_fetching_orders`
   - `test_answer_stream_generic_cheapest_seller_intent_returns_whisper_and_link`
2. Run the focused red test command.
   - `.\.venv\Scripts\python.exe -m pytest tests/test_chat.py -k "direct_market_intent_takes_precedence_over_bilibili_video_words_when_market_requested or answer_stream_generic_market_link_intent_returns_url_without_fetching_orders or answer_stream_generic_cheapest_seller_intent_returns_whisper_and_link" -q`
3. Update `warframe_agent/chat.py` so direct market intents run before direct Bilibili recommendation intents in both `answer` and `answer_stream`, while keeping Prime Resurgence ahead of item-market matching.
4. Rerun the focused tests and the existing market/Bilibili guard tests.
5. Sync the learning notes into `githubProduct` and `md/rebuilt`.

## Verification

- Focused tests for the new behavior.
- Existing chat tests around market link, cheapest seller, bargain, and Bilibili routing.
- AST parse for changed Python files.
- `git diff --check` for changed files.

## Result

- Red tests confirmed two gaps: Bilibili/video words could preempt an explicit market link request, and "cheapest seller + market link" returned only the link.
- Implementation now routes direct market intents before direct Bilibili recommendations and lets seller/bargain intents outrank plain link responses.
- Focused tests passed: `4 passed`.
- Market/Bilibili guard tests passed: `16 passed`.
