import type { ReactNode } from "react";
import { Icon } from "@/components/Icon";
import { MicButton } from "@/components/MicButton";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

/**
 * The one composer, both surfaces: mic on the left, field in the middle, send
 * on the right. The mic is neutral outlined; only the send carries the accent,
 * filled with dark ink — fuchsia on the consumer side, cyan on pro — and while
 * a reply streams the send slot becomes stop. brand-rules.md carries the spec.
 */
export function Composer({
  value,
  onChange,
  onSend,
  onStop,
  isStreaming = false,
  disabled = false,
  accent,
  placeholder,
  transcribe,
  onTranscript,
  attachSlot,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  isStreaming?: boolean;
  /** Busy without a stream to stop — file ingest, publish. Mic and send wait. */
  disabled?: boolean;
  accent: "consumer" | "pro";
  placeholder: string;
  transcribe: (recording: Blob) => Promise<string>;
  onTranscript: (text: string) => void;
  /** The pro attach control; the consumer side passes nothing and gets nothing. */
  attachSlot?: ReactNode;
}) {
  const { t } = useTranslation();
  const pro = accent === "pro";

  return (
    <div className={cn("mx-auto flex max-w-3xl items-center", pro ? "gap-3" : "gap-2.5")}>
      {attachSlot}
      <MicButton
        variant={pro ? "proNeutralOutline" : "neutralOutline"}
        transcribe={transcribe}
        onTranscript={onTranscript}
        disabled={disabled || isStreaming}
      />
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) =>
          event.key === "Enter" &&
          !isStreaming &&
          !disabled &&
          value.trim() !== "" &&
          onSend()
        }
        placeholder={placeholder}
        aria-label={placeholder}
        className={cn(pro && "focus-visible:ring-pro-accent")}
      />
      {isStreaming ? (
        // t.chat.stop on both surfaces: there is no pro.stop key, and the word
        // is the same. If consumer copy ever diverges, pro grows its own key.
        <Button
          variant={pro ? "cyan" : "primary"}
          size="icon"
          onClick={onStop}
          aria-label={t.chat.stop}
        >
          <Icon name="close" />
        </Button>
      ) : (
        <Button
          variant={pro ? "cyan" : "primary"}
          size="icon"
          onClick={onSend}
          disabled={disabled || !value.trim()}
          aria-label={pro ? t.pro.send : t.chat.send}
        >
          <Icon name="send" className="h-[18px] w-[18px]" />
        </Button>
      )}
    </div>
  );
}
