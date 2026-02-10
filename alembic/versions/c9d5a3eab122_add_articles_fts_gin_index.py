"""add articles fts gin index

Revision ID: c9d5a3eab122
Revises: 7f4b93e4b2c1
Create Date: 2026-02-10 18:05:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d5a3eab122"
down_revision: str | Sequence[str] | None = "7f4b93e4b2c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_articles_search_fts
        ON articles
        USING GIN (
            to_tsvector(
                'russian',
                coalesce(title, '') || ' ' || coalesce(text, '')
            )
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.execute("DROP INDEX IF EXISTS ix_articles_search_fts")
