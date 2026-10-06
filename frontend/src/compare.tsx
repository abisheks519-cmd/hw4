import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export const MAX_COMPARE = 4;
const STORAGE_KEY = "campus-customs-compare";

// Products picked for side-by-side comparison (ids only), remembered in this browser.
interface CompareValue {
  ids: string[];
  has: (id: string) => boolean;
  toggle: (id: string) => boolean; // false when the list is already full
  remove: (id: string) => void;
  clear: () => void;
  full: boolean;
}

const CompareContext = createContext<CompareValue | null>(null);

function load(): string[] {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(saved) ? saved.filter((x) => typeof x === "string").slice(0, MAX_COMPARE) : [];
  } catch {
    return [];
  }
}

export function CompareProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<string[]>(load);
  useEffect(() => localStorage.setItem(STORAGE_KEY, JSON.stringify(ids)), [ids]);

  const value: CompareValue = {
    ids,
    has: (id) => ids.includes(id),
    toggle: (id) => {
      if (ids.includes(id)) {
        setIds(ids.filter((x) => x !== id));
        return true;
      }
      if (ids.length >= MAX_COMPARE) return false;
      setIds([...ids, id]);
      return true;
    },
    remove: (id) => setIds((prev) => prev.filter((x) => x !== id)),
    clear: () => setIds([]),
    full: ids.length >= MAX_COMPARE,
  };
  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}

export function useCompare(): CompareValue {
  const ctx = useContext(CompareContext);
  if (!ctx) throw new Error("useCompare must be used within a CompareProvider");
  return ctx;
}
