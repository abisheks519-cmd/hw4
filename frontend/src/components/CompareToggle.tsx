import { useState } from "react";
import { MAX_COMPARE, useCompare } from "../compare";

// "Compare" checkbox-style button for a product card or product page.
export default function CompareToggle({ productId, variant = "card" }: { productId: string; variant?: "card" | "detail" }) {
  const compare = useCompare();
  const [full, setFull] = useState(false);
  const on = compare.has(productId);

  const click = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const ok = compare.toggle(productId);
    setFull(!ok);
    if (!ok) setTimeout(() => setFull(false), 2200);
  };

  return (
    <button
      type="button"
      className={`compare-toggle ${variant} ${on ? "on" : ""}`}
      onClick={click}
      aria-pressed={on}
      title={on ? "Remove from compare" : "Add to compare"}
    >
      <span className="compare-box" aria-hidden="true">{on ? "✓" : ""}</span>
      {full ? `Compare holds ${MAX_COMPARE}` : on ? "Comparing" : "Compare"}
    </button>
  );
}
