import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useNavigate } from "react-router-dom";
import { Play } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { useAuth } from "@/hooks/useAuth";
import { UserAvatar } from "@/components/UserAvatar";

const Promoters = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user, isPromoter, isLoading } = useAuth();

  const handleCTAClick = () => {
    if (isLoading) return;

    if (user && isPromoter) {
      // Already a promoter, go directly to create
      navigate("/promoters/create");
    } else {
      // Not logged in or not a promoter, go to promoter auth
      navigate("/promoters/auth");
    }
  };

  return (
    <div className="min-h-screen bg-[#1a1a1a]">
      {/* Header */}
      <header className="border-b border-accent/20 bg-[hsl(var(--pro-bg))] p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-end gap-4">
            <div className="flex items-center gap-1">
              <span className="text-xl font-bold text-foreground">laiive</span>
              <span className="text-xs px-2 py-0.5 bg-accent/20 text-accent rounded-full border border-accent/30">
                PRO
              </span>
            </div>
            <button
              onClick={() => navigate("/")}
              className="font-ibm-plex text-[10px] text-muted-foreground hover:text-primary transition-colors pb-0.5 flex items-center gap-0.5"
            >
              <span className="text-[10px]">🫦</span>
              <span>laiive</span>
            </button>
          </div>
          <UserAvatar variant="pro" />
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-12 space-y-12">
        {/* Hero section */}
        <div className="text-center space-y-4">
          <h1 className="font-montserrat font-bold text-4xl md:text-5xl bg-gradient-to-r from-cyan-400 to-cyan-600 bg-clip-text text-transparent">
            {t.promoter.title}
          </h1>
          <p className="font-ibm-plex text-lg text-muted-foreground max-w-2xl mx-auto">
            {t.promoter.subtitle}
          </p>
        </div>

        {/* Video section */}
        <Card className="p-8 bg-[hsl(var(--pro-bg-card))] border-accent/20">
          <div className="aspect-video bg-[#1a1a1a] rounded-lg flex items-center justify-center">
            <div className="text-center space-y-4">
              <div className="w-20 h-20 mx-auto rounded-full bg-cyan-500/10 flex items-center justify-center">
                <Play className="w-10 h-10 text-cyan-400" />
              </div>
              <p className="font-ibm-plex text-muted-foreground">
                {t.promoter.videoPlaceholder}
              </p>
              <p className="font-ibm-plex text-sm text-muted-foreground">
                {t.promoter.videoDescription}
              </p>
            </div>
          </div>
        </Card>

        {/* Primary CTA */}
        <div className="text-center space-y-4">
          <Button
            size="lg"
            onClick={handleCTAClick}
            disabled={isLoading}
            className="text-lg px-8 py-6 h-auto font-montserrat font-bold bg-accent hover:bg-cyan-600 text-accent-foreground"
          >
            {t.promoter.ctaButton}
          </Button>
        </div>

        {/* Contact */}
        <div className="text-center space-y-2">
          <a href="mailto:info@laiive.com" className="font-ibm-plex text-sm text-cyan-400 hover:underline">
            info@laiive.com
          </a>
          <span className="text-muted-foreground mx-2">·</span>
          <button
            onClick={() => navigate("/promoters/about")}
            className="font-ibm-plex text-sm text-muted-foreground hover:text-cyan-400 transition-colors"
          >
            more about laiive →
          </button>
        </div>
      </div>
    </div>
  );
};

export default Promoters;
