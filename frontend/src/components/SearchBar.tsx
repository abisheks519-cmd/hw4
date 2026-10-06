import { useRef, useState, type FormEvent } from "react";
import { useMatch, useNavigate } from "react-router-dom";
import { searchCatalogue } from "../api";
import { useAssistantResults } from "../assistantResults";

const POPULAR = ["T-shirts", "Hoodies", "Quarter-zips", "Gray hoodies", "Hockey", "Under $40"];

// Header search: runs the same catalogue search the chat assistant uses (GET /api/search)
// and shows the matches as product cards at the top of the page.
export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { showResults } = useAssistantResults();
  const navigate = useNavigate();
  const onProductPage = useMatch("/products/:productId");

  const run = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setQuery(q);
    setBusy(true);
    inputRef.current?.blur();
    try {
      const res = await searchCatalogue(q);
      showResults({ source: "search", query: q, title: res.results_title ?? q, products: res.products, total: res.total_matches });
    } catch {
      showResults({ source: "search", query: q, title: q, products: [], error: "We couldn't reach the store. Please try again." });
    } finally {
      setBusy(false);
    }
    // A product page doesn't show results, so go to Products.
    if (onProductPage) navigate("/products", { state: { keepResults: true } });
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(query);
  };

  return (
    <form className="nav-search" role="search" onSubmit={submit}>
      <svg className="nav-search-icon" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
      </svg>
      <input
        ref={inputRef}
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onKeyDown={(e) => e.key === "Escape" && inputRef.current?.blur()}
        placeholder="Search tees, hoodies, colors, teams…"
        aria-label="Search products"
      />
      {busy ? (
        <span className="nav-search-spinner" aria-label="Searching" />
      ) : (
        query && (
          <button type="button" className="nav-search-clear" aria-label="Clear search" onClick={() => { setQuery(""); inputRef.current?.focus(); }}>
            ×
          </button>
        )
      )}
      {focused && !query && (
        <div className="nav-search-popular">
          <span>Popular searches</span>
          <div>
            {POPULAR.map((p) => (
              // onMouseDown so the click lands before the input loses focus and hides this list.
              <button key={p} type="button" onMouseDown={(e) => { e.preventDefault(); run(p); }}>
                {p}
              </button>
            ))}
          </div>
        </div>
      )}
    </form>
  );
}
