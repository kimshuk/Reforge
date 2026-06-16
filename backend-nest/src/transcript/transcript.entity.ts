import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  JoinColumn,
  ManyToOne,
  OneToMany,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';

import { SourceEntity } from './source.entity';
import { TranscriptSegmentEntity } from './transcript-segment.entity';

@Entity({ name: 'transcripts' })
@Index(['sourceId', 'transcriptHash'], { unique: true })
export class TranscriptEntity {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column()
  sourceId!: string;

  @ManyToOne(() => SourceEntity, (source) => source.transcripts, {
    onDelete: 'CASCADE',
  })
  @JoinColumn({ name: 'sourceId' })
  source!: SourceEntity;

  @Column()
  transcriptHash!: string;

  @Column({ type: 'text' })
  transcriptText!: string;

  @Column({ type: 'varchar', nullable: true })
  videoId!: string | null;

  @OneToMany(() => TranscriptSegmentEntity, (segment) => segment.transcript)
  segments!: TranscriptSegmentEntity[];

  @CreateDateColumn()
  createdAt!: Date;

  @UpdateDateColumn()
  updatedAt!: Date;
}
