import { Link } from "react-router-dom";
import { Mark } from "@/components/Mark";
import { useTranslation } from "@/i18n/useTranslation";

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-5 bg-background p-6">
      <Mark size={30} />
      <p className="font-bebas text-[54px] leading-none tracking-[0.04em] text-foreground/[0.14]">
        404
      </p>
      <Link
        to="/"
        className="inline-flex min-h-11 items-center text-md text-muted-foreground transition-colors hover:text-foreground"
      >
        {t.notFound.back}
      </Link>
    </div>
  );
}
