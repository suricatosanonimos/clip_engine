"""
POST /api/video/process

Pipeline simplificado — sem IA externa, sem VideoAssembler:
  1. Download yt-dlp (retry)
  2. VideoProcessor (tracking + clipes brutos)
  3. SubtitleGenerator (opcional, se subtitles=True)
  4. Upload clipes → Supabase Storage + registro em public.clips
  5. Atualiza public.jobs
"""

import asyncio
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, status

from src.api.schemas import (
    ClipResult, TaskStatus, VideoProcessRequest, VideoProcessResponse,
)
from src.api.task_store import create_task, update_task
from src.controllers.video_processing.video_processor import VideoProcessor
from src.services.downloader import VideoDownloader
from src.utils.logs import logger

router = APIRouter(prefix="/video", tags=["Video"])

ROOT_DIR      = Path(__file__).resolve().parent.parent.parent.parent
DOWNLOADS_DIR = ROOT_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

_DOWNLOAD_MAX_RETRIES = 3


# ──────────────────────────────────────────────────────────────────
#  HELPERS — compartilhados com upload.py
# ──────────────────────────────────────────────────────────────────

def _run_async(coro):
    """Loop isolado para corrotinas em BackgroundTasks (thread separada)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _montar_clip_results(clips: list) -> list:
    """Converte lista de dicts (com storage_path/public_url) para ClipResult."""
    return [
        ClipResult(
            index=c["index"], filename=c["filename"], path=c["path"],
            size_mb=c["size_mb"], storage_path=c.get("storage_path"),
            public_url=c.get("public_url"),
        ).model_dump()
        for c in clips
    ]


def _montar_clip_results_simples(clips_finais: list) -> list:
    """Fallback sem Storage — converte Paths em dicts."""
    results = []
    for i, cp in enumerate(clips_finais, start=1):
        cp = Path(cp)
        if cp.exists():
            results.append(ClipResult(
                index=i, filename=cp.name, path=str(cp),
                size_mb=round(cp.stat().st_size / (1024 * 1024), 2),
            ).model_dump())
    return results


def _atualizar_job_safe(job_id: str, user_id: Optional[str], **kwargs):
    """Atualiza job no banco somente se user_id foi fornecido."""
    if not user_id:
        return
    try:
        from src.services.storage_service import atualizar_job_status
        atualizar_job_status(job_id, **kwargs)
    except Exception as e:
        logger.warning(f"[{job_id}] Não foi possível atualizar job no banco: {e}")


def _salvar_clips_safe(
    clips_finais: list,
    user_id: Optional[str],
    job_id: str,
    task_id: str,
) -> list:
    """Upload para Storage se autenticado; senão retorna paths locais."""
    if not user_id:
        logger.info(f"[{task_id}] Sem user_id — pulando upload para Storage.")
        return _montar_clip_results_simples(clips_finais)
    try:
        from src.services.storage_service import processar_e_salvar_clips
        salvos = processar_e_salvar_clips(clips_finais, user_id, job_id, task_id)
        if salvos:
            return _montar_clip_results(salvos)
    except Exception as e:
        logger.warning(f"[{task_id}] Upload Storage falhou, usando fallback local: {e}")
    return _montar_clip_results_simples(clips_finais)


# ──────────────────────────────────────────────────────────────────
#  ETAPA DE LEGENDAS (opcional)
# ──────────────────────────────────────────────────────────────────

def _etapa_legendas(
    task_id: str,
    clips: List[Path],
    cor_legenda: str = "white",
) -> List[Path]:
    """
    Gera legendas word-by-word nos clipes via SubtitleGenerator.
    Se falhar em qualquer clipe, usa o clipe original como fallback.
    Retorna lista de Paths dos clipes finais (com ou sem legenda).
    """
    try:
        from src.controllers.services.transcriber import SubtitleGenerator
        gen = SubtitleGenerator(cor_legenda=cor_legenda)
    except Exception as e:
        logger.warning(f"[{task_id}] SubtitleGenerator não disponível: {e}")
        return clips

    finais = []
    for i, clip in enumerate(clips, start=1):
        update_task(
            task_id,
            progress=0.60 + (i / len(clips)) * 0.20,
            message=f"Gerando legenda {i}/{len(clips)}...",
        )
        try:
            resultado = _run_async(gen.process_video(str(clip), cor_legenda=cor_legenda))
            if resultado and resultado.exists():
                finais.append(resultado)
                logger.info(f"[{task_id}] Legenda OK: {resultado.name}")
            else:
                finais.append(clip)
                logger.warning(f"[{task_id}] Legenda falhou para {clip.name}, usando original.")
        except Exception as e:
            finais.append(clip)
            logger.warning(f"[{task_id}] Legenda erro em {clip.name}: {e}")

    return finais


# ──────────────────────────────────────────────────────────────────
#  DOWNLOAD COM RETRY
# ──────────────────────────────────────────────────────────────────

def _download_com_retry(url: str, task_id: str) -> dict:
    downloader  = VideoDownloader(output_dir=str(DOWNLOADS_DIR))
    ultimo_erro = None
    for tentativa in range(1, _DOWNLOAD_MAX_RETRIES + 1):
        try:
            logger.info(f"[{task_id}] Download tentativa {tentativa}/{_DOWNLOAD_MAX_RETRIES}")
            update_task(task_id, message=f"Baixando vídeo... (tentativa {tentativa})")
            return downloader.download_and_split(url=url, num_parts=1)
        except Exception as e:
            ultimo_erro = e
            logger.warning(f"[{task_id}] Tentativa {tentativa} falhou: {e}")
    raise RuntimeError(
        f"Download falhou após {_DOWNLOAD_MAX_RETRIES} tentativas. "
        f"Último erro: {ultimo_erro}"
    )


# ──────────────────────────────────────────────────────────────────
#  WORKER PRINCIPAL
# ──────────────────────────────────────────────────────────────────

def _run_pipeline(
    task_id:       str,
    job_id:        str,
    user_id:       Optional[str],
    url:           str,
    num_clips:     int,
    clip_duration: int,
    tracking:      bool,
    subtitles:     bool,
    cor_legenda:   str  = "white",
):
    try:
        # ── ETAPA 1: Download ──────────────────────────────────────
        update_task(task_id, status=TaskStatus.DOWNLOADING, progress=0.05,
                    message="Baixando vídeo do YouTube...")
        _atualizar_job_safe(job_id, user_id, status="downloading",
                            progress=0.05, message="Baixando vídeo...")

        resultado  = _download_com_retry(url, task_id)
        partes     = resultado.get("file_parts", [])
        if not partes:
            raise RuntimeError("download_and_split não retornou nenhuma parte.")

        video_name = Path(partes[0]).name
        titulo     = resultado.get("title", video_name)

        update_task(task_id, progress=0.25, message=f"Download concluído: {titulo}")
        _atualizar_job_safe(job_id, user_id, status="downloading",
                            progress=0.25, message=f"Download OK: {titulo}",
                            video_title=titulo)

        # ── ETAPA 2: VideoProcessor ────────────────────────────────
        update_task(task_id, status=TaskStatus.PROCESSING, progress=0.30,
                    message="Processando vídeo com tracking de rostos...")
        _atualizar_job_safe(job_id, user_id, status="processing",
                            progress=0.30, message="Processando com tracking...")

        processor = VideoProcessor(num_shots=num_clips)
        processor.clip_duration = clip_duration
        processor.in_dir        = DOWNLOADS_DIR

        clips_gerados: List[Path] = _run_async(
            processor.process(video_name=video_name, tracking=tracking)
        )
        if not clips_gerados:
            raise RuntimeError("VideoProcessor não gerou nenhum clipe.")

        logger.info(f"[{task_id}] ✅ {len(clips_gerados)} clipes gerados.")
        update_task(task_id, status=TaskStatus.TRANSCRIBING, progress=0.55,
                    message=f"{len(clips_gerados)} clipes brutos gerados.")
        _atualizar_job_safe(job_id, user_id, status="transcribing",
                            progress=0.55, message=f"{len(clips_gerados)} clipes gerados.")

        # ── ETAPA 3: Legendas (opcional) ───────────────────────────
        clips_finais = list(clips_gerados)
        if subtitles:
            update_task(task_id, status=TaskStatus.ANALYZING, progress=0.60,
                        message="Gerando legendas word-by-word...")
            _atualizar_job_safe(job_id, user_id, status="analyzing",
                                progress=0.60, message="Gerando legendas...")
            clips_finais = _etapa_legendas(task_id, clips_gerados, cor_legenda)

        # ── ETAPA 4: Upload para Supabase Storage ─────────────────
        update_task(task_id, status=TaskStatus.ANALYZING, progress=0.82,
                    message="Salvando clipes na nuvem...")
        _atualizar_job_safe(job_id, user_id, status="analyzing",
                            progress=0.82, message="Enviando para Storage...")

        clip_results = _salvar_clips_safe(clips_finais, user_id, job_id, task_id)

        if not clip_results:
            raise RuntimeError("Nenhum clipe foi gerado ou salvo.")

        # ── Resultado ──────────────────────────────────────────────
        update_task(task_id, status=TaskStatus.DONE, progress=1.0,
                    message=f"✅ {len(clip_results)} clipes prontos!",
                    clips=clip_results)
        _atualizar_job_safe(job_id, user_id, status="done",
                            progress=1.0, message=f"{len(clip_results)} clipes prontos.")
        logger.info(f"[{task_id}] ✅ Pipeline concluído com {len(clip_results)} clipes.")

    except Exception as exc:
        logger.error(f"[{task_id}] ❌ Erro: {exc}", exc_info=True)
        update_task(task_id, status=TaskStatus.ERROR, progress=0.0,
                    message="Erro durante o processamento.", error=str(exc))
        _atualizar_job_safe(job_id, user_id, status="error",
                            progress=0.0, message="Erro.", error=str(exc))


# ──────────────────────────────────────────────────────────────────
#  ROTA
# ──────────────────────────────────────────────────────────────────

@router.post(
    "/process",
    response_model=VideoProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Inicia pipeline com URL do YouTube ou URL assinada do Storage",
)
async def process_video(body: VideoProcessRequest, background_tasks: BackgroundTasks):
    task_id = create_task()
    job_id  = body.job_id or str(uuid.uuid4())

    # Cria job no banco se vier user_id mas não job_id
    if body.user_id and not body.job_id:
        try:
            from src.database.supabase_client import get_supabase_admin_client
            client = get_supabase_admin_client()
            client.table("jobs").insert({
                "id":            job_id,
                "user_id":       body.user_id,
                "status":        "pending",
                "source_type":   body.source_type,
                "source_url":    body.url if body.source_type == "youtube" else None,
                "num_clips":     body.num_clips,
                "clip_duration": body.clip_duration,
                "tracking":      body.tracking,
            }).execute()
            logger.info(f"Job criado no banco: {job_id}")
        except Exception as e:
            logger.warning(f"Não foi possível criar job no banco: {e}")

    background_tasks.add_task(
        _run_pipeline,
        task_id=task_id,
        job_id=job_id,
        user_id=body.user_id,
        url=body.url,
        num_clips=body.num_clips,
        clip_duration=body.clip_duration,
        tracking=body.tracking,
        subtitles=body.subtitles,
        cor_legenda=getattr(body, "cor_legenda", "white"),
    )

    return VideoProcessResponse(
        task_id=task_id,
        job_id=job_id,
        status=TaskStatus.PENDING,
        message=f"Pipeline iniciado. Acompanhe em GET /api/status/{task_id}",
    )
