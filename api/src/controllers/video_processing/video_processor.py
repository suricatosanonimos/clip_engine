import asyncio
import bisect
import heapq
import json
import subprocess
import sys
import tempfile
import time
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import mediapipe as mp
import numpy as np
from src.utils.time_log import time_for_logs

from .precise_tracker import PreciseTracker
from .transcriber_video import TranscriberVideo

# ──────────────────────────────────────────────────────────────────
#  DIRETÓRIOS
#  video_processor.py está em:
#    api/src/controllers/video_processing/video_processor.py
#  Precisamos subir 4 níveis para chegar em api/
# ──────────────────────────────────────────────────────────────────
ROOT_DIR      = Path(__file__).resolve().parent.parent.parent.parent
DOWNLOADS_DIR = ROOT_DIR / "downloads"
PROCESSED_DIR = ROOT_DIR / "processed_videos"
RAW_CLIPS_DIR = PROCESSED_DIR / "raw_clips"

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
RAW_CLIPS_DIR.mkdir(parents=True, exist_ok=True)


class FaceTrackerOptimized:
    """Helper class para tracking otimizado de faces com O(log n)."""

    def __init__(self):
        self.faces: Dict[str, Dict] = {}
        self.face_positions: Dict[str, List[int]] = defaultdict(list)
        self.face_areas: Dict[str, List[float]] = defaultdict(list)
        self.faces_by_position_x: List[Tuple[int, str]] = []
        self.faces_by_area: List[Tuple[float, str]] = []
        self.faces_by_id: Dict[str, int] = {}
        self.recent_faces_heap: List[Tuple[float, str]] = []
        self.next_id = 0

    def add_or_update_face(self, face_id: str, center_x: int, center_y: int, area: float):
        """Adiciona ou atualiza face — O(log n) com bisect."""
        if face_id in self.faces_by_id:
            self._remove_face(face_id)

        self.faces[face_id] = {
            "center_x": center_x,
            "center_y": center_y,
            "area":      area,
            "last_seen": time.time(),
        }
        self.face_positions[face_id].append(center_x)
        self.face_areas[face_id].append(area)

        pos = bisect.bisect_left(self.faces_by_position_x, (center_x, face_id))
        self.faces_by_position_x.insert(pos, (center_x, face_id))

        pos = bisect.bisect_left(self.faces_by_area, (area, face_id))
        self.faces_by_area.insert(pos, (area, face_id))

        self.faces_by_id[face_id] = pos

    def _remove_face(self, face_id: str):
        pass  # Reconstrução feita esporadicamente

    def get_faces_in_x_range(self, min_x: int, max_x: int) -> List[str]:
        if not self.faces_by_position_x:
            return []
        left  = bisect.bisect_left(self.faces_by_position_x,  (min_x, ""))
        right = bisect.bisect_right(self.faces_by_position_x, (max_x, ""))
        return [face_id for _, face_id in self.faces_by_position_x[left:right]]

    def get_largest_faces(self, k: int = 5) -> List[str]:
        if not self.faces_by_area:
            return []
        return [face_id for _, face_id in self.faces_by_area[-k:]]

    def get_nearest_faces(self, target_x: int, target_y: int, radius: int) -> List[Tuple[str, float]]:
        candidates = []
        for face_id in self.get_faces_in_x_range(target_x - radius, target_x + radius):
            face = self.faces.get(face_id)
            if face:
                dx = face["center_x"] - target_x
                dy = face["center_y"] - target_y
                distance = np.sqrt(dx * dx + dy * dy)
                if distance <= radius:
                    candidates.append((distance, face_id))
        candidates.sort()
        return candidates


class VideoProcessor:
    def __init__(self, num_shots: int = 10):
        self.ffmpeg   = "ffmpeg"
        self.ffprobe  = "ffprobe"
        self.num_shots = num_shots
        self.in_dir   = DOWNLOADS_DIR   # sobrescrito externamente quando necessário
        self.out_dir  = PROCESSED_DIR
        self.raw_dir  = RAW_CLIPS_DIR
        self.clip_duration = 60

        self.mp_face      = mp.solutions.face_detection
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_detector = self.mp_face.FaceDetection(
            model_selection=0, min_detection_confidence=0.5,
        )
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=20,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.6,
        )
        self.next_face_id  = 0
        self.min_face_area = 0.02
        self.face_tracker  = FaceTrackerOptimized()

        self._frame_cache: Dict[int, List[Dict]] = {}
        self._cache_size  = 30
        self._face_frequency: Dict[str, int]   = defaultdict(int)
        self._face_confidence: Dict[str, float] = defaultdict(float)

    # ──────────────────────────────────────────────────────────────
    #  HELPERS INTERNOS
    # ──────────────────────────────────────────────────────────────

    def _get_video_info(self, path: Path) -> Dict:
        """Retorna metadados do vídeo via ffprobe. Valida antes de chamar."""

        # Garante que o arquivo existe e não é um _safe.mp4 fantasma
        if not path.exists():
            raise FileNotFoundError(
                f"Vídeo não encontrado antes do ffprobe: {path}\n"
                f"  DOWNLOADS_DIR = {self.in_dir}"
            )

        if path.stat().st_size == 0:
            raise ValueError(f"Arquivo vazio: {path}")

        # Remove sufixo _safe acidental (gerado pelo downloader mas não movido)
        if "_safe" in path.name and not path.exists():
            base = Path(str(path).replace("_safe", ""))
            if base.exists():
                path = base

        cmd = [
            self.ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            str(path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"ffprobe falhou para '{path.name}'.\n"
                f"  stderr: {e.stderr[:300]}\n"
                f"  Verifique se o arquivo não está corrompido."
            ) from e

        data  = json.loads(result.stdout)
        video = next(
            (s for s in data["streams"] if s["codec_type"] == "video"), None
        )
        if video is None:
            raise RuntimeError(f"Nenhuma stream de vídeo encontrada em '{path.name}'.")

        num, den = video["r_frame_rate"].split("/")
        fps = float(num) / float(den)
        return {
            "duration": float(data["format"]["duration"]),
            "width":    int(video["width"]),
            "height":   int(video["height"]),
            "fps":      fps,
        }

    def _generate_timestamps(self, duration: float) -> List[Dict]:
        clips = min(self.num_shots, int(duration // self.clip_duration))
        if clips <= 0:
            return []
        step = (duration - self.clip_duration) / max(clips - 1, 1)
        return [
            {"start": round(i * step, 2), "end": round(i * step + self.clip_duration, 2)}
            for i in range(clips)
        ]

    def _add_watermark(self, frame: np.ndarray) -> np.ndarray:
        h, w  = frame.shape[:2]
        text  = "THE ATLAS"
        font  = cv2.FONT_HERSHEY_SIMPLEX
        fs, ft, alpha = 1.2, 3, 0.3
        ts    = cv2.getTextSize(text, font, fs, ft)[0]
        tx    = (w - ts[0]) // 2
        ty    = ts[1] + 20
        ov    = frame.copy()
        cv2.putText(ov, text, (tx, ty), font, fs, (0, 0, 0),   ft + 2)
        cv2.putText(ov, text, (tx, ty), font, fs, (255,255,255), ft)
        cv2.addWeighted(ov, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def _detect_faces_optimized(self, frame: np.ndarray, previous_faces: Dict) -> Tuple[List[Dict], Any]:
        rgb          = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        det_results  = self.face_detector.process(rgb)
        mesh_results = self.face_mesh.process(rgb)
        detections   = []

        if det_results and det_results.detections:
            h, w, _ = frame.shape
            for prev_id, prev_data in previous_faces.items():
                self.face_tracker.add_or_update_face(
                    prev_id,
                    prev_data["center"][0],
                    prev_data["center"][1],
                    prev_data["area"],
                )

            for detection in det_results.detections:
                bbox = detection.location_data.relative_bounding_box
                area = bbox.width * bbox.height
                if area < self.min_face_area:
                    continue

                center_x = int((bbox.xmin + bbox.width  / 2) * w)
                center_y = int((bbox.ymin + bbox.height / 2) * h)
                radius   = int(w * 0.15)

                nearby  = self.face_tracker.get_nearest_faces(center_x, center_y, radius)
                face_id = nearby[0][1] if nearby else None

                if face_id is None:
                    face_id = f"face_{self.next_face_id}"
                    self.next_face_id += 1

                self._face_frequency[face_id]  += 1
                confidence = (
                    min(1.0, self._face_frequency[face_id] / 100)
                    * min(1.0, area / 0.1)
                )
                self._face_confidence[face_id] = confidence
                self.face_tracker.add_or_update_face(face_id, center_x, center_y, area)

                detections.append({
                    "id":         face_id,
                    "center":     (center_x, center_y),
                    "center_x":   center_x,
                    "center_y":   center_y,
                    "area":       area,
                    "confidence": confidence,
                    "frame":      frame,
                })

        return detections, mesh_results

    # ──────────────────────────────────────────────────────────────
    #  GERAÇÃO DE CLIPES
    # ──────────────────────────────────────────────────────────────

    def create_clip_with_precise_tracking(
        self, video_path: Path, start: float, end: float, index: int
    ) -> Optional[Path]:
        duration = end - start
        output   = self.raw_dir / f"{video_path.stem}_clip_{index:02d}.mp4"

        if output.exists():
            print(f"{time_for_logs()} Clipe {index} já existe, pulando...")
            return output

        print(f"{time_for_logs()} 🎯 Processando clipe {index}: {start}s — {end}s")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"{time_for_logs()} ❌ Erro ao abrir vídeo: {video_path}")
            return None

        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        crop_width   = int(frame_height * 0.75)
        crop_height  = frame_height
        out_width, out_height = 720, 1280

        tracker = PreciseTracker(
            frame_width=frame_width, frame_height=frame_height,
            crop_width=crop_width, fps=fps, transition_seconds=1.0,
        )

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out    = cv2.VideoWriter(str(output), fourcc, fps, (out_width, out_height))

        total_frames     = int(duration * fps)
        frames_processed = 0
        previous_faces   = {}
        start_time = last_progress_time = time.time()

        print(f"{time_for_logs()} Renderizando {total_frames} frames...")

        while frames_processed < total_frames:
            ret, frame = cap.read()
            if not ret:
                break

            detections, mesh_results = self._detect_faces_optimized(frame, previous_faces)
            previous_faces = {d["id"]: d for d in detections}

            crop_x  = tracker.update(detections, mesh_results, frames_processed)
            cropped = frame[0:crop_height, crop_x: crop_x + crop_width]
            resized = cv2.resize(cropped, (out_width, out_height))
            resized = self._add_watermark(resized)
            out.write(resized)
            frames_processed += 1

            if frames_processed % 100 == 0:
                now     = time.time()
                elapsed = now - last_progress_time
                fps_r   = 100 / elapsed if elapsed > 0 else 0
                last_progress_time = now
                pct     = frames_processed / total_frames * 100
                if frames_processed % 500 == 0 and self.face_tracker.faces_by_area:
                    print(f"{time_for_logs()} Maiores faces: {self.face_tracker.get_largest_faces(3)}")
                print(f"{time_for_logs()} Progresso: {frames_processed}/{total_frames} ({pct:.1f}%) | {fps_r:.1f} fps")

        cap.release()
        out.release()

        elapsed = time.time() - start_time
        print(f"{time_for_logs()} ✅ Renderização: {frames_processed} frames em {elapsed:.1f}s")

        if frames_processed > 0:
            return self._add_audio_to_video(video_path, output, start, duration)
        return None

    def _add_audio_to_video(
        self, source_video: Path, video_no_audio: Path, start: float, duration: float
    ) -> Optional[Path]:
        output_with_audio = (
            video_no_audio.parent
            / f"{video_no_audio.stem}_with_audio{video_no_audio.suffix}"
        )
        cmd = [
            self.ffmpeg,
            "-i",  str(video_no_audio),
            "-ss", str(start),
            "-i",  str(source_video),
            "-t",  str(duration),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            "-y",  str(output_with_audio),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            video_no_audio.unlink()
            output_with_audio.rename(video_no_audio)
            print(f"{time_for_logs()} Áudio adicionado")
            return video_no_audio
        except subprocess.CalledProcessError as e:
            print(f"{time_for_logs()} Erro ao adicionar áudio: {e}")
            return video_no_audio

    def _create_clip_ffmpeg(
        self, video_path: Path, start: float, end: float, index: int
    ) -> Optional[Path]:
        """Fallback sem tracking — usa apenas FFmpeg."""
        duration = end - start
        output   = self.raw_dir / f"{video_path.stem}_clip_{index:02d}.mp4"
        print(f"{time_for_logs()} Usando FFmpeg (fallback)...")

        info       = self._get_video_info(video_path)
        crop_width = int(info["height"] * 0.75)
        crop_x     = (info["width"] - crop_width) // 2
        crop_filter = f"crop={crop_width}:{info['height']}:{crop_x}:0,scale=720:1280"

        cmd = [
            self.ffmpeg,
            "-ss", str(start),
            "-i",  str(video_path),
            "-t",  str(duration),
            "-vf", crop_filter,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-y",  str(output),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output if output.exists() else None
        except subprocess.CalledProcessError as e:
            print(f"{time_for_logs()} Erro no FFmpeg: {e}")
            return None

    def create_clip(
        self, video_path: Path, start: float, end: float, index: int, tracking: bool = True
    ):
        if tracking:
            return self.create_clip_with_precise_tracking(video_path, start, end, index)
        return self._create_clip_ffmpeg(video_path, start, end, index)

    # ──────────────────────────────────────────────────────────────
    #  ENTRY POINT
    # ──────────────────────────────────────────────────────────────

    async def process(self, video_name: str, tracking: bool = True) -> List[Path]:
        """
        Processa todos os clipes do vídeo.
        Resolve automaticamente o caminho correto do arquivo,
        removendo sufixos '_safe' deixados pelo downloader.
        """
        # ── 1. Resolve o caminho real do vídeo ────────────────────
        video_path = self.in_dir / video_name

        # Fallback: remove sufixo _safe se o arquivo original existir
        if not video_path.exists() and "_safe" in video_name:
            sem_safe = video_name.replace("_safe", "")
            candidato = self.in_dir / sem_safe
            if candidato.exists():
                print(f"{time_for_logs()} Usando arquivo sem sufixo _safe: {sem_safe}")
                video_path = candidato
                video_name = sem_safe

        # Fallback: procura qualquer .mp4 com stem parecido
        if not video_path.exists():
            stem_base = Path(video_name).stem.replace("_safe", "")
            candidatos = list(self.in_dir.glob(f"{stem_base}*.mp4"))
            candidatos = [c for c in candidatos if "_safe" not in c.name]
            if candidatos:
                video_path = candidatos[0]
                video_name = video_path.name
                print(f"{time_for_logs()} Arquivo encontrado por busca: {video_name}")

        if not video_path.exists():
            print(
                f"{time_for_logs()} ❌ Vídeo não encontrado: {video_path}\n"
                f"  in_dir = {self.in_dir}\n"
                f"  Arquivos disponíveis: {[f.name for f in self.in_dir.iterdir() if f.is_file()]}"
            )
            return []

        # ── 2. Processa ───────────────────────────────────────────
        print(f"{time_for_logs()} Processando vídeo: {video_name}")
        print(f"{time_for_logs()} Caminho: {video_path}")

        info       = self._get_video_info(video_path)
        timestamps = self._generate_timestamps(info["duration"])
        print(f"{time_for_logs()} Gerando {len(timestamps)} clipes de {self.clip_duration}s cada")

        clips = []
        for i, ts in enumerate(timestamps):
            print(f"\n{time_for_logs()} {'='*50}")
            print(f"{time_for_logs()} Clipe {i+1}/{len(timestamps)}")
            print(f"{time_for_logs()} {'='*50}")

            clip = await asyncio.to_thread(
                self.create_clip,
                video_path, ts["start"], ts["end"], i + 1, tracking,
            )

            if clip and clip.exists() and clip.stat().st_size > 1024 * 1024:
                clips.append(clip)
                print(f"{time_for_logs()} ✅ Clipe salvo: {clip.name} ({clip.stat().st_size/1024/1024:.1f} MB)")
            elif clip and clip.exists():
                print(f"{time_for_logs()} ⚠️ Clipe muito pequeno, removendo: {clip.name}")
                clip.unlink()

        return clips
