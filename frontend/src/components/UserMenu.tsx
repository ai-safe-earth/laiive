import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useProfile } from "@/api/profile";
import { useAuth } from "@/auth/AuthProvider";
import { Avatar } from "@/components/Avatar";
import { Icon, type IconName } from "@/components/Icon";
import { useTranslation } from "@/i18n/useTranslation";
import { cn } from "@/lib/cn";

/**
 * Icons only, no labels — the chrome inventory allows the account icon and
 * nothing beside it. Language and every other preference live in settings,
 * inside this menu, never in the header.
 */
export function UserMenu() {
  const { t } = useTranslation();
  const { user, role, signOut } = useAuth();
  const { data: profile } = useProfile(user?.id);
  const [open, setOpen] = useState(false);
  // Back means back. /account's arrow returns to whatever page opened it, and
  // this menu is the way in from /pro — without telling it where we came from
  // a promoter is returned to the consumer chat, a different product.
  const { pathname } = useLocation();
  const wrapper = useRef<HTMLDivElement>(null);

  // Admin satisfies a pro gate everywhere else in the app; it does here too.
  const isPromoter = role === "pro" || role === "admin";
  const onPromoterSurface = pathname.startsWith("/pro") || pathname.startsWith("/admin");
  // The menu wears the palette of the surface it sits on.
  const pro = onPromoterSurface;

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
        className={cn(
          "flex h-11 w-11 items-center justify-center transition-colors",
          pro ? "text-pro-dim hover:text-pro-fg" : "text-ink-dim hover:text-foreground",
        )}
      >
        <Avatar displayName={profile?.display_name} email={user.email} pro={pro} />
      </button>

      {open && (
        <div
          className={cn(
            "absolute right-0 z-20 mt-1 w-60 overflow-hidden rounded-[26px] border p-2",
            pro ? "border-pro-border bg-pro-elevated" : "border-border bg-popover",
          )}
        >
          <div className="flex items-center gap-2.5 px-3 pb-2 pt-2">
            <Avatar displayName={profile?.display_name} email={user.email} pro={pro} />
            <div className="min-w-0">
              <p className={cn("truncate text-md", pro ? "text-pro-fg" : "text-popover-foreground")}>
                {user.email}
              </p>
              <p
                className={cn(
                  "font-mono text-2xs uppercase tracking-[0.11em]",
                  pro ? "text-pro-dim" : "text-ink-dim",
                )}
              >
                {role}
              </p>
            </div>
          </div>
          <MenuLink
            to="/account"
            icon="settings"
            pro={pro}
            state={{ from: pathname }}
            onNavigate={() => setOpen(false)}
          >
            {t.menu.settings}
          </MenuLink>
          {/* The two surfaces are linked from here and nowhere else — a logo
              that navigates to a different product is a door nobody means to
              open. Only a promoter sees either: to somebody who is not one,
              /pro is a refusal screen, and the ways to become one are on
              /account and the promoter door at /auth?kind=pro. */}
          {isPromoter && !onPromoterSurface && (
            <MenuLink to="/pro" icon="flyer" pro={pro} onNavigate={() => setOpen(false)}>
              {t.menu.pro}
            </MenuLink>
          )}
          {isPromoter && onPromoterSurface && (
            <>
              {/* The organisation screen has no other way in from the chat. */}
              <MenuLink to="/pro/org" icon="saved" pro={pro} onNavigate={() => setOpen(false)}>
                {t.org.title}
              </MenuLink>
              <MenuLink to="/" icon="back" pro={pro} onNavigate={() => setOpen(false)}>
                {t.menu.toLaiive}
              </MenuLink>
            </>
          )}
          {/* Untranslated on purpose — the admin surface behind it is
              English-only, and a translated door onto an English room is worse
              than neither. */}
          {role === "admin" && (
            <MenuLink to="/admin" icon="saved" pro={pro} onNavigate={() => setOpen(false)}>
              Admin
            </MenuLink>
          )}
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              void signOut();
            }}
            className={cn(ITEM, pro ? ITEM_PRO : ITEM_CONSUMER)}
          >
            <Icon name="sign-out" className={cn("h-[18px] w-[18px]", pro ? "text-pro-dim" : "text-ink-dim")} />
            {t.menu.signOut}
          </button>
        </div>
      )}
    </div>
  );
}

const ITEM = "flex w-full items-center gap-2.5 rounded-full px-3 py-2.5 text-left text-base transition-colors";
const ITEM_CONSUMER = "text-popover-foreground hover:bg-muted";
const ITEM_PRO = "text-pro-fg hover:bg-pro-control";

function MenuLink({
  to,
  icon,
  pro,
  state,
  onNavigate,
  children,
}: {
  to: string;
  icon: IconName;
  pro: boolean;
  state?: { from: string };
  onNavigate: () => void;
  children: React.ReactNode;
}) {
  return (
    <Link
      to={to}
      state={state}
      onClick={onNavigate}
      className={cn(ITEM, pro ? ITEM_PRO : ITEM_CONSUMER)}
    >
      <Icon name={icon} className={cn("h-[18px] w-[18px]", pro ? "text-pro-dim" : "text-ink-dim")} />
      {children}
    </Link>
  );
}
