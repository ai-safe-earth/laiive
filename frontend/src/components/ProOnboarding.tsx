import { useState } from "react";
import { useTranslation } from "@/i18n/useTranslation";

/**
 * What the walk is, shown once.
 *
 * brand-rules.md bans onboarding copy, and that rule is written for the
 * consumer chat: a reader types a question and gets an answer, and anything
 * before that is in the way. The promoter side is not that. It asks somebody
 * to hand over their event and trust what comes back, and nothing on the
 * screen said what the four steps were. This is the deliberate exception, and
 * it is one panel, dismissible for good.
 *
 * The walkthrough video ships from /public and plays silently on loop: it is
 * illustration, so it is aria-hidden and the numbered steps below stay the
 * accessible account of the same four moves.
 */
const STORAGE_KEY = "laiive-pro-onboarding-seen";

/** Private mode throws on both of these, and a throw here would blank /pro. */
function seen(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Three-quarter speed: at 1x the cut outruns a first-time reader. */
const SPEED = 0.75;

/**
 * Both rates, and a stable function so React sets them once. The media load
 * algorithm resets `playbackRate` to `defaultPlaybackRate`, so setting only
 * the former would snap back to 1x the moment the source finished loading.
 */
function setSpeed(node: HTMLVideoElement | null): void {
  if (!node) return;
  node.defaultPlaybackRate = SPEED;
  node.playbackRate = SPEED;
}

function remember(): void {
  try {
    localStorage.setItem(STORAGE_KEY, "1");
  } catch {
    // Nothing to do: it shows again next time, which is the safe failure.
  }
}

export function ProOnboarding() {
  // Lazy initialiser, not an effect — an effect would flash the panel at
  // somebody who dismissed it months ago.
  const [open, setOpen] = useState(() => !seen());
  const { t } = useTranslation();

  if (!open) return null;

  return (
    <section className="flex flex-col gap-3.5 rounded-[20px] border border-pro-border bg-pro-card px-5 py-[18px]">
      {/* No heading: the video opens the panel and shows what this is faster
          than a line of copy naming it. The numbered steps under it carry the
          same account for anyone who cannot see the video. */}
      <video
        ref={setSpeed}
        aria-hidden="true"
        className="aspect-[16/9] w-full rounded-[14px] border border-pro-border bg-pro-bg object-cover"
        src="/pro-walkthrough.mp4"
        autoPlay
        muted
        loop
        playsInline
      />

      <ol className="flex flex-col gap-1.5">
        {t.pro.onboardingSteps.map((step, index) => (
          <li key={step} className="flex gap-2.5 text-md leading-[1.45] text-pro-muted">
            <span className="font-mono text-xs leading-[1.6] text-pro-accent">{index + 1}</span>
            {step}
          </li>
        ))}
      </ol>

      <button
        type="button"
        onClick={() => {
          remember();
          setOpen(false);
        }}
        className="min-h-11 self-start rounded-full font-mono text-xs text-pro-accent transition-opacity hover:opacity-80"
      >
        {t.pro.onboardingDismiss}
      </button>
    </section>
  );
}
