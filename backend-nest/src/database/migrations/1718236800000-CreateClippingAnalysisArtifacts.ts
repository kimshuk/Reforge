import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateClippingAnalysisArtifacts1718236800000
  implements MigrationInterface
{
  name = 'CreateClippingAnalysisArtifacts1718236800000';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS "topic_chunks" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "sourceId" uuid NOT NULL,
        "transcriptId" uuid NOT NULL,
        "analysisRunId" uuid NOT NULL,
        "sequence" integer NOT NULL,
        "startSegmentId" varchar NOT NULL,
        "endSegmentId" varchar NOT NULL,
        "startTime" double precision NOT NULL,
        "endTime" double precision NOT NULL,
        "title" varchar NOT NULL,
        "summary" text NOT NULL,
        "signalLevel" varchar NOT NULL,
        "coverageStatus" varchar NOT NULL DEFAULT 'pending',
        "text" text NOT NULL,
        "createdAt" timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT "FK_topic_chunks_sourceId" FOREIGN KEY ("sourceId")
          REFERENCES "sources" ("id") ON DELETE CASCADE,
        CONSTRAINT "FK_topic_chunks_transcriptId" FOREIGN KEY ("transcriptId")
          REFERENCES "transcripts" ("id") ON DELETE CASCADE,
        CONSTRAINT "FK_topic_chunks_analysisRunId" FOREIGN KEY ("analysisRunId")
          REFERENCES "analysis_runs" ("id") ON DELETE CASCADE,
        CONSTRAINT "UQ_topic_chunks_analysisRunId_sequence"
          UNIQUE ("analysisRunId", "sequence")
      )
    `);

    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS "candidate_clippings" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "sourceId" uuid NOT NULL,
        "transcriptId" uuid NOT NULL,
        "analysisRunId" uuid NOT NULL,
        "topicChunkId" uuid NOT NULL,
        "kind" varchar NOT NULL,
        "title" varchar NOT NULL,
        "text" text NOT NULL,
        "brief" varchar NOT NULL,
        "level1" text NOT NULL,
        "level2" text NOT NULL,
        "level3" text NOT NULL,
        "signalLevel" varchar NOT NULL,
        "sourceRefStatus" varchar NOT NULL,
        "sourceRefs" jsonb NOT NULL,
        "createdAt" timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT "FK_candidate_clippings_sourceId" FOREIGN KEY ("sourceId")
          REFERENCES "sources" ("id") ON DELETE CASCADE,
        CONSTRAINT "FK_candidate_clippings_transcriptId" FOREIGN KEY ("transcriptId")
          REFERENCES "transcripts" ("id") ON DELETE CASCADE,
        CONSTRAINT "FK_candidate_clippings_analysisRunId" FOREIGN KEY ("analysisRunId")
          REFERENCES "analysis_runs" ("id") ON DELETE CASCADE,
        CONSTRAINT "FK_candidate_clippings_topicChunkId" FOREIGN KEY ("topicChunkId")
          REFERENCES "topic_chunks" ("id") ON DELETE CASCADE
      )
    `);

    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS "coverage_warnings" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "sourceId" uuid NOT NULL,
        "transcriptId" uuid NOT NULL,
        "analysisRunId" uuid NOT NULL,
        "reason" varchar NOT NULL,
        "startSegmentId" varchar,
        "endSegmentId" varchar,
        "startTime" double precision,
        "endTime" double precision,
        "message" text,
        "createdAt" timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT "FK_coverage_warnings_sourceId" FOREIGN KEY ("sourceId")
          REFERENCES "sources" ("id") ON DELETE CASCADE,
        CONSTRAINT "FK_coverage_warnings_transcriptId" FOREIGN KEY ("transcriptId")
          REFERENCES "transcripts" ("id") ON DELETE CASCADE,
        CONSTRAINT "FK_coverage_warnings_analysisRunId" FOREIGN KEY ("analysisRunId")
          REFERENCES "analysis_runs" ("id") ON DELETE CASCADE
      )
    `);

    await queryRunner.query(
      'CREATE INDEX IF NOT EXISTS "IDX_candidate_clippings_analysisRunId" ON "candidate_clippings" ("analysisRunId")',
    );
    await queryRunner.query(
      'CREATE INDEX IF NOT EXISTS "IDX_candidate_clippings_topicChunkId" ON "candidate_clippings" ("topicChunkId")',
    );
    await queryRunner.query(
      'CREATE INDEX IF NOT EXISTS "IDX_coverage_warnings_analysisRunId" ON "coverage_warnings" ("analysisRunId")',
    );
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query('DROP INDEX IF EXISTS "IDX_coverage_warnings_analysisRunId"');
    await queryRunner.query('DROP INDEX IF EXISTS "IDX_candidate_clippings_topicChunkId"');
    await queryRunner.query('DROP INDEX IF EXISTS "IDX_candidate_clippings_analysisRunId"');
    await queryRunner.query('DROP TABLE IF EXISTS "coverage_warnings"');
    await queryRunner.query('DROP TABLE IF EXISTS "candidate_clippings"');
    await queryRunner.query('DROP TABLE IF EXISTS "topic_chunks"');
  }
}
