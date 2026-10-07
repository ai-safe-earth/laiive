// laiive · live accents — reference hook. Mount ONCE at the app root (App.tsx).
// Writes each .live-accent's viewport position into --hx / --hy so all holes
// sample one shared, viewport-fixed world. Batched to one rAF per frame.
import { useEffect } from "react";

export function useLiveAccents() {
  useEffect(() => {
    let raf = 0;
    const sync = () => {
      raf = 0;
      document.querySelectorAll<HTMLElement>(".live-accent").forEach((el) => {
        const r = el.getBoundingClientRect();
        el.style.setProperty("--hx", `${r.left}px`);
        el.style.setProperty("--hy", `${r.top}px`);
      });
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(sync); };

    schedule();
    const mo = new MutationObserver(schedule); // new messages, sheets, route changes
    mo.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
    const ro = new ResizeObserver(schedule);
    ro.observe(document.documentElement);
    window.addEventListener("scroll", schedule, { capture: true, passive: true });
    window.addEventListener("resize", schedule);
    document.addEventListener("transitionend", schedule, true);
    document.addEventListener("animationend", schedule, true);
    document.fonts?.ready.then(schedule);

    return () => {
      cancelAnimationFrame(raf);
      mo.disconnect();
      ro.disconnect();
      window.removeEventListener("scroll", schedule, { capture: true } as EventListenerOptions);
      window.removeEventListener("resize", schedule);
      document.removeEventListener("transitionend", schedule, true);
      document.removeEventListener("animationend", schedule, true);
    };
  }, []);
}
