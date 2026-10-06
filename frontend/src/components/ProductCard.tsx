import { useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { formatPrice, type Product } from "../api";
import { useReturnState } from "../assistantResults";
import { openProductWithMorph, usePointerVars } from "../motion";
import { swatch } from "../swatches";
import CompareToggle from "./CompareToggle";

const MAX_SWATCHES = 5;

export default function ProductCard({ product }: { product: Product }) {
  const soldOut = product.total_stock === 0;
  const lowStock = !soldOut && product.total_stock <= 10;
  const returnState = useReturnState();
  const navigate = useNavigate();
  const ref = useRef<HTMLDivElement>(null);
  usePointerVars(ref); // drives the gentle 3D tilt and light sheen on hover
  const to = `/products/${product.product_id}`;
  const cut = Boolean(product.cutout_thumb_url);

  return (
    <div ref={ref} className="product-card">
      <Link to={to} state={returnState} className="product-card-link" onClick={(e) => openProductWithMorph(e, navigate, to, returnState)}>
        <div className={`product-card-stage ${cut ? "" : "photo"}`}>
          {/* Background-free cutout on a soft stage; small, lazy-loaded WebP. */}
          <img
            src={product.cutout_thumb_url ?? product.thumb_url}
            alt={product.name}
            loading="lazy"
            decoding="async"
            width={320}
            height={320}
            data-morph
          />
          {soldOut ? <span className="badge badge-out">Sold out</span> : lowStock && <span className="badge badge-low">Almost gone</span>}
        </div>
        <div className="product-card-body">
          <span className="eyebrow">{product.category}</span>
          <h3>{product.name}</h3>
          <p>{product.short_description}</p>
          <div className="product-card-foot">
            <span className="price">{formatPrice(product.price)}</span>
            <span className="swatches" aria-label={`Colors: ${product.colors.join(", ")}`}>
              {product.colors.slice(0, MAX_SWATCHES).map((c) => (
                <i key={c} style={{ background: swatch(c) }} title={c} />
              ))}
              {product.colors.length > MAX_SWATCHES && <em>+{product.colors.length - MAX_SWATCHES}</em>}
            </span>
          </div>
        </div>
      </Link>
      <CompareToggle productId={product.product_id} />
    </div>
  );
}
