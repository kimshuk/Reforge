import { LlmProviderAdapter } from './llm.types';
import { LlmService } from './llm.service';

function serviceWithPayload(payload: unknown) {
  const adapter: LlmProviderAdapter = {
    provider: 'openai',
    generateJson: jest.fn().mockResolvedValue(JSON.stringify(payload)),
  };

  return new LlmService([adapter]);
}

const validCandidate = {
  kind: 'claim',
  title: 'Pricing Pressure',
  text: 'The speaker says competitors are pushing prices down.',
  brief: 'Competitors are pushing prices down',
  simpleExplanation: 'Pricing pressure means outside forces make prices harder to maintain.',
  contextualExplanation:
    'In this chunk, the speaker says competitors are pushing prices down. They connect that pressure to the team needing a clearer response.',
  detailedExplanation:
    'The speaker claims competitors are pushing prices down and making the current approach harder to defend. Their reasoning is that buyers now compare options more directly, so the team needs a clearer response. The implication is that pricing cannot be treated as a static decision in this part of the discussion.',
  signalLevel: 'high',
  sourceRefs: [
    {
      startSegmentId: 'seg_1',
      endSegmentId: 'seg_2',
      timestamp: '00:10',
      text: 'competitors are pushing prices down',
    },
  ],
};

async function generateCandidate(overrides: Record<string, unknown> = {}) {
  const service = serviceWithPayload({
    candidateClippings: [{ ...validCandidate, ...overrides }],
  });

  return service.generateCandidateClippings({
    chunkTitle: 'Market Response',
    chunkSummary: 'Pricing and competitor response',
    chunkSegments:
      'seg_1 | 00:10 | competitors are pushing prices down\nseg_2 | 00:20 | we need a clearer response',
    targetLanguage: 'English',
    options: {
      provider: 'openai',
      model: 'test-model',
      temperature: 0,
    },
  });
}

describe('LlmService candidate clipping contract', () => {
  it('maps semantic explanation fields to compatibility levels', async () => {
    await expect(generateCandidate()).resolves.toEqual([
      expect.objectContaining({
        simpleExplanation: validCandidate.simpleExplanation,
        contextualExplanation: validCandidate.contextualExplanation,
        detailedExplanation: validCandidate.detailedExplanation,
      }),
    ]);
  });

  it('rejects repeated explanation levels', async () => {
    await expect(
      generateCandidate({
        contextualExplanation: validCandidate.simpleExplanation,
      }),
    ).rejects.toMatchObject({
      code: 'LLM_CLIPPINGS_INVALID_JSON',
    });
  });

  it('rejects explanations that do not grow in detail', async () => {
    await expect(
      generateCandidate({
        detailedExplanation: 'Too short.',
      }),
    ).rejects.toMatchObject({
      code: 'LLM_CLIPPINGS_INVALID_JSON',
    });
  });

  it('accepts source refs that drop the label prefix and canonicalizes them', async () => {
    const service = serviceWithPayload({
      candidateClippings: [
        {
          ...validCandidate,
          sourceRefs: [
            {
              startSegmentId: '001',
              endSegmentId: '002',
              timestamp: '00:10',
              text: 'competitors are pushing prices down',
            },
          ],
        },
      ],
    });

    const result = await service.generateCandidateClippings({
      chunkTitle: 'Market Response',
      chunkSummary: 'Pricing and competitor response',
      chunkSegments:
        'S001 | 00:10 | competitors are pushing prices down\nS002 | 00:20 | we need a clearer response',
      targetLanguage: 'English',
      options: { provider: 'openai', model: 'test-model', temperature: 0 },
    });

    expect(result[0].sourceRefs[0]).toMatchObject({
      startSegmentId: 'S001',
      endSegmentId: 'S002',
    });
  });

  it('rejects source refs outside the parent topic chunk', async () => {
    await expect(
      generateCandidate({
        sourceRefs: [
          {
            startSegmentId: 'seg_1',
            endSegmentId: 'seg_999',
            timestamp: '00:10',
            text: 'competitors are pushing prices down',
          },
        ],
      }),
    ).rejects.toMatchObject({
      code: 'LLM_CLIPPINGS_INVALID_SOURCE_REF',
    });
  });
});
