# PHASE 23.8 — Applied AI/ML Engineering Production Roadmap

**Document Version:** 1.0  
**Phase:** 23.8 — Future AI/ML Capability Specification & Governance Framework  
**Date:** November 14, 2026  
**Auditor Roles:** Principal AI Architect, Data Governance & Ethics Officer  
**Classification:** Strategic Engineering Roadmap & Compliance Framework  

---

## 1. Executive Summary

This roadmap defines the future AI/ML architecture for the Flatmate platform, transitioning from the production deterministic baseline to modular, trained machine learning models. 

In strict adherence to **Non-Negotiable Rule 0**:
- **No Synthetic Pseudo-Training:** Models will NOT be trained on fabricated or synthetic user profiles to claim false production readiness.
- **Privacy First (DPDP Act 2023):** Real training will occur only after obtaining explicit user consent for algorithmic matching and recommendation optimization.
- **Deterministic Fallback Contract:** All production AI/ML services must inherit the `BaseSemanticSearchProvider` and fallback seamlessly to the deterministic engine during outages or cold starts.

---

## 2. Modular ML Services Specifications

### Model 1: Neural Semantic Search & Hybrid Retrieval
- **Task:** Map natural language search queries (e.g. "sunlit room near Manyata Tech Park with balcony") to property vector embeddings.
- **Input:** Search query string (text).
- **Output:** Dense 384-dimensional normalized vector (using `sentence-transformers/all-MiniLM-L6-v2` or BGE-small).
- **Dataset Source:** Anonymized search queries paired with clicked and booked property listings.
- **Target Metrics:** NDCG@10 $\ge 0.82$, MRR $\ge 0.75$, latency $< 30\text{ms}$ on CPU.
- **Fallback:** `KeywordFallbackSearchProvider` (64-dim token projection).

### Model 2: Fraud & Advance-Fee Rental Scam Classifier
- **Task:** Classify chat messages and new listings for rental fraud and advance fee demands.
- **Input:** Listing text, deposit-to-rent ratio, price outlier metrics, chat text.
- **Output:** Risk probability score $P(\text{scam}) \in [0.0, 1.0]$ and explainability tokens.
- **Dataset Source:** Flagged moderation reports, verified scams, and legitimate listings.
- **Target Metrics:** Precision $\ge 0.95$ (minimize false bans), Recall $\ge 0.88$, ROC-AUC $\ge 0.96$.
- **Fairness Defense:** Reject protected attributes (religion, caste, marital status) from feature vectors.

### Model 3: Personalized Flatmate Ranking & Preference Learning
- **Task:** Re-rank candidate flatmates based on implicit engagement (swipes, profile views, chat response rate) on top of the deterministic compatibility score.
- **Input:** Pairwise compatibility factors, historical interaction CTR, response latency.
- **Output:** Personalized ranking coefficient $\gamma_{AB} \in [0.8, 1.2]$.
- **Target Metrics:** Mutual Match Conversion Rate uplift $\ge +15\%$.

---

## 3. Data Governance, Consent & Anti-Discrimination Principles

1. **Indian DPDP Act 2023 Compliance:**
   - Explicit opt-in consent collected for algorithmic profiling.
   - Users retain the right to opt out of ML personalization and revert to purely deterministic filters.
2. **Exclusion of Protected Attributes:**
   - Under no circumstances shall caste, religion, community, or dietary discrimination be reinforced by machine learning models.
   - Algorithms must be audited quarterly for disparate impact across demographic segments.
3. **Train / Validation / Test Discipline:**
   - Strict temporal splitting (train on month $T-3 \dots T-1$, validate on month $T$, test on $T+1$) to avoid future data leakage.

---

## 4. Phased Implementation Timeline

| Phase | Target Horizon | Deliverables | Gate Requirement |
| :---: | :--- | :--- | :--- |
| **Phase 1 (Current)** | Launch Gate | Deterministic 10-dimension heuristic + Lexical token search | 100% verified, 0 inference cost |
| **Phase 2** | Post-Launch + 3 Months | LightGBM Listing Scam Detector | 5,000 verified moderation samples |
| **Phase 3** | Post-Launch + 6 Months | ONNX Sentence-Transformer Semantic Search | pgvector hosted index enabled |
| **Phase 4** | Post-Launch + 12 Months | Two-Tower Recommendation Model | 50,000+ active user interactions |
