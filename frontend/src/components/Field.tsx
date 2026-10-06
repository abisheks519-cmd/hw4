import type { InputHTMLAttributes, ReactNode } from "react";

// A labelled input with its validation message underneath.
export default function Field({
  label,
  error,
  hint,
  className = "",
  children,
  ...input
}: { label: string; error?: string; hint?: ReactNode; children?: ReactNode } & InputHTMLAttributes<HTMLInputElement>) {
  const id = `f-${input.name}`;
  return (
    <label className={`field ${error ? "has-error" : ""} ${className}`} htmlFor={id}>
      <span className="field-label">{label}</span>
      <span className="field-control">
        <input id={id} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-err` : undefined} {...input} />
        {children}
      </span>
      {error ? (
        <span className="field-error" id={`${id}-err`} role="alert">
          {error}
        </span>
      ) : (
        hint && <span className="field-hint">{hint}</span>
      )}
    </label>
  );
}
