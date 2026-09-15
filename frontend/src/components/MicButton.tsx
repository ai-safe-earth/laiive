import { toast } from "sonner";
import { useEffect, useState } from "react";
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
 * At rest the mic wears its surface's neutral outline — the send keeps the
 * fuchsia and the cyan, and the variant is the caller's (the Composer's) call.
 * Recording, it fills amber and breathes: amber is the mic's colour in the
 * token file, and the one thing a live microphone must not look like is the
 * same button it was a second ago.
 */
export function MicButton({
  onTranscript,
  transcribe,
  disabled,
  variant,
  onRecordingChange,
}: {
  onTranscript: (text: string) => void;
  transcribe: (recording: Blob) => Promise<string>;
  disabled?: boolean;
  variant: ButtonProps["variant"];
  /** The composer draws the meter in its field; this is how it hears about it. */
  onRecordingChange?: (recording: boolean) => void;
}) {
  const { t } = useTranslation();
  const { isRecording, start, stop } = useRecorder();
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    onRecordingChange?.(isRecording);
  }, [isRecording, onRecordingChange]);

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
      // No spinner glyph in the set: transcribing reads as the mic breathing,
      // which is the only state the user can act on anyway. Recording breathes
      // in amber, with dark ink on it — cream on amber is 3.45:1.
      className={cn(
        (isRecording || busy) && "animate-pulse",
        // The hover has to be restated: the variant's own `hover:text-*` is a
        // different key to tailwind-merge, so without this the live mic turns
        // cream-on-amber under the pointer — 3.45:1, the pair banned above.
        isRecording &&
          "border-transparent bg-secondary text-secondary-foreground hover:text-secondary-foreground",
      )}
    >
      <Icon name="mic" />
    </Button>
  );
}
