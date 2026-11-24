"""
UniGlobe Backend Internationalization Registry & BCP 47 Schema
"""
from typing import Optional, List, Dict
from pydantic import BaseModel


class LanguageInfo(BaseModel):
    tag: str
    iso639_1: str
    iso639_3: str
    english_name: str
    native_name: str
    direction: str  # "ltr" or "rtl"
    script: str
    default_locale: str
    default_currency: str
    tier: str  # "fully_supported", "beta_preview", "discovery"
    flag_emoji: str


GLOBAL_LANGUAGES: List[LanguageInfo] = [
    LanguageInfo(
        tag="en-US", iso639_1="en", iso639_3="eng", english_name="English (US)", native_name="English",
        direction="ltr", script="Latn", default_locale="en-US", default_currency="USD", tier="fully_supported", flag_emoji="🇺🇸"
    ),
    LanguageInfo(
        tag="ht-HT", iso639_1="ht", iso639_3="hat", english_name="Haitian Creole", native_name="Kreyòl Ayisyen",
        direction="ltr", script="Latn", default_locale="ht-HT", default_currency="HTG", tier="fully_supported", flag_emoji="🇭🇹"
    ),
    LanguageInfo(
        tag="es-419", iso639_1="es", iso639_3="spa", english_name="Spanish (Latin America)", native_name="Español",
        direction="ltr", script="Latn", default_locale="es-419", default_currency="USD", tier="fully_supported", flag_emoji="🇲🇽"
    ),
    LanguageInfo(
        tag="fr-FR", iso639_1="fr", iso639_3="fra", english_name="French", native_name="Français",
        direction="ltr", script="Latn", default_locale="fr-FR", default_currency="EUR", tier="fully_supported", flag_emoji="🇫🇷"
    ),
    LanguageInfo(
        tag="ar-SA", iso639_1="ar", iso639_3="ara", english_name="Arabic", native_name="العربية",
        direction="rtl", script="Arab", default_locale="ar-SA", default_currency="SAR", tier="fully_supported", flag_emoji="🇸🇦"
    ),
    LanguageInfo(
        tag="zh-Hans", iso639_1="zh", iso639_3="zho", english_name="Chinese (Simplified)", native_name="简体中文",
        direction="ltr", script="Hans", default_locale="zh-CN", default_currency="CNY", tier="fully_supported", flag_emoji="🇨🇳"
    ),
    LanguageInfo(
        tag="hi-IN", iso639_1="hi", iso639_3="hin", english_name="Hindi", native_name="हिन्दी",
        direction="ltr", script="Deva", default_locale="hi-IN", default_currency="INR", tier="fully_supported", flag_emoji="🇮🇳"
    ),
    LanguageInfo(
        tag="pt-BR", iso639_1="pt", iso639_3="por", english_name="Portuguese (Brazil)", native_name="Português",
        direction="ltr", script="Latn", default_locale="pt-BR", default_currency="BRL", tier="fully_supported", flag_emoji="🇧🇷"
    ),
    LanguageInfo(
        tag="vi-VN", iso639_1="vi", iso639_3="vie", english_name="Vietnamese", native_name="Tiếng Việt",
        direction="ltr", script="Latn", default_locale="vi-VN", default_currency="VND", tier="beta_preview", flag_emoji="🇻🇳"
    ),
    LanguageInfo(
        tag="he-IL", iso639_1="he", iso639_3="heb", english_name="Hebrew", native_name="עבריت",
        direction="rtl", script="Hebr", default_locale="he-IL", default_currency="ILS", tier="beta_preview", flag_emoji="🇮🇱"
    ),
    LanguageInfo(
        tag="fa-IR", iso639_1="fa", iso639_3="fas", english_name="Persian (Farsi)", native_name="فارسی",
        direction="rtl", script="Arab", default_locale="fa-IR", default_currency="IRR", tier="beta_preview", flag_emoji="🇮🇷"
    ),
    LanguageInfo(
        tag="ur-PK", iso639_1="ur", iso639_3="urd", english_name="Urdu", native_name="اردو",
        direction="rtl", script="Arab", default_locale="ur-PK", default_currency="PKR", tier="beta_preview", flag_emoji="🇵🇰"
    ),
    LanguageInfo(
        tag="ko-KR", iso639_1="ko", iso639_3="kor", english_name="Korean", native_name="한국어",
        direction="ltr", script="Kore", default_locale="ko-KR", default_currency="KRW", tier="beta_preview", flag_emoji="🇰🇷"
    ),
    LanguageInfo(
        tag="ja-JP", iso639_1="ja", iso639_3="jpn", english_name="Japanese", native_name="日本語",
        direction="ltr", script="Jpan", default_locale="ja-JP", default_currency="JPY", tier="fully_supported", flag_emoji="🇯🇵"
    ),
    LanguageInfo(
        tag="de-DE", iso639_1="de", iso639_3="deu", english_name="German", native_name="Deutsch",
        direction="ltr", script="Latn", default_locale="de-DE", default_currency="EUR", tier="fully_supported", flag_emoji="🇩🇪"
    ),
    LanguageInfo(
        tag="uk-UA", iso639_1="uk", iso639_3="ukr", english_name="Ukrainian", native_name="Українська",
        direction="ltr", script="Cyrl", default_locale="uk-UA", default_currency="UAH", tier="beta_preview", flag_emoji="🇺🇦"
    ),
    LanguageInfo(
        tag="tl-PH", iso639_1="tl", iso639_3="tgl", english_name="Tagalog", native_name="Wikang Filipino",
        direction="ltr", script="Latn", default_locale="fil-PH", default_currency="PHP", tier="beta_preview", flag_emoji="🇵🇭"
    ),
    LanguageInfo(
        tag="sw-KE", iso639_1="sw", iso639_3="swa", english_name="Swahili", native_name="Kiswahili",
        direction="ltr", script="Latn", default_locale="sw-KE", default_currency="KES", tier="beta_preview", flag_emoji="🇰🇪"
    ),
    LanguageInfo(
        tag="bn-BD", iso639_1="bn", iso639_3="ben", english_name="Bengali", native_name="বাংলা",
        direction="ltr", script="Beng", default_locale="bn-BD", default_currency="BDT", tier="discovery", flag_emoji="🇧🇩"
    ),
    LanguageInfo(
        tag="tr-TR", iso639_1="tr", iso639_3="tur", english_name="Turkish", native_name="Türkçe",
        direction="ltr", script="Latn", default_locale="tr-TR", default_currency="TRY", tier="discovery", flag_emoji="🇹🇷"
    ),
    LanguageInfo(
        tag="id-ID", iso639_1="id", iso639_3="ind", english_name="Indonesian", native_name="Bahasa Indonesia",
        direction="ltr", script="Latn", default_locale="id-ID", default_currency="IDR", tier="discovery", flag_emoji="🇮🇩"
    ),
    LanguageInfo(
        tag="it-IT", iso639_1="it", iso639_3="ita", english_name="Italian", native_name="Italiano",
        direction="ltr", script="Latn", default_locale="it-IT", default_currency="EUR", tier="discovery", flag_emoji="🇮🇹"
    ),
    LanguageInfo(
        tag="ru-RU", iso639_1="ru", iso639_3="rus", english_name="Russian", native_name="Русский",
        direction="ltr", script="Cyrl", default_locale="ru-RU", default_currency="RUB", tier="discovery", flag_emoji="🇷🇺"
    ),
    LanguageInfo(
        tag="pl-PL", iso639_1="pl", iso639_3="pol", english_name="Polish", native_name="Polski",
        direction="ltr", script="Latn", default_locale="pl-PL", default_currency="PLN", tier="discovery", flag_emoji="🇵🇱"
    ),
    LanguageInfo(
        tag="am-ET", iso639_1="am", iso639_3="amh", english_name="Amharic", native_name="አማርኛ",
        direction="ltr", script="Ethi", default_locale="am-ET", default_currency="ETB", tier="discovery", flag_emoji="🇪🇹"
    ),
    LanguageInfo(
        tag="yo-NG", iso639_1="yo", iso639_3="yor", english_name="Yoruba", native_name="Èdè Yorùbá",
        direction="ltr", script="Latn", default_locale="yo-NG", default_currency="NGN", tier="discovery", flag_emoji="🇳🇬"
    ),
    LanguageInfo(
        tag="nl-NL", iso639_1="nl", iso639_3="nld", english_name="Dutch", native_name="Nederlands",
        direction="ltr", script="Latn", default_locale="nl-NL", default_currency="EUR", tier="discovery", flag_emoji="🇳🇱"
    ),
    LanguageInfo(
        tag="el-GR", iso639_1="el", iso639_3="ell", english_name="Greek", native_name="Ελληνικά",
        direction="ltr", script="Grek", default_locale="el-GR", default_currency="EUR", tier="discovery", flag_emoji="🇬🇷"
    ),
    LanguageInfo(
        tag="sv-SE", iso639_1="sv", iso639_3="swe", english_name="Swedish", native_name="Svenska",
        direction="ltr", script="Latn", default_locale="sv-SE", default_currency="SEK", tier="discovery", flag_emoji="🇸🇪"
    ),
    LanguageInfo(
        tag="th-TH", iso639_1="th", iso639_3="tha", english_name="Thai", native_name="ไทย",
        direction="ltr", script="Thai", default_locale="th-TH", default_currency="THB", tier="discovery", flag_emoji="🇹🇭"
    ),
    LanguageInfo(
        tag="ro-RO", iso639_1="ro", iso639_3="ron", english_name="Romanian", native_name="Română",
        direction="ltr", script="Latn", default_locale="ro-RO", default_currency="RON", tier="discovery", flag_emoji="🇷🇴"
    ),
    LanguageInfo(
        tag="hu-HU", iso639_1="hu", iso639_3="hun", english_name="Hungarian", native_name="Magyar",
        direction="ltr", script="Latn", default_locale="hu-HU", default_currency="HUF", tier="discovery", flag_emoji="🇭🇺"
    ),
    LanguageInfo(
        tag="cs-CZ", iso639_1="cs", iso639_3="ces", english_name="Czech", native_name="Čeština",
        direction="ltr", script="Latn", default_locale="cs-CZ", default_currency="CZK", tier="discovery", flag_emoji="🇨🇿"
    ),
    LanguageInfo(
        tag="ta-IN", iso639_1="ta", iso639_3="tam", english_name="Tamil", native_name="தமிழ்",
        direction="ltr", script="Taml", default_locale="ta-IN", default_currency="INR", tier="discovery", flag_emoji="🇮🇳"
    ),
    LanguageInfo(
        tag="ms-MY", iso639_1="ms", iso639_3="msa", english_name="Malay", native_name="Bahasa Melayu",
        direction="ltr", script="Latn", default_locale="ms-MY", default_currency="MYR", tier="discovery", flag_emoji="🇲🇾"
    ),
    LanguageInfo(
        tag="zh-Hant", iso639_1="zh", iso639_3="zho", english_name="Chinese (Traditional)", native_name="繁體中文",
        direction="ltr", script="Hant", default_locale="zh-TW", default_currency="TWD", tier="discovery", flag_emoji="🇹🇼"
    ),
]


def get_language(tag: str) -> LanguageInfo:
    normalized = tag.lower().replace("_", "-")
    for lang in GLOBAL_LANGUAGES:
        if lang.tag.lower() == normalized or lang.iso639_1 == normalized:
            return lang
    return GLOBAL_LANGUAGES[0]  # default en-US


def is_rtl(tag: str) -> bool:
    return get_language(tag).direction == "rtl"
