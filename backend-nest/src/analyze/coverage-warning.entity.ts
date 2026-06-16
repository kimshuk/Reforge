import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
} from 'typeorm';

@Entity({ name: 'coverage_warnings' })
@Index(['analysisRunId'])
export class CoverageWarningEntity {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column()
  sourceId!: string;

  @Column()
  transcriptId!: string;

  @Column()
  analysisRunId!: string;

  @Column()
  reason!: string;

  @Column({ type: 'varchar', nullable: true })
  startSegmentId!: string | null;

  @Column({ type: 'varchar', nullable: true })
  endSegmentId!: string | null;

  @Column({ type: 'double precision', nullable: true })
  startTime!: number | null;

  @Column({ type: 'double precision', nullable: true })
  endTime!: number | null;

  @Column({ type: 'text', nullable: true })
  message!: string | null;

  @CreateDateColumn()
  createdAt!: Date;
}
