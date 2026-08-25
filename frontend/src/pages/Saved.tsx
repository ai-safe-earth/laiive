import type { EventCard } from "@shared/protocol";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { claimTarget } from "@/auth/claimTarget";
import { useSavedCards, useSavedUids, useToggleSaved } from "@/api/savedEvents";
import { EventCardView } from "@/components/EventCardView";
import { Icon } from "@/components/Icon";
import { useTranslation } from "@/i18n/useTranslation";

/**
 * Upcoming first, ascending; then what has already happened, most recent
 * first. A saved night that has passed is not deleted — it is just no longer
 * news, and a card silently vanishing on the day would be worse.
 */
export function splitByTime(
  cards: EventCard[],
  now = Date.now(),
): { upcoming: EventCard[]; past: EventCard[] } {
  const upcoming: EventCard[] = [];
  const past: EventCard[] = [];
  for (const card of cards) {
    const at = card.start_at ? new Date(card.start_at).getTime() : Number.NaN;
    // No date at all counts as upcoming: it has not been shown to be over.
    if (Number.isNaN(at) || at >= now) upcoming.push(card);
    else past.push(card);
  }
  const by = (a: EventCard, b: EventCard) =>
    new Date(a.start_at ?? 0).getTime() - new Date(b.start_at ?? 0).getTime();
  upcoming.sort(by);
  past.sort((a, b) => by(b, a));
  return { upcoming, past };
}

/** Mono small-caps section rule, the voice used for every other label here. */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-ink-dim">{children}</p>
  );
}

export default function Saved() {
  const { user, role } = useAuth();
  const { language, t } = useTranslation();

  const { data: uids, isLoading: uidsLoading } = useSavedUids(user?.id);
  const {
    data: cards,
    isLoading: cardsLoading,
    isError,
    refetch,
  } = useSavedCards(uids);
  const toggleSaved = useToggleSaved(user?.id);

  const { upcoming, past } = splitByTime(cards ?? []);
  const loading = uidsLoading || (uids !== undefined && uids.length > 0 && cardsLoading);

  const group = (heading: string, group: EventCard[]) =>
    group.length > 0 && (
      <section className="flex flex-col gap-2">
        <SectionLabel>{heading}</SectionLabel>
        {group.map((card) => (
          <EventCardView
            key={card.uid}
            card={card}
            language={language}
            saved
            claimTo={claimTarget(Boolean(user), role)}
            // Unsaving from this page removes the card in front of you. That
            // is the whole point of being here, and the app has no undo
            // anywhere, so it does not pretend to have one now.
            onToggleSave={(uid, next) => toggleSaved.mutate({ uid, next })}
          />
        ))}
      </section>
    );

  return (
    <div className="min-h-[100dvh] bg-background">
      <header className="flex items-center gap-2 border-b border-rule px-3 py-2 sm:px-4">
        <Link
          to="/"
          aria-label={t.savedPage.back}
          className="flex h-11 w-11 items-center justify-center text-ink-dim transition-colors hover:text-foreground"
        >
          <Icon name="back" />
        </Link>
        <h1 className="font-bebas text-[24px] leading-none tracking-[0.04em] text-card-foreground">
          {t.savedPage.title}
        </h1>
      </header>

      <div className="mx-auto flex max-w-3xl flex-col gap-6 p-4 sm:p-6">
        {loading && (
          <p className="animate-pulse font-mono text-[11px] uppercase tracking-[0.11em] text-ink-dim">
            {t.savedPage.title}
          </p>
        )}

        {!loading && isError && (
          <div className="flex flex-col items-start gap-2.5">
            <p className="text-[14px] text-muted-foreground">{t.savedPage.failed}</p>
            <button
              type="button"
              onClick={() => void refetch()}
              className="rounded-full bg-field-border px-3.5 py-2.5 text-[12.5px] leading-none text-white transition-colors hover:bg-muted"
            >
              {t.savedPage.retry}
            </button>
          </div>
        )}

        {!loading && !isError && upcoming.length === 0 && past.length === 0 && (
          <div className="flex flex-col gap-1.5 pt-10">
            <p className="text-[15px] leading-[1.5] text-foreground">{t.savedPage.empty}</p>
            <p className="font-mono text-[11px] text-ink-dim">{t.savedPage.emptyHint}</p>
          </div>
        )}

        {group(t.savedPage.upcoming, upcoming)}
        {group(t.savedPage.past, past)}
      </div>
    </div>
  );
}
