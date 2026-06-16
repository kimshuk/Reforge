import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  JoinColumn,
  ManyToOne,
  PrimaryColumn,
} from 'typeorm';

import { TranscriptEntity } from './transcript.entity';

@Entity({ name: 'transcript_segments' })
@Index(['transcriptId', 'sequence'], { unique: true })
export class TranscriptSegmentEntity {
  @PrimaryColumn()
  id!: string;

  @Column()
  sourceId!: string;

  @Column()
  transcriptId!: string;

  @ManyToOne(() => TranscriptEntity, (transcript) => transcript.segments, {
    onDelete: 'CASCADE',
  })
  @JoinColumn({ name: 'transcriptId' })
  transcript!: TranscriptEntity;

  @Column()
  sequence!: number;

  @Column({ type: 'double precision' })
  startTime!: number;

  @Column({ type: 'double precision' })
  endTime!: number;

  @Column({ type: 'text' })
  rawText!: string;

  @Column({ type: 'text' })
  text!: string;

  @CreateDateColumn()
  createdAt!: Date;
}
