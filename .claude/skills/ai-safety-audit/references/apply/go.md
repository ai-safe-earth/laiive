# Applying controls in Go

Idioms per tier for Go services that call a model or run an agent loop. Deep analysis is
Python-only, so every AUD-401..406 finding in Go is a co-located grep hit (a sink within 60
lines of a model call sharing an identifier): read the code before proposing a change.
Standard-library names below are stable; for third-party SDKs check the current docs.

## T1 -- config

- AUD-601: pin the model id in one config value (`Model: "gpt-4o-2024-11-20"`-style dated
  names, never `-latest`).
- AUD-602: Dockerfiles `RUN` lines pin versions; images by `@sha256:` digest.
- AUD-106: the service's env carries a scoped credential (read-only DB role, narrow token),
  not the deploy account's.
- AUD-802: a guard error is a denied call: `if err != nil { return ErrDenied }`, never
  `_ = guard(...)`.

## T2 -- gates and files

### Approval gate on irreversible tools (AUD-201, AUD-202)

    var requiresApproval = map[string]bool{"send_email": true, "delete_record": true}

    func dispatch(ctx context.Context, call ToolCall) (string, error) {
        fn, ok := tools[call.Name]            // fixed table; the model picks a name only
        if !ok {
            return "", fmt.Errorf("unknown tool %q", call.Name)
        }
        if requiresApproval[call.Name] {
            ok, err := approvals.Wait(ctx, call) // a human can say no; a stub returning true is AUD-202
            if err != nil || !ok {
                return "", ErrDenied
            }
        }
        return fn(ctx, call.Args)
    }

### Iteration cap and deadline (AUD-102)

    ctx, cancel := context.WithTimeout(ctx, 2*time.Minute)
    defer cancel()
    const maxIterations = 20
    for i := 0; i < maxIterations; i++ {
        if err := ctx.Err(); err != nil {
            return err
        }
        ...
    }
    return ErrIterationCap

Pass `ctx` into every model and tool call so the deadline propagates.

### Kill switch and budget (AUD-107, AUD-105)

    if os.Getenv("AGENT_DISABLED") == "1" { return ErrDisabled } // read per request, not at init

    if s.toolCalls.Add(1) > maxToolCallsPerSession { return ErrBudget } // atomic.Int64

### URL allowlist (AUD-103, AUD-405)

    u, err := url.Parse(raw)
    if err != nil || u.Scheme != "https" || !allowedHosts[u.Hostname()] {
        return ErrHostNotAllowed
    }
    client := &http.Client{Timeout: 10 * time.Second,
        CheckRedirect: func(r *http.Request, via []*http.Request) error { return http.ErrUseLastResponse }}
    body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))

### Audit log (AUD-702) and tracing (AUD-701)

One JSON line per tool call with `log/slog`: `slog.Info("tool_call", "session", id,
"tool", name, "args_sha256", h, "decision", d, "approver", who, "outcome", o)`. Log hashes and
lengths of prompts, not their text (AUD-504). For LLM tracing, OpenTelemetry spans carrying
`gen_ai.*` attributes; a generic APM alone yields `AUD-701/apm-only`.

## T3 -- restructuring

- AUD-401: `exec.CommandContext(ctx, name, args...)` with `name` from an allowlist; never
  `exec.Command("sh", "-c", s)` where `s` contains model output.
- AUD-402: Go has no `eval`; the equivalent is dispatching through `reflect` or a plugin
  on a model-chosen name. Use a fixed map of functions instead.
- AUD-403: `db.QueryContext(ctx, "select ... where id = $1", id)` (`database/sql`
  placeholders; `?` for MySQL); never `fmt.Sprintf` into SQL text. A read-only role for the
  agent's connection.
- AUD-404: `html/template` escapes by default; `template.HTML(s)` on model output turns that
  off and is the finding. For rich text, `github.com/microcosm-cc/bluemonday` with a strict
  policy (check the current docs).
- AUD-406: `p := filepath.Join(base, name); rel, err := filepath.Rel(base, p); if err !=
  nil || strings.HasPrefix(rel, "..") { deny }` before `os.WriteFile`; no `os.RemoveAll` on
  model-derived paths.
- AUD-301: split the service so the handler that reads private data cannot reach the
  client that sends; exchange a validated struct between them; untrusted content goes to a
  separate model call whose output is data.
- AUD-203: a `DryRun bool` field on irreversible tool inputs and an `Idempotency-Key`
  header (or a stored key) per external write.

## Verify (phase 5, with approval)

`go test ./...` (`verify.sh` detects it from `go.mod`). If the service exposes an HTTP chat
endpoint on loopback, `aisg probe http://127.0.0.1:<port>/chat -o probe-report.json` through
the bootstrap chain; only `passed` means passed.
