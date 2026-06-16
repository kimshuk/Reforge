import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
} from 'typeorm';

@Entity({ name: 'candidate_clippings' })
@Index(['analysisRunId'])
@Index(['topicChunkId'])
export class CandidateClippingEntity {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column()
  sourceId!: string;

  @Column()
  transcriptId!: string;

  @Column()
  analysisRunId!: string;

  @Column()
  topicChunkId!: string;

  @Column()
  kind!: string;

  @Column()
  title!: string;

  @Column({ type: 'text' })
  text!: string;

  @Column()
  brief!: string;

  @Column({ type: 'text' })
  level1!: string;

  @Column({ type: 'text' })
  level2!: string;

  @Column({ type: 'text' })
  level3!: string;

  @Column()
  signalLevel!: string;

  @Column()
  sourceRefStatus!: string;

  @Column({ type: 'jsonb' })
  sourceRefs!: Array<{
    startSegmentId: string;
    endSegmentId: string;
    timestamp: string;
    ref: string;
    text?: string;
  }>;

  @CreateDateColumn()
  createdAt!: Date;
}
