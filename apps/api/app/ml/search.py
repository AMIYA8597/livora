"""
Hybrid search: Postgres full-text search fused with embedding similarity.

Each retriever returns up to CANDIDATES ids in its own order; Reciprocal Rank Fusion
(score = sum of 1 / (RRF_K + rank)) merges them. RRF needs no score calibration between the two
retrievers, and a document both agree on rises to the top.

- Lexical: `websearch_to_tsquery('english', q)` against `properties.search_tsv` (weighted title >
  locality > description, GIN index) or an on-the-fly vector over profile bios. Handles stemming
  ("furnished" ~ "furnishing") and quoted phrases / -exclusions. Documents matching every word
  come first; documents matching only some words follow, so one typo or an extra word
  ("koramangla pet friendly") doesn't empty the results.
- Semantic: the query is embedded with the configured provider and compared with stored vectors
  of the same model. With pgvector this is an HNSW index scan; without it (local dev) the
  newest SCAN_LIMIT vectors are scored in numpy. Matches below the provider's similarity floor
  are dropped so unrelated documents never fill the results.

If the embedding provider fails, search silently degrades to lexical only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

import numpy as np
import re

from sqlalchemy import ColumnElement, Select, Text, cast, func, literal_column, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession

from pgvector.sqlalchemy import Vector

from app.ml.embeddings import EMBEDDING_DIM, Embedder, EmbeddingUnavailable, get_embedder
from app.ml.indexing import has_vector_index
from app.ml.models import ContentEmbedding
from app.modules.profiles.models import Profile
from app.modules.properties.models import Property

logger = logging.getLogger("flatmate.ml.search")

RRF_K = 60
CANDIDATES = 200
SCAN_LIMIT = 3000
MAX_QUERY_CHARS = 300


@dataclass
class SearchRanking:
    ids: List[UUID]
    retrievers: List[str] = field(default_factory=list)  # which retrievers contributed


def rrf_fuse(rankings: Sequence[Sequence[UUID]], k: int = RRF_K) -> List[UUID]:
    scores: Dict[UUID, float] = {}
    first_seen: Dict[UUID, int] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            first_seen.setdefault(doc_id, rank)
    return sorted(scores, key=lambda d: (-scores[d], first_seen[d], str(d)))


async def _semantic(
    db: AsyncSession, entity_type: str, eligible_ids: Select, query: str, embedder: Embedder,
    newest_first,
) -> Optional[List[UUID]]:
    try:
        [qvec] = await embedder.embed([query], kind="query")
    except EmbeddingUnavailable as exc:
        logger.warning("Semantic search unavailable, using lexical only: %s", exc)
        return None

    base = (
        select(ContentEmbedding.entity_id)
        .where(
            ContentEmbedding.entity_type == entity_type,
            ContentEmbedding.model == embedder.model_id,
            ContentEmbedding.entity_id.in_(eligible_ids),
        )
    )
    if await has_vector_index(db):
        vec_col = literal_column("content_embeddings.embedding_vec", type_=Vector(EMBEDDING_DIM))
        distance = vec_col.cosine_distance(qvec)
        stmt = (
            base.add_columns((1 - distance).label("similarity"))
            .order_by(distance)
            .limit(CANDIDATES)
        )
        rows = (await db.execute(stmt)).all()
        return [r[0] for r in rows if r[1] >= embedder.min_similarity]

    stmt = base.add_columns(ContentEmbedding.embedding).order_by(newest_first).limit(SCAN_LIMIT)
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []
    matrix = np.asarray([r[1] for r in rows], dtype=np.float32)
    q = np.asarray(qvec, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(q) or 1.0)
    sims = (matrix @ q) / np.where(norms == 0, 1.0, norms)
    order = np.argsort(-sims)[:CANDIDATES]
    return [rows[i][0] for i in order if sims[i] >= embedder.min_similarity]


def clean_query(q: Optional[str]) -> str:
    return " ".join((q or "").split())[:MAX_QUERY_CHARS]


# Quotes, "-word" exclusions and "or" are websearch operators: an any-word fallback would ignore
# them (and return what the user excluded), so such queries get only the exact matches.
_OPERATORS = re.compile(r'"|(^|\s)-\S|\bor\b', re.IGNORECASE)


_EXCLUDED = re.compile(r'(?:^|\s)-([^\s"]+)')


def split_exclusions(query: str) -> tuple[str, List[str]]:
    """'furnished flat -shared' -> ('furnished flat', ['shared'])."""
    excluded = _EXCLUDED.findall(query)
    return " ".join(_EXCLUDED.sub(" ", query).split()), excluded


def _without(id_col, eligible_ids: Select, doc, excluded: List[str]) -> Select:
    """Narrow the eligible ids to documents mentioning none of the excluded words. Both retrievers
    then honour "-word"; embeddings alone would treat "shared" as something to look for."""
    if not excluded:
        return eligible_ids
    banned = func.websearch_to_tsquery("english", " or ".join(excluded))
    return select(id_col).where(id_col.in_(eligible_ids), ~doc.op("@@")(banned))


async def _lexical(db: AsyncSession, id_col, eligible_ids: Select, doc, query: str, tiebreak) -> List[UUID]:
    all_words = func.websearch_to_tsquery("english", query)
    stmt = (
        select(id_col)
        .where(id_col.in_(eligible_ids), doc.op("@@")(all_words))
        .order_by(func.ts_rank_cd(doc, all_words).desc(), tiebreak)
        .limit(CANDIDATES)
    )
    ids = list((await db.execute(stmt)).scalars().all())
    if len(ids) >= CANDIDATES or _OPERATORS.search(query):
        return ids
    # plainto_tsquery only joins lexemes with "&"; swapping in "|" gives an any-word query.
    any_word = cast(func.replace(cast(func.plainto_tsquery("english", query), Text), "&", "|"), TSQUERY)
    stmt = (
        select(id_col)
        .where(id_col.in_(eligible_ids), doc.op("@@")(any_word))
        .order_by(func.ts_rank_cd(doc, any_word).desc(), tiebreak)
        .limit(CANDIDATES - len(ids))
    )
    if ids:
        stmt = stmt.where(id_col.not_in(ids))
    return ids + list((await db.execute(stmt)).scalars().all())


async def rank_properties(
    db: AsyncSession, query: str, eligible_ids: Select, embedder: Optional[Embedder] = None
) -> SearchRanking:
    """`eligible_ids` is a SELECT of Property.id with the caller's filters already applied."""
    embedder = embedder or get_embedder()
    tsv: ColumnElement[Any] = literal_column("properties.search_tsv")
    positive, excluded = split_exclusions(query)
    eligible_ids = _without(Property.id, eligible_ids, tsv, excluded)
    lexical = await _lexical(db, Property.id, eligible_ids, tsv, query, Property.created_at.desc())

    semantic_join_order = (
        select(Property.created_at).where(Property.id == ContentEmbedding.entity_id)
        .scalar_subquery().desc()
    )
    semantic = (
        await _semantic(db, "property", eligible_ids, positive, embedder, semantic_join_order)
        if positive else []
    )

    rankings, used = [lexical], ["full_text"]
    if semantic is not None:
        rankings.append(semantic)
        used.append(f"embeddings:{embedder.model_id}")
    return SearchRanking(ids=rrf_fuse(rankings), retrievers=used)


async def rank_profiles(
    db: AsyncSession, query: str, eligible_user_ids: Select, embedder: Optional[Embedder] = None
) -> SearchRanking:
    """"About me" search over bios, occupation and lifestyle. Ids are user ids."""
    embedder = embedder or get_embedder()
    doc = func.to_tsvector(
        "english",
        func.coalesce(Profile.bio, "") + " " + func.coalesce(Profile.occupation, ""),
    )
    positive, excluded = split_exclusions(query)
    eligible_user_ids = _without(Profile.user_id, eligible_user_ids, doc, excluded)
    lexical = await _lexical(
        db, Profile.user_id, eligible_user_ids, doc, query, Profile.updated_at.desc().nullslast()
    )

    newest = (
        select(Profile.updated_at).where(Profile.user_id == ContentEmbedding.entity_id)
        .scalar_subquery().desc().nullslast()
    )
    semantic = (
        await _semantic(db, "profile", eligible_user_ids, positive, embedder, newest) if positive else []
    )

    rankings, used = [lexical], ["full_text"]
    if semantic is not None:
        rankings.append(semantic)
        used.append(f"embeddings:{embedder.model_id}")
    return SearchRanking(ids=rrf_fuse(rankings), retrievers=used)
