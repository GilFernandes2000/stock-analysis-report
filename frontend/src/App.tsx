import { FormEvent, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ApiStatusBanner } from "./components/ApiStatusBanner";
import { DisclaimerBanner } from "./components/DisclaimerBanner";
import { useDisplayCurrency } from "./hooks/useDisplayCurrency";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/screener", label: "Screener" },
  { to: "/portfolio", label: "Portfolio" },
  { to: "/reports", label: "Reports" },
];

export function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const { currency, setCurrency, supported } = useDisplayCurrency();

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    const ticker = query.trim().toUpperCase();
    if (ticker) navigate(`/stock/${ticker}`);
  }

  return (
    <div className="min-h-screen">
      <DisclaimerBanner />
      <ApiStatusBanner />
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-10">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <Link to="/" className="text-lg font-bold tracking-tight text-white shrink-0">
            Stock Analysis Report
          </Link>
          <form onSubmit={handleSearch} className="flex flex-1 max-w-md gap-2 sm:mx-4">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value.toUpperCase())}
              placeholder="AAPL, SAP.DE, VOD.L, MC.PA..."
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none"
            />
            <button
              type="submit"
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              Go
            </button>
          </form>
          <nav className="flex gap-1 shrink-0 items-center">
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value as typeof currency)}
              className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-sm text-white focus:border-emerald-500 focus:outline-none"
              aria-label="Display currency"
            >
              {supported.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
            {nav.map((item) => {
              const active =
                item.to === "/"
                  ? location.pathname === "/"
                  : location.pathname.startsWith(item.to);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                    active
                      ? "bg-slate-800 text-white"
                      : "text-slate-400 hover:bg-slate-900 hover:text-white"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
