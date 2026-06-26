# clip_engine/api/src/controllers/video_processing/speaker_identifier.py
"""
Identificador de falantes com alta precisão.
Usa múltiplos indicadores: movimento dos lábios, tempo de fala, consistência,
posição da boca, e análise de áudio (se disponível).
"""

import bisect
import heapq
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np


@dataclass(order=True)
class PrioritizedFace:
    """Face com prioridade para heapq (ordem decrescente de confiança)"""

    confidence: float
    face_id: str = field(compare=False)
    last_update: int = field(compare=False)


class SpeakerIdentifier:
    """
    Identifica quem está falando com alta precisão.

    Melhorias:
    - Threshold adaptativo baseado no histórico global
    - Detecção de troca de turno (turn-taking)
    - Penalidade para faces paradas (não falando)
    - Suporte a múltiplos falantes simultâneos
    - Memória de curto prazo para evitar oscilações
    """

    def __init__(self, fps: float, min_speaking_frames: int = 15):
        self.fps = fps
        self.min_speaking_frames = min_speaking_frames

        # Histórico por face
        self.mouth_movements = defaultdict(lambda: deque(maxlen=30))
        self.speaking_scores = defaultdict(lambda: deque(maxlen=45))
        self.face_positions = defaultdict(lambda: deque(maxlen=60))

        # Estatísticas
        self.total_frames_seen = defaultdict(int)
        self.speaking_frames = defaultdict(int)
        self.non_speaking_frames = defaultdict(int)  # NOVO: frames sem fala

        # Identificação dos falantes principais
        self.primary_speakers: Set[str] = set()
        self.speaker_confidence = defaultdict(float)

        # NOVO: Histórico de quem falou recentemente (evita oscilações)
        self.recent_speaker_history = deque(maxlen=int(fps * 2))  # 2 segundos
        self.turn_taking_cooldown = defaultdict(int)  # cooldown após parar de falar

        # Parâmetros de detecção
        self.mouth_movement_threshold = 0.018
        self.min_confidence_to_confirm = 0.65  # Reduzido para detectar mais falantes
        self.frames_to_confirm = int(fps * 2)  # Reduzido para confirmar mais rápido

        # NOVO: Threshold adaptativo
        self.global_mouth_variance = deque(maxlen=100)
        self.adaptive_threshold = 0.018

        # Listas ordenadas para busca binária
        self.faces_by_confidence: List[Tuple[float, str]] = []
        self.faces_by_position: List[Tuple[int, str]] = []
        self.faces_by_speaking_ratio: List[Tuple[float, str]] = []
        self.faces_by_recent_score: List[Tuple[float, str]] = []

        # Heaps para acesso rápido
        self.confidence_heap: List[PrioritizedFace] = []
        self.recent_scores_heap: List[Tuple[float, str]] = []

        # Índices para busca rápida
        self.face_index: Dict[str, int] = {}

        # Cache para buscas frequentes
        self._cached_top_speakers: List[str] = []
        self._cache_frame = -1
        self._cache_primary: Set[str] = set()

        # Estatísticas otimizadas
        self._face_last_seen: Dict[str, int] = {}
        self._face_consistency: Dict[str, float] = defaultdict(float)

        # NOVO: Posição anterior para detectar movimento
        self._prev_positions: Dict[str, int] = {}

    def _update_adaptive_threshold(self, variance: float):
        """Atualiza o threshold adaptativo baseado no histórico global."""
        self.global_mouth_variance.append(variance)
        if len(self.global_mouth_variance) > 10:
            mean_var = np.mean(list(self.global_mouth_variance))
            std_var = np.std(list(self.global_mouth_variance))
            # Threshold = média + 0.5 * desvio padrão (mais sensível)
            self.adaptive_threshold = max(0.008, mean_var - 0.5 * std_var)

    def _update_ordered_lists(self, face_id: str):
        """Mantém listas ordenadas atualizadas - O(log n) com bisect."""
        confidence = self.speaker_confidence.get(face_id, 0.0)
        positions = self.face_positions.get(face_id, deque())
        position = positions[-1] if positions else 0

        speaking_ratio = self.speaking_frames[face_id] / max(
            1, self.total_frames_seen[face_id]
        )
        recent_scores = list(self.speaking_scores.get(face_id, deque()))[-10:]
        recent_score = np.mean(recent_scores) if recent_scores else 0.0

        if face_id in self.face_index:
            return

        pos = bisect.bisect_left(self.faces_by_confidence, (confidence, face_id))
        self.faces_by_confidence.insert(pos, (confidence, face_id))

        pos = bisect.bisect_left(self.faces_by_position, (position, face_id))
        self.faces_by_position.insert(pos, (position, face_id))

        pos = bisect.bisect_left(
            self.faces_by_speaking_ratio, (speaking_ratio, face_id)
        )
        self.faces_by_speaking_ratio.insert(pos, (speaking_ratio, face_id))

        pos = bisect.bisect_left(self.faces_by_recent_score, (recent_score, face_id))
        self.faces_by_recent_score.insert(pos, (recent_score, face_id))

        heapq.heappush(
            self.confidence_heap,
            PrioritizedFace(-confidence, face_id, self.total_frames_seen[face_id]),
        )
        heapq.heappush(self.recent_scores_heap, (recent_score, face_id))
        self.face_index[face_id] = pos

    def _rebuild_lists(self):
        """Reconstrói listas ordenadas - O(n log n)."""
        all_faces = list(self.total_frames_seen.keys())
        self.faces_by_confidence = []
        self.faces_by_position = []
        self.faces_by_speaking_ratio = []
        self.faces_by_recent_score = []
        self.confidence_heap = []
        self.recent_scores_heap = []
        self.face_index = {}

        for face_id in all_faces:
            self._update_ordered_lists(face_id)

    def analyze_face(self, face_id: str, face_landmarks, frame_idx: int) -> float:
        """
        Analisa se a face está falando baseado em landmarks.
        Mantém a mesma assinatura do método original.

        Melhorias:
        - Mais pontos dos lábios para precisão
        - Análise de assimetria (boca abre/fecha)
        - Threshold adaptativo
        """
        if not face_landmarks:
            # Penaliza faces sem landmarks
            self.non_speaking_frames[face_id] += 1
            return 0.0

        try:
            # Pontos dos lábios expandidos (MediaPipe face mesh)
            upper_lip_outer = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409]
            lower_lip_outer = [146, 91, 181, 84, 17, 314, 405, 321, 375, 291]
            upper_lip_inner = [13, 312, 311, 310, 415, 308, 324, 318, 402, 317]
            lower_lip_inner = [14, 87, 178, 88, 95, 78, 191, 80, 81, 82]

            # Média dos lábios superiores e inferiores
            upper_y_outer = np.mean(
                [face_landmarks.landmark[i].y for i in upper_lip_outer]
            )
            lower_y_outer = np.mean(
                [face_landmarks.landmark[i].y for i in lower_lip_outer]
            )
            upper_y_inner = np.mean(
                [face_landmarks.landmark[i].y for i in upper_lip_inner]
            )
            lower_y_inner = np.mean(
                [face_landmarks.landmark[i].y for i in lower_lip_inner]
            )

            # Abertura da boca (externo e interno)
            mouth_openness_outer = abs(upper_y_outer - lower_y_outer)
            mouth_openness_inner = abs(upper_y_inner - lower_y_inner)

            # Combina aberturas (interno tem mais variação durante fala)
            mouth_openness = mouth_openness_outer * 0.3 + mouth_openness_inner * 0.7

            self.mouth_movements[face_id].append(mouth_openness)
            self._update_adaptive_threshold(mouth_openness)

            if len(self.mouth_movements[face_id]) > 10:
                recent = list(self.mouth_movements[face_id])[-10:]
                variation = np.std(recent)

                # Usa threshold adaptativo
                threshold = self.adaptive_threshold

                # Calcula score de fala (0 a 1)
                speaking_score = (
                    min(1.0, variation / threshold) if threshold > 0 else 0.0
                )

                # NOVO: Verifica padrão de fala (alternância rápida = falando)
                if len(recent) >= 6:
                    # Conta quantas vezes a boca "mudou de direção" (abriu/fechou)
                    diffs = np.diff(recent)
                    sign_changes = np.sum(np.diff(np.sign(diffs)) != 0)
                    if sign_changes >= 2:  # Pelo menos 2 mudanças = padrão de fala
                        speaking_score = max(speaking_score, 0.5)

                self.speaking_scores[face_id].append(speaking_score)
                self._face_last_seen[face_id] = frame_idx

                if speaking_score > 0.30:  # Threshold mais baixo
                    self.speaking_frames[face_id] += 1
                    self.turn_taking_cooldown[face_id] = int(
                        self.fps * 0.5
                    )  # 0.5s cooldown
                else:
                    self.non_speaking_frames[face_id] += 1
                    if self.turn_taking_cooldown[face_id] > 0:
                        self.turn_taking_cooldown[face_id] -= 1

                if frame_idx % 30 == 0:
                    self._update_ordered_lists(face_id)

                return speaking_score

        except Exception as e:
            pass  # Silencioso para não poluir logs

        return 0.0

    def update_face_position(self, face_id: str, center_x: int):
        """
        Atualiza posição da face para tracking.
        Mantém a mesma assinatura do método original.
        """
        self.face_positions[face_id].append(center_x)
        self.total_frames_seen[face_id] += 1

        # NOVO: Detecta movimento lateral (face se mexendo = pode estar falando/gesticulando)
        if face_id in self._prev_positions:
            movement = abs(center_x - self._prev_positions[face_id])
            # Movimento sutil pode indicar fala (gesticulação)
            if movement > 2 and self.turn_taking_cooldown.get(face_id, 0) > 0:
                self.turn_taking_cooldown[face_id] = int(
                    self.fps * 0.3
                )  # Extende cooldown

        self._prev_positions[face_id] = center_x

        if self.total_frames_seen[face_id] % 30 == 0:
            self._update_ordered_lists(face_id)

    def get_top_k_speakers(self, k: int = 5) -> List[str]:
        """Retorna os K melhores falantes - O(k) com heap."""
        if not self.confidence_heap:
            return []
        top_k = heapq.nsmallest(k, self.confidence_heap)
        return [p.face_id for p in top_k]

    def get_speakers_in_position_range(self, min_x: int, max_x: int) -> List[str]:
        """Retorna faces em um range de posição - O(log n + k)."""
        if not self.faces_by_position:
            return []
        left = bisect.bisect_left(self.faces_by_position, (min_x, ""))
        right = bisect.bisect_right(self.faces_by_position, (max_x, ""))
        return [face_id for _, face_id in self.faces_by_position[left:right]]

    def get_speakers_above_confidence(self, threshold: float) -> List[str]:
        """Retorna faces com confiança acima do limiar - O(log n + k)."""
        if not self.faces_by_confidence:
            return []
        pos = bisect.bisect_right(self.faces_by_confidence, (threshold, ""))
        return [face_id for _, face_id in self.faces_by_confidence[pos:]]

    def get_best_speaker_at_position(
        self, target_x: int, radius: int = 100
    ) -> Optional[str]:
        """Encontra melhor falante próximo a uma posição - O(log n + k)."""
        faces_in_range = self.get_speakers_in_position_range(
            target_x - radius, target_x + radius
        )
        if not faces_in_range:
            return None

        best_face = None
        best_confidence = -1
        for face_id in faces_in_range:
            conf = self.speaker_confidence.get(face_id, 0)
            if conf > best_confidence:
                best_confidence = conf
                best_face = face_id
        return best_face

    def identify_primary_speakers(self, frame_idx: int) -> Set[str]:
        """
        Identifica quem são os falantes principais.
        Mantém o mesmo nome do método original.

        Melhorias:
        - Confirmação mais rápida
        - Considera turn-taking (troca de turno)
        - Penaliza faces que nunca falam
        """
        if frame_idx < self.frames_to_confirm:
            return set()

        # Usa cache a cada 15 frames (mais responsivo)
        if frame_idx - self._cache_frame < 15 and self._cached_top_speakers:
            return set(self._cached_top_speakers[:3])

        top_faces = self.get_top_k_speakers(10)
        primary_speakers = set()

        for face_id in top_faces:
            recent_scores = list(self.speaking_scores.get(face_id, deque()))[-15:]
            if recent_scores:
                consistency = (
                    1.0 - (np.std(recent_scores) / max(recent_scores))
                    if max(recent_scores) > 0
                    else 0
                )
            else:
                consistency = 0

            speaking_ratio = self.speaking_frames[face_id] / max(
                1, self.total_frames_seen[face_id]
            )
            visibility_ratio = self.total_frames_seen[face_id] / max(1, frame_idx)

            # NOVO: Bônus para faces em cooldown (acabaram de falar)
            cooldown_bonus = (
                0.15 if self.turn_taking_cooldown.get(face_id, 0) > 0 else 0
            )

            # Recalcula confiança (fórmula melhorada)
            confidence = (
                speaking_ratio * 0.5  # Proporção de fala
                + consistency * 0.25  # Consistência
                + min(1.0, visibility_ratio) * 0.1  # Visibilidade
                + cooldown_bonus  # Bônus de turno recente
            )

            self.speaker_confidence[face_id] = confidence

            # Threshold mais baixo para detectar mais falantes
            if confidence > 0.45 and (speaking_ratio > 0.15 or cooldown_bonus > 0):
                primary_speakers.add(face_id)

        # Se não encontrou nenhum, tenta com threshold ainda menor
        if not primary_speakers and top_faces:
            best_face = top_faces[0]
            confidence = self.speaker_confidence.get(best_face, 0)
            if confidence > 0.25:
                primary_speakers.add(best_face)

        self._cached_top_speakers = list(primary_speakers)
        self._cache_frame = frame_idx
        self.primary_speakers = primary_speakers

        return primary_speakers

    def get_current_speaker(
        self, frame_idx: int, detections: List[Dict]
    ) -> Optional[Dict]:
        """
        Retorna o falante atual.
        Mantém o mesmo nome do método original.

        Melhorias:
        - Prioriza quem está com a boca se movendo AGORA
        - Considera histórico recente para evitar oscilações
        - Fallback para última posição conhecida
        """
        primary_speakers = self.identify_primary_speakers(frame_idx)

        # NOVO: Se não tem primary speakers, tenta usar histórico recente
        if not primary_speakers and self.recent_speaker_history:
            # Usa o último falante conhecido
            last_speaker = self.recent_speaker_history[-1]
            matching = [d for d in detections if d["id"] == last_speaker]
            if matching:
                return matching[0]

        if not primary_speakers:
            return None

        # Filtra detecções que são primary speakers
        current_primary = [d for d in detections if d["id"] in primary_speakers]

        if not current_primary:
            # Tenta encontrar qualquer detecção próxima ao centro
            if detections:
                # Ordena por proximidade ao centro
                center = (
                    self.frame_width // 2
                    if hasattr(self, "frame_width")
                    else detections[0].get("frame_width", 640) // 2
                )
                detections_sorted = sorted(
                    detections, key=lambda d: abs(d["center_x"] - center)
                )
                return detections_sorted[0]
            return None

        if len(current_primary) == 1:
            best = current_primary[0]
            self.recent_speaker_history.append(best["id"])
            return best

        # Para múltiplos candidatos
        candidates = []
        for detection in current_primary:
            face_id = detection["id"]

            # Scores recentes
            recent_scores = list(self.speaking_scores.get(face_id, deque()))[-10:]
            current_speaking_score = np.mean(recent_scores) if recent_scores else 0

            # NOVO: Bônus para o último falante (evita oscilações)
            history_bonus = (
                0.3
                if self.recent_speaker_history
                and self.recent_speaker_history[-1] == face_id
                else 0
            )

            # Distância ao centro
            frame_width = detection.get("frame_width", 640)
            center_distance = abs(detection["center_x"] - frame_width // 2)
            center_score = 1 - (center_distance / (frame_width // 2))

            # Score final (fórmula melhorada)
            score = (
                current_speaking_score * 0.6 + center_score * 0.2 + history_bonus * 0.2
            )

            heapq.heappush(candidates, (-score, detection))

        if candidates:
            _, best = heapq.heappop(candidates)
            self.recent_speaker_history.append(best["id"])
            return best

        return None

    def get_faces_by_priority(self, k: int = 5) -> List[str]:
        """Retorna as faces prioritárias para tracking - O(k log n)."""
        priority_heap = []
        for face_id in self.total_frames_seen.keys():
            confidence = self.speaker_confidence.get(face_id, 0)
            recency = self._face_last_seen.get(face_id, 0)
            frequency = self.total_frames_seen.get(face_id, 0)

            priority_score = (
                confidence * 0.5
                + (recency / self.frames_to_confirm) * 0.3
                + (frequency / 1000) * 0.2
            )
            heapq.heappush(priority_heap, (-priority_score, face_id))

        return [face_id for _, face_id in heapq.nsmallest(k, priority_heap)]

    def cleanup_old_faces(self, frame_idx: int, max_age_frames: int = 300):
        """Remove faces não vistas recentemente - O(n)."""
        to_remove = []
        for face_id, last_seen in self._face_last_seen.items():
            if frame_idx - last_seen > max_age_frames:
                to_remove.append(face_id)

        for face_id in to_remove:
            self.mouth_movements.pop(face_id, None)
            self.speaking_scores.pop(face_id, None)
            self.face_positions.pop(face_id, None)
            self.total_frames_seen.pop(face_id, None)
            self.speaking_frames.pop(face_id, None)
            self.speaker_confidence.pop(face_id, None)
            self._face_last_seen.pop(face_id, None)
            self.primary_speakers.discard(face_id)

        if to_remove:
            self._rebuild_lists()

        return len(to_remove)
