const OpenAI = require("openai");
const { AppError } = require("../middleware/errorHandler");

function createOpenAIClient() {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new AppError(500, "OPENAI_API_KEY_MISSING", "OPENAI_API_KEY is not configured");
  }

  return new OpenAI({ apiKey });
}

module.exports = createOpenAIClient();
