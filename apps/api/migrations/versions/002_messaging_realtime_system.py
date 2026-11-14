"""messaging realtime system

Revision ID: 002_messaging_realtime
Revises: 001_initial_schema
Create Date: 2026-11-13 23:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_messaging_realtime'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update conversations table with new context columns
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'title') THEN
                ALTER TABLE conversations ADD COLUMN title VARCHAR(255) NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'application_id') THEN
                ALTER TABLE conversations ADD COLUMN application_id UUID NULL REFERENCES applications(id) ON DELETE SET NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'group_id') THEN
                ALTER TABLE conversations ADD COLUMN group_id UUID NULL REFERENCES groups(id) ON DELETE SET NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'flatmate_match_id') THEN
                ALTER TABLE conversations ADD COLUMN flatmate_match_id UUID NULL REFERENCES mutual_matches(id) ON DELETE SET NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'status') THEN
                ALTER TABLE conversations ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'active';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'context_metadata') THEN
                ALTER TABLE conversations ADD COLUMN context_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
            END IF;
        END $$;
    """))

    # 2. Update conversation_participants table with role and status
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversation_participants' AND column_name = 'role') THEN
                ALTER TABLE conversation_participants ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'member';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversation_participants' AND column_name = 'left_at') THEN
                ALTER TABLE conversation_participants ADD COLUMN left_at TIMESTAMPTZ NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversation_participants' AND column_name = 'is_active') THEN
                ALTER TABLE conversation_participants ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
            END IF;
        END $$;
    """))

    # 3. Update messages table with idempotency, reply, edit, delete
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'idempotency_key') THEN
                ALTER TABLE messages ADD COLUMN idempotency_key VARCHAR(64) NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'reply_to_message_id') THEN
                ALTER TABLE messages ADD COLUMN reply_to_message_id UUID NULL REFERENCES messages(id) ON DELETE SET NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'is_edited') THEN
                ALTER TABLE messages ADD COLUMN is_edited BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'edited_at') THEN
                ALTER TABLE messages ADD COLUMN edited_at TIMESTAMPTZ NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'is_deleted') THEN
                ALTER TABLE messages ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'messages' AND column_name = 'deleted_at') THEN
                ALTER TABLE messages ADD COLUMN deleted_at TIMESTAMPTZ NULL;
            END IF;
        END $$;
    """))

    # 4. Create attachments table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS attachments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            message_id UUID NULL REFERENCES messages(id) ON DELETE CASCADE,
            uploader_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            file_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(512) NOT NULL,
            mime_type VARCHAR(100) NOT NULL,
            file_size_bytes BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_attachments_conv ON attachments(conversation_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_attachments_msg ON attachments(message_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_attachments_uploader ON attachments(uploader_id)"))

    # 5. Create conversation_read_cursors table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS conversation_read_cursors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            last_read_message_id UUID NULL REFERENCES messages(id) ON DELETE SET NULL,
            last_read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_conv_read_cursor UNIQUE (conversation_id, user_id)
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_read_cursor_user ON conversation_read_cursors(user_id, last_read_at)"))

    # 6. Create conversation_preferences table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS conversation_preferences (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            is_muted BOOLEAN NOT NULL DEFAULT FALSE,
            muted_until TIMESTAMPTZ NULL,
            is_archived BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_conv_user_pref UNIQUE (conversation_id, user_id)
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_conv_pref_archived ON conversation_preferences(user_id, is_archived)"))

    # 7. Create outbox_events table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS outbox_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type VARCHAR(64) NOT NULL,
            payload JSONB NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ NULL
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_outbox_status_created ON outbox_events(status, created_at)"))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS outbox_events CASCADE;"))
    op.execute(sa.text("DROP TABLE IF EXISTS conversation_preferences CASCADE;"))
    op.execute(sa.text("DROP TABLE IF EXISTS conversation_read_cursors CASCADE;"))
    op.execute(sa.text("DROP TABLE IF EXISTS attachments CASCADE;"))
