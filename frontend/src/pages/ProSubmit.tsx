import type { EventDraft } from "@shared/protocol";
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
import { cn } from "@/lib/cn";

const STATUS_LABEL: Record<string, string> = {
  extracting: "reading what you sent…",
};

const ACCEPTED =
  "image/*,audio/*,.pdf,.docx,.txt,.md,.csv";

export default function ProSubmit() {
  const { user, role, isLoading } = useAuth();

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState<EventDraft | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, draft, status]);

  if (isLoading) return null;
  if (!user || (role !== "pro" && role !== "admin")) {
    return (
      <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-3 bg-pro-bg p-6 text-center">
        <p className="font-montserrat text-lg font-bold text-accent">laiive pro</p>
        <p className="max-w-sm font-ibm-plex text-sm text-muted-foreground">
          Publishing events needs a promoter account.
        </p>
        <Link to="/auth" className="text-sm text-accent hover:underline">
          {user ? "signed in without pro access — contact us" : "sign in →"}
        </Link>
      </div>
    );
  }

  /** Send the conversation up; the server re-extracts over all of it. */
  const runTurn = async (history: ChatMessage[]) => {
    setMessages(history);
    setBusy(true);

    let answer = "";
    let started = false;

    try {
      await streamSubmission(history, {
        handlers: {
          onStatus: (state) => setStatus(STATUS_LABEL[state] ?? state),
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
        toast.error("Your account is not a promoter account yet.");
      } else {
        toast.error(error instanceof Error ? error.message : "Something went wrong");
      }
    } finally {
      setBusy(false);
      setStatus(null);
    }
  };

  const send = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setInput("");
    void runTurn([...messages, { role: "user", content: trimmed }]);
  };

  /**
   * Attachments do not have their own extraction path: the server turns the
   * file into text, the text joins the conversation, and the ordinary turn
   * merges it with everything already said.
   */
  const attach = async (file: File) => {
    setBusy(true);
    setStatus(`reading ${file.name}…`);
    try {
      const { text, source, kind } = await ingestFile(file);
      await runTurn([
        ...messages,
        { role: "user", content: `[${kind} · ${source}]\n${text}` },
      ]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not read that file");
      setBusy(false);
      setStatus(null);
    }
  };

  const publish = async (completed: EventDraft) => {
    setSaving(true);
    try {
      const result = await saveEvent(completed);
      toast.success(`Published — ${result.event_name ?? "event"} is live`);
      for (const warning of result.warnings ?? []) toast.warning(warning);
      setDraft(null);
      setMissing([]);
      setMessages([]);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        toast.error("That event is already on laiive.");
      } else {
        toast.error(error instanceof Error ? error.message : "Could not publish");
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
              <p>Tell me about your event — type it, say it, or drop a flyer.</p>
              <p className="text-xs">
                photo · PDF · Word · voice — all of it becomes the same form
              </p>
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
            <EventForm draft={draft} missing={missing} onSave={publish} saving={saving} />
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
            aria-label="Attach a flyer, document or recording"
            title="Attach a flyer, document or recording"
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
            placeholder="artist, venue, date, price…"
            className="focus-visible:ring-accent"
          />

          <Button
            variant="accent"
            size="icon"
            onClick={() => send(input)}
            disabled={busy || !input.trim()}
            aria-label="Send"
          >
            {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
