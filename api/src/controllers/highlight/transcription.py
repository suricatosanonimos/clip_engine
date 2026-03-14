import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from src.services.brain_IA import Brain

# Configuração de caminhos
# ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
# sys.path.append(str(ROOT_DIR))
from src.utils.logs import logger


class TranscriptionEngine:
    def __init__(self, model_size: str = "tiny"):
        self._model = None
        self.model_size = model_size
        self.cache_dir = os.path.expanduser("~/.cache/whisper-models/")
        os.makedirs(self.cache_dir, exist_ok=True)

    @property
    def model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info(f"Carregando Whisper {self.model_size}...")
            self._model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
                download_root=self.cache_dir,
            )
        return self._model

    async def get_video_duration(self, video_path: Path) -> float:
        """Obtém a duração total do vídeo usando ffprobe."""
        import subprocess

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return float(result.stdout)

    async def transcribe_to_json(self, video_path: str) -> List[Dict]:
        path = Path(video_path)
        if not path.exists():
            logger.error(f"Arquivo não encontrado: {video_path}")
            return []

        logger.info(f"Transcrevendo: {path.name}")
        loop = asyncio.get_event_loop()

        segments, _ = await loop.run_in_executor(
            None,
            lambda: self.model.transcribe(
                str(path), beam_size=5, word_timestamps=True, language="pt"
            ),
        )

        return [
            {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in segments
        ]


async def process_video_with_ai(video_input: str):
    """
    Fluxo Completo: Transcreve o vídeo e envia os dados para a Brain IA selecionar momentos.
    """
    engine = TranscriptionEngine(model_size="tiny")
    brain = Brain()  # Instancia a sua IA

    path = Path(video_input)

    # 1. Obter duração total (importante para a IA ter contexto)
    try:
        duracao_total = await engine.get_video_duration(path)
    except Exception:
        duracao_total = 0.0

    # 2. Gerar Transcrição
    transcricao = await engine.transcribe_to_json(video_input)

    if not transcricao:
        logger.error("Falha na transcrição. Abortando.")
        return

    logger.info(
        f"Transcrição concluída ({len(transcricao)} segmentos). Enviando para Brain IA..."
    )

    # 3. Passar conteúdo para a IA
    # O método 'encontrar_melhores_momentos' já espera a lista de dicts
    melhores_momentos = brain.encontrar_melhores_momentos(transcricao, duracao_total)

    # 4. Salvar o resultado final da IA
    output_path = path.with_name(f"ai_analysis_{path.stem}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(melhores_momentos, f, ensure_ascii=False, indent=2)

    logger.info(f"✨ Análise da IA completa! Salva em: {output_path}")
    return melhores_momentos
