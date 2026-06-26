#!/usr/bin/env python3
"""
src/utils/brain_selector.py

Fase 2: Analisa os clipes com IA e seleciona os melhores momentos.
Lê clipes de raw_clips/, transcreve com Whisper, e usa BestMoments para análise.
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
    Analisa clipes de vídeo com IA para selecionar os melhores momentos.

    Suporta:
    - JSON de clipes (*_clipes.json, *_final.json)
    - Scan direto de arquivos .mp4 na pasta
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
        """
        Encontra clipes para analisar.

        Prioridade:
        1. JSON *_clipes.json ou *_final.json
        2. Scan de arquivos .mp4 na pasta
        """
        clipes = []

        # Tenta JSON primeiro
        json_patterns = ["*_clipes.json", "*_final.json"]
        if video_base_name:
            json_patterns = [
                f"{video_base_name}_clipes.json",
                f"{video_base_name}_final.json",
                f"{video_base_name}_clipes.json",
            ]

        for pattern in json_patterns:
            for json_file in self.raw_clips_dir.glob(pattern):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        # Verifica se tem campo 'path'
                        if "path" in data[0]:
                            clipes = data
                            logger.info(
                                f"📁 Loaded {len(clipes)} clips from {json_file.name}"
                            )
                            return clipes
                except Exception as e:
                    logger.warning(f"⚠️  Error reading {json_file.name}: {e}")

        # Fallback: scan de arquivos .mp4 (exclui _hook e _final)
        mp4_files = sorted(self.raw_clips_dir.glob("*.mp4"))
        for mp4 in mp4_files:
            # Pula ganchos e finais (já processados)
            if "_hook" in mp4.name or "_final" in mp4.name:
                continue

            # Obtém info do vídeo
            try:
                import subprocess

                cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(mp4),
                ]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                )
                duration = float(result.stdout.strip())
            except Exception:
                duration = 0

            clipes.append(
                {
                    "clip_id": len(clipes) + 1,
                    "filename": mp4.name,
                    "path": str(mp4),
                    "start": 0,
                    "end": duration,
                    "duration": duration,
                }
            )

        if clipes:
            logger.info(f"📁 Found {len(clipes)} clips via .mp4 scan")

        return clipes

    async def transcribe_clip(self, video_path: Path) -> List[Dict]:
        """Transcreve um clipe e retorna frases com timestamps."""
        logger.info(f"🎙️ Transcribing: {video_path.name}")

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
                            frases.append(
                                {
                                    "start": start_atual,
                                    "end": word.end,
                                    "text": texto_atual.strip(),
                                }
                            )
                            texto_atual = ""
                            start_atual = None
                        elif hasattr(word, "end") and len(texto_atual.strip()) > 10:
                            # Pausa > 0.5s = nova frase
                            pass  # Simplificado: usa só pontuação

            if texto_atual.strip():
                frases.append(
                    {
                        "start": start_atual or 0,
                        "end": segment.end if hasattr(segment, "end") else 0,
                        "text": texto_atual.strip(),
                    }
                )

            return frases

        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            return []

    async def analyze_clip(self, clipe: Dict) -> Dict:
        """Analisa um clipe: transcreve e usa IA para encontrar momentos."""
        video_path = Path(clipe["path"])

        if not video_path.exists():
            logger.warning(f"❌ File not found: {video_path}")
            clipe["analysis"] = "error"
            clipe["interesting"] = False
            clipe["score"] = 0
            return clipe

        # Transcrever
        frases = await self.transcribe_clip(video_path)

        if not frases:
            logger.warning(f"⚠️ No speech in: {video_path.name}")
            clipe["analysis"] = "no_speech"
            clipe["interesting"] = False
            clipe["score"] = 0
            return clipe

        # Salvar transcrição
        transcription_data = {
            "video": str(video_path),
            "video_name": video_path.stem,
            "duration": clipe.get("duration", 0),
            "segments": frases,
            "total_segments": len(frases),
        }

        transcription_path = (
            self.transcriptions_dir / f"{video_path.stem}_transcription.json"
        )
        with open(transcription_path, "w", encoding="utf-8") as f:
            json.dump(transcription_data, f, ensure_ascii=False, indent=2)

        clipe["transcription_path"] = str(transcription_path)
        clipe["transcription_segments"] = len(frases)

        # Analisar com IA
        try:
            resultado = self.best_moments.find_best_moments(
                frases, clipe.get("duration", 0)
            )

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

    async def select_best_clips(
        self, clipes_json_path: str = None, video_base_name: str = None
    ) -> List[Dict]:
        """
        Carrega clipes, transcreve, analisa e seleciona os melhores.

        Args:
            clipes_json_path: Caminho para JSON (opcional)
            video_base_name: Nome base para busca automática

        Returns:
            Lista de clipes selecionados
        """
        # Encontra clipes
        if clipes_json_path and Path(clipes_json_path).exists():
            with open(clipes_json_path, "r", encoding="utf-8") as f:
                clipes = json.load(f)
        else:
            clipes = self._find_clips(video_base_name)

        if not clipes:
            logger.warning("⚠️ No clips to analyze")
            return []

        print(f"\n{'='*60}")
        print(f"🧠 BRAIN SELECTOR - Analyzing {len(clipes)} clips with AI")
        print(f"{'='*60}")
        print(f"📁 Raw clips: {self.raw_clips_dir}")
        print(f"📁 Transcriptions: {self.transcriptions_dir}")
        print(f"📁 Moments: {self.moments_dir}")
        print("-" * 60)

        resultados = []
        for i, clipe in enumerate(clipes, 1):
            print(f"\n🔍 Clip {i}/{len(clipes)}: {clipe.get('filename', 'unknown')}")
            resultado = await self.analyze_clip(clipe)
            resultados.append(resultado)

            if resultado.get("interesting"):
                score = resultado.get("score", 0)
                moments_count = len(resultado.get("moments", []))
                print(f"   ✅ INTERESTING (score: {score}, moments: {moments_count})")
            else:
                motivo = resultado.get("analysis", "unknown")
                print(f"   ⏩ Skipping ({motivo})")

        # Filtra e ordena
        selecionados = [r for r in resultados if r.get("interesting")]
        selecionados.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Salva resultados
        base_name = video_base_name or "analysis"
        if clipes and "filename" in clipes[0]:
            base_name = clipes[0]["filename"].split("_clip_")[0]

        analysis_path = self.moments_dir / f"{base_name}_analysis.json"
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)

        selected_path = self.moments_dir / f"{base_name}_selected.json"
        with open(selected_path, "w", encoding="utf-8") as f:
            json.dump(selecionados, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"✅ ANALYSIS COMPLETED")
        print(f"{'='*60}")
        print(f"   📊 Total: {len(resultados)} | 🎯 Selected: {len(selecionados)}")
        print(f"   💾 {analysis_path}")
        print(f"   💾 {selected_path}")

        return selecionados


async def main():
    import sys

    try:
        whisper_instance = model()
        print("✅ Whisper available!")
    except Exception as e:
        print(f"❌ Error loading Whisper: {e}")
        sys.exit(1)

    selector = BrainSelector()

    if not selector.raw_clips_dir.exists():
        print(f"❌ Raw clips directory not found: {selector.raw_clips_dir}")
        sys.exit(1)

    # Procura JSONs
    json_files = list(selector.raw_clips_dir.glob("*_clipes.json")) + list(
        selector.raw_clips_dir.glob("*_final.json")
    )

    print("=" * 60)
    print("🧠 FASE 2: Brain Selector - Analyzing clips with AI")
    print("=" * 60)

    if json_files:
        print(f"\n📁 Available JSONs:")
        for i, jf in enumerate(json_files, 1):
            print(f"   {i}. {jf.name}")

        if len(json_files) == 1:
            clipes_json = json_files[0]
        else:
            try:
                choice = int(
                    input(f"\n🔢 Choose (1-{len(json_files)}): ").strip() or "1"
                )
                clipes_json = json_files[choice - 1]
            except (ValueError, IndexError):
                clipes_json = json_files[0]

        print(f"\n📁 Selected: {clipes_json.name}")
        selecionados = await selector.select_best_clips(str(clipes_json))
    else:
        # Tenta scan direto de .mp4
        print(f"\n⚠️  No JSON found, scanning .mp4 files...")
        selecionados = await selector.select_best_clips()

    if selecionados:
        print(f"\n{'='*60}")
        print(f"🏆 SELECTED CLIPS")
        print(f"{'='*60}")
        for i, clip in enumerate(selecionados, 1):
            print(f"\n   {i}. {clip.get('filename', 'unknown')}")
            print(
                f"      Score: {clip.get('score', 0)} | Moments: {len(clip.get('moments', []))}"
            )
            for m in clip.get("moments", [])[:2]:
                print(
                    f"      🎯 [{m.get('start',0)}s-{m.get('end',0)}s] {m.get('text','')[:60]}..."
                )
    else:
        print("\n⚠️ No interesting clips found.")


if __name__ == "__main__":
    asyncio.run(main())
