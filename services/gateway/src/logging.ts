import type { FastifyInstance } from "fastify";
import type { GatewayConfig } from "./config.js";

const LOGGED_ROUTES = [/^\/api\/chat(\/|$)/, /^\/api\/push\/(chat|validate-event)(\/|$)/];
// /api/chat/feedback sits under the chat prefix but is not a conversation:
// its reason already lands in turn_feedback, and logging it here would store
// that free text twice, under the feedback request's own id rather than the
// turn's.
const EXCLUDED_ROUTE = /^\/api\/chat\/feedback([/?]|$)/;

/**
 * Fire-and-forget conversation capture into Supabase `conversation_logs`
 * (replaces the old validate-conversation edge function). Request-side only:
 * response bodies stream through the proxy and are not buffered here — the
 * answer side is the retriever's eval_records write, joined on request_id.
 * Payload is only available on the chat routes (parsed JSON); upload routes
 * stream past and log metadata only.
 */
export function registerConversationLogging(app: FastifyInstance, config: GatewayConfig): void {
  if (!config.conversationLogging) return;

  const endpoint = `${config.supabaseUrl}/rest/v1/conversation_logs`;
  const headers = {
    "content-type": "application/json",
    apikey: config.supabaseServiceRoleKey,
    authorization: `Bearer ${config.supabaseServiceRoleKey}`,
    prefer: "return=minimal",
  };

  app.addHook("onResponse", (request, reply, done) => {
    done();
    if (request.method !== "POST") return;
    if (!LOGGED_ROUTES.some((route) => route.test(request.url))) return;
    if (EXCLUDED_ROUTE.test(request.url)) return;

    const body = request.body;
    const payload =
      body !== null && typeof body === "object" && !Buffer.isBuffer(body) && !("pipe" in body)
        ? body
        : null;

    fetch(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify({
        request_id: request.id,
        user_id: request.user?.id ?? null,
        user_role: request.user?.role ?? "anon",
        route: request.url.split("?")[0],
        status: reply.statusCode,
        duration_ms: Math.round(reply.elapsedTime),
        payload,
      }),
    }).catch((error: unknown) => {
      request.log.warn({ err: error }, "conversation log insert failed");
    });
  });
}
