"""Add semantic keyword categories and occurrence memberships."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_add_keyword_categories"
down_revision = "0001_nest_schema_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "keyword_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("analysisRunId", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("normalizedTitle", sa.String(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysisRunId"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysisRunId", "sequence"),
        sa.UniqueConstraint("analysisRunId", "normalizedTitle"),
    )
    op.create_table(
        "keyword_category_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("analysisRunId", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("categoryId", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidateClippingId", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysisRunId"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidateClippingId"], ["candidate_clippings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["categoryId"], ["keyword_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidateClippingId"),
        sa.UniqueConstraint("categoryId", "sequence"),
    )
    op.create_index(
        "IDX_keyword_categories_analysisRunId",
        "keyword_categories",
        ["analysisRunId"],
    )
    op.create_index(
        "IDX_keyword_category_memberships_analysisRunId",
        "keyword_category_memberships",
        ["analysisRunId"],
    )
    op.execute(
        '''CREATE FUNCTION validate_keyword_category_membership_run()
        RETURNS trigger AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM keyword_categories
            WHERE id = NEW."categoryId" AND "analysisRunId" = NEW."analysisRunId"
          ) OR NOT EXISTS (
            SELECT 1 FROM candidate_clippings
            WHERE id = NEW."candidateClippingId" AND "analysisRunId" = NEW."analysisRunId"
          ) THEN
            RAISE EXCEPTION 'keyword category membership crosses analysis runs';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql'''
    )
    op.execute(
        '''CREATE CONSTRAINT TRIGGER "TRG_keyword_category_membership_run"
        AFTER INSERT OR UPDATE ON keyword_category_memberships
        DEFERRABLE INITIALLY IMMEDIATE
        FOR EACH ROW EXECUTE FUNCTION validate_keyword_category_membership_run()'''
    )


def downgrade() -> None:
    op.drop_table("keyword_category_memberships")
    op.drop_table("keyword_categories")
    op.execute("DROP FUNCTION IF EXISTS validate_keyword_category_membership_run()")
