from warframe_agent.video_analysis.frame_capture import ExistingFrameCapture
from warframe_agent.video_analysis.models import VideoSource


def test_existing_frame_capture_pairs_frames_and_timestamps():
    capture = ExistingFrameCapture()
    source = VideoSource.from_url("https://www.bilibili.com/video/BV1dJ5LzREZk")

    frames = capture.capture(source, frame_paths=["a.png", "b.png"], timestamps=[8, 13])

    assert frames[0].path == "a.png"
    assert frames[0].timestamp_seconds == 8
    assert frames[1].path == "b.png"
    assert frames[1].timestamp_seconds == 13
