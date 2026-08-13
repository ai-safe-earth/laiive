import type { EventDraft } from "@shared/protocol";
import { AlertCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";

/** Fields the graph write refuses without (laiive_shared.REQUIRED_DRAFT_FIELDS). */
const REQUIRED = ["artists", "start_at", "venue", "city", "price_min"] as const;

const FIELDS: { key: keyof EventDraft; label: string; type?: string }[] = [
  { key: "name", label: "event name" },
  { key: "artists", label: "artists (comma separated)" },
  { key: "start_at", label: "starts at", type: "datetime-local" },
  { key: "venue", label: "venue" },
  { key: "address", label: "address" },
  { key: "city", label: "city" },
  { key: "price_min", label: "price from", type: "number" },
  { key: "price_max", label: "price to", type: "number" },
  { key: "price_currency", label: "currency" },
  { key: "genre", label: "genre" },
  { key: "ticket_url", label: "ticket link" },
  { key: "description", label: "description" },
];

/** `datetime-local` wants "YYYY-MM-DDTHH:mm" and rejects anything longer. */
function toInputDateTime(value: string | null | undefined): string {
  if (!value) return "";
  return value.slice(0, 16);
}

function displayValue(draft: EventDraft, key: keyof EventDraft): string {
  const value = draft[key];
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join(", ");
  if (key === "start_at") return toInputDateTime(String(value));
  return String(value);
}

/**
 * The last step of every submission path: whatever voice, a flyer, a document
 * or plain typing produced, it lands here for the human to complete and
 * approve. Saving is the only thing that writes to the graph.
 */
export function EventForm({
  draft,
  missing,
  onSave,
  saving,
}: {
  draft: EventDraft;
  missing: string[];
  onSave: (draft: EventDraft) => void;
  saving: boolean;
}) {
  const [values, setValues] = useState<EventDraft>(draft);

  // Each turn re-extracts over the whole conversation, so a later message can
  // fill a field the user has not touched — take the server's draft as truth.
  useEffect(() => setValues(draft), [draft]);

  const stillMissing = REQUIRED.filter((key) => {
    const value = values[key];
    return value === null || value === undefined || value === "" ||
      (Array.isArray(value) && value.length === 0);
  });

  const update = (key: keyof EventDraft, raw: string) => {
    setValues((current) => ({
      ...current,
      [key]:
        key === "artists"
          ? raw.split(",").map((part) => part.trim()).filter(Boolean)
          : key === "price_min" || key === "price_max"
            ? raw === "" ? null : Number(raw)
            : raw === "" ? null : raw,
    }));
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSave(values);
      }}
      className="space-y-3 rounded-lg border border-pro-border bg-pro-card p-4"
    >
      <div className="flex items-center justify-between">
        <h3 className="font-montserrat text-sm font-bold text-accent">event details</h3>
        {stillMissing.length > 0 && (
          <span className="flex items-center gap-1 text-xs text-destructive">
            <AlertCircle className="h-3 w-3" />
            {stillMissing.length} still needed
          </span>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {FIELDS.map(({ key, label, type }) => {
          const isMissing = stillMissing.includes(key as (typeof REQUIRED)[number]);
          const wasMissing = missing.includes(key);
          return (
            <label key={key} className="space-y-1">
              <span
                className={cn(
                  "font-ibm-plex text-xs",
                  isMissing ? "text-destructive" : "text-muted-foreground",
                )}
              >
                {label}
                {(REQUIRED as readonly string[]).includes(key) && " *"}
              </span>
              <Input
                type={type ?? "text"}
                value={displayValue(values, key)}
                onChange={(event) => update(key, event.target.value)}
                placeholder={wasMissing ? "the assistant could not find this" : ""}
                className={cn(
                  "h-9 text-sm",
                  isMissing && "border-destructive/60 focus-visible:ring-destructive",
                )}
              />
            </label>
          );
        })}
      </div>

      <div className="flex items-center gap-3 pt-1">
        <Button type="submit" variant="accent" disabled={saving || stillMissing.length > 0}>
          {saving ? "publishing…" : "publish to laiive"}
        </Button>
        {stillMissing.length > 0 && (
          <span className="text-xs text-muted-foreground">
            fill {stillMissing.join(", ")} — by typing here or just telling the assistant
          </span>
        )}
      </div>
    </form>
  );
}
