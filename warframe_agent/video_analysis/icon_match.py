from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from .models import IconMatch

try:
    import imagehash
except Exception:
    imagehash = None


@dataclass(frozen=True)
class _IconEntry:
    label: str
    kind: str
    path: Path
    fingerprint: Any


class IconHashIndex:
    def __init__(self, entries: list[_IconEntry]) -> None:
        self.entries = entries

    @classmethod
    def from_directory(cls, directory: str | Path, *, kind: str) -> "IconHashIndex":
        entries = []
        for path in sorted(Path(directory).glob("*.png")):
            entries.append(_IconEntry(label=path.stem, kind=kind, path=path, fingerprint=_fingerprint(path)))
        return cls(entries)

    def match(self, image_path: str | Path, *, limit: int = 3) -> list[IconMatch]:
        query = _fingerprint(image_path)
        scored = []
        for entry in self.entries:
            score = _similarity(query, entry.fingerprint)
            scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            IconMatch(label=entry.label, kind=entry.kind, score=round(score, 3), source_icon=str(entry.path))
            for score, entry in scored[:limit]
        ]


def _fingerprint(image_path: str | Path) -> Any:
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        if imagehash is not None:
            return imagehash.phash(rgb)
        return rgb.resize((1, 1)).getpixel((0, 0))


def _similarity(left: Any, right: Any) -> float:
    if imagehash is not None:
        distance = left - right
        return max(0.0, 1.0 - distance / 64.0)
    distance = sum(abs(a - b) for a, b in zip(left, right))
    return max(0.0, 1.0 - distance / 765.0)
