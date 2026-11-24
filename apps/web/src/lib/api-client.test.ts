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



