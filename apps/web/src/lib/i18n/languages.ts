/**
 * UniGlobe Centralized Global Language Library & BCP 47 Registry
 *
 * Implements ISO 639-1 / ISO 639-3 and BCP 47 language tags with:
 * - Native names and English names (searchable)
 * - Directionality (LTR / RTL)
 * - Script system and family
 * - Translation Readiness Tiers:
 *     - "fully_supported": Complete professional UI coverage
 *     - "beta_preview": High coverage with AI translation assist
 *     - "discovery": Catalog registration for student discovery; fallback to English
 */

export type TextDirection = "ltr" | "rtl";

export type TranslationTier = "fully_supported" | "beta_preview" | "discovery";

export interface LanguageDefinition {
  tag: string;             // BCP 47 tag (e.g., 'en-US', 'ht-HT', 'ar-SA')
  iso639_1: string;        // 2-letter code
  iso639_3: string;        // 3-letter code
  englishName: string;     // English display name
  nativeName: string;      // Native endonym
  direction: TextDirection;
  script: string;          // Script code (e.g., 'Latn', 'Arab', 'Deva', 'Hans')
  defaultLocale: string;   // Default formatting locale
  defaultCurrency: string; // Default local currency reference (independent of student tuition currency)
  tier: TranslationTier;
  flagEmoji: string;
}

export const GLOBAL_LANGUAGE_REGISTRY: LanguageDefinition[] = [
  // --- Tier 1: Fully Supported ---
  {
    tag: "en-US",
    iso639_1: "en",
    iso639_3: "eng",
    englishName: "English (US)",
    nativeName: "English",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "en-US",
    defaultCurrency: "USD",
    tier: "fully_supported",
    flagEmoji: "🇺🇸",
  },
  {
    tag: "ht-HT",
    iso639_1: "ht",
    iso639_3: "hat",
    englishName: "Haitian Creole",
    nativeName: "Kreyòl Ayisyen",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "ht-HT",
    defaultCurrency: "HTG",
    tier: "fully_supported",
    flagEmoji: "🇭🇹",
  },
  {
    tag: "es-419",
    iso639_1: "es",
    iso639_3: "spa",
    englishName: "Spanish (Latin America)",
    nativeName: "Español",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "es-419",
    defaultCurrency: "USD",
    tier: "fully_supported",
    flagEmoji: "🇲🇽",
  },
  {
    tag: "fr-FR",
    iso639_1: "fr",
    iso639_3: "fra",
    englishName: "French",
    nativeName: "Français",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "fr-FR",
    defaultCurrency: "EUR",
    tier: "fully_supported",
    flagEmoji: "🇫🇷",
  },
  {
    tag: "ar-SA",
    iso639_1: "ar",
    iso639_3: "ara",
    englishName: "Arabic",
    nativeName: "العربية",
    direction: "rtl",
    script: "Arab",
    defaultLocale: "ar-SA",
    defaultCurrency: "SAR",
    tier: "fully_supported",
    flagEmoji: "🇸🇦",
  },
  {
    tag: "zh-Hans",
    iso639_1: "zh",
    iso639_3: "zho",
    englishName: "Chinese (Simplified)",
    nativeName: "简体中文",
    direction: "ltr",
    script: "Hans",
    defaultLocale: "zh-CN",
    defaultCurrency: "CNY",
    tier: "fully_supported",
    flagEmoji: "🇨🇳",
  },
  {
    tag: "hi-IN",
    iso639_1: "hi",
    iso639_3: "hin",
    englishName: "Hindi",
    nativeName: "हिन्दी",
    direction: "ltr",
    script: "Deva",
    defaultLocale: "hi-IN",
    defaultCurrency: "INR",
    tier: "fully_supported",
    flagEmoji: "🇮🇳",
  },
  {
    tag: "pt-BR",
    iso639_1: "pt",
    iso639_3: "por",
    englishName: "Portuguese (Brazil)",
    nativeName: "Português",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "pt-BR",
    defaultCurrency: "BRL",
    tier: "fully_supported",
    flagEmoji: "🇧🇷",
  },
  {
    tag: "vi-VN",
    iso639_1: "vi",
    iso639_3: "vie",
    englishName: "Vietnamese",
    nativeName: "Tiếng Việt",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "vi-VN",
    defaultCurrency: "VND",
    tier: "fully_supported",
    flagEmoji: "🇻🇳",
  },

  // --- Tier 2: Beta Preview (AI Assisted & In-Verification) ---
  {
    tag: "he-IL",
    iso639_1: "he",
    iso639_3: "heb",
    englishName: "Hebrew",
    nativeName: "עברית",
    direction: "rtl",
    script: "Hebr",
    defaultLocale: "he-IL",
    defaultCurrency: "ILS",
    tier: "beta_preview",
    flagEmoji: "🇮🇱",
  },
  {
    tag: "fa-IR",
    iso639_1: "fa",
    iso639_3: "fas",
    englishName: "Persian (Farsi)",
    nativeName: "فارسی",
    direction: "rtl",
    script: "Arab",
    defaultLocale: "fa-IR",
    defaultCurrency: "IRR",
    tier: "beta_preview",
    flagEmoji: "🇮🇷",
  },
  {
    tag: "ur-PK",
    iso639_1: "ur",
    iso639_3: "urd",
    englishName: "Urdu",
    nativeName: "اردو",
    direction: "rtl",
    script: "Arab",
    defaultLocale: "ur-PK",
    defaultCurrency: "PKR",
    tier: "beta_preview",
    flagEmoji: "🇵🇰",
  },
  {
    tag: "ko-KR",
    iso639_1: "ko",
    iso639_3: "kor",
    englishName: "Korean",
    nativeName: "한국어",
    direction: "ltr",
    script: "Kore",
    defaultLocale: "ko-KR",
    defaultCurrency: "KRW",
    tier: "beta_preview",
    flagEmoji: "🇰🇷",
  },
  {
    tag: "ja-JP",
    iso639_1: "ja",
    iso639_3: "jpn",
    englishName: "Japanese",
    nativeName: "日本語",
    direction: "ltr",
    script: "Jpan",
    defaultLocale: "ja-JP",
    defaultCurrency: "JPY",
    tier: "beta_preview",
    flagEmoji: "🇯🇵",
  },
  {
    tag: "de-DE",
    iso639_1: "de",
    iso639_3: "deu",
    englishName: "German",
    nativeName: "Deutsch",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "de-DE",
    defaultCurrency: "EUR",
    tier: "beta_preview",
    flagEmoji: "🇩🇪",
  },
  {
    tag: "uk-UA",
    iso639_1: "uk",
    iso639_3: "ukr",
    englishName: "Ukrainian",
    nativeName: "Українська",
    direction: "ltr",
    script: "Cyrl",
    defaultLocale: "uk-UA",
    defaultCurrency: "UAH",
    tier: "beta_preview",
    flagEmoji: "🇺🇦",
  },
  {
    tag: "tl-PH",
    iso639_1: "tl",
    iso639_3: "tgl",
    englishName: "Tagalog / Filipino",
    nativeName: "Wikang Filipino",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "fil-PH",
    defaultCurrency: "PHP",
    tier: "beta_preview",
    flagEmoji: "🇵🇭",
  },
  {
    tag: "sw-KE",
    iso639_1: "sw",
    iso639_3: "swa",
    englishName: "Swahili",
    nativeName: "Kiswahili",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "sw-KE",
    defaultCurrency: "KES",
    tier: "beta_preview",
    flagEmoji: "🇰🇪",
  },

  // --- Tier 3: Discovery (Registered & Expansion-Ready) ---
  {
    tag: "bn-BD",
    iso639_1: "bn",
    iso639_3: "ben",
    englishName: "Bengali",
    nativeName: "বাংলা",
    direction: "ltr",
    script: "Beng",
    defaultLocale: "bn-BD",
    defaultCurrency: "BDT",
    tier: "discovery",
    flagEmoji: "🇧🇩",
  },
  {
    tag: "tr-TR",
    iso639_1: "tr",
    iso639_3: "tur",
    englishName: "Turkish",
    nativeName: "Türkçe",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "tr-TR",
    defaultCurrency: "TRY",
    tier: "discovery",
    flagEmoji: "🇹🇷",
  },
  {
    tag: "id-ID",
    iso639_1: "id",
    iso639_3: "ind",
    englishName: "Indonesian",
    nativeName: "Bahasa Indonesia",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "id-ID",
    defaultCurrency: "IDR",
    tier: "discovery",
    flagEmoji: "🇮🇩",
  },
  {
    tag: "it-IT",
    iso639_1: "it",
    iso639_3: "ita",
    englishName: "Italian",
    nativeName: "Italiano",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "it-IT",
    defaultCurrency: "EUR",
    tier: "discovery",
    flagEmoji: "🇮🇹",
  },
  {
    tag: "ru-RU",
    iso639_1: "ru",
    iso639_3: "rus",
    englishName: "Russian",
    nativeName: "Русский",
    direction: "ltr",
    script: "Cyrl",
    defaultLocale: "ru-RU",
    defaultCurrency: "RUB",
    tier: "discovery",
    flagEmoji: "🇷🇺",
  },
  {
    tag: "pl-PL",
    iso639_1: "pl",
    iso639_3: "pol",
    englishName: "Polish",
    nativeName: "Polski",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "pl-PL",
    defaultCurrency: "PLN",
    tier: "discovery",
    flagEmoji: "🇵🇱",
  },
  {
    tag: "am-ET",
    iso639_1: "am",
    iso639_3: "amh",
    englishName: "Amharic",
    nativeName: "አማርኛ",
    direction: "ltr",
    script: "Ethi",
    defaultLocale: "am-ET",
    defaultCurrency: "ETB",
    tier: "discovery",
    flagEmoji: "🇪🇹",
  },
  {
    tag: "yo-NG",
    iso639_1: "yo",
    iso639_3: "yor",
    englishName: "Yoruba",
    nativeName: "Èdè Yorùbá",
    direction: "ltr",
    script: "Latn",
    defaultLocale: "yo-NG",
    defaultCurrency: "NGN",
    tier: "discovery",
    flagEmoji: "🇳🇬",
  },
];

/**
 * Registry Lookup Helpers
 */
export function getLanguageByTag(tag: string): LanguageDefinition {
  const match = GLOBAL_LANGUAGE_REGISTRY.find(
    (lang) => lang.tag.toLowerCase() === tag.toLowerCase() || lang.iso639_1 === tag.toLowerCase()
  );
  return match || GLOBAL_LANGUAGE_REGISTRY[0]; // Fallback to en-US
}

export function searchLanguages(query: string): LanguageDefinition[] {
  if (!query || !query.trim()) return GLOBAL_LANGUAGE_REGISTRY;
  const q = query.toLowerCase().trim();
  return GLOBAL_LANGUAGE_REGISTRY.filter(
    (lang) =>
      lang.englishName.toLowerCase().includes(q) ||
      lang.nativeName.toLowerCase().includes(q) ||
      lang.tag.toLowerCase().includes(q) ||
      lang.iso639_1.toLowerCase().includes(q)
  );
}

export function getRTLTags(): string[] {
  return GLOBAL_LANGUAGE_REGISTRY.filter((l) => l.direction === "rtl").map((l) => l.tag);
}

export function isRTLLanguage(tag: string): boolean {
  return getLanguageByTag(tag).direction === "rtl";
}
