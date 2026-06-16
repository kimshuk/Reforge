import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';

@Entity({ name: 'analysis_runs' })
@Index(['transcriptHash'])
export class AnalysisRunEntity {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column()
  sourceType!: string;

  @Column({ type: 'uuid', nullable: true })
  sourceId!: string | null;

  @Column({ type: 'uuid', nullable: true })
  transcriptId!: string | null;

  @Column({ type: 'varchar', nullable: true })
  transcriptHash!: string | null;

  @Column()
  status!: string;

  @Column({ type: 'varchar', nullable: true })
  failureStage!: string | null;

  @Column({ type: 'varchar', nullable: true })
  errorCode!: string | null;

  @Column({ type: 'varchar', nullable: true })
  safeErrorMessage!: string | null;

  @Column()
  provider!: string;

  @Column()
  model!: string;

  @Column()
  promptVersion!: string;

  @Column()
  schemaVersion!: string;

  @Column({ type: 'double precision' })
  temperature!: number;

  @Column({ type: 'integer', nullable: true })
  maxOutputTokens!: number | null;

  @CreateDateColumn()
  createdAt!: Date;

  @UpdateDateColumn()
  updatedAt!: Date;
}
