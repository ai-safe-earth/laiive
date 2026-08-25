import { toast } from "sonner";
import { useState } from "react";
import { useRecorder } from "@/audio/useRecorder";
import { Icon } from "@/components/Icon";
import { Button, type ButtonProps } from "@/components/ui/Button";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

/**
 * Record → transcribe → hand the text back. The caller decides what the
 * transcript means: in consumer chat it becomes the message, in the pro flow it
 * becomes another line of the conversation the extractor reads.
 *
 * The mic wears the surface's accent outlined — fuchsia on the consumer side,
 * cyan on pro — and the variant is the caller's (the Composer's) call.
 */
export function MicButton({
  onTranscript,
  transcribe,
  disabled,
  variant,
}: {
  onTranscript: (text: string) => void;
  transcribe: (recording: Blob) => Promise<string>;
  disabled?: boolean;
  variant: ButtonProps["variant"];
}) {
  const { t } = useTranslation();
  const { isRecording, start, stop } = useRecorder();
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    if (busy) return;

    if (!isRecording) {
      try {
        await start();
      } catch {
        toast.error(t.voice.denied);
      }
      return;
    }

    setBusy(true);
    try {
      const text = await transcribe(await stop());
      if (text.trim()) onTranscript(text.trim());
      else toast.error(t.voice.nothing);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.voice.failed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      variant={variant}
      size="icon"
      onClick={() => void toggle()}
      // A recording in progress stays stoppable even when the composer rests
      // the mic (streaming, ingest): the alternative is a trapped recording
      // whose browser indicator stays lit until the whole turn ends.
      disabled={busy || (disabled && !isRecording)}
      aria-label={isRecording ? t.voice.stop : t.voice.speak}
      // No spinner glyph in the set: recording and transcribing both read as
      // the mic breathing, which is the only state the user can act on anyway.
      className={cn((isRecording || busy) && "animate-pulse")}
    >
      <Icon name="mic" />
    </Button>
  );
}
