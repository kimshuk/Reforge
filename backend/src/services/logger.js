function log(level, event, metadata = {}) {
  const payload = {
    timestamp: new Date().toISOString(),
    level,
    event,
    ...metadata,
  };

  const line = JSON.stringify(payload);
  if (level === "error") {
    console.error(line);
    return;
  }

  console.log(line);
}

module.exports = {
  info: (event, metadata) => log("info", event, metadata),
  warn: (event, metadata) => log("warn", event, metadata),
  error: (event, metadata) => log("error", event, metadata),
};
