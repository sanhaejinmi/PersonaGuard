"""
엔티티 span 매칭 및 Precision/Recall/F1 계산 — 실험 1·2 공통 유틸리티.

정답(gold)과 예측(pred)은 dict 또는 dataclass 어느 쪽이든 상관없다
(type/start/end 속성 또는 키만 있으면 됨).
"""

from __future__ import annotations

from dataclasses import dataclass


def _field(entity, name: str):
    if isinstance(entity, dict):
        return entity[name]
    return getattr(entity, name)


def _iou(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    inter = max(0, min(a_end, b_end) - max(a_start, b_start))
    if inter == 0:
        return 0.0
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union


def match_entities(
    gold: list,
    pred: list,
    iou_threshold: float = 0.5,
    require_type_match: bool = True,
) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    """탐욕적(greedy) 최대 IoU 매칭.

    반환: (matches, unmatched_gold_idx, unmatched_pred_idx)
    matches: [(gold_idx, pred_idx, iou), ...]
    """
    candidates = []
    for gi, g in enumerate(gold):
        g_type, g_start, g_end = _field(g, "type"), _field(g, "start"), _field(g, "end")
        for pi, p in enumerate(pred):
            p_type, p_start, p_end = _field(p, "type"), _field(p, "start"), _field(p, "end")
            if require_type_match and g_type != p_type:
                continue
            iou = _iou(g_start, g_end, p_start, p_end)
            if iou >= iou_threshold:
                candidates.append((iou, gi, pi))

    candidates.sort(key=lambda c: c[0], reverse=True)
    used_gold: set[int] = set()
    used_pred: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for iou, gi, pi in candidates:
        if gi in used_gold or pi in used_pred:
            continue
        used_gold.add(gi)
        used_pred.add(pi)
        matches.append((gi, pi, iou))

    unmatched_gold = [i for i in range(len(gold)) if i not in used_gold]
    unmatched_pred = [i for i in range(len(pred)) if i not in used_pred]
    return matches, unmatched_gold, unmatched_pred


@dataclass
class PRF:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> dict:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }
