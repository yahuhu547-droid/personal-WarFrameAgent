from warframe_agent.video_analysis.models import DetectedRegion
from warframe_agent.video_analysis.ocr import FakeOcrEngine, PaddleOcrEngine


def test_fake_ocr_engine_returns_configured_region_text():
    region = DetectedRegion(kind="weapon_name", box=[0, 0, 10, 10], confidence=1, frame_path="frame.png")
    engine = FakeOcrEngine({"weapon_name": ["伯斯顿"]})

    candidates = engine.read_region("frame.png", region)

    assert candidates[0].text == "伯斯顿"
    assert candidates[0].region_kind == "weapon_name"
    assert candidates[0].frame_path == "frame.png"


def test_paddle_ocr_engine_can_be_disabled_without_dependency():
    engine = PaddleOcrEngine(enabled=False)

    assert engine.available is False
    assert engine.error == "disabled"


def test_paddle_ocr_engine_reports_missing_runtime_dependency():
    engine = PaddleOcrEngine(enabled=True)

    if not engine.available:
        assert engine.error
