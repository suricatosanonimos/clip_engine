# clip_engine/api/src/controllers/video_processing/precise_tracker.py
"""
Tracker preciso que foca exclusivamente nos falantes identificados.
Suaviza transições e evita que a câmera fique parada no centro
quando há um falante ativo.
"""

from collections import deque
from typing import Any, Dict, List, Optional

import numpy as np

from .speaker_identifier import SpeakerIdentifier


class PreciseTracker:
    """
    Tracker preciso que foca exclusivamente nos falantes identificados.

    Melhorias:
    - Nunca fica parado no centro se há um falante detectado
    - Transições mais suaves e responsivas
    - Memória de posição do falante (não perde o falante)
    - Dead zone reduzida para evitar câmera parada
    - Fallback inteligente quando perde o falante
    """

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        crop_width: int,
        fps: float,
        transition_seconds: float = 0.5,  # Mais rápido
    ):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.crop_width = crop_width
        self.fps = fps
        self.transition_frames = int(fps * transition_seconds)

        # Posição atual e alvo
        self.current_position = frame_width // 2
        self.target_position = frame_width // 2

        # Estado de transição
        self.in_transition = False
        self.transition_start_pos = None
        self.transition_target_pos = None
        self.transition_frame = 0

        # Histórico para suavização
        self.position_history = deque(maxlen=int(fps * 0.3))  # 300ms

        # NOVO: Memória do último falante
        self.last_speaker_position = None
        self.last_speaker_id = None
        self.frames_since_last_speaker = 0
        self.max_frames_without_speaker = int(fps * 1.5)  # 1.5 segundos

        # NOVO: Dead zone menor (2% em vez de 5%)
        self.dead_zone_percent = 0.02

        # NOVO: Margens mais flexíveis
        self.margin_percent = 0.15  # 15% de margem nas bordas

        # Identificador de falantes
        self.speaker_identifier = SpeakerIdentifier(fps)
        self.face_landmarks_cache = {}

    def update(
        self,
        detections: List[Dict],
        face_mesh_results,
        frame_idx: int,
    ) -> int:
        """
        Atualiza o rastreamento e retorna a posição X do crop.
        Mantém a mesma assinatura do método original.
        """
        # ── Processa detecções ──
        enhanced_detections = []
        for det in detections:
            face_id = det["id"]
            face_landmarks = None

            # Match com face mesh
            if face_mesh_results and face_mesh_results.multi_face_landmarks:
                h, w, _ = (
                    det["frame"].shape
                    if "frame" in det
                    else (self.frame_height, self.frame_width, 3)
                )
                for landmarks in face_mesh_results.multi_face_landmarks:
                    lms_center_x = int(np.mean([lm.x for lm in landmarks.landmark]) * w)
                    lms_center_y = int(np.mean([lm.y for lm in landmarks.landmark]) * h)
                    distance = np.sqrt(
                        (det["center_x"] - lms_center_x) ** 2
                        + (det["center_y"] - lms_center_y) ** 2
                    )
                    if distance < w * 0.08:  # Mais tolerante
                        face_landmarks = landmarks
                        break

            # Analisa se está falando
            speaking_score = self.speaker_identifier.analyze_face(
                face_id, face_landmarks, frame_idx
            )
            self.speaker_identifier.update_face_position(face_id, det["center_x"])

            enhanced_det = det.copy()
            enhanced_det["speaking_score"] = speaking_score
            enhanced_det["frame_width"] = self.frame_width
            enhanced_detections.append(enhanced_det)

        # ── Identifica falante atual ──
        current_speaker = self.speaker_identifier.get_current_speaker(
            frame_idx, enhanced_detections
        )

        # ── Calcula posição alvo ──
        if current_speaker:
            target = current_speaker["center_x"]

            # Atualiza memória do falante
            self.last_speaker_position = target
            self.last_speaker_id = current_speaker["id"]
            self.frames_since_last_speaker = 0

            # Margens dinâmicas
            margin = int(self.frame_width * self.margin_percent)
            min_target = self.crop_width // 2 + margin
            max_target = self.frame_width - self.crop_width // 2 - margin

            self.target_position = max(min_target, min(target, max_target))

        else:
            self.frames_since_last_speaker += 1

            # NOVO: Fallback inteligente
            if (
                self.last_speaker_position is not None
                and self.frames_since_last_speaker < self.max_frames_without_speaker
            ):
                # Mantém a última posição conhecida do falante por um tempo
                self.target_position = self.last_speaker_position
                # Gradualmente volta ao centro após o timeout
                if (
                    self.frames_since_last_speaker
                    > self.max_frames_without_speaker * 0.7
                ):
                    center = self.frame_width // 2
                    alpha = (
                        self.frames_since_last_speaker
                        - self.max_frames_without_speaker * 0.7
                    ) / (self.max_frames_without_speaker * 0.3)
                    self.target_position = int(
                        self.last_speaker_position * (1 - alpha) + center * alpha
                    )
            else:
                # Se tem primary speakers, tenta encontrar qualquer um
                if self.speaker_identifier.primary_speakers and enhanced_detections:
                    # Pega a detecção mais próxima do último falante
                    if self.last_speaker_position is not None:
                        closest = min(
                            enhanced_detections,
                            key=lambda d: abs(
                                d["center_x"] - self.last_speaker_position
                            ),
                        )
                        self.target_position = closest["center_x"]
                    else:
                        # Último recurso: centro
                        self.target_position = self.frame_width // 2
                else:
                    # Nenhum falante: centro
                    self.target_position = self.frame_width // 2

        # ── Verifica se precisa mover (dead zone menor) ──
        dead_zone = int(self.frame_width * self.dead_zone_percent)
        distance = abs(self.current_position - self.target_position)

        if distance > dead_zone:
            if not self.in_transition:
                self.in_transition = True
                self.transition_start_pos = self.current_position
                self.transition_target_pos = self.target_position
                self.transition_frame = 0
        else:
            # Dentro da dead zone: mantém posição
            if not self.in_transition:
                self.current_position = self.target_position

        # ── Executa transição suave ──
        if self.in_transition:
            self.transition_frame += 1

            # Recalcula alvo se mudou durante a transição
            if abs(self.transition_target_pos - self.target_position) > dead_zone:
                self.transition_start_pos = self.current_position
                self.transition_target_pos = self.target_position
                self.transition_frame = 0

            t = min(1.0, self.transition_frame / self.transition_frames)
            # Easing suave (smoothstep)
            t_smooth = t * t * (3 - 2 * t)

            self.current_position = int(
                self.transition_start_pos * (1 - t_smooth)
                + self.transition_target_pos * t_smooth
            )

            if t >= 1.0:
                self.in_transition = False

        # ── Suavização adicional ──
        self.position_history.append(self.current_position)
        if len(self.position_history) > 3:
            # Média móvel ponderada (mais peso nos frames recentes)
            positions = list(self.position_history)
            weights = np.linspace(0.5, 1.0, len(positions))
            smoothed = np.average(positions, weights=weights)
            self.current_position = int(smoothed)

        # ── Calcula crop_x final ──
        crop_x = self.current_position - self.crop_width // 2
        crop_x = max(0, min(crop_x, self.frame_width - self.crop_width))

        return crop_x
