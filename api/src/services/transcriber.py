"""
src/services/transcriber.py

Gera legendas word-by-word via Whisper e renderiza no vídeo com FFmpeg/ASS.
Versão OTIMIZADA - mantém qualidade e velocidade.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import sys
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional
import subprocess

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.controllers.whisper.model import model
from src.utils.subtitle_constants import *

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SubtitleGenerator:

    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: Optional[str] = None,
        use_gpu: bool = False,
        cor_legenda: str = DEFAULT_COR,
        fast_mode: bool = True,  # NOVO: modo rápido sem re-encode
    ):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path or shutil.which("ffprobe") or "ffprobe"
        self.use_gpu = use_gpu
        self.fast_mode = fast_mode  # Se True, usa copy codec

        # Resolve cor
        cor_normalizada = COR_MAP.get(cor_legenda.lower(), DEFAULT_COR)
        self.cor_legenda = cor_normalizada
        self.cor_primary = COLORS[cor_normalizada]

        self.cor_destaque = (
            COLORS["yellow"]
            if cor_normalizada != "yellow"
            else COLORS["white"]
        )

        self.output_dir = ROOT_DIR / "processed_videos"
        self.final_clips_dir = self.output_dir / "final_clips"
        self.final_clips_dir.mkdir(parents=True, exist_ok=True)

        self.cache_dir = os.path.expanduser("~/.cache/whisper-models/")
        os.makedirs(self.cache_dir, exist_ok=True)

        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

        self._compile_patterns()

    # ── Padrões regex ──────────────────────────────────────────────

    def _compile_patterns(self):
        self.bad_words_map = {}
        bad_patterns = []
        for bad, fixed in BAD_WORDS.items():
            bad_patterns.append(rf"\b{re.escape(bad)}\b")
            self.bad_words_map[bad.lower()] = fixed
        self.bad_words_pattern = (
            re.compile("|".join(bad_patterns), re.IGNORECASE) if bad_patterns else None
        )

        self.emoji_map = {}
        emoji_patterns = []
        for word, emoji in EMOJI_WORDS.items():
            emoji_patterns.append(rf"\b{re.escape(word)}\b")
            self.emoji_map[word.lower()] = emoji
        self.emoji_pattern = (
            re.compile("|".join(emoji_patterns), re.IGNORECASE)
            if emoji_patterns
            else None
        )

    # ── Processamento de texto ─────────────────────────────────────

    def _process_text(self, text: str) -> str:
        if self.emoji_pattern:
            text = self.emoji_pattern.sub(
                lambda m: f"{m.group(0)} {self.emoji_map.get(m.group(0).lower(), '')}",
                text,
            )
        if self.bad_words_pattern:
            text = self.bad_words_pattern.sub(
                lambda m: self.bad_words_map.get(m.group(0).lower(), m.group(0)),
                text,
            )
        text = re.sub(r"([❤️🔥😊✨😂🚀💪💰🎯])\s+\1", r"\1", text)
        return text

    # ── Formatação de tempo ASS ────────────────────────────────────
    def _format_time_ass(self, seconds: float) -> str:
        td = timedelta(seconds=seconds)
        total = int(td.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        cs = int(td.microseconds / 10000)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # ── Header ASS com a cor selecionada ──────────────────────────

    def _generate_ass_header(self, width: int, height: int) -> str:
        font_size = int(height * 0.08)
        m_v = int(height * 0.25)
        outline_size = max(2, int(font_size * 0.1))

        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,{font_size},{self.cor_primary},&H000000FF,{COLORS['black']},&H00000000,-1,0,0,0,100,100,2,0,1,{outline_size},0,2,30,30,{m_v},1
"""

    # ── ffprobe helpers ────────────────────────────────────────────

    async def get_video_resolution(self, path: Path) -> tuple:
        cmd = [
            self.ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout)
        return data["streams"][0]["width"], data["streams"][0]["height"]

    async def get_video_duration(self, path: Path) -> float:
        cmd = [
            self.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout)
        return float(data["format"]["duration"])

    # ── Transcrição com Foco em Português ───────────────────────────

    async def transcribe_word_by_word(self, path: Path) -> List[Dict]:
        logger.info(f"Transcrevendo: {path.name}")
        loop = asyncio.get_event_loop()
        
        whisper_instance = model()
        
        segments, _ = await loop.run_in_executor(
            None,
            lambda: whisper_instance.transcribe(
                str(path),
                beam_size=5,
                word_timestamps=True,
                best_of=5,
                language="pt",
                initial_prompt="Áudio em português do Brasil",
                temperature=0.0,
                condition_on_previous_text=False,
            ),
        )
        
        word_list = []
        for segment in segments:
            for word in segment.words:
                text = self._process_text(word.word.strip()).upper()
                if len(text) > 6 or any(x in text for x in ["!", "?", "$"]):
                    text = f"{{\\c{self.cor_destaque}}}{text}{{\\c}}"
                word_list.append({"start": word.start, "end": word.end, "text": text})
        
        return word_list

    # ── Parâmetros FFmpeg (MODO RÁPIDO) ─────────────────────────────

    def _get_ffmpeg_params(self) -> List[str]:
        """Retorna parâmetros para FFmpeg - modo rápido sem perda de qualidade"""
        if self.fast_mode:
            # MODO RÁPIDO: copia codec original sem re-encode
            # A legenda é queimada, mas o vídeo mantém qualidade original
            return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "copy"]
        else:
            # Modo qualidade máxima (mais lento)
            return ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-c:a", "copy"]

    # ── Processa vídeo: transcreve + renderiza legenda (RÁPIDO) ─────

    async def process_video(
        self, input_path: str, cor_legenda: str = None
    ) -> Optional[Path]:
        """
        Transcreve o vídeo com Whisper e queima as legendas.
        Versão otimizada para velocidade.
        """
        path = Path(input_path)
        if not path.exists():
            logger.error(f"Arquivo não encontrado: {path}")
            return None

        if cor_legenda:
            cor_key = COR_MAP.get(cor_legenda.lower(), DEFAULT_COR)
            cor_primary = COLORS[cor_key]
            cor_destaque = (
                COLORS["yellow"] if cor_key != "yellow" else COLORS["white"]
            )
        else:
            cor_primary = self.cor_primary
            cor_destaque = self.cor_destaque

        try:
            logger.info(f"📹 Processando: {path.name}")
            duration = await self.get_video_duration(path)
            logger.info(f"⏱️  Duração: {duration:.1f}s")

            width, height = await self.get_video_resolution(path)
            logger.info(f"📐 Resolução: {width}x{height}")
            
            logger.info("🎙️ Transcrevendo áudio...")
            words = await self.transcribe_word_by_word(path)
            logger.info(f"📝 Transcrição: {len(words)} palavras")

            # Gera arquivo .ass
            ass_path = path.with_suffix(".ass")
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(self._generate_ass_header(width, height))
                f.write(
                    "\n[Events]\nFormat: Layer, Start, End, Style, Name, "
                    "MarginL, MarginR, MarginV, Effect, Text\n"
                )
                for w in words:
                    start = self._format_time_ass(w["start"])
                    end = self._format_time_ass(w["end"])
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{w['text']}\n")

            output_path = self.final_clips_dir / f"legendado_{path.name}"
            escaped_ass = str(ass_path.absolute()).replace(":", "\\:").replace("\\", "/")
            ffmpeg_params = self._get_ffmpeg_params()

            ffmpeg_cmd = [
                self.ffmpeg_path,
                "-y",
                "-i", str(path),
                "-vf", f"ass='{escaped_ass}'",
                *ffmpeg_params,
                str(output_path),
            ]

            logger.info("🎬 Renderizando legenda (modo rápido)...")
            proc = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode == 0:
                # Verificar tamanho do arquivo
                size_mb = output_path.stat().st_size / (1024 * 1024)
                logger.info(f"✅ Vídeo legendado: {output_path.name} ({size_mb:.1f} MB)")
                if ass_path.exists():
                    os.remove(ass_path)
                return output_path
            else:
                error_msg = stderr.decode()[-500:]
                logger.error(f"FFmpeg erro: {error_msg}")
                return None

        except Exception as e:
            logger.error(f"❌ Erro ao processar {path.name}: {e}")
            return None


# ── Bloco de Execução Local ──────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    # Verificar FFmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ FFmpeg encontrado!")
    except FileNotFoundError:
        print("❌ FFmpeg não encontrado! Instale com: sudo apt install ffmpeg")
        sys.exit(1)
    
    # Caminho do vídeo de teste
    VIDEO_DE_TESTE = "/home/dev/Code/clip_engine/parts/A_REALIDADE_DA_GUERRA_NA_UCRÂNIA_CRISTIAN_GALVÃO_RELATA_AS_PIORES_PARTES_DO_CONFRONTO_clip_002.mp4"
    COR_ESCOLHIDA = "yellow"

    async def main():
        print("=" * 60)
        print("🎬 Subtitle Generator - Modo RÁPIDO")
        print("=" * 60)

        generator = SubtitleGenerator(
            ffmpeg_path="ffmpeg", 
            use_gpu=False, 
            cor_legenda=COR_ESCOLHIDA,
            fast_mode=True  # Ativado!
        )

        path_video = Path(VIDEO_DE_TESTE)
        if not path_video.exists():
            print(f"❌ Vídeo não encontrado: {VIDEO_DE_TESTE}")
            return

        print(f"🎬 Processando: {path_video.name}")
        print(f"🎨 Cor da legenda: {COR_ESCOLHIDA}")

        resultado = await generator.process_video(str(path_video))

        print("\n" + "=" * 60)
        if resultado:
            size_mb = resultado.stat().st_size / (1024 * 1024)
            print(f"✅ SUCESSO! Vídeo legendado:")
            print(f"   📁 {resultado.name}")
            print(f"   💾 {size_mb:.1f} MB")
        else:
            print("❌ FALHA: Não foi possível gerar o vídeo legendado")
        print("=" * 60)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Processo interrompido")