"""
Offline evaluation metrics (dependency-free apart from numpy).

Ranking: ROC AUC, log loss, precision@k, NDCG@k and MRR, computed per user and averaged
(a ranker is judged on how it orders one person's candidates, not across people).
Classification: per-class precision / recall / F1, used for the moderation eval set.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Hashable, Iterable, List, Sequence, Tuple

import numpy as np


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float:
    """Probability that a random positive outscores a random negative (ties count half).
    NaN when only one class is present."""
    y = np.asarray(labels, dtype=float)
    s = np.asarray(scores, dtype=float)
    pos, neg = int(y.sum()), int(len(y) - y.sum())
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):  # average ranks over ties
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg))


def log_loss(labels: Sequence[int], probs: Sequence[float], eps: float = 1e-7) -> float:
    y = np.asarray(labels, dtype=float)
    p = np.clip(np.asarray(probs, dtype=float), eps, 1 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def precision_at_k(ranked_labels: Sequence[int], k: int) -> float:
    top = list(ranked_labels)[:k]
    return sum(top) / k if k else 0.0


def ndcg_at_k(ranked_labels: Sequence[int], k: int) -> float:
    def dcg(labels: Iterable[int]) -> float:
        return sum(rel / math.log2(i + 2) for i, rel in enumerate(labels))

    ideal = dcg(sorted(ranked_labels, reverse=True)[:k])
    return dcg(list(ranked_labels)[:k]) / ideal if ideal > 0 else 0.0


def reciprocal_rank(ranked_labels: Sequence[int]) -> float:
    for i, rel in enumerate(ranked_labels, start=1):
        if rel:
            return 1.0 / i
    return 0.0


def grouped_ranking_metrics(
    groups: Sequence[Hashable], labels: Sequence[int], scores: Sequence[float], k: int = 5
) -> Dict[str, float]:
    """Per-group (per-user) ranking quality, averaged over groups that have at least one
    positive and one negative (others can't distinguish rankers)."""
    by_group: Dict[Hashable, List[Tuple[float, int]]] = defaultdict(list)
    for g, y, s in zip(groups, labels, scores):
        by_group[g].append((s, int(y)))
    p, n, m = [], [], []
    for items in by_group.values():
        ys = [y for _, y in items]
        if 0 < sum(ys) < len(ys):
            ranked = [y for _, y in sorted(items, key=lambda t: -t[0])]
            p.append(precision_at_k(ranked, k))
            n.append(ndcg_at_k(ranked, k))
            m.append(reciprocal_rank(ranked))
    if not p:
        return {f"precision@{k}": float("nan"), f"ndcg@{k}": float("nan"), "mrr": float("nan"), "groups": 0}
    return {f"precision@{k}": float(np.mean(p)), f"ndcg@{k}": float(np.mean(n)), "mrr": float(np.mean(m)),
            "groups": len(p)}


def classification_report(gold: Sequence[str], predicted: Sequence[str]) -> Dict[str, Dict[str, float]]:
    labels = sorted(set(gold) | set(predicted))
    report: Dict[str, Dict[str, float]] = {}
    for label in labels:
        tp = sum(1 for g, p in zip(gold, predicted) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold, predicted) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold, predicted) if g == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    report["accuracy"] = {"value": sum(1 for g, p in zip(gold, predicted) if g == p) / len(gold) if gold else 0.0}
    return report
