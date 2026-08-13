import { Card } from "@/components/ui/card";
import { Link } from "react-router-dom";
import { useTranslation } from "@/hooks/useTranslation";

const PromoterAbout = () => {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-accent/20 bg-[hsl(var(--pro-bg))] p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link to="/" className="flex items-end gap-1 hover:opacity-80 transition-opacity">
            <span className="text-xl sm:text-2xl pb-0.5">🫦</span>
            <span className="font-montserrat font-bold text-lg sm:text-xl text-primary">laiive</span>
          </Link>
          <Link to="/promoters" className="flex items-center gap-1 hover:opacity-80 transition-opacity">
            <span className="text-xl font-bold text-foreground">laiive</span>
            <span className="text-xs px-2 py-0.5 bg-accent/20 text-accent rounded-full border border-accent/30">
              PRO
            </span>
          </Link>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-12 space-y-8">
        {/* Hero */}
        <div className="space-y-4">
          <h1 className="font-montserrat font-bold text-2xl md:text-3xl text-[#FF2AA0]">
            {t.about.title}
          </h1>
          <p className="font-ibm-plex text-base md:text-lg font-bold text-[#FF2AA0] leading-relaxed">
            {t.about.subtitle}
          </p>
        </div>

        {/* Content Cards */}
        <div className="space-y-6">
          <Card className="p-6 bg-card border-border">
            <h2 className="font-montserrat font-bold text-2xl mb-4 text-[#FFD500]">
              {t.about.philosophyTitle}
            </h2>
            <p className="font-ibm-plex text-muted-foreground leading-relaxed">
              {t.about.philosophyText}
            </p>
          </Card>

          <Card className="p-6 bg-card border-border">
            <h2 className="font-montserrat font-bold text-2xl mb-4 text-[#FF8C00]">
              {t.about.aiEthicsTitle}
            </h2>
            <p className="font-ibm-plex text-muted-foreground leading-relaxed">
              {t.about.aiEthicsText}
            </p>
          </Card>

          <Card className="p-6 bg-card border-border">
            <h2 className="font-montserrat font-bold text-2xl mb-4 text-[#E72828]">
              {t.about.smallVenuesTitle}
            </h2>
            <p className="font-ibm-plex text-muted-foreground leading-relaxed">
              {t.about.smallVenuesText}
            </p>
          </Card>

          <Card className="p-6 bg-card border-border">
            <h2 className="font-montserrat font-bold text-2xl mb-4 text-accent">
              {t.about.joinTitle}
            </h2>
            <p className="font-ibm-plex text-muted-foreground leading-relaxed mb-6">
              {t.about.joinText}
            </p>

            <h3 className="font-montserrat font-bold text-base mb-4 text-accent">
              {t.about.joinInstructionsTitle}
            </h3>
            <ol className="font-ibm-plex text-muted-foreground leading-relaxed space-y-3">
              <li className="flex gap-2">
                <span className="text-accent font-bold">1.</span>
                <span>{t.about.joinStep1}</span>
              </li>
              <li className="flex gap-2">
                <span className="text-accent font-bold">2.</span>
                <span>{t.about.joinStep2}</span>
              </li>
              <li className="flex gap-2">
                <span className="text-accent font-bold">3.</span>
                <span>
                  {t.about.joinStep3}{" "}
                  <a
                    href="/printable-flyer"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent underline hover:text-accent/80 transition-colors"
                  >
                    {t.about.joinStep3Link}
                  </a>{" "}
                  {t.about.joinStep4}
                </span>
              </li>
            </ol>
          </Card>
        </div>

        {/* Contact */}
        <div className="text-center pt-8">
          <a
            href="mailto:info@laiive.com"
            className="font-ibm-plex text-muted-foreground hover:text-primary transition-colors"
          >
            info@laiive.com
          </a>
        </div>
      </div>
    </div>
  );
};

export default PromoterAbout;
