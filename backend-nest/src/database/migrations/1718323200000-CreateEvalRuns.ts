import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateEvalRuns1718323200000 implements MigrationInterface {
  name = 'CreateEvalRuns1718323200000';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      CREATE TABLE IF NOT EXISTS "eval_runs" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "provider" varchar NOT NULL,
        "model" varchar NOT NULL,
        "promptVersion" varchar NOT NULL,
        "schemaVersion" varchar NOT NULL,
        "transcriptHash" varchar NOT NULL,
        "latencyMs" integer NOT NULL,
        "estimatedCost" varchar,
        "validationErrors" jsonb NOT NULL,
        "rawOutput" jsonb NOT NULL,
        "review" jsonb NOT NULL,
        "createdAt" timestamptz NOT NULL DEFAULT now()
      )
    `);
    await queryRunner.query(
      'CREATE INDEX IF NOT EXISTS "IDX_eval_runs_transcriptHash" ON "eval_runs" ("transcriptHash")',
    );
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query('DROP INDEX IF EXISTS "IDX_eval_runs_transcriptHash"');
    await queryRunner.query('DROP TABLE IF EXISTS "eval_runs"');
  }
}
