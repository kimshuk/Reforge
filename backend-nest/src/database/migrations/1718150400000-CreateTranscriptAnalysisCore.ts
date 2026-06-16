import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateTranscriptAnalysisCore1718150400000
  implements MigrationInterface
{
  name = 'CreateTranscriptAnalysisCore1718150400000';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query('CREATE EXTENSION IF NOT EXISTS "pgcrypto"');

    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS "sources" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "type" varchar NOT NULL,
        "provider" varchar NOT NULL,
        "externalId" varchar NOT NULL,
        "url" varchar,
        "title" varchar,
        "createdAt" timestamptz NOT NULL DEFAULT now(),
        "updatedAt" timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT "UQ_sources_provider_externalId" UNIQUE ("provider", "externalId")
      )
    `);

    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS "transcripts" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "sourceId" uuid NOT NULL,
        "transcriptHash" varchar NOT NULL,
        "transcriptText" text NOT NULL,
        "videoId" varchar,
        "createdAt" timestamptz NOT NULL DEFAULT now(),
        "updatedAt" timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT "FK_transcripts_sourceId" FOREIGN KEY ("sourceId")
          REFERENCES "sources" ("id") ON DELETE CASCADE,
        CONSTRAINT "UQ_transcripts_sourceId_transcriptHash"
          UNIQUE ("sourceId", "transcriptHash")
      )
    `);

    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS "transcript_segments" (
        "id" varchar PRIMARY KEY,
        "sourceId" uuid NOT NULL,
        "transcriptId" uuid NOT NULL,
        "sequence" integer NOT NULL,
        "startTime" double precision NOT NULL,
        "endTime" double precision NOT NULL,
        "rawText" text NOT NULL,
        "text" text NOT NULL,
        "createdAt" timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT "FK_transcript_segments_transcriptId" FOREIGN KEY ("transcriptId")
          REFERENCES "transcripts" ("id") ON DELETE CASCADE,
        CONSTRAINT "UQ_transcript_segments_transcriptId_sequence"
          UNIQUE ("transcriptId", "sequence")
      )
    `);

    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS "analysis_runs" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "sourceType" varchar NOT NULL,
        "sourceId" uuid,
        "transcriptId" uuid,
        "transcriptHash" varchar,
        "status" varchar NOT NULL,
        "failureStage" varchar,
        "errorCode" varchar,
        "safeErrorMessage" varchar,
        "provider" varchar NOT NULL,
        "model" varchar NOT NULL,
        "promptVersion" varchar NOT NULL,
        "schemaVersion" varchar NOT NULL,
        "temperature" double precision NOT NULL,
        "maxOutputTokens" integer,
        "createdAt" timestamptz NOT NULL DEFAULT now(),
        "updatedAt" timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT "FK_analysis_runs_sourceId" FOREIGN KEY ("sourceId")
          REFERENCES "sources" ("id") ON DELETE SET NULL,
        CONSTRAINT "FK_analysis_runs_transcriptId" FOREIGN KEY ("transcriptId")
          REFERENCES "transcripts" ("id") ON DELETE SET NULL
      )
    `);

    await queryRunner.query(
      'CREATE INDEX IF NOT EXISTS "IDX_analysis_runs_transcriptHash" ON "analysis_runs" ("transcriptHash")',
    );
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query('DROP INDEX IF EXISTS "IDX_analysis_runs_transcriptHash"');
    await queryRunner.query('DROP TABLE IF EXISTS "analysis_runs"');
    await queryRunner.query('DROP TABLE IF EXISTS "transcript_segments"');
    await queryRunner.query('DROP TABLE IF EXISTS "transcripts"');
    await queryRunner.query('DROP TABLE IF EXISTS "sources"');
  }
}
