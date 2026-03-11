require("dotenv").config();

const express = require("express");
const { randomUUID } = require("crypto");

const analyzeRoute = require("./routes/analyze");
const transcriptRoute = require("./routes/transcript");
const logger = require("./services/logger");
const { notFoundHandler, errorHandler } = require("./middleware/errorHandler");

const app = express();
const PORT = Number(process.env.PORT || 3000);

app.use(express.json({ limit: "1mb" }));

app.use((req, res, next) => {
  req.requestId = randomUUID();
  const start = Date.now();

  res.on("finish", () => {
    logger.info("http.request", {
      requestId: req.requestId,
      method: req.method,
      path: req.originalUrl,
      statusCode: res.statusCode,
      durationMs: Date.now() - start,
    });
  });

  next();
});

app.get("/health", (_req, res) => {
  res.status(200).json({ ok: true });
});

app.use("/analyze", analyzeRoute);
app.use("/transcript", transcriptRoute);

app.use(notFoundHandler);
app.use(errorHandler);

app.listen(PORT, () => {
  logger.info("server.started", { port: PORT });
});
