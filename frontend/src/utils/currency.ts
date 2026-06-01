const STORAGE_KEY = "displayCurrency";
const DEFAULT_CURRENCY = "EUR";
export const SUPPORTED_CURRENCIES = ["EUR", "USD", "GBP"] as const;

export type DisplayCurrency = (typeof SUPPORTED_CURRENCIES)[number];

export function getDisplayCurrency(): DisplayCurrency {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && SUPPORTED_CURRENCIES.includes(stored as DisplayCurrency)) {
    return stored as DisplayCurrency;
  }
  return DEFAULT_CURRENCY;
}

export function setDisplayCurrency(currency: DisplayCurrency): void {
  localStorage.setItem(STORAGE_KEY, currency);
  window.dispatchEvent(new CustomEvent("displayCurrencyChange", { detail: currency }));
}

export function formatMoney(amount: number, currency?: string | null): string {
  const code = currency || getDisplayCurrency();
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: code,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${code}`;
  }
}

export function currencyQueryParam(): string {
  return `currency=${encodeURIComponent(getDisplayCurrency())}`;
}
