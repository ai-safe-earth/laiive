import { Loader2, Mic, Square } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useRecorder } from "@/audio/useRecorder";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

/**
 * Record → transcribe → hand the text back. The caller decides what the
 * transcript means: in consumer chat it becomes the message, in the pro flow it
 * becomes another line of the conversation the extractor reads.
 */
export function MicButton({
  onTranscript,
  transcribe,
  disabled,
}: {
  onTranscript: (text: string) => void;
  transcribe: (recording: Blob) => Promise<string>;
  disabled?: boolean;
}) {
  const { isRecording, start, stop } = useRecorder();
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    if (busy) return;

    if (!isRecording) {
      try {
        await start();
      } catch {
        toast.error("Microphone permission denied");
      }
      return;
    }

    setBusy(true);
    try {
      const text = await transcribe(await stop());
      if (text.trim()) onTranscript(text.trim());
      else toast.error("Nothing came through — try again");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Transcription failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => void toggle()}
      disabled={disabled || busy}
      aria-label={isRecording ? "Stop recording" : "Record a message"}
      title={isRecording ? "Stop and transcribe" : "Speak instead of typing"}
      className={cn(isRecording && "text-destructive animate-pulse")}
    >
      {busy ? (
        <Loader2 className="h-5 w-5 animate-spin" />
      ) : isRecording ? (
        <Square className="h-4 w-4" />
      ) : (
        <Mic className="h-5 w-5" />
      )}
    </Button>
  );
}
