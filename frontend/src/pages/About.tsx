import { Link } from "react-router-dom";
import { CountUp } from "../motion";
import { useProducts } from "../useProducts";

const VALUES = [
  { title: "Quality First", text: "Every piece is chosen for comfort, durability, and a look that holds up wash after wash." },
  { title: "Priced for Students", text: "We keep our prices affordable so everyone on campus can rep their school." },
  { title: "Campus Pride", text: "Our designs celebrate teams, residential colleges, traditions, and the rivalries that bring us together." },
  { title: "Customers at the Center", text: "We listen to our community and stock the styles and sizes you actually want." },
];
const MOSAIC = ["champion-reverse-weave-hoodie-1", "poly-twill-crewneck-arched-yale", "2025-yale-vs-harvard-t-shirt", "benjamin-franklin-fleece-jacket", "big-yale-tri-blend-t-shirt"];

export default function About() {
  const { products } = useProducts();
  const mosaic = MOSAIC.map((id) => products.find((p) => p.product_id === id)).filter(Boolean);
  const minPrice = products.length ? Math.min(...products.map((p) => p.price)) : 32;

  return (
    <div className="about">
      <section className="about-hero">
        <div className="container">
          <span className="hero-eyebrow">About Us</span>
          <h1>
            Made on campus,
            <br />
            <em>for campus.</em>
          </h1>
          <p>We are a university-based brand that provides high quality merchandise.</p>
        </div>
        <div className="about-mosaic" aria-hidden="true">
          {mosaic.map((p, i) => (
            <img key={p!.product_id} className={`m${i}`} src={p!.cutout_thumb_url ?? p!.thumb_url} alt="" />
          ))}
        </div>
      </section>

      <div className="container">
        <section className="about-story">
          <div data-reveal>
            <span className="eyebrow">Our story</span>
            <h2 className="display">Apparel that feels as good as it looks.</h2>
            <p>
              Campus Customs started with a simple idea: students, alumni, families, and fans deserve apparel that feels
              as good as it looks, without the premium price tag. As a university-based brand, we know what the
              campus community wears, from a warm hoodie on a cold walk to class to a bold tee on game day.
            </p>
            <p>
              Today we offer a curated collection of hoodies, crewnecks, T-shirts, quarter-zips, and jackets that
              celebrate athletics, residential colleges, and campus traditions.
            </p>
          </div>
          <div className="about-stats">
            <div data-reveal>
              <strong><CountUp to={products.length || 102} /></strong>
              <span>Styles in our catalogue</span>
            </div>
            <div data-reveal style={{ ["--d" as string]: "90ms" }}>
              <strong>XS–XXL</strong>
              <span>Sizes for everyone</span>
            </div>
            <div data-reveal style={{ ["--d" as string]: "180ms" }}>
              <strong><CountUp to={minPrice} prefix="$" suffix="+" /></strong>
              <span>Affordable price points</span>
            </div>
          </div>
        </section>

        <section className="section values">
          <h2 className="display center" data-reveal>What we stand for.</h2>
          <div className="values-grid">
            {VALUES.map((v, i) => (
              <div key={v.title} className="value-card" data-reveal style={{ ["--d" as string]: `${i * 80}ms` }}>
                <span className="value-num">0{i + 1}</span>
                <h3>{v.title}</h3>
                <p>{v.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="cta-banner" data-reveal>
          <div>
            <h2>Ready to find your new favorite?</h2>
            <p>Browse the full collection or ask our shopping assistant for help.</p>
          </div>
          <Link to="/products" className="btn btn-light">
            Browse Products
          </Link>
        </section>
      </div>
    </div>
  );
}
