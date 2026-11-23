import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface FormatCurrencyOptions {
  currency?: string;
  showDecimals?: boolean | "auto";
  fallback?: string;
}

/**
 * Reusable Indian Rupee (INR) and multi-currency formatting utility.
 * Uses Intl.NumberFormat with "en-IN" locale for proper Indian numbering system (Lakhs, Crores).
 *
 * Decimal Decision:
 * In rental marketplace transactions, whole rupee amounts are shown without paise (e.g. ₹35,000)
 * to maximize readability, while non-zero fractional values automatically retain 2 decimal places
 * (e.g. ₹35,000.50) to prevent precision loss.
 *
 * Missing or invalid values return "N/A" (or caller-supplied fallback) rather than silently
 * masking errors as ₹0.
 */
export function formatCurrency(
  amount: number | string | null | undefined,
  currencyOrOptions?: string | FormatCurrencyOptions
): string {
  const options: FormatCurrencyOptions =
    typeof currencyOrOptions === "string"
      ? { currency: currencyOrOptions }
      : currencyOrOptions || {};

  const currency = (options.currency || "INR").toUpperCase();
  const fallback = options.fallback ?? "N/A";

  if (amount === null || amount === undefined) {
    return fallback;
  }

  let num: number;
  if (typeof amount === "number") {
    num = amount;
  } else if (typeof amount === "string") {
    const trimmed = amount.trim();
    if (trimmed === "" || isNaN(Number(trimmed))) {
      return fallback;
    }
    num = Number(trimmed);
  } else {
    return fallback;
  }

  if (isNaN(num)) {
    return fallback;
  }

  const isUSD = currency === "USD";
  const locale = isUSD ? "en-US" : "en-IN";

  const hasDecimals = num % 1 !== 0;
  const showDecimals =
    options.showDecimals === true ||
    (options.showDecimals !== false && hasDecimals);

  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: isUSD ? "USD" : "INR",
    minimumFractionDigits: showDecimals ? 2 : 0,
    maximumFractionDigits: showDecimals ? 2 : 0,
  }).format(num);
}

/**
 * Compact Indian currency representation (e.g., ₹1.5 Cr, ₹3.5 L, ₹25 k, ₹800).
 */
export function formatIndianCompactCurrency(
  amount: number | null | undefined
): string {
  if (amount === null || amount === undefined || isNaN(amount) || amount === 0) {
    return "₹0";
  }

  const absAmount = Math.abs(amount);
  const sign = amount < 0 ? "-" : "";

  if (absAmount >= 10000000) {
    const cr = (absAmount / 10000000).toFixed(1).replace(/\.0$/, "");
    return `${sign}₹${cr} Cr`;
  }
  if (absAmount >= 100000) {
    const l = (absAmount / 100000).toFixed(1).replace(/\.0$/, "");
    return `${sign}₹${l} L`;
  }
  if (absAmount >= 1000) {
    const k = (absAmount / 1000).toFixed(1).replace(/\.0$/, "");
    return `${sign}₹${k} k`;
  }
  return `${sign}₹${absAmount}`;
}

export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return "Flexible";
  try {
    return new Date(dateStr).toLocaleDateString("en-IN", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

/** Today's date as `YYYY-MM-DD` in the user's local time zone, for `<input type="date" min>`. */
export function localDateInputValue(d: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function formatDateTimeIST(dateStr?: string | null): string {
  if (!dateStr) return "Flexible";
  try {
    return new Date(dateStr).toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function formatIndianPhoneNumber(
  phone?: string | null,
  mask: boolean = false
): string {
  if (!phone) return "Not provided";
  const cleaned = phone.replace(/[^\d]/g, "");
  if (cleaned.length < 10) return phone;
  const last10 = cleaned.slice(-10);
  if (mask) {
    return `+91 XXXXX XX${last10.slice(6)}`;
  }
  return `+91 ${last10.slice(0, 5)} ${last10.slice(5)}`;
}

export interface IndianCityInfo {
  name: string;
  state: string;
  tier: 1 | 2;
  localities: string[];
}

export const TOP_INDIAN_CITIES: IndianCityInfo[] = [
  {
    name: "Bengaluru",
    state: "Karnataka",
    tier: 1,
    localities: [
      "Koramangala",
      "HSR Layout",
      "Indiranagar",
      "Whitefield",
      "Bellandur",
      "Electronic City",
      "BTM Layout",
      "Jayanagar",
      "Marathahalli",
    ],
  },
  {
    name: "Mumbai",
    state: "Maharashtra",
    tier: 1,
    localities: ["Bandra West", "Andheri West", "Powai", "Juhu", "Worli", "BKC"],
  },
  {
    name: "Delhi NCR",
    state: "Delhi",
    tier: 1,
    localities: ["Hauz Khas", "Saket", "Cyber City", "Golf Course Road", "Sector 62"],
  },
  {
    name: "Hyderabad",
    state: "Telangana",
    tier: 1,
    localities: ["Gachibowli", "HITEC City", "Madhapur", "Jubilee Hills", "Kondapur"],
  },
  {
    name: "Pune",
    state: "Maharashtra",
    tier: 1,
    localities: ["Koregaon Park", "Viman Nagar", "Hinjewadi", "Baner", "Kothrud"],
  },
  {
    name: "Chennai",
    state: "Tamil Nadu",
    tier: 1,
    localities: ["OMR", "Adyar", "Besant Nagar", "Velachery", "T Nagar"],
  },
];
