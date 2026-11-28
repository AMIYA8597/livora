"""Which embedder each kind of text goes to: listings may use Voyage, people's bios stay on the
server unless EXTERNAL_PROFILE_EMBEDDINGS is turned on."""
import json
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.config import settings
from app.ml import embeddings
from app.ml.embeddings import EmbeddingUnavailable, LocalHashingEmbedder, VoyageEmbedder, get_embedder


@pytest.fixture
def voyage_on(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "voyage")
    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "pa-test")
    get_embedder.cache_clear()
    yield monkeypatch
    get_embedder.cache_clear()


def test_listings_use_voyage_but_bios_stay_on_the_server(voyage_on):
    listing = get_embedder("property")
    assert isinstance(listing, VoyageEmbedder) and listing.model_id == "voyage:voyage-4-lite:512"
    assert isinstance(get_embedder(), VoyageEmbedder)
    assert isinstance(get_embedder("profile"), LocalHashingEmbedder)


def test_bios_go_to_voyage_only_when_allowed(voyage_on):
    voyage_on.setattr(settings, "EXTERNAL_PROFILE_EMBEDDINGS", True)
    get_embedder.cache_clear()
    assert isinstance(get_embedder("profile"), VoyageEmbedder)


def test_both_fit_the_vector_column():
    assert LocalHashingEmbedder().dimensions == embeddings.EMBEDDING_DIM == 512


@pytest.mark.asyncio
async def test_the_backfill_embeds_profiles_with_the_profile_embedder(voyage_on):
    from unittest.mock import AsyncMock, patch

    from app.ml import indexing

    seen = []

    class Recording(LocalHashingEmbedder):
        async def embed(self, texts, kind):
            seen.append(type(self))
            return await super().embed(texts, kind)

    db = AsyncMock()
    ids_result = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=["u1"]))))
    none_result = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    db.execute.side_effect = [ids_result, none_result]
    db.add = MagicMock()
    with patch.object(indexing, "_source_text", AsyncMock(return_value="likes cooking")),          patch.object(indexing, "get_embedder", return_value=Recording()) as pick:
        result = await indexing.backfill(db, "profile")
    pick.assert_called_once_with("profile")
    assert seen == [Recording] and result.updated == 1


def _voyage_with(monkeypatch, handler):
    """A VoyageEmbedder whose HTTP calls go to `handler` instead of the network."""
    real_client = httpx.AsyncClient
    monkeypatch.setattr(embeddings.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    return VoyageEmbedder("pa-test", "voyage-4-lite")


def _vectors(request):
    texts = json.loads(request.content)["input"]
    return httpx.Response(200, json={"data": [
        {"index": i, "embedding": [1.0] + [0.0] * 511} for i in range(len(texts))]})


@pytest.mark.asyncio
async def test_repeated_searches_reuse_the_query_vector(monkeypatch):
    calls = []

    def handler(request):
        calls.append(json.loads(request.content)["input"])
        return _vectors(request)

    voyage = _voyage_with(monkeypatch, handler)
    await voyage.embed(["Quiet room near metro"], kind="query")
    await voyage.embed(["  quiet ROOM near metro "], kind="query")
    await voyage.embed(["Quiet room near metro"], kind="document")  # documents are never cached
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_a_rate_limit_pauses_voyage_instead_of_retrying_every_search(monkeypatch):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "30"}, json={"detail": "rate limited"})

    voyage = _voyage_with(monkeypatch, handler)
    with pytest.raises(EmbeddingUnavailable, match="HTTP 429"):
        await voyage.embed(["pet friendly"], kind="query")
    with pytest.raises(EmbeddingUnavailable, match="cooling down"):
        await voyage.embed(["near the lake"], kind="query")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_many_documents_go_in_one_request(monkeypatch):
    sizes = []

    def handler(request):
        sizes.append(len(json.loads(request.content)["input"]))
        return _vectors(request)

    voyage = _voyage_with(monkeypatch, handler)
    out = await voyage.embed([f"listing {n}" for n in range(130)], kind="document")
    assert len(out) == 130 and sizes == [128, 2]


def test_neural_matches_must_be_close_to_the_best_one():
    from app.core.database import QueryStats
    from app.ml.search import _keep_close_matches

    stats = QueryStats()
    scored = [("pg", 0.52), ("co-living", 0.49), ("studio", 0.43), ("far", 0.15)]
    assert _keep_close_matches(scored, VoyageEmbedder("k", "voyage-4-lite"), stats) == ["pg", "co-living"]
    assert stats.search == "kept=2/4 top=0.520 floor=0.460"
    # The local embedder has no margin: only its absolute floor applies.
    assert _keep_close_matches(scored, LocalHashingEmbedder()) == ["pg", "co-living", "studio", "far"]
    assert _keep_close_matches([], VoyageEmbedder("k", "voyage-4-lite")) == []
