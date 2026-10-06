import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import {
  addToCart as apiAdd,
  clearCart as apiClear,
  getCart,
  removeFromCart as apiRemove,
  setCartQuantity as apiSetQuantity,
  type Cart,
} from "./api";
import { useAuth } from "./auth";

// The cart lives on the server: a signed-in shopper's cart is saved to their account (it's still
// there after they log out and back in); a guest's cart is tied to their browser.
interface CartValue {
  cart: Cart | null;
  count: number;
  drawerOpen: boolean;
  lastAdded: { productId: string; size: string } | null;
  openDrawer: () => void;
  closeDrawer: () => void;
  add: (productId: string, size: string, quantity?: number) => Promise<void>;
  setQuantity: (productId: string, size: string, quantity: number) => Promise<void>;
  remove: (productId: string, size: string) => Promise<void>;
  clear: () => Promise<void>;
  refresh: () => Promise<void>;
}

const CartContext = createContext<CartValue | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  const [cart, setCart] = useState<Cart | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [lastAdded, setLastAdded] = useState<CartValue["lastAdded"]>(null);

  const refresh = useCallback(async () => {
    setCart(await getCart().catch(() => null));
  }, []);

  // Load the right cart whenever the shopper signs in or out.
  useEffect(() => {
    if (ready) refresh();
  }, [ready, user?.id, refresh]);

  const value: CartValue = {
    cart,
    count: cart?.item_count ?? 0,
    drawerOpen,
    lastAdded,
    openDrawer: () => setDrawerOpen(true),
    closeDrawer: () => setDrawerOpen(false),
    add: async (productId, size, quantity = 1) => {
      setCart(await apiAdd(productId, size, quantity));
      setLastAdded({ productId, size });
      setDrawerOpen(true);
    },
    setQuantity: async (productId, size, quantity) => setCart(await apiSetQuantity(productId, size, quantity)),
    remove: async (productId, size) => setCart(await apiRemove(productId, size)),
    clear: async () => setCart(await apiClear()),
    refresh,
  };
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within a CartProvider");
  return ctx;
}
