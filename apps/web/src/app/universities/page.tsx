"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Building2,
  Search,
  Filter,
  CheckCircle2,
  ExternalLink,
  GraduationCap,
  Globe2,
  Compass,
  ArrowRight,
  Sparkles,
  BookOpen
} from "lucide-react";
import {
  fetchInstitutions,
  createApplication,
  Institution
} from "@/lib/api-client";

export default function UniversitiesPage() {
  const router = useRouter();
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterPathway, setFilterPathway] = useState<"all" | "transfer" | "first_year">("all");
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [createdNotice, setCreatedNotice] = useState<string | null>(null);

  useEffect(() => {
    async function loadInstitutions() {
      try {
        const data = await fetchInstitutions();
        setInstitutions(data);
      } catch (err) {
        console.error("Failed to load institutions:", err);
      } finally {
        setLoading(false);
      }
    }
    loadInstitutions();
  }, []);

  const handleStartApplication = async (inst: Institution, pathway: "first_year" | "transfer") => {
    setApplyingId(inst.id);
    try {
      await createApplication(inst.id, pathway, "Computer Science");
      setCreatedNotice(`Application workspace created for ${inst.official_name}!`);
      setTimeout(() => {
        router.push(pathway === "transfer" ? "/transfer" : "/first-year");
      }, 1200);
    } catch (err) {
      console.error("Failed to create application:", err);
      setApplyingId(null);
    }
  };

  const filtered = institutions.filter((inst) => {
    const matchesSearch =
      inst.official_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (inst.city && inst.city.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (inst.state_province && inst.state_province.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;

    if (filterPathway === "transfer") {
      return inst.accepts_transfer !== false;
    }
    if (filterPathway === "first_year") {
      return inst.accepts_first_year !== false;
    }
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-600 dark:text-brand-400">
            <Globe2 className="w-4 h-4" /> Global Admissions Directory
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white mt-1">
            Global University Catalog
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Explore verified four-year universities, community colleges, and international partner institutions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-800 text-xs font-semibold hover:bg-slate-50 dark:hover:bg-slate-850 text-slate-700 dark:text-slate-200 transition-colors"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>

      {createdNotice && (
        <div className="p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl text-emerald-800 dark:text-emerald-300 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span>{createdNotice} Redirecting to workspace...</span>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Search Input */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search universities by name, state, or city..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {/* Pathway Pills */}
        <div className="flex items-center gap-2 self-start md:self-auto overflow-x-auto pb-1 md:pb-0">
          <button
            onClick={() => setFilterPathway("all")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-medium transition-colors ${
              filterPathway === "all"
                ? "bg-brand-600 text-white"
                : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900"
            }`}
          >
            All Institutions
          </button>
          <button
            onClick={() => setFilterPathway("transfer")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-medium transition-colors ${
              filterPathway === "transfer"
                ? "bg-brand-600 text-white"
                : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900"
            }`}
          >
            Transfer Friendly
          </button>
          <button
            onClick={() => setFilterPathway("first_year")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-medium transition-colors ${
              filterPathway === "first_year"
                ? "bg-brand-600 text-white"
                : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900"
            }`}
          >
            First-Year Admissions
          </button>
        </div>
      </div>

      {/* Institutions Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filtered.map((inst) => {
          const isTransferTarget = inst.institution_type !== "community_college";
          return (
            <div
              key={inst.id}
              className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col justify-between hover:border-slate-300 dark:hover:border-slate-700 transition-all hover:shadow-md"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-brand-600 dark:text-brand-400 font-bold text-lg shrink-0">
                    {inst.abbreviation || inst.official_name.substring(0, 2).toUpperCase()}
                  </div>
                  <div className="flex flex-wrap gap-1 justify-end">
                    {inst.accepts_transfer !== false && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                        Transfer Ready
                      </span>
                    )}
                    {inst.accepts_first_year !== false && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                        First-Year
                      </span>
                    )}
                  </div>
                </div>

                <div className="mt-4">
                  <h3 className="text-base font-bold text-slate-900 dark:text-white leading-snug">
                    {inst.official_name}
                  </h3>
                  <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                    <span>{inst.city}, {inst.state_province} &bull; {inst.country_code}</span>
                  </p>
                </div>

                {/* Key Details */}
                <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 text-[11px] block">Institution Type</span>
                    <span className="font-medium text-slate-700 dark:text-slate-300 capitalize">
                      {inst.institution_type.replace("_", " ")}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 text-[11px] block">Articulation</span>
                    <span className="font-medium text-emerald-600 dark:text-emerald-400">
                      Standardized Matrix
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2">
                {isTransferTarget ? (
                  <>
                    <button
                      onClick={() => handleStartApplication(inst, "transfer")}
                      disabled={applyingId === inst.id}
                      className="flex-1 py-2 px-3 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-sm"
                    >
                      <GraduationCap className="w-3.5 h-3.5" />
                      {applyingId === inst.id ? "Creating..." : "Transfer App"}
                    </button>
                    <button
                      onClick={() => handleStartApplication(inst, "first_year")}
                      disabled={applyingId === inst.id}
                      className="flex-1 py-2 px-3 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
                    >
                      <BookOpen className="w-3.5 h-3.5" />
                      First-Year
                    </button>
                  </>
                ) : (
                  <Link
                    href="/transfer"
                    className="w-full py-2 px-3 rounded-xl border border-brand-200 dark:border-brand-800 bg-brand-50/50 dark:bg-brand-950/20 text-brand-700 dark:text-brand-300 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 text-center"
                  >
                    Transfer Feeder &bull; View Articulation
                  </Link>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && !loading && (
        <div className="p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
          <Building2 className="w-10 h-10 text-slate-300 dark:text-slate-700 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">No institutions match your search</h3>
          <p className="text-xs text-slate-500 mt-1">Try clearing your search query or selecting another pathway filter.</p>
        </div>
      )}
    </div>
  );
}
