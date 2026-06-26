"""
src/controllers/whisper/__init__.py

Carregamento do modelo Whisper para transcrição de áudio.
"""

from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel
from src.utils.logs import logger

# Configuração
CACHE_DIR = Path.home() / ".cache" / "whisper-models"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Singleton
_MODEL = None


def load_model(model_size: str = "base") -> WhisperModel:
    """Carrega (ou retorna em cache) o modelo Whisper"""
    global _MODEL

    if _MODEL is not None:
        logger.debug(f"Reutilizando modelo já carregado: {model_size}")
        return _MODEL

    logger.info(f"Carregando modelo Whisper: {model_size} (primeira vez pode demorar)")

    try:
        _MODEL = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=str(CACHE_DIR),
            local_files_only=False,  # Permite download se não existir
        )
        logger.info(f"✅ Modelo carregado com sucesso: {model_size}")
        return _MODEL
    except Exception as e:
        logger.error(f"❌ Erro ao carregar modelo {model_size}: {e}")
        raise


def get_model(model_size: Optional[str] = None) -> WhisperModel:
    """Interface pública para obter o modelo"""
    return load_model(model_size or "base")


# Para compatibilidade
model = get_model
