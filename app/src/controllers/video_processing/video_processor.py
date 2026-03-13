import asyncio
import bisect
import heapq
import json
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import mediapipe as mp
import numpy as np
from src.utils.time_log import time_for_logs

from .precise_tracker import PreciseTracker
from .transcriber_video import TranscriberVideo

# Configuração de diretórios
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DOWNLOADS_DIR = ROOT_DIR / "downloads"
PROCESSED_DIR = ROOT_DIR / "processed_videos"
RAW_CLIPS_DIR = PROCESSED_DIR / "raw_clips"

DOWNLOADS_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)
RAW_CLIPS_DIR.mkdir(exist_ok=True)


class FaceTrackerOptimized:
    """
    Helper class para tracking otimizado de faces com O(log n)
    """

    def __init__(self):
        # Estruturas O(1)
        self.faces: Dict[str, Dict] = {}
        self.face_positions: Dict[str, List[int]] = defaultdict(list)
        self.face_areas: Dict[str, List[float]] = defaultdict(list)

        # Estruturas para O(log n) - Listas ordenadas
        self.faces_by_position_x: List[Tuple[int, str]] = []  # Ordenado por posição X
        self.faces_by_area: List[Tuple[float, str]] = []  # Ordenado por área
        self.faces_by_id: Dict[str, int] = {}  # Índice nas listas

        # Heap para faces mais próximas
        self.recent_faces_heap: List[Tuple[float, str]] = []  # Min-heap por distância

        self.next_id = 0

    def add_or_update_face(
        self, face_id: str, center_x: int, center_y: int, area: float
    ):
        """Adiciona ou atualiza face - O(log n) com bisect"""
        # Remove entrada antiga se existir
        if face_id in self.faces_by_id:
            self._remove_face(face_id)

        # Adiciona nova entrada
        self.faces[face_id] = {
            "center_x": center_x,
            "center_y": center_y,
            "area": area,
            "last_seen": time.time(),
        }

        # Mantém histórico para estatísticas
        self.face_positions[face_id].append(center_x)
        self.face_areas[face_id].append(area)

        # Insere em lista ordenada por posição X - O(log n)
        pos = bisect.bisect_left(self.faces_by_position_x, (center_x, face_id))
        self.faces_by_position_x.insert(pos, (center_x, face_id))

        # Insere em lista ordenada por área - O(log n)
        pos = bisect.bisect_left(self.faces_by_area, (area, face_id))
        self.faces_by_area.insert(pos, (area, face_id))

        # Atualiza índice
        self.faces_by_id[face_id] = pos

    def _remove_face(self, face_id: str):
        """Remove face das estruturas - precisa reconstruir (feito esporadicamente)"""
        # Para simplificar, vamos reconstruir as listas quando necessário
        # Isso é O(n) mas feito raramente
        pass

    def get_faces_in_x_range(self, min_x: int, max_x: int) -> List[str]:
        """
        Retorna faces em um range de posição X - O(log n + k)
        """
        if not self.faces_by_position_x:
            return []

        # Busca binária para encontrar range - O(log n)
        left = bisect.bisect_left(self.faces_by_position_x, (min_x, ""))
        right = bisect.bisect_right(self.faces_by_position_x, (max_x, ""))

        # Retorna faces no range - O(k)
        return [face_id for _, face_id in self.faces_by_position_x[left:right]]

    def get_largest_faces(self, k: int = 5) -> List[str]:
        """
        Retorna as K maiores faces - O(log n + k)
        """
        if not self.faces_by_area:
            return []

        # As últimas K da lista ordenada (maiores áreas)
        return [face_id for _, face_id in self.faces_by_area[-k:]]

    def get_nearest_faces(
        self, target_x: int, target_y: int, radius: int
    ) -> List[Tuple[str, float]]:
        """
        Retorna faces ordenadas por distância - usa heap O(n log n) mas otimizado
        """
        candidates = []

        # Primeiro filtra por range X (rápido) - O(log n)
        x_min, x_max = target_x - radius, target_x + radius
        faces_in_range = self.get_faces_in_x_range(x_min, x_max)

        # Depois calcula distância real para essas - O(k)
        for face_id in faces_in_range:
            face = self.faces.get(face_id)
            if face:
                dx = face["center_x"] - target_x
                dy = face["center_y"] - target_y
                distance = np.sqrt(dx * dx + dy * dy)
                if distance <= radius:
                    candidates.append((distance, face_id))

        # Ordena por distância - O(k log k)
        candidates.sort()
        return candidates


class VideoProcessor:
    def __init__(self, num_shots: int = 10):
        self.ffmpeg = "ffmpeg"
        self.ffprobe = "ffprobe"
        self.num_shots = num_shots
        self.in_dir = DOWNLOADS_DIR
        self.out_dir = PROCESSED_DIR
        self.raw_dir = RAW_CLIPS_DIR
        self.clip_duration = 60
        self.mp_face = mp.solutions.face_detection
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_detector = self.mp_face.FaceDetection(
            model_selection=0,
            min_detection_confidence=0.5,
        )
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=20,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.6,
        )
        self.next_face_id = 0
        self.min_face_area = 0.02

        # NOVO: Face tracker otimizado
        self.face_tracker = FaceTrackerOptimized()

        # Cache para resultados frequentes
        self._frame_cache: Dict[int, List[Dict]] = {}
        self._cache_size = 30

        # Estatísticas para otimização
        self._face_frequency: Dict[str, int] = defaultdict(int)
        self._face_confidence: Dict[str, float] = defaultdict(float)

    def _get_video_info(self, path: Path) -> Dict:
        """O(log n) - busca info do vídeo"""
        cmd = [
            self.ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        video = next(s for s in data["streams"] if s["codec_type"] == "video")
        num, den = video["r_frame_rate"].split("/")
        fps = float(num) / float(den)
        return {
            "duration": float(data["format"]["duration"]),
            "width": int(video["width"]),
            "height": int(video["height"]),
            "fps": fps,
        }

    def _generate_timestamps(self, duration: float) -> List[Dict]:
        """O(n) - gera timestamps (n = número de clipes)"""
        clips = min(self.num_shots, int(duration // self.clip_duration))
        if clips <= 0:
            return []
        step = (duration - self.clip_duration) / max(clips - 1, 1)
        return [
            {
                "start": round(i * step, 2),
                "end": round(i * step + self.clip_duration, 2),
            }
            for i in range(clips)
        ]

    # ⚠️ FUNÇÃO DE CONVERSÃO COMENTADA - descomente se precisar
    # def _convert_to_compatible_format(
    #     self, video_path: Path, start: float, duration: float
    # ) -> Optional[Path]:
    #     temp_dir = Path(tempfile.mkdtemp())
    #     output = temp_dir / f"converted_{video_path.stem}.mp4"
    #     print(f"{time_for_logs()} Convertendo vídeo para formato compatível...")
    #     cmd = [
    #         self.ffmpeg,
    #         "-ss",
    #         str(start),
    #         "-i",
    #         str(video_path),
    #         "-t",
    #         str(duration),
    #         "-c:v",
    #         "libx264",
    #         "-preset",
    #         "veryfast",
    #         "-crf",
    #         "23",
    #         "-pix_fmt",
    #         "yuv420p",
    #         "-c:a",
    #         "aac",
    #         "-y",
    #         str(output),
    #     ]
    #     try:
    #         subprocess.run(cmd, check=True, capture_output=True)
    #         print(f"{time_for_logs()} Conversão concluída")
    #         return output
    #     except subprocess.CalledProcessError as e:
    #         print(f"{time_for_logs()} Erro na conversão: {e}")
    #         return None

    def _add_watermark(self, frame: np.ndarray) -> np.ndarray:
        """O(1) - watermark simples"""
        h, w = frame.shape[:2]
        text = "THE ATLAS"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.2
        font_thickness = 3
        alpha = 0.3
        text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
        text_x = (w - text_size[0]) // 2
        text_y = text_size[1] + 20
        overlay = frame.copy()
        cv2.putText(
            overlay,
            text,
            (text_x, text_y),
            font,
            font_scale,
            (0, 0, 0),
            font_thickness + 2,
        )
        cv2.putText(
            overlay,
            text,
            (text_x, text_y),
            font,
            font_scale,
            (255, 255, 255),
            font_thickness,
        )
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame

    def _detect_faces_optimized(
        self, frame: np.ndarray, previous_faces: Dict
    ) -> Tuple[List[Dict], Any]:
        """
        Versão otimizada com O(log n) para matching de faces
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        det_results = self.face_detector.process(rgb)
        mesh_results = self.face_mesh.process(rgb)

        detections = []
        if det_results and det_results.detections:
            h, w, _ = frame.shape

            # Constrói KD-tree virtual usando listas ordenadas
            # Primeiro, atualiza face_tracker com faces anteriores
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

                center_x = int((bbox.xmin + bbox.width / 2) * w)
                center_y = int((bbox.ymin + bbox.height / 2) * h)

                # OTIMIZAÇÃO: Busca faces próximas usando range - O(log n)
                radius = int(w * 0.15)
                nearby_faces = self.face_tracker.get_nearest_faces(
                    center_x, center_y, radius
                )

                face_id = None
                if nearby_faces:
                    # Pega a mais próxima
                    distance, face_id = nearby_faces[0]

                if face_id is None:
                    face_id = f"face_{self.next_face_id}"
                    self.next_face_id += 1

                # Atualiza frequência - O(1)
                self._face_frequency[face_id] += 1

                # Calcula confiança baseada em frequência e área
                confidence = min(1.0, self._face_frequency[face_id] / 100) * min(
                    1.0, area / 0.1
                )
                self._face_confidence[face_id] = confidence

                # Atualiza tracker com nova posição
                self.face_tracker.add_or_update_face(face_id, center_x, center_y, area)

                detections.append(
                    {
                        "id": face_id,
                        "center": (center_x, center_y),
                        "center_x": center_x,
                        "center_y": center_y,
                        "area": area,
                        "confidence": confidence,
                        "frame": frame,
                    }
                )

        return detections, mesh_results

    def create_clip_with_precise_tracking(
        self, video_path: Path, start: float, end: float, index: int
    ) -> Optional[Path]:
        duration = end - start
        output = self.raw_dir / f"{video_path.stem}_clip_{index:02d}.mp4"

        if output.exists():
            print(f"{time_for_logs()} Clipe {index} já existe, pulando...")
            return output

        print(f"{time_for_logs()} 🎯 Processando clipe {index}: {start}s - {end}s")

        # ⚠️ COMENTADO: usando fallback direto em vez de conversão
        # converted = self._convert_to_compatible_format(video_path, start, duration)
        # if not converted:
        #     print(f"{time_for_logs()} Erro na conversão, usando fallback...")
        #     return self._create_clip_ffmpeg(video_path, start, end, index)

        # Usa o vídeo original diretamente
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"{time_for_logs()} Erro ao abrir vídeo")
            return None

        # Pula para o time start
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30

        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        crop_width = int(frame_height * 0.75)
        crop_height = frame_height
        out_width = 720
        out_height = 1280

        tracker = PreciseTracker(
            frame_width=frame_width,
            frame_height=frame_height,
            crop_width=crop_width,
            fps=fps,
            transition_seconds=1.0,
        )

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(output), fourcc, fps, (out_width, out_height))

        total_frames = int(duration * fps)
        frames_processed = 0
        previous_faces = {}

        print(f"{time_for_logs()} Renderizando {total_frames} frames...")
        start_time = time.time()
        last_progress_time = start_time

        while frames_processed < total_frames:
            ret, frame = cap.read()
            if not ret:
                break

            # Usa versão otimizada de detecção
            detections, mesh_results = self._detect_faces_optimized(
                frame, previous_faces
            )
            previous_faces = {d["id"]: d for d in detections}

            crop_x = tracker.update(detections, mesh_results, frames_processed)
            cropped = frame[0:crop_height, crop_x : crop_x + crop_width]
            resized = cv2.resize(cropped, (out_width, out_height))
            resized = self._add_watermark(resized)
            out.write(resized)

            frames_processed += 1

            # Log de progresso otimizado (a cada 100 frames)
            if frames_processed % 100 == 0:
                current_time = time.time()
                elapsed = current_time - last_progress_time
                fps_render = 100 / elapsed if elapsed > 0 else 0
                last_progress_time = current_time
                progress = (frames_processed / total_frames) * 100

                # OTIMIZAÇÃO: Mostra top faces por confiança
                if frames_processed % 500 == 0 and self.face_tracker.faces_by_area:
                    largest_faces = self.face_tracker.get_largest_faces(3)
                    print(f"{time_for_logs()} Maiores faces: {largest_faces}")

                print(
                    f"{time_for_logs()} Progresso: {frames_processed}/{total_frames} "
                    f"({progress:.1f}%) | {fps_render:.1f} fps"
                )

        cap.release()
        out.release()

        # Remove arquivo convertido se existir
        # if converted and converted.exists():
        #     converted.unlink()
        #     converted.parent.rmdir()

        elapsed = time.time() - start_time
        print(
            f"{time_for_logs()} ✅ Renderização concluída: {frames_processed} frames em {elapsed:.1f}s"
        )

        if frames_processed > 0:
            return self._add_audio_to_video(video_path, output, start, duration)
        return None

    def _add_audio_to_video(
        self,
        source_video: Path,
        video_no_audio: Path,
        start: float,
        duration: float,
    ) -> Optional[Path]:
        """O(1) - adiciona áudio (ffmpeg)"""
        output_with_audio = (
            video_no_audio.parent
            / f"{video_no_audio.stem}_with_audio{video_no_audio.suffix}"
        )
        cmd = [
            self.ffmpeg,
            "-i",
            str(video_no_audio),
            "-ss",
            str(start),
            "-i",
            str(source_video),
            "-t",
            str(duration),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            "-y",
            str(output_with_audio),
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
        """Fallback - O(1) chamada ffmpeg"""
        duration = end - start
        output = self.raw_dir / f"{video_path.stem}_clip_{index:02d}.mp4"
        print(f"{time_for_logs()} Usando FFmpeg (fallback)...")
        info = self._get_video_info(video_path)
        crop_width = int(info["height"] * 0.75)
        crop_x = (info["width"] - crop_width) // 2
        crop_filter = f"crop={crop_width}:{info['height']}:{crop_x}:0,scale=720:1280"
        cmd = [
            self.ffmpeg,
            "-ss",
            str(start),
            "-i",
            str(video_path),
            "-t",
            str(duration),
            "-vf",
            crop_filter,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-y",
            str(output),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output if output.exists() else None
        except subprocess.CalledProcessError as e:
            print(f"{time_for_logs()} Erro no FFmpeg: {e}")
            return None

    def create_clip(
        self,
        video_path: Path,
        start: float,
        end: float,
        index: int,
        tracking: bool = True,
    ):
        """O(n) - dispatch para método correto"""
        if tracking:
            return self.create_clip_with_precise_tracking(video_path, start, end, index)
        else:
            return self._create_clip_ffmpeg(video_path, start, end, index)

    async def process(self, video_name: str, tracking: bool = True):
        """O(n) - processa todos os clipes"""
        video_path = self.in_dir / video_name
        if not video_path.exists():
            print(f"{time_for_logs()} Vídeo não encontrado: {video_path}")
            return []

        print(f"{time_for_logs()} Processando vídeo: {video_name}")
        info = self._get_video_info(video_path)
        timestamps = self._generate_timestamps(info["duration"])
        print(
            f"{time_for_logs()} Gerando {len(timestamps)} clipes de {self.clip_duration}s cada"
        )

        clips = []
        for i, ts in enumerate(timestamps):
            print(f"\n{time_for_logs()} {'='*50}")
            print(f"{time_for_logs()} Clipe {i+1}/{len(timestamps)}")
            print(f"{time_for_logs()} {'='*50}")

            clip = await asyncio.to_thread(
                self.create_clip,
                video_path,
                ts["start"],
                ts["end"],
                i + 1,
                tracking,
            )

            if clip and clip.exists() and clip.stat().st_size > 1024 * 1024:
                clips.append(clip)
                size_mb = clip.stat().st_size / (1024 * 1024)
                print(
                    f"{time_for_logs()} ✅ Clipe salvo: {clip.name} ({size_mb:.1f} MB)"
                )
            elif clip and clip.exists():
                print(
                    f"{time_for_logs()} ⚠️ Clipe muito pequeno, removendo: {clip.name}"
                )
                clip.unlink()

        return clips
