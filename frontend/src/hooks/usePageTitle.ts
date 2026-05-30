import { useEffect } from "react";

const BASE = "Stock Analysis Report";

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · ${BASE}` : BASE;
    return () => {
      document.title = BASE;
    };
  }, [title]);
}
