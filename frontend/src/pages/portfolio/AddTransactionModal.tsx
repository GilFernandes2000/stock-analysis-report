import { FormEvent, useEffect, useState } from "react";
import { api } from "../../api/client";
import { Button, ErrorNote, Field, inputClass } from "../../components/ui";
import type { TransactionType } from "../../types";
import { Modal } from "../Portfolios";

export function AddTransactionModal({
  portfolioId,
  baseCurrency,
  onClose,
  onAdded,
}: {
  portfolioId: number;
  baseCurrency: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [type, setType] = useState<TransactionType>("buy");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("");
  const [price, setPrice] = useState("");
  const [amount, setAmount] = useState("");
  const [fees, setFees] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isTrade = type === "buy" || type === "sell";
  const needsTicker = isTrade || type === "dividend";

  // Auto-fill amount from shares × price for trades
  useEffect(() => {
    if (isTrade && shares && price) {
      const value = Number(shares) * Number(price);
      if (Number.isFinite(value)) {
        setAmount((type === "buy" ? -value : value).toFixed(2));
      }
    }
  }, [shares, price, type, isTrade]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.addTransaction(portfolioId, {
        type,
        date: `${date}T12:00:00`,
        ticker: needsTicker ? ticker : null,
        shares: isTrade ? Number(shares) : null,
        price: isTrade && price ? Number(price) : null,
        currency: baseCurrency,
        amount: Number(amount),
        fees: fees ? Number(fees) : 0,
      });
      onAdded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add transaction");
      setBusy(false);
    }
  }

  return (
    <Modal title="Add transaction" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Type">
            <select
              className={inputClass}
              value={type}
              onChange={(e) => setType(e.target.value as TransactionType)}
            >
              {["buy", "sell", "dividend", "deposit", "withdrawal", "fee", "interest"].map(
                (t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                )
              )}
            </select>
          </Field>
          <Field label="Date">
            <input
              type="date"
              className={inputClass}
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </Field>
        </div>
        {needsTicker && (
          <Field label="Ticker (Yahoo symbol)">
            <input
              className={inputClass}
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="AAPL, ASML.AS, VOD.L…"
              required
            />
          </Field>
        )}
        {isTrade && (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Shares">
              <input
                type="number"
                step="any"
                min="0"
                className={inputClass}
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                required
              />
            </Field>
            <Field label={`Price per share (${baseCurrency})`}>
              <input
                type="number"
                step="any"
                min="0"
                className={inputClass}
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </Field>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label={`Amount (${baseCurrency}, signed)`}>
            <input
              type="number"
              step="any"
              className={inputClass}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder={type === "buy" ? "-1000.00" : "1000.00"}
              required
            />
          </Field>
          <Field label={`Fees (${baseCurrency})`}>
            <input
              type="number"
              step="any"
              min="0"
              className={inputClass}
              value={fees}
              onChange={(e) => setFees(e.target.value)}
              placeholder="0.00"
            />
          </Field>
        </div>
        <p className="text-xs text-muted">
          Amount is the signed cash impact: buys negative, sells/dividends/deposits
          positive.
        </p>
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={busy}>
            {busy ? "Saving…" : "Add"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
