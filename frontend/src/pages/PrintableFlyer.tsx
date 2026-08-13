import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Printer, Download, Share2, ChevronDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type ColorTheme = 'fuchsia' | 'cyan' | 'yellow' | 'orange';

const colorThemes: Record<ColorTheme, { bg: string; primary: string; accent: string; text: string; selectorBg: string }> = {
  fuchsia: { bg: '#0a0a0a', primary: '#FF2AA0', accent: '#00CFEA', text: '#ffffff', selectorBg: '#FF2AA0' },
  cyan: { bg: '#0a0a0a', primary: '#00CFEA', accent: '#FF2AA0', text: '#ffffff', selectorBg: '#00CFEA' },
  yellow: { bg: '#0a0a0a', primary: '#FFD500', accent: '#FF8C00', text: '#ffffff', selectorBg: '#FFD500' },
  orange: { bg: '#0a0a0a', primary: '#FF8C00', accent: '#FFD500', text: '#ffffff', selectorBg: '#FF8C00' },
};

const PrintableFlyer = () => {
  const flyerRef = useRef<HTMLDivElement>(null);
  const [colorTheme, setColorTheme] = useState<ColorTheme>('fuchsia');

  const theme = colorThemes[colorTheme];

  const handlePrint = () => {
    window.print();
  };

  const handleDownload = async (format: 'png' | 'jpg' | 'svg') => {
    const svgContent = generateSvg(format === 'svg' ? 400 : 800, format === 'svg' ? 600 : 1200);

    if (format === 'svg') {
      const blob = new Blob([svgContent], { type: 'image/svg+xml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `laiive-flyer.svg`;
      a.click();
      URL.revokeObjectURL(url);
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = 800;
    canvas.height = 1200;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    const svgBlob = new Blob([svgContent], { type: 'image/svg+xml' });
    const svgUrl = URL.createObjectURL(svgBlob);

    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      const mimeType = format === 'png' ? 'image/png' : 'image/jpeg';
      const quality = format === 'jpg' ? 0.95 : undefined;

      canvas.toBlob((blob) => {
        if (blob) {
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `laiive-flyer.${format}`;
          a.click();
          URL.revokeObjectURL(url);
        }
      }, mimeType, quality);

      URL.revokeObjectURL(svgUrl);
    };

    img.src = svgUrl;
  };

  const handleShare = async (platform?: string) => {
    const shareUrl = 'https://laiive.com';
    const shareText = 'Discover live music in your neighborhood with laiive';

    if (!platform && navigator.share) {
      try {
        await navigator.share({
          title: 'laiive - Discover live music',
          text: shareText,
          url: shareUrl,
        });
        return;
      } catch (err) {
        // User cancelled
      }
    }

    const shareUrls: Record<string, string> = {
      twitter: `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`,
      facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`,
      whatsapp: `https://wa.me/?text=${encodeURIComponent(shareText + ' ' + shareUrl)}`,
      linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`,
      copy: '',
    };

    if (platform === 'copy') {
      await navigator.clipboard.writeText(shareUrl);
      alert('Link copied!');
      return;
    }

    if (platform && shareUrls[platform]) {
      window.open(shareUrls[platform], '_blank', 'width=600,height=400');
    }
  };

  const generateSvg = (width: number, height: number) => `
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 400 600">
  <rect width="400" height="600" fill="${theme.bg}"/>
  <text x="200" y="80" text-anchor="middle" font-family="Arial, sans-serif" font-size="48" fill="${theme.primary}" font-weight="bold">🫦 laiive</text>
  <text x="200" y="260" text-anchor="middle" font-family="Arial, sans-serif" font-size="36" fill="${theme.text}" font-weight="bold">Discover live music</text>
  <text x="200" y="310" text-anchor="middle" font-family="Arial, sans-serif" font-size="36" fill="${theme.accent}" font-weight="bold">in your neighborhood</text>
  <rect x="100" y="360" width="200" height="200" fill="white" rx="12"/>
  <image x="115" y="375" width="170" height="170" href="https://api.qrserver.com/v1/create-qr-code/?size=200x200&amp;data=https://laiive.com&amp;color=000000"/>
  <text x="200" y="595" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" fill="${theme.primary}" font-weight="bold">laiive.com</text>
</svg>`;

  const qrCodeUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https://laiive.com&color=000000`;

  return (
    <div className="min-h-screen bg-background">
      {/* Print Controls - Hidden when printing */}
      <div className="print:hidden fixed top-4 right-4 flex gap-2 z-50">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                className="bg-primary hover:bg-primary/90"
                onClick={handlePrint}
              >
                <Printer className="w-4 h-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Print</TooltipContent>
          </Tooltip>

          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <Button size="icon" variant="outline" className="border-border">
                    <Download className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent>Download</TooltipContent>
            </Tooltip>
            <DropdownMenuContent align="end" className="bg-card border-border">
              <DropdownMenuLabel className="text-xs text-muted-foreground">Format</DropdownMenuLabel>
              <DropdownMenuItem onClick={() => handleDownload('png')}>
                PNG (High Quality)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleDownload('jpg')}>
                JPG (Smaller File)
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => handleDownload('svg')}>
                SVG (Vector)
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <Button size="icon" variant="outline" className="border-border">
                    <Share2 className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent>Share</TooltipContent>
            </Tooltip>
            <DropdownMenuContent align="end" className="bg-card border-border">
              <DropdownMenuItem onClick={() => handleShare('twitter')}>
                Twitter / X
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleShare('facebook')}>
                Facebook
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleShare('whatsapp')}>
                WhatsApp
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleShare('linkedin')}>
                LinkedIn
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => handleShare('copy')}>
                Copy link
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </TooltipProvider>
      </div>

      {/* Back link - Hidden when printing */}
      <div className="print:hidden p-4">
        <a href="/promoters/about" className="text-muted-foreground hover:text-foreground transition-colors">
          ← back
        </a>
      </div>

      {/* Flyer Content */}
      <div
        ref={flyerRef}
        className="max-w-lg mx-auto p-4 print:p-0 print:max-w-full print:mx-0 relative"
        style={{ backgroundColor: theme.bg }}
      >
        {/* Color Theme Selector - 4 balls */}
        <div className="print:hidden absolute top-2 left-1/2 -translate-x-1/2 flex gap-3 z-10">
          {(Object.keys(colorThemes) as ColorTheme[]).map((key) => (
            <button
              key={key}
              onClick={() => setColorTheme(key)}
              className={`w-6 h-6 rounded-full transition-all duration-200 hover:scale-110 border border-white/20 ${
                colorTheme === key ? 'ring-2 ring-white ring-offset-2 scale-110' : ''
              }`}
              style={{ backgroundColor: colorThemes[key].selectorBg }}
              aria-label={`${key} theme`}
            />
          ))}
        </div>

        <div
          className="flyer-content aspect-[2/3] flex flex-col items-center justify-between py-12 px-6 print:py-16 print:px-8 border border-border print:border-none"
          style={{ backgroundColor: theme.bg, color: theme.text }}
        >
          {/* Top Section - Logo */}
          <div className="text-center">
            <div className="flex items-end justify-center gap-2">
              <span className="text-6xl pb-1">🫦</span>
              <span
                className="font-montserrat font-bold text-6xl"
                style={{ color: theme.primary }}
              >
                laiive
              </span>
            </div>
          </div>

          {/* Middle Section - Main Message */}
          <div className="text-center space-y-2 flex-1 flex flex-col justify-center">
            <h1 className="font-montserrat font-bold text-4xl md:text-5xl leading-tight">
              Discover live music
              <br />
              <span style={{ color: theme.accent }}>in your neighborhood</span>
            </h1>
          </div>

          {/* QR Code Section */}
          <div className="text-center space-y-4">
            <div className="bg-white p-4 rounded-xl inline-block">
              <img
                src={qrCodeUrl}
                alt="Scan to visit laiive"
                className="w-44 h-44 md:w-52 md:h-52"
              />
            </div>
            <p
              className="font-montserrat font-bold text-2xl"
              style={{ color: theme.primary }}
            >
              laiive.com
            </p>
          </div>
        </div>
      </div>

      {/* Print Styles */}
      <style>{`
        @media print {
          @page {
            size: A4 portrait;
            margin: 0;
          }
          body {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
          }
          .print\\:hidden {
            display: none !important;
          }
          .flyer-content {
            width: 100vw;
            height: 100vh;
            max-width: none;
            aspect-ratio: auto;
          }
        }
      `}</style>
    </div>
  );
};

export default PrintableFlyer;
