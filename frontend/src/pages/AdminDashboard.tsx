import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { clearSampleData, formatPrice, getAnalytics, loadSampleData, type Analytics } from "../api";
import { useAuth } from "../auth";

const RANGES = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
  { days: 0, label: "All time" },
];
type Metric = "revenue" | "orders" | "visitors" | "views" | "searches" | "cart_adds";
const METRICS: { key: Metric; label: string; money?: boolean }[] = [
  { key: "revenue", label: "Revenue", money: true },
  { key: "orders", label: "Orders" },
  { key: "visitors", label: "Visitors" },
  { key: "views", label: "Product views" },
  { key: "searches", label: "Searches" },
  { key: "cart_adds", label: "Cart adds" },
];

const num = (n: number) => n.toLocaleString("en-US");
const money = (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
// Timestamps are stored in UTC.
const when = (t: string) =>
  new Date(t.replace(" ", "T") + "Z").toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
const idle = (h: number) => (h < 1 ? `${Math.round(h * 60)} min` : h < 48 ? `${Math.round(h)} hr` : `${Math.round(h / 24)} days`);

export default function AdminDashboard() {
  const { user, ready } = useAuth();
  const [days, setDays] = useState(30);
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [metric, setMetric] = useState<Metric>("revenue");
  const [openCart, setOpenCart] = useState<number | null>(null);
  const [working, setWorking] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    getAnalytics(days)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    if (user?.is_admin) load();
  }, [days, user?.id]);

  if (!ready) return <div className="container page"><div className="skeleton-detail" /></div>;
  if (!user?.is_admin)
    return (
      <div className="container page">
        <div className="empty-state">
          <div className="empty-state-icon">🔒</div>
          <h2>Admins only</h2>
          <p className="muted">
            {user ? "Your account doesn't have access to the analytics dashboard." : "Log in with an admin account to see the analytics dashboard."}
          </p>
          {!user && <Link to="/login" className="btn btn-primary">Log in</Link>}
        </div>
      </div>
    );

  const sample = async (add: boolean) => {
    setWorking(true);
    await (add ? loadSampleData() : clearSampleData()).catch(() => undefined);
    setWorking(false);
    load();
  };

  const k = data?.kpis;
  return (
    <div className="admin">
      <div className="admin-top">
        <div className="container admin-top-inner">
          <div>
            <span className="eyebrow light">Campus Customs · Admin</span>
            <h1>Store analytics</h1>
            <p>Searches, carts, checkouts, and product popularity{data && <> · updated {when(data.generated_at)}</>}</p>
          </div>
          <div className="admin-controls">
            <div className="segmented" role="tablist" aria-label="Date range">
              {RANGES.map((r) => (
                <button key={r.days} role="tab" aria-selected={days === r.days} className={days === r.days ? "on" : ""} onClick={() => setDays(r.days)}>
                  {r.label}
                </button>
              ))}
            </div>
            <button className="btn btn-light small" onClick={load} disabled={loading}>
              {loading ? "Refreshing…" : "↻ Refresh"}
            </button>
          </div>
        </div>
      </div>

      <div className="container admin-body">
        {error && <div className="alert">{error}</div>}
        {data && (
          <div className={`sample-banner ${data.includes_sample_data ? "on" : ""}`}>
            {data.includes_sample_data ? (
              <>
                <span>🧪 This dashboard includes <strong>sample data</strong> (orders numbered SAMPLE-…, guest shoppers). Real activity is mixed in.</span>
                <button className="btn btn-outline small" disabled={working} onClick={() => sample(false)}>Remove sample data</button>
              </>
            ) : (
              <>
                <span>Showing real store activity only. New shop? Load sample activity to preview every chart (it's flagged and removable; real stock isn't touched).</span>
                <button className="btn btn-outline small" disabled={working} onClick={() => sample(true)}>Load sample data</button>
              </>
            )}
          </div>
        )}

        {!data || !k ? (
          <div className="kpi-grid">{Array.from({ length: 8 }, (_, i) => <div key={i} className="kpi skeleton-kpi" />)}</div>
        ) : (
          <>
            <div className="kpi-grid">
              <Kpi label="Revenue" value={money(k.revenue)} note={`${money(k.merchandise_sales)} merchandise`} tone="navy" />
              <Kpi label="Orders" value={num(k.orders)} note={`${num(k.units_sold)} items · ${k.units_per_order} per order`} />
              <Kpi label="Avg. order value" value={money(k.avg_order_value)} />
              <Kpi label="Conversion rate" value={`${k.conversion_rate}%`} note={`of ${num(k.visitors)} visitors bought`} />
              <Kpi label="Abandoned carts" value={num(k.abandoned_carts)} note={`${money(k.abandoned_value)} left in carts`} tone="warn" />
              <Kpi label="Cart abandonment" value={`${k.cart_abandonment_rate}%`} note={`idle ${data.abandoned_after_minutes}+ min without checkout`} tone="warn" />
              <Kpi label="Searches" value={num(k.searches)} note={`${k.zero_result_rate}% found nothing`} />
              <Kpi label="Product views" value={num(k.product_views)} note={`${num(k.cart_adds)} cart adds · ${num(k.comparisons)} comparisons`} />
            </div>

            <div className="admin-grid two">
              <Panel title="Day by day" subtitle={`${METRICS.find((m) => m.key === metric)!.label} per day`}
                action={
                  <select value={metric} onChange={(e) => setMetric(e.target.value as Metric)} aria-label="Chart metric">
                    {METRICS.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
                  </select>
                }>
                <BarChart data={data.daily.map((d) => ({ label: d.date, value: d[metric] }))} money={metric === "revenue"} />
              </Panel>
              <Panel title="Shopper funnel" subtitle="Unique shoppers reaching each step">
                <div className="funnel">
                  {data.funnel.map((f, i) => (
                    <div key={f.step} className="funnel-row">
                      <div className="funnel-label">
                        <span>{f.step}</span>
                        <strong>{num(f.shoppers)}</strong>
                      </div>
                      <div className="funnel-bar"><i style={{ width: `${Math.max(f.pct_of_visitors, f.shoppers ? 2 : 0)}%` }} /></div>
                      <span className="funnel-pct">{i === 0 ? "100%" : `${f.pct_of_previous}% of previous step`}</span>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>

            <Panel title="Popular products" subtitle="Ranked by views, cart adds, and units sold (score = views + 3× units added + 5× units sold)">
              <Table empty="No product activity in this period yet." rows={data.popular_products} head={["#", "Product", "Views", "Cart adds", "View → cart", "Units sold", "Revenue", "In stock"]}
                row={(p, i) => [
                  <span className="rank">{i + 1}</span>,
                  <ProductCell {...p} />,
                  num(p.views), `${num(p.cart_adds)} (${num(p.cart_add_units)} units)`, `${p.view_to_cart_pct}%`, num(p.units_sold), money(p.revenue),
                  <StockCell n={p.total_stock} />,
                ]} />
            </Panel>

            <div className="admin-grid two">
              <Panel title="Top searches" subtitle={`Search bar: ${num(data.search_sources.search_bar)} · Chat assistant: ${num(data.search_sources.chat)}`}>
                <Table empty="No searches in this period yet." rows={data.top_searches} head={["Search", "Times", "Avg. results", "Bar / Chat", "Last"]}
                  row={(s) => [
                    <strong className={s.zero_results === s.count ? "zero" : ""}>{s.query}</strong>,
                    num(s.count), s.avg_results, `${s.search_bar} / ${s.chat}`, when(s.last_searched),
                  ]} />
              </Panel>
              <Panel title="Searches that found nothing" subtitle="Products shoppers want that the shop doesn't carry">
                {data.zero_result_searches.length ? (
                  <ul className="miss-list">
                    {data.zero_result_searches.map((s) => (
                      <li key={s.query}>
                        <span>“{s.query}”</span>
                        <strong>{s.count}×</strong>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted empty-note">Every search found something. 🎉</p>
                )}
              </Panel>
            </div>

            <Panel title="Abandoned carts" subtitle={`Carts with items and no activity for ${data.abandoned_after_minutes}+ minutes, priced at today's prices`}>
              <Table empty="No abandoned carts in this period." rows={data.abandoned_carts} head={["Shopper", "Items", "Cart value", "Last active", "Idle for", ""]}
                row={(c) => [
                  <div className="shopper-cell">
                    <strong>{c.shopper}</strong>
                    <span>{c.signed_in ? c.email : "Not signed in"}{c.is_demo && " · sample"}</span>
                    {openCart === c.cart_id && (
                      <ul className="cart-peek">
                        {c.items.map((i) => (
                          <li key={i.product_id + i.size}>{i.quantity}× {i.name} ({i.size}) · {formatPrice(i.line_total)}</li>
                        ))}
                      </ul>
                    )}
                  </div>,
                  `${c.units} item${c.units === 1 ? "" : "s"}`, <strong>{money(c.value)}</strong>, when(c.last_active), idle(c.idle_hours),
                  <button className="link-btn" onClick={() => setOpenCart(openCart === c.cart_id ? null : c.cart_id)}>{openCart === c.cart_id ? "Hide" : "View items"}</button>,
                ]} />
            </Panel>

            <div className="admin-grid two">
              <Panel title="Checked-out items" subtitle="What sold, by product and size">
                <Table empty="Nothing sold in this period yet." rows={data.checked_out_items} head={["Product", "Size", "Units", "Orders", "Revenue"]}
                  row={(i) => [<ProductCell {...i} />, i.size, num(i.units), num(i.orders), money(i.revenue)]} />
              </Panel>
              <div className="admin-stack">
                <Panel title="Sales by category">
                  {data.sales_by_category.length ? (
                    <div className="hbars">
                      {data.sales_by_category.map((c) => (
                        <div key={c.category} className="hbar">
                          <div className="hbar-label"><span>{c.category}</span><strong>{money(c.revenue)}</strong></div>
                          <div className="hbar-track"><i style={{ width: `${c.share_pct}%` }} /></div>
                          <span className="hbar-note">{c.share_pct}% of sales · {num(c.units)} units</span>
                        </div>
                      ))}
                    </div>
                  ) : <p className="muted empty-note">No sales yet.</p>}
                </Panel>
                <Panel title="Sizes sold">
                  {data.sizes_sold.length ? (
                    <div className="size-bars">
                      {data.sizes_sold.map((s) => {
                        const max = Math.max(...data.sizes_sold.map((x) => x.units));
                        return (
                          <div key={s.size}>
                            <div className="size-bar"><i style={{ height: `${(s.units / max) * 100}%` }} /></div>
                            <strong>{s.size}</strong>
                            <span>{num(s.units)}</span>
                          </div>
                        );
                      })}
                    </div>
                  ) : <p className="muted empty-note">No sales yet.</p>}
                </Panel>
              </div>
            </div>

            <Panel title="Recent orders">
              <Table empty="No orders in this period yet." rows={data.recent_orders} head={["Order", "Placed", "Customer", "Items", "Ships to", "Total"]}
                row={(o) => [
                  <strong className="mono">{o.order_number}</strong>, when(o.created_at),
                  <div className="shopper-cell"><strong>{o.customer}</strong><span>{o.email}{o.signed_in ? " · member" : " · guest"}</span></div>,
                  <span className="order-items" title={o.items.join("\n")}>{o.items.join(", ")}</span>, o.city, <strong>{money(o.total)}</strong>,
                ]} />
            </Panel>

            <Panel title="Low stock alerts" subtitle={`${data.low_stock_counts.out_of_stock} sizes sold out · ${data.low_stock_counts.low} sizes with 5 or fewer left`}>
              <div className="stock-alerts">
                {data.low_stock.map((s) => (
                  <Link key={s.product_id + s.size} to={`/products/${s.product_id}`} className={`stock-alert ${s.quantity === 0 ? "out" : "low"}`}>
                    {s.thumb_url && <img src={s.thumb_url} alt="" />}
                    <span><strong>{s.name}</strong>Size {s.size}</span>
                    <em>{s.quantity === 0 ? "Sold out" : `${s.quantity} left`}</em>
                  </Link>
                ))}
              </div>
            </Panel>
          </>
        )}
      </div>
    </div>
  );
}

function Kpi({ label, value, note, tone }: { label: string; value: string; note?: string; tone?: "navy" | "warn" }) {
  return (
    <div className={`kpi ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <em>{note}</em>}
    </div>
  );
}

function Panel({ title, subtitle, action, children }: { title: string; subtitle?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Table<T>({ head, rows, row, empty }: { head: string[]; rows: T[]; row: (r: T, i: number) => ReactNode[]; empty: string }) {
  if (!rows.length) return <p className="muted empty-note">{empty}</p>;
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>{head.map((h, i) => <th key={i}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{row(r, i).map((cell, j) => <td key={j}>{cell}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProductCell({ product_id, name, thumb_url, category }: { product_id: string; name: string; thumb_url: string | null; category: string }) {
  return (
    <Link to={`/products/${product_id}`} className="product-cell">
      {thumb_url && <img src={thumb_url} alt="" />}
      <span><strong>{name}</strong>{category}</span>
    </Link>
  );
}

function StockCell({ n }: { n: number | null }) {
  if (n === null) return <>—</>;
  return <span className={`stock-pill ${n === 0 ? "out" : n <= 10 ? "low" : "ok"}`}>{n === 0 ? "Sold out" : num(n)}</span>;
}

// Simple SVG bar chart with a hover label on each bar.
function BarChart({ data, money: isMoney }: { data: { label: string; value: number }[]; money?: boolean }) {
  const [hover, setHover] = useState<number | null>(null);
  if (!data.length) return <p className="muted empty-note">No data.</p>;
  const max = Math.max(1, ...data.map((d) => d.value));
  const total = data.reduce((s, d) => s + d.value, 0);
  const W = 640, H = 200, gap = data.length > 60 ? 1 : 3;
  const bw = (W - gap * (data.length - 1)) / data.length;
  const fmt = (v: number) => (isMoney ? money(v) : num(v));
  const day = (d: string) => new Date(d + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const shown = hover !== null ? data[hover] : null;
  return (
    <div className="chart">
      <div className="chart-readout">
        {shown ? <><strong>{fmt(shown.value)}</strong> on {day(shown.label)}</> : <><strong>{fmt(Math.round(total * 100) / 100)}</strong> total · peak {fmt(max)}</>}
      </div>
      <svg viewBox={`0 0 ${W} ${H + 22}`} role="img" aria-label="Daily chart" onMouseLeave={() => setHover(null)}>
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} x1="0" x2={W} y1={H - H * f} y2={H - H * f} className="chart-grid" />
        ))}
        {data.map((d, i) => {
          const h = (d.value / max) * (H - 6);
          return (
            <g key={d.label} onMouseEnter={() => setHover(i)}>
              <rect x={i * (bw + gap)} y={0} width={bw} height={H} fill="transparent" />
              <rect x={i * (bw + gap)} y={H - h} width={bw} height={Math.max(h, d.value ? 2 : 0)} rx={Math.min(3, bw / 3)} className={`chart-bar ${hover === i ? "hover" : ""}`} />
            </g>
          );
        })}
        <text x="0" y={H + 16} className="chart-axis">{day(data[0].label)}</text>
        <text x={W} y={H + 16} textAnchor="end" className="chart-axis">{day(data[data.length - 1].label)}</text>
      </svg>
    </div>
  );
}
