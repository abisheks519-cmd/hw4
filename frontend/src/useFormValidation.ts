import { useState } from "react";
import { ApiError, validateFields, type FormName } from "./api";

// Field-by-field checks using the server's validation rules (POST /api/validate/<form>).
// A field is checked when the shopper leaves it; after that it re-checks as they type, so the
// message disappears as soon as it's fixed. The server checks everything again on submit.
export function useFormValidation(form: FormName) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [hints, setHints] = useState<Record<string, string>>({});

  const check = async (field: string, data: Record<string, string>) => {
    try {
      const res = await validateFields(form, data, [field]);
      setErrors((prev) => {
        const next = { ...prev };
        if (res.errors[field]) next[field] = res.errors[field];
        else delete next[field];
        return next;
      });
      setHints((prev) => ({ ...prev, ...res.cleaned }));
    } catch {
      // Can't reach the server: the check on submit will still catch it.
    }
  };

  return {
    errors,
    hints,
    // Call from onBlur.
    blur: (field: string, data: Record<string, string>) => {
      setTouched((prev) => new Set(prev).add(field));
      if (data[field] !== undefined) check(field, data);
    },
    // Call from onChange (only re-checks fields the shopper has already left once).
    change: (field: string, data: Record<string, string>, also: string[] = []) => {
      for (const f of [field, ...also]) if (touched.has(f) || errors[f]) check(f, data);
    },
    // Show the per-field errors the server returned when the form was submitted.
    fromError: (err: unknown) => {
      if (err instanceof ApiError && Object.keys(err.errors).length) {
        setErrors(err.errors);
        setTouched(new Set(Object.keys(err.errors)));
        return true;
      }
      return false;
    },
    clear: () => setErrors({}),
  };
}
