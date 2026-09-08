import { afterEach, describe, expect, it } from "vitest";
import { currencyQueryParam, formatMoney, getDisplayCurrency } from "./currency";

afterEach(() => localStorage.clear());

describe("currency utils", () => {
  it("formats an amount in the given currency (locale-independent digits)", () => {
    // The runner's locale is unknown; assert the grouped digits appear.
    expect(formatMoney(1234.5, "USD").replace(/[^\d]/g, "")).toContain("123450");
    expect(formatMoney(10, "EUR")).toMatch(/10/);
  });

  it("falls back to a plain string for an invalid currency code", () => {
    expect(formatMoney(5, "NOTACCY")).toBe("5.00 NOTACCY");
  });

  it("defaults the display currency to EUR and rejects unknown stored values", () => {
    expect(getDisplayCurrency()).toBe("EUR");
    localStorage.setItem("displayCurrency", "JPY");
    expect(getDisplayCurrency()).toBe("EUR");
    localStorage.setItem("displayCurrency", "USD");
    expect(getDisplayCurrency()).toBe("USD");
  });

  it("builds the currency query param from the stored value", () => {
    localStorage.setItem("displayCurrency", "GBP");
    expect(currencyQueryParam()).toBe("currency=GBP");
  });
});
