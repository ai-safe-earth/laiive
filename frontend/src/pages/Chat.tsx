import type { EventCard } from "@shared/protocol";
import { Loader2, Send, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import { streamChat, type ChatMessage, type UserLocation } from "@/api/chat";
import { EventCardView } from "@/components/EventCardView";
import { Markdown } from "@/components/Markdown";
import { UserMenu } from "@/components/UserMenu";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/auth/AuthProvider";
import { detectLanguageFromText } from "@/i18n/detectLanguage";
import { useTranslation, type Language } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

/** Pipeline states the retriever emits, worded for humans. */
const STATUS_LABEL: Record<string, string> = {
  classifying: "reading your question…",
  searching: "searching the graph…",
  composing: "writing…",
};

export default function Chat() {
  const { t, language, setLanguage } = useTranslation();
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

  const send = async () => {
    const text = input.trim();
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
          onStatus: (state) => setStatus(STATUS_LABEL[state] ?? state),
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
          content: user
            ? "You are sending requests a little fast — give it a minute."
            : "That's the free quota for now. [Sign in →](/auth) for a higher limit.",
        },
      ]);
      return;
    }
    if (error instanceof ApiError && error.status === 401) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Your session expired. [Sign in again →](/auth)" },
      ]);
      return;
    }
    toast.error(error instanceof Error ? error.message : "Something went wrong.");
  };

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-background">
      <header className="border-b border-border bg-card p-3 sm:p-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3">
          <div className="flex items-end gap-4">
            <div className="flex items-end gap-1">
              <span className="pb-0.5 text-xl sm:text-2xl">🫦</span>
              <span className="font-montserrat text-lg font-bold text-primary sm:text-xl">
                laiive
              </span>
            </div>
            <Link
              to="/pro"
              className="pb-0.5 font-ibm-plex text-[10px] text-muted-foreground transition-colors hover:text-accent"
            >
              {t.chat.promoterLink}
            </Link>
          </div>
          <UserMenu />
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-4 md:p-6">
        <div className="mx-auto max-w-4xl space-y-3 sm:space-y-4">
          {messages.length === 0 && (
            <p className="pt-12 text-center font-ibm-plex text-muted-foreground">
              {t.chat.welcome}
            </p>
          )}

          {messages.map((message, index) => (
            <div
              key={index}
              className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}
            >
              <div
                className={cn(
                  "max-w-[92%] font-ibm-plex text-base sm:max-w-[85%]",
                  message.role === "user"
                    ? "rounded-2xl border border-border bg-muted px-4 py-3 text-foreground"
                    : message.events && message.events.length > 0
                      ? "w-full space-y-3 bg-transparent"
                      : "rounded-2xl border border-border bg-card px-4 py-3 text-card-foreground",
                )}
              >
                {message.events && message.events.length > 0 && (
                  <div className="space-y-2">
                    {message.events.map((card) => (
                      <EventCardView key={card.uid} card={card} language={language} />
                    ))}
                  </div>
                )}
                {message.content && (
                  <Markdown
                    text={message.content}
                    className={cn(
                      "whitespace-pre-wrap",
                      message.events && message.events.length > 0 && "text-muted-foreground",
                    )}
                  />
                )}
              </div>
            </div>
          ))}

          {status && (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                {status}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="flex-shrink-0 border-t border-border bg-card p-3 pb-[env(safe-area-inset-bottom,12px)] sm:p-4">
        <div className="mx-auto flex max-w-4xl items-center gap-2 sm:gap-3">
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && void send()}
            placeholder={t.chat.placeholder}
            aria-label={t.chat.placeholder}
          />
          {isStreaming ? (
            <Button variant="outline" size="icon" onClick={stop} aria-label="Stop">
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={() => void send()}
              disabled={!input.trim()}
              aria-label="Send"
            >
              <Send className="h-5 w-5" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
