import { Link } from "react-router-dom";
import { useTranslation } from "@/i18n/useTranslation";

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-3 bg-background">
      <p className="font-montserrat text-2xl font-bold text-primary">404</p>
      <Link to="/" className="font-ibm-plex text-sm text-muted-foreground hover:text-primary">
        {t.notFound.back}
      </Link>
    </div>
  );
}
