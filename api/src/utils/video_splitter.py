#!/usr/bin/env python3
"""
src/utils/video_splitter_fast.py

Fase 1: Corta o vídeo em clipes de X segundos (MUITO RÁPIDO - sem re-encode)
Cria apenas os arquivos de vídeo e um JSON simples para referência.
Agora com suporte a formato 9:16 (vertical) para Reels/Shorts/TikTok.
"""

import subprocess
import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))


class VideoSplitterFast:
    """
    Corta vídeos rapidamente (sem re-encode) e opcionalmente converte para 9:16.
    
    Attributes:
        base_dir: Diretório onde os clipes serão salvos
        output_format: '9:16' (vertical) ou '16:9' (horizontal)
        crop_mode: 'center' (centralizar) ou 'face' (seguir rosto - futuro)
    """
    
    def __init__(
        self, 
        base_dir: Optional[Path] = None,
        output_format: str = "9:16",
        crop_mode: str = "center"
    ) -> None:
        """
        Inicializa o cortador de vídeos.
        
        Args:
            base_dir: Diretório para salvar os clipes (padrão: "downloads")
            output_format: Formato de saída ('9:16' ou '16:9')
            crop_mode: Modo de corte ('center' ou 'face')
        """
        self.base_dir: Path = base_dir or Path("downloads")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.output_format = output_format
        self.crop_mode = crop_mode
        
        # Configurações de resolução para 9:16
        self.target_width = 720
        self.target_height = 1280
        
        # Para 16:9 (paisagem)
        self.landscape_width = 1280
        self.landscape_height = 720

    def _get_video_info(self, video_path: Path) -> Dict:
        """
        Obtém informações detalhadas do vídeo usando ffprobe.
        
        Returns:
            Dicionário com: width, height, duration, fps, codec, etc.
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=width,height,codec_name,r_frame_rate",
            "-show_entries", "format=duration,size",
            "-of", "json",
            str(video_path),
        ]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            data = json.loads(result.stdout)
            
            # Extrai informações
            video_stream = None
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break
            
            if not video_stream:
                raise ValueError("Nenhuma stream de vídeo encontrada")
            
            # Calcula FPS
            fps_str = video_stream.get("r_frame_rate", "30/1")
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if den != "0" else 30.0
            
            return {
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "duration": float(data.get("format", {}).get("duration", 0)),
                "fps": fps,
                "codec": video_stream.get("codec_name", "unknown"),
                "size_bytes": int(data.get("format", {}).get("size", 0)),
            }
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffprobe falhou: {e.stderr}") from e
        except Exception as e:
            raise RuntimeError(f"Erro ao obter informações do vídeo: {e}") from e

    def _calculate_crop_9_16(self, width: int, height: int) -> Tuple[int, int, int, int]:
        """
        Calcula as coordenadas de corte para formato 9:16.
        
        Args:
            width: Largura original do vídeo
            height: Altura original do vídeo
        
        Returns:
            Tupla (x, y, crop_width, crop_height)
        """
        # Se o vídeo já é vertical (9:16), mantém
        if width / height < 1.2:  # Proporção próxima a 9:16
            return (0, 0, width, height)
        
        # Vídeo horizontal: corta o centro para 9:16
        # Altura alvo = altura original
        crop_height = height
        # Largura alvo = altura * 9 / 16
        crop_width = int(height * 9 / 16)
        
        # Centraliza horizontalmente
        x = (width - crop_width) // 2
        y = 0
        
        return (x, y, crop_width, crop_height)

    def _calculate_crop_16_9(self, width: int, height: int) -> Tuple[int, int, int, int]:
        """
        Calcula as coordenadas de corte para formato 16:9.
        
        Args:
            width: Largura original do vídeo
            height: Altura original do vídeo
        
        Returns:
            Tupla (x, y, crop_width, crop_height)
        """
        # Se o vídeo já é horizontal, mantém
        if width / height > 1.3:
            return (0, 0, width, height)
        
        # Vídeo vertical: corta o centro para 16:9
        crop_width = width
        crop_height = int(width * 9 / 16)
        
        # Centraliza verticalmente
        x = 0
        y = (height - crop_height) // 2
        
        return (x, y, crop_width, crop_height)

    def _build_ffmpeg_filter(
        self, 
        width: int, 
        height: int, 
        start_x: int, 
        start_y: int, 
        crop_w: int, 
        crop_h: int
    ) -> str:
        """
        Constrói o filtro de vídeo para FFmpeg.
        
        Returns:
            String com o filtro no formato: "crop=w:h:x:y,scale=W:H"
        """
        # Filtro de corte + escala
        crop_filter = f"crop={crop_w}:{crop_h}:{start_x}:{start_y}"
        
        # Escala para resolução alvo
        if self.output_format == "9:16":
            scale_filter = f"scale={self.target_width}:{self.target_height}"
        else:  # 16:9
            scale_filter = f"scale={self.landscape_width}:{self.landscape_height}"
        
        return f"{crop_filter},{scale_filter}"

    def _fast_cut_with_transform(
        self,
        input_path: Path,
        output_path: Path,
        start_seconds: float,
        end_seconds: float,
        video_info: Dict
    ) -> bool:
        """
        Corta vídeo e aplica transformação para 9:16 (com re-encode).
        
        Args:
            input_path: Caminho do vídeo de entrada
            output_path: Caminho do vídeo de saída
            start_seconds: Tempo de início
            end_seconds: Tempo de fim
            video_info: Dicionário com informações do vídeo
        
        Returns:
            True se bem-sucedido, False caso contrário
        """
        duration = end_seconds - start_seconds
        width = video_info["width"]
        height = video_info["height"]
        
        # Calcula corte para 9:16 ou 16:9
        if self.output_format == "9:16":
            x, y, crop_w, crop_h = self._calculate_crop_9_16(width, height)
        else:
            x, y, crop_w, crop_h = self._calculate_crop_16_9(width, height)
        
        # Constrói filtro
        filter_str = self._build_ffmpeg_filter(width, height, x, y, crop_w, crop_h)
        
        # Comando FFmpeg com re-encode (necessário para crop e scale)
        # Usa presets rápidos para manter qualidade
        command = [
            "ffmpeg",
            "-ss", str(start_seconds),
            "-i", str(input_path),
            "-t", str(duration),
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "veryfast",      # Prioriza velocidade
            "-crf", "23",               # Boa qualidade
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-y",
            str(output_path),
        ]
        
        try:
            result = subprocess.run(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                check=True
            )
            return output_path.exists() and output_path.stat().st_size > 0
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro FFmpeg: {e.stderr[-300:]}")
            return False

    def _fast_cut_copy(self, input_path: Path, output_path: Path, start_seconds: float, end_seconds: float) -> bool:
        """
        Corta vídeo SEM re-encode (extremamente rápido).
        Útil quando o vídeo já está no formato correto.
        """
        duration = end_seconds - start_seconds
        
        command = [
            "ffmpeg",
            "-ss", str(start_seconds),
            "-i", str(input_path),
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_path),
        ]
        
        try:
            subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return output_path.exists() and output_path.stat().st_size > 0
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro no corte copy: {e}")
            return False

    def split_all_clips(
        self,
        video_path: str,
        clip_duration: int = 60,
        start_offset: float = 0,
        apply_transform: bool = True
    ) -> List[Dict]:
        """
        Corta TODO o vídeo em clipes de X segundos.
        
        Args:
            video_path: Caminho do vídeo
            clip_duration: Duração de cada clipe em segundos
            start_offset: Tempo de início em segundos
            apply_transform: Se True, aplica transformação 9:16 (mais lento)
                             Se False, apenas copia (mais rápido)
        
        Returns:
            Lista de dicionários com metadados dos clipes
        """
        input_path = Path(video_path)
        clipes = []

        if not input_path.exists():
            print(f"❌ Arquivo não encontrado: {video_path}")
            return clipes

        # Obtém informações do vídeo
        try:
            video_info = self._get_video_info(input_path)
        except Exception as e:
            print(f"❌ Erro ao obter informações: {e}")
            return clipes

        duration = video_info["duration"]
        width = video_info["width"]
        height = video_info["height"]

        print(f"\n📹 Vídeo: {input_path.name}")
        print(f"📐 Resolução: {width}x{height}")
        print(f"⏱️  Duração total: {duration:.2f}s")
        print(f"📱 Formato de saída: {self.output_format}")
        
        # Verifica se precisa re-encode
        needs_transform = apply_transform and (
            width / height >= 1.2 if self.output_format == "9:16" else width / height < 1.3
        )
        
        if needs_transform:
            print(f"🔄 Aplicando transformação {self.output_format} (re-encode)")
        else:
            print(f"⚡ Corte rápido (copy codec) - vídeo já no formato adequado")
        
        print(f"✂️  Cortando em clipes de {clip_duration}s")
        print("-" * 60)
        
        base_name = input_path.stem
        extension = input_path.suffix
        current_start = start_offset
        clip_index = 1
        
        while current_start < duration:
            current_end = min(current_start + clip_duration, duration)
            clip_dur = current_end - current_start
            
            # Pula clipes muito curtos (< 5 segundos)
            if clip_dur < 5:
                break
            
            output_name = f"{base_name}_clip_{clip_index:04d}{extension}"
            output_path = self.base_dir / output_name
            
            print(f"🎬 Clip {clip_index:03d}: {current_start:.1f}s → {current_end:.1f}s", end=" ")
            
            if needs_transform:
                success = self._fast_cut_with_transform(
                    input_path=input_path,
                    output_path=output_path,
                    start_seconds=current_start,
                    end_seconds=current_end,
                    video_info=video_info
                )
            else:
                success = self._fast_cut_copy(
                    input_path=input_path,
                    output_path=output_path,
                    start_seconds=current_start,
                    end_seconds=current_end
                )
            
            if success:
                size_mb = output_path.stat().st_size / (1024 * 1024)
                clipes.append({
                    "clip_id": clip_index,
                    "filename": output_name,
                    "path": str(output_path),
                    "start": round(current_start, 2),
                    "end": round(current_end, 2),
                    "duration": round(clip_dur, 2),
                    "size_mb": round(size_mb, 2),
                    "format": self.output_format,
                    "resolution": f"{self.target_width}x{self.target_height}" if needs_transform else f"{width}x{height}",
                })
                print(f"✅ {size_mb:.1f} MB")
            else:
                print(f"❌ Falha")
                # Em caso de falha, tenta modo copy (fallback)
                if needs_transform:
                    print("   ⚡ Tentando fallback com copy codec...")
                    success_fallback = self._fast_cut_copy(
                        input_path=input_path,
                        output_path=output_path,
                        start_seconds=current_start,
                        end_seconds=current_end
                    )
                    if success_fallback:
                        size_mb = output_path.stat().st_size / (1024 * 1024)
                        clipes.append({
                            "clip_id": clip_index,
                            "filename": output_name,
                            "path": str(output_path),
                            "start": round(current_start, 2),
                            "end": round(current_end, 2),
                            "duration": round(clip_dur, 2),
                            "size_mb": round(size_mb, 2),
                            "format": "original (copy)",
                            "resolution": f"{width}x{height}",
                        })
                        print(f"   ✅ Fallback funcionou! {size_mb:.1f} MB")
            
            current_start = current_end
            clip_index += 1
        
        # Salvar metadados
        metadata_path = self.base_dir / f"{base_name}_clipes.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(clipes, f, ensure_ascii=False, indent=2)
        
        print("\n" + "=" * 60)
        print(f"✅ Total de clipes: {len(clipes)}")
        print(f"📁 Diretório: {self.base_dir}")
        print(f"💾 Metadados salvos: {metadata_path}")
        
        return clipes


if __name__ == "__main__":
    # Verificar FFmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ FFmpeg encontrado!")
    except FileNotFoundError:
        print("❌ FFmpeg não encontrado! Instale com: sudo apt install ffmpeg")
        sys.exit(1)
    
    # Caminho do vídeo
    VIDEO_PATH = "/home/dev/Code/clip_engine/api/src/services/clip_engine/A_REALIDADE_DA_GUERRA_NA_UCRÂNIA_CRISTIAN_GALVÃO_RELATA_AS_PIORES_PARTES_DO_CONFRONTO.mp4"
    
    if not Path(VIDEO_PATH).exists():
        print(f"❌ Vídeo não encontrado: {VIDEO_PATH}")
        print("   Verifique o caminho e tente novamente.")
        sys.exit(1)
    
    print("=" * 60)
    print("🎬 FASE 1: Corte Rápido do Vídeo")
    print("=" * 60)
    
    # Criar instância com formato 9:16 (Shorts/Reels/TikTok)
    splitter = VideoSplitterFast(
        base_dir=Path("/home/dev/Code/clip_engine/parts"),
        output_format="9:16",  # ou "16:9" para paisagem
        crop_mode="center"
    )
    
    # Processar vídeo
    clipes = splitter.split_all_clips(
        video_path=VIDEO_PATH,
        clip_duration=60,      # 60 segundos por clipe
        start_offset=0,
        apply_transform=True   # Aplica transformação 9:16
    )
    
    print(f"\n📋 {len(clipes)} clipes prontos para processamento com IA!")
    
    # Mostrar resumo dos clipes
    if clipes:
        print("\n📊 Resumo dos clipes:")
        for i, clip in enumerate(clipes[:5], 1):
            print(f"   {i}. {clip['filename']} ({clip['duration']}s, {clip['size_mb']} MB)")
        if len(clipes) > 5:
            print(f"   ... e mais {len(clipes) - 5} clipes")