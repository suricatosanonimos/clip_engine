#!/usr/bin/env python3
"""
src/utils/brain_selector.py

Fase 2: Analisa os clipes com IA e seleciona os melhores momentos.
Lê clipes de raw_clips/, transcreve com Whisper de forma dinâmica e leve,
e usa BestMoments para análise focada nos pedaços cortados.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.controllers.highlight.best_moments import BestMoments
from src.controllers.whisper.model import model
from src.utils.logs import logger


class BrainSelector:
    """
    Analisa clipes de vídeo curtíssimos com IA para selecionar os melhores momentos.
    Focado 100% em velocidade, ignorando completamente o vídeo bruto original.
    """

    def __init__(self):
        self.best_moments = BestMoments()
        self.whisper_instance = None

        self.raw_clips_dir = ROOT_DIR / "processed_videos" / "raw_clips"
        self.transcriptions_dir = ROOT_DIR / "processed_videos" / "transcriptions"
        self.moments_dir = ROOT_DIR / "processed_videos" / "moments"

        self.transcriptions_dir.mkdir(parents=True, exist_ok=True)
        self.moments_dir.mkdir(parents=True, exist_ok=True)

    def _get_whisper(self):
        if self.whisper_instance is None:
            self.whisper_instance = model()
        return self.whisper_instance

    def _find_clips(self, video_base_name: Optional[str] = None) -> List[Dict]:
        """Encontra os clipes pré-cortados na pasta para análise."""
        clipes = []
        json_patterns = ["*_clipes.json", "*_final.json"]
        if video_base_name:
            json_patterns = [
                f"{video_base_name}_clipes.json",
                f"{video_base_name}_final.json",
            ]

        for pattern in json_patterns:
            for json_file in self.raw_clips_dir.glob(pattern):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        if "path" in data[0]:
                            logger.info(f"📁 Loaded {len(clipes)} clips from {json_file.name}")
                            return data
                except Exception as e:
                    logger.warning(f"⚠️  Error reading {json_file.name}: {e}")

        # Fallback: scan de arquivos .mp4 cortados (ignora ganchos antigos)
        mp4_files = sorted(self.raw_clips_dir.glob("*.mp4"))
        for mp4 in mp4_files:
            if "_hook" in mp4.name or "_final" in mp4.name:
                continue

            try:
                import subprocess
                cmd = [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(mp4)
                ]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                duration = float(result.stdout.strip())
            except Exception:
                duration = 0

            clipes.append({
                "clip_id": len(clipes) + 1,
                "filename": mp4.name,
                "path": str(mp4),
                "start": 0,
                "end": duration,
                "duration": duration,
            })

        if clipes:
            logger.info(f"📁 Found {len(clipes)} clips via .mp4 scan")
        return clipes

    async def transcribe_clip(self, video_path: Path, max_duration: Optional[float] = None) -> List[Dict]:
        """Transcreve o clipe limitando o áudio estritamente ao tamanho dele + margem."""
        logger.info(f"🎙️ Transcribing: {video_path.name}")
        if max_duration:
            logger.info(f"⏱️ Whisper processing limit: {max_duration:.1f}s")

        whisper_instance = self._get_whisper()
        loop = asyncio.get_event_loop()

        try:
            segments, _ = await loop.run_in_executor(
                None,
                lambda: whisper_instance.transcribe(
                    str(video_path),
                    beam_size=5,
                    word_timestamps=True,
                    best_of=5,
                    language="pt",
                    initial_prompt="Áudio em português do Brasil",
                    temperature=0.0,
                    condition_on_previous_text=False,
                    clip_duration=max_duration  # 🔥 Aplica a restrição de tempo dinamicamente!
                ),
            )

            frases = []
            texto_atual = ""
            start_atual = None

            for segment in segments:
                if hasattr(segment, "words") and segment.words:
                    for word in segment.words:
                        if start_atual is None:
                            start_atual = word.start
                        texto_atual += " " + word.word

                        if texto_atual.strip().endswith((".", "!", "?")):
                            frases.append({
                                "start": start_atual,
                                "end": word.end,
                                "text": texto_atual.strip(),
                            })
                            texto_atual = ""
                            start_atual = None

            if texto_atual.strip():
                frases.append({
                    "start": start_atual or 0,
                    "end": segment.end if hasattr(segment, "end") else 0,
                    "text": texto_atual.strip(),
                })

            return frases

        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            return []

    async def analyze_clip(self, clipe: Dict) -> Dict:
        """Analisa o clipe individual focado no gancho interno."""
        video_path = Path(clipe["path"])

        if not video_path.exists():
            logger.warning(f"❌ File not found: {video_path}")
            clipe["analysis"] = "error"
            clipe["interesting"] = False
            clipe["score"] = 0
            return clipe

        # 🧠 REGRA DE SEGURANÇA: Duração do clipe + 20 segundos de margem
        duracao_clipe = clipe.get("duration", 0)
        limite_whisper = duracao_clipe + 20.0 if duracao_clipe > 0 else None

        # Transcrever apenas a dimensão real do clipe
        frases = await self.transcribe_clip(video_path, max_duration=limite_whisper)

        if not frases:
            logger.warning(f"⚠️ No speech in: {video_path.name}")
            clipe["analysis"] = "no_speech"
            clipe["interesting"] = False
            clipe["score"] = 0
            return clipe

        # Salvar transcrição local do clipe
        transcription_data = {
            "video": str(video_path),
            "video_name": video_path.stem,
            "duration": duracao_clipe,
            "segments": frases,
            "total_segments": len(frases),
        }

        transcription_path = self.transcriptions_dir / f"{video_path.stem}_transcription.json"
        with open(transcription_path, "w", encoding="utf-8") as f:
            json.dump(transcription_data, f, ensure_ascii=False, indent=2)

        clipe["transcription_path"] = str(transcription_path)
        clipe["transcription_segments"] = len(frases)

        # Encontrar momentos interessantes APENAS dentro desta janela curta
        try:
            resultado = self.best_moments.find_best_moments(frases, duracao_clipe)

            if resultado and isinstance(resultado, dict):
                momentos = resultado.get("moments", [])
                if momentos and len(momentos) > 0:
                    clipe["analysis"] = "interesting"
                    clipe["interesting"] = True
                    clipe["moments"] = momentos
                    clipe["score"] = len(momentos)
                else:
                    clipe["analysis"] = "no_interest"
                    clipe["interesting"] = False
                    clipe["score"] = 0
            else:
                clipe["analysis"] = "no_interest"
                clipe["interesting"] = False
                clipe["score"] = 0

        except Exception as e:
            logger.error(f"❌ AI analysis error: {e}")
            clipe["analysis"] = "ai_error"
            clipe["interesting"] = False
            clipe["score"] = 0

        return clipe

    async def select_best_clips(self, clipes_json_path: str = None, video_base_name: str = None) -> List[Dict]:
        """Carrega e executa a análise veloz em cima da lista de clipes curtos."""
        if clipes_json_path and Path(clipes_json_path).exists():
            with open(clipes_json_path, "r", encoding="utf-8") as f:
                clipes = json.load(f)
        else:
            clipes = self._find_clips(video_base_name)

        if not clipes:
            logger.warning("⚠️ No clips to analyze")
            return []

        print(f"\n{'='*60}")
        print(f"🧠 FAST BRAIN SELECTOR - Focado 100% em Clipes Curtos")
        print(f"{'='*60}")

        resultados = []
        for i, clipe in enumerate(clipes, 1):
            print(f"\n🔍 Clip {i}/{len(clipes)}: {clipe.get('filename', 'unknown')}")
            resultado = await self.analyze_clip(clipe)
            resultados.append(resultado)

            if resultado.get("interesting"):
                print(f"   ✅ Clip Válido! Score: {resultado.get('score', 0)}")
            else:
                print(f"   ⏩ Ignorado ({resultado.get('analysis', 'unknown')})")

        # Ordenação inteligente
        selecionados = [r for r in resultados if r.get("interesting")]
        selecionados.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Salva relatórios de tracking
        base_name = video_base_name or "analysis"
        if clipes and "filename" in clipes[0]:
            base_name = clipes[0]["filename"].split("_clip_")[0]

        with open(self.moments_dir / f"{base_name}_analysis.json", "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)

        with open(self.moments_dir / f"{base_name}_selected.json", "w", encoding="utf-8") as f:
            json.dump(selecionados, f, ensure_ascii=False, indent=2)

        return selecionados