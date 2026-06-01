from __future__ import annotations

import json
from pathlib import Path

from .models import ParsedBuildDraft


class JsonlDraftStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, draft: ParsedBuildDraft) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(draft.to_dict(), ensure_ascii=False) + "\n")
