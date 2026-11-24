/**
 * Core UI Internationalization Dictionary
 *
 * Covers core platform navigation, application workflows, transfer articulators,
 * document vault terminology, and AI counselor interactions.
 */

export const UI_TRANSLATIONS: Record<string, Record<string, string>> = {
  // Brand & General
  "brand.tagline": {
    "en-US": "ONE STUDENT PROFILE. EVERY UNIVERSITY. ONE GLOBAL PLATFORM.",
    "ht-HT": "YON SÈL PWOFIL ETIDYAN. CHAK INIVÈSITE. YON PLATFÒM MONDIYAL.",
    "es-419": "UN PERFIL DE ESTUDIANTE. CADA UNIVERSIDAD. UNA PLATAFORMA GLOBAL.",
    "fr-FR": "UN PROFIL ÉTUDIANT. CHAQUE UNIVERSITÉ. UNE PLATEFORME MONDIALE.",
    "ar-SA": "ملف طالب واحد. كل جامعة. منصة عالمية واحدة.",
    "zh-Hans": "一份学生档案。遍及全球大学。统一全球平台。",
    "hi-IN": "एक छात्र प्रोफ़ाइल। हर विश्वविद्यालय। एक वैश्विक मंच।",
  },
  "nav.student_os": {
    "en-US": "Student OS",
    "ht-HT": "Sistèm Etidyan (OS)",
    "es-419": "Sistema de Estudiante",
    "fr-FR": "Système Étudiant (OS)",
    "ar-SA": "نظام الطالب",
    "zh-Hans": "学生操作系统",
    "hi-IN": "छात्र ओएस",
  },
  "nav.first_year": {
    "en-US": "First-Year Portal",
    "ht-HT": "Pòtay Premye Ane",
    "es-419": "Portal de Primer Año",
    "fr-FR": "Portail Première Année",
    "ar-SA": "بوابة السنة الأولى",
    "zh-Hans": "大一申请门户",
    "hi-IN": "प्रथम वर्ष पोर्टल",
  },
  "nav.transfer": {
    "en-US": "Transfer Portal",
    "ht-HT": "Pòtay Transfè",
    "es-419": "Portal de Transferencia",
    "fr-FR": "Portail de Transfert",
    "ar-SA": "بوابة التحويل الجامعي",
    "zh-Hans": "转学申请门户",
    "hi-IN": "स्थानांतरण पोर्टल",
  },
  "nav.universities": {
    "en-US": "Universities",
    "ht-HT": "Inivèsite yo",
    "es-419": "Universidades",
    "fr-FR": "Universités",
    "ar-SA": "الجامعات",
    "zh-Hans": "全球大学",
    "hi-IN": "विश्वविद्यालय",
  },
  "nav.profile": {
    "en-US": "Universal Profile",
    "ht-HT": "Pwofil Inivèsèl",
    "es-419": "Perfil Universal",
    "fr-FR": "Profil Universel",
    "ar-SA": "الملف التعريفي الشامل",
    "zh-Hans": "通用学生档案",
    "hi-IN": "सार्वभौमिक प्रोफ़ाइल",
  },
  "nav.counselor": {
    "en-US": "AI Admissions Counselor",
    "ht-HT": "Konseye Admisyon AI",
    "es-419": "Consejero de Admisiones IA",
    "fr-FR": "Conseiller d'Admission IA",
    "ar-SA": "مستشار القبول الذكي",
    "zh-Hans": "AI 招生顾问",
    "hi-IN": "एआई प्रवेश सलाहकार",
  },
  "nav.documents": {
    "en-US": "Document Vault",
    "ht-HT": "Kòf Dokiman",
    "es-419": "Bóveda de Documentos",
    "fr-FR": "Coffre-fort de Documents",
    "ar-SA": "خزينة المستندات",
    "zh-Hans": "文档保险库",
    "hi-IN": "दस्तावेज़ तिजोरी",
  },

  // Document Vault & Translation Integrity
  "doc.original_preserved": {
    "en-US": "Original Document Preserved & Verified",
    "ht-HT": "Dokiman Orijinal Konsève & Verifye",
    "es-419": "Documento Original Conservado y Verificado",
    "fr-FR": "Document Original Préservé et Vérifié",
    "ar-SA": "المستند الأصلي محفوظ ومتحقق منه",
    "zh-Hans": "原始文件已保留并验证",
    "hi-IN": "मूल दस्तावेज़ संरक्षित और सत्यापित",
  },
  "doc.machine_disclaimer": {
    "en-US": "Machine Translation — Not Certified as an Official University Transcript",
    "ht-HT": "Tradiksyon Otomatik — Li Pa Yon Relve Nòt Ofisyèl Sètifye pa Inivèsite a",
    "es-419": "Traducción Automática — No Certificada como Expediente Oficial Universitario",
    "fr-FR": "Traduction Automatique — Non Certifiée comme Relevé de Notes Officiel",
    "ar-SA": "ترجمة آلية — غير معتمدة كسجل أكاديمي رسمي",
    "zh-Hans": "机器翻译 — 未经大学官方认证的正式成绩单",
    "hi-IN": "मशीनी अनुवाद — आधिकारिक विश्वविद्यालय प्रतिलेख के रूप में प्रमाणित नहीं",
  },
  "doc.compare_side_by_side": {
    "en-US": "Compare Original and Translation Side-by-Side",
    "ht-HT": "Konpare Orijinal ak Tradiksyon Kòt a Kòt",
    "es-419": "Comparar Original y Traducción Lado a Lado",
    "fr-FR": "Comparer l'Original et la Traduction Côte à Côte",
    "ar-SA": "مقارنة الأصل والترجمة جنبًا إلى جنب",
    "zh-Hans": "左右对比原文与译文",
    "hi-IN": "मूल और अनुवाद की साथ-साथ तुलना करें",
  },

  // Confidence & Verification Tiers
  "confidence.high": {
    "en-US": "High Confidence",
    "ht-HT": "Konfyans Segondè",
    "es-419": "Alta Confianza",
    "fr-FR": "Haute Confiance",
    "ar-SA": "ثقة عالية",
    "zh-Hans": "高度可信",
    "hi-IN": "उच्च विश्वास",
  },
  "confidence.needs_review": {
    "en-US": "Needs Review",
    "ht-HT": "Mande Revizyon",
    "es-419": "Requiere Revisión",
    "fr-FR": "À Vérifier",
    "ar-SA": "يتطلب مراجعة",
    "zh-Hans": "待人工复核",
    "hi-IN": "समीक्षा की आवश्यकता",
  },
  "confidence.uncertain": {
    "en-US": "Uncertain Extraction",
    "ht-HT": "Ekstraksyon Ensèten",
    "es-419": "Extracción Incierta",
    "fr-FR": "Extraction Incertaine",
    "ar-SA": "استخراج غير مؤكد",
    "zh-Hans": "提取存在不确定性",
    "hi-IN": "अनिश्चित निष्कर्षण",
  },
  "confidence.human_verification": {
    "en-US": "Human Verification Required",
    "ht-HT": "Verifikasyon Imèn Obligatwa",
    "es-419": "Verificación Humana Requerida",
    "fr-FR": "Vérification Humaine Requise",
    "ar-SA": "التحقق البشري مطلوب",
    "zh-Hans": "需人工核实验证",
    "hi-IN": "मानव सत्यापन अनिवार्य",
  },
};

export function translate(key: string, languageTag: string, fallback?: string): string {
  const entry = UI_TRANSLATIONS[key];
  if (!entry) return fallback || key;
  if (entry[languageTag]) return entry[languageTag];
  
  // Try 2-letter ISO prefix
  const prefix = languageTag.split("-")[0];
  const matchedKey = Object.keys(entry).find((k) => k.startsWith(prefix));
  if (matchedKey && entry[matchedKey]) return entry[matchedKey];

  return entry["en-US"] || fallback || key;
}
