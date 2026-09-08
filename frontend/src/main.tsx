import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { FavoritesProvider } from "./favorites/FavoritesContext";
import { Login } from "./pages/Login";
import "./index.css";

// Route components are code-split so the initial bundle stays small; the
// chart-heavy ones (Reports, ReportView, PortfolioDetail, StockDetail) pull
// recharts into their own chunks, loaded on navigation.
const Portfolios = lazy(() => import("./pages/Portfolios").then((m) => ({ default: m.Portfolios })));
const PortfolioDetail = lazy(() =>
  import("./pages/PortfolioDetail").then((m) => ({ default: m.PortfolioDetail }))
);
const Reports = lazy(() => import("./pages/Reports").then((m) => ({ default: m.Reports })));
const ReportView = lazy(() => import("./pages/ReportView").then((m) => ({ default: m.ReportView })));
const Market = lazy(() => import("./pages/Market").then((m) => ({ default: m.Market })));
const Screener = lazy(() => import("./pages/Screener").then((m) => ({ default: m.Screener })));
const Favorites = lazy(() => import("./pages/Favorites").then((m) => ({ default: m.Favorites })));
const StockDetail = lazy(() =>
  import("./pages/StockDetail").then((m) => ({ default: m.StockDetail }))
);

function RouteFallback() {
  return <div className="p-8 text-sm text-ink2">Loading…</div>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <FavoritesProvider>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route element={<App />}>
                <Route index element={<Portfolios />} />
                <Route path="portfolios/:id" element={<PortfolioDetail />} />
                <Route path="reports" element={<Reports />} />
                <Route path="reports/:id" element={<ReportView />} />
                <Route path="market" element={<Market />} />
                <Route path="screener" element={<Screener />} />
                <Route path="favorites" element={<Favorites />} />
                <Route path="stock/:ticker" element={<StockDetail />} />
              </Route>
            </Routes>
          </Suspense>
        </FavoritesProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>
);
