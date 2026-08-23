import type { EventCard } from "@shared/protocol";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import { streamChat, type ChatMessage, type UserLocation } from "@/api/chat";
import { transcribe as transcribeRecording } from "@/api/ingest";
import { EventCardView } from "@/components/EventCardView";
import { Icon } from "@/components/Icon";
import { Mark } from "@/components/Mark";
import { Markdown } from "@/components/Markdown";
import { MicButton } from "@/components/MicButton";
import { UserMenu } from "@/components/UserMenu";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/auth/AuthProvider";
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
  const { user } = useAuth();

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [location, setLocation] = useState<UserLocation | null>(null);
  const abortRef = useRef<AbortController | null>(null);
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
      await streamChat(history, {
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
            {/* Artwork and a place in the bar; the feature is not built, so the
                icon ships inert rather than promising something. */}
            <span
              aria-label={t.menu.saved}
              className="flex h-11 w-11 items-center justify-center text-ink-dim/60"
            >
              <Icon name="saved" />
            </span>
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
                  className="rounded-full bg-field-border px-3.5 py-2.5 text-[12.5px] leading-none text-white transition-colors hover:bg-muted"
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
                  className="max-w-[74%] self-end whitespace-pre-wrap rounded-[22px] bg-muted px-4 py-2.5 text-[14.5px] leading-[1.4] text-white"
                >
                  {message.content}
                </p>
              ) : (
                <div key={index} className="flex flex-col gap-2.5">
                  {/* Answer first, cards second — the reason follows the answer. */}
                  {message.content && (
                    <Markdown
                      text={message.content}
                      className="whitespace-pre-wrap text-[15px] leading-[1.5] text-foreground"
                    />
                  )}
                  {message.events && message.events.length > 0 && (
                    <div className="flex flex-col gap-2 border-l-2 border-secondary/50 pl-[11px]">
                      {message.events.map((card) => (
                        <EventCardView key={card.uid} card={card} language={language} />
                      ))}
                    </div>
                  )}
                </div>
              ),
            )}

            {status && (
              <p className="animate-pulse font-mono text-[11px] uppercase tracking-[0.11em] text-ink-dim">
                {status}
              </p>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="flex-shrink-0 border-t border-rule px-4 pb-[max(env(safe-area-inset-bottom),14px)] pt-3 sm:px-5">
        <div className="mx-auto flex max-w-3xl items-center gap-2.5">
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && void send()}
            placeholder={t.chat.placeholder}
            aria-label={t.chat.placeholder}
          />
          {/* One amber control: stop while streaming, send once there is
              something to send, and the mic the rest of the time. */}
          {isStreaming ? (
            <Button variant="amber" size="icon" onClick={stop} aria-label={t.chat.stop}>
              <Icon name="close" />
            </Button>
          ) : input.trim() ? (
            <Button
              variant="amber"
              size="icon"
              onClick={() => void send()}
              aria-label={t.chat.send}
            >
              <Icon name="send" className="h-[18px] w-[18px]" />
            </Button>
          ) : (
            <MicButton
              transcribe={transcribeRecording}
              onTranscript={(text) =>
                setInput((current) => (current ? `${current} ${text}` : text))
              }
            />
          )}
        </div>
      </div>
    </div>
  );
}
