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
 * The animation itself is a Claude Design piece and is not here yet; the frame
 * below is sized for it and holds its place, so landing it later changes this
 * component's contents and nothing else on the page.
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
    <section className="flex flex-col gap-3.5 rounded-[20px] border border-pro-border bg-pro-bg-card px-5 py-[18px]">
      {/* One control, and it says what it does. A close X beside it would
          read as "hide for now" while quietly meaning "never again", and
          two buttons would carry the same accessible name. */}
      <h2 className="font-bebas text-[21px] leading-none tracking-[0.05em] text-pro-fg">
        {t.pro.onboardingTitle}
      </h2>

      {/* Placeholder for the walkthrough animation. Its aspect ratio is the
          contract with the artwork; everything else here is scaffolding. */}
      <div
        aria-hidden="true"
        className="flex aspect-[16/9] w-full items-center justify-center rounded-[14px] border border-dashed border-pro-border bg-pro-bg"
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.11em] text-pro-dim">
          {t.pro.onboardingPending}
        </span>
      </div>

      <ol className="flex flex-col gap-1.5">
        {t.pro.onboardingSteps.map((step, index) => (
          <li key={step} className="flex gap-2.5 text-[13.5px] leading-[1.45] text-pro-muted">
            <span className="font-mono text-[11px] leading-[1.6] text-pro-accent">{index + 1}</span>
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
        className="self-start rounded-full py-2 font-mono text-[11px] text-pro-accent transition-opacity hover:opacity-80"
      >
        {t.pro.onboardingDismiss}
      </button>
    </section>
  );
}
