import type { EventDraft, WalkState } from "@shared/protocol";
import { Loader2, Paperclip, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import type { ChatMessage } from "@/api/chat";
import { ApiError } from "@/api/client";
import { ingestFile } from "@/api/ingest";
import { saveEvent, streamSubmission } from "@/api/push";
import { EventForm } from "@/components/EventForm";
import { Markdown } from "@/components/Markdown";
import { MicButton } from "@/components/MicButton";
import { UserMenu } from "@/components/UserMenu";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/auth/AuthProvider";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

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
  const [saving, setSaving] = useState(false);
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
      <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-3 bg-pro-bg p-6 text-center">
        <p className="font-montserrat text-lg font-bold text-accent">laiive pro</p>
        <p className="max-w-sm font-ibm-plex text-sm text-muted-foreground">
          {t.pro.needsPro}
        </p>
        <Link to="/auth" className="text-sm text-accent hover:underline">
          {user ? t.pro.contactUs : t.pro.signInLink}
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

    let answer = "";
    let started = false;

    try {
      await streamSubmission(history, {
        walk: walkEcho,
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
      if (error instanceof ApiError && error.status === 403) {
        toast.error(t.pro.notPromoter);
      } else {
        toast.error(error instanceof Error ? error.message : t.pro.genericError);
      }
    } finally {
      setBusy(false);
      setStatus(null);
    }
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

  const publish = async (completed: EventDraft) => {
    setSaving(true);
    try {
      const result = await saveEvent(completed);
      toast.success(t.pro.published(result.event_name ?? completed.name ?? "✓"));
      for (const warning of result.warnings ?? []) toast.warning(warning);
      setDraft(null);
      setMissing([]);

      if (walk && walk.cursor + 1 < walk.total) {
        // Mid-walk: keep the promoter's final edits in the echoed set, tell
        // the server we advanced, and let it introduce the next event.
        const drafts = walk.drafts.map((d, i) => (i === walk.cursor ? completed : d));
        const name = result.event_name ?? completed.name ?? "the event";
        const marker = t.pro.publishedMarker(name, walk.cursor + 1, walk.total);
        await runTurn([...messages, { role: "user", content: marker }], {
          drafts,
          cursor: walk.cursor + 1,
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
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-pro-bg">
      <header className="border-b border-pro-border bg-pro-elevated p-3 sm:p-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3">
          <div className="flex items-end gap-1">
            <span className="pb-0.5 text-xl sm:text-2xl">🫦</span>
            <Link to="/" className="font-montserrat text-lg font-bold text-accent sm:text-xl">
              laiive
            </Link>
            <span className="mb-1 ml-0.5 rounded bg-accent/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent">
              pro
            </span>
          </div>
          <UserMenu />
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-4 md:p-6">
        <div className="mx-auto max-w-3xl space-y-3">
          {messages.length === 0 && !draft && (
            <div className="space-y-2 pt-8 text-center font-ibm-plex text-muted-foreground">
              <p>{t.pro.emptyTitle}</p>
              <p className="text-xs">{t.pro.emptyHint}</p>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={index}
              className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}
            >
              <div
                className={cn(
                  "max-w-[92%] whitespace-pre-wrap rounded-2xl border px-4 py-3 font-ibm-plex text-base sm:max-w-[85%]",
                  message.role === "user"
                    ? "border-pro-border bg-pro-card text-foreground"
                    : "border-pro-border bg-pro-elevated text-card-foreground",
                )}
              >
                <Markdown text={message.content} />
              </div>
            </div>
          ))}

          {status && (
            <div className="flex items-center gap-2 rounded-2xl border border-pro-border bg-pro-elevated px-4 py-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin text-accent" />
              {status}
            </div>
          )}

          {draft && (
            <div className="space-y-1">
              {walk && (
                <p className="font-ibm-plex text-xs font-bold uppercase tracking-wider text-accent">
                  {t.pro.eventOf(walk.cursor + 1, walk.total)}
                </p>
              )}
              <EventForm draft={draft} missing={missing} onSave={publish} saving={saving} />
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="flex-shrink-0 border-t border-pro-border bg-pro-elevated p-3 pb-[env(safe-area-inset-bottom,12px)] sm:p-4">
        <div className="mx-auto flex max-w-3xl items-center gap-2 sm:gap-3">
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
            variant="ghost"
            size="icon"
            onClick={() => fileInput.current?.click()}
            disabled={busy}
            aria-label={t.pro.attach}
            title={t.pro.attach}
          >
            <Paperclip className="h-5 w-5" />
          </Button>

          <MicButton
            transcribe={async (recording) => {
              const file = new File([recording], "recording.webm", { type: "audio/webm" });
              const { text } = await ingestFile(file);
              return text;
            }}
            onTranscript={(text) => setInput((current) => (current ? `${current} ${text}` : text))}
            disabled={busy}
          />

          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && send(input)}
            placeholder={t.pro.placeholder}
            className="focus-visible:ring-accent"
          />

          <Button
            variant="accent"
            size="icon"
            onClick={() => send(input)}
            disabled={busy || !input.trim()}
            aria-label={t.pro.send}
          >
            {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
