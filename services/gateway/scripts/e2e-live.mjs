/**
 * Live end-to-end check of the gateway against the real Supabase project and
 * the real services (Phase 3 verify step of docs/refactor/04-plan.md).
 *
 * The vitest suite fakes Supabase; this one proves the parts that only a live
 * project can: the custom access token hook actually stamping `user_role`, JWKS
 * verification of real ES256 tokens, role routing, and unbuffered SSE through
 * the proxy.
 *
 * Prerequisites — retriever :8002, pusher :8003, gateway :8000 all running, and
 * SUPABASE_SERVICE_ROLE_KEY set in the root .env.
 *
 *   node scripts/e2e-live.mjs          (from services/gateway)
 *
 * It creates two throwaway auth users and deletes them again at the end.
 */
import path from "node:path";
import process from "node:process";
import dotenv from "dotenv";

dotenv.config({ path: path.resolve(process.cwd(), "../../.env") });

const GATEWAY = process.env.E2E_GATEWAY_URL ?? "http://localhost:8000";
const SUPABASE_URL = (process.env.SUPABASE_URL ?? "").replace(/\/$/, "");
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";
const PASSWORD = "e2e-Passw0rd!-laiive"; // pragma: allowlist secret — throwaway users, deleted at the end
const USERS = [
  { email: "e2e-user@laiive.test", role: "user" },
  { email: "e2e-pro@laiive.test", role: "pro" },
  { email: "e2e-admin@laiive.test", role: "admin" },
];

if (!SUPABASE_URL || !SERVICE_KEY || SERVICE_KEY.startsWith("PASTE_")) {
  console.error("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing from the root .env");
  process.exit(2);
}

let passed = 0;
const failures = [];

function check(name, ok, detail = "") {
  if (ok) {
    passed += 1;
    console.log(`  ok   ${name}`);
  } else {
    failures.push(`${name}${detail ? ` — ${detail}` : ""}`);
    console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ""}`);
  }
}

const admin = (path, init = {}) =>
  fetch(`${SUPABASE_URL}${path}`, {
    ...init,
    headers: {
      apikey: SERVICE_KEY,
      authorization: `Bearer ${SERVICE_KEY}`,
      "content-type": "application/json",
      ...(init.headers ?? {}),
    },
  });

function decodeClaims(jwt) {
  return JSON.parse(Buffer.from(jwt.split(".")[1], "base64url").toString("utf8"));
}

/** Deletes any leftover user with this email (previous interrupted run). */
async function purge(email) {
  const listed = await admin("/auth/v1/admin/users?per_page=200").then((r) => r.json());
  for (const user of listed.users ?? []) {
    if (user.email === email) {
      await admin(`/auth/v1/admin/users/${user.id}`, { method: "DELETE" });
    }
  }
}

/** Create (or recreate) a confirmed user and give it `role` in user_roles. */
async function provision({ email, role }) {
  const create = () =>
    admin("/auth/v1/admin/users", {
      method: "POST",
      body: JSON.stringify({ email, password: PASSWORD, email_confirm: true }),
    }).then((r) => r.json());

  let created = await create();
  if (!created.id) {
    await purge(email);
    created = await create();
  }
  if (!created.id) throw new Error(`could not create ${email}: ${JSON.stringify(created)}`);

  if (role !== "user") {
    const res = await admin(`/rest/v1/user_roles?user_id=eq.${created.id}`, {
      method: "PATCH",
      headers: { prefer: "return=representation" },
      body: JSON.stringify({ role }),
    });
    const rows = await res.json();
    if (!Array.isArray(rows) || rows[0]?.role !== role) {
      throw new Error(`could not set role ${role}: ${JSON.stringify(rows)}`);
    }
  }

  const session = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: SERVICE_KEY, "content-type": "application/json" },
    body: JSON.stringify({ email, password: PASSWORD }),
  }).then((r) => r.json());
  if (!session.access_token) throw new Error(`no session for ${email}: ${JSON.stringify(session)}`);

  return { id: created.id, email, role, token: session.access_token };
}

async function cleanup(users) {
  for (const user of users) {
    await admin(`/auth/v1/admin/users/${user.id}`, { method: "DELETE" }).catch(() => {});
  }
}

/** /chat/stream body — retriever ChatRequestSSE. */
const chatBody = () =>
  JSON.stringify({
    messages: [{ role: "user", content: "jazz concerts in Barcelona" }],
  });

/** Reads an SSE response, returning the chunk count and total bytes. */
async function readStream(res, maxChunks = 40) {
  const reader = res.body.getReader();
  let chunks = 0;
  let bytes = 0;
  let text = "";
  while (chunks < maxChunks) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks += 1;
    bytes += value.length;
    text += Buffer.from(value).toString("utf8");
  }
  await reader.cancel().catch(() => {});
  return { chunks, bytes, text };
}

/**
 * The run ends by deliberately exhausting the anonymous per-IP budget, so a
 * second run inside the same window would see 429s everywhere. Wait it out.
 */
async function waitForAnonBudget() {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const res = await fetch(`${GATEWAY}/healthz`, { headers: { "x-probe": "budget" } });
    const remaining = Number(res.headers.get("x-ratelimit-remaining") ?? "99");
    const probe = await fetch(`${GATEWAY}/api/push/health`);
    if (probe.status !== 429) return;
    const wait = Number(probe.headers.get("retry-after") ?? "10");
    console.log(`  … anon rate-limit window still open (${remaining} left), waiting ${wait}s`);
    await new Promise((resolve) => setTimeout(resolve, (wait + 1) * 1000));
  }
  console.log("  … anon budget never freed up; anonymous checks may fail");
}

async function main() {
  console.log(`gateway ${GATEWAY} | supabase ${SUPABASE_URL}\n`);

  const health = await fetch(`${GATEWAY}/healthz`).then((r) => r.json());
  check("gateway /healthz", health.status === "ok", JSON.stringify(health));

  const users = [];
  try {
    for (const spec of USERS) users.push(await provision(spec));

    console.log("\n-- JWT claims (custom access token hook) --");
    for (const user of users) {
      const claims = decodeClaims(user.token);
      check(
        `${user.role} token carries user_role=${user.role}`,
        claims.user_role === user.role,
        `got ${JSON.stringify(claims.user_role)} — is the access token hook registered?`,
      );
    }

    const [normal, pro, adminUser] = users;

    console.log("\n-- anonymous chat (D7) --");
    await waitForAnonBudget();
    const anon = await fetch(`${GATEWAY}/api/chat/stream`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: chatBody("v2"),
    });
    check("anon POST /api/chat/stream 200", anon.status === 200, `got ${anon.status}`);
    check("x-login-upsell header on anon", Boolean(anon.headers.get("x-login-upsell")));
    check("x-request-id header", Boolean(anon.headers.get("x-request-id")));
    const anonStream = await readStream(anon);
    check(
      "SSE arrives unbuffered (multiple chunks)",
      anonStream.chunks > 1,
      `${anonStream.chunks} chunk(s), ${anonStream.bytes} bytes`,
    );
    check("SSE frames look like the protocol", anonStream.text.includes("data:"));

    console.log("\n-- token validity --");
    const bogus = await fetch(`${GATEWAY}/api/chat/stream`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: "Bearer not.a.jwt" },
      body: chatBody(),
    });
    check("garbage bearer → 401", bogus.status === 401, `got ${bogus.status}`);

    const malformed = await fetch(`${GATEWAY}/api/chat/stream`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: SERVICE_KEY },
      body: chatBody(),
    });
    check("malformed authorization → 401", malformed.status === 401, `got ${malformed.status}`);

    console.log("\n-- role routing --");
    const pushAnon = await fetch(`${GATEWAY}/api/push/health`);
    check("anon /api/push → 401", pushAnon.status === 401, `got ${pushAnon.status}`);

    const pushUser = await fetch(`${GATEWAY}/api/push/health`, {
      headers: { authorization: `Bearer ${normal.token}` },
    });
    check("user role /api/push → 403", pushUser.status === 403, `got ${pushUser.status}`);

    const pushPro = await fetch(`${GATEWAY}/api/push/health`, {
      headers: { authorization: `Bearer ${pro.token}` },
    });
    check("pro role /api/push → 200", pushPro.status === 200, `got ${pushPro.status}`);

    const searchPro = await fetch(`${GATEWAY}/api/admin/search/ping`, {
      headers: { authorization: `Bearer ${pro.token}` },
    });
    check("pro role /api/admin/search → 403", searchPro.status === 403, `got ${searchPro.status}`);

    const searchAdmin = await fetch(`${GATEWAY}/api/admin/search/ping`, {
      headers: { authorization: `Bearer ${adminUser.token}` },
    });
    check(
      "admin role /api/admin/search → 503 (Phase 5 not deployed)",
      searchAdmin.status === 503,
      `got ${searchAdmin.status}`,
    );

    console.log("\n-- identity spoofing --");
    const spoofed = await fetch(`${GATEWAY}/api/push/health`, {
      headers: {
        authorization: `Bearer ${normal.token}`,
        "x-user-role": "admin",
        "x-user-id": "00000000-0000-0000-0000-000000000000",
      },
    });
    check(
      "client-sent X-User-Role cannot escalate → 403",
      spoofed.status === 403,
      `got ${spoofed.status}`,
    );

    console.log("\n-- authed chat --");
    const authed = await fetch(`${GATEWAY}/api/chat/stream`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${pro.token}` },
      body: chatBody(),
    });
    check("pro POST /api/chat/stream 200", authed.status === 200, `got ${authed.status}`);
    check("no upsell header when authed", !authed.headers.get("x-login-upsell"));
    // Drain: the log row is written in onResponse, i.e. after the last frame.
    await readStream(authed, 500);

    console.log("\n-- conversation logging --");
    let logs = [];
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      logs = await admin(
        `/rest/v1/conversation_logs?select=route,user_role,user_id&order=created_at.desc&limit=10`,
      ).then((r) => r.json());
      if (Array.isArray(logs) && logs.some((row) => row.user_id === pro.id)) break;
    }
    check(
      "chat requests landed in conversation_logs",
      Array.isArray(logs) && logs.some((row) => row.route.includes("/api/chat")),
      JSON.stringify(logs).slice(0, 200),
    );
    check(
      "authed log row carries the verified user id",
      Array.isArray(logs) && logs.some((row) => row.user_id === pro.id),
    );

    // Last: this exhausts the anonymous per-IP budget for the window.
    console.log("\n-- anonymous rate limit --");
    let limited = null;
    for (let i = 0; i < 15 && !limited; i += 1) {
      const res = await fetch(`${GATEWAY}/api/push/health`);
      if (res.status === 429) limited = await res.json();
    }
    check("anon burst → 429", Boolean(limited), "no 429 within 15 requests");
    check(
      "429 body upsells signing in",
      Boolean(limited?.message?.includes("sign in")),
      JSON.stringify(limited),
    );
  } finally {
    await cleanup(users);
  }

  console.log(`\n${passed} passed, ${failures.length} failed`);
  if (failures.length > 0) {
    for (const failure of failures) console.log(`  - ${failure}`);
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
