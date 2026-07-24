import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { Login } from "./pages/Login";
import { Market } from "./pages/Market";
import { PortfolioDetail } from "./pages/PortfolioDetail";
import { Portfolios } from "./pages/Portfolios";
import { Reports } from "./pages/Reports";
import { ReportView } from "./pages/ReportView";
import { Screener } from "./pages/Screener";
import { StockDetail } from "./pages/StockDetail";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<App />}>
            <Route index element={<Portfolios />} />
            <Route path="portfolios/:id" element={<PortfolioDetail />} />
            <Route path="reports" element={<Reports />} />
            <Route path="reports/:id" element={<ReportView />} />
            <Route path="market" element={<Market />} />
            <Route path="screener" element={<Screener />} />
            <Route path="stock/:ticker" element={<StockDetail />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>
);
