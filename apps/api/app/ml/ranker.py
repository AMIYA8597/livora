"""
Learning-to-rank for flatmate recommendations, trained on like/pass decisions.

Model: L2-regularised logistic regression (Newton's method) over standardised features that
describe a (viewer, candidate) pair: the 10 explainable compatibility factors, lifestyle-vector
similarity, "about me" embedding similarity, dealbreakers, and profile-quality signals. It
predicts P(viewer likes candidate) and orders recommendations by it; the explainable
compatibility breakdown shown to users is unchanged.

Safety rails:
- Training uses a time-based split (older 80% to fit, newest 20% to evaluate), so evaluation
  mimics predicting future behaviour.
- A new version only becomes active if it beats the heuristic baseline (ranking by the
  compatibility score) on held-out ROC AUC by MIN_AUC_GAIN, with enough data. Otherwise it is
  stored inactive with its metrics, and recommendations keep using the heuristic.
- The features each user saw are snapshotted when they act (`match_interactions.features`).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.evaluation import grouped_ranking_metrics, log_loss, roc_auc
from app.ml.models import MLModel

logger = logging.getLogger("flatmate.ml.ranker")

MODEL_NAME = "flatmate_ranker"
FACTOR_KEYS = (
    "working_schedule", "sleep_schedule", "budget", "cleanliness", "lifestyle",
    "noise_and_lighting", "guests_and_social", "food_and_cooking", "professional_domain", "location",
)
FEATURES: tuple = (
    "overall", *(f"factor_{k}" for k in FACTOR_KEYS), "vector_sim", "dealbreakers_cleared",
    "bio_similarity", "has_bio_similarity", "candidate_verified", "candidate_has_avatar",
    "candidate_has_bio",
)
POSITIVE_ACTIONS = ("like", "super_like")
NEGATIVE_ACTIONS = ("pass",)
HOLDOUT_FRACTION = 0.2
MIN_AUC_GAIN = 0.01
CACHE_SECONDS = 300


def pair_features(
    breakdown: Dict[str, Any], *, vector_sim: float, bio_similarity: Optional[float],
    candidate_verified: bool, candidate_has_avatar: bool, candidate_has_bio: bool,
) -> Dict[str, float]:
    factors = breakdown.get("factors") or {}
    feats: Dict[str, float] = {
        "overall": float(breakdown.get("overall_score", 0.0)) / 100.0,
        "vector_sim": float(vector_sim),
        "dealbreakers_cleared": 1.0 if breakdown.get("dealbreakers_cleared", True) else 0.0,
        "bio_similarity": float(bio_similarity) if bio_similarity is not None else 0.0,
        "has_bio_similarity": 1.0 if bio_similarity is not None else 0.0,
        "candidate_verified": 1.0 if candidate_verified else 0.0,
        "candidate_has_avatar": 1.0 if candidate_has_avatar else 0.0,
        "candidate_has_bio": 1.0 if candidate_has_bio else 0.0,
    }
    for k in FACTOR_KEYS:
        feats[f"factor_{k}"] = float(factors.get(k, 50.0)) / 100.0
    return feats


def to_matrix(rows: Sequence[Dict[str, float]], names: Sequence[str] = FEATURES) -> np.ndarray:
    return np.asarray([[float(r.get(n, 0.0)) for n in names] for r in rows], dtype=float)


@dataclass
class LogisticRanker:
    feature_names: List[str]
    mean: np.ndarray
    std: np.ndarray
    weights: np.ndarray
    bias: float

    def predict(self, X: np.ndarray) -> np.ndarray:
        z = ((X - self.mean) / self.std) @ self.weights + self.bias
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    def score(self, features: Dict[str, float]) -> float:
        return float(self.predict(to_matrix([features], self.feature_names))[0])

    def to_params(self) -> Dict[str, Any]:
        return {"type": "logistic_regression", "feature_names": self.feature_names,
                "mean": self.mean.tolist(), "std": self.std.tolist(),
                "weights": self.weights.tolist(), "bias": self.bias}

    @classmethod
    def from_params(cls, p: Dict[str, Any]) -> "LogisticRanker":
        return cls(list(p["feature_names"]), np.asarray(p["mean"]), np.asarray(p["std"]),
                   np.asarray(p["weights"]), float(p["bias"]))


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 50,
                 names: Sequence[str] = FEATURES) -> LogisticRanker:
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std < 1e-9] = 1.0
    Z = np.hstack([(X - mean) / std, np.ones((len(X), 1))])
    w = np.zeros(Z.shape[1])
    reg = np.full(Z.shape[1], l2)
    reg[-1] = 0.0  # don't shrink the intercept
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(Z @ w, -30, 30)))
        grad = Z.T @ (p - y) + reg * w
        hess = (Z * (p * (1 - p))[:, None]).T @ Z + np.diag(reg) + 1e-9 * np.eye(len(w))
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return LogisticRanker(list(names), mean, std, w[:-1], float(w[-1]))


@dataclass
class Example:
    user_id: Any
    created_at: Any
    features: Dict[str, float]
    label: int


@dataclass
class TrainReport:
    rows: int
    metrics: Dict[str, Any] = field(default_factory=dict)
    activated: bool = False
    version: Optional[int] = None
    reason: str = ""


def _overall(features: Dict[str, float]) -> float:
    return features.get("overall", 0.0)


def evaluate_split(examples: Sequence[Example], names: Sequence[str] = FEATURES,
                   baseline: Callable[[Dict[str, float]], float] = _overall) -> Dict[str, Any]:
    """Fit on the oldest 80%, evaluate on the newest 20%, against the heuristic baseline."""
    ordered = sorted(examples, key=lambda e: e.created_at)
    cut = int(len(ordered) * (1 - HOLDOUT_FRACTION))
    train, test = ordered[:cut], ordered[cut:]
    y_train = np.asarray([e.label for e in train], dtype=float)
    if len(train) == 0 or len(test) == 0 or y_train.min() == y_train.max():
        return {"error": "not enough labelled data of both kinds"}
    model = fit_logistic(to_matrix([e.features for e in train], names), y_train, names=names)
    y_test = [e.label for e in test]
    groups = [e.user_id for e in test]
    learned = model.predict(to_matrix([e.features for e in test], names)).tolist()
    base_scores = [baseline(e.features) for e in test]
    return {
        "train_rows": len(train), "test_rows": len(test),
        "positive_rate": float(np.mean([e.label for e in ordered])),
        "learned": {"auc": roc_auc(y_test, learned), "log_loss": log_loss(y_test, learned),
                    **grouped_ranking_metrics(groups, y_test, learned)},
        "baseline": {"auc": roc_auc(y_test, base_scores),
                     **grouped_ranking_metrics(groups, y_test, base_scores)},
    }


async def train_and_register(db: AsyncSession, examples: Sequence[Example], min_rows: int,
                             dry_run: bool = False, model_name: str = MODEL_NAME,
                             names: Sequence[str] = FEATURES,
                             baseline: Callable[[Dict[str, float]], float] = _overall) -> TrainReport:
    report = TrainReport(rows=len(examples))
    if len(examples) < min_rows:
        report.reason = f"needs at least {min_rows} labelled interactions, have {len(examples)}"
        return report
    metrics = evaluate_split(examples, names, baseline)
    report.metrics = metrics
    if "error" in metrics:
        report.reason = metrics["error"]
        return report
    learned_auc, base_auc = metrics["learned"]["auc"], metrics["baseline"]["auc"]
    beats = not np.isnan(learned_auc) and (np.isnan(base_auc) or learned_auc >= base_auc + MIN_AUC_GAIN)
    report.reason = (
        f"held-out AUC {learned_auc:.3f} vs heuristic {base_auc:.3f}: "
        + ("activated" if beats else "kept heuristic")
    )
    if dry_run:
        return report

    # Validated on the split; the stored model is refit on all data.
    y_all = np.asarray([e.label for e in examples], dtype=float)
    model = fit_logistic(to_matrix([e.features for e in examples], names), y_all, names=names)
    version = int((await db.execute(
        select(func.coalesce(func.max(MLModel.version), 0)).where(MLModel.name == model_name)
    )).scalar_one()) + 1
    if beats:
        await db.execute(update(MLModel).where(MLModel.name == model_name, MLModel.is_active.is_(True))
                         .values(is_active=False))
    db.add(MLModel(name=model_name, version=version, params=model.to_params(),
                   metrics=_jsonable(metrics), training_rows=len(examples), is_active=beats))
    await db.commit()
    _cache.pop(model_name, None)
    report.activated, report.version = beats, version
    return report


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    if isinstance(value, (np.floating, np.integer)):
        return _jsonable(value.item())
    return value


_cache: Dict[str, Dict[str, Any]] = {}  # model name -> {"model", "expires"}


async def active_ranker(db: AsyncSession, model_name: str = MODEL_NAME) -> Optional[LogisticRanker]:
    """The active model with this name, cached per process for CACHE_SECONDS."""
    now = time.monotonic()
    entry = _cache.get(model_name)
    if entry and entry["expires"] > now:
        return entry["model"]
    row = (await db.execute(
        select(MLModel).where(MLModel.name == model_name, MLModel.is_active.is_(True))
    )).scalar_one_or_none()
    model = None
    if row is not None:
        try:
            model = LogisticRanker.from_params(row.params)
        except (KeyError, ValueError, TypeError):
            logger.error("Active ranker %s has invalid parameters; using the heuristic", row.version)
    _cache[model_name] = {"model": model, "expires": now + CACHE_SECONDS}
    return model
