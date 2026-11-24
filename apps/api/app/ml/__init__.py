"""
AI/ML features. Each one has a local, deterministic path, so the product works without any
paid provider, and an optional provider path that is used only when configured:

- embeddings.py / search.py: hybrid listing and "about me" search (Postgres full-text search
  fused with embedding similarity).
- ranker.py: learning-to-rank for flatmate recommendations from like/pass interactions.
- moderation.py: rule pre-screen for scams and abuse, with Claude adjudicating flagged content.
- smart_replies.py: chat reply and icebreaker suggestions.
- evaluation.py / cli.py: offline metrics, training and backfills.
"""
