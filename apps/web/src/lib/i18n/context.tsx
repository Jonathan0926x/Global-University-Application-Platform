"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import {
  LanguageDefinition,
  GLOBAL_LANGUAGE_REGISTRY,
  getLanguageByTag,
  TextDirection,
} from "./languages";
import { formatNumber, formatCurrency, formatDate, formatGPA } from "./formatters";
import { translate } from "./translations";
import { auth } from "../auth";

export interface UserPreferencesState {
  language: LanguageDefinition;
  direction: TextDirection;
  locale: string;
  currency: string;
  calendar: "gregory" | "islamic-umalqura" | "persian" | "hebrew";
  autoDetectEnabled: boolean;
  manualOverrideSet: boolean;
}

interface I18nContextType extends UserPreferencesState {
  setLanguage: (tag: string) => void;
  setLocale: (locale: string) => void;
  setCurrency: (currency: string) => void;
  setCalendar: (calendar: "gregory" | "islamic-umalqura" | "persian" | "hebrew") => void;
  setAutoDetectEnabled: (enabled: boolean) => void;
  t: (key: string, fallback?: string) => string;
  formatNumber: (value: number, options?: any) => string;
  formatCurrency: (amount: number, currencyCode?: string) => string;
  formatDate: (date: Date | string | number, options?: any) => string;
  formatGPA: (gpa: number, scale?: number) => string;
}

const I18nContext = createContext<I18nContextType | null>(null);

const STORAGE_KEY_LANG = "uniglobe_preferred_lang";
const STORAGE_KEY_LOCALE = "uniglobe_preferred_locale";
const STORAGE_KEY_CURRENCY = "uniglobe_preferred_currency";
const STORAGE_KEY_CALENDAR = "uniglobe_preferred_calendar";
const STORAGE_KEY_MANUAL = "uniglobe_manual_lang_override";

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<LanguageDefinition>(GLOBAL_LANGUAGE_REGISTRY[0]);
  const [locale, setLocaleState] = useState<string>("en-US");
  const [currency, setCurrencyState] = useState<string>("USD");
  const [calendar, setCalendarState] = useState<"gregory" | "islamic-umalqura" | "persian" | "hebrew">("gregory");
  const [autoDetectEnabled, setAutoDetectEnabledState] = useState<boolean>(true);
  const [manualOverrideSet, setManualOverrideSet] = useState<boolean>(false);
  const [mounted, setMounted] = useState<boolean>(false);

  // Initialize preferences on client mount
  useEffect(() => {
    setMounted(true);
    const storedLang = localStorage.getItem(STORAGE_KEY_LANG);
    const storedLocale = localStorage.getItem(STORAGE_KEY_LOCALE);
    const storedCurrency = localStorage.getItem(STORAGE_KEY_CURRENCY);
    const storedCalendar = localStorage.getItem(STORAGE_KEY_CALENDAR) as any;
    const manualFlag = localStorage.getItem(STORAGE_KEY_MANUAL) === "true";

    let chosenLang = GLOBAL_LANGUAGE_REGISTRY[0];

    if (manualFlag && storedLang) {
      chosenLang = getLanguageByTag(storedLang);
      setManualOverrideSet(true);
    } else if (typeof navigator !== "undefined" && navigator.language) {
      // Auto-detect only if user has not set a manual override
      const browserTag = navigator.language;
      const matched = GLOBAL_LANGUAGE_REGISTRY.find(
        (l) => l.tag.toLowerCase() === browserTag.toLowerCase() || l.iso639_1 === browserTag.split("-")[0].toLowerCase()
      );
      if (matched) chosenLang = matched;
    }

    setLanguageState(chosenLang);
    setLocaleState(storedLocale || chosenLang.defaultLocale);
    setCurrencyState(storedCurrency || "USD"); // Never silently mutate currency to foreign currency by default
    if (storedCalendar) setCalendarState(storedCalendar);

    // Apply document direction and lang attributes
    document.documentElement.dir = chosenLang.direction;
    document.documentElement.lang = chosenLang.tag;
  }, []);

  const setLanguage = (tag: string) => {
    const lang = getLanguageByTag(tag);
    setLanguageState(lang);
    setManualOverrideSet(true);
    localStorage.setItem(STORAGE_KEY_LANG, lang.tag);
    localStorage.setItem(STORAGE_KEY_MANUAL, "true");

    // Adjust document direction immediately for instant RTL / LTR layout adaptation
    if (typeof document !== "undefined") {
      document.documentElement.dir = lang.direction;
      document.documentElement.lang = lang.tag;
    }

    // Sync with backend if authenticated
    const authSession = auth.getSession();
    if (authSession.isAuthenticated && authSession.token) {
      fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1"}/preferences`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...auth.getAuthHeader(),
        },
        body: JSON.stringify({ preferred_language: lang.tag }),
      }).catch(() => {
        // Silent catch for offline or guest mode
      });
    }
  };

  const setLocale = (newLocale: string) => {
    setLocaleState(newLocale);
    localStorage.setItem(STORAGE_KEY_LOCALE, newLocale);
  };

  const setCurrency = (newCurrency: string) => {
    setCurrencyState(newCurrency);
    localStorage.setItem(STORAGE_KEY_CURRENCY, newCurrency);
  };

  const setCalendar = (newCalendar: "gregory" | "islamic-umalqura" | "persian" | "hebrew") => {
    setCalendarState(newCalendar);
    localStorage.setItem(STORAGE_KEY_CALENDAR, newCalendar);
  };

  const setAutoDetectEnabled = (enabled: boolean) => {
    setAutoDetectEnabledState(enabled);
    if (!enabled) {
      localStorage.setItem(STORAGE_KEY_MANUAL, "true");
      setManualOverrideSet(true);
    }
  };

  const t = (key: string, fallback?: string): string => {
    return translate(key, language.tag, fallback);
  };

  return (
    <I18nContext.Provider
      value={{
        language,
        direction: language.direction,
        locale,
        currency,
        calendar,
        autoDetectEnabled,
        manualOverrideSet,
        setLanguage,
        setLocale,
        setCurrency,
        setCalendar,
        setAutoDetectEnabled,
        t,
        formatNumber: (v, opt) => formatNumber(v, { locale, ...opt }),
        formatCurrency: (amt, code) => formatCurrency(amt, code || currency, locale),
        formatDate: (d, opt) => formatDate(d, { locale, calendar, ...opt }),
        formatGPA: (gpa, scale) => formatGPA(gpa, scale, locale),
      }}
    >
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return context;
}
