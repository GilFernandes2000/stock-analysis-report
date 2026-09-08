import { FormEvent, useState } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { useDisplayCurrency } from "./hooks/useDisplayCurrency";

const NAV_SECTIONS: {
  heading: string;
  items: { to: string; label: string; icon: string }[];
}[] = [
  {
    heading: "Portfolio",
    items: [
      { to: "/", label: "Portfolios", icon: "◫" },
      { to: "/reports", label: "Reports", icon: "▤" },
    ],
  },
  {
    heading: "Research",
    items: [
      { to: "/market", label: "Market", icon: "◉" },
      { to: "/screener", label: "Screener", icon: "☰" },
      { to: "/favorites", label: "Favorites", icon: "★" },
    ],
  },
];

export function App() {
  const { user, loading, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const { currency, setCurrency, supported } = useDisplayCurrency();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-edge border-t-accent" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    const ticker = query.trim().toUpperCase();
    if (ticker) {
      setQuery("");
      navigate(`/stock/${ticker}`);
    }
  }

  function isActive(to: string): boolean {
    if (to === "/") return location.pathname === "/" || location.pathname.startsWith("/portfolios");
    return location.pathname.startsWith(to);
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="no-print fixed inset-y-0 left-0 z-20 hidden w-56 flex-col border-r border-grid bg-panel/60 backdrop-blur lg:flex">
        <Link to="/" className="flex items-center gap-2.5 px-5 pb-2 pt-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent font-bold text-white">
            M
          </span>
          <span>
            <span className="block text-sm font-bold tracking-tight text-ink">
              Meridian
            </span>
            <span className="block text-[10px] uppercase tracking-widest text-muted">
              Portfolio Intelligence
            </span>
          </span>
        </Link>
        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
          {NAV_SECTIONS.map((section) => (
            <div key={section.heading}>
              <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted">
                {section.heading}
              </p>
              <div className="space-y-0.5">
                {section.items.map((item) => (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition ${
                      isActive(item.to)
                        ? "bg-raised text-ink"
                        : "text-ink2 hover:bg-raised/60 hover:text-ink"
                    }`}
                  >
                    <span className="w-4 text-center text-muted">{item.icon}</span>
                    {item.label}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="border-t border-grid p-3">
          <div className="flex items-center justify-between gap-2 rounded-xl px-2 py-1.5">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink">
                {user.display_name}
              </p>
              <p className="truncate text-xs text-muted">@{user.username}</p>
            </div>
            <button
              onClick={() => logout().then(() => navigate("/login"))}
              className="shrink-0 rounded-lg border border-edge px-2 py-1 text-xs text-muted transition hover:border-crit/50 hover:text-down"
              title="Sign out"
            >
              Exit
            </button>
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-56">
        <header className="no-print sticky top-0 z-10 border-b border-grid bg-page/80 backdrop-blur">
          <div className="flex items-center gap-3 px-4 py-3 sm:px-6">
            {/* Mobile brand */}
            <Link to="/" className="flex items-center gap-2 lg:hidden">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-sm font-bold text-white">
                M
              </span>
            </Link>
            <form onSubmit={handleSearch} className="flex max-w-md flex-1 gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value.toUpperCase())}
                placeholder="Search ticker — AAPL, ASML.AS, VOD.L…"
                className="w-full rounded-xl border border-edge bg-inset px-3.5 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none"
              />
            </form>
            <div className="ml-auto flex items-center gap-2">
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value as typeof currency)}
                className="rounded-xl border border-edge bg-inset px-2.5 py-2 text-sm text-ink focus:border-accent focus:outline-none"
                aria-label="Display currency"
              >
                {supported.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
              {/* Mobile nav */}
              <nav className="flex gap-1 lg:hidden">
                {[
                  { to: "/", label: "Portfolios" },
                  { to: "/market", label: "Market" },
                  { to: "/favorites", label: "Favorites" },
                ].map((item) => (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`rounded-lg px-2.5 py-1.5 text-xs font-medium ${
                      isActive(item.to) ? "bg-raised text-ink" : "text-ink2"
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
          <Outlet />
        </main>
        <footer className="no-print border-t border-grid px-6 py-3 text-center text-[11px] text-muted">
          Market data from Finviz &amp; Yahoo Finance, delayed 15–20 min. Analytics
          are informational only — not investment advice.
        </footer>
      </div>
    </div>
  );
}
