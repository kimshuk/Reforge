import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
} from 'typeorm';

@Entity({ name: 'topic_chunks' })
@Index(['analysisRunId', 'sequence'], { unique: true })
export class TopicChunkEntity {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column()
  sourceId!: string;

  @Column()
  transcriptId!: string;

  @Column()
  analysisRunId!: string;

  @Column()
  sequence!: number;

  @Column()
  startSegmentId!: string;

  @Column()
  endSegmentId!: string;

  @Column({ type: 'double precision' })
  startTime!: number;

  @Column({ type: 'double precision' })
  endTime!: number;

  @Column()
  title!: string;

  @Column({ type: 'text' })
  summary!: string;

  @Column()
  signalLevel!: string;

  @Column()
  coverageStatus!: string;

  @Column({ type: 'text' })
  text!: string;

  @CreateDateColumn()
  createdAt!: Date;
}
