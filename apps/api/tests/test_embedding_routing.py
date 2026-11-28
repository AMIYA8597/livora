"""Which embedder each kind of text goes to: listings may use Voyage, people's bios stay on the
server unless EXTERNAL_PROFILE_EMBEDDINGS is turned on."""
import pytest

from app.core.config import settings
from app.ml import embeddings
from app.ml.embeddings import LocalHashingEmbedder, VoyageEmbedder, get_embedder


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
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.ml import indexing

    db = AsyncMock()
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=["u1"]))))
    with patch.object(indexing, "refresh_embedding", AsyncMock(return_value="updated")) as refresh:
        await indexing.backfill(db, "profile")
    assert isinstance(refresh.call_args.args[3], LocalHashingEmbedder)
