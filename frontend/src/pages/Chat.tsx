import type { EventCard } from "@shared/protocol";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import { sendFeedback, streamChat, type ChatMessage, type UserLocation } from "@/api/chat";
import { transcribe as transcribeRecording } from "@/api/ingest";
import { useSavedUids, useToggleSaved } from "@/api/savedEvents";
import { Composer } from "@/components/Composer";
import { Button } from "@/components/ui/Button";
import { EventCardView } from "@/components/EventCardView";
import { Icon } from "@/components/Icon";
import { Mark } from "@/components/Mark";
import { Markdown } from "@/components/Markdown";
import { UserMenu } from "@/components/UserMenu";
import { useAuth } from "@/auth/AuthProvider";
import { claimTarget } from "@/auth/claimTarget";
import { detectLanguageFromText } from "@/i18n/detectLanguage";
import { useTranslation, type Language } from "@/i18n/useTranslation";

export default function Chat() {
  const { t, language, setLanguage } = useTranslation();

  // Pipeline states the retriever emits, worded for humans.
  const statusLabel: Record<string, string> = {
    classifying: t.chat.statusReading,
    searching: t.chat.statusSearching,
    composing: t.chat.statusWriting,
  };
  const { user, role } = useAuth();

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [location, setLocation] = useState<UserLocation | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // One query for every card on the page rather than one per card, which
  // is why EventCardView takes the state as a prop instead of reading it.
  const { data: savedUids } = useSavedUids(user?.id);
  const savedSet = useMemo(() => new Set(savedUids ?? []), [savedUids]);
  const toggleSaved = useToggleSaved(user?.id);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

  // Location is optional: "near me" queries need it, everything else does not,
  // so a denied permission is not worth a toast.
  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => setLocation({ latitude: coords.latitude, longitude: coords.longitude }),
      () => undefined,
      { timeout: 8000 },
    );
  }, []);

  const stop = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setStatus(null);
  };

  /**
   * `preset` is how the example chips ask: they cannot fill the composer
   * and then call this, because the state they wrote is not readable until
   * the next render.
   */
  const send = async (preset?: string) => {
    const text = (preset ?? input).trim();
    if (!text || isStreaming) return;

    const detected = detectLanguageFromText(text);
    if (detected && detected !== language) setLanguage(detected as Language);

    const history: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(history);
    setInput("");
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    // The assistant turn is appended once and then mutated in place as frames
    // arrive — cards land before the first token, per the protocol's ordering.
    let answer = "";
    let cards: EventCard[] = [];
    let started = false;

    const upsert = () => {
      const turn: ChatMessage = { role: "assistant", content: answer, events: cards };
      setMessages((prev) => {
        if (!started) return prev;
        const last = prev[prev.length - 1];
        return last?.role === "assistant"
          ? [...prev.slice(0, -1), turn]
          : [...prev, turn];
      });
    };

    try {
      const requestId = await streamChat(history, {
        location,
        signal: controller.signal,
        handlers: {
          onStatus: (state) => setStatus(statusLabel[state] ?? state),
          onEvents: (events) => {
            cards = events;
            started = true;
            setMessages((prev) => [...prev, { role: "assistant", content: "", events }]);
            setStatus(null);
          },
          onDelta: (chunk) => {
            answer += chunk;
            if (!started) {
              started = true;
              setMessages((prev) => [...prev, { role: "assistant", content: answer, events: [] }]);
              setStatus(null);
              return;
            }
            upsert();
          },
          onError: (message) => toast.error(message),
        },
      });
      // Stamped after the stream ends: the id's presence is also what tells
      // the UI this turn is finished and can take feedback.
      if (requestId) {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          return last?.role === "assistant"
            ? [...prev.slice(0, -1), { ...last, requestId }]
            : prev;
        });
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      handleFailure(error);
    } finally {
      abortRef.current = null;
      setIsStreaming(false);
      setStatus(null);
    }
  };

  const handleFailure = (error: unknown) => {
    if (error instanceof ApiError && error.status === 429) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: user ? t.chat.rateLimited : t.chat.rateLimitedAnon,
        },
      ]);
      return;
    }
    if (error instanceof ApiError && error.status === 401) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: t.chat.sessionExpired },
      ]);
      return;
    }
    toast.error(error instanceof Error ? error.message : t.chat.genericError);
  };

  const isEmpty = messages.length === 0 && !status;

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-background">
      {/* The whole chrome inventory: mark + wordmark, saved, account. */}
      <header className="flex-shrink-0 border-b border-rule px-4 pb-2 pt-3 sm:px-5">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <Mark size={27} />
          <div className="flex items-center">
            {/* Visible signed out too: the route sends you to /auth and
                back, and a header control that appears on sign-in makes
                the bar jump. */}
            <Link
              to="/saved"
              aria-label={t.menu.saved}
              className="flex h-11 w-11 items-center justify-center text-ink-dim transition-colors hover:text-foreground"
            >
              <Icon name="saved" />
            </Link>
            <UserMenu />
          </div>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 sm:px-5">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-8">
            <span
              aria-hidden="true"
              className="select-none font-bebas text-[26vw] leading-none tracking-[0.04em] text-foreground/[0.05] sm:text-[9rem]"
            >
              laiive
            </span>
            {/* Three real queries, sent verbatim. An empty chat gives no
                clue what it will understand, and a promoter's event is
                only found if somebody asks in a shape that reaches it. */}
            <div className="flex max-w-md flex-wrap justify-center gap-2">
              {t.chat.examples.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => void send(example)}
                  className="min-h-11 rounded-full bg-field-border px-3.5 text-sm leading-tight text-white transition-colors hover:bg-muted"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-3.5 py-4">
            {messages.map((message, index) =>
              message.role === "user" ? (
                <p
                  key={index}
                  className="max-w-[74%] self-end whitespace-pre-wrap rounded-[22px] bg-muted px-4 py-2.5 text-base leading-[1.4] text-white"
                >
                  {message.content}
                </p>
              ) : (
                <div key={index} className="flex flex-col gap-2.5">
                  {/* Answer first, cards second — the reason follows the answer. */}
                  {message.content && (
                    <Markdown
                      text={message.content}
                      className="whitespace-pre-wrap text-lg leading-[1.5] text-foreground"
                    />
                  )}
                  {message.events && message.events.length > 0 && (
                    <div className="flex flex-col gap-2 border-l-2 border-secondary/50 pl-[11px]">
                      {message.events.map((card) => (
                        <EventCardView
                          key={card.uid}
                          card={card}
                          language={language}
                          saved={savedSet.has(card.uid)}
                          claimTo={claimTarget(Boolean(user), role)}
                          // No control at all when signed out, rather than a pill
                          // that breaks its promise once per card.
                          onToggleSave={
                            user ? (uid, next) => toggleSaved.mutate({ uid, next }) : undefined
                          }
                        />
                      ))}
                    </div>
                  )}
                  {message.requestId && <TurnFeedback requestId={message.requestId} />}
                </div>
              ),
            )}

            {status && (
              <p className="animate-pulse font-mono text-xs uppercase tracking-[0.11em] text-ink-dim">
                {status}
              </p>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="flex-shrink-0 border-t border-rule px-4 pb-[max(env(safe-area-inset-bottom),14px)] pt-3 sm:px-5">
        <Composer
          value={input}
          onChange={setInput}
          onSend={() => void send()}
          onStop={stop}
          isStreaming={isStreaming}
          accent="consumer"
          placeholder={t.chat.placeholder}
          transcribe={transcribeRecording}
          onTranscript={(text) =>
            setInput((current) => (current ? `${current} ${text}` : text))
          }
        />
      </div>
    </div>
  );
}

/**
 * Thumbs on an assistant turn (eval phase 1). The down is the informative
 * event: it posts immediately so an abandoned reason box still counts, and a
 * typed reason goes out as a second post for the same request_id. The up
 * posts once and stops — a stored positive label; only downs feed error
 * analysis.
 */
export function TurnFeedback({ requestId }: { requestId: string }) {
  const { t } = useTranslation();
  const [stage, setStage] = useState<"idle" | "asking" | "done">("idle");
  const [reason, setReason] = useState("");

  const down = () => {
    setStage("asking");
    sendFeedback(requestId, "down").catch(() => {
      setStage("idle");
      toast.error(t.chat.genericError);
    });
  };

  const up = () => {
    setStage("done");
    sendFeedback(requestId, "up").catch(() => {
      setStage("idle");
      toast.error(t.chat.genericError);
    });
  };

  const submit = () => {
    const text = reason.trim();
    setStage("done");
    if (text) sendFeedback(requestId, "down", text).catch(() => undefined);
  };

  if (stage === "done") {
    return (
      <p
        role="status"
        className="font-mono text-xs uppercase tracking-[0.11em] text-ink-dim"
      >
        {t.chat.feedbackThanks}
      </p>
    );
  }

  if (stage === "asking") {
    return (
      <input
        autoFocus
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") submit();
        }}
        placeholder={t.chat.feedbackReasonPlaceholder}
        maxLength={2000}
        className="h-11 w-full max-w-sm rounded-full border border-rule bg-transparent px-3.5 text-base text-foreground placeholder:text-ink-dim focus:outline-none"
      />
    );
  }

  return (
    <div className="-ml-3.5 flex items-center self-start">
      <ThumbButton label={t.chat.feedbackUp} onClick={up}>
        <path d="M7 10v12" />
        <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
      </ThumbButton>
      <ThumbButton label={t.chat.feedbackDown} onClick={down}>
        <path d="M17 14V2" />
        <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
      </ThumbButton>
    </div>
  );
}

/** One 44px ghost pill per thumb; only the label, handler and paths differ. */
function ThumbButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button variant="ghost" size="icon" onClick={onClick} aria-label={label} title={label}>
      <svg
        className="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        {children}
      </svg>
    </Button>
  );
}
