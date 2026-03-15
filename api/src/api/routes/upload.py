"""
POST /api/video/upload

Fluxo:
  1. Recebe arquivo via multipart
  2. Salva em downloads/ localmente
  3. Sobe o vídeo original para Supabase Storage (bucket: videos)
  4. Registra job no banco como "processing"
  5. VideoProcessor gera clipes (com tracking)
  6. SubtitleGenerator (opcional)
  7. Clipes finais → Storage (bucket: clips) + registro em public.clips
"""

import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, BackgroundTasks, File, Form,
    HTTPException, UploadFile, status,
)

from src.api.routes.video import (
    _etapa_legendas, _montar_clip_results, _montar_clip_results_simples,
    _run_async, _salvar_clips_safe, _atualizar_job_safe,
)
from src.api.schemas import TaskStatus, VideoProcessResponse
from src.api.task_store import create_task, update_task
from src.controllers.video_processing.video_processor import VideoProcessor
from src.utils.logs import logger

router = APIRouter(prefix="/video", tags=["Video"])

ROOT_DIR      = Path(__file__).resolve().parent.parent.parent.parent
DOWNLOADS_DIR = ROOT_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

EXTENSOES_PERMITIDAS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".3gp", ".m4v"}


# ──────────────────────────────────────────────────────────────────
#  UPLOAD DO VÍDEO ORIGINAL PARA STORAGE
# ──────────────────────────────────────────────────────────────────

def _upload_video_original(
    video_path: Path,
    user_id: str,
    job_id: str,
) -> Optional[str]:
    """
    Envia o vídeo original para o bucket 'videos' no Supabase Storage.
    Retorna o storage_path ou None se falhar.
    """
    try:
        from src.database.supabase_client import get_supabase_admin_client
        import mimetypes

        client       = get_supabase_admin_client()
        storage_path = f"{user_id}/{job_id}/{video_path.name}"
        mime_type    = mimetypes.guess_type(str(video_path))[0] or "video/mp4"

        with open(video_path, "rb") as f:
            client.storage.from_("videos").upload(
                path=storage_path,
                file=f,
                file_options={
                    "content-type":  mime_type,
                    "cache-control": "3600",
                    "upsert":        "true",
                },
            )
        logger.info(f"Vídeo original enviado para Storage: {storage_path}")
        return storage_path
    except Exception as e:
        logger.warning(f"Falha ao enviar vídeo original para Storage: {e}")
        return None


# ──────────────────────────────────────────────────────────────────
#  WORKER
# ──────────────────────────────────────────────────────────────────

def _run_pipeline_upload(
    task_id:       str,
    job_id:        str,
    user_id:       str,
    video_path:    str,
    num_clips:     int,
    clip_duration: int,
    tracking:      bool,
    subtitles:     bool,
    cor_legenda:   str = "white",
):
    try:
        video_path_obj = Path(video_path)
        video_name     = video_path_obj.name

        # ── ETAPA 1: Sobe vídeo original para Storage ─────────────
        update_task(task_id, status=TaskStatus.DOWNLOADING, progress=0.10,
                    message="Enviando vídeo para a nuvem...")
        _atualizar_job_safe(job_id, user_id, status="downloading",
                            progress=0.10, message="Enviando vídeo original...")

        storage_path_original = _upload_video_original(video_path_obj, user_id, job_id)

        # Atualiza source_storage_path no job
        if storage_path_original:
            try:
                from src.database.supabase_client import get_supabase_admin_client
                get_supabase_admin_client().table("jobs").update({
                    "source_storage_path": storage_path_original,
                    "status": "processing",
                }).eq("id", job_id).execute()
            except Exception as e:
                logger.warning(f"Não foi possível atualizar source_storage_path: {e}")

        # ── ETAPA 2: VideoProcessor ────────────────────────────────
        update_task(task_id, status=TaskStatus.PROCESSING, progress=0.20,
                    message="Processando vídeo com tracking de rostos...")
        _atualizar_job_safe(job_id, user_id, status="processing",
                            progress=0.20, message="Processando com tracking...")

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

        # ── ETAPA 4: Upload clipes para Storage ────────────────────
        update_task(task_id, status=TaskStatus.ANALYZING, progress=0.82,
                    message="Salvando clipes na nuvem...")
        _atualizar_job_safe(job_id, user_id, status="analyzing",
                            progress=0.82, message="Enviando clipes para Storage...")

        clip_results = _salvar_clips_safe(clips_finais, user_id, job_id, task_id)

        if not clip_results:
            raise RuntimeError("Nenhum clipe foi gerado ou salvo.")

        # ── Resultado ──────────────────────────────────────────────
        update_task(task_id, status=TaskStatus.DONE, progress=1.0,
                    message=f"✅ {len(clip_results)} clipes prontos!",
                    clips=clip_results)
        _atualizar_job_safe(job_id, user_id, status="done",
                            progress=1.0, message=f"{len(clip_results)} clipes prontos.")
        logger.info(f"[{task_id}] ✅ Upload pipeline finalizado com {len(clip_results)} clipes.")

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
    "/upload",
    response_model=VideoProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Recebe vídeo, envia para Storage e inicia o pipeline",
)
async def upload_video(
    background_tasks: BackgroundTasks,
    file:          UploadFile = File(...,          description="Arquivo de vídeo"),
    user_id:       str        = Form(...,          description="UUID do usuário autenticado"),
    job_id:        str        = Form(...,          description="UUID do job criado no banco"),
    num_clips:     int        = Form(default=3),
    clip_duration: int        = Form(default=60),
    tracking:      bool       = Form(default=True),
    subtitles:     bool       = Form(default=False),
    cor_legenda:   str        = Form(default="white"),
):
    """
    1. Salva o arquivo em downloads/
    2. Envia o vídeo original para Supabase Storage (bucket: videos)
    3. Processa os clipes com tracking
    4. (Opcional) Gera legendas
    5. Envia clipes para Storage (bucket: clips) e registra no banco
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Não foi possível salvar o arquivo: {e}",
        )
    finally:
        await file.close()

    size_mb = destino.stat().st_size / 1024 / 1024
    logger.info(f"Upload recebido: {destino.name} ({size_mb:.1f} MB) | job: {job_id}")

    task_id = create_task()
    update_task(task_id, status=TaskStatus.PENDING,
                message=f"Arquivo recebido: {destino.name}. Iniciando...")

    background_tasks.add_task(
        _run_pipeline_upload,
        task_id=task_id,
        job_id=job_id,
        user_id=user_id,
        video_path=str(destino),
        num_clips=num_clips,
        clip_duration=clip_duration,
        tracking=tracking,
        subtitles=subtitles,
        cor_legenda=cor_legenda,
    )

    return VideoProcessResponse(
        task_id=task_id,
        job_id=job_id,
        status=TaskStatus.PENDING,
        message=f"Upload recebido. Acompanhe em GET /api/status/{task_id}",
    )
