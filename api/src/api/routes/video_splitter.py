# src/api/routes/video_splitter.py
"""
Rota para corte de vídeos usando VideoSplitterFast.
"""

import sys
import logging
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi import APIRouter, HTTPException, Query, status
from src.utils.video_splitter import VideoSplitterFast

# Importando os schemas com apelidos (as) explícitos para clareza
from src.api.schemas.splitter import (
    CutRequest as VideoCutRequest,
    ClipeInfo as VideoClipInfo,
    CutResponse as VideoCutResponse
)

# Configuração de log básico para não perder os erros reais ocultados do usuário
logger = logging.getLogger(__name__)

# Configuração global de rotas e tags para o Swagger UI (Deixado limpo conforme instruído)
router = APIRouter()


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.post(
    "/videos",
    response_model=VideoCutResponse,
    summary="Corta um vídeo em múltiplos clipes",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Vídeo processado e clipes gerados com sucesso."},
        404: {"description": "O arquivo de vídeo especificado não foi encontrado."},
        500: {"description": "Erro interno durante o processamento do vídeo."}
    }
)
async def cut_video(req: VideoCutRequest):
    """
    Processa um vídeo local, aplicando cortes temporais e ajustes de aspecto (9:16 / 16:9).
    Também permite a extração e junção automática de um gancho (hook) inicial.
    """
    video = Path(req.video_path)
    
    if not video.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="O arquivo de vídeo informado não existe no servidor."
        )
    
    try:
        splitter = VideoSplitterFast(
            base_dir=ROOT_DIR / "processed_videos" / "raw_clips",
            output_format=req.formato,
            num_threads=2,
            zoom_factor=req.zoom,
        )
        
        # 🚀 VELOCIDADE MÁXIMA: Primeiro gera todos os clipes brutos super rápido (Sem IA/Whisper nesta etapa)
        clipes = splitter.split_all_clips(
            video_path=str(video),
            clip_duration=req.duracao,
            num_clips=req.num_clipes,
            start_offset=0,  # Sempre começa do zero para capturar a integridade inicial
            apply_transform=True,
        )
        
        # Se houver pedido de gancho, a análise com IA roda inteligentemente em cima dos clipes enxutos
        if req.com_gancho and clipes:
            clipes_json = splitter.base_dir / f"{video.stem}_clipes.json"
            
            # Chama o extrator que usa o BrainSelector focado estritamente na duração menor do clipe
            hook = await splitter.extract_hook_from_clips_json(
                clips_json_path=str(clipes_json),
                moment_duration=8
            )
            
            # Se o gancho foi gerado com sucesso, faz a unificação de encode único em paralelo
            if hook:
                clipes = splitter.prepend_hook_to_clips(
                    hook_path=hook["path"],
                    clips_json_path=str(clipes_json),
                )
        
        return VideoCutResponse(
            status="concluido",
            mensagem=f"{len(clipes)} clipes gerados com sucesso",
            total_clipes=len(clipes),
            clipes=clipes,
        )
        
    except Exception as e:
        logger.error(f"Erro crítico no processamento de vídeo: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Ocorreu um erro inesperado ao processar os cortes do vídeo."
        )


@router.get(
    "/status",
    summary="Verifica a integridade do ambiente de corte",
    responses={
        200: {
            "description": "Retorna o estado das dependências (FFmpeg) e capacidades do sistema.",
            "content": {
                "application/json": {
                    "example": {
                        "servico": "VideoSplitterFast",
                        "ffmpeg": "disponivel",
                        "formatos": ["9:16", "16:9"],
                        "zoom": "0.5 a 2.0"
                    }
                }
            }
        }
    }
)
async def cutoff_status():
    """
    Verifica se as dependências do sistema operacional (como o FFmpeg) estão 
    prontas para o processamento de mídia.
    """
    import subprocess
    try:
        subprocess.check_output(["ffmpeg", "-version"], stderr=subprocess.STDOUT)
        ffmpeg_ok = True
    except Exception:
        ffmpeg_ok = False
    
    return {
        "servico": "VideoSplitterFast",
        "ffmpeg": "disponivel" if ffmpeg_ok else "indisponivel",
        "formatos": ["9:16", "16:9"],
        "zoom": "0.5 a 2.0",
    }


@router.post(
    "/hook",
    summary="Extrai estritamente a introdução/gancho do vídeo",
    responses={
        200: {"description": "Gancho extraído com sucesso."},
        404: {"description": "O vídeo original não foi encontrado."},
        500: {"description": "Falha interna ao tentar gerar o gancho do vídeo."}
    }
)
async def extract_hook(
    video_path: str = Query(..., description="Caminho do arquivo de vídeo original"), 
    duration: int = Query(8, ge=1, le=30, description="Duração desejada do gancho em segundos")
):
    """
    Identifica e isola os momentos iniciais importantes baseando-se estritamente
    na análise do primeiro bloco de clipe reduzido do pipeline.
    """
    video = Path(video_path)
    
    if not video.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="O arquivo de vídeo informado não existe no servidor."
        )
    
    try:
        splitter = VideoSplitterFast(
            base_dir=ROOT_DIR / "processed_videos" / "raw_clips",
            output_format="9:16",
            zoom_factor=1.15,
        )
        
        # Cria uma amostragem inicial rápida em formato de clipe
        clipes_temporarios = splitter.split_all_clips(
            video_path=str(video),
            clip_duration=60,  # Amostragem enxuta de 1 minuto em vez de processar o vídeo bruto inteiro
            num_clips=1,
            start_offset=0,
            apply_transform=False
        )
        
        if clipes_temporarios:
            clipes_json = splitter.base_dir / f"{video.stem}_clipes.json"
            
            # Executa a busca mapeada com Whisper dinâmico
            hook = await splitter.extract_hook_from_clips_json(
                clips_json_path=str(clipes_json),
                moment_duration=duration,
            )
            
            if hook:
                return {"status": "concluido", "gancho": hook}
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="O sistema não conseguiu gerar um gancho válido para este vídeo."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao extrair gancho: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Erro interno ao extrair a introdução do vídeo."
        )