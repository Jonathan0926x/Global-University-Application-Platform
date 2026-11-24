"use client";

import React, { useState } from "react";
import {
  Globe2,
  Search,
  Check,
  Sparkles,
  SlidersHorizontal,
  X,
  Languages,
  ArrowRightLeft,
  Calendar as CalendarIcon,
  Coins
} from "lucide-react";
import { useI18n } from "@/lib/i18n/context";
import {
  GLOBAL_LANGUAGE_REGISTRY,
  searchLanguages,
  LanguageDefinition,
  TranslationTier
} from "@/lib/i18n/languages";

interface LanguageModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function LanguageModal({ isOpen, onClose }: LanguageModalProps) {
  const {
    language,
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
    t
  } = useI18n();

  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"languages" | "regional">("languages");

  if (!isOpen) return null;

  const filteredLanguages = searchLanguages(searchQuery);

  const getTierBadge = (tier: TranslationTier) => {
    switch (tier) {
      case "fully_supported":
        return (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
            Fully Supported
          </span>
        );
      case "beta_preview":
        return (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
            Beta Preview
          </span>
        );
      case "discovery":
        return (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
            Catalog Registered
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-50 dark:bg-brand-950/40 border border-brand-200 dark:border-brand-800 flex items-center justify-center text-brand-600 dark:text-brand-400">
              <Globe2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                Global Language & Regional Settings
              </h2>
              <p className="text-xs text-slate-500">
                Choose your preferred language and regional formatting conventions.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab switch */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 px-6 gap-6 text-xs font-semibold">
          <button
            onClick={() => setActiveTab("languages")}
            className={`py-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "languages"
                ? "border-brand-600 text-brand-600 dark:text-brand-400"
                : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <Languages className="w-4 h-4" /> Global Language Library ({filteredLanguages.length})
          </button>
          <button
            onClick={() => setActiveTab("regional")}
            className={`py-3 border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "regional"
                ? "border-brand-600 text-brand-600 dark:text-brand-400"
                : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <SlidersHorizontal className="w-4 h-4" /> Regional Formats & Calendars
          </button>
        </div>

        {/* Tab Content: Languages */}
        {activeTab === "languages" && (
          <div className="flex-1 overflow-hidden flex flex-col p-6 space-y-4">
            {/* Search Box */}
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search languages by English name, native script, or BCP 47 code..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            {/* Language List */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1 divide-y divide-slate-100 dark:divide-slate-850">
              {filteredLanguages.map((lang) => {
                const isSelected = language.tag === lang.tag;
                return (
                  <div
                    key={lang.tag}
                    onClick={() => {
                      setLanguage(lang.tag);
                      onClose();
                    }}
                    className={`pt-2 pb-2 px-3 rounded-xl flex items-center justify-between cursor-pointer transition-all ${
                      isSelected
                        ? "bg-brand-50/70 dark:bg-brand-950/30 border border-brand-200 dark:border-brand-800"
                        : "hover:bg-slate-50 dark:hover:bg-slate-850/60"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xl shrink-0">{lang.flagEmoji}</span>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-slate-900 dark:text-white">
                            {lang.nativeName}
                          </span>
                          <span className="text-xs text-slate-500">
                            ({lang.englishName})
                          </span>
                          {lang.direction === "rtl" && (
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                              RTL
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5 flex items-center gap-2">
                          <span>BCP 47: {lang.tag}</span>
                          <span>&bull;</span>
                          <span>Script: {lang.script}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {getTierBadge(lang.tier)}
                      {isSelected && (
                        <div className="w-6 h-6 rounded-full bg-brand-600 text-white flex items-center justify-center">
                          <Check className="w-3.5 h-3.5" />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Preferences note */}
            <div className="pt-2 border-t border-slate-100 dark:border-slate-850 text-xs text-slate-500 flex items-center justify-between">
              <span>{manualOverrideSet ? "Manual preference locked" : "Browser auto-detect active"}</span>
              <button
                onClick={() => setAutoDetectEnabled(!autoDetectEnabled)}
                className="text-brand-600 dark:text-brand-400 font-semibold hover:underline"
              >
                {autoDetectEnabled ? "Disable Auto-Detect" : "Enable Auto-Detect"}
              </button>
            </div>
          </div>
        )}

        {/* Tab Content: Regional Formats */}
        {activeTab === "regional" && (
          <div className="p-6 space-y-6 overflow-y-auto">
            {/* Locale Setting */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-1.5">
                <SlidersHorizontal className="w-3.5 h-3.5 text-brand-600" />
                Regional Formatting Locale
              </label>
              <select
                value={locale}
                onChange={(e) => setLocale(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-850 text-sm"
              >
                <option value="en-US">United States (en-US) — 1,234.56 &bull; MM/DD/YYYY</option>
                <option value="fr-FR">France (fr-FR) — 1 234,56 &bull; DD/MM/YYYY</option>
                <option value="ht-HT">Haiti (ht-HT) — 1,234.56 &bull; DD/MM/YYYY</option>
                <option value="ar-SA">Saudi Arabia (ar-SA) — ١٬٢٣٤٫٥٦ &bull; YYYY/MM/DD</option>
                <option value="de-DE">Germany (de-DE) — 1.234,56 &bull; DD.MM.YYYY</option>
                <option value="hi-IN">India (hi-IN) — 1,23,456.00 &bull; DD/MM/YYYY</option>
              </select>
              <p className="text-[11px] text-slate-500 mt-1">
                Controls decimal and thousand separators and regional date patterns.
              </p>
            </div>

            {/* Independent Currency Setting */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-1.5">
                <Coins className="w-3.5 h-3.5 text-brand-600" />
                Display Reference Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-850 text-sm"
              >
                <option value="USD">USD ($) — US Dollar</option>
                <option value="EUR">EUR (€) — Euro</option>
                <option value="HTG">HTG (G) — Haitian Gourde</option>
                <option value="CAD">CAD ($) — Canadian Dollar</option>
                <option value="GBP">GBP (£) — British Pound</option>
                <option value="INR">INR (₹) — Indian Rupee</option>
                <option value="SAR">SAR (﷼) — Saudi Riyal</option>
              </select>
              <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-1">
                Important: Language and display currency are strictly isolated. Changing currency never silently recalculates official university tuition costs.
              </p>
            </div>

            {/* Regional Calendar */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-1.5">
                <CalendarIcon className="w-3.5 h-3.5 text-brand-600" />
                Regional Calendar System
              </label>
              <select
                value={calendar}
                onChange={(e) => setCalendar(e.target.value as any)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-850 text-sm"
              >
                <option value="gregory">Gregorian Calendar (Standard Global)</option>
                <option value="islamic-umalqura">Islamic Hijri Calendar (Umm al-Qura)</option>
                <option value="persian">Solar Hijri (Persian Calendar)</option>
                <option value="hebrew">Hebrew Calendar</option>
              </select>
            </div>

            <div className="flex justify-end pt-4">
              <button
                onClick={onClose}
                className="px-5 py-2 rounded-xl bg-brand-600 text-white text-xs font-semibold hover:bg-brand-700"
              >
                Apply & Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
