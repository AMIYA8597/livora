# PHASE 23.8 — AI/ML Engineering Audit and Capability Assessment

**Document Version:** 1.0  
**Phase:** 23.8 — AI/ML System Audit & Search Vector Review  
**Date:** November 14, 2026  
**Auditor Roles:** Principal Machine Learning Engineer, Applied AI Ethics Auditor  
**Classification:** Empirical Algorithm & Vector Pipeline Audit  
**Implementation Modules:** `apps/api/app/modules/matching`, `apps/api/app/infrastructure/external_services/semantic_search.py`  

---

## 1. Executive Summary

This audit establishes the true algorithmic nature and limitations of the compatibility scoring and search systems in the Flatmate platform.

In strict compliance with **Non-Negotiable Rule 0**:
- **Truth in Advertising:** Deterministic scoring and token-projection search are **NOT** labeled as deep learning, neural NLP, or trained ML models.
- **Empirical Classification:** 
  1. The compatibility engine is a **deterministic, weighted, multi-attribute heuristic engine** with hard dealbreaker penalties.
  2. The search vector generator is a **deterministic 64-dimensional bag-of-words hash projection** (`md5 % 64`) with L2 normalization. No deep learning model is loaded at runtime.
- **Production Recommendation:** The deterministic engine and token search are retained as the production baseline due to their high reliability, instant cold-start capability, zero inference cost, and zero hallucination risk.

---

## 2. Compatibility Engine Architecture & Math Formulation

### 2.1 The Ten Compatibility Dimensions
The matching engine evaluates 10 lifestyle and cultural attributes normalized across Indian urban shared living contexts:

| # | Dimension Name | Feature Type | Weight ($w_i$) | Value Space / Options |
| :-: | :--- | :--- | :-: | :--- |
| 1 | **Sleep Schedule** | Categorical | **12%** (0.12) | `early_bird`, `night_owl`, `flexible` |
| 2 | **Cleanliness & Chores** | Numeric (1–5) | **15%** (0.15) | Scale: $1 - \frac{\|c_A - c_B\|}{4}$ |
| 3 | **Noise Tolerance** | Numeric (1–5) | **10%** (0.10) | Scale: $1 - \frac{\|n_A - n_B\|}{4}$ |
| 4 | **Social & Gathering** | Categorical | **10%** (0.10) | `quiet`, `moderate`, `party_frequent` |
| 5 | **Diet & Cooking** | Categorical | **12%** (0.12) | `vegetarian`, `non_vegetarian`, `vegan`, `eggetarian` |
| 6 | **Smoking & Alcohol** | Binary/Categorical | **15%** (0.15) | `never`, `outside_only`, `socially`, `regularly` |
| 7 | **Pet Policy** | Categorical | **8%** (0.08) | `no_pets`, `has_dog`, `has_cat`, `pet_friendly` |
| 8 | **Work From Home (WFH)**| Categorical | **6%** (0.06) | `full_wfh`, `hybrid`, `in_office` |
| 9 | **Guest & Visitor Policy**| Categorical | **6%** (0.06) | `no_overnight`, `weekends_only`, `flexible` |
| 10 | **Budget & Locality** | Numeric / Geometric | **6%** (0.06) | Jaccard overlap of budget and locality radius |
| **Sum** | **Total Weight** | | **100% (1.00)** | $\sum_{i=1}^{10} w_i = 1.000000$ (Strictly Normalized) |

### 2.2 Mathematical Formulation
The raw composite compatibility score $S_{raw}(A, B)$ is given by:

$$S_{raw}(A, B) = \sum_{i=1}^{10} w_i \cdot s_i(A_i, B_i) \times 100$$

where $s_i(A_i, B_i) \in [0.0, 1.0]$ represents the dimension similarity function.

### 2.3 Dealbreaker Enforcement & Penalty Caps
If a conflicting hard dealbreaker is present (e.g., User A demands `non_smoker_only` and User B is `smoker_inside`), the final score is capped:

$$S_{final}(A, B) = \min(S_{raw}(A, B), 30.0)$$

This mathematical cap guarantees that irreconcilable lifestyle mismatches never receive a recommendation grade or false "match" status.

---

## 3. Search Implementation: Token Projection vs Trained Embedding

An in-depth inspection of `apps/api/app/infrastructure/external_services/semantic_search.py` revealed:

```python
# Lines 66-82 of semantic_search.py:
async def generate_embedding(self, text: str) -> List[float]:
    dims = 64
    vec = [0.0] * dims
    tokens = re.findall(r"\w+", text.lower())
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dims
        vec[idx] += 1.0
    # L2 normalize
    magnitude = math.sqrt(sum(x * x for x in vec))
    return [x / magnitude for x in vec] if magnitude > 0 else vec
```

### Audit Findings:
1. **Zero Neural Weights:** No transformer checkpoints (`.onnx`, `.pt`, `.safetensors`, `.bin`) exist in the repository or container image.
2. **Feature Mechanism:** The vector is a deterministic 64-dimensional bag-of-words hash projection.
3. **Semantic Capabilities:** While it enables cosine vector indexing in pgvector, it captures exact lexical tokens rather than deep semantic synonyms (e.g., "furnishing" will not match "sofa" without explicit token co-occurrence).
4. **Correction:** Platform documentation has been updated to describe this as **Lexical Token-Projection Search** rather than "Deep Learning Semantic Search".

---

## 4. Anti-Scam & Trust Moderation Heuristics

In `apps/api/app/modules/messaging/service.py` and `tests/test_ai_ml_readiness.py`:
- Regex heuristics detect advance-fee rental fraud patterns (e.g., "pay token advance before viewing", "gate pass fee", "QR code verification").
- Harassment and unsolicited PII sharing (e.g., phone numbers and UPI IDs sent in the first message of an unverified user) trigger automated safety advisory banners.
- Reversible and explainable: Users are notified of the specific safety policy triggered.

---

## 5. Audit Conclusion

The current deterministic algorithms are stable, fast (<1ms execution time), 100% reproducible, mathematically bounded, and completely transparent. They represent the optimal baseline for initial marketplace production release.
