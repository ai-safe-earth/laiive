// laiive · live accents. Mounted ONCE at the app root (App.tsx).
// Writes each .live-accent's viewport position into --hx / --hy so all holes
// sample one shared, viewport-fixed world. Batched to one rAF per frame.
// Not `background-attachment: fixed`, which would need no script: iOS Safari
// ignores it, and the chat is a phone app first.
import { useEffect } from "react";

export function useLiveAccents() {
  useEffect(() => {
    let raf = 0;
    const sync = () => {
      raf = 0;
      // Every read before any write: a write between two reads would make the
      // second read recompute style, once per accent.
      const holes = [...document.querySelectorAll<HTMLElement>(".live-accent")].map(
        (el) => [el, el.getBoundingClientRect()] as const,
      );
      for (const [el, r] of holes) {
        const hx = `${r.left}px`;
        const hy = `${r.top}px`;
        // Unchanged positions are left alone, so a streaming reply that moves
        // nothing costs no restyle.
        if (el.style.getPropertyValue("--hx") !== hx) el.style.setProperty("--hx", hx);
        if (el.style.getPropertyValue("--hy") !== hy) el.style.setProperty("--hy", hy);
      }
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
