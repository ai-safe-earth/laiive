import type { EventDraft, WalkState } from "@shared/protocol";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import type { ChatMessage } from "@/api/chat";
import { ApiError } from "@/api/client";
import { ingestFile } from "@/api/ingest";
import { saveEvent, streamSubmission } from "@/api/push";
import { Composer } from "@/components/Composer";
import { EventForm } from "@/components/EventForm";
import { Icon } from "@/components/Icon";
import { Mark } from "@/components/Mark";
import { Markdown } from "@/components/Markdown";
import { ProOnboarding } from "@/components/ProOnboarding";
import { ProWatermark } from "@/components/ProWatermark";
import { UserMenu } from "@/components/UserMenu";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/auth/AuthProvider";
import { useTranslation } from "@/i18n/useTranslation";

const ACCEPTED =
  "image/*,audio/*,.pdf,.docx,.txt,.md,.csv";

/**
 * A multi-event walk survives a page reload: the draft set lives only in the
 * browser (the server is stateless), so losing it would lose the promoter's
 * place mid-walk.
 */
const STORAGE_KEY = "laiive-pro-submission";

interface StoredSession {
  messages: ChatMessage[];
  walk: WalkState | null;
  draft: EventDraft | null;
  missing: string[];
}

function loadSession(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

/** The PRO badge — cyan, mono, the promoter side's one mark of identity. */
function ProBadge() {
  return (
    <span className="rounded-full border border-pro-accent/45 bg-pro-accent/[0.12] px-2 py-[5px] font-mono text-[9.5px] font-medium uppercase leading-none tracking-[0.11em] text-pro-accent">
      pro
    </span>
  );
}

export default function ProSubmit() {
  const { user, role, isLoading } = useAuth();
  const { t } = useTranslation();

  const restored = useRef(loadSession()).current;

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(restored?.messages ?? []);
  const [walk, setWalk] = useState<WalkState | null>(restored?.walk ?? null);
  const [draft, setDraft] = useState<EventDraft | null>(restored?.draft ?? null);
  const [missing, setMissing] = useState<string[]>(restored?.missing ?? []);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // `busy` covers the whole turn, ingest included; `streaming` only the part a
  // stop can actually abort, so the composer never offers a stop that is a lie.
  const [streaming, setStreaming] = useState(false);
  const [saving, setSaving] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, draft, status]);

  useEffect(() => {
    if (messages.length === 0 && !walk && !draft) {
      sessionStorage.removeItem(STORAGE_KEY);
    } else {
      const session: StoredSession = { messages, walk, draft, missing };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    }
  }, [messages, walk, draft, missing]);

  if (isLoading) return null;
  if (!user || (role !== "pro" && role !== "admin")) {
    return (
      <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-4 bg-pro-bg p-6 text-center">
        <span className="flex items-center gap-2.5">
          <Mark size={30} />
          <ProBadge />
        </span>
        <p className="max-w-sm text-[15px] leading-[1.5] text-pro-fg">{t.pro.needsPro}</p>
        <Link
          to={user ? "/account" : "/auth?kind=pro"}
          // So /account's back arrow returns here rather than dumping a
          // promoter on the consumer chat, which is a different product.
          state={user ? { from: "/pro" } : undefined}
          className="text-[13.5px] text-pro-accent transition-opacity hover:opacity-80"
        >
          {user ? t.pro.becomeProLink : t.pro.signInLink}
        </Link>
      </div>
    );
  }

  /**
   * Send the conversation up. Outside a walk the server re-extracts over all
   * of it; mid-walk we echo the draft set + cursor back (`walkEcho`) and it
   * refines only the current event.
   */
  const runTurn = async (
    history: ChatMessage[],
    walkEcho?: { drafts: EventDraft[]; cursor: number } | null,
  ) => {
    setMessages(history);
    setBusy(true);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    let answer = "";
    let started = false;

    try {
      await streamSubmission(history, {
        walk: walkEcho,
        signal: controller.signal,
        handlers: {
          onStatus: (state) =>
            setStatus(state === "extracting" ? t.pro.statusExtracting : state),
          onWalk: (state) => setWalk(state),
          onForm: (extracted, stillMissing) => {
            setDraft(extracted);
            setMissing(stillMissing);
            setStatus(null);
          },
          onDelta: (chunk) => {
            answer += chunk;
            setStatus(null);
            // Decide append-vs-replace *outside* the updater: StrictMode calls
            // updaters twice, and flipping `started` inside one made the second
            // pass replace the user's message instead of appending the answer.
            const isFirstChunk = !started;
            started = true;
            const turn: ChatMessage = { role: "assistant", content: answer };
            setMessages((prev) =>
              isFirstChunk ? [...prev, turn] : [...prev.slice(0, -1), turn],
            );
          },
          onError: (message) => toast.error(message),
        },
      });
    } catch (error) {
      if (controller.signal.aborted) {
        // The promoter pressed stop; whatever streamed so far stands.
      } else if (error instanceof ApiError && error.status === 403) {
        toast.error(t.pro.notPromoter);
      } else {
        toast.error(error instanceof Error ? error.message : t.pro.genericError);
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
      setStreaming(false);
      setStatus(null);
    }
  };

  const stopStreaming = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    // Clear eagerly, as Chat's stop() does — waiting for the rejection to
    // reach finally leaves a stop button pressed against a dead stream.
    setStreaming(false);
    setStatus(null);
  };

  const walkEcho = walk ? { drafts: walk.drafts, cursor: walk.cursor } : null;

  const send = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setInput("");
    void runTurn([...messages, { role: "user", content: trimmed }], walkEcho);
  };

  /**
   * Attachments do not have their own extraction path: the server turns the
   * file into text, the text joins the conversation, and the ordinary turn
   * merges it with everything already said.
   */
  const attach = async (file: File) => {
    setBusy(true);
    setStatus(t.pro.readingFile(file.name));
    try {
      const { text, source, kind } = await ingestFile(file);
      await runTurn(
        [...messages, { role: "user", content: `[${kind} · ${source}]\n${text}` }],
        walkEcho,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.pro.couldNotRead);
      setBusy(false);
      setStatus(null);
    }
  };

  const publish = async (completed: EventDraft, venueUid: string | null) => {
    setSaving(true);
    try {
      const result = await saveEvent(completed, venueUid);
      toast.success(t.pro.published(result.event_name ?? completed.name ?? "✓"));
      for (const warning of result.warnings ?? []) toast.warning(warning);
      setDraft(null);
      setMissing([]);

      if (walk && walk.cursor + 1 < walk.total) {
        // Mid-walk: keep the promoter's final edits in the echoed set, tell
        // the server we advanced, and let it introduce the next event. The
        // cursor is client-owned, so advance it here and now — advancing only
        // when the server echoes walk.state let a stopped turn strand the
        // cursor on the event just published.
        const drafts = walk.drafts.map((d, i) => (i === walk.cursor ? completed : d));
        const advanced = { ...walk, drafts, cursor: walk.cursor + 1 };
        setWalk(advanced);
        const name = result.event_name ?? completed.name ?? "the event";
        const marker = t.pro.publishedMarker(name, advanced.cursor, walk.total);
        await runTurn([...messages, { role: "user", content: marker }], {
          drafts,
          cursor: advanced.cursor,
        });
      } else {
        // End of the walk: reset the draft state but leave a completion
        // message behind. It names no event details, so a fresh listing
        // typed after it extracts cleanly.
        const total = walk?.total ?? 1;
        setWalk(null);
        setMessages([{ role: "assistant", content: t.pro.walkComplete(total) }]);
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        toast.error(t.pro.alreadyExists);
      } else {
        toast.error(error instanceof Error ? error.message : t.pro.publishFailed);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="relative flex h-[100dvh] flex-col overflow-hidden bg-pro-bg">
      {/* First child, so it paints under everything positioned after it. The
          root is the clip, not the scroll region, so the ground stays still
          while the conversation moves over it. */}
      <ProWatermark />
      <header className="relative flex-shrink-0 border-b border-pro-border px-4 pb-2 pt-3 sm:px-6">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3">
          {/* Not a link. The way back to the consumer chat is in the account
              menu, where the way to every other surface already is — a logo
              that navigates somewhere else is a door nobody means to open. */}
          <span className="flex items-center gap-2.5">
            <Mark size={27} />
            <ProBadge />
          </span>
          <UserMenu />
        </div>
      </header>

      {/* The conversation is flat on the page — no chat panel, no bubbles for
          what laiive says. Only the promoter's own lines are pills. */}
      <div className="relative min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {/* Above the conversation and scrolling with it, after the role
              refusal, so only an actual promoter ever sees it. */}
          <ProOnboarding />

          {messages.map((message, index) =>
            message.role === "user" ? (
              <p
                key={index}
                className="max-w-[84%] self-end whitespace-pre-wrap rounded-[22px] bg-muted px-5 py-3 text-[14.5px] leading-[1.5] text-white"
              >
                {message.content}
              </p>
            ) : (
              <Markdown
                key={index}
                text={message.content}
                className="max-w-[84%] whitespace-pre-wrap text-[15px] leading-[1.5] text-pro-fg"
              />
            ),
          )}

          {status && (
            <span className="self-start rounded-full border border-pro-accent/40 bg-pro-accent/10 px-3 py-[7px] font-mono text-[9.5px] uppercase leading-none tracking-[0.06em] text-pro-accent">
              {status}
            </span>
          )}

          {draft && (
            <div className="flex flex-col gap-2">
              {walk && (
                <span className="self-start rounded-full border border-pro-accent/40 bg-pro-accent/10 px-3 py-[7px] font-mono text-[9.5px] uppercase leading-none tracking-[0.06em] text-pro-accent">
                  {t.pro.eventOf(walk.cursor + 1, walk.total)}
                </span>
              )}
              <EventForm draft={draft} missing={missing} onSave={publish} saving={saving} />
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Cyan accents per brand-rules.md: outlined mic, filled send. Only the
          attach control stays warm-neutral, so the accent means "speak or send". */}
      <div className="flex-shrink-0 border-t border-pro-border px-4 pb-[max(env(safe-area-inset-bottom),16px)] pt-4 sm:px-6">
        <Composer
          value={input}
          onChange={setInput}
          onSend={() => send(input)}
          onStop={stopStreaming}
          isStreaming={streaming}
          disabled={busy || saving}
          accent="pro"
          placeholder={t.pro.placeholder}
          transcribe={async (recording) => {
            const file = new File([recording], "recording.webm", { type: "audio/webm" });
            const { text } = await ingestFile(file);
            return text;
          }}
          onTranscript={(text) => setInput((current) => (current ? `${current} ${text}` : text))}
          attachSlot={
            <>
              <input
                ref={fileInput}
                type="file"
                accept={ACCEPTED}
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (file) void attach(file);
                }}
              />
              <Button
                variant="neutral"
                size="icon"
                onClick={() => fileInput.current?.click()}
                disabled={busy}
                aria-label={t.pro.attach}
                title={t.pro.attach}
              >
                <Icon name="attach" />
              </Button>
            </>
          }
        />
      </div>
    </div>
  );
}
