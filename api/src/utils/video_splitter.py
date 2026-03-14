# src/utils/video_splitter.py
import subprocess
from pathlib import Path
from typing import List, Optional


class VideoSplitter:
    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir: Path = base_dir or Path("downloads")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_duration(self, video_path: Path) -> Optional[float]:
        # Get video duration using ffprobe
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            return float(result.stdout.strip())
        except Exception:
            return None

    def _safe_cut(
        self,
        input_path: Path,
        output_path: Path,
        start_seconds: float,
        duration_seconds: float,
    ) -> bool:

        # Re-encode to ensure proper keyframes and avoid corruption
        command = [
            "ffmpeg",
            "-ss",
            str(start_seconds),
            "-i",
            str(input_path),
            "-t",
            str(duration_seconds),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-y",
            str(output_path),
        ]

        try:
            subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return output_path.exists()
        except Exception:
            return False

    def split_video(self, video_path: str, num_parts: int = 4) -> List[str]:

        input_path: Path = Path(video_path)
        parts_created: List[str] = []

        if not input_path.exists():
            return []

        duration: Optional[float] = self._get_duration(input_path)

        if not duration or duration <= 0:
            return []

        part_duration: float = duration / num_parts

        base_name: str = input_path.stem
        extension: str = input_path.suffix

        for index in range(num_parts):
            start_time: float = index * part_duration

            output_name: str = f"{base_name}_part{index + 1}{extension}"
            output_path: Path = self.base_dir / output_name

            success: bool = self._safe_cut(
                input_path=input_path,
                output_path=output_path,
                start_seconds=start_time,
                duration_seconds=part_duration,
            )

            if success:
                parts_created.append(str(output_path))

        return parts_created
