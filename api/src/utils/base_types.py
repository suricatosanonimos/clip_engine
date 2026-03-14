# src/utils/base_types.py
"""
Shared type definitions to avoid circular imports.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class ClipMetadata:
    """Metadata for a video clip."""

    source_video: str
    start_time: float
    end_time: float
    duration: float
    title: str = ""
    score: int = 70
    face_tracking: bool = False
    stage: str = "raw"
    transcribed_at: Optional[datetime] = None
    has_subtitles: bool = False


@dataclass
class VideoInfo:
    """Video information."""

    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    size: int
    bitrate: str


class SubtitleGeneratorProtocol(Protocol):
    """Protocol for subtitle generator to avoid circular imports."""

    def process_raw_clip(
        self, clip_path: Path, custom_title: Optional[str] = None
    ) -> Optional[Path]:
        """Process a single raw clip."""
        ...

    def process_all_raw_clips(
        self, video_name: Optional[str] = None, max_workers: int = 1
    ) -> List[Path]:
        """Process all raw clips."""
        ...

    def get_clips_status(self) -> Dict[str, Any]:
        """Get clips status."""
        ...
