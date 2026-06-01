# Step 43: Multi-Channel Gateway Boundary

## Route

- Source projects: CowAgent / Suna / OpenClaw.
- Borrowed idea: personal agents often have multiple user entrypoints and notification exits, but each channel needs an explicit trust and action boundary.
- Warframe mapping: describe allowed chat entrypoints, configured outbound push, and blocked public or anonymous gateways as a read-only runtime policy.
- Safety boundary: no new platform connector, no webhook executor, no anonymous inbound command execution, no Browser/GUI executor, no voice/TTS/STT/mic/Live2D work.
- Verification: TDD unit tests for gateway classification plus runtime policy embedding.

## Completion Criteria

1. A new `warframe_agent.gateway_policy` module classifies gateway channel/action pairs without echoing raw secrets.
2. `build_runtime_safety_policy(...)` exposes a read-only `gateway_policy` and a `multi_channel_gateway` capability summary.
3. Public social comments, anonymous webhooks, seller/buyer DMs, arbitrary tools, shell, browser control, and file writes are blocked by policy.
4. Web chat, WebSocket chat, and local CLI are treated as interactive user input; configured Feishu inbound is constrained to existing confirmation flows; WxPusher/Feishu push remain outbound notification surfaces.
5. `AGENTS.md`, route ledger, and `md/rebuilt` record Step 43 after implementation.

## Test Plan

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gateway_policy.py tests\test_tool_registry.py -k "gateway_policy or runtime_safety_policy_embeds_tool_registry_summary_without_tool_details" -q --basetemp .pytest-tmp -p no:cacheprovider
.\.venv\Scripts\python.exe -B -c "import ast, pathlib; files=['warframe_agent/gateway_policy.py','warframe_agent/safety_policy.py']; [ast.parse(pathlib.Path(path).read_text(encoding='utf-8')) for path in files]; print('AST OK')"
```

## Tasks

1. Write red tests for gateway classification, redaction, snapshot shape, and runtime policy embedding.
2. Implement `gateway_policy.py` with conservative allow/confirm/block decisions.
3. Integrate policy into `safety_policy.py`.
4. Update learning documents and `AGENTS.md`.
5. Run targeted verification and diff check.
