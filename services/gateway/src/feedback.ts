import type { FastifyInstance } from "fastify";
import type { GatewayConfig } from "./config.js";

/**
 * Thumbs-down on an assistant turn (eval phase 1). Anonymous allowed — chat
 * is. The static route wins over the /api/chat/* proxy wildcard. The
 * request_id is the turn's x-request-id, which joins conversation_logs (full
 * client-sent history) and eval_records (the answer).
 */
export function registerFeedback(app: FastifyInstance, config: GatewayConfig): void {
  const endpoint = `${config.supabaseUrl}/rest/v1/turn_feedback`;
  const headers = {
    "content-type": "application/json",
    apikey: config.supabaseServiceRoleKey,
    authorization: `Bearer ${config.supabaseServiceRoleKey}`,
    prefer: "return=minimal",
  };

  app.post("/api/chat/feedback", async (request, reply) => {
    const body = request.body as { request_id?: unknown; reason?: unknown } | null;
    const requestId = body?.request_id;
    const reason = body?.reason ?? null;
    if (typeof requestId !== "string" || requestId.length === 0 || requestId.length > 128) {
      return reply.code(400).send({ error: "request_id required" });
    }
    if (reason !== null && (typeof reason !== "string" || reason.length > 2000)) {
      return reply.code(400).send({ error: "reason must be a string of at most 2000 chars" });
    }

    const response = await fetch(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify({
        request_id: requestId,
        user_id: request.user?.id ?? null,
        reason,
      }),
    });
    if (!response.ok) {
      request.log.error({ status: response.status }, "turn_feedback insert failed");
      return reply.code(502).send({ error: "feedback not recorded" });
    }
    return reply.code(204).send();
  });
}
