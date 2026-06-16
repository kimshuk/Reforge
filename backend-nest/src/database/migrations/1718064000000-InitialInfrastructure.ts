import { MigrationInterface, QueryRunner } from 'typeorm';

export class InitialInfrastructure1718064000000 implements MigrationInterface {
  name = 'InitialInfrastructure1718064000000';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query('SELECT 1');
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query('SELECT 1');
  }
}
