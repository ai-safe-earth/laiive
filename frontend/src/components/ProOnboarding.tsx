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
 * The numbered steps that used to sit under the video are gone: the new cut
 * shows the four moves in the product itself, and a written list beside it was
 * the same thing said twice. That leaves the video carrying the whole panel,
 * so it is no longer aria-hidden — it takes a label naming what it shows,
 * which is what a screen reader now gets in place of the steps.
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
      {/* No heading and no copy: the cut shows what this is faster than a line
          naming it, which is the whole reason the steps came out. */}
      <video
        ref={setSpeed}
        aria-label={t.pro.onboardingVideo}
        className="aspect-[16/9] w-full rounded-[14px] border border-pro-border bg-pro-bg object-cover"
        src="/pro-walkthrough.mp4"
        autoPlay
        muted
        loop
        playsInline
      />

      {/* A checkbox, not a button: "don't show this again" is a preference
          about future visits, and a button that makes the panel vanish reads
          as closing it for now. Ticking it is the whole interaction — there is
          no separate confirm, because there is nothing else on the panel. */}
      <label
        htmlFor="pro-onboarding-hide"
        className="flex min-h-11 cursor-pointer items-center gap-2.5 font-mono text-xs text-pro-accent"
      >
        <input
          id="pro-onboarding-hide"
          type="checkbox"
          onChange={(event) => {
            if (!event.target.checked) return;
            remember();
            setOpen(false);
          }}
          className="h-4 w-4 flex-none accent-pro-accent"
        />
        {t.pro.onboardingDismiss}
      </label>
    </section>
  );
}
