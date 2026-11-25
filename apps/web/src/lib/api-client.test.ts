import test from "node:test";
import assert from "node:assert/strict";
import { auth, AuthManager, mockDevSession } from "./auth/index.ts";
import { getLanguageByTag, isRTLLanguage, searchLanguages } from "./i18n/languages.ts";
import { formatNumber, formatCurrency, formatGPA } from "./i18n/formatters.ts";
import { translate } from "./i18n/translations.ts";

test("AuthManager returns active development session when in mock mode", () => {
  const authInstance = AuthManager.getInstance();
  const session = authInstance.getSession();
  assert.equal(session.isAuthenticated, true);
  assert.equal(session.user?.email, "dev.student@uniglobe.edu");
  assert.equal(session.user?.role, "student");
});

test("AuthManager provides correct Bearer authorization header", () => {
  const headers = auth.getAuthHeader();
  assert.ok(headers.Authorization);
  assert.equal(headers.Authorization, "Bearer dev_token");
});

test("Dual pathway model supports both first-year and transfer modes", () => {
  const allowedTypes = ["first_year", "transfer", "both", "undecided"];
  assert.ok(allowedTypes.includes("first_year"));
  assert.ok(allowedTypes.includes("transfer"));
  assert.ok(allowedTypes.includes("both"));
  assert.equal(allowedTypes.length, 4);
});

test("Language registry correctly resolves BCP 47 tags and RTL directionality", () => {
  const ht = getLanguageByTag("ht-HT");
  assert.equal(ht.tag, "ht-HT");
  assert.equal(ht.nativeName, "Kreyòl Ayisyen");
  assert.equal(ht.direction, "ltr");
  assert.equal(ht.tier, "fully_supported");

  const ar = getLanguageByTag("ar-SA");
  assert.equal(ar.direction, "rtl");
  assert.equal(isRTLLanguage("ar-SA"), true);
  assert.equal(isRTLLanguage("he-IL"), true);
  assert.equal(isRTLLanguage("en-US"), false);

  const searchResults = searchLanguages("Creole");
  assert.ok(searchResults.some((l) => l.tag === "ht-HT"));
});

test("Regional formatters isolate currency and locale from language", () => {
  // Format numbers
  const formattedUs = formatNumber(1250000.5, { locale: "en-US" });
  assert.equal(formattedUs, "1,250,000.5");

  // Format currency: Changing currency does not change amount
  const tuitionUsd = formatCurrency(14500, "USD", "en-US");
  assert.ok(tuitionUsd.includes("14,500"));

  const tuitionHtg = formatCurrency(14500, "HTG", "en-US");
  assert.ok(tuitionHtg.includes("14,500"));

  // Academic GPA formatting preserves exact scale
  const gpa = formatGPA(3.88, 4.0, "en-US");
  assert.equal(gpa, "3.88 / 4.0");
});

test("Core UI translations accurately resolve for Haitian Creole, Spanish, and Arabic", () => {
  const titleHt = translate("brand.tagline", "ht-HT");
  assert.ok(titleHt.includes("PWOFIL ETIDYAN"));

  const navTransferHt = translate("nav.transfer", "ht-HT");
  assert.equal(navTransferHt, "Pòtay Transfè");

  const disclaimerAr = translate("doc.machine_disclaimer", "ar-SA");
  assert.ok(disclaimerAr.length > 5);

  const fallback = translate("non_existent_key", "en-US", "Default Fallback");
  assert.equal(fallback, "Default Fallback");
});

test("Homepage headline and CTA buttons translate accurately into Spanish, French, Haitian Creole, and Arabic", () => {
  // Spanish (es-419 and regional es-MX / es)
  assert.equal(translate("home.hero_title_1", "es-419"), "Un perfil de estudiante.");
  assert.equal(translate("home.hero_title_2", "es-419"), "Todas las universidades. Una plataforma global.");
  assert.equal(translate("home.hero_title_1", "es-MX"), "Un perfil de estudiante.");
  assert.equal(translate("home.hero_title_2", "es-ES"), "Todas las universidades. Una plataforma global.");
  assert.equal(translate("home.cta_transfer", "es-419"), "Comenzar como estudiante de transferencia");
  assert.equal(translate("home.cta_first_year", "es-419"), "Comenzar como estudiante de primer año");
  assert.equal(translate("nav.student_os", "es-419"), "Sistema del Estudiante");

  // French (fr-FR)
  assert.equal(translate("home.hero_title_1", "fr-FR"), "Un profil étudiant.");
  assert.equal(translate("home.hero_title_2", "fr-FR"), "Chaque université. Une plateforme mondiale.");
  assert.equal(translate("home.cta_transfer", "fr-FR"), "Commencer comme étudiant de transfert");

  // Haitian Creole (ht-HT)
  assert.equal(translate("home.hero_title_1", "ht-HT"), "Yon sèl pwofil etidyan.");
  assert.equal(translate("home.hero_title_2", "ht-HT"), "Chak inivèsite. Yon platfòm mondyal.");
  assert.equal(translate("home.cta_transfer", "ht-HT"), "Kòmanse kòm etidyan transfè");

  // Arabic (ar-SA)
  assert.equal(translate("home.hero_title_1", "ar-SA"), "ملف طالب واحد.");
  assert.equal(translate("home.hero_title_2", "ar-SA"), "كل جامعة. منصة عالمية واحدة.");
});

test("Milestone 5 matching navigation and disclaimer keys translate cleanly across LTR and RTL", () => {
  assert.equal(translate("nav.matching", "en-US"), "Match Engine");
  assert.equal(translate("nav.matching", "es-419"), "Motor de Compatibilidad");
  assert.equal(translate("nav.matching", "fr-FR"), "Moteur de Compatibilité");
  assert.equal(translate("nav.matching", "ht-HT"), "Motè Konpatibilite");
  assert.equal(translate("nav.matching", "ar-SA"), "محرك المطابقة");

  assert.ok(translate("matching.title", "ar-SA").includes("رباعي الأبعاد"));
  assert.ok(translate("matching.disclaimer", "ht-HT").includes("jamè pwobabilite"));
  assert.ok(translate("matching.run_button", "es-MX") === "Ejecutar Análisis");
});

test("Milestone 6 RAG counselor keys translate across Haitian Creole, French, Spanish, Arabic RTL, and English", () => {
  assert.ok(translate("counselor.title", "ht-HT").includes("Konseye Admisyon"));
  assert.ok(translate("counselor.title", "ar-SA").includes("مستشار القبول"));
  assert.ok(translate("counselor.subtitle", "fr-FR").includes("pgvector"));
  assert.equal(translate("counselor.send", "es-419"), "Enviar");
  assert.equal(translate("counselor.new_chat", "ar-SA"), "محادثة جديدة");
});

test("Milestone 7 routing and application lifecycle keys translate cleanly across LTR and RTL", () => {
  assert.equal(translate("nav.applications", "en-US"), "Applications & Routing");
  assert.equal(translate("nav.applications", "fr-FR"), "Candidatures et Portails");
  assert.equal(translate("nav.applications", "ar-SA"), "الطلبات والتوجيه الرسمي");
  assert.ok(translate("applications.launch_portal", "ht-HT").includes("Pòtay Ofisyèl"));
  assert.ok(translate("applications.report_submitted", "es-419").includes("Externamente"));
  assert.ok(translate("applications.title", "ar-SA").includes("التقديم"));
});

test("Operations console keys translate cleanly across Arabic RTL, French, Spanish, Haitian Creole, and English", () => {
  assert.equal(translate("ops.title", "en-US"), "Verification & Trust Operations Console");
  assert.equal(translate("ops.title", "ar-SA"), "وحدة عمليات التحقق والثقة");
  assert.equal(translate("ops.role_verifier", "ar-SA"), "مدقق البيانات");
  assert.equal(translate("ops.role_verifier", "fr-FR"), "Vérificateur");
  assert.equal(translate("ops.btn_verify_url", "ht-HT"), "Verifye Lyen");
  assert.equal(translate("ops.rt_filter_manual_review", "es-419"), "Revisión Manual y Pendientes");
  assert.ok(translate("ops.forbidden_title", "ar-SA").includes("403"));
});

test("Phase 4 Financial & Credential keys translate cleanly across LTR and RTL", () => {
  assert.equal(translate("nav.financial", "en-US"), "Financial & Aid");
  assert.equal(translate("nav.financial", "ar-SA"), "المنح والتكلفة الصافية");
  assert.equal(translate("nav.credentials", "ht-HT"), "Ekivalans Diplòm");
  assert.equal(translate("cred.title", "fr-FR"), "Intelligence des Diplômes Internationaux & Équivalences");
  // Step 2 secondary labels & statuses localized cleanly in Arabic RTL (zero English leftovers)
  assert.equal(translate("fin.stat_insufficient", "ar-SA"), "معلومات غير كافية");
  assert.equal(translate("fin.stat_review", "ar-SA"), "يتطلب مراجعة يدوية");
  assert.equal(translate("fin.net_coa", "ar-SA"), "إجمالي تكلفة الحضور");
  assert.equal(translate("fin.net_est_price", "ar-SA"), "صافي التكلفة السنوية التقديرية (غير مضمونة)");
  assert.equal(translate("fin.fresh_expired", "ar-SA"), "منتهي الصلاحية");
  assert.equal(translate("fin.amount_unpublished", "en-US"), "Amount varies / not published");
  assert.equal(translate("fin.amount_unpublished", "ar-SA"), "القيمة متغيرة / غير منشورة رسميًا");
  assert.equal(translate("fin.cycle_closed", "fr-FR"), "Cycle Clôturé");
  assert.equal(translate("fin.cycle_closed", "ht-HT"), "Sik Fèmen");
  assert.equal(translate("fin.cycle_open", "ar-SA"), "مفتوح الآن");
  assert.equal(translate("fin.sponsor_label", "es-419"), "Patrocinador");

  const ALL_10_LOCALES = [
    "en-US",
    "es-419",
    "fr-FR",
    "ht-HT",
    "ar-SA",
    "zh-Hans",
    "hi-IN",
    "pt-BR",
    "ja-JP",
    "de-DE",
  ] as const;
  const BATCH2_REQUIRED_KEYS = [
    "nav.financial",
    "fin.amount_unpublished",
    "fin.cycle_closed",
    "fin.cycle_open",
    "fin.sponsor_label",
    "fin.verified_funding_coverage",
    "fin.verified_funding_detail",
  ] as const;
  for (const locale of ALL_10_LOCALES) {
    for (const key of BATCH2_REQUIRED_KEYS) {
      const value = translate(key, locale);
      assert.ok(value && value.trim().length > 0 && value !== key, `Missing ${key} for ${locale}`);
    }
  }
});




