import { useEffect, useState } from "react";
import { api } from "../api/client";

type Status = "loading" | "online" | "offline";

export function ApiStatusBanner() {
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        await api.health();
        if (!cancelled) setStatus("online");
      } catch {
        if (!cancelled) setStatus("offline");
      }
    }

    check();
    const interval = setInterval(check, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (status === "loading" || status === "online") return null;

  return (
    <div className="border-b border-red-500/40 bg-red-500/15 px-4 py-2 text-center text-sm text-red-200">
      Cannot reach the API. Start the backend with{" "}
      <code className="rounded bg-red-950/50 px-1">uvicorn app.main:app --port 8000</code>
    </div>
  );
}
