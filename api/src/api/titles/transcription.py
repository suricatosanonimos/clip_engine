"""
POST /api/transcription
Transcreve um vídeo já salvo no servidor com Whisper
e passa o resultado pela Brain IA para identificar os melhores momentos.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from src.api.schemas import TranscriptionRequest, TranscriptionResponse, TranscriptionSegment
from src.controllers.highlight.transcription import TranscriptionEngine, process_video_with_ai
from src.utils.logs import logger

router = APIRouter(prefix="/transcription", tags=["Transcription"])


@router.post(
    "/",
    response_model=TranscriptionResponse,
    summary="Transcreve um vídeo com Whisper e analisa com a Brain IA",
)
async def transcribe_video(body: TranscriptionRequest):
    """
    Recebe o **caminho absoluto** de um vídeo já salvo no servidor,
    transcreve com Whisper e envia os segmentos para a Brain IA
    identificar os melhores momentos.

    Use após `POST /api/video/process` quando o processamento já tiver
    gerado os clipes e você quiser a análise textual + sugestão de cortes.
    """
    video_path = Path(body.video_path)

    if not video_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo não encontrado: {body.video_path}",
        )

    if video_path.suffix.lower() not in {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Formato de arquivo não suportado.",
        )

    try:
        logger.info(f"Transcrevendo: {video_path.name} (modelo: {body.model_size})")

        # 1. Transcrição com Whisper
        engine = TranscriptionEngine(model_size=body.model_size)
        segmentos_raw = await engine.transcribe_to_json(str(video_path))

        if not segmentos_raw:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Whisper não conseguiu transcrever o vídeo. Verifique se possui áudio.",
            )

        segmentos = [TranscriptionSegment(**s) for s in segmentos_raw]

        # 2. Brain IA — melhores momentos
        ai_analysis = None
        try:
            ai_analysis = await process_video_with_ai(video_input=str(video_path))
        except Exception as e:
            logger.warning(f"Brain IA falhou (não crítico): {e}")

        return TranscriptionResponse(
            video_path=str(video_path),
            segments=segmentos,
            total_segments=len(segmentos),
            ai_analysis=ai_analysis,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Erro na transcrição: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
