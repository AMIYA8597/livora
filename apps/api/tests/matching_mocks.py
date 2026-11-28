"""Mock results for MatchingService.record_interaction, which loads both people's earlier
decisions (mine about them, theirs about me) in a single query."""
from unittest.mock import MagicMock


def interactions_found(*rows):
    """What `select(MatchInteraction)` for the pair returns: zero, one or both decisions."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(rows)
    return result
