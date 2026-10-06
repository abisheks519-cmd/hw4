import { useEffect, useRef, useState, type RefObject } from "react";
import { flushSync } from "react-dom";
import { useLocation, type NavigateFunction } from "react-router-dom";

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Fade-and-rise on scroll: any element with a data-reveal attribute animates in the first time
// it enters the screen. One observer for the whole site; new elements (e.g. product grids that
// load later) are picked up automatically.
export function useRevealOnScroll() {
  const { pathname } = useLocation();
  useEffect(() => {
    const show = (el: Element) => el.classList.add("is-in");
    if (prefersReducedMotion() || !("IntersectionObserver" in window)) {
      document.querySelectorAll("[data-reveal]").forEach(show);
    }
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && (show(e.target), io.unobserve(e.target))),
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 },
    );
    const scan = () => document.querySelectorAll("[data-reveal]:not(.is-in)").forEach((el) => io.observe(el));
    scan();
    const mo = new MutationObserver(scan);
    mo.observe(document.body, { childList: true, subtree: true });
    return () => {
      io.disconnect();
      mo.disconnect();
    };
  }, [pathname]);
}

// 0 → 1 as an element scrolls through the screen (0 when its top reaches the bottom of the
// screen, 1 when its bottom reaches the top). Written to a CSS variable (--p) so styles can
// move, scale, or fade things with it, without re-rendering React on every scroll.
// "pinned" mode is for a tall section with a sticky inside: 0 when it reaches the top of the
// screen, 1 when its last screenful has scrolled past.
export function useScrollProgress<T extends HTMLElement>(
  ref: RefObject<T | null>,
  onChange?: (p: number) => void,
  mode: "through" | "pinned" = "through",
) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const r = el.getBoundingClientRect();
      const raw =
        mode === "pinned"
          ? -r.top / Math.max(1, r.height - window.innerHeight)
          : (window.innerHeight - r.top) / (r.height + window.innerHeight);
      const p = Math.min(1, Math.max(0, raw));
      el.style.setProperty("--p", p.toFixed(4));
      onChange?.(p);
    };
    const onScroll = () => (frame ||= requestAnimationFrame(update));
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(frame);
    };
  }, [ref]);
}

// Pointer position over an element as --mx / --my (-1 → 1), for parallax and spotlight glows.
export function usePointerVars<T extends HTMLElement>(ref: RefObject<T | null>) {
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || window.matchMedia("(hover: none)").matches) return;
    let frame = 0;
    const move = (e: PointerEvent) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const r = el.getBoundingClientRect();
        el.style.setProperty("--mx", (((e.clientX - r.left) / r.width) * 2 - 1).toFixed(3));
        el.style.setProperty("--my", (((e.clientY - r.top) / r.height) * 2 - 1).toFixed(3));
      });
    };
    el.addEventListener("pointermove", move);
    return () => el.removeEventListener("pointermove", move);
  }, [ref]);
}

// A number that counts up the first time it scrolls into view.
export function CountUp({ to, prefix = "", suffix = "", duration = 1400 }: { to: number; prefix?: string; suffix?: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [value, setValue] = useState(prefersReducedMotion() ? to : 0);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return setValue(to);
    const io = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      io.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / duration);
        setValue(Math.round(to * (1 - Math.pow(1 - t, 3))));
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    io.observe(el);
    return () => io.disconnect();
  }, [to]);
  return (
    <span ref={ref}>
      {prefix}
      {value.toLocaleString("en-US")}
      {suffix}
    </span>
  );
}

// Opening a product from a card: the card's photo glides into place as the product page's big
// photo (a "view transition", supported in Chrome, Edge, and Safari). Other browsers, or
// shoppers who prefer reduced motion, get a normal page change.
export function openProductWithMorph(
  e: React.MouseEvent<HTMLAnchorElement>,
  navigate: NavigateFunction,
  to: string,
  state?: unknown,
) {
  const doc = document as Document & { startViewTransition?: (cb: () => Promise<void>) => unknown };
  if (!doc.startViewTransition || prefersReducedMotion() || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  const img = e.currentTarget.querySelector<HTMLImageElement>("[data-morph]");
  if (img) img.style.viewTransitionName = "product-hero";
  document.documentElement.classList.add("vt-active");
  const done = doc.startViewTransition(async () => {
    flushSync(() => navigate(to, { state }));
    if (img) img.style.viewTransitionName = "";
    window.scrollTo(0, 0);
    await waitForHeroImage();
  }) as { finished?: Promise<void> };
  const cleanup = () => document.documentElement.classList.remove("vt-active");
  done.finished ? done.finished.finally(cleanup) : setTimeout(cleanup, 600);
}

function waitForHeroImage(): Promise<void> {
  return new Promise((resolve) => {
    const img = document.querySelector<HTMLImageElement>(".detail-stage img");
    if (!img || img.complete) return resolve();
    const finish = () => resolve();
    img.addEventListener("load", finish, { once: true });
    img.addEventListener("error", finish, { once: true });
    setTimeout(finish, 350);
  });
}
