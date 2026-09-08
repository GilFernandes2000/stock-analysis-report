import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

interface FavoritesState {
  tickers: Set<string>;
  loading: boolean;
  isFavorite: (ticker: string) => boolean;
  add: (ticker: string) => Promise<void>;
  remove: (ticker: string) => Promise<void>;
  toggle: (ticker: string) => Promise<void>;
  refresh: () => void;
}

const FavoritesContext = createContext<FavoritesState | null>(null);

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [tickers, setTickers] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(() => {
    if (!user) {
      setTickers(new Set());
      return;
    }
    setLoading(true);
    api
      .listFavorites()
      .then((list) => setTickers(new Set(list.map((f) => f.ticker))))
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const add = useCallback(async (ticker: string) => {
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    // optimistic
    setTickers((prev) => new Set(prev).add(t));
    try {
      await api.addFavorite(t);
    } catch {
      setTickers((prev) => {
        const next = new Set(prev);
        next.delete(t);
        return next;
      });
    }
  }, []);

  const remove = useCallback(async (ticker: string) => {
    const t = ticker.trim().toUpperCase();
    setTickers((prev) => {
      const next = new Set(prev);
      next.delete(t);
      return next;
    });
    try {
      await api.removeFavorite(t);
    } catch {
      setTickers((prev) => new Set(prev).add(t));
    }
  }, []);

  const toggle = useCallback(
    async (ticker: string) => {
      const t = ticker.trim().toUpperCase();
      if (tickers.has(t)) await remove(t);
      else await add(t);
    },
    [tickers, add, remove]
  );

  const value = useMemo(
    () => ({
      tickers,
      loading,
      isFavorite: (t: string) => tickers.has(t.toUpperCase()),
      add,
      remove,
      toggle,
      refresh,
    }),
    [tickers, loading, add, remove, toggle, refresh]
  );

  return (
    <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>
  );
}

export function useFavorites(): FavoritesState {
  const ctx = useContext(FavoritesContext);
  if (!ctx) throw new Error("useFavorites must be used within FavoritesProvider");
  return ctx;
}
