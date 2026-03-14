"""
POST /api/video/upload
Recebe arquivo de vídeo via multipart/form-data, salva em downloads/
e dispara o pipeline sem etapa de download.
"""

import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status

from src.api.routes.video import _etapa_ia_e_assembler, _montar_clip_results, _run_async
from src.api.schemas import ClipResult, TaskStatus, VideoProcessResponse
from src.api.task_store import create_task, update_task
from src.controllers.video_processing.video_processor import VideoProcessor
from src.utils.logs import logger

router = APIRouter(prefix="/video", tags=["Video"])

ROOT_DIR      = Path(__file__).resolve().parent.parent.parent
DOWNLOADS_DIR = ROOT_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

EXTENSOES_PERMITIDAS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".3gp", ".m4v"}


# ──────────────────────────────────────────────────────────────────
#  WORKER — arquivo local (sem download)
# ──────────────────────────────────────────────────────────────────

def _run_pipeline_local(
    task_id: str,
    video_path: str,
    num_clips: int,
    clip_duration: int,
    tracking: bool,
):
    try:
        video_name = Path(video_path).name

        # ETAPA 1 — VideoProcessor
        update_task(task_id, status=TaskStatus.PROCESSING, progress=0.15,
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

        # ETAPA 2 — IA + Assembler (compartilhado com video.py)
        clips_finais = _etapa_ia_e_assembler(task_id, clips_gerados)

        # Resultado final
        clip_results = _montar_clip_results(clips_finais)
        update_task(task_id, status=TaskStatus.DONE, progress=1.0,
                    message=f"✅ {len(clip_results)} clipes prontos.",
                    clips=clip_results)
        logger.info(f"[{task_id}] ✅ Upload pipeline finalizado com {len(clip_results)} clipes.")

    except Exception as exc:
        logger.error(f"[{task_id}] ❌ Erro: {exc}", exc_info=True)
        update_task(task_id, status=TaskStatus.ERROR, progress=0.0,
                    message="Erro durante o processamento.", error=str(exc))


# ──────────────────────────────────────────────────────────────────
#  ROTA
# ──────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=VideoProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Recebe vídeo local e inicia o pipeline",
)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile         = File(..., description="Arquivo de vídeo"),
    num_clips:     int       = Form(default=10),
    clip_duration: int       = Form(default=60),
    tracking:      bool      = Form(default=True),
    subtitles:     bool      = Form(default=False),
):
    """
    Recebe o vídeo via `multipart/form-data`, salva em `downloads/`
    e dispara o pipeline pulando a etapa de download.

    Retorna um `task_id` — acompanhe via `GET /api/status/{task_id}`.
    """
    sufixo = Path(file.filename or "").suffix.lower()
    if sufixo not in EXTENSOES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Formato não suportado: '{sufixo}'. Use: {', '.join(sorted(EXTENSOES_PERMITIDAS))}",
        )

    destino = DOWNLOADS_DIR / (file.filename or "upload.mp4")
    try:
        with open(destino, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        logger.error(f"Falha ao salvar upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Não foi possível salvar o arquivo: {e}",
        )
    finally:
        await file.close()

    size_mb = destino.stat().st_size / 1024 / 1024
    logger.info(f"Upload recebido: {destino.name} ({size_mb:.1f} MB)")

    task_id = create_task()
    update_task(task_id, status=TaskStatus.PENDING,
                message=f"Arquivo recebido: {destino.name}. Iniciando processamento...")

    background_tasks.add_task(
        _run_pipeline_local,
        task_id=task_id,
        video_path=str(destino),
        num_clips=num_clips,
        clip_duration=clip_duration,
        tracking=tracking,
    )

    return VideoProcessResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message=f"Upload recebido. Acompanhe em GET /api/status/{task_id}",
    )
