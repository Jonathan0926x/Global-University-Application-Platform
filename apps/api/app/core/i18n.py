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
        direction="ltr", script="Latn", default_locale="vi-VN", default_currency="VND", tier="fully_supported", flag_emoji="🇻🇳"
    ),
    LanguageInfo(
        tag="he-IL", iso639_1="he", iso639_3="heb", english_name="Hebrew", native_name="עברית",
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
        direction="ltr", script="Jpan", default_locale="ja-JP", default_currency="JPY", tier="beta_preview", flag_emoji="🇯🇵"
    ),
    LanguageInfo(
        tag="de-DE", iso639_1="de", iso639_3="deu", english_name="German", native_name="Deutsch",
        direction="ltr", script="Latn", default_locale="de-DE", default_currency="EUR", tier="beta_preview", flag_emoji="🇩🇪"
    ),
    LanguageInfo(
        tag="uk-UA", iso639_1="uk", iso639_3="ukr", english_name="Ukrainian", native_name="Українська",
        direction="ltr", script="Cyrl", default_locale="uk-UA", default_currency="UAH", tier="beta_preview", flag_emoji="🇺🇦"
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
