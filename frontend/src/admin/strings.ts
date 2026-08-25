/**
 * Admin copy — English only, deliberately outside `i18n/translations.ts`.
 *
 * Every other surface in this app is translated into en/es/it/ca, and a
 * missing key there is a compile error rather than a fallback. That rule is
 * right for anything a user sees. This surface has exactly one reader, who
 * speaks English, and putting ~50 keys through four language blocks would add
 * real work to every label forever in exchange for nothing.
 *
 * If a second admin ever arrives who does not read English, move this module
 * into `Translations` rather than bolting a second mechanism beside it.
 */
export const A = {
  title: "Admin",
  nav: { queue: "Review queue", back: "Back to laiive" },

  queue: {
    heading: "Reports",
    waiting: "Waiting",
    all: "All",
    empty: "Nothing waiting. Every sweep has been reviewed.",
    emptyAll: "No reports yet. A sweep writes one when it finishes.",
    loading: "Reading the queue…",
    failed: "Could not read the queue.",
    retry: "Try again",
    city: "City",
    when: "Swept",
    found: "New",
    credits: "Credits",
    status: "Status",
    backfillKind: "backfill",
  },

  report: {
    back: "All reports",
    candidates: "Candidates",
    selected: (n: number) => `${n} selected`,
    selectAll: "Select all new",
    clear: "Clear",
    approve: "Approve selected",
    approving: "Writing to the graph…",
    dismiss: "Dismiss report",
    dismissing: "Dismissing…",
    dismissPrompt: "Why is this being dismissed? (optional)",
    empty: "This sweep found nothing.",
    loading: "Opening the report…",
    failed: "Could not open the report.",

    colName: "Event",
    colVenue: "Venue",
    colWhen: "Starts",
    colSource: "Source",
    colVerdict: "Verdict",

    missing: (fields: string[]) => `missing ${fields.join(", ")}`,
    noVenue: "no venue",
    // The writer refuses a draft without a venue, so saying so up front beats
    // an "invalid" row in the result afterwards.
    willBeRefused: "will be refused — no venue",
  },

  verdict: {
    new: "new",
    exists: "already in graph",
    similar: "looks similar",
  },

  result: {
    heading: "What was written",
    created: "written",
    duplicate: "already there",
    invalid: "refused",
    error: "failed",
    summary: (created: number, total: number) =>
      `${created} of ${total} written to the graph`,
  },

  stats: {
    failed: "The numbers did not load — the queue below still works.",
    schedulerDown:
      "Schedules are registered but nothing is polling — the next run will not fire until flows/serve.py is up.",
    schedulerUnconfigured: "scheduler not configured (PREFECT_API_URL unset)",
    prefectUnreachable:
      "Prefect Cloud is unreachable — the scheduler may be fine, but this panel cannot see it right now.",
    eventsDaily: "events added · last 30 days",
    waitingReports: "waiting reports",
    waitingCandidates: (n: number) => `${n} candidates to review`,
    creditsMonth: "tavily this month",
    projected: (n: number) => `projected ${n} by month end`,
    graphEvents: "events in the graph",
    graphUnreachable: "graph unreachable (Aura paused?)",
    artistsVenues: (artists: number, venues: number) =>
      `${artists} artists · ${venues} venues`,
    quality: "start time known",
    priceKnown: (pct: number) => `price known ${pct}%`,
    creditsWeekly: "credits per week",
    perSweep: "new candidates per sweep",
    noSweeps: "No sweeps in the window yet.",
    sources: "top sources by new candidates",
    queriesStanding: (standing: number, trial: number) =>
      `${standing} standing · ${trial} trial phrasings`,
    upcoming: "scheduled rounds",
    noDeployments: "No deployments registered in Prefect Cloud.",
    neverRan: "never ran",
  },

  status: {
    dry_run: "waiting",
    approved: "approved",
    dismissed: "dismissed",
    running: "running",
    failed: "failed",
    done: "done",
  } as Record<string, string>,
};
