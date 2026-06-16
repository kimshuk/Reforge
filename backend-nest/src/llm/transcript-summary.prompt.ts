import { ProviderPrompt, TranscriptType } from './llm.types';

export function buildTranscriptSummaryPrompt(input: {
  transcriptText: string;
  transcriptType: TranscriptType;
  targetLanguage: string;
}): ProviderPrompt {
  return {
    system: `
You summarize transcripts and identify timestamped key moments.

Return only valid JSON in this exact shape:
{
  "summary": "string",
  "timestamps": [
    {
      "time": "MM:SS or H:MM:SS",
      "title": "string",
      "summary": "string"
    }
  ]
}

Rules:
- Write summary, title, and timestamp summaries in ${input.targetLanguage}.
- summary must be concise: 3-6 sentences.
- timestamps should identify 5-10 important moments.
- Each timestamp title should be 2-8 words.
- Each timestamp summary should be one short sentence.
- Use only transcript content. Do not infer facts.
- For YouTube transcripts, lines are formatted as "S### | MM:SS | text".
- For YouTube transcripts, each time must exactly match a timestamp that appears in the transcript.
- For manual transcripts, include timestamps only when explicit timestamps appear in the text; otherwise return an empty timestamps array.
`.trim(),
    user: `Transcript type: ${input.transcriptType}
Target language: ${input.targetLanguage}
Transcript:
${input.transcriptText}`,
  };
}
