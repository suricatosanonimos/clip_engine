from collections import deque
from typing import Any, Dict, List, Optional

import numpy as np

from .speaker_identifier import SpeakerIdentifier


class PreciseTracker:
    """Tracker preciso que foca exclusivamente nos falantes identificados"""

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        crop_width: int,
        fps: float,
        transition_seconds: float = 1.0,
    ):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.crop_width = crop_width
        self.fps = fps
        self.transition_frames = int(fps * transition_seconds)
        self.current_position = frame_width // 2
        self.target_position = frame_width // 2
        self.in_transition = False
        self.transition_start_pos = None
        self.transition_target_pos = None
        self.transition_frame = 0
        self.position_history = deque(maxlen=int(fps * 0.5))
        self.speaker_identifier = SpeakerIdentifier(fps)
        self.face_landmarks_cache = {}

    def update(
        self,
        detections: List[Dict],
        face_mesh_results,
        frame_idx: int,
    ) -> int:
        enhanced_detections = []
        for det in detections:
            face_id = det["id"]
            face_landmarks = None
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
                    if distance < w * 0.1:  # Mais estrito para matching
                        face_landmarks = landmarks
                        break
            speaking_score = self.speaker_identifier.analyze_face(
                face_id, face_landmarks, frame_idx
            )
            self.speaker_identifier.update_face_position(face_id, det["center_x"])
            enhanced_det = det.copy()
            enhanced_det["speaking_score"] = speaking_score
            enhanced_det["frame_width"] = self.frame_width
            enhanced_detections.append(enhanced_det)
        current_speaker = self.speaker_identifier.get_current_speaker(
            frame_idx, enhanced_detections
        )
        if current_speaker:
            target = current_speaker["center_x"]
            face_width = self.frame_width * 0.25  # Mais margem para zoom out
            margin = int(face_width * 0.5)  # Mais margem
            min_target = self.crop_width // 2 + margin
            max_target = self.frame_width - self.crop_width // 2 - margin
            self.target_position = max(min_target, min(target, max_target))
        else:
            if self.speaker_identifier.primary_speakers:
                pass
            else:
                self.target_position = self.frame_width // 2
        if abs(self.current_position - self.target_position) > self.frame_width * 0.05:
            if not self.in_transition:
                self.in_transition = True
                self.transition_start_pos = self.current_position
                self.transition_target_pos = self.target_position
                self.transition_frame = 0
        else:
            self.current_position = self.target_position
            self.in_transition = False
        if self.in_transition:
            self.transition_frame += 1
            t = min(1.0, self.transition_frame / self.transition_frames)
            t_smooth = t * t * (3 - 2 * t)
            self.current_position = int(
                self.transition_start_pos * (1 - t_smooth)
                + self.transition_target_pos * t_smooth
            )
            if t >= 1.0:
                self.in_transition = False
        self.position_history.append(self.current_position)
        if len(self.position_history) > 5:
            smoothed = np.mean(list(self.position_history)[-5:])
            self.current_position = int(smoothed)
        crop_x = self.current_position - self.crop_width // 2
        crop_x = max(0, min(crop_x, self.frame_width - self.crop_width))
        return crop_x
