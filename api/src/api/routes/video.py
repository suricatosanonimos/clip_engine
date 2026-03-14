"""
POST /api/video/process
Recebe URL do YouTube, dispara o pipeline completo em background.
"""

import asyncio
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, status

from src.api.schemas import ClipResult, TaskStatus, VideoProcessRequest, VideoProcessResponse
from src.api.task_store import create_task, update_task
from src.controllers.highlight.create_video import VideoAssembler
from src.controllers.highlight.transcription import process_video_with_ai
from src.controllers.video_processing.video_processor import VideoProcessor
from src.services.downloader import VideoDownloader
from src.utils.logs import logger

router = APIRouter(prefix="/video", tags=["Video"])

ROOT_DIR      = Path(__file__).resolve().parent.parent.parent.parent
DOWNLOADS_DIR = ROOT_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

_DOWNLOAD_MAX_RETRIES = 3


# ──────────────────────────────────────────────────────────────────
#  HELPERS COMPARTILHADOS (importados também pelo upload.py)
# ──────────────────────────────────────────────────────────────────

def _run_async(coro):
    """
    Cria um event loop isolado para rodar corrotinas dentro de threads.
    Necessário pois BackgroundTasks roda em thread separada do FastAPI.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _montar_clip_results(clips_finais: list) -> list:
    """Converte lista de Path em lista de dicts prontos para ClipResult."""
    results = []
    for i, cp in enumerate(clips_finais, start=1):
        cp = Path(cp)
        if cp.exists():
            results.append(
                ClipResult(
                    index=i,
                    filename=cp.name,
                    path=str(cp),
                    size_mb=round(cp.stat().st_size / (1024 * 1024), 2),
                ).model_dump()
            )
    return results


def _etapa_ia_e_assembler(task_id: str, clips_gerados: list) -> list:
    """
    Roda Whisper + Brain IA + VideoAssembler.
    Erros não abortam o pipeline — retorna clips_gerados como fallback.
    """
    clips_finais  = list(clips_gerados)
    ai_analysis   = None
    ai_json_path  = None

    # Whisper + Brain IA
    try:
        clip_para_ia = str(clips_gerados[0])
        ai_analysis  = _run_async(process_video_with_ai(video_input=clip_para_ia))
        ai_json_path = Path(clip_para_ia).with_name(
            f"ai_analysis_{Path(clip_para_ia).stem}.json"
        )
        logger.info(f"[{task_id}] ✅ Análise IA concluída.")
    except Exception as e:
        logger.warning(f"[{task_id}] ⚠️ Análise IA falhou (não crítico): {e}")

    update_task(
        task_id,
        status=TaskStatus.ANALYZING,
        progress=0.80,
        message="Montando vídeo final com hook...",
        ai_analysis=ai_analysis,
    )

    # VideoAssembler
    if ai_json_path and ai_json_path.exists():
        try:
            assembler = VideoAssembler(ai_results_path=str(ai_json_path))
            for cp in clips_gerados:
                assembler.create_final_cut(original_video_path=str(cp))

            final_dir   = ROOT_DIR / "processed_videos" / "final_clips"
            finais_hook = sorted(final_dir.glob("FINAL_HOOK_*.mp4"))
            if finais_hook:
                clips_finais = finais_hook

            logger.info(f"[{task_id}] ✅ Montagem final concluída.")
        except Exception as e:
            logger.warning(f"[{task_id}] ⚠️ Montagem falhou, usando clipes brutos: {e}")

    return clips_finais


# ──────────────────────────────────────────────────────────────────
#  DOWNLOAD COM RETRY
# ──────────────────────────────────────────────────────────────────

def _download_com_retry(url: str, task_id: str) -> dict:
    downloader  = VideoDownloader(output_dir=str(DOWNLOADS_DIR))
    ultimo_erro = None

    for tentativa in range(1, _DOWNLOAD_MAX_RETRIES + 1):
        try:
            logger.info(f"[{task_id}] Download tentativa {tentativa}/{_DOWNLOAD_MAX_RETRIES}")
            update_task(
                task_id,
                message=f"Baixando vídeo... (tentativa {tentativa}/{_DOWNLOAD_MAX_RETRIES})",
            )
            return downloader.download_and_split(url=url, num_parts=1)
        except Exception as e:
            ultimo_erro = e
            logger.warning(f"[{task_id}] Tentativa {tentativa} falhou: {e}")

    raise RuntimeError(
        f"Download falhou após {_DOWNLOAD_MAX_RETRIES} tentativas. "
        f"Último erro: {ultimo_erro}"
    )


# ──────────────────────────────────────────────────────────────────
#  WORKER — YouTube
# ──────────────────────────────────────────────────────────────────

def _run_pipeline(
    task_id: str,
    url: str,
    num_clips: int,
    clip_duration: int,
    tracking: bool,
    subtitles: bool,
):
    try:
        # ETAPA 1 — Download
        update_task(task_id, status=TaskStatus.DOWNLOADING, progress=0.05,
                    message="Iniciando download do YouTube...")
        logger.info(f"[{task_id}] URL: {url}")

        resultado  = _download_com_retry(url, task_id)
        partes     = resultado.get("file_parts", [])
        if not partes:
            raise RuntimeError("download_and_split não retornou nenhuma parte.")

        video_name = Path(partes[0]).name
        titulo     = resultado.get("title", video_name)

        logger.info(f"[{task_id}] ✅ Download OK → {video_name}")
        update_task(task_id, progress=0.25, message=f"Download concluído: {titulo}")

        # ETAPA 2 — VideoProcessor
        update_task(task_id, status=TaskStatus.PROCESSING, progress=0.30,
                    message="Processando vídeo com tracking de rostos...")

        processor = VideoProcessor(num_shots=num_clips)
        processor.clip_duration = clip_duration

        clips_gerados: List[Path] = _run_async(
            processor.process(video_name=video_name, tracking=tracking)
        )
        if not clips_gerados:
            raise RuntimeError("VideoProcessor não gerou nenhum clipe.")

        logger.info(f"[{task_id}] ✅ {len(clips_gerados)} clipes gerados.")
        update_task(task_id, status=TaskStatus.TRANSCRIBING, progress=0.60,
                    message=f"{len(clips_gerados)} clipes brutos gerados.")

        # ETAPA 3 — IA + Assembler
        clips_finais = _etapa_ia_e_assembler(task_id, clips_gerados)

        # Resultado final
        clip_results = _montar_clip_results(clips_finais)
        update_task(task_id, status=TaskStatus.DONE, progress=1.0,
                    message=f"✅ Pipeline concluído! {len(clip_results)} clipes prontos.",
                    clips=clip_results)
        logger.info(f"[{task_id}] ✅ Pipeline finalizado com {len(clip_results)} clipes.")

    except Exception as exc:
        logger.error(f"[{task_id}] ❌ Erro: {exc}", exc_info=True)
        update_task(task_id, status=TaskStatus.ERROR, progress=0.0,
                    message="Erro durante o processamento.", error=str(exc))


# ──────────────────────────────────────────────────────────────────
#  ROTA
# ──────────────────────────────────────────────────────────────────

@router.post(
    "/process",
    response_model=VideoProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Inicia o pipeline com URL do YouTube",
)
async def process_video(body: VideoProcessRequest, background_tasks: BackgroundTasks):
    """
    Dispara o pipeline em background e retorna um `task_id` imediatamente.
    Acompanhe via `GET /api/status/{task_id}`.
    """
    task_id = create_task()
    background_tasks.add_task(
        _run_pipeline,
        task_id=task_id,
        url=body.url,
        num_clips=body.num_clips,
        clip_duration=body.clip_duration,
        tracking=body.tracking,
        subtitles=body.subtitles,
    )
    return VideoProcessResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message=f"Pipeline iniciado. Acompanhe em GET /api/status/{task_id}",
    )
