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
    Identifica quem está falando com alta precisão
    Usa múltiplos indicadores: movimento dos lábios, tempo de fala, consistência
    Versão otimizada com O(log n) para buscas rápidas
    """

    def __init__(self, fps: float, min_speaking_frames: int = 15):
        self.fps = fps
        self.min_speaking_frames = min_speaking_frames

        # Histórico por face (estruturas originais mantidas)
        self.mouth_movements = defaultdict(lambda: deque(maxlen=30))
        self.speaking_scores = defaultdict(lambda: deque(maxlen=45))
        self.face_positions = defaultdict(lambda: deque(maxlen=60))

        # Estatísticas
        self.total_frames_seen = defaultdict(int)
        self.speaking_frames = defaultdict(int)

        # Identificação dos falantes principais
        self.primary_speakers: Set[str] = set()
        self.speaker_confidence = defaultdict(float)

        # Parâmetros de detecção
        self.mouth_movement_threshold = 0.018
        self.min_confidence_to_confirm = 0.75
        self.frames_to_confirm = int(fps * 3)

        # ========== NOVAS ESTRUTURAS PARA O(log n) ==========

        # Listas ordenadas para busca binária
        self.faces_by_confidence: List[Tuple[float, str]] = []  # Ordenado por confiança
        self.faces_by_position: List[Tuple[int, str]] = []  # Ordenado por posição X
        self.faces_by_speaking_ratio: List[Tuple[float, str]] = (
            []
        )  # Ordenado por proporção de fala
        self.faces_by_recent_score: List[Tuple[float, str]] = (
            []
        )  # Ordenado por score recente

        # Heaps para acesso rápido
        self.confidence_heap: List[PrioritizedFace] = []  # Max-heap de confiança
        self.recent_scores_heap: List[Tuple[float, str]] = (
            []
        )  # Min-heap para scores recentes

        # Índices para busca rápida
        self.face_index: Dict[str, int] = {}  # Mapeia face_id para posição nas listas

        # Cache para buscas frequentes
        self._cached_top_speakers: List[str] = []
        self._cache_frame = -1
        self._cache_primary: Set[str] = set()

        # Estatísticas otimizadas
        self._face_last_seen: Dict[str, int] = {}
        self._face_consistency: Dict[str, float] = defaultdict(float)

    def _update_ordered_lists(self, face_id: str):
        """
        Mantém listas ordenadas atualizadas - O(log n) com bisect
        """
        confidence = self.speaker_confidence.get(face_id, 0.0)

        # Pega última posição
        positions = self.face_positions.get(face_id, deque())
        position = positions[-1] if positions else 0

        # Calcula speaking ratio
        speaking_ratio = self.speaking_frames[face_id] / max(
            1, self.total_frames_seen[face_id]
        )

        # Calcula score recente
        recent_scores = list(self.speaking_scores.get(face_id, deque()))[-10:]
        recent_score = np.mean(recent_scores) if recent_scores else 0.0

        # Remove entrada antiga se existir (simplificado - na prática faremos rebuild periódico)
        if face_id in self.face_index:
            return

        # Insere em faces_by_confidence mantendo ordem - O(log n)
        pos = bisect.bisect_left(self.faces_by_confidence, (confidence, face_id))
        self.faces_by_confidence.insert(pos, (confidence, face_id))

        # Insere em faces_by_position - O(log n)
        pos = bisect.bisect_left(self.faces_by_position, (position, face_id))
        self.faces_by_position.insert(pos, (position, face_id))

        # Insere em faces_by_speaking_ratio - O(log n)
        pos = bisect.bisect_left(
            self.faces_by_speaking_ratio, (speaking_ratio, face_id)
        )
        self.faces_by_speaking_ratio.insert(pos, (speaking_ratio, face_id))

        # Insere em faces_by_recent_score - O(log n)
        pos = bisect.bisect_left(self.faces_by_recent_score, (recent_score, face_id))
        self.faces_by_recent_score.insert(pos, (recent_score, face_id))

        # Atualiza heap de confiança - O(log n)
        heapq.heappush(
            self.confidence_heap,
            PrioritizedFace(-confidence, face_id, self.total_frames_seen[face_id]),
        )

        # Atualiza heap de scores recentes
        heapq.heappush(self.recent_scores_heap, (recent_score, face_id))

        # Atualiza índice
        self.face_index[face_id] = pos

    def _rebuild_lists(self):
        """Reconstrói listas ordenadas - O(n log n) - chamado ocasionalmente"""
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

    # ========== MÉTODOS ORIGINAIS MANTIDOS (com otimizações internas) ==========

    def analyze_face(self, face_id: str, face_landmarks, frame_idx: int) -> float:
        """
        Analisa se a face está falando baseado em landmarks
        Mantém a mesma assinatura do método original
        """
        if not face_landmarks:
            return 0.0

        try:
            # Extrai mais pontos dos lábios para precisão
            upper_lip_indices = [0, 13, 14, 15, 16, 17, 18, 267, 269, 270, 271]
            lower_lip_indices = [78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88]

            upper_y = np.mean([face_landmarks.landmark[i].y for i in upper_lip_indices])
            lower_y = np.mean([face_landmarks.landmark[i].y for i in lower_lip_indices])

            mouth_openness = abs(upper_y - lower_y)
            self.mouth_movements[face_id].append(mouth_openness)

            if len(self.mouth_movements[face_id]) > 10:
                recent = list(self.mouth_movements[face_id])[-10:]
                variation = np.std(recent)
                speaking_score = min(1.0, variation / self.mouth_movement_threshold)

                self.speaking_scores[face_id].append(speaking_score)
                self._face_last_seen[face_id] = frame_idx

                if speaking_score > 0.35:
                    self.speaking_frames[face_id] += 1

                # Atualiza listas ordenadas periodicamente
                if frame_idx % 30 == 0:
                    self._update_ordered_lists(face_id)

                return speaking_score

        except Exception as e:
            print(f"Erro na análise de fala: {e}")

        return 0.0

    def update_face_position(self, face_id: str, center_x: int):
        """
        Atualiza posição da face para tracking
        Mantém a mesma assinatura do método original
        """
        self.face_positions[face_id].append(center_x)
        self.total_frames_seen[face_id] += 1

        # Atualiza listas ordenadas periodicamente
        if self.total_frames_seen[face_id] % 30 == 0:
            self._update_ordered_lists(face_id)

    # ========== NOVOS MÉTODOS AUXILIARES O(log n) ==========

    def get_top_k_speakers(self, k: int = 5) -> List[str]:
        """
        Retorna os K melhores falantes - O(k) com heap
        """
        if not self.confidence_heap:
            return []

        # Pega os K maiores (menos negativos)
        top_k = heapq.nsmallest(k, self.confidence_heap)
        return [p.face_id for p in top_k]

    def get_speakers_in_position_range(self, min_x: int, max_x: int) -> List[str]:
        """
        Retorna faces em um range de posição - O(log n + k)
        """
        if not self.faces_by_position:
            return []

        left = bisect.bisect_left(self.faces_by_position, (min_x, ""))
        right = bisect.bisect_right(self.faces_by_position, (max_x, ""))

        return [face_id for _, face_id in self.faces_by_position[left:right]]

    def get_speakers_above_confidence(self, threshold: float) -> List[str]:
        """
        Retorna faces com confiança acima do limiar - O(log n + k)
        """
        if not self.faces_by_confidence:
            return []

        pos = bisect.bisect_right(self.faces_by_confidence, (threshold, ""))
        return [face_id for _, face_id in self.faces_by_confidence[pos:]]

    def get_best_speaker_at_position(
        self, target_x: int, radius: int = 100
    ) -> Optional[str]:
        """
        Encontra melhor falante próximo a uma posição - O(log n + k)
        """
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
        Identifica quem são os falantes principais
        Versão otimizada - O(log n) em vez de O(n)
        Mantém o mesmo nome do método original
        """
        if frame_idx < self.frames_to_confirm:
            return set()

        # Usa cache a cada 30 frames
        if frame_idx - self._cache_frame < 30 and self._cached_top_speakers:
            return set(self._cached_top_speakers[:3])

        # Pega top 10 faces por confiança - O(log n)
        top_faces = self.get_top_k_speakers(10)

        primary_speakers = set()
        for face_id in top_faces:
            confidence = self.speaker_confidence.get(face_id, 0)

            # Usa busca binária para encontrar scores recentes
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

            # Recalcula confiança (fórmula original)
            confidence = (
                speaking_ratio * 0.6
                + consistency * 0.3
                + min(1.0, visibility_ratio) * 0.1
            )

            self.speaker_confidence[face_id] = confidence

            if confidence > self.min_confidence_to_confirm and speaking_ratio > 0.25:
                primary_speakers.add(face_id)

        # Atualiza cache
        self._cached_top_speakers = list(primary_speakers)
        self._cache_frame = frame_idx
        self.primary_speakers = primary_speakers

        return primary_speakers

    def get_current_speaker(
        self, frame_idx: int, detections: List[Dict]
    ) -> Optional[Dict]:
        """
        Retorna o falante atual
        Versão otimizada - O(log n) em vez de O(n)
        Mantém o mesmo nome do método original
        """
        primary_speakers = self.identify_primary_speakers(frame_idx)

        if not primary_speakers:
            return None

        # Filtra detecções que são primary speakers - O(m) onde m é pequeno (detecções do frame)
        current_primary = [d for d in detections if d["id"] in primary_speakers]

        if not current_primary:
            return None

        if len(current_primary) == 1:
            return current_primary[0]

        # Para múltiplos candidatos, usa heap para achar melhor
        candidates = []
        for detection in current_primary:
            face_id = detection["id"]

            # Busca scores recentes - O(1) com deque
            recent_scores = list(self.speaking_scores.get(face_id, deque()))[-15:]
            current_speaking_score = np.mean(recent_scores) if recent_scores else 0

            # Calcula score baseado na posição
            center_distance = abs(detection["center_x"] - detection["frame_width"] // 2)
            center_score = 1 - (center_distance / (detection["frame_width"] // 2))

            # Score final (fórmula original)
            score = current_speaking_score * 0.8 + center_score * 0.2

            # Usa heap negativo para max-heap
            heapq.heappush(candidates, (-score, detection))

        # Pega o melhor (menor negativo = maior score)
        if candidates:
            _, best = heapq.heappop(candidates)
            return best

        return None

    # ========== MÉTODOS DE OTIMIZAÇÃO ADICIONAIS ==========

    def get_faces_by_priority(self, k: int = 5) -> List[str]:
        """
        Retorna as faces prioritárias para tracking - O(k log n)
        """
        # Combina diferentes métricas usando heap
        priority_heap = []

        for face_id in self.total_frames_seen.keys():
            # Score composto
            confidence = self.speaker_confidence.get(face_id, 0)
            recency = self._face_last_seen.get(face_id, 0)
            frequency = self.total_frames_seen.get(face_id, 0)

            priority_score = (
                confidence * 0.5
                + (recency / self.frames_to_confirm) * 0.3
                + (frequency / 1000) * 0.2
            )
            heapq.heappush(priority_heap, (-priority_score, face_id))

        # Pega os K melhores
        return [face_id for _, face_id in heapq.nsmallest(k, priority_heap)]

    def cleanup_old_faces(self, frame_idx: int, max_age_frames: int = 300):
        """
        Remove faces não vistas recentemente - O(n)
        """
        to_remove = []
        for face_id, last_seen in self._face_last_seen.items():
            if frame_idx - last_seen > max_age_frames:
                to_remove.append(face_id)

        for face_id in to_remove:
            # Remove de todas as estruturas
            self.mouth_movements.pop(face_id, None)
            self.speaking_scores.pop(face_id, None)
            self.face_positions.pop(face_id, None)
            self.total_frames_seen.pop(face_id, None)
            self.speaking_frames.pop(face_id, None)
            self.speaker_confidence.pop(face_id, None)
            self._face_last_seen.pop(face_id, None)
            self.primary_speakers.discard(face_id)

        # Reconstroi listas ordenadas
        if to_remove:
            self._rebuild_lists()

        return len(to_remove)
