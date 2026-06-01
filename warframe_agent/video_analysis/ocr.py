from __future__ import annotations

from .models import DetectedRegion, OcrCandidate


class FakeOcrEngine:
    def __init__(self, responses: dict[str, list[str]] | None = None) -> None:
        self.responses = responses or {}

    def read_region(self, image_path: str, region: DetectedRegion) -> list[OcrCandidate]:
        return [
            OcrCandidate(text=text, region_kind=region.kind, confidence=0.99, frame_path=image_path)
            for text in self.responses.get(region.kind, [])
        ]


class PaddleOcrEngine:
    def __init__(self, *, lang: str = "ch", enabled: bool = True) -> None:
        self.lang = lang
        self._ocr = None
        self.error = "disabled"
        if enabled:
            try:
                import paddle  # noqa: F401
                from paddleocr import PaddleOCR

                self._ocr = PaddleOCR(lang=lang, use_angle_cls=True)
                self.error = ""
            except Exception as exc:
                self._ocr = None
                self.error = repr(exc)

    @property
    def available(self) -> bool:
        return self._ocr is not None

    def read_region(self, image_path: str, region: DetectedRegion) -> list[OcrCandidate]:
        if self._ocr is None:
            return []
        raw = self._ocr.ocr(image_path, cls=True)
        candidates: list[OcrCandidate] = []
        for page in raw or []:
            for item in page or []:
                text = item[1][0] if len(item) > 1 and item[1] else ""
                confidence = float(item[1][1]) if len(item) > 1 and item[1] and len(item[1]) > 1 else 0.0
                if text:
                    candidates.append(
                        OcrCandidate(text=text, region_kind=region.kind, confidence=confidence, frame_path=image_path)
                    )
        return candidates
