import { lazy, Suspense, useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ChatWidget from "./components/ChatWidget";
import AssistantResults from "./components/AssistantResults";
import Breadcrumbs from "./components/Breadcrumbs";
import CartDrawer from "./components/CartDrawer";
import CompareTray from "./components/CompareTray";
import Home from "./pages/Home";
import Products from "./pages/Products";
import ProductDetail from "./pages/ProductDetail";
import About from "./pages/About";
import Login from "./pages/Login";
import CreateAccount from "./pages/CreateAccount";
import Logout from "./pages/Logout";
import NotFound from "./pages/NotFound";
import CartPage from "./pages/Cart";
import { useRevealOnScroll } from "./motion";

// Loaded only when opened, so shoppers' first page load stays small.
const Checkout = lazy(() => import("./pages/Checkout"));
const OrderConfirmation = lazy(() => import("./pages/OrderConfirmation"));
const Compare = lazy(() => import("./pages/Compare"));
const AdminDashboard = lazy(() => import("./pages/AdminDashboard"));

export default function App() {
  const { pathname } = useLocation();
  useEffect(() => window.scrollTo(0, 0), [pathname]);
  useRevealOnScroll();

  return (
    <div className="app">
      <Navbar />
      <main>
        <Breadcrumbs />
        <AssistantResults />
        <Suspense fallback={<div className="container page"><div className="skeleton-detail" /></div>}>
          {/* Each page fades up as it arrives. */}
          <div key={pathname} className="page-enter">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/products" element={<Products />} />
              <Route path="/products/:productId" element={<ProductDetail />} />
              <Route path="/about" element={<About />} />
              <Route path="/login" element={<Login />} />
              <Route path="/create-account" element={<CreateAccount />} />
              <Route path="/logout" element={<Logout />} />
              <Route path="/cart" element={<CartPage />} />
              <Route path="/checkout" element={<Checkout />} />
              <Route path="/order/:orderNumber" element={<OrderConfirmation />} />
              <Route path="/compare" element={<Compare />} />
              <Route path="/admin" element={<AdminDashboard />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </div>
        </Suspense>
      </main>
      <Footer />
      <CompareTray />
      <CartDrawer />
      <ChatWidget />
    </div>
  );
}
