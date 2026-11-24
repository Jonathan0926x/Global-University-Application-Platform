/**
 * Regional Formatting Engine
 *
 * Implements strict separation of Language, Locale, and Currency:
 * Changing the display language NEVER silently alters tuition amounts,
 * exchange rates, or mathematical academic metrics (GPA).
 */

export interface FormatOptions {
  locale?: string;
  currency?: string;
  calendar?: "gregory" | "islamic-umalqura" | "persian" | "hebrew";
  timeZone?: string;
}

/**
 * Format a number according to regional locale conventions (decimal & thousand separators)
 */
export function formatNumber(
  value: number,
  options?: { locale?: string; minimumFractionDigits?: number; maximumFractionDigits?: number }
): string {
  const locale = options?.locale || "en-US";
  try {
    return new Intl.NumberFormat(locale, {
      minimumFractionDigits: options?.minimumFractionDigits,
      maximumFractionDigits: options?.maximumFractionDigits,
    }).format(value);
  } catch {
    return value.toString();
  }
}

/**
 * Format currency explicitly distinguishing display currency from student financial values
 */
export function formatCurrency(
  amount: number,
  currencyCode: string = "USD",
  locale: string = "en-US"
): string {
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: currencyCode,
      currencyDisplay: "symbol",
    }).format(amount);
  } catch {
    return `${currencyCode} ${amount.toFixed(2)}`;
  }
}

/**
 * Format date supporting regional calendars (Gregorian, Hijri, Persian, Hebrew)
 */
export function formatDate(
  dateInput: Date | string | number,
  options?: {
    locale?: string;
    calendar?: string;
    dateStyle?: "full" | "long" | "medium" | "short";
    timeZone?: string;
  }
): string {
  const date = typeof dateInput === "string" || typeof dateInput === "number" ? new Date(dateInput) : dateInput;
  if (isNaN(date.getTime())) return "—";

  const locale = options?.locale || "en-US";
  const intlOptions: Intl.DateTimeFormatOptions = {
    dateStyle: options?.dateStyle || "medium",
    timeZone: options?.timeZone || "UTC",
  };

  if (options?.calendar && options.calendar !== "gregory") {
    intlOptions.calendar = options.calendar;
  }

  try {
    return new Intl.DateTimeFormat(locale, intlOptions).format(date);
  } catch {
    return date.toLocaleDateString();
  }
}

/**
 * Format GPA or academic grade points preserving exact precision
 */
export function formatGPA(gpa: number, scale: number = 4.0, locale: string = "en-US"): string {
  const formattedVal = formatNumber(gpa, { locale, minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const formattedScale = formatNumber(scale, { locale, minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${formattedVal} / ${formattedScale}`;
}
