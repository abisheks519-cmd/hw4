// − 2 + control for a cart line. Limited to what's in stock (and 10 per size).
export default function QuantityStepper({
  value,
  max,
  onChange,
  disabled,
}: {
  value: number;
  max: number;
  onChange: (next: number) => void;
  disabled?: boolean;
}) {
  const cap = Math.min(max, 10);
  return (
    <div className="qty">
      <button type="button" aria-label="Decrease quantity" disabled={disabled || value <= 1} onClick={() => onChange(value - 1)}>
        −
      </button>
      <span aria-live="polite">{value}</span>
      <button type="button" aria-label="Increase quantity" disabled={disabled || value >= cap} onClick={() => onChange(value + 1)}>
        +
      </button>
    </div>
  );
}
