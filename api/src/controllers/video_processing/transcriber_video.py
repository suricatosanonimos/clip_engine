import subprocess
from pathlib import Path
from typing import Optional

from src.services.transcriber import SubtitleGenerator
from src.utils.time_log import time_for_logs


class TranscriberVideo:
    def __init__(self, video_path: Path):
        self.video_path = video_path
        # Inicializa com lazy_load=True para não carregar Whisper desnecessariamente
        self.subtitle_generator = SubtitleGenerator(lazy_load=True)

    def extract_audio(self) -> Optional[Path]:
        audio_path = self.video_path.with_suffix(".wav")
        cmd = [
            "ffmpeg",
            "-i",
            str(self.video_path),
            "-q:a",
            "0",
            "-map",
            "a",
            "-y",
            str(audio_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return audio_path if audio_path.exists() else None
        except subprocess.CalledProcessError as e:
            print(f"{time_for_logs()} Erro ao extrair áudio: {e}")
            return None

    def cleanup_audio(self, audio_path: Path):
        if audio_path.exists():
            audio_path.unlink()
