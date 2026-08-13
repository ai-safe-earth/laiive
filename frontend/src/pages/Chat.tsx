import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Mic, Send, Loader2, MicOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "@/hooks/useTranslation";
import { AudioRecorder } from "@/utils/audioRecorder";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useSession } from "@/hooks/useSession";
import DOMPurify from "dompurify";
import { useAuth } from "@/hooks/useAuth";
import { useQueryLimit } from "@/components/QueryCounter";
import { UserAvatar } from "@/components/UserAvatar";
import { EventCard, parseEventContent } from "@/components/EventCard";
import { detectLanguageFromText } from "@/utils/detectLanguage";
import { parseSSEStream } from "@/utils/parseSSE";
import { callFunction, callFunctionJSON } from "@/utils/apiClient";
import { retrieverFetch } from "@/utils/retrieverClient";
import type { ChatMessage, UserLocation } from "@/types/api";

// Pro mode styling constants
const proStyles = {
  bg: "bg-[hsl(var(--pro-bg))]",
  bgElevated: "bg-[hsl(var(--pro-bg-elevated))]",
  bgCard: "bg-[hsl(var(--pro-bg-card))]",
  border: "border-[hsl(var(--pro-border))]",
  accent: "text-accent",
  accentBg: "bg-accent/10",
};

type Message = ChatMessage;

/** Render markdown-lite content (bold + links) via DOMPurify */
function renderMarkdown(text: string): string {
  return DOMPurify.sanitize(
    text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(
        /\[(.*?)\]\((.*?)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline">$1</a>',
      ),
    { ALLOWED_TAGS: ["strong", "a"], ALLOWED_ATTR: ["href", "target", "rel", "class"] },
  );
}

const Chat = () => {
  const navigate = useNavigate();
  const { t, language, setLanguage } = useTranslation();
  const { sessionId, deviceType, userAgent } = useSession();
  const { user, session, isLoading: authLoading } = useAuth();
  const { canQuery, incrementCount, isPromoter } = useQueryLimit();
  const [mode, setMode] = useState<"user" | "promoter">("user");

  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [location, setLocation] = useState<UserLocation | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const audioRecorderRef = useRef<AudioRecorder | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Lazy-init audio recorder and clean up on unmount
  useEffect(() => {
    audioRecorderRef.current = new AudioRecorder();
    return () => {
      audioRecorderRef.current?.stop().catch(() => {});
      audioRecorderRef.current = null;
    };
  }, []);

  const handleModeChange = () => {
    const newMode = mode === "user" ? "promoter" : "user";
    setMode(newMode);
    if (newMode === "promoter") {
      setMessages([
        {
          role: "assistant",
          content:
            "Hello! I can help you add your event to the laiive platform. To start, please provide me with the following information:\n\n*   **Artist name**\n*   **Event description**\n*   **Date and time**\n*   **Venue name**\n*   **City**\n*   **Ticket price**",
        },
      ]);
    } else {
      setMessages([]);
    }
  };

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLocation({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          });
        },
        () => {
          toast({
            title: "Location access denied",
            description: "Using default location. Grant location access for better results.",
            variant: "destructive",
          });
        },
      );
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /** Log a conversation message (fire-and-forget) */
  const logMessage = (role: string, content: string, lang: string) => {
    if (!sessionId) return;
    callFunction("validate-conversation", {
      session_id: sessionId,
      conversation_type: "user",
      message_role: role,
      message_content: content,
      device_type: deviceType,
      user_agent: userAgent,
      language: lang,
    }).catch(() => {});
  };

  const handleSendMessage = async () => {
    if (!message.trim() || isLoading) return;

    // Auth and query limit checks (skipped when not signed in for dev/testing)
    // TODO: re-enable for production
    // if (!user) {
    //   setMessages((prev) => [
    //     ...prev,
    //     { role: "user", content: message },
    //     { role: "assistant", content: "Sign in to start discovering live music events\n\n[Sign in →](/auth)" },
    //   ]);
    //   setMessage("");
    //   return;
    // }

    // if (!canQuery) {
    //   setMessages((prev) => [
    //     ...prev,
    //     { role: "user", content: message },
    //     {
    //       role: "assistant",
    //       content: "You've used all 5 free queries this week. Upgrade to Pro for unlimited access!\n\n[Become a Pro →](/promoters)",
    //     },
    //   ]);
    //   setMessage("");
    //   return;
    // }

    // Detect language
    const detected = detectLanguageFromText(message);
    if (detected && detected !== language) {
      setLanguage(detected as "en" | "es" | "it" | "ca");
    }
    const currentLanguage = detected || language;

    const userMessage: Message = { role: "user", content: message };
    setMessages((prev) => [...prev, userMessage]);
    setMessage("");
    setIsLoading(true);
    incrementCount();

    logMessage("user", userMessage.content, currentLanguage);

    try {
      let response: Response;

      if (mode === "promoter") {
        const accessToken = session?.access_token;
        if (!accessToken) {
          toast({ title: "Session expired", description: "Please sign in again.", variant: "destructive" });
          navigate("/auth");
          return;
        }
        // Promoter mode → pusher service
        response = await callFunction(
          "promoter-create",
          { messages: [...messages, userMessage], language: currentLanguage },
          { accessToken },
        );
      } else {
        // User mode → retriever service directly (no auth needed)
        response = await retrieverFetch("/chat/stream", {
          messages: [...messages, userMessage],
          location,
          language: currentLanguage,
        });
      }

      if (!response.ok) {
        if (response.status === 401) {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: "Your session has expired. Please sign in again.\n\n[Sign in →](/auth)" },
          ]);
          return;
        }
        if (response.status === 429) {
          const errorData = await response.json().catch(() => ({}));
          if (errorData.queries_remaining === 0) {
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content:
                  "You've used all 5 free queries this week. Upgrade to Pro for unlimited access!\n\n[Become a Pro →](/promoters)",
              },
            ]);
          } else {
            toast({ title: "Rate limit exceeded", description: "Please try again later.", variant: "destructive" });
          }
          return;
        }
        if (response.status === 402) {
          toast({ title: "Payment required", description: "Please add funds to continue.", variant: "destructive" });
          return;
        }
        throw new Error("Failed to get response");
      }

      let assistantContent = "";
      for await (const chunk of parseSSEStream(response)) {
        assistantContent += chunk;
        const content = assistantContent;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant") {
            return prev.map((m, i) => (i === prev.length - 1 ? { ...m, content } : m));
          }
          return [...prev, { role: "assistant", content }];
        });
      }

      logMessage("assistant", assistantContent, currentLanguage);
    } catch (error) {
      console.error("Chat error:", error);
      toast({ title: "Error", description: "Failed to send message. Please try again.", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleMicClick = async () => {
    const recorder = audioRecorderRef.current;
    if (!recorder) return;

    if (isRecording) {
      try {
        const audioBase64 = await recorder.stop();
        setIsRecording(false);

        const { text } = await callFunctionJSON<{ text: string }>(
          "transcribe-audio",
          { audio: audioBase64 },
        );
        setMessage(text);
        toast({ title: "Audio transcribed", description: "Please review and send the message." });
      } catch (error) {
        console.error("Error processing audio:", error);
        toast({
          title: "Transcription failed",
          description: "We couldn't understand the audio. Please try speaking again.",
          variant: "destructive",
        });
      }
    } else {
      try {
        await recorder.start();
        setIsRecording(true);
        toast({ title: "Recording...", description: "Speak now. Click again to stop." });
      } catch (error) {
        console.error("Error starting recording:", error);
        toast({
          title: "Microphone access denied",
          description: "Please grant microphone permission to use voice input.",
          variant: "destructive",
        });
      }
    }
  };

  return (
    <div
      className={cn(
        "flex flex-col h-[100dvh] overflow-hidden",
        mode === "promoter" ? proStyles.bg : "bg-background",
      )}
    >
      {/* Header with mode toggle */}
      <header
        className={cn(
          "border-b p-3 sm:p-4",
          mode === "promoter"
            ? `${proStyles.bgElevated} ${proStyles.border}`
            : "bg-card border-border",
        )}
      >
        <div className="max-w-4xl mx-auto flex items-center justify-between gap-3 sm:gap-4">
          <div className="flex items-end gap-4">
            <div className="flex items-end gap-1">
              <span className="text-xl sm:text-2xl pb-0.5">🫦</span>
              <span
                className={cn(
                  "font-montserrat font-bold text-lg sm:text-xl",
                  mode === "promoter" ? "text-accent" : "text-primary",
                )}
              >
                laiive
              </span>
              {mode === "promoter" && (
                <span className="ml-0.5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-accent/20 text-accent rounded mb-1">
                  Pro
                </span>
              )}
            </div>
            <button
              onClick={() => navigate("/promoters")}
              className={cn(
                "font-ibm-plex text-[10px] transition-colors pb-0.5",
                "text-muted-foreground hover:text-accent",
              )}
            >
              laiive.pro
            </button>
          </div>
          <UserAvatar />
        </div>
      </header>

      {/* Chat messages */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4 md:p-6">
        <div className="max-w-4xl mx-auto space-y-3 sm:space-y-4">
          {messages.length === 0 ? null : (
            <>
              {messages.map((msg, idx) => {
                const parsed = msg.role === "assistant" ? parseEventContent(msg.content) : null;

                return (
                  <div key={idx} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                    <div
                      className={cn(
                        "max-w-[92%] sm:max-w-[85%] rounded-2xl font-ibm-plex text-base",
                        msg.role === "user"
                          ? mode === "promoter"
                            ? `${proStyles.bgCard} text-foreground ${proStyles.border} border px-4 py-3`
                            : "bg-muted text-foreground border border-border px-4 py-3"
                          : mode === "promoter"
                            ? `${proStyles.bgElevated} text-card-foreground ${proStyles.border} border px-4 py-3`
                            : parsed?.hasEvents
                              ? "bg-transparent p-0"
                              : "bg-card text-card-foreground border border-border px-4 py-3",
                      )}
                    >
                      {parsed?.hasEvents ? (
                        <div className="space-y-3">
                          {parsed.textParts.map(
                            (text, i) =>
                              text.trim() && (
                                <p
                                  key={`text-${i}`}
                                  className="whitespace-pre-wrap text-muted-foreground text-base sm:text-sm"
                                  dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
                                />
                              ),
                          )}
                          {parsed.events.map((event, i) => (
                            <EventCard key={`event-${i}`} event={event} />
                          ))}
                        </div>
                      ) : (
                        <div
                          className="whitespace-pre-wrap"
                          dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
              {isLoading && (
                <div className="flex justify-start">
                  <div
                    className={cn(
                      "rounded-2xl px-4 py-3 border",
                      mode === "promoter"
                        ? `${proStyles.bgElevated} ${proStyles.border}`
                        : "bg-card border-border",
                    )}
                  >
                    <div
                      className={cn(
                        "w-5 h-5 border-2 border-muted-foreground/30 rounded-full animate-spin",
                        mode === "promoter" ? "border-t-accent" : "border-t-primary",
                      )}
                    />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </div>

      {/* Input area */}
      <div
        className={cn(
          "flex-shrink-0 border-t p-3 sm:p-4 pb-[env(safe-area-inset-bottom,12px)]",
          mode === "promoter"
            ? `${proStyles.bgElevated} ${proStyles.border}`
            : "bg-card border-border",
        )}
      >
        <div className="max-w-4xl mx-auto flex items-center gap-2 sm:gap-3">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleMicClick}
                  className={cn(
                    "h-10 w-10",
                    mode === "promoter"
                      ? "text-muted-foreground hover:text-accent"
                      : "text-muted-foreground hover:text-primary",
                    isRecording && "text-destructive animate-pulse",
                  )}
                  disabled={isLoading}
                >
                  {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p className="text-xs">Beta — voice transcription may contain errors</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
            placeholder={mode === "promoter" ? "Tell me about your event..." : t.chat.placeholder}
            className={cn(
              "flex-1 font-ibm-plex text-base h-11 sm:h-10",
              mode === "promoter"
                ? `${proStyles.bgCard} ${proStyles.border} focus-visible:ring-accent`
                : "bg-background border-border",
            )}
          />

          <Button
            onClick={handleSendMessage}
            variant={mode === "promoter" ? "secondary" : "default"}
            size="icon"
            disabled={isLoading || !message.trim()}
            className={cn(
              "h-10 w-10",
              mode === "promoter" && "bg-accent text-accent-foreground hover:bg-accent/90",
            )}
          >
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Chat;
