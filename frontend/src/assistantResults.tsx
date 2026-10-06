import { createContext, useContext, useLayoutEffect, useState, type ReactNode } from "react";
import { useLocation, useNavigationType } from "react-router-dom";
import type { Product } from "./api";

export interface ResultSet {
  id: number; // changes on every new set, so the page re-animates and scrolls to it
  source: "assistant" | "search"; // the chat assistant or the header search bar
  title: string;
  products: Product[];
  query?: string; // what was typed in the search bar
  total?: number; // total matches, when more were found than are shown
  error?: string; // the search couldn't reach the store
}

type NewResults = Omit<ResultSet, "id">;

interface ResultsValue {
  results: ResultSet | null;
  showResults: (results: NewResults) => void;
  clearResults: () => void;
}

const ResultsContext = createContext<ResultsValue | null>(null);

// Holds the latest product matches (from the chat assistant or the search bar), so any page can show them.
export function AssistantResultsProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<ResultSet | null>(null);
  const location = useLocation();
  const navigationType = useNavigationType();

  // Results stay while the shopper works with them: opening a product, coming back with the
  // browser's Back button, or a link marked keepResults (the "Back to results" link, or a new
  // search/chat question from a product page). Any other navigation, like the navbar tabs,
  // clears them so the page the shopper picked isn't hidden under old results.
  useLayoutEffect(() => {
    const onProductPage = location.pathname.startsWith("/products/");
    const keep = (location.state as { keepResults?: boolean } | null)?.keepResults;
    if (!onProductPage && !keep && navigationType !== "POP") setResults(null);
  }, [location.key]);
  const value: ResultsValue = {
    results,
    showResults: (next) => setResults((prev) => ({ ...next, id: (prev?.id ?? 0) + 1 })),
    clearResults: () => setResults(null),
  };
  return <ResultsContext.Provider value={value}>{children}</ResultsContext.Provider>;
}

export function useAssistantResults(): ResultsValue {
  const ctx = useContext(ResultsContext);
  if (!ctx) throw new Error("useAssistantResults must be used within an AssistantResultsProvider");
  return ctx;
}

// Product links carry the page the shopper came from, so a product page can link back to it.
// Moving from one product page to another keeps the original page.
export function useReturnState(): { from?: string } | undefined {
  const location = useLocation();
  if (location.pathname.startsWith("/products/")) return (location.state as { from?: string } | null) ?? undefined;
  return { from: location.pathname + location.search };
}
