import Link from "next/link";
import { ArrowRight, GraduationCap, ArrowRightLeft, Globe, Compass, ShieldCheck, Sparkles, CheckCircle2 } from "lucide-react";

export default function HomePage() {
  return (
    <div className="relative overflow-hidden">
      {/* Background radial gradient accent */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-gradient-to-tr from-sky-100 via-indigo-50 to-transparent blur-3xl opacity-70" />

      {/* Hero Section */}
      <div className="mx-auto max-w-7xl px-4 pt-16 pb-20 sm:px-6 lg:px-8 lg:pt-24">
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white/80 px-3.5 py-1 text-xs font-medium text-zinc-800 shadow-xs backdrop-blur-xs mb-8">
            <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
            <span>The Global Operating System for University Admissions</span>
          </div>

          <h1 className="text-4xl font-extrabold tracking-tight text-zinc-900 sm:text-6xl sm:leading-[1.1]">
            One Student Profile. <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-zinc-900 via-indigo-950 to-zinc-700">
              Every University. One Global Platform.
            </span>
          </h1>

          <p className="mt-6 text-lg leading-relaxed text-zinc-600 sm:text-xl">
            A student should never navigate the complexity of global higher education alone. Discover universities worldwide, verify transfer course equivalencies, and manage applications from one intelligent workspace.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/transfer"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-6 py-3.5 text-sm font-semibold text-white shadow-md hover:bg-zinc-800 transition-all hover:scale-[1.02]"
            >
              <ArrowRightLeft className="h-4 w-4" />
              Start as Transfer Student
              <ArrowRight className="h-4 w-4 opacity-70" />
            </Link>

            <Link
              href="/first-year"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-6 py-3.5 text-sm font-semibold text-zinc-900 shadow-xs hover:bg-zinc-50 transition-all hover:scale-[1.02]"
            >
              <GraduationCap className="h-4 w-4 text-zinc-700" />
              Start as First-Year Student
            </Link>
          </div>

          <div className="mt-8 flex items-center justify-center gap-6 text-xs text-zinc-500">
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Free Universal Profile
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Verified Articulation
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Multilingual Support
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
            <h3 className="text-lg font-bold text-zinc-900">Transfer Intelligence Portal</h3>
            <p className="mt-2 text-sm leading-relaxed text-zinc-600">
              Never lose earned credits. Compare completed courses from community colleges or universities against target institution degree requirements with verified course equivalencies.
            </p>
            <Link
              href="/transfer"
              className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-sky-600 hover:text-sky-700"
            >
              Explore Transfer Portal <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {/* Pathway 2: First-Year Portal */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-7 shadow-xs hover:shadow-md transition-shadow">
            <div className="h-10 w-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 mb-5">
              <GraduationCap className="h-5 w-5" />
            </div>
            <h3 className="text-lg font-bold text-zinc-900">First-Year Application Suite</h3>
            <p className="mt-2 text-sm leading-relaxed text-zinc-600">
              Prepare once, apply everywhere. Manage secondary transcripts, national examinations (SAT, ACT, Baccalauréat, A-Levels), essays, and recommendation letters from a unified profile.
            </p>
            <Link
              href="/first-year"
              className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-indigo-600 hover:text-indigo-700"
            >
              Explore First-Year Portal <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {/* Pathway 3: Global Discovery */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-7 shadow-xs hover:shadow-md transition-shadow">
            <div className="h-10 w-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600 mb-5">
              <Compass className="h-5 w-5" />
            </div>
            <h3 className="text-lg font-bold text-zinc-900">Global University Discovery</h3>
            <p className="mt-2 text-sm leading-relaxed text-zinc-600">
              Explore thousands of institutions across 195 countries. Compare verified in-state/out-of-state tuition, net affordability, deadlines, and official institutional application pathways.
            </p>
            <Link
              href="/universities"
              className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-emerald-600 hover:text-emerald-700"
            >
              Discover Universities <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        {/* Global Reach Highlight */}
        <div className="mt-16 rounded-2xl border border-zinc-200 bg-gradient-to-r from-zinc-900 to-zinc-800 p-8 text-white sm:p-12">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
            <div>
              <div className="inline-flex items-center gap-1.5 rounded-md bg-white/10 px-2.5 py-1 text-xs font-medium text-zinc-200 mb-4">
                <Globe className="h-3.5 w-3.5" /> Global Access Architecture
              </div>
              <h2 className="text-2xl font-bold sm:text-3xl">Designed for students in every educational system.</h2>
              <p className="mt-3 text-sm leading-relaxed text-zinc-300">
                Whether transferring from a California community college, completing the Haitian Baccalauréat, graduating from a French Lycée, or earning credits in India, the platform understands and respects your credentials.
              </p>
              <div className="mt-6 flex flex-wrap gap-2 text-xs font-mono text-zinc-300">
                <span className="rounded-md bg-white/10 px-2.5 py-1">US 4.0 Scale</span>
                <span className="rounded-md bg-white/10 px-2.5 py-1">French 0-20</span>
                <span className="rounded-md bg-white/10 px-2.5 py-1">Haitian NSIV</span>
                <span className="rounded-md bg-white/10 px-2.5 py-1">UK A-Levels</span>
                <span className="rounded-md bg-white/10 px-2.5 py-1">Indian CBSE</span>
                <span className="rounded-md bg-white/10 px-2.5 py-1">German Abitur</span>
              </div>
            </div>
            <div className="flex flex-col gap-3 rounded-xl bg-white/5 p-6 border border-white/10 text-xs">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <span className="text-zinc-400">Universal Profile Support</span>
                <span className="font-semibold text-emerald-400">100% Reusable</span>
              </div>
              <div className="flex items-center justify-between border-b border-white/10 py-3">
                <span className="text-zinc-400">Credit Loss Prevention</span>
                <span className="font-semibold text-white">Tier 1-3 Articulation</span>
              </div>
              <div className="flex items-center justify-between border-b border-white/10 py-3">
                <span className="text-zinc-400">Document Privacy</span>
                <span className="font-semibold text-white">Zero Third-Party Model Training</span>
              </div>
              <div className="flex items-center justify-between pt-3">
                <span className="text-zinc-400">Application Routing</span>
                <span className="font-semibold text-white">Direct Official Portals</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
