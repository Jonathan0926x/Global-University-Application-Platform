"use client";

import Link from "next/link";
import {
  ArrowRight,
  GraduationCap,
  ArrowRightLeft,
  Globe,
  Compass,
  ShieldCheck,
  Sparkles,
  CheckCircle2,
  Bot,
  FileText
} from "lucide-react";
import { useI18n } from "@/lib/i18n/context";

export default function HomePage() {
  const { t } = useI18n();

  return (
    <div className="relative overflow-hidden">
      {/* Background radial gradient accent */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-gradient-to-tr from-sky-100 via-indigo-50 to-transparent blur-3xl opacity-70" />

      {/* Hero Section */}
      <div className="mx-auto max-w-7xl px-4 pt-16 pb-20 sm:px-6 lg:px-8 lg:pt-24">
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white/80 px-3.5 py-1 text-xs font-medium text-zinc-800 shadow-xs backdrop-blur-xs mb-8">
            <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
            <span>{t("home.badge", "The Global Operating System for University Admissions")}</span>
          </div>

          <h1 className="text-4xl font-extrabold tracking-tight text-zinc-900 sm:text-6xl sm:leading-[1.1]">
            <span>{t("home.hero_title_1", "One Student Profile.")}</span> <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-zinc-900 via-indigo-950 to-zinc-700">
              {t("home.hero_title_2", "Every University. One Global Platform.")}
            </span>
          </h1>

          <p className="mt-6 text-lg leading-relaxed text-zinc-600 sm:text-xl">
            {t(
              "home.hero_subtitle",
              "A student should never navigate the complexity of global higher education alone. Discover universities worldwide, verify transfer course equivalencies, and manage applications from one intelligent workspace."
            )}
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/transfer"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-6 py-3.5 text-sm font-semibold text-white shadow-md hover:bg-zinc-800 transition-all hover:scale-[1.02]"
            >
              <ArrowRightLeft className="h-4 w-4" />
              <span>{t("home.cta_transfer", "Start as Transfer Student")}</span>
              <ArrowRight className="h-4 w-4 opacity-70" />
            </Link>

            <Link
              href="/first-year"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-6 py-3.5 text-sm font-semibold text-zinc-900 shadow-xs hover:bg-zinc-50 transition-all hover:scale-[1.02]"
            >
              <GraduationCap className="h-4 w-4 text-zinc-700" />
              <span>{t("home.cta_first_year", "Start as First-Year Student")}</span>
            </Link>
          </div>

          <div className="mt-8 flex items-center justify-center gap-6 text-xs text-zinc-500 flex-wrap">
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span>{t("home.trust_profile", "Free Universal Profile")}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span>{t("home.trust_articulation", "Verified Articulation")}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span>{t("home.trust_multilingual", "Multilingual Support")}</span>
            </span>
          </div>
        </div>

        {/* Feature Pathways Grid */}
        <div className="mt-24 grid grid-cols-1 gap-6 md:grid-cols-3">
          {/* Pathway 1: Transfer Portal */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-7 shadow-xs hover:shadow-md transition-shadow">
            <div className="h-10 w-10 rounded-xl bg-sky-50 flex items-center justify-center text-sky-600 mb-5">
              <ArrowRightLeft className="h-5 w-5" />
            </div>
            <h3 className="text-lg font-bold text-zinc-900">
              {t("home.feat_transfer_title", "Transfer Intelligence Portal")}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-zinc-600">
              {t(
                "home.feat_transfer_desc",
                "Never lose earned credits. Compare completed courses from community colleges or universities against target institution degree requirements with verified course equivalencies."
              )}
            </p>
            <Link
              href="/transfer"
              className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-sky-600 hover:text-sky-700"
            >
              <span>{t("home.feat_transfer_link", "Explore Transfer Portal")}</span>{" "}
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {/* Pathway 2: First-Year Portal */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-7 shadow-xs hover:shadow-md transition-shadow">
            <div className="h-10 w-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 mb-5">
              <GraduationCap className="h-5 w-5" />
            </div>
            <h3 className="text-lg font-bold text-zinc-900">
              {t("home.feat_fy_title", "First-Year Application Suite")}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-zinc-600">
              {t(
                "home.feat_fy_desc",
                "Prepare once, apply everywhere. Manage secondary transcripts, national examinations (SAT, ACT, Baccalauréat, A-Levels), essays, and recommendation letters from a unified profile."
              )}
            </p>
            <Link
              href="/first-year"
              className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-indigo-600 hover:text-indigo-700"
            >
              <span>{t("home.feat_fy_link", "Explore First-Year Portal")}</span>{" "}
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {/* Pathway 3: Global Discovery */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-7 shadow-xs hover:shadow-md transition-shadow">
            <div className="h-10 w-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600 mb-5">
              <Compass className="h-5 w-5" />
            </div>
            <h3 className="text-lg font-bold text-zinc-900">
              {t("home.feat_discovery_title", "Global Discovery & Affordability")}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-zinc-600">
              {t(
                "home.feat_discovery_desc",
                "Find institutions that fit your academic goals, budget, and visa pathway. Calculate net costs, institutional scholarships, and admission probabilities."
              )}
            </p>
            <Link
              href="/universities"
              className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-emerald-600 hover:text-emerald-700"
            >
              <span>{t("home.feat_discovery_link", "Explore Universities")}</span>{" "}
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        {/* Three Pillars Section */}
        <div className="mt-28 border-t border-zinc-200 pt-16">
          <div className="text-center max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold tracking-tight text-zinc-900 sm:text-3xl">
              {t("home.pillars_title", "Three Products. One Unified Higher Education Operating System.")}
            </h2>
            <p className="mt-3 text-sm text-zinc-600">
              {t(
                "home.pillars_subtitle",
                "Designed to serve students, high schools, transfer counselors, and higher education institutions globally."
              )}
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="p-6 rounded-2xl bg-zinc-50 border border-zinc-200/80">
              <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider">
                {t("home.pillar_1_title", "Product A: Student OS")}
              </span>
              <p className="mt-2 text-sm text-zinc-700 leading-relaxed">
                {t(
                  "home.pillar_1_desc",
                  "Universal profile, course history, test scores, document vault, and personalized application workspaces for first-year and transfer routes."
                )}
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-zinc-50 border border-zinc-200/80">
              <span className="text-xs font-bold text-sky-600 uppercase tracking-wider">
                {t("home.pillar_2_title", "Product B: Admissions Intelligence")}
              </span>
              <p className="mt-2 text-sm text-zinc-700 leading-relaxed">
                {t(
                  "home.pillar_2_desc",
                  "Multilingual AI Counselor, 3-tier transfer credit articulation, international foreign credential conversion, and university matching."
                )}
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-zinc-50 border border-zinc-200/80">
              <span className="text-xs font-bold text-emerald-600 uppercase tracking-wider">
                {t("home.pillar_3_title", "Product C: Global Infrastructure")}
              </span>
              <p className="mt-2 text-sm text-zinc-700 leading-relaxed">
                {t(
                  "home.pillar_3_desc",
                  "Verified university directory, requirement update engine, counselor recommendation collaboration, and secure transcript delivery."
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-28 border-t border-zinc-200 pt-8 pb-12 flex flex-col sm:flex-row items-center justify-between text-xs text-zinc-500 gap-4">
          <div className="space-y-1 text-center sm:text-left">
            <div className="font-semibold text-zinc-800">
              {t("brand.tagline", "ONE STUDENT PROFILE. EVERY UNIVERSITY. ONE GLOBAL PLATFORM.")}
            </div>
            <div>
              {t(
                "home.footer_desc",
                "The world's first universal college application and admissions intelligence platform. One student profile. Every university. One global platform."
              )}
            </div>
          </div>
          <div className="text-center sm:text-right">
            <div>
              &copy; {new Date().getFullYear()} UniGlobe Inc.{" "}
              {t("home.footer_rights", "All rights reserved. Designed for international higher education access.")}
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
