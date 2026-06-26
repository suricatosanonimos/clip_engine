# src/services/downloader.py

import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import yt_dlp
from fastapi import BackgroundTasks, HTTPException, Response, status

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.utils.video_splitter import VideoSplitterFast

logger = logging.getLogger(__name__)


class VideoDownloader:
    """
    Downloader de vídeos com suporte a:
    - Corte em clipes uniformes
    - Extração de gancho via IA (sem duplicar conteúdo)
    - Pipeline completo (clipes + gancho)
    - Verifica se vídeo já foi baixado (evita re-download)
    """

    def __init__(self, output_dir=Path(f"{BASE_DIR}/downloads/")) -> None:
        self.output_dir = output_dir
        self.base_path = Path(self.output_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.raw_clips_dir = Path(f"{BASE_DIR}/processed_videos/raw_clips/")
        self.raw_clips_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"📁 Download dir: {self.base_path}")
        logger.info(f"📁 Raw clips dir: {self.raw_clips_dir}")

    # ── HELPERS ──

    def _sanitize_filename(self, name: str) -> str:
        s = name or "video"
        s = (
            s.replace("á", "a")
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
        s = re.sub(r"[^\w\-\.]", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s or "video"

    def _validate_url(self, url: str) -> None:
        yt = r"^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+"
        supa = r"^https?://.+\.supabase\.co/.+"
        if re.match(yt, url) or re.match(supa, url):
            return
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="URL inválida."
        )

    FORMAT_H264 = "/".join(
        [
            "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]",
            "bestvideo[vcodec^=avc1]+bestaudio",
            "bestvideo[ext=mp4][vcodec!*=av01][vcodec!*=vp9]+bestaudio[ext=m4a]",
            "best[ext=mp4][vcodec!*=av01][vcodec!*=vp9]",
            "best",
        ]
    )

    def _configure_splitter(
        self, output_format="9:16", crop_mode="center"
    ) -> VideoSplitterFast:
        return VideoSplitterFast(
            base_dir=self.raw_clips_dir,
            output_format=output_format,
            crop_mode=crop_mode,
            num_threads=2,
        )

    def _download_video(self, url: str) -> tuple:
        """Baixa o vídeo ou retorna caminho se já existir."""
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            meta = ydl.extract_info(url, download=False)
            video_title = meta.get("title", "video")

        sanitized = self._sanitize_filename(video_title)
        expected_path = self.base_path / f"{sanitized}.mp4"

        # Verifica se já existe
        if expected_path.exists() and expected_path.stat().st_size > 0:
            logger.info(
                f"✅ Vídeo já baixado: {expected_path.name} ({expected_path.stat().st_size/1024/1024:.1f} MB)"
            )
            return expected_path, video_title

        # Download
        output_template = str(self.base_path / f"{sanitized}.%(ext)s")
        logger.info(f"⬇️  Baixando: {video_title}")

        ydl_opts = {
            "format": self.FORMAT_H264,
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": False,
            "continuedl": True,
            "retries": 10,
            "postprocessors": [
                {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
            ],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            final_filename = ydl.prepare_filename(info)

        if not final_filename.lower().endswith(".mp4"):
            final_filename = final_filename.rsplit(".", 1)[0] + ".mp4"

        video_path = Path(final_filename)
        if not video_path.exists():
            mp4s = sorted(
                self.base_path.glob(f"{sanitized}*.mp4"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            video_path = mp4s[0] if mp4s else None
            if not video_path:
                raise RuntimeError(f"Arquivo não encontrado: {final_filename}")

        logger.info(
            f"✅ Download: {video_path.name} ({video_path.stat().st_size/1024/1024:.1f} MB)"
        )
        return video_path, video_title

    # ══════════════════════════════════════════════════════════════
    #  DOWNLOAD + CORTE EM CLIPES
    # ══════════════════════════════════════════════════════════════

    def download_and_split(
        self,
        url: str,
        num_parts: int = 2,
        task_id: str = "manual",
        clip_duration: int = 60,
        output_format: str = "9:16",
        crop_mode: str = "center",
        apply_transform: bool = True,
    ) -> Dict:
        self._validate_url(url)
        try:
            video_path, video_title = self._download_video(url)
            file_size_mb = video_path.stat().st_size / (1024 * 1024)

            if num_parts <= 1:
                parts = [str(video_path)]
                parts_info = [
                    {
                        "clip_id": 1,
                        "filename": video_path.name,
                        "path": str(video_path),
                        "start": 0,
                        "end": 0,
                        "duration": 0,
                        "size_mb": round(file_size_mb, 2),
                    }
                ]
            else:
                splitter = self._configure_splitter(output_format, crop_mode)
                parts_info = splitter.split_all_clips(
                    video_path=str(video_path),
                    clip_duration=clip_duration,
                    num_clips=num_parts,
                    apply_transform=apply_transform,
                )
                if not parts_info:
                    raise RuntimeError("Falha ao dividir o vídeo.")
                parts = [p["path"] for p in parts_info]
                # Só remove original se os clipes estão em raw_clips (diretório diferente)
                if (
                    all(Path(p).exists() for p in parts)
                    and self.base_path != self.raw_clips_dir
                ):
                    try:
                        os.remove(str(video_path))
                    except Exception:
                        pass

            return {
                "status": "completed",
                "task_id": task_id,
                "title": video_title,
                "file_parts": parts,
                "parts_info": parts_info,
                "parts_count": len(parts),
                "output_dir": str(self.raw_clips_dir),
                "download_dir": str(self.base_path),
                "clip_duration": clip_duration,
                "output_format": output_format,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro: {e}", exc_info=True)
            raise

    # ══════════════════════════════════════════════════════════════
    #  PIPELINE COMPLETO: GANCHO + CLIPES (SEM DUPLICAR)
    # ══════════════════════════════════════════════════════════════

    def download_full_pipeline(
        self,
        url: str,
        num_parts: int = 3,
        task_id: str = "manual",
        clip_duration: int = 90,
        moment_duration: int = 8,
        output_format: str = "9:16",
        crop_mode: str = "center",
        apply_transform: bool = True,
    ) -> Dict:
        """
        Pipeline completo:
        1. Baixa o vídeo (ou usa cache)
        2. Extrai gancho de 8s (IA ou fallback do meio do vídeo)
        3. Corta clipes a partir de onde o gancho termina (evita duplicação)
        4. Adiciona gancho ANTES de cada clipe
        → Resultado: clipes com introdução SEM conteúdo repetido
        """
        self._validate_url(url)
        try:
            video_path, video_title = self._download_video(url)
            splitter = self._configure_splitter(output_format, crop_mode)

            # FASE 1: Extrai gancho (ANTES de cortar clipes)
            logger.info(f"\n🎯 FASE 1: Extraindo gancho de {moment_duration}s")
            hook = splitter.extract_hook(
                video_path=str(video_path),
                moment_duration=moment_duration,
                apply_transform=apply_transform,
            )

            if hook:
                logger.info(f"✅ Gancho extraído: {hook['filename']}")
                # Clipes começam DEPOIS do gancho (evita duplicar)
                start_offset = hook.get("hook_end", 30)
            else:
                logger.warning("⚠️  Gancho não gerado, usando fallback")
                start_offset = 30  # pula os primeiros 30s

            # FASE 2: Corta clipes (começando após o gancho)
            logger.info(
                f"\n📦 FASE 2: Cortando {num_parts} clipe(s) de {clip_duration}s"
            )
            logger.info(f"   Início: {start_offset}s (após o gancho)")

            clips_info = splitter.split_all_clips(
                video_path=str(video_path),
                clip_duration=clip_duration,
                num_clips=num_parts,
                start_offset=start_offset,
                apply_transform=apply_transform,
            )

            if not clips_info:
                raise RuntimeError("Falha ao cortar clipes.")

            # FASE 3: Adiciona gancho antes de cada clipe
            if hook:
                logger.info(f"\n🔗 FASE 3: Adicionando gancho antes de cada clipe")
                clipes_json = splitter.base_dir / f"{video_path.stem}_clipes.json"
                final_clips = splitter.prepend_hook_to_clips(
                    hook_path=hook["path"],
                    clips_json_path=str(clipes_json),
                    output_dir=self.raw_clips_dir,
                )
            else:
                final_clips = clips_info

            # Remove vídeo original (downloads/)
            if self.base_path != self.raw_clips_dir:
                try:
                    os.remove(str(video_path))
                except Exception:
                    pass

            parts = [c["path"] for c in final_clips]

            logger.info(
                f"\n✅ PIPELINE CONCLUÍDO: {len(final_clips)} clipes com gancho"
            )
            return {
                "status": "completed",
                "task_id": task_id,
                "title": video_title,
                "file_parts": parts,
                "parts_info": final_clips,
                "parts_count": len(final_clips),
                "hook_duration": moment_duration,
                "clip_duration": clip_duration,
                "output_dir": str(self.raw_clips_dir),
                "download_dir": str(self.base_path),
                "output_format": output_format,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro no pipeline: {e}", exc_info=True)
            raise

    # ══════════════════════════════════════════════════════════════
    #  MÉTODOS AUXILIARES
    # ══════════════════════════════════════════════════════════════

    def split_existing_video(
        self,
        video_path: str,
        num_clips=None,
        clip_duration=60,
        output_format="9:16",
        crop_mode="center",
        apply_transform=True,
        remove_original=False,
    ) -> Dict:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")
        splitter = self._configure_splitter(output_format, crop_mode)
        parts_info = splitter.split_all_clips(
            video_path=str(video_path),
            clip_duration=clip_duration,
            num_clips=num_clips,
            apply_transform=apply_transform,
        )
        if not parts_info:
            raise RuntimeError("Nenhum clipe foi gerado.")
        parts = [p["path"] for p in parts_info]
        if remove_original and all(Path(p).exists() for p in parts):
            try:
                os.remove(str(video_path))
            except Exception:
                pass
        return {
            "status": "completed",
            "original_video": str(video_path),
            "file_parts": parts,
            "parts_info": parts_info,
            "parts_count": len(parts),
            "output_dir": str(self.raw_clips_dir),
        }

    def download_video(
        self,
        url: str,
        response: Response,
        num_parts=1,
        clip_duration=60,
        output_format="9:16",
        crop_mode="center",
    ) -> Dict:
        resultado = self.download_and_split(
            url=url,
            num_parts=num_parts,
            clip_duration=clip_duration,
            output_format=output_format,
            crop_mode=crop_mode,
        )
        response.status_code = status.HTTP_201_CREATED
        return resultado

    def process_in_background(
        self,
        url: str,
        num_parts: int,
        background_tasks: BackgroundTasks,
        clip_duration=60,
        output_format="9:16",
        crop_mode="center",
        apply_transform=True,
        mode: str = "clips",
    ) -> str:
        task_id = str(uuid.uuid4())[:8]
        if mode == "full":
            background_tasks.add_task(
                self.download_full_pipeline,
                url=url,
                num_parts=num_parts,
                task_id=task_id,
                clip_duration=clip_duration,
                output_format=output_format,
                crop_mode=crop_mode,
                apply_transform=apply_transform,
            )
        else:
            background_tasks.add_task(
                self.download_and_split,
                url=url,
                num_parts=num_parts,
                task_id=task_id,
                clip_duration=clip_duration,
                output_format=output_format,
                crop_mode=crop_mode,
                apply_transform=apply_transform,
            )
        logger.info(f"🚀 Tarefa {task_id} agendada ({mode})")
        return task_id


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🎬 VIDEO DOWNLOADER - TESTE")
    print("=" * 60)
    print("\n📋 Modos:")
    print("   1. Baixar e cortar em clipes")
    print("   2. Pipeline completo (clipes + gancho)")

    modo = input("\n🔢 Escolha (1 ou 2): ").strip() or "1"
    url = input("🔗 URL do vídeo: ").strip() or "https://youtu.be/fi4YiZvbLXU"
    num = int(input("✂️  Quantos clipes? (3): ").strip() or "3")
    formato = input("📱 Formato (1=9:16, 2=16:9): ").strip() or "1"
    output_format = "9:16" if formato == "1" else "16:9"

    print(f"\n🚀 INICIANDO...\n")
    start = VideoDownloader()

    if modo == "2":
        resultado = start.download_full_pipeline(
            url=url,
            num_parts=num,
            output_format=output_format,
        )
        print(
            f"\n✅ {resultado['parts_count']} clipe(s) com gancho de {resultado.get('hook_duration', 8)}s"
        )
    else:
        resultado = start.download_and_split(
            url=url,
            num_parts=num,
            output_format=output_format,
        )
        print(f"\n✅ {resultado['parts_count']} clipe(s)")

    print(f"📁 Saída: {resultado['output_dir']}")
