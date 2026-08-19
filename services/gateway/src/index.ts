import { loadConfig } from "./config.js";
import { buildServer } from "./server.js";

const config = loadConfig();
const app = await buildServer(config);

// Kubernetes sends SIGTERM on every rollout. Node's default action is immediate
// exit, which truncates in-flight SSE streams and the minutes-long sweep proxy —
// `terminationGracePeriodSeconds` means nothing without this. Fastify's close()
// stops accepting and drains what is already running.
for (const signal of ["SIGTERM", "SIGINT"] as const) {
  process.once(signal, () => {
    app.log.info({ signal }, "draining");
    void app
      .close()
      .then(() => process.exit(0))
      .catch((error) => {
        app.log.error(error);
        process.exit(1);
      });
  });
}

try {
  await app.listen({ host: config.host, port: config.port });
} catch (error) {
  app.log.error(error);
  process.exit(1);
}
