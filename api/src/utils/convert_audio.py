#!/usr/bin/env python3
"""
src/utils/convert_audio.py

Converte arquivos de áudio entre formatos (MP3, WAV, M4A, etc).
Usa FFmpeg para conversão rápida.

Por padrão, lê arquivos de api/audio/voice/ e salva em api/audio/voice/wav/

Uso:
    python3 convert_audio.py                           # Converte todos .mp3 de voice/
    python3 convert_audio.py --input arquivo.mp3       # Converte um arquivo
    python3 convert_audio.py --whisper                 # Otimizado para Whisper
    python3 convert_audio.py --batch mp3 wav           # Converte todos de voice/
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, List

# ══════════════════════════════════════════════════════════════
#  CONFIGURAÇÃO DE DIRETÓRIOS
# ══════════════════════════════════════════════════════════════

ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # api/
AUDIO_DIR = ROOT_DIR / "audio"
VOICE_DIR = AUDIO_DIR / "voice"
MUSIC_DIR = AUDIO_DIR / "music"
WAV_DIR = VOICE_DIR / "wav"  # Saída dos arquivos convertidos

# Garante que diretórios existem
WAV_DIR.mkdir(parents=True, exist_ok=True)
MUSIC_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════
#  CONVERSOR
# ══════════════════════════════════════════════════════════════

class AudioConverter:
    """Conversor de áudio usando FFmpeg."""
    
    FORMATS = {
        "wav": {"codec": "pcm_s16le", "sample_rate": 44100},
        "mp3": {"codec": "libmp3lame", "bitrate": "192k"},
        "m4a": {"codec": "aac", "bitrate": "192k"},
        "ogg": {"codec": "libvorbis", "bitrate": "192k"},
        "flac": {"codec": "flac", "sample_rate": 44100},
    }
    
    def __init__(self, bitrate: str = "192k", sample_rate: int = 44100):
        self.bitrate = bitrate
        self.sample_rate = sample_rate
    
    def convert(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        fmt: str = "wav",
        bitrate: Optional[str] = None,
        sample_rate: Optional[int] = None,
    ) -> Optional[Path]:
        """Converte arquivo de áudio."""
        inp = Path(input_path)
        if not inp.exists():
            print(f"❌ Arquivo não encontrado: {input_path}")
            return None
        
        fmt = fmt.lower().lstrip(".")
        if fmt not in self.FORMATS:
            print(f"❌ Formato não suportado: {fmt}")
            return None
        
        out = Path(output_path) if output_path else WAV_DIR / f"{inp.stem}.{fmt}"
        br = bitrate or self.bitrate
        sr = sample_rate or self.sample_rate
        codec = self.FORMATS.get(fmt, {}).get("codec", "pcm_s16le")
        
        print(f"🎵 {inp.name} → {out.name} ({fmt}, {br}, {sr}Hz)")
        
        cmd = ["ffmpeg", "-i", str(inp), "-c:a", codec, "-ar", str(sr)]
        if fmt not in ("wav", "flac"):
            cmd.extend(["-b:a", br])
        cmd.extend(["-y", str(out)])
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            if out.exists() and out.stat().st_size > 0:
                size_mb = out.stat().st_size / (1024 * 1024)
                print(f"   ✅ {size_mb:.1f} MB")
                return out
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Erro: {e.stderr[-200:]}")
        
        return None
    
    def batch_convert(
        self,
        input_dir: Optional[str] = None,
        input_format: str = "mp3",
        output_format: str = "wav",
    ) -> List[Path]:
        """Converte todos os arquivos de uma pasta."""
        d = Path(input_dir) if input_dir else VOICE_DIR
        files = sorted(d.glob(f"*.{input_format}"))
        
        if not files:
            print(f"❌ Nenhum .{input_format} em: {d}")
            return []
        
        print(f"\n📁 {len(files)} arquivo(s) .{input_format} → .{output_format}")
        print(f"   De: {d}")
        print(f"   Para: {WAV_DIR}")
        print("-" * 50)
        
        converted = []
        for i, f in enumerate(files, 1):
            print(f"[{i}/{len(files)}]", end=" ")
            out = self.convert(str(f), fmt=output_format)
            if out:
                converted.append(out)
        
        print(f"\n✅ {len(converted)}/{len(files)} convertidos → {WAV_DIR}")
        return converted


# ══════════════════════════════════════════════════════════════
#  CONVERSÃO OTIMIZADA PARA WHISPER
# ══════════════════════════════════════════════════════════════

def convert_for_whisper(input_path: str, output_path: Optional[str] = None) -> Optional[Path]:
    """
    Converte áudio para formato ideal para Whisper.
    - Mono, 16kHz, PCM 16-bit
    """
    inp = Path(input_path)
    out = Path(output_path) if output_path else WAV_DIR / f"{inp.stem}_whisper.wav"
    
    print(f"🎙️ Whisper: {inp.name} → {out.name}")
    
    cmd = [
        "ffmpeg", "-i", str(inp),
        "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", "-y", str(out),
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if out.exists():
            print(f"   ✅ {out.stat().st_size / (1024*1024):.1f} MB | 16kHz mono")
            return out
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Erro: {e.stderr[-200:]}")
    
    return None


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Conversor de áudio para Clip Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Pastas:
  Entrada: {VOICE_DIR}
  Saída:   {WAV_DIR}
  Música:  {MUSIC_DIR}

Exemplos:
  %(prog)s                              # Converte todos .mp3 de voice/
  %(prog)s -i voz.mp3                   # Converte um arquivo
  %(prog)s -i voz.mp3 --whisper         # Otimizado para Whisper
  %(prog)s --batch mp3 wav              # Converte todos de voice/
  %(prog)s -i voz.mp3 -f flac           # Formato FLAC
        """,
    )
    
    parser.add_argument("-i", "--input", help="Arquivo específico em voice/")
    parser.add_argument("-f", "--format", default="wav", help="Formato de saída")
    parser.add_argument("-b", "--bitrate", default="192k", help="Bitrate")
    parser.add_argument("--batch", nargs=2, metavar=("IN_FMT", "OUT_FMT"),
                       help="Converter todos de voice/")
    parser.add_argument("--whisper", action="store_true", help="Otimizar para Whisper")
    
    args = parser.parse_args()
    
    # Modo Whisper
    if args.whisper:
        if args.input:
            inp = VOICE_DIR / args.input
            convert_for_whisper(str(inp))
        else:
            # Todos os .mp3 de voice/
            for f in sorted(VOICE_DIR.glob("*.mp3")):
                convert_for_whisper(str(f))
        return
    
    # Modo batch
    if args.batch:
        converter = AudioConverter()
        converter.batch_convert(input_format=args.batch[0], output_format=args.batch[1])
        return
    
    # Modo arquivo único
    if args.input:
        inp = VOICE_DIR / args.input
        converter = AudioConverter(bitrate=args.bitrate)
        converter.convert(str(inp), fmt=args.format, bitrate=args.bitrate)
        return
    
    # Sem argumentos: converte todos .mp3 de voice/
    converter = AudioConverter(bitrate=args.bitrate)
    converter.batch_convert(input_format="mp3", output_format=args.format)


if __name__ == "__main__":
    main()