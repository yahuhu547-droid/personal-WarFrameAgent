from __future__ import annotations

from .models import FrameSample, VideoSource


class ExistingFrameCapture:
    def capture(
        self,
        source: VideoSource,
        *,
        frame_paths: list[str],
        timestamps: list[float] | None = None,
    ) -> list[FrameSample]:
        del source
        timestamps = timestamps or []
        frames = []
        for index, path in enumerate(frame_paths):
            timestamp = timestamps[index] if index < len(timestamps) else 0.0
            frames.append(FrameSample(path=path, timestamp_seconds=float(timestamp)))
        return frames
