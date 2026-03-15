# src/services/downloader.py

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import yt_dlp
from fastapi import BackgroundTasks, HTTPException, Response, status

from src.utils.video_splitter import VideoSplitter

logger = logging.getLogger(__name__)


class VideoDownloader:
    def __init__(self, output_dir: str = "clip_engine") -> None:
        self.output_dir = output_dir
        self.base_path  = Path(self.output_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────────────
    #  HELPERS
    # ──────────────────────────────────────────────────────────────

    def _sanitize_filename(self, name: str) -> str:
        s = name or "video"
        s = (
            s.replace("á","a").replace("à","a").replace("ã","a").replace("â","a")
             .replace("é","e").replace("ê","e").replace("í","i")
             .replace("ó","o").replace("ô","o").replace("õ","o")
             .replace("ú","u").replace("ç","c")
        )
        s = re.sub(r"[^\w\-\.]", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s or "video"

    def _validate_url(self, url: str) -> None:
        """Aceita URLs do YouTube e URLs assinadas do Supabase Storage."""
        yt      = r"^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+"
        supa    = r"^https?://.+\.supabase\.co/.+"
        if re.match(yt, url) or re.match(supa, url):
            return
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL inválida. Use uma URL do YouTube ou URL assinada do Supabase Storage.",
        )

    # ──────────────────────────────────────────────────────────────
    #  SELETOR DE FORMATO — garante H264 / AVC
    #
    #  O yt-dlp escolhe por preferência decrescente:
    #
    #  1. bestvideo[vcodec^=avc1] — H264 puro, melhor resolução
    #     + bestaudio[ext=m4a]
    #
    #  2. bestvideo[vcodec^=avc1] + bestaudio/best
    #     (fallback se m4a não disponível)
    #
    #  3. bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=vp9]
    #     + bestaudio[ext=m4a]
    #     (MP4 que não seja AV1 nem VP9)
    #
    #  4. best[ext=mp4][vcodec!*=av01][vcodec!*=vp9]
    #     (stream única, não AV1/VP9)
    #
    #  5. best — último recurso, qualquer formato
    #     → neste caso _garantir_compatibilidade() no VideoProcessor
    #       fará a conversão necessária como último recurso.
    #
    #  vcodec^=avc1 → começa com "avc1" (H.264 / AVC)
    #  vcodec!*=av01 → não contém "av01" (AV1)
    #  vcodec!*=vp9  → não contém "vp9"
    # ──────────────────────────────────────────────────────────────

    FORMAT_H264 = "/".join([
        "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]",
        "bestvideo[vcodec^=avc1]+bestaudio",
        "bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=vp9]+bestaudio[ext=m4a]",
        "best[ext=mp4][vcodec!*=av01][vcodec!*=vp9]",
        "best",
    ])

    # ──────────────────────────────────────────────────────────────
    #  DOWNLOAD PRINCIPAL
    # ──────────────────────────────────────────────────────────────

    def download_and_split(
        self,
        url:       str,
        num_parts: int = 1,
        task_id:   str = "manual",
    ) -> Dict:
        """
        Baixa o vídeo em H264 diretamente, sem re-encode.
        Se o YouTube só tiver AV1/VP9, cai no último fallback "best"
        e o VideoProcessor fará a conversão necessária.
        """
        self._validate_url(url)

        try:
            # 1. Extrai título sem baixar
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                meta        = ydl.extract_info(url, download=False)
                video_title = meta.get("title", "video")

            sanitized_title = self._sanitize_filename(video_title)
            output_template = str(self.base_path / f"{sanitized_title}.%(ext)s")

            # 2. Download forçando H264
            ydl_opts = {
                "format":              self.FORMAT_H264,
                "outtmpl":             output_template,
                "merge_output_format": "mp4",
                "noplaylist":          True,
                "quiet":               False,      # mostra progresso no log
                "continuedl":          True,
                "retries":             10,
                # Pós-processamento: garante que o container final é MP4
                "postprocessors": [{
                    "key":              "FFmpegVideoConvertor",
                    "preferedformat":   "mp4",
                }],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info           = ydl.extract_info(url, download=True)
                final_filename = ydl.prepare_filename(info)

            # Garante extensão .mp4
            if not final_filename.lower().endswith(".mp4"):
                final_filename = final_filename.rsplit(".", 1)[0] + ".mp4"

            video_path = Path(final_filename)
            if not video_path.exists():
                # Às vezes o pós-processador gera com nome diferente — busca
                mp4s = sorted(self.base_path.glob(f"{sanitized_title}*.mp4"),
                              key=lambda p: p.stat().st_mtime, reverse=True)
                if mp4s:
                    video_path = mp4s[0]
                else:
                    raise RuntimeError(f"Arquivo não encontrado após download: {final_filename}")

            logger.info(f"Download concluído: {video_path.name} "
                        f"({video_path.stat().st_size / 1024 / 1024:.1f} MB)")

            # 3. Divide em partes se necessário (padrão = 1 → arquivo inteiro)
            if num_parts <= 1:
                parts = [str(video_path)]
            else:
                splitter = VideoSplitter()
                parts    = splitter.split_video(
                    video_path=str(video_path), num_parts=num_parts
                )
                if not parts:
                    raise RuntimeError("Falha ao dividir o vídeo.")
                if all(Path(p).exists() for p in parts):
                    try:
                        os.remove(str(video_path))
                    except Exception:
                        pass

            return {
                "status":      "completed",
                "task_id":     task_id,
                "title":       video_title,
                "file_parts":  parts,
                "parts_count": len(parts),
                "output_dir":  self.output_dir,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro no download: {e}", exc_info=True)
            raise

    # ──────────────────────────────────────────────────────────────
    #  COMPATIBILIDADE — rota legada
    # ──────────────────────────────────────────────────────────────

    def download_video(self, url: str, response: Response, num_parts: int = 1) -> Dict:
        resultado = self.download_and_split(url=url, num_parts=num_parts)
        response.status_code = status.HTTP_201_CREATED
        return resultado

    # ──────────────────────────────────────────────────────────────
    #  BACKGROUND
    # ──────────────────────────────────────────────────────────────

    def process_in_background(
        self,
        url:              str,
        num_parts:        int,
        background_tasks: BackgroundTasks,
    ) -> str:
        task_id = str(uuid.uuid4())[:8]
        background_tasks.add_task(
            self.download_and_split,
            url=url,
            num_parts=num_parts,
            task_id=task_id,
        )
        return task_id
