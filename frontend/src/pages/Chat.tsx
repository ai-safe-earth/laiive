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
import { LiveAccent } from "@/components/LiveAccent";
import { Mark } from "@/components/Mark";
import { Markdown } from "@/components/Markdown";
import { UserMenu } from "@/components/UserMenu";
import { useAuth } from "@/auth/AuthProvider";
import { claimTarget } from "@/auth/claimTarget";
import { useTranslation } from "@/i18n/useTranslation";

export default function Chat() {
  const { t, language } = useTranslation();

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
  const send = async (preset?: string, here?: UserLocation) => {
    const text = (preset ?? input).trim();
    if (!text || isStreaming) return;

    // No guessing the language from the words typed: the picker on /account is
    // persisted and is the one answer. A word-list guesser overrode a reader's
    // own choice on the overlap between four Romance languages.
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
    let capped = false;
    let needsLocation = false;
    let started = false;

    const upsert = () => {
      const turn: ChatMessage = { role: "assistant", content: answer, events: cards, capped, needsLocation };
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
        location: here ?? location,
        signal: controller.signal,
        handlers: {
          onStatus: (state) => {
            if (state === "needs_location") needsLocation = true;
            else setStatus(statusLabel[state] ?? state);
          },
          onEvents: (events, more) => {
            cards = events;
            capped = more;
            started = true;
            setMessages((prev) => [...prev, { role: "assistant", content: "", events, capped, needsLocation }]);
            setStatus(null);
          },
          onDelta: (chunk) => {
            answer += chunk;
            if (!started) {
              started = true;
              setMessages((prev) => [...prev, { role: "assistant", content: answer, events: [], needsLocation }]);
              setStatus(null);
              return;
            }
            upsert();
          },
          onError: (message, code) => {
            // An outage is said in the chat, in the reader's language: a toast
            // vanishes, and the server's English message is not theirs.
            if (code === "graph_unavailable") {
              setMessages((prev) => [
                ...prev,
                { role: "assistant", content: t.chat.graphUnavailable },
              ]);
              return;
            }
            toast.error(message);
          },
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
      <header className="flex-shrink-0 border-b border-rule bg-chrome px-4 pb-2 pt-3 sm:px-5">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <Mark size={30} live />
          <div className="flex items-center">
            {/* Visible signed out too: the route sends you to /auth and
                back, and a header control that appears on sign-in makes
                the bar jump. */}
            <Link
              to="/saved"
              aria-label={t.menu.saved}
              className="flex h-11 w-11 items-center justify-center"
            >
              <LiveAccent variant="mask" mask="saved" aria-hidden="true" className="h-5 w-5" />
            </Link>
            <UserMenu />
          </div>
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1 flex-col">
        {isEmpty && (
          /* The grey wordmark behind the empty chat.
             Its geometry was measured off the last frame of the opening film
             (since removed), in a 1080x1080 viewBox with a `meet` fit: ink from x 192 to 876, baseline at
             y 441, cap height 232, stable between luminance thresholds 40 and
             60 so that is the letters and not their glow.

             Bebas sits its caps at 0.70em, so 232/0.70 gives the 330. The 16.4
             of tracking is 0.0497em, a hair over the 0.04em brand-rules.md
             gives the lockup: the cut was set fractionally wider, and 685 of
             ink is the target here, not the rule. `x` is 182 rather than 192
             because L carries a 10px left side bearing at this size, and it is
             the ink that has to line up, not the origin. */
          <svg
            aria-hidden="true"
            viewBox="0 0 1080 1080"
            preserveAspectRatio="xMidYMid meet"
            className="pointer-events-none absolute inset-0 h-full w-full select-none text-foreground/[0.05]"
          >
            <text
              x="182"
              y="441"
              fill="currentColor"
              className="font-bebas"
              fontSize="330"
              letterSpacing="16.4"
            >
              LAIIVE
            </text>
          </svg>
        )}

      <div className="relative z-0 min-h-0 flex-1 overflow-y-auto px-4 sm:px-5">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-8">
            {/* Three real queries, sent verbatim. An empty chat gives no
                clue what it will understand, and a promoter's event is
                only found if somebody asks in a shape that reaches it. */}
            <div className="flex max-w-md flex-wrap justify-center gap-2">
              {t.chat.examples.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => void send(example)}
                  className="min-h-11 rounded-full bg-field-border px-3.5 text-md leading-tight text-white transition-colors hover:bg-muted"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-4 py-4">
            {messages.map((message, index) =>
              message.role === "user" ? (
                <p
                  key={index}
                  className="max-w-[85%] self-end whitespace-pre-wrap rounded-[22px] bg-muted px-4 py-2.5 text-lg leading-[1.45] text-white"
                >
                  {message.content}
                </p>
              ) : (
                <div key={index} className="flex flex-col gap-2.5">
                  {/* Answer first, cards second — the reason follows the answer. */}
                  {message.content && (
                    <Markdown
                      text={message.content}
                      className="whitespace-pre-wrap text-xl leading-[1.55] text-foreground"
                    />
                  )}
                  {message.events && message.events.length > 0 && (
                    <ResultCards
                      events={message.events}
                      capped={Boolean(message.capped)}
                      render={(card) => (
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
                      )}
                    />
                  )}
                  {message.needsLocation &&
                    message.requestId &&
                    !location &&
                    index === messages.length - 1 && (
                      <ShareLocation
                        onShared={(here) => {
                          setLocation(here);
                          void send(messages[index - 1]?.content, here);
                        }}
                      />
                    )}
                  {message.requestId && <TurnFeedback requestId={message.requestId} />}
                </div>
              ),
            )}

            {status && (
              <p className="animate-pulse font-mono text-sm uppercase tracking-[0.11em] text-ink-dim">
                {status}
              </p>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      </div>

      <div className="relative z-20 flex-shrink-0 border-t border-rule bg-chrome px-4 pb-[max(env(safe-area-inset-bottom),14px)] pt-3 sm:px-5">
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

/** Cards shown a page at a time; the retriever sends up to 50 at once. */
const RESULTS_PAGE = 10;

/**
 * An answer's cards, ten first and the rest behind "show more". A list past two
 * pages is too long to browse, so it says how many there are and suggests
 * narrowing the search instead (owner, 2026-10-09).
 */
export function ResultCards({
  events,
  capped,
  render,
}: {
  events: EventCard[];
  capped: boolean;
  render: (card: EventCard) => ReactNode;
}) {
  const { t } = useTranslation();
  const [shown, setShown] = useState(RESULTS_PAGE);
  const left = events.length - shown;
  const total = capped ? `${events.length}+` : String(events.length);
  return (
    <div className="flex flex-col gap-2 border-l-2 border-secondary/50 pl-[11px]">
      {events.slice(0, shown).map(render)}
      {events.length > 2 * RESULTS_PAGE && (
        <p className="text-sm text-ink-dim">{t.chat.manyResults(total)}</p>
      )}
      {left > 0 && (
        <button
          type="button"
          onClick={() => setShown((n) => n + RESULTS_PAGE)}
          className="self-start rounded-full border border-secondary/50 px-4 py-1.5 text-sm text-foreground hover:bg-muted"
        >
          {t.chat.showMore(Math.min(left, RESULTS_PAGE), total)}
        </button>
      )}
    </div>
  );
}

/**
 * Offered under a reply that needed the asker's position and had none: one tap
 * asks the browser, and the same question goes again with the location. The
 * silent ask on page load is easy to miss or dismiss (owner, 2026-10-09).
 */
export function ShareLocation({ onShared }: { onShared: (here: UserLocation) => void }) {
  const { t } = useTranslation();
  const [denied, setDenied] = useState(false);
  if (!navigator.geolocation) return null;
  if (denied) return <p className="text-sm text-ink-dim">{t.chat.locationDenied}</p>;
  const ask = () =>
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => onShared({ latitude: coords.latitude, longitude: coords.longitude }),
      () => setDenied(true),
      { timeout: 8000 },
    );
  return (
    <button
      type="button"
      onClick={ask}
      className="self-start rounded-full border border-secondary/50 px-4 py-1.5 text-sm text-foreground hover:bg-muted"
    >
      {t.chat.shareLocation}
    </button>
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
        className="font-mono text-sm uppercase tracking-[0.11em] text-ink-dim"
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
