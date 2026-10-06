import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AssistantResultsProvider } from "./assistantResults";
import { AuthProvider } from "./auth";
import { CartProvider } from "./cart";
import { CompareProvider } from "./compare";
// Self-hosted web fonts: Bricolage Grotesque (headlines), Inter (text), Instrument Serif (accents).
import "@fontsource-variable/bricolage-grotesque/index.css";
import "@fontsource-variable/inter/index.css";
import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CartProvider>
          <CompareProvider>
            <AssistantResultsProvider>
              <App />
            </AssistantResultsProvider>
          </CompareProvider>
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
