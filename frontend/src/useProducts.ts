import { useEffect, useState } from "react";
import { getProducts, type Product } from "./api";

// Loads the full catalogue once per page that needs it.
export function useProducts() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProducts()
      .then(setProducts)
      .catch(() => setError("We couldn't load products. Make sure the API server is running on port 8000."))
      .finally(() => setLoading(false));
  }, []);

  return { products, loading, error };
}
