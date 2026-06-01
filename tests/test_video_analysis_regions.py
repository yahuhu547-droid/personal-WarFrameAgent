from warframe_agent.video_analysis.models import FrameSample
from warframe_agent.video_analysis.regions import FixedRegionLocator


def test_fixed_region_locator_projects_default_ratios_to_pixels():
    frame = FrameSample(path="frame.png", timestamp_seconds=29.0, width=1920, height=1080)

    regions = FixedRegionLocator().locate(frame)
    mod_grid = next(region for region in regions if region.kind == "mod_grid")

    assert mod_grid.box == [346, 238, 1574, 842]
    assert mod_grid.frame_path == "frame.png"
    assert 0 < mod_grid.confidence <= 1


def test_fixed_region_locator_uses_custom_ratios():
    frame = FrameSample(path="frame.png", timestamp_seconds=8.0, width=100, height=50)
    locator = FixedRegionLocator({"weapon_name": [0.1, 0.2, 0.5, 0.8]})

    assert locator.locate(frame)[0].box == [10, 10, 50, 40]
