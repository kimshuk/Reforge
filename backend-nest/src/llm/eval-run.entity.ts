import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
} from 'typeorm';

@Entity({ name: 'eval_runs' })
@Index(['transcriptHash'])
export class EvalRunEntity {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column()
  provider!: string;

  @Column()
  model!: string;

  @Column()
  promptVersion!: string;

  @Column()
  schemaVersion!: string;

  @Column()
  transcriptHash!: string;

  @Column()
  latencyMs!: number;

  @Column({ type: 'varchar', nullable: true })
  estimatedCost!: string | null;

  @Column({ type: 'jsonb' })
  validationErrors!: string[];

  @Column({ type: 'jsonb' })
  rawOutput!: unknown;

  @Column({ type: 'jsonb' })
  review!: {
    schemaValidity: string | null;
    majorTopicCoverage: string | null;
    candidateUsefulness: string | null;
    neutrality: string | null;
    sourceGrounding: string | null;
    redundancy: string | null;
    titleClarity: string | null;
    explanationFaithfulness: string | null;
    latencyCost: string | null;
  };

  @CreateDateColumn()
  createdAt!: Date;
}
