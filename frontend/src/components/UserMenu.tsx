import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { Icon } from "@/components/Icon";
import { useTranslation } from "@/i18n/useTranslation";

/**
 * Icons only, no labels — the chrome inventory allows the account icon and
 * nothing beside it. Language and every other preference live in settings,
 * inside this menu, never in the header.
 */
export function UserMenu() {
  const { t } = useTranslation();
  const { user, role, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);

  // A menu that only closes on its own items strands the user on a phone,
  // where there is no Escape key and no obvious way back.
  useEffect(() => {
    if (!open) return;
    const dismiss = (event: MouseEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", dismiss);
    return () => document.removeEventListener("mousedown", dismiss);
  }, [open]);

  if (!user) {
    return (
      <Link
        to="/auth"
        aria-label={t.menu.signIn}
        className="flex h-11 w-11 items-center justify-center text-ink-dim transition-colors hover:text-foreground"
      >
        <Icon name="account" />
      </Link>
    );
  }

  return (
    <div className="relative" ref={wrapper}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-label={t.menu.aria}
        aria-expanded={open}
        className="flex h-11 w-11 items-center justify-center text-ink-dim transition-colors hover:text-foreground"
      >
        <Icon name="account" />
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-1 w-60 overflow-hidden rounded-[26px] border border-border bg-popover p-2">
          <p className="truncate px-3 pt-2 text-[13px] text-popover-foreground">{user.email}</p>
          <p className="px-3 pb-2 font-mono text-[10px] uppercase tracking-[0.11em] text-ink-dim">
            {role}
          </p>
          <MenuLink to="/account" icon="settings" onNavigate={() => setOpen(false)}>
            {t.menu.settings}
          </MenuLink>
          <MenuLink to="/pro" icon="flyer" onNavigate={() => setOpen(false)}>
            {t.menu.pro}
          </MenuLink>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              void signOut();
            }}
            className="flex w-full items-center gap-2.5 rounded-full px-3 py-2.5 text-left text-[14px] text-popover-foreground transition-colors hover:bg-muted"
          >
            <Icon name="sign-out" className="h-[18px] w-[18px] text-ink-dim" />
            {t.menu.signOut}
          </button>
        </div>
      )}
    </div>
  );
}

function MenuLink({
  to,
  icon,
  onNavigate,
  children,
}: {
  to: string;
  icon: "settings" | "flyer";
  onNavigate: () => void;
  children: React.ReactNode;
}) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      className="flex w-full items-center gap-2.5 rounded-full px-3 py-2.5 text-left text-[14px] text-popover-foreground transition-colors hover:bg-muted"
    >
      <Icon name={icon} className="h-[18px] w-[18px] text-ink-dim" />
      {children}
    </Link>
  );
}
