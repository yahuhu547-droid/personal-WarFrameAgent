from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from warframe_agent.video_analysis.draft import ParsedBuildDraftBuilder
from warframe_agent.video_analysis.frame_capture import ExistingFrameCapture
from warframe_agent.video_analysis.models import VideoSource
from warframe_agent.video_analysis.ocr import FakeOcrEngine
from warframe_agent.video_analysis.regions import FixedRegionLocator
from warframe_agent.video_analysis.storage import JsonlDraftStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an untrusted Warframe Bilibili build parse draft.")
    parser.add_argument("url")
    parser.add_argument("--title", default="")
    parser.add_argument("--timestamp", type=float, action="append", default=[])
    parser.add_argument("--frame", action="append", default=[])
    parser.add_argument("--output", default="data/video_parse_drafts.jsonl")
    parser.add_argument("--fake-ocr-weapon", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = VideoSource.from_url(args.url)
    title = args.title or source.bvid
    frames = ExistingFrameCapture().capture(source, frame_paths=args.frame, timestamps=args.timestamp)
    regions = []
    for frame in frames:
        regions.extend(FixedRegionLocator().locate(frame))

    ocr_responses = {"weapon_name": [args.fake_ocr_weapon]} if args.fake_ocr_weapon else {}
    ocr_engine = FakeOcrEngine(ocr_responses)
    ocr_candidates = []
    for region in regions:
        ocr_candidates.extend(ocr_engine.read_region(region.frame_path, region))

    draft = ParsedBuildDraftBuilder().build(
        source=source,
        title=title,
        frames=frames,
        regions=regions,
        ocr_candidates=ocr_candidates,
        icon_matches=[],
    )
    JsonlDraftStore(args.output).append(draft)
    print(json.dumps({"bvid": source.bvid, "output": args.output, "needs_review": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
