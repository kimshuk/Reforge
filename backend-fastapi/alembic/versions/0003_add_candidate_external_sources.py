"""Add occurrence-scoped external explanation citations."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_add_candidate_external_sources"
down_revision = "0002_add_keyword_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_external_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("candidateClippingId", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("citationId", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["candidateClippingId"], ["candidate_clippings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidateClippingId", "citationId"),
        sa.UniqueConstraint("candidateClippingId", "sequence"),
        sa.UniqueConstraint("candidateClippingId", "id"),
    )
    op.create_table(
        "candidate_external_citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("candidateClippingId", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("externalSourceId", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("level IN (2, 3)"),
        sa.ForeignKeyConstraint(
            ["candidateClippingId", "externalSourceId"],
            ["candidate_external_sources.candidateClippingId", "candidate_external_sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidateClippingId", "level", "externalSourceId"),
    )


def downgrade() -> None:
    op.drop_table("candidate_external_citations")
    op.drop_table("candidate_external_sources")
