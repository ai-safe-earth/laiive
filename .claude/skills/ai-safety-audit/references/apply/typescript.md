# Applying controls in TypeScript / JavaScript

Idioms per tier for Node and browser code. Library APIs move; where a name is quoted below,
check the current docs before writing it into the user's code. Deep analysis is Python-only,
so every AUD-401..406 finding in TypeScript is a co-located grep hit: read the code first.

## T1 -- config

- AUD-101 / AUD-108: `.claude/settings.json` `permissions.allow` lists exact commands, not
  `Bash(*)` or `Bash(npx*)`; hooks run scripts the repo ships, never `curl ... | sh` or
  `npx -y <pkg>` (pin: `npx -y <pkg>@1.2.3`).
- AUD-602 / AUD-603: `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`: pin server
  packages, use `stdio` or loopback / `https://` transports, and reference secrets as
  `${ENV_VAR}` (AUD-502), never as literals.
- AUD-601: pin model ids (`gpt-4o-2024-11-20`-style dated names, not aliases).
- AUD-802: no `catch {}` around a guard call; a failed guard is a denied call.

## T2 -- gates and files

### Approval gate on tools (AUD-201, AUD-202)

Vercel AI SDK (v5 and later) lets a tool declare that it needs approval before `execute`
runs; the loop then surfaces a pending approval the application must resolve before
continuing:

    import { tool } from "ai";
    import { z } from "zod";

    export const sendEmail = tool({
      description: "Send an email",
      inputSchema: z.object({ to: z.string().email(), body: z.string() }),
      needsApproval: true,            // or (input) => boolean; check the current docs
      execute: async ({ to, body }) => mailer.send(to, body),
    });

Without that SDK, gate in the dispatch loop: look the tool up in a fixed table
(`TOOLS[name]`), and for names in `REQUIRES_APPROVAL` await a human decision that can
return `false`. A gate that always resolves `true` is AUD-202.

### MCP client allowlist (AUD-301 untrusted leg, AUD-604)

When connecting an MCP client, filter the server's tool list before handing it to the
model instead of exposing everything the server advertises:

    const allowed = new Set(["search_docs", "read_ticket"]);
    const { tools } = await client.listTools();
    const exposed = tools.filter((t) => allowed.has(t.name));

Treat `description` strings from a remote server as untrusted input the model reads every
turn; pin the server version and review descriptions on upgrade.

### URL allowlist (AUD-103, AUD-405)

    const ALLOWED_HOSTS = new Set(["docs.example.com"]);
    const u = new URL(input);
    if (u.protocol !== "https:" || !ALLOWED_HOSTS.has(u.hostname)) throw new Error("host not allowed");
    const res = await fetch(u, { signal: AbortSignal.timeout(10_000) });

Cap the response size when reading the body.

### Iteration cap, budget and kill switch (AUD-102, AUD-105, AUD-107)

    const MAX_STEPS = 20;
    for (let step = 0; step < MAX_STEPS; step++) {
      if (process.env.AGENT_DISABLED === "1") throw new Error("agent disabled");
      if (toolCalls >= MAX_TOOL_CALLS) throw new Error("tool budget exhausted");
      ...
    }

`maxSteps` / `stopWhen` options exist in agent SDKs; a named constant in the loop is the
version the audit can see.

### Audit log (AUD-702) and observability (AUD-701)

Append one JSON line per tool call (`ts`, `session`, `tool`, `argsHash`, `decision`,
`approver`, `outcome`) with `pino` or `winston` to a file the app never truncates. For LLM
tracing use an OpenTelemetry GenAI instrumentation, Langfuse or LangSmith; a generic APM
(Sentry, Datadog) alone yields `AUD-701/apm-only`.

### PII and secrets (AUD-503, AUD-504)

Redact before logging (`console.log(completion)` is AUD-504); pass credentials to tools out
of band, never inside prompt text. This package has no TypeScript runtime; LLM Guard (via a
sidecar) or a provider-side moderation endpoint are the usual detectors here.

## T3 -- restructuring

- AUD-401: `execFile(cmd, args)` / `spawn(cmd, args)` with `cmd` from an allowlist; never
  `exec(\`${modelOutput}\`)` and never `{ shell: true }` with model-derived strings.
- AUD-402: `JSON.parse` into a validated schema (zod), then dispatch by name; no
  `new Function(...)`, `eval`, or `vm.runInNewContext` on model output.
- AUD-403: parameterised queries: `client.query("select * from t where id = $1", [id])`
  (pg), `?` placeholders (mysql2), the query builder's bindings (knex, prisma); never a
  template literal with model text inside the SQL.
- AUD-404: React text nodes escape by default; for the rare rich-text case
  `DOMPurify.sanitize(html)` before `dangerouslySetInnerHTML` / `innerHTML`; server-side,
  `isomorphic-dompurify` or `sanitize-html`. Never `v-html` / `{{{ }}}` on model output.
- AUD-406: `path.resolve(base, name)` and check `startsWith(base + path.sep)` before any
  `fs.writeFile`; no `fs.rm` with `recursive: true` on model-derived paths.
- AUD-301: a reader agent (private data, no external action) and a writer agent (external
  action, no private data) exchanging a validated object; untrusted content quarantined in
  its own model call whose output is data.
- AUD-203: a `dryRun` flag on irreversible tools and an idempotency key per external write.

## Verify (phase 5, with approval)

`npm test` if `package.json` defines it (`verify.sh` detects and prints it). If the app
serves an HTTP chat endpoint, `aisg probe http://127.0.0.1:<port>/chat -o probe-report.json`
(through the bootstrap chain); only `passed` means passed.
