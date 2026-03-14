# src/services/downloader.py  (modificado)

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import yt_dlp
from fastapi import BackgroundTasks, HTTPException, Response, status
from src.utils.video_splitter import VideoSplitter


class VideoDownloader:
    def __init__(self, output_dir: str = "clip_engine") -> None:
        self.output_dir = output_dir
        self.base_path = Path(self.output_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    # ... mantenha _sanitize_filename, _validate_url, _verify_video_integrity, _reencode_safe_mp4 como estão ...

    def _verify_video_integrity(self, file_path: str) -> bool:
        result: Optional[subprocess.CompletedProcess] = None

        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _reencode_safe_mp4(self, input_path: str) -> str:
        safe_path: str = input_path.replace(".mp4", "_safe.mp4")

        # Re-encode to guarantee proper keyframes and container integrity
        command: List[str] = [
            "ffmpeg",
            "-i",
            input_path,
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
            safe_path,
        ]

        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if self._verify_video_integrity(safe_path):
            os.replace(safe_path, input_path)

        return input_path

    def _validate_url(self, url: str) -> None:
        pattern: str = r"^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+$"

        if not re.match(pattern, url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid YouTube URL",
            )

    def _sanitize_filename(self, name: str) -> str:
        sanitized: str = name or "video"

        # Remove accents basic normalization
        sanitized = (
            sanitized.replace("á", "a")
            .replace("à", "a")
            .replace("ã", "a")
            .replace("â", "a")
            .replace("é", "e")
            .replace("ê", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ô", "o")
            .replace("õ", "o")
            .replace("ú", "u")
            .replace("ç", "c")
        )

        # Remove invalid characters
        sanitized = re.sub(r"[^\w\-\.]", "_", sanitized)

        # Collapse multiple underscores
        sanitized = re.sub(r"_+", "_", sanitized)

        sanitized = sanitized.strip("_")

        return sanitized or "video"

    def download_video(self, url: str, response: Response, num_parts: int = 4) -> Dict:

        self._validate_url(url)

        video_title: Optional[str] = None
        sanitized_title: Optional[str] = None
        output_template: Optional[str] = None
        final_filename: Optional[str] = None
        parts: List[str] = []

        try:
            # Extract metadata first
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get("title", "video")

            sanitized_title = self._sanitize_filename(video_title)
            output_template = str(self.base_path / f"{sanitized_title}.%(ext)s")

            ydl_opts = {
                "format": "bestvideo+bestaudio/best",
                "outtmpl": output_template,
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": True,
            }

            # Download video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                final_filename = ydl.prepare_filename(info)

            if not final_filename.endswith(".mp4"):
                base_name = final_filename.rsplit(".", 1)[0]
                final_filename = f"{base_name}.mp4"

            if not Path(final_filename).exists():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Download failed",
                )

            # Validate integrity
            if not self._verify_video_integrity(final_filename):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Corrupted video after download",
                )

            # Re-encode to ensure safe splitting
            final_filename = self._reencode_safe_mp4(final_filename)

            # Split video
            splitter: VideoSplitter = VideoSplitter()
            parts = splitter.split_video(
                video_path=final_filename, num_parts=num_parts
            )  # type: ignore

            if not parts or not isinstance(parts, list):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Video splitting failed",
                )

            # Remove original if parts created
            if all(Path(p).exists() for p in parts):
                os.remove(final_filename)

            response.status_code = status.HTTP_201_CREATED

            return {
                "status": "completed",
                "title": video_title,
                "file_parts": parts,
                "parts_count": len(parts),
                "output_dir": self.output_dir,
            }

        except HTTPException:
            raise

        except Exception as exc:
            logging.error(f"Download error: {str(exc)}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during video processing",
            )

    def download_and_split(
        self,
        url: str,
        num_parts: int = 4,
        task_id: str = "manual",  # pode virar UUID depois
    ) -> Dict:
        """Executa TODO o fluxo: download → valida → re-encode → split"""
        self._validate_url(url)

        try:
            # 1. Pegar título e definir nome
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get("title", "video")

            sanitized_title = self._sanitize_filename(video_title)
            output_template = str(self.base_path / f"{sanitized_title}.%(ext)s")

            # 2. Download completo
            ydl_opts = {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "outtmpl": output_template,
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": True,
                "continuedl": True,  # continua se interrompido
                "retries": 10,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                final_filename = ydl.prepare_filename(info)

            if not final_filename.lower().endswith(".mp4"):
                final_filename = final_filename.rsplit(".", 1)[0] + ".mp4"

            video_path = Path(final_filename)
            if not video_path.exists():
                raise RuntimeError("Arquivo não encontrado após download")

            # 3. Validar integridade
            if not self._verify_video_integrity(str(video_path)):
                raise RuntimeError("Vídeo corrompido após download")

            # 4. Re-encode seguro (garante keyframes para corte limpo)
            final_filename = self._reencode_safe_mp4(str(video_path))

            # 5. Só agora corta
            splitter = VideoSplitter()
            parts = splitter.split_video(video_path=final_filename, num_parts=num_parts)

            if not parts:
                raise RuntimeError("Falha ao dividir o vídeo")

            # 6. Opcional: remover original após sucesso
            if all(Path(p).exists() for p in parts):
                try:
                    os.remove(final_filename)
                except:
                    pass

            return {
                "status": "completed",
                "task_id": task_id,
                "title": video_title,
                "file_parts": parts,
                "parts_count": len(parts),
                "output_dir": self.output_dir,
            }

        except Exception as e:
            logging.error(
                f"Erro no processamento completo: {str(e)}",
                exc_info=True,
            )
            raise

    # Método auxiliar para background
    def process_in_background(
        self,
        url: str,
        num_parts: int,
        background_tasks: BackgroundTasks,
    ) -> str:
        import uuid

        task_id = str(uuid.uuid4())[:8]

        background_tasks.add_task(
            self.download_and_split,
            url=url,
            num_parts=num_parts,
            task_id=task_id,
        )
        return task_id
