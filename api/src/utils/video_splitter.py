#!/usr/bin/env python3
"""
src/utils/video_splitter.py

Corta vídeos rapidamente com suporte a 9:16 e gancho focado em velocidade bruta.
OTIMIZADO: Elimina completamente análises e transcrições do vídeo bruto original.
"""

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from src.utils.brain_selector import BrainSelector
    HAS_BRAIN_SELECTOR = True
except ImportError:
    HAS_BRAIN_SELECTOR = False


class VideoSplitterFast:
    """Cortador de vídeos rápido com FFmpeg focado em clipes."""

    CRF_DEFAULT = 20
    PRESET = "veryfast"

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        output_format: str = "9:16",
        crop_mode: str = "center",
        num_threads: int = 2,
        zoom_factor: float = 1.0,
    ) -> None:
        self.base_dir = Path(base_dir) if base_dir else Path("downloads")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.output_format = output_format
        self.crop_mode = crop_mode
        self.num_threads = num_threads
        self.zoom_factor = zoom_factor

        self.target_width = 720
        self.target_height = 1280
        self.landscape_width = 1280
        self.landscape_height = 720

    # ══════════════════════════════════════════════════════════════
    #  INFORMAÇÕES DO VÍDEO
    # ══════════════════════════════════════════════════════════════

    def _get_video_info(self, video_path: Path) -> Dict:
        if not video_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {video_path}")
        if video_path.stat().st_size == 0:
            raise ValueError(f"Arquivo vazio: {video_path}")

        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height,codec_type,r_frame_rate",
            "-show_entries", "format=duration",
            "-of", "json", str(video_path),
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            data = json.loads(result.stdout)

            video_stream = None
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break

            if video_stream:
                w = int(video_stream.get("width", 0))
                h = int(video_stream.get("height", 0))
                fps_str = video_stream.get("r_frame_rate", "30/1")
                try:
                    num, den = fps_str.split("/")
                    fps = float(num) / float(den) if float(den) != 0 else 30.0
                except:
                    fps = 30.0
            else:
                w, h, fps = self._get_info_ffmpeg(video_path)

            duration = float(data.get("format", {}).get("duration", 0))
            return {"width": w, "height": h, "duration": duration, "fps": fps}
        except Exception:
            w, h, fps = self._get_info_ffmpeg(video_path)
            return {"width": w, "height": h, "duration": 0, "fps": fps}

    def _get_info_ffmpeg(self, video_path: Path) -> tuple:
        cmd = ["ffmpeg", "-i", str(video_path), "-f", "null", "-"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stderr = result.stderr

        match_res = re.search(r"(\d{2,4})x(\d{2,4})", stderr)
        width = int(match_res.group(1)) if match_res else 1920
        height = int(match_res.group(2)) if match_res else 1080

        match_fps = re.search(r"(\d+\.?\d*)\s*fps", stderr)
        fps = float(match_fps.group(1)) if match_fps else 30.0

        return width, height, fps

    # ══════════════════════════════════════════════════════════════
    #  CROP / TRANSFORMAÇÃO
    # ══════════════════════════════════════════════════════════════

    def _calculate_crop(self, width: int, height: int) -> Tuple[int, int, int, int]:
        if self.output_format == "9:16":
            crop_w = int(height * 9 / 16 * self.zoom_factor)
            crop_h = height
            x = (width - crop_w) // 2
            return (max(0, x), 0, min(crop_w, width), crop_h)
        else:
            crop_w = width
            crop_h = int(width * 9 / 16)
            y = (height - crop_h) // 2
            return (0, max(0, y), crop_w, min(crop_h, height))

    def _build_filter_string(self, crop_x, crop_y, crop_w, crop_h) -> str:
        scale_w = self.target_width if self.output_format == "9:16" else self.landscape_width
        scale_h = self.target_height if self.output_format == "9:16" else self.landscape_height
        return f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={scale_w}:{scale_h}"

    def _build_ffmpeg_command(
        self, input_path, output_path, start_seconds, duration, apply_transform=False, width=0, height=0
    ) -> List[str]:
        cmd = [
            "ffmpeg",
            "-ss", str(start_seconds),
            "-i", str(input_path),
            "-t", str(duration),
        ]

        if apply_transform:
            cx, cy, cw, ch = self._calculate_crop(width, height)
            filter_str = self._build_filter_string(cx, cy, cw, ch)
            cmd.extend([
                "-vf", filter_str,
                "-c:v", "libx264",
                "-preset", self.PRESET,
                "-crf", str(self.CRF_DEFAULT),
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                "-threads", str(self.num_threads),
            ])
        else:
            cmd.extend(["-c", "copy", "-avoid_negative_ts", "make_zero"])

        cmd.extend(["-y", str(output_path)])
        return cmd

    def _execute_cut(
        self, input_path, output_path, start_seconds, end_seconds, video_info, apply_transform
    ) -> Optional[Dict]:
        duration = end_seconds - start_seconds
        width, height = video_info["width"], video_info["height"]

        if width == 0 or height == 0:
            info = self._get_video_info(input_path)
            width, height = info["width"], info["height"]

        command = self._build_ffmpeg_command(
            input_path, output_path, start_seconds, duration, apply_transform, width, height
        )

        try:
            subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            if output_path.exists() and output_path.stat().st_size > 0:
                final_w = self.target_width if apply_transform and self.output_format == "9:16" else width
                final_h = self.target_height if apply_transform and self.output_format == "9:16" else height
                return {
                    "start": round(start_seconds, 2),
                    "end": round(end_seconds, 2),
                    "duration": round(duration, 2),
                    "size_mb": round(output_path.stat().st_size / (1024 * 1024), 2),
                    "resolution": f"{final_w}x{final_h}",
                }
            return None
        except subprocess.CalledProcessError:
            if apply_transform:
                return self._execute_cut(input_path, output_path, start_seconds, end_seconds, video_info, False)
            return None

    # ══════════════════════════════════════════════════════════════
    #  CORTE EM CLIPES BRUTOS (FALCON SPEED)
    # ══════════════════════════════════════════════════════════════

    def split_all_clips(
        self, video_path, clip_duration=60, num_clips=None, start_offset=0, apply_transform=True
    ) -> List[Dict]:
        input_path = Path(video_path)
        if not input_path.exists():
            print(f"❌ Arquivo não encontrado: {video_path}")
            return []

        try:
            video_info = self._get_video_info(input_path)
        except Exception as e:
            print(f"❌ Erro: {e}")
            return []

        duration = video_info["duration"]
        width, height = video_info["width"], video_info["height"]

        if num_clips and num_clips > 0:
            max_clips = num_clips
            total_cut = min(start_offset + num_clips * clip_duration, duration)
        else:
            max_clips = int((duration - start_offset) / clip_duration) + 1
            total_cut = duration

        print(f"\n📹 {input_path.name} | {width}x{height} | {duration:.1f}s")
        
        current_transform = apply_transform 
        if os.environ.get("PIPELINE_MODO") == "2":
            current_transform = False

        print(f"✂️  {max_clips} clipe(s) de {clip_duration}s | Renderização 9:16 imediata: {'Sim' if current_transform else 'Não (Adiada para Concatenação)'}")
        print("-" * 60)

        base_name = input_path.stem
        extension = input_path.suffix

        cortes = []
        current_start = start_offset
        for i in range(1, max_clips + 1):
            current_end = min(current_start + clip_duration, total_cut)
            if current_end - current_start < 3:
                break
            cortes.append({
                "index": i,
                "start": current_start,
                "end": current_end,
                "output_path": self.base_dir / f"{base_name}_clip_{i:04d}{extension}",
                "output_name": f"{base_name}_clip_{i:04d}{extension}",
            })
            current_start = current_end

        results = []
        
        with ThreadPoolExecutor(max_workers=min(4, len(cortes))) as executor:
            futures = {}
            for c in cortes:
                f = executor.submit(
                    self._execute_cut, input_path, c["output_path"], c["start"], c["end"], video_info, current_transform
                )
                futures[f] = c

            for f in as_completed(futures):
                c = futures[f]
                r = f.result()
                if r:
                    r.update({
                        "clip_id": c["index"],
                        "filename": c["output_name"],
                        "path": str(c["output_path"]),
                    })
                    results.append(r)
                    print(f"✅ Clip {c['index']:03d} extraído com sucesso ({r['size_mb']:.1f} MB)")
                else:
                    print(f"❌ Falha no Clip {c['index']:03d}")

        results.sort(key=lambda x: x.get("clip_id", 0))

        metadata_path = self.base_dir / f"{base_name}_clipes.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n✅ {len(results)} clipes salvos em metadata | 💾 {metadata_path}")
        return results

    # ══════════════════════════════════════════════════════════════
    #  NOVA LÓGICA DE GANCHO (DENTRO DOS CLIPES CURTOS)
    # ══════════════════════════════════════════════════════════════

    async def extract_hook_from_clips_json(self, clips_json_path: str, moment_duration=8) -> Optional[Dict]:
        """
        🧠 ESTRATÉGIA DE VELOCIDADE BRUTA:
        Lê os clipes já cortados e chama o BrainSelector para analisar 
        o primeiro clipe curto gerado. Retorna onde o gancho ideal deve começar.
        """
        json_path = Path(clips_json_path)
        if not json_path.exists():
            return None

        with open(json_path, "r", encoding="utf-8") as f:
            clipes = json.load(f)

        if not clipes or not HAS_BRAIN_SELECTOR:
            print("⚠️ Sem clipes ou BrainSelector indisponível. Usando fallback no meio.")
            return {"hook_start": 0, "hook_end": moment_duration}

        print("\n🧠 Analisando os clipes cortados com IA para criar o Gancho Ideal...")
        
        # Joga o JSON dos clipes enxutos diretamente para o BrainSelector processar em milissegundos
        selector = BrainSelector()
        try:
            selecionados = await selector.select_best_clips(str(json_path))
        except RuntimeError:
            import asyncio
            selecionados = asyncio.run(selector.select_best_clips(str(json_path)))

        # Fallback padrão seguro: Começo do primeiro clipe
        hook_start = 0
        target_clip_path = Path(clipes[0]["path"])

        # Se a IA encontrou um momento impactante em algum clipe, ele vira o nosso gancho!
        if selecionados and selecionados[0].get("moments"):
            best_clip = selecionados[0]
            target_clip_path = Path(best_clip["path"])
            moment = best_clip["moments"][0]
            hook_start = moment["start"]
            print(f"   🎯 IA detectou gancho ideal no arquivo {target_clip_path.name} em: {hook_start:.1f}s")
        else:
            print(f"   ⚠️ IA sem resultados nos clipes, aplicando gancho fixo no início do clip_0001.")

        # Corta o pedaço de 8 segundos do próprio clipe menor em vez de mexer no vídeo bruto original!
        output_path = self.base_dir / f"{target_clip_path.stem}_hook{target_clip_path.suffix}"
        
        # Info do clipe curto
        clip_info = self._get_video_info(target_clip_path)
        hook_end = min(hook_start + moment_duration, clip_info["duration"])

        result = self._execute_cut(target_clip_path, output_path, hook_start, hook_end, clip_info, apply_transform=False)

        if result:
            result.update({
                "type": "hook",
                "path": str(output_path),
                "filename": output_path.name,
                "hook_start": hook_start,
                "hook_end": hook_end,
            })
            print(f"✅ Gancho extraído do clipe reduzido: {output_path.name} ({result['size_mb']:.1f} MB)")
            return result

        return None

    # ══════════════════════════════════════════════════════════════
    #  CONCATENAÇÃO
    # ══════════════════════════════════════════════════════════════

    def prepend_hook_to_clips(
        self, hook_path: str, clips_json_path: str, output_dir: Optional[Path] = None
    ) -> List[Dict]:
        hook = Path(hook_path)
        json_path = Path(clips_json_path)

        if not hook.exists() or not json_path.exists():
            print("❌ Arquivos de entrada faltando para a concatenação.")
            return []

        with open(json_path, "r", encoding="utf-8") as f:
            clipes = json.load(f)

        output_dir = Path(output_dir) if output_dir else json_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        hook_info = self._get_video_info(hook)
        hook_w = hook_info.get("width", self.target_width)
        hook_h = hook_info.get("height", self.target_height)

        print(f"\n🔗 UNIFICANDO GANCHOS + CLIPES EM PARALELO (Aplicando Crop 9:16 único)")
        print("-" * 60)

        novos_clipes = []
        files_to_remove = [hook, json_path]

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = {}
            for clipe in clipes:
                clip_path = Path(clipe["path"])
                if not clip_path.exists() or "hook" in clip_path.name:
                    continue

                output_path = output_dir / f"{clip_path.stem}_final{clip_path.suffix}"
                files_to_remove.append(clip_path)

                f = executor.submit(
                    self._concat_two_videos, hook, clip_path, output_path, hook_w, hook_h
                )
                futures[f] = (clipe, output_path)

            for f in as_completed(futures):
                clipe, output_path = futures[f]
                success = f.result()

                if success:
                    novos_clipes.append({
                        "clip_id": clipe.get("clip_id"),
                        "filename": output_path.name,
                        "path": str(output_path),
                        "start": clipe.get("start", 0),
                        "end": clipe.get("end", 0),
                        "duration": clipe.get("duration", 0),
                        "size_mb": round(output_path.stat().st_size / (1024 * 1024), 2),
                        "has_hook": True,
                    })
                    print(f"✅ Vídeo Final Combinado Criado: {output_path.name} ({novos_clipes[-1]['size_mb']:.1f} MB)")
                else:
                    print(f"⚠️ Erro ao processar combinação para o arquivo {output_path.name}")

        for f in files_to_remove:
            try:
                if f.exists(): f.unlink()
            except: pass

        novos_clipes.sort(key=lambda x: x.get("clip_id", 0))
        base_name = json_path.name.replace("_clipes.json", "")
        final_json = output_dir / f"{base_name}_final.json"
        
        with open(final_json, "w", encoding="utf-8") as f:
            json.dump(novos_clipes, f, ensure_ascii=False, indent=2)

        return novos_clipes

    def _concat_two_videos(self, video1: Path, video2: Path, output: Path, width: int, height: int) -> bool:
        concat_list = self.base_dir / f"_concat_{output.stem}.txt"
        with open(concat_list, "w") as f:
            f.write(f"file '{video1.absolute()}'\n")
            f.write(f"file '{video2.absolute()}'\n")

        if self.output_format == "9:16" and width > 0 and height > 0:
            cx, cy, cw, ch = self._calculate_crop(width, height)
            vf = self._build_filter_string(cx, cy, cw, ch)
        else:
            vf = f"scale={self.target_width}:{self.target_height}"

        command = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", self.PRESET,
            "-crf", str(self.CRF_DEFAULT),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-threads", "2",
            "-y", str(output),
        ]

        try:
            subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            concat_list.unlink(missing_ok=True)
            return output.exists() and output.stat().st_size > 0
        except subprocess.CalledProcessError:
            concat_list.unlink(missing_ok=True)
            return False


if __name__ == "__main__":
    print("=" * 60)
    print("🎬 VIDEO SPLITTER ULTRA FAST - CORTES INTELIGENTES")
    print("=" * 60)

    print("\n📋 Modos:")
    print("   1. Cortar vídeo em clipes")
    print("   2. Pipeline completo de alta velocidade (clipes -> gancho via IA)")

    modo = input("\n🔢 Escolha: ").strip() or "1"
    video_path = input("📹 Vídeo: ").strip()

    if not video_path:
        print("❌ Caminho obrigatório")
        sys.exit(1)

    os.environ["PIPELINE_MODO"] = modo

    splitter = VideoSplitterFast(
        base_dir=ROOT_DIR / "processed_videos" / "raw_clips",
        output_format="9:16",
        num_threads=4,
        zoom_factor=1.15,
    )

    if modo == "2":
        num = int(input("✂️  Quantos clipes? (3): ").strip() or "3")
        dur = int(input("⏱️  Duração por clipe (90s): ").strip() or "90")

        # PASSO 1: Fazer os cortes brutos super rápidos primeiro
        clips = splitter.split_all_clips(
            video_path=video_path,
            clip_duration=dur,
            num_clips=num,
            start_offset=0,
            apply_transform=True,
        )

        if clips:
            clipes_json = splitter.base_dir / f"{Path(video_path).stem}_clipes.json"
            
            # PASSO 2: Extrair o gancho de forma inteligente a partir do clipe gerado
            import asyncio
            hook = asyncio.run(splitter.extract_hook_from_clips_json(clips_json_path=str(clipes_json), moment_duration=8))
            
            if hook:
                # PASSO 3: Unificar com re-encode único em paralelo
                final = splitter.prepend_hook_to_clips(
                    hook_path=hook["path"],
                    clips_json_path=str(clipes_json),
                )
                print(f"\n🚀 SUCESSO EM TEMPO RECORDE! {len(final)} clipes unificados com ganchos!")
            else:
                print(f"\n✅ Clipes gerados com sucesso, gancho ignorado.")
        else:
            print("❌ Falha na geração dos clipes base.")
    else:
        num = int(input("✂️  Quantos clipes? (3): ").strip() or "3")
        dur = int(input("⏱️  Duração (90s): ").strip() or "90")

        resultados = splitter.split_all_clips(
            video_path=video_path,
            clip_duration=dur,
            num_clips=num,
            apply_transform=True,
        )
        print(f"\n✅ {len(resultados)} clipe(s) gerado(s)")