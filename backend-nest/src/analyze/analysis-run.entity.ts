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

  @Column({ nullable: true })
  sourceId!: string | null;

  @Column({ nullable: true })
  transcriptId!: string | null;

  @Column({ nullable: true })
  transcriptHash!: string | null;

  @Column()
  status!: string;

  @Column({ nullable: true })
  failureStage!: string | null;

  @Column({ nullable: true })
  errorCode!: string | null;

  @Column({ nullable: true })
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

  @Column({ nullable: true })
  maxOutputTokens!: number | null;

  @CreateDateColumn()
  createdAt!: Date;

  @UpdateDateColumn()
  updatedAt!: Date;
}
