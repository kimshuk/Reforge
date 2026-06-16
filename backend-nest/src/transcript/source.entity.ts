import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  OneToMany,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';

import { TranscriptEntity } from './transcript.entity';

@Entity({ name: 'sources' })
@Index(['provider', 'externalId'], { unique: true })
export class SourceEntity {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column()
  type!: string;

  @Column()
  provider!: string;

  @Column()
  externalId!: string;

  @Column({ nullable: true })
  url!: string | null;

  @Column({ nullable: true })
  title!: string | null;

  @OneToMany(() => TranscriptEntity, (transcript) => transcript.source)
  transcripts!: TranscriptEntity[];

  @CreateDateColumn()
  createdAt!: Date;

  @UpdateDateColumn()
  updatedAt!: Date;
}
