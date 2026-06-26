#!/usr/bin/env python3
"""
📹 Transcriptor Rápido de Vídeos
───────────────────────────────────────────────
Transcreve vídeos com timestamps e salva em JSON.
Otimizado com extração de áudio e processamento em lote.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional

# ── Configuração de Path ──────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from src.controllers.whisper.model import model
    from src.utils.logs import logger
    from src.utils.time_log import time_for_logs
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    def time_for_logs():
        import time

        return time.strftime("%H:%M:%S")


class FastTranscriptor:
    """
    Transcrição rápida de vídeos com timestamps.
    Extrai áudio, transcreve com Whisper e salva em JSON.
    """

    def __init__(
        self,
        model_size: str = "base",
        language: str = "pt",
        output_dir: Optional[Path] = None,
        keep_audio: bool = False,
        device: str = "cpu",
    ):
        """
        Inicializa o transcriptor.

        Args:
            model_size: Tamanho do modelo Whisper (tiny, base, small, medium)
            language: Idioma do áudio (pt, en, es, etc.)
            output_dir: Diretório de saída (padrão: pasta do vídeo)
            keep_audio: Manter arquivo de áudio extraído
            device: Dispositivo para processamento (cpu ou cuda)
        """
        self.model_size = model_size
        self.language = language
        self.output_dir = output_dir
        self.keep_audio = keep_audio
        self.device = device

        self._whisper = None
        self._ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        """Verifica se o FFmpeg está disponível"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ FFmpeg não encontrado! Instale: sudo apt install ffmpeg")
            return False

    def _get_whisper(self):
        """Obtém instância do Whisper (lazy loading)"""
        if self._whisper is None:
            print(f"📥 Carregando modelo Whisper: {self.model_size}...")
            self._whisper = model()
        return self._whisper

    def extract_audio(self, video_path: Path) -> Optional[Path]:
        """
        Extrai o áudio do vídeo para um arquivo WAV.

        Args:
            video_path: Caminho do vídeo

        Returns:
            Caminho do arquivo de áudio extraído
        """
        if not self._ffmpeg_available:
            return None

        # Cria arquivo temporário
        audio_path = video_path.parent / f"{video_path.stem}_audio_temp.wav"

        print(f"🎵 Extraindo áudio: {video_path.name}")

        # Comando FFmpeg otimizado
        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vn",  # Sem vídeo
            "-acodec",
            "pcm_s16le",  # Codec WAV
            "-ar",
            "16000",  # Taxa de amostragem (16kHz)
            "-ac",
            "1",  # Mono
            "-y",  # Sobrescrever
            str(audio_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300,  # 5 minutos
            )

            if result.returncode == 0 and audio_path.exists():
                size_mb = audio_path.stat().st_size / (1024 * 1024)
                print(f"✅ Áudio extraído: {audio_path.name} ({size_mb:.1f} MB)")
                return audio_path
            else:
                print(f"❌ Erro ao extrair áudio: {result.stderr[:200]}")
                return None

        except subprocess.TimeoutExpired:
            print("❌ Timeout na extração de áudio")
            return None
        except Exception as e:
            print(f"❌ Erro: {e}")
            return None

    def transcribe(self, audio_path: Path, word_timestamps: bool = True) -> List[Dict]:
        """
        Transcreve o áudio e retorna segmentos com timestamps.

        Args:
            audio_path: Caminho do arquivo de áudio
            word_timestamps: Incluir timestamps por palavra

        Returns:
            Lista de segmentos com texto e timestamps
        """
        print(f"🎙️ Transcrevendo: {audio_path.name}")

        whisper = self._get_whisper()

        # Configurações otimizadas
        segments, info = whisper.transcribe(
            str(audio_path),
            beam_size=3,  # Menos beam = mais rápido
            language=self.language,
            task="transcribe",
            vad_filter=True,  # Filtra silêncio (mais rápido)
            vad_parameters=dict(
                threshold=0.5, min_speech_duration_ms=250, min_silence_duration_ms=100
            ),
            word_timestamps=word_timestamps,
            condition_on_previous_text=False,
        )

        result = []
        for segment in segments:
            # Verifica se tem palavras individuais
            if hasattr(segment, "words") and segment.words:
                for word in segment.words:
                    if hasattr(word, "start") and hasattr(word, "end"):
                        result.append(
                            {
                                "start": round(word.start, 2),
                                "end": round(word.end, 2),
                                "text": word.word.strip(),
                                "type": "word",
                            }
                        )
            else:
                # Fallback: texto do segmento
                result.append(
                    {
                        "start": round(segment.start, 2),
                        "end": round(segment.end, 2),
                        "text": segment.text.strip(),
                        "type": "segment",
                    }
                )

        print(f"✅ Transcrição concluída: {len(result)} palavras/segmentos")
        return result

    def format_timestamp(self, seconds: float) -> str:
        """Formata segundos para MM:SS ou HH:MM:SS"""
        td = timedelta(seconds=seconds)
        total = int(td.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60

        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def format_transcription(self, segments: List[Dict]) -> str:
        """
        Formata a transcrição para texto legível com timestamps.

        Args:
            segments: Lista de segmentos do transcriptor

        Returns:
            Texto formatado com timestamps
        """
        lines = []
        last_end = 0
        current_text = []
        current_start = None

        for seg in segments:
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            text = seg.get("text", "")

            # Agrupa palavras em frases (se for word-level)
            if seg.get("type") == "word":
                if current_start is None:
                    current_start = start
                current_text.append(text)

                # Quebra a cada 5-10 palavras ou pausa > 0.3s
                if len(current_text) >= 8 or (start - last_end) > 0.3:
                    phrase = " ".join(current_text)
                    lines.append(f"[{self.format_timestamp(current_start)}] {phrase}")
                    current_text = []
                    current_start = None
            else:
                # Segmento já é uma frase
                lines.append(f"[{self.format_timestamp(start)}] {text}")

            last_end = end

        # Adiciona texto restante
        if current_text:
            phrase = " ".join(current_text)
            lines.append(f"[{self.format_timestamp(current_start or 0)}] {phrase}")

        return "\n".join(lines)

    def process_video(
        self,
        video_path: Path,
        save_json: bool = True,
        save_text: bool = True,
        word_timestamps: bool = True,
    ) -> Dict:
        """
        Processa um vídeo completo: extrai áudio, transcreve e salva.

        Args:
            video_path: Caminho do vídeo
            save_json: Salvar JSON com resultados
            save_text: Salvar TXT formatado
            word_timestamps: Incluir timestamps por palavra

        Returns:
            Dicionário com resultados da transcrição
        """
        print("\n" + "=" * 60)
        print(f"🎬 TRANSCREVENDO: {video_path.name}")
        print("=" * 60)

        if not video_path.exists():
            print(f"❌ Vídeo não encontrado: {video_path}")
            return {"error": "Arquivo não encontrado"}

        if not self._ffmpeg_available:
            return {"error": "FFmpeg não disponível"}

        # ── Extrai áudio ──
        audio_path = self.extract_audio(video_path)
        if audio_path is None:
            return {"error": "Falha na extração de áudio"}

        try:
            # ── Transcrição ──
            segments = self.transcribe(audio_path, word_timestamps)

            if not segments:
                return {"error": "Nenhuma fala detectada"}

            # ── Formata resultados ──
            text_formatted = self.format_transcription(segments)

            # ── Prepara resultado ──
            result = {
                "video": str(video_path),
                "video_name": video_path.name,
                "duration": float(video_path.stat().st_size),
                "model": self.model_size,
                "language": self.language,
                "total_segments": len(segments),
                "segments": segments,
                "text": text_formatted,
                "full_text": " ".join([s.get("text", "") for s in segments]),
            }

            # ── Salva arquivos ──
            output_dir = self.output_dir or video_path.parent
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            base_name = video_path.stem

            if save_json:
                json_path = output_dir / f"{base_name}_transcricao.json"
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"💾 JSON salvo: {json_path}")

            if save_text:
                txt_path = output_dir / f"{base_name}_transcricao.txt"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(f"=== TRANSCRIÇÃO: {video_path.name} ===\n\n")
                    f.write(text_formatted)
                    f.write(f"\n\n--- FIM DA TRANSCRIÇÃO ---\n")
                print(f"💾 TXT salvo: {txt_path}")

            # ── Limpa áudio temporário ──
            if not self.keep_audio and audio_path.exists():
                audio_path.unlink()
                print(f"🗑️ Áudio temporário removido: {audio_path.name}")

            print("\n" + "=" * 60)
            print(f"✅ TRANSCRIÇÃO CONCLUÍDA!")
            print(f"   📊 Segmentos: {len(segments)}")
            print(
                f"   📝 Palavras: {len([s for s in segments if s.get('type') == 'word'])}"
            )
            print("=" * 60)

            return result

        except Exception as e:
            print(f"❌ Erro durante transcrição: {e}")
            import traceback

            traceback.print_exc()

            # Limpa áudio em caso de erro
            if audio_path.exists() and not self.keep_audio:
                audio_path.unlink()

            return {"error": str(e)}

    def process_batch(
        self, video_paths: List[Path], max_workers: int = 2
    ) -> List[Dict]:
        """
        Processa múltiplos vídeos em paralelo.

        Args:
            video_paths: Lista de caminhos de vídeos
            max_workers: Número máximo de workers paralelos

        Returns:
            Lista de resultados
        """
        print(f"\n📦 Processando lote de {len(video_paths)} vídeos")
        print("=" * 60)

        results = []

        # Processa em paralelo com ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for video_path in video_paths:
                future = executor.submit(self.process_video, video_path)
                futures.append((video_path, future))

            for video_path, future in futures:
                try:
                    result = future.result(timeout=600)  # 10 minutos por vídeo
                    results.append(result)
                except Exception as e:
                    print(f"❌ Erro ao processar {video_path.name}: {e}")
                    results.append({"error": str(e), "video": str(video_path)})

        # Salva relatório do lote
        if results:
            report_path = self.output_dir or video_paths[0].parent
            report_path = Path(report_path) / "transcricao_lote.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Relatório do lote: {report_path}")

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Transcrição rápida de vídeos com timestamps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Transcrever um vídeo
  python transcriptor.py video.mp4
  
  # Transcrever com modelo small e salvar em outra pasta
  python transcriptor.py video.mp4 --model small --output ./transcricoes
  
  # Transcrever múltiplos vídeos
  python transcriptor.py video1.mp4 video2.mp4 video3.mp4 --workers 2
  
  # Transcrever mantendo arquivo de áudio
  python transcriptor.py video.mp4 --keep-audio
        """,
    )

    parser.add_argument("videos", nargs="+", help="Caminhos dos vídeos a transcrever")
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium"],
        help="Modelo Whisper (padrão: base)",
    )
    parser.add_argument("--language", default="pt", help="Idioma do áudio (padrão: pt)")
    parser.add_argument("--output", help="Diretório de saída (padrão: pasta do vídeo)")
    parser.add_argument(
        "--keep-audio", action="store_true", help="Manter arquivo de áudio extraído"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Número de workers para processamento paralelo (padrão: 1)",
    )
    parser.add_argument(
        "--no-word-timestamps",
        action="store_true",
        help="Desativar timestamps por palavra (mais rápido)",
    )
    parser.add_argument(
        "--no-json", action="store_true", help="Não salvar arquivo JSON"
    )
    parser.add_argument("--no-text", action="store_true", help="Não salvar arquivo TXT")

    args = parser.parse_args()

    # ── Configuração ──
    output_dir = Path(args.output) if args.output else None
    video_paths = [Path(v) for v in args.videos]

    # ── Inicializa transcriptor ──
    transcriptor = FastTranscriptor(
        model_size=args.model,
        language=args.language,
        output_dir=output_dir,
        keep_audio=args.keep_audio,
    )

    # ── Processa ──
    if len(video_paths) == 1:
        # Vídeo único
        result = transcriptor.process_video(
            video_paths[0],
            save_json=not args.no_json,
            save_text=not args.no_text,
            word_timestamps=not args.no_word_timestamps,
        )

        # Mostra preview
        if "text" in result:
            print("\n📝 PREVIEW DA TRANSCRIÇÃO:")
            print("-" * 40)
            lines = result["text"].split("\n")[:10]
            print("\n".join(lines))
            if len(result["text"].split("\n")) > 10:
                print("... (continua)")

    else:
        # Múltiplos vídeos
        results = transcriptor.process_batch(video_paths, max_workers=args.workers)

        # Resumo
        print("\n📊 RESUMO DO LOTE:")
        print("-" * 40)
        for i, result in enumerate(results, 1):
            video = result.get("video_name", f"Vídeo {i}")
            if "error" in result:
                print(f"  ❌ {video}: {result['error']}")
            else:
                print(f"  ✅ {video}: {result.get('total_segments', 0)} segmentos")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Processamento interrompido pelo usuário.")
        sys.exit(0)
