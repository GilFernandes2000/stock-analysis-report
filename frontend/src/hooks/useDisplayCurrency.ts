import { useCallback, useEffect, useState } from "react";
import {
  type DisplayCurrency,
  SUPPORTED_CURRENCIES,
  getDisplayCurrency,
  setDisplayCurrency as persistDisplayCurrency,
} from "../utils/currency";

export function useDisplayCurrency() {
  const [currency, setCurrencyState] = useState<DisplayCurrency>(getDisplayCurrency);

  useEffect(() => {
    function onChange(e: Event) {
      const detail = (e as CustomEvent<DisplayCurrency>).detail;
      if (detail && SUPPORTED_CURRENCIES.includes(detail)) {
        setCurrencyState(detail);
      } else {
        setCurrencyState(getDisplayCurrency());
      }
    }
    window.addEventListener("displayCurrencyChange", onChange);
    return () => window.removeEventListener("displayCurrencyChange", onChange);
  }, []);

  const setCurrency = useCallback((next: DisplayCurrency) => {
    persistDisplayCurrency(next);
    setCurrencyState(next);
  }, []);

  return { currency, setCurrency, supported: SUPPORTED_CURRENCIES };
}
