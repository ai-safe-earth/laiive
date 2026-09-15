import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Icon } from "@/components/Icon";
import { MicButton } from "@/components/MicButton";
import { Button } from "@/components/ui/Button";
import { FIELD, PRO_FIELD } from "@/components/ui/Input";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

/**
 * The one composer, both surfaces: attach (pro only) on the left, the field in
 * the middle, then mic and send on the right — the order every chat app has
 * settled on, so the two controls that act on what you just typed sit next to
 * it. Only the send carries the accent, filled with dark ink — fuchsia on the
 * consumer side, cyan on pro — and it keeps that accent while it waits, dimmed
 * rather than greyed, so the send is never the colourless control in the row.
 * While a reply streams the send slot becomes stop. brand-rules.md carries the
 * spec.
 *
 * The field grows with the message, one line to six, and then scrolls.
 */

/**
 * Six lines of 32px, 9px padding either side, 1px border either side. The 9 is
 * what keeps one line at exactly 52px — the height of the mic and the send it
 * sits between. 32px of leading, not 24, because `base` is 23px now: a 23px
 * face in a 24px line box is cramped and clips its descenders. 52 is the new
 * number to match when either changes; it is still over the 44px touch floor.
 */
const MAX_FIELD_HEIGHT = 212;

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
  // Lifted out of the mic so the field can show the recording too: a pulsing
  // 44px pill on its own was not enough to tell somebody the mic is live.
  const [recording, setRecording] = useState(false);
  const field = useRef<HTMLTextAreaElement>(null);

  // Grow with the content. Height must go back to auto first, or scrollHeight
  // only ever reports the height we last set and the field never shrinks again.
  // `recording` is a dependency because the meter's padding rewraps the text:
  // without it, starting a recording over a typed draft pushes the extra lines
  // out of a box that never grew.
  useLayoutEffect(() => {
    const element = field.current;
    if (!element) return;
    element.style.height = "auto";
    // scrollHeight is the padding box; the field is border-box with a 1px edge
    // top and bottom, so setting the height to it leaves the content 2px short
    // and the pill carries a scrollbar at every size, one line included.
    const edges = element.offsetHeight - element.clientHeight;
    element.style.height = `${Math.min(element.scrollHeight + edges, MAX_FIELD_HEIGHT)}px`;
  }, [value, recording]);

  const send = () => {
    if (isStreaming || disabled || value.trim() === "") return;
    onSend();
  };

  return (
    // items-end, not items-center: when the field grows past one line the
    // controls stay on the bottom row with it, as they do everywhere else.
    <div className={cn("mx-auto flex max-w-3xl items-end", pro ? "gap-3" : "gap-2.5")}>
      {attachSlot}
      <div className="relative min-w-0 flex-1">
        <textarea
          ref={field}
          rows={1}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            // An IME's Enter confirms the candidate word; on a Japanese or
            // Chinese keyboard that keystroke would otherwise send half a
            // sentence and clear the rest.
            if (event.nativeEvent.isComposing) return;
            // Enter sends, shift+Enter breaks the line — and the composer is
            // the one place a stray Enter must not queue a second turn.
            if (event.key !== "Enter" || event.shiftKey) return;
            event.preventDefault();
            send();
          }}
          placeholder={placeholder}
          aria-label={placeholder}
          className={cn(
            FIELD,
            // The literal 212 twice on purpose: tailwind scans this file as
            // text, so a class built from MAX_FIELD_HEIGHT is never generated.
            "block max-h-[212px] resize-none overflow-y-auto rounded-[22px] px-4 py-[9px] leading-8",
            // Room for the meter — nine 8px cells, 16px off the right edge,
            // and 8px of air — so a typed draft never runs underneath it.
            recording && "pr-[96px]",
            pro && PRO_FIELD,
          )}
        />
        {recording && <Waveform />}
      </div>
      <MicButton
        variant={pro ? "proNeutralOutline" : "neutralOutline"}
        transcribe={transcribe}
        onTranscript={onTranscript}
        onRecordingChange={setRecording}
        disabled={disabled || isStreaming}
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
          onClick={send}
          disabled={disabled || !value.trim()}
          aria-label={pro ? t.pro.send : t.chat.send}
          // Waiting, not absent: the disabled send keeps its accent at half
          // strength instead of taking the grey card fill every other disabled
          // button wears. Dark ink stays full strength — it is the only thing
          // holding the glyph up against a 45% fill.
          className={cn(
            "disabled:border-transparent",
            pro
              ? "disabled:bg-pro-accent/45 disabled:text-background"
              : "disabled:bg-primary/45 disabled:text-primary-foreground",
          )}
        >
          <Icon name="send" className="h-[18px] w-[18px]" />
        </Button>
      )}
    </div>
  );
}

/** The bar glyphs, quietest to loudest. */
const BARS = ["▁", "▂", "▃", "▄", "▅", "▆", "▇"];
const BAR_COUNT = 9;

/**
 * Proof the mic is live, inside the field where the words will land. A
 * travelling sine rather than sampled amplitude: the recorder hands back one
 * Blob at the end, so there is no level to read, and a meter that pretends to
 * follow a voice it cannot hear is a lie told sixty times a second.
 *
 * aria-hidden — the mic button already announces "stop and transcribe", which
 * is the same fact said once, in words.
 */
function Waveform() {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setFrame((n) => n + 1), 110);
    return () => clearInterval(timer);
  }, []);

  const bars = Array.from({ length: BAR_COUNT }, (_, index) => {
    const level = (Math.sin((frame + index) * 0.7) + 1) / 2;
    return BARS[Math.round(level * (BARS.length - 1))];
  });

  return (
    <span
      aria-hidden="true"
      data-testid="recording-waveform"
      className={cn(
        "pointer-events-none absolute bottom-0 right-4 flex h-[52px] items-center",
        // The one place a literal size is right: these glyphs are a graphic,
        // not type, and they have to stay inside the 8px cells below. `base`
        // would drag them to 23px and burst the meter out of its reservation.
        "font-mono text-[15px] leading-none text-secondary",
      )}
    >
      {bars.map((bar, index) => (
        // A fixed cell per bar. The block glyphs are not monospaced — ▇ is half
        // again as wide as ▁, measured — so a plain string would jitter between
        // 94 and 142px as the levels move. Nine 8px cells is 72px, and with the
        // right-4 offset that sits inside the pr-[96px] the field reserves.
        <span key={index} className="inline-block w-2 text-center">
          {bar}
        </span>
      ))}
    </span>
  );
}
