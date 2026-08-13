import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-3 bg-background">
      <p className="font-montserrat text-2xl font-bold text-primary">404</p>
      <Link to="/" className="font-ibm-plex text-sm text-muted-foreground hover:text-primary">
        back to the chat →
      </Link>
    </div>
  );
}
