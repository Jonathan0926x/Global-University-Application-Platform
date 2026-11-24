"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Globe2, GraduationCap, ArrowRightLeft, User, LayoutDashboard, Compass } from "lucide-react";

export function Header() {
  const pathname = usePathname();

  const navLinks = [
    { href: "/dashboard", label: "Student OS", icon: LayoutDashboard },
    { href: "/first-year", label: "First-Year Portal", icon: GraduationCap },
    { href: "/transfer", label: "Transfer Portal", icon: ArrowRightLeft },
    { href: "/universities", label: "Universities", icon: Compass },
    { href: "/profile", label: "Universal Profile", icon: User },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-zinc-200 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-900 text-white transition-transform group-hover:scale-105">
              <Globe2 className="h-5 w-5" />
            </div>
            <div>
              <span className="font-semibold tracking-tight text-zinc-900 text-lg">UniGlobe</span>
              <span className="ml-1.5 hidden rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium tracking-wide text-zinc-600 uppercase sm:inline-block">
                Platform
              </span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive = pathname === link.href || pathname?.startsWith(link.href + "/");
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-zinc-100 text-zinc-900 font-semibold"
                      : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
                  }`}
                >
                  <Icon className="h-4 w-4 text-zinc-500" />
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/70 px-2.5 py-1 text-xs font-medium text-emerald-800">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 animate-pulse" />
            Backend Connected
          </div>

          <Link
            href="/profile"
            className="flex h-9 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-700 shadow-xs hover:bg-zinc-50 transition-colors"
          >
            <div className="h-5 w-5 rounded-full bg-zinc-200 flex items-center justify-center text-xs font-bold text-zinc-700">
              J
            </div>
            <span className="hidden sm:inline">Jordan T.</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
