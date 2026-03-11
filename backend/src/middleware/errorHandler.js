const logger = require("../services/logger");

class AppError extends Error {
  constructor(statusCode, code, message) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
  }
}

function notFoundHandler(req, res) {
  res.status(404).json({
    error: {
      code: "NOT_FOUND",
      message: `Route not found: ${req.method} ${req.path}`,
    },
  });
}

function errorHandler(err, req, res, _next) {
  const statusCode = Number.isInteger(err.statusCode) ? err.statusCode : 500;
  const code = err.code || "INTERNAL_SERVER_ERROR";
  const message = statusCode >= 500 ? "Internal server error" : err.message;

  logger.error("request.error", {
    requestId: req.requestId,
    method: req.method,
    path: req.path,
    statusCode,
    code,
    message: err.message,
  });

  res.status(statusCode).json({
    error: {
      code,
      message,
    },
  });
}

module.exports = {
  AppError,
  notFoundHandler,
  errorHandler,
};
