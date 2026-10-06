import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import ProductCard from "../components/ProductCard";
import { formatPrice, type Product } from "../api";
import { openChat } from "../chatHistory";
import { CountUp, usePointerVars, useScrollProgress } from "../motion";
import { useProducts } from "../useProducts";

const HERO = { main: "champion-reverse-weave-hoodie-1", left: "poly-twill-crewneck-arched-yale", right: "big-yale-tri-blend-t-shirt" };
const TILES = [
  { id: "district-vit-hoodie-vintage-bulldog", category: "Hoodies", title: "Hoodies.", line: "Built for late nights and early lectures.", tone: "light" },
  { id: "2025-yale-vs-harvard-t-shirt", category: "T-Shirts", title: "Game Day.", line: "Show up for The Game in style.", tone: "dark" },
  { id: "benjamin-franklin-1-4-zip", category: "Quarter-Zips", title: "Quarter-Zips.", line: "Sharp enough for class. Cozy enough for the library.", tone: "blue" },
  { id: "t-felt-y-heavyweight", category: "T-Shirts", title: "Everyday tees.", line: "Soft, simple, and easy to wear on repeat.", tone: "cream" },
];
const STORY = [
  { id: "berkeley-1-4-zip", time: "8:00 AM", title: "Morning lecture.", line: "A quarter-zip that looks polished and feels like a sweatshirt." },
  { id: "tri-blend-sports-football-t-shirt", time: "1:00 PM", title: "Game day.", line: "A soft tri-blend tee that's ready for the stands." },
  { id: "district-vit-hoodie-vintage-sailor-bulldog", time: "11:00 PM", title: "Late-night library.", line: "A hoodie you'll live in until finals are over." },
];
const CATEGORY_ORDER = ["Hoodies", "Crewnecks & Sweatshirts", "T-Shirts", "Quarter-Zips", "Jackets", "Long Sleeves"];
const CATEGORY_PICK: Record<string, string> = {
  Hoodies: "yale-sports-hoodie-hockey",
  "Crewnecks & Sweatshirts": "hype-and-vice-yale-university-premium-crewneck",
  "T-Shirts": "yale-bowl-t-shirt",
  "Quarter-Zips": "school-of-engineering-1-4-zip",
  Jackets: "brooks-brothers-bomber-jacket-yale",
  "Long Sleeves": "ua-mens-tech-l-s-2-0",
};
const MARQUEE = ["Hoodies", "Crewnecks", "Tees", "Quarter-Zips", "Jackets", "Long Sleeves", "Game Day"];

const art = (p?: Product) => (p ? p.cutout_url ?? p.image_url : undefined);
const fromPrice = (items: Product[]) => (items.length ? Math.min(...items.map((p) => p.price)) : null);

export default function Home() {
  const { products, error } = useProducts();
  const byId = (id: string) => products.find((p) => p.product_id === id);
  const inCategory = (c: string) => products.filter((p) => p.category === c);

  return (
    <div className="home">
      <Hero main={byId(HERO.main)} left={byId(HERO.left)} right={byId(HERO.right)} />

      <div className="marquee" aria-hidden="true">
        <div className="marquee-track">
          {[0, 1].map((n) => (
            <span key={n}>
              {MARQUEE.map((w) => (
                <em key={w}>
                  {w} <b>✦</b>{" "}
                </em>
              ))}
            </span>
          ))}
        </div>
      </div>

      {error && <div className="container"><div className="alert">{error}</div></div>}

      <section className="tiles container">
        {TILES.map((t, i) => {
          const p = byId(t.id);
          const from = fromPrice(inCategory(t.category));
          return (
            <article key={t.id} className={`tile tile-${t.tone}`} data-reveal style={{ ["--d" as string]: `${(i % 2) * 90}ms` }}>
              <div className="tile-copy">
                <h2>{t.title}</h2>
                <p>{t.line}</p>
                {from !== null && <span className="tile-price">From {formatPrice(from)}</span>}
                <div className="tile-actions">
                  <Link to={`/products?category=${encodeURIComponent(t.category)}`} className="btn btn-primary small">
                    Shop {t.category}
                  </Link>
                  {p && (
                    <Link to={`/products/${p.product_id}`} className="link-arrow">
                      See this one ›
                    </Link>
                  )}
                </div>
              </div>
              {p && <img className="tile-art" src={art(p)} alt={p.name} loading="lazy" />}
            </article>
          );
        })}
      </section>

      <Story items={STORY.map((s) => ({ ...s, product: byId(s.id) }))} />

      <ReadyToShip products={[...products].filter((p) => p.total_stock > 0).sort((a, b) => b.total_stock - a.total_stock).slice(0, 10)} />

      <section className="stats">
        <div className="container stats-grid">
          <div data-reveal>
            <strong><CountUp to={products.length || 102} /></strong>
            <span>styles in the collection</span>
          </div>
          <div data-reveal style={{ ["--d" as string]: "80ms" }}>
            <strong><CountUp to={CATEGORY_ORDER.length} /></strong>
            <span>categories, from tees to jackets</span>
          </div>
          <div data-reveal style={{ ["--d" as string]: "160ms" }}>
            <strong>XS–XXL</strong>
            <span>sizes for everyone</span>
          </div>
          <div data-reveal style={{ ["--d" as string]: "240ms" }}>
            <strong><CountUp to={fromPrice(products) ?? 32} prefix="$" /></strong>
            <span>starting price</span>
          </div>
          <div data-reveal style={{ ["--d" as string]: "320ms" }}>
            <strong><CountUp to={75} prefix="$" /></strong>
            <span>for free shipping</span>
          </div>
        </div>
      </section>

      <section className="container section bento-section">
        <div className="section-head" data-reveal>
          <div>
            <span className="eyebrow">The lineup</span>
            <h2 className="display">Find your fit.</h2>
          </div>
          <Link to="/products" className="link-arrow">Shop everything ›</Link>
        </div>
        <div className="bento">
          {CATEGORY_ORDER.map((c, i) => {
            const items = inCategory(c);
            const p = byId(CATEGORY_PICK[c]) ?? items[0];
            return (
              <Link key={c} to={`/products?category=${encodeURIComponent(c)}`} className={`bento-tile b${i}`} data-reveal style={{ ["--d" as string]: `${i * 60}ms` }}>
                <div>
                  <strong>{c}</strong>
                  <span>{items.length} styles{fromPrice(items) !== null && ` · from ${formatPrice(fromPrice(items)!)}`}</span>
                </div>
                {p && <img src={p.cutout_thumb_url ?? p.thumb_url} alt="" loading="lazy" />}
                <span className="bento-go" aria-hidden="true">→</span>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="container section perks-v2">
        <div className="perk" data-reveal>
          <span className="perk-emoji">💬</span>
          <h3>Ask anything.</h3>
          <p>Sizes, stock, and prices, answered straight from our live catalogue.</p>
          <button className="link-arrow" onClick={openChat}>Chat with our assistant ›</button>
        </div>
        <div className="perk" data-reveal style={{ ["--d" as string]: "90ms" }}>
          <span className="perk-emoji">⚖️</span>
          <h3>Compare side by side.</h3>
          <p>Price, colors, material, and sizes for up to four items at once.</p>
          <Link to="/products" className="link-arrow">Pick items to compare ›</Link>
        </div>
        <div className="perk" data-reveal style={{ ["--d" as string]: "180ms" }}>
          <span className="perk-emoji">🛍️</span>
          <h3>Your cart, saved.</h3>
          <p>Log in and your cart follows you to any device.</p>
          <Link to="/create-account" className="link-arrow">Create an account ›</Link>
        </div>
      </section>

      <section className="finale">
        <div className="container" data-reveal>
          <h2>
            Your new favorite <em>is in here.</em>
          </h2>
          <p>High quality campus apparel at prices that work for students.</p>
          <Link to="/products" className="btn btn-light">
            Shop all {products.length || 102} styles
          </Link>
        </div>
      </section>
    </div>
  );
}

function Hero({ main, left, right }: { main?: Product; left?: Product; right?: Product }) {
  const ref = useRef<HTMLElement>(null);
  usePointerVars(ref);
  useScrollProgress(ref);
  return (
    <section ref={ref} className="hero">
      <div className="hero-glow" aria-hidden="true" />
      <div className="hero-inner">
        <div className="hero-copy">
          <span className="hero-eyebrow">Welcome to Campus Customs</span>
          <h1>
            <span>Campus pride.</span>
            <br />
            <span><em>Made to wear.</em></span>
          </h1>
          <p>We value our customers and provide high quality merchandise at affordable costs.</p>
          <div className="hero-actions">
            <Link to="/products" className="btn btn-light">
              Shop the collection
            </Link>
            <Link to="/about" className="hero-link">
              Our story ›
            </Link>
          </div>
        </div>
        <div className="hero-stage" aria-hidden={!main}>
          <div className="hero-ring" />
          {left && <img className="hero-item left" src={art(left)} alt="" />}
          {right && <img className="hero-item right" src={art(right)} alt="" />}
          {main && (
            <Link to={`/products/${main.product_id}`} className="hero-main">
              <img src={art(main)} alt={main.name} />
            </Link>
          )}
          {main && (
            <Link to={`/products/${main.product_id}`} className="hero-tag">
              <span>{main.name}</span>
              <strong>{formatPrice(main.price)}</strong>
            </Link>
          )}
        </div>
      </div>
      <div className="hero-scroll" aria-hidden="true">
        <span />
      </div>
    </section>
  );
}

// A tall section that pins in place while the shopper scrolls through three moments of the day;
// the product and the words change with the scroll.
function Story({ items }: { items: (typeof STORY[number] & { product?: Product })[] }) {
  const ref = useRef<HTMLElement>(null);
  const [step, setStep] = useState(0);
  useScrollProgress(ref, (p) => setStep(Math.min(items.length - 1, Math.floor(p * items.length))), "pinned");
  return (
    <section ref={ref} className="story" style={{ ["--steps" as string]: items.length }}>
      <div className="story-pin">
        <div className="container story-inner">
          <div className="story-copy">
            <span className="eyebrow light">A day on campus</span>
            <h2 className="display">Made for every moment.</h2>
            <ol>
              {items.map((s, i) => (
                <li key={s.id} className={i === step ? "on" : i < step ? "past" : ""}>
                  <span className="story-time">{s.time}</span>
                  <strong>{s.title}</strong>
                  <p>{s.line}</p>
                  {s.product && (
                    <Link to={`/products/${s.product.product_id}`} className="story-link">
                      {s.product.name} · {formatPrice(s.product.price)} ›
                    </Link>
                  )}
                </li>
              ))}
            </ol>
          </div>
          <div className="story-stage">
            {items.map((s, i) =>
              s.product ? (
                <img key={s.id} src={art(s.product)} alt={i === step ? s.product.name : ""} className={i === step ? "on" : i < step ? "past" : ""} />
              ) : null,
            )}
            <div className="story-dots">
              {items.map((s, i) => (
                <i key={s.id} className={i === step ? "on" : ""} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function ReadyToShip({ products }: { products: Product[] }) {
  const rail = useRef<HTMLDivElement>(null);
  const scroll = (dir: number) => rail.current?.scrollBy({ left: dir * rail.current.clientWidth * 0.8, behavior: "smooth" });
  if (!products.length) return null;
  return (
    <section className="section rail-section">
      <div className="container section-head" data-reveal>
        <div>
          <span className="eyebrow">Ready to ship</span>
          <h2 className="display">Campus favorites.</h2>
        </div>
        <div className="rail-arrows">
          <button onClick={() => scroll(-1)} aria-label="Scroll left">‹</button>
          <button onClick={() => scroll(1)} aria-label="Scroll right">›</button>
        </div>
      </div>
      <div className="rail" ref={rail}>
        {products.map((p, i) => (
          <div key={p.product_id} className="rail-item" data-reveal style={{ ["--d" as string]: `${Math.min(i, 5) * 70}ms` }}>
            <ProductCard product={p} />
          </div>
        ))}
      </div>
    </section>
  );
}
