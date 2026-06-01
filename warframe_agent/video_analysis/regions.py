from __future__ import annotations

from .models import DetectedRegion, FrameSample

_DEFAULT_REGION_RATIOS = {
    "weapon_name": [0.05, 0.05, 0.35, 0.15],
    "mod_grid": [0.18, 0.22, 0.82, 0.78],
    "arcane_slots": [0.78, 0.18, 0.96, 0.42],
    "exilus_slot": [0.04, 0.28, 0.18, 0.48],
    "incarnon_choices": [0.12, 0.12, 0.88, 0.88],
}


class FixedRegionLocator:
    def __init__(self, region_ratios: dict[str, list[float]] | None = None) -> None:
        self.region_ratios = region_ratios or _DEFAULT_REGION_RATIOS

    def locate(self, frame: FrameSample) -> list[DetectedRegion]:
        width = frame.width or 1920
        height = frame.height or 1080
        regions = []
        for kind, ratios in self.region_ratios.items():
            x1, y1, x2, y2 = ratios
            regions.append(
                DetectedRegion(
                    kind=kind,
                    box=[round(x1 * width), round(y1 * height), round(x2 * width), round(y2 * height)],
                    confidence=0.5,
                    frame_path=frame.path,
                )
            )
        return regions
