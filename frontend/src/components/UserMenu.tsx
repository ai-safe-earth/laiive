import { LogOut, User as UserIcon } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { useLanguagePreference } from "@/i18n/useLanguagePreference";
import { LANGUAGES, type Language } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

export function UserMenu() {
  const { user, role, signOut } = useAuth();
  const { language, chooseLanguage } = useLanguagePreference();
  const [open, setOpen] = useState(false);

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1">
        {LANGUAGES.map((code: Language) => (
          <button
            key={code}
            onClick={() => chooseLanguage(code)}
            className={cn(
              "px-1 font-ibm-plex text-[11px] uppercase transition-colors",
              code === language ? "text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {code}
          </button>
        ))}
      </div>

      {user ? (
        <div className="relative">
          <button
            onClick={() => setOpen(!open)}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-muted text-xs font-semibold uppercase text-foreground"
            aria-label="Account menu"
          >
            {user.email?.[0] ?? <UserIcon className="h-4 w-4" />}
          </button>
          {open && (
            <div className="absolute right-0 z-20 mt-2 w-56 rounded-md border border-border bg-popover p-2 shadow-lg">
              <p className="truncate px-2 py-1 text-xs text-muted-foreground">{user.email}</p>
              <p className="px-2 pb-2 text-[10px] uppercase tracking-wider text-accent">{role}</p>
              <Link
                to="/account"
                onClick={() => setOpen(false)}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted"
              >
                <UserIcon className="h-4 w-4" /> account
              </Link>
              <button
                onClick={() => {
                  setOpen(false);
                  void signOut();
                }}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted"
              >
                <LogOut className="h-4 w-4" /> sign out
              </button>
            </div>
          )}
        </div>
      ) : (
        <Link
          to="/auth"
          className="font-ibm-plex text-sm text-muted-foreground transition-colors hover:text-primary"
        >
          sign in
        </Link>
      )}
    </div>
  );
}
