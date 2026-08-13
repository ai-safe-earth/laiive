import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Mic, Loader2, Camera, MicOff, Plus, X, Upload } from "lucide-react";
import { UserAvatar } from "@/components/UserAvatar";
import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { EventConfirmationForm } from "@/components/EventConfirmationForm";
import { toast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { AudioRecorder } from "@/utils/audioRecorder";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useTranslation } from "@/hooks/useTranslation";
import { useSession } from "@/hooks/useSession";
import { useAuth } from "@/hooks/useAuth";
import { detectLanguageFromText } from "@/utils/detectLanguage";
import { parseSSEStream } from "@/utils/parseSSE";
import { callFunction } from "@/utils/apiClient";
import { pusherFetch, pusherFetchJSON } from "@/utils/pusherClient";
import type { EventDetails } from "@/types/api";

const PromoterCreate = () => {
  const navigate = useNavigate();
  const { language, setLanguage, t } = useTranslation();
  const { sessionId, deviceType, userAgent } = useSession();
  const { user, session, isLoading: authLoading, isPromoter } = useAuth();
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [extractedEvent, setExtractedEvent] = useState<EventDetails | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [promoterName, setPromoterName] = useState<string>("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const audioRecorderRef = useRef<AudioRecorder | null>(null);

  // Lazy-init audio recorder and clean up on unmount
  useEffect(() => {
    audioRecorderRef.current = new AudioRecorder();
    return () => {
      audioRecorderRef.current?.stop().catch(() => {});
      audioRecorderRef.current = null;
    };
  }, []);

  // Fetch promoter profile name
  useEffect(() => {
    const fetchPromoterName = async () => {
      if (user?.id) {
        const { data } = await supabase
          .from('promoter_profiles')
          .select('first_name, last_name')
          .eq('user_id', user.id)
          .single();

        if (data) {
          setPromoterName(`${data.first_name} ${data.last_name}`);
        }
      }
    };
    fetchPromoterName();
  }, [user?.id]);

  // Detect URL in text
  const extractUrl = (text: string): string | null => {
    const urlRegex = /(https?:\/\/[^\s]+)/i;
    const match = text.match(urlRegex);
    return match ? match[1] : null;
  };

  // Extract event from URL
  const extractEventFromUrl = async (url: string) => {
    setIsExtracting(true);
    try {
      const data = await pusherFetchJSON<{ success: boolean; eventData?: EventDetails; error?: string }>(
        "/extract-event-from-url",
        { url, language },
      );

      if (data.success && data.eventData) {
        setExtractedEvent(data.eventData);
        return true;
      } else {
        throw new Error(data.error || "Could not extract event details");
      }
    } catch (error) {
      console.error("Error extracting from URL:", error);
      toast({
        title: "Extraction failed",
        description: "Could not extract event details from this URL. Please enter manually.",
        variant: "destructive",
      });
      return false;
    } finally {
      setIsExtracting(false);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      toast({
        title: "Invalid file type",
        description: "Please upload an image file (JPG, PNG, etc.)",
        variant: "destructive",
      });
      return;
    }

    setIsExtracting(true);
    setIsMenuOpen(false);

    try {
      const reader = new FileReader();
      reader.onload = async () => {
        const base64 = reader.result?.toString().split(",")[1];

        const data = await pusherFetchJSON<{ success: boolean; eventDetails?: EventDetails; error?: string }>(
          "/extract-event-details",
          { imageBase64: base64 },
        );

        if (data.success && data.eventDetails) {
          setExtractedEvent(data.eventDetails);
        } else {
          throw new Error(data.error || "Extraction failed");
        }
      };
      reader.readAsDataURL(file);
    } catch (error) {
      console.error("Error extracting event details:", error);
      toast({
        title: "Extraction failed",
        description: "We couldn't read all details from this file. Please try again or enter manually.",
        variant: "destructive",
      });
    } finally {
      setIsExtracting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (cameraInputRef.current) cameraInputRef.current.value = "";
    }
  };

  const handleConfirmEvent = async (eventDetails: EventDetails): Promise<void> => {
    const data = await pusherFetchJSON<{ success?: boolean; error?: string }>(
      "/validate-event",
      {
        event: {
          name: eventDetails.name,
          artist: eventDetails.artist,
          description: eventDetails.description,
          event_date: eventDetails.event_date,
          venue: eventDetails.venue,
          city: eventDetails.city,
          price: eventDetails.price,
          ticket_url: eventDetails.ticket_url,
        },
        session_id: sessionId,
        user_id: user?.id,
      },
    );

    if (!data.success) {
      toast({
        title: "Error",
        description: data.error || "Failed to create event. Please try again.",
        variant: "destructive",
      });
      throw new Error(data.error || "Event validation failed");
    }
  };

  const handleFormClose = () => {
    setExtractedEvent(null);
    setMessages([
      ...messages,
      { role: "assistant", content: t.promoterCreate.welcome },
    ]);
  };

  /** Log a conversation message (fire-and-forget) */
  const logMessage = (role: string, content: string, lang: string) => {
    if (!sessionId) return;
    callFunction("validate-conversation", {
      session_id: sessionId,
      conversation_type: "promoter",
      message_role: role,
      message_content: content,
      device_type: deviceType,
      user_agent: userAgent,
      language: lang,
    }).catch(() => {});
  };

  const handleSendMessage = async () => {
    if (!message.trim() || isLoading) return;

    const detected = detectLanguageFromText(message);
    if (detected && detected !== language) {
      setLanguage(detected as 'en' | 'es' | 'it' | 'ca');
    }
    const currentLanguage = detected || language;

    // Check if message contains a URL and try to extract event
    const url = extractUrl(message);
    if (url) {
      const userMessage = { role: "user" as const, content: message };
      setMessages([...messages, userMessage]);
      setMessage("");

      const extracted = await extractEventFromUrl(url);
      if (extracted) return;
    }

    const userMessage = { role: "user" as const, content: message };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setMessage("");
    setIsLoading(true);

    logMessage("user", userMessage.content, currentLanguage);

    try {
      const accessToken = session?.access_token;
      if (!accessToken) {
        toast({ title: "Session expired", description: "Please sign in again.", variant: "destructive" });
        navigate('/auth');
        return;
      }

      const response = await pusherFetch(
        "/chat/stream",
        { messages: newMessages, language: currentLanguage },
      );

      if (!response.ok || !response.body) {
        throw new Error("Failed to send message");
      }

      let assistantMessage = "";
      for await (const chunk of parseSSEStream(response)) {
        assistantMessage += chunk;

        // Check accumulated message for the extraction marker
        const extractedMatch = assistantMessage.match(/__EVENT_EXTRACTED__(.+)__EVENT_EXTRACTED__/);
        if (extractedMatch) {
          const eventDetails = JSON.parse(extractedMatch[1]);
          setExtractedEvent(eventDetails);
          setIsLoading(false);
          return;
        }

        // Only update visible messages if no marker is building up
        if (!assistantMessage.includes("__EVENT_EXTRACTED__")) {
          setMessages([...newMessages, { role: "assistant", content: assistantMessage }]);
        }
      }

      logMessage("assistant", assistantMessage, currentLanguage);
    } catch (error) {
      console.error("Error sending message:", error);
      setMessages([
        ...newMessages,
        { role: "assistant", content: "Sorry, I encountered an error. Please try again." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMicClick = async () => {
    setIsMenuOpen(false);
    const recorder = audioRecorderRef.current;
    if (!recorder) return;

    if (isRecording) {
      try {
        const audioBase64 = await recorder.stop();
        setIsRecording(false);
        setIsExtracting(true);

        const { text } = await pusherFetchJSON<{ text: string }>(
          "/transcribe-audio",
          { audio: audioBase64 },
        );

        const extractData = await pusherFetchJSON<{ success: boolean; eventDetails?: EventDetails; error?: string }>(
          "/extract-event-from-text",
          { text },
        );

        if (!extractData.success) {
          throw new Error(extractData.error || "Failed to extract event details");
        }

        setExtractedEvent(extractData.eventDetails!);
        toast({ title: "Event details extracted!", description: "Please review and confirm the information." });
      } catch (error) {
        console.error("Error processing audio:", error);
        toast({
          title: "Extraction failed",
          description: "We couldn't understand the audio. Please try speaking again.",
          variant: "destructive",
        });
      } finally {
        setIsExtracting(false);
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
    <div className="flex flex-col h-screen bg-[hsl(var(--pro-bg))]">
      {/* Header */}
      <header className="border-b border-accent/20 bg-[hsl(var(--pro-bg))] p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-end gap-4">
            <div className="flex items-center gap-1">
              <span className="text-xl font-bold text-foreground">laiive</span>
              <span className="text-xs px-2 py-0.5 bg-accent/20 text-accent rounded-full border border-accent/30">
                PRO
              </span>
            </div>
            <button
              onClick={() => navigate("/")}
              className="font-ibm-plex text-[10px] text-muted-foreground hover:text-primary transition-colors pb-0.5 flex items-center gap-0.5"
            >
              <span className="text-[10px]">🫦</span>
              <span>laiive</span>
            </button>
          </div>

          <UserAvatar variant="pro" />
        </div>
      </header>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-4xl mx-auto space-y-4">
          {extractedEvent ? (
            <EventConfirmationForm
              eventDetails={extractedEvent}
              onConfirm={handleConfirmEvent}
              onCancel={handleFormClose}
            />
          ) : (
            <>
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}
                >
                  <div
                    className={cn(
                      "max-w-[80%] rounded-2xl px-4 py-3 font-ibm-plex whitespace-pre-wrap",
                      msg.role === "user"
                        ? "bg-muted text-foreground border border-border"
                        : "bg-card text-card-foreground border border-border",
                    )}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
              {(isLoading || isExtracting) && (
                <div className="flex justify-start">
                  <div className="bg-card text-card-foreground border border-border rounded-2xl px-4 py-3 flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="font-ibm-plex text-sm">
                      {isExtracting ? "Extracting event details..." : "Thinking..."}
                    </span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </div>

      {/* Input area */}
      <div className="border-t border-border bg-card p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-2">
            <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleFileUpload}
              className="hidden"
            />

            {/* Plus button with expandable menu */}
            <div className="relative">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                disabled={isExtracting || isLoading || extractedEvent !== null}
                className={cn(
                  "text-muted-foreground hover:text-primary transition-transform",
                  isMenuOpen && "rotate-45",
                )}
              >
                {isMenuOpen ? <X className="w-5 h-5" /> : <Plus className="w-5 h-5" />}
              </Button>

              {isMenuOpen && (
                <div className="absolute bottom-full left-0 mb-2 flex flex-col gap-1 bg-card border border-border rounded-lg p-1 shadow-lg">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => cameraInputRef.current?.click()}
                          className="text-muted-foreground hover:text-primary"
                        >
                          <Camera className="w-5 h-5" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="right">
                        <p className="text-xs">Take a photo</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={handleMicClick}
                          className={cn(
                            "text-muted-foreground hover:text-primary",
                            isRecording && "text-destructive animate-pulse",
                          )}
                        >
                          {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="right">
                        <p className="text-xs">Voice input (Beta)</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => fileInputRef.current?.click()}
                          className="text-muted-foreground hover:text-primary"
                        >
                          <Upload className="w-5 h-5" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="right">
                        <p className="text-xs">Upload image or document</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              )}
            </div>

            <Input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
              placeholder={t.promoterCreate.placeholder}
              className="flex-1 bg-background border-border font-ibm-plex focus-visible:ring-accent focus-visible:border-accent"
              disabled={extractedEvent !== null}
            />

            <Button
              onClick={handleSendMessage}
              size="icon"
              disabled={isLoading || !message.trim() || extractedEvent !== null}
              className="bg-accent hover:bg-cyan-600 text-accent-foreground"
            >
              {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PromoterCreate;
