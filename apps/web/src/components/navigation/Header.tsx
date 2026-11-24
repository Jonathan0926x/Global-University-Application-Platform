"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Globe2,
  GraduationCap,
  ArrowRightLeft,
  User,
  LayoutDashboard,
  Compass,
  Bot,
  FileText,
  ChevronDown
} from "lucide-react";
import { useI18n } from "@/lib/i18n/context";
import { LanguageModal } from "@/components/i18n/LanguageModal";

export function Header() {
  const pathname = usePathname();
  const { language, direction, t } = useI18n();
  const [langModalOpen, setLangModalOpen] = useState(false);

  const navLinks = [
    { href: "/dashboard", label: t("nav.student_os", "Student OS"), icon: LayoutDashboard },
    { href: "/first-year", label: t("nav.first_year", "First-Year Portal"), icon: GraduationCap },
    { href: "/transfer", label: t("nav.transfer", "Transfer Portal"), icon: ArrowRightLeft },
    { href: "/counselor", label: t("nav.counselor", "AI Counselor"), icon: Bot },
    { href: "/documents", label: t("nav.documents", "Document Vault"), icon: FileText },
    { href: "/universities", label: t("nav.universities", "Universities"), icon: Compass },
    { href: "/profile", label: t("nav.profile", "Universal Profile"), icon: User },
  ];

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-zinc-200 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-900 text-white transition-transform group-hover:scale-105">
                <Globe2 className="h-5 w-5" />
              </div>
              <div>
                <span className="font-semibold tracking-tight text-zinc-900 text-lg">UniGlobe</span>
                <span className="ml-1.5 hidden rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium tracking-wide text-zinc-600 uppercase sm:inline-block">
                  Global OS
                </span>
              </div>
            </Link>

            <nav className="hidden lg:flex items-center gap-1">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const isActive = pathname === link.href || pathname?.startsWith(link.href + "/");
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                      isActive
                        ? "bg-zinc-100 text-zinc-900 font-semibold"
                        : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5 text-zinc-500" />
                    <span>{link.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            {/* Language & Regional trigger button */}
            <button
              onClick={() => setLangModalOpen(true)}
              className="flex items-center gap-2 rounded-xl border border-zinc-200 bg-zinc-50 hover:bg-zinc-100 dark:bg-zinc-800 dark:border-zinc-700 px-3 py-1.5 text-xs font-semibold text-zinc-700 dark:text-zinc-200 transition-all shadow-xs"
              title="Change language and regional formats"
            >
              <span className="text-base">{language.flagEmoji}</span>
              <span className="max-w-[120px] truncate">{language.nativeName}</span>
              {direction === "rtl" && (
                <span className="text-[9px] font-mono font-bold px-1 py-0.2 rounded bg-purple-100 text-purple-700">
                  RTL
                </span>
              )}
              <ChevronDown className="h-3 w-3 text-zinc-400" />
            </button>

            <Link
              href="/profile"
              className="flex h-9 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-2.5 text-xs font-medium text-zinc-700 shadow-xs hover:bg-zinc-50 transition-colors"
            >
              <div className="h-5 w-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[11px] font-bold">
                J
              </div>
              <span className="hidden sm:inline">Jordan T.</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Language & Region Selector Modal */}
      <LanguageModal isOpen={langModalOpen} onClose={() => setLangModalOpen(false)} />
    </>
  );
}
