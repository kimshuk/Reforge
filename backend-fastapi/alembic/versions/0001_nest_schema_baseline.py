"""Create the schema shared with the legacy Nest backend."""

from alembic import op

revision = "0001_nest_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    statements = [
        '''CREATE TABLE IF NOT EXISTS "sources" (
          "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(), "type" varchar NOT NULL,
          "provider" varchar NOT NULL, "externalId" varchar NOT NULL, "url" varchar,
          "title" varchar, "createdAt" timestamptz NOT NULL DEFAULT now(),
          "updatedAt" timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT "UQ_sources_provider_externalId" UNIQUE ("provider", "externalId"))''',
        '''CREATE TABLE IF NOT EXISTS "transcripts" (
          "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(), "sourceId" uuid NOT NULL,
          "transcriptHash" varchar NOT NULL, "transcriptText" text NOT NULL, "videoId" varchar,
          "createdAt" timestamptz NOT NULL DEFAULT now(), "updatedAt" timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT "FK_transcripts_sourceId" FOREIGN KEY ("sourceId") REFERENCES "sources" ("id") ON DELETE CASCADE,
          CONSTRAINT "UQ_transcripts_sourceId_transcriptHash" UNIQUE ("sourceId", "transcriptHash"))''',
        '''CREATE TABLE IF NOT EXISTS "transcript_segments" (
          "id" varchar PRIMARY KEY, "sourceId" uuid NOT NULL, "transcriptId" uuid NOT NULL,
          "sequence" integer NOT NULL, "startTime" double precision NOT NULL,
          "endTime" double precision NOT NULL, "rawText" text NOT NULL, "text" text NOT NULL,
          "createdAt" timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT "FK_transcript_segments_transcriptId" FOREIGN KEY ("transcriptId") REFERENCES "transcripts" ("id") ON DELETE CASCADE,
          CONSTRAINT "UQ_transcript_segments_transcriptId_sequence" UNIQUE ("transcriptId", "sequence"))''',
        '''CREATE TABLE IF NOT EXISTS "analysis_runs" (
          "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(), "sourceType" varchar NOT NULL,
          "sourceId" uuid, "transcriptId" uuid, "transcriptHash" varchar, "status" varchar NOT NULL,
          "failureStage" varchar, "errorCode" varchar, "safeErrorMessage" varchar,
          "provider" varchar NOT NULL, "model" varchar NOT NULL, "promptVersion" varchar NOT NULL,
          "schemaVersion" varchar NOT NULL, "temperature" double precision NOT NULL,
          "maxOutputTokens" integer, "createdAt" timestamptz NOT NULL DEFAULT now(),
          "updatedAt" timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT "FK_analysis_runs_sourceId" FOREIGN KEY ("sourceId") REFERENCES "sources" ("id") ON DELETE SET NULL,
          CONSTRAINT "FK_analysis_runs_transcriptId" FOREIGN KEY ("transcriptId") REFERENCES "transcripts" ("id") ON DELETE SET NULL)''',
        '''CREATE TABLE IF NOT EXISTS "topic_chunks" (
          "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(), "sourceId" uuid NOT NULL,
          "transcriptId" uuid NOT NULL, "analysisRunId" uuid NOT NULL, "sequence" integer NOT NULL,
          "startSegmentId" varchar NOT NULL, "endSegmentId" varchar NOT NULL,
          "startTime" double precision NOT NULL, "endTime" double precision NOT NULL,
          "title" varchar NOT NULL, "summary" text NOT NULL, "signalLevel" varchar NOT NULL,
          "coverageStatus" varchar NOT NULL DEFAULT 'pending', "text" text NOT NULL,
          "createdAt" timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT "FK_topic_chunks_sourceId" FOREIGN KEY ("sourceId") REFERENCES "sources" ("id") ON DELETE CASCADE,
          CONSTRAINT "FK_topic_chunks_transcriptId" FOREIGN KEY ("transcriptId") REFERENCES "transcripts" ("id") ON DELETE CASCADE,
          CONSTRAINT "FK_topic_chunks_analysisRunId" FOREIGN KEY ("analysisRunId") REFERENCES "analysis_runs" ("id") ON DELETE CASCADE,
          CONSTRAINT "UQ_topic_chunks_analysisRunId_sequence" UNIQUE ("analysisRunId", "sequence"))''',
        '''CREATE TABLE IF NOT EXISTS "candidate_clippings" (
          "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(), "sourceId" uuid NOT NULL,
          "transcriptId" uuid NOT NULL, "analysisRunId" uuid NOT NULL, "topicChunkId" uuid NOT NULL,
          "kind" varchar NOT NULL, "title" varchar NOT NULL, "text" text NOT NULL,
          "brief" varchar NOT NULL, "level1" text NOT NULL, "level2" text NOT NULL,
          "level3" text NOT NULL, "signalLevel" varchar NOT NULL, "sourceRefStatus" varchar NOT NULL,
          "sourceRefs" jsonb NOT NULL, "createdAt" timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT "FK_candidate_clippings_sourceId" FOREIGN KEY ("sourceId") REFERENCES "sources" ("id") ON DELETE CASCADE,
          CONSTRAINT "FK_candidate_clippings_transcriptId" FOREIGN KEY ("transcriptId") REFERENCES "transcripts" ("id") ON DELETE CASCADE,
          CONSTRAINT "FK_candidate_clippings_analysisRunId" FOREIGN KEY ("analysisRunId") REFERENCES "analysis_runs" ("id") ON DELETE CASCADE,
          CONSTRAINT "FK_candidate_clippings_topicChunkId" FOREIGN KEY ("topicChunkId") REFERENCES "topic_chunks" ("id") ON DELETE CASCADE)''',
        '''CREATE TABLE IF NOT EXISTS "coverage_warnings" (
          "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(), "sourceId" uuid NOT NULL,
          "transcriptId" uuid NOT NULL, "analysisRunId" uuid NOT NULL, "reason" varchar NOT NULL,
          "startSegmentId" varchar, "endSegmentId" varchar, "startTime" double precision,
          "endTime" double precision, "message" text, "createdAt" timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT "FK_coverage_warnings_sourceId" FOREIGN KEY ("sourceId") REFERENCES "sources" ("id") ON DELETE CASCADE,
          CONSTRAINT "FK_coverage_warnings_transcriptId" FOREIGN KEY ("transcriptId") REFERENCES "transcripts" ("id") ON DELETE CASCADE,
          CONSTRAINT "FK_coverage_warnings_analysisRunId" FOREIGN KEY ("analysisRunId") REFERENCES "analysis_runs" ("id") ON DELETE CASCADE)''',
        '''CREATE TABLE IF NOT EXISTS "eval_runs" (
          "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(), "provider" varchar NOT NULL,
          "model" varchar NOT NULL, "promptVersion" varchar NOT NULL, "schemaVersion" varchar NOT NULL,
          "transcriptHash" varchar NOT NULL, "latencyMs" integer NOT NULL, "estimatedCost" varchar,
          "validationErrors" jsonb NOT NULL, "rawOutput" jsonb NOT NULL, "review" jsonb NOT NULL,
          "createdAt" timestamptz NOT NULL DEFAULT now())''',
    ]
    for statement in statements:
        op.execute(statement)
    indexes = [
        'CREATE INDEX IF NOT EXISTS "IDX_analysis_runs_transcriptHash" ON "analysis_runs" ("transcriptHash")',
        'CREATE INDEX IF NOT EXISTS "IDX_candidate_clippings_analysisRunId" ON "candidate_clippings" ("analysisRunId")',
        'CREATE INDEX IF NOT EXISTS "IDX_candidate_clippings_topicChunkId" ON "candidate_clippings" ("topicChunkId")',
        'CREATE INDEX IF NOT EXISTS "IDX_coverage_warnings_analysisRunId" ON "coverage_warnings" ("analysisRunId")',
        'CREATE INDEX IF NOT EXISTS "IDX_eval_runs_transcriptHash" ON "eval_runs" ("transcriptHash")',
    ]
    for statement in indexes:
        op.execute(statement)


def downgrade() -> None:
    for table in (
        "eval_runs", "coverage_warnings", "candidate_clippings", "topic_chunks",
        "analysis_runs", "transcript_segments", "transcripts", "sources",
    ):
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
