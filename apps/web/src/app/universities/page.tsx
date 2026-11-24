"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Building2,
  Search,
  CheckCircle2,
  ExternalLink,
  GraduationCap,
  Globe2,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Database,
  Users,
  DollarSign,
  SlidersHorizontal
} from "lucide-react";
import {
  searchInstitutions,
  fetchInstitutionFilters,
  fetchCountries,
  createApplication,
  InstitutionV3,
  InstitutionFilterOptions,
  CountryItem
} from "@/lib/api-client";
import { useI18n } from "@/lib/i18n/context";

const CONTROL_LABELS: Record<string, string> = {
  public: "Public",
  private_nonprofit: "Private Nonprofit",
  private_forprofit: "Private For-Profit",
};

const TYPE_LABELS: Record<string, string> = {
  university: "University (4-Year+)",
  liberal_arts_college: "Liberal Arts College",
  community_college: "Community College (2-Year)",
  technical_college: "Technical / Career College",
  vocational: "Vocational Institution",
  branch_campus: "Branch Campus",
  specialized: "Specialized Institution",
  other: "Other Postsecondary",
};

const SOURCE_LABELS: Record<string, string> = {
  ipeds: "NCES IPEDS",
  college_scorecard: "College Scorecard",
  openalex_ror: "OpenAlex / ROR",
  official_website: "Official Website",
};

export default function UniversitiesPage() {
  const router = useRouter();
  const { t, formatNumber } = useI18n();

  const [institutions, setInstitutions] = useState<InstitutionV3[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const limit = 24;

  const [filters, setFilters] = useState<InstitutionFilterOptions | null>(null);
  const [countries, setCountries] = useState<CountryItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Query state
  const [searchInput, setSearchInput] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [country, setCountry] = useState("");
  const [stateCode, setStateCode] = useState("");
  const [instType, setInstType] = useState("");
  const [control, setControl] = useState("");
  const [tuitionMax, setTuitionMax] = useState("");
  const [enrollmentMin, setEnrollmentMin] = useState("");
  const [filterPathway, setFilterPathway] = useState<"all" | "transfer" | "first_year">("all");
  const [sortBy, setSortBy] = useState("relevance");

  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [createdNotice, setCreatedNotice] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQ(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    async function loadMeta() {
      const [filterData, countryData] = await Promise.all([
        fetchInstitutionFilters(),
        fetchCountries(),
      ]);
      setFilters(filterData);
      setCountries(countryData);
    }
    loadMeta();
  }, []);

  const loadResults = useCallback(async () => {
    setLoading(true);
    try {
      const res = await searchInstitutions({
        q: debouncedQ || undefined,
        country: country || undefined,
        state: stateCode || undefined,
        type: instType || undefined,
        control: control || undefined,
        accepts_transfer: filterPathway === "transfer" ? true : undefined,
        accepts_first_year: filterPathway === "first_year" ? true : undefined,
        tuition_max: tuitionMax ? Number(tuitionMax) : undefined,
        enrollment_min: enrollmentMin ? Number(enrollmentMin) : undefined,
        sort: sortBy,
        page,
        limit,
      });
      setInstitutions(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error("Failed to search institutions:", err);
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, country, stateCode, instType, control, filterPathway, tuitionMax, enrollmentMin, sortBy, page]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  const handleStartApplication = async (inst: InstitutionV3, pathway: "first_year" | "transfer") => {
    setApplyingId(inst.id);
    try {
      await createApplication(inst.id, pathway, "Computer Science");
      setCreatedNotice(`Application workspace created for ${inst.official_name}!`);
      setTimeout(() => {
        router.push(pathway === "transfer" ? "/transfer" : "/first-year");
      }, 1000);
    } catch (err) {
      console.error("Failed to create application:", err);
      setApplyingId(null);
    }
  };

  const resetFilters = () => {
    setSearchInput("");
    setDebouncedQ("");
    setCountry("");
    setStateCode("");
    setInstType("");
    setControl("");
    setTuitionMax("");
    setEnrollmentMin("");
    setFilterPathway("all");
    setSortBy("relevance");
    setPage(1);
  };

  const formatMoneyOrUnavailable = (amount?: number | null, currency: string = "USD") => {
    if (amount === null || amount === undefined) {
      return "Not Reported";
    }
    return `${currency === "USD" ? "$" : `${currency} `}${formatNumber(Math.round(amount))}`;
  };

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const countryNameMap = Object.fromEntries(countries.map((c) => [c.code, c.name]));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-600">
            <Globe2 className="w-4 h-4" /> {t("univ.badge", "Global Admissions Directory")}
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 mt-1">
            {t("univ.title", "Global University Catalog")}
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            {t(
              "univ.subtitle",
              "Explore verified four-year universities, community colleges, and international partner institutions."
            )}
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {filters && (
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs font-medium text-emerald-800">
              <Database className="w-3.5 h-3.5" />
              <span>{formatNumber(filters.total_institutions)} Verified Institutions Indexed</span>
            </div>
          )}
          <Link
            href="/dashboard"
            className="px-4 py-2 rounded-xl border border-slate-200 bg-white text-xs font-semibold hover:bg-slate-50 text-slate-700 transition-colors"
          >
            {t("nav.student_os", "Student OS")}
          </Link>
        </div>
      </div>

      {createdNotice && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          <span>{createdNotice} Redirecting to workspace...</span>
        </div>
      )}

      {/* Search & Multi-Faceted Filter Bar */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col lg:flex-row gap-3">
          {/* Full-text Search Input */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder={t("univ.search_placeholder", "Search by institution name, city, state, IPEDS ID, or ROR ID...")}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white"
            />
          </div>

          {/* Pathway Pills */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 lg:pb-0">
            <button
              onClick={() => { setFilterPathway("all"); setPage(1); }}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors ${
                filterPathway === "all"
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {t("univ.filter_all", "All Institutions")}
            </button>
            <button
              onClick={() => { setFilterPathway("transfer"); setPage(1); }}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors ${
                filterPathway === "transfer"
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {t("univ.filter_transfer", "Accepts Transfer")}
            </button>
            <button
              onClick={() => { setFilterPathway("first_year"); setPage(1); }}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors ${
                filterPathway === "first_year"
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {t("univ.filter_first_year", "Accepts First-Year")}
            </button>
          </div>
        </div>

        {/* Faceted Dropdowns */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 pt-2 border-t border-slate-100">
          {/* Country Filter */}
          <select
            aria-label="Filter by country"
            value={country}
            onChange={(e) => {
              setCountry(e.target.value);
              if (e.target.value && e.target.value !== "US") setStateCode("");
              setPage(1);
            }}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 font-medium"
          >
            <option value="">All Countries</option>
            {filters?.countries.map((c) => (
              <option key={c.code} value={c.code}>
                {countryNameMap[c.code] || c.code} ({formatNumber(c.count)})
              </option>
            ))}
          </select>

          {/* State Filter */}
          <select
            aria-label="Filter by US state"
            value={stateCode}
            onChange={(e) => { setStateCode(e.target.value); setPage(1); }}
            disabled={country !== "" && country !== "US"}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 font-medium disabled:opacity-50"
          >
            <option value="">All States (US)</option>
            {filters?.us_states.map((st) => (
              <option key={st} value={st}>{st}</option>
            ))}
          </select>

          {/* Institution Type */}
          <select
            aria-label="Filter by institution type"
            value={instType}
            onChange={(e) => { setInstType(e.target.value); setPage(1); }}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 font-medium"
          >
            <option value="">All Institution Types</option>
            {Object.entries(TYPE_LABELS).map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>

          {/* Control Type (Public/Private) */}
          <select
            aria-label="Filter by public or private"
            value={control}
            onChange={(e) => { setControl(e.target.value); setPage(1); }}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 font-medium"
          >
            <option value="">Public & Private</option>
            <option value="public">Public</option>
            <option value="private_nonprofit">Private Nonprofit</option>
            <option value="private_forprofit">Private For-Profit</option>
          </select>

          {/* Tuition Max */}
          <select
            aria-label="Filter by max tuition"
            value={tuitionMax}
            onChange={(e) => { setTuitionMax(e.target.value); setPage(1); }}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 font-medium"
          >
            <option value="">Any Reported Tuition</option>
            <option value="5000">Under $5,000 / yr</option>
            <option value="10000">Under $10,000 / yr</option>
            <option value="20000">Under $20,000 / yr</option>
            <option value="35000">Under $35,000 / yr</option>
            <option value="50000">Under $50,000 / yr</option>
          </select>

          {/* Min Enrollment + Sort */}
          <div className="flex gap-2">
            <select
              aria-label="Filter by minimum enrollment"
              value={enrollmentMin}
              onChange={(e) => { setEnrollmentMin(e.target.value); setPage(1); }}
              className="w-1/2 rounded-xl border border-slate-200 bg-slate-50 px-2 py-2 text-xs text-slate-800 font-medium"
            >
              <option value="">Any Size</option>
              <option value="1000">1,000+ Students</option>
              <option value="5000">5,000+ Students</option>
              <option value="15000">15,000+ Students</option>
              <option value="30000">30,000+ Students</option>
            </select>
            <select
              aria-label="Sort institutions"
              value={sortBy}
              onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
              className="w-1/2 rounded-xl border border-slate-200 bg-slate-50 px-2 py-2 text-xs text-slate-800 font-medium"
            >
              <option value="relevance">Relevance</option>
              <option value="enrollment_desc">Largest Enrollment</option>
              <option value="tuition_asc">Lowest Tuition</option>
              <option value="name_asc">A–Z</option>
            </select>
          </div>
        </div>

        {/* Result Summary & Reset */}
        <div className="flex items-center justify-between text-xs text-slate-600 pt-1">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-3.5 h-3.5 text-slate-500" />
            <span>
              Showing{" "}
              <strong className="text-slate-900">
                {total === 0 ? 0 : (page - 1) * limit + 1}–{Math.min(page * limit, total)}
              </strong>{" "}
              of <strong className="text-slate-900">{formatNumber(total)}</strong> matching institutions
            </span>
          </div>
          {(debouncedQ || country || stateCode || instType || control || tuitionMax || enrollmentMin || filterPathway !== "all") && (
            <button onClick={resetFilters} className="text-brand-600 hover:underline font-medium">
              Reset All Filters
            </button>
          )}
        </div>
      </div>

      {/* Institutions Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-64 rounded-2xl border border-slate-200 bg-white animate-pulse p-6" />
          ))}
        </div>
      ) : institutions.length === 0 ? (
        <div className="text-center py-16 bg-white border border-slate-200 rounded-2xl">
          <Building2 className="w-10 h-10 text-slate-400 mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-700">
            No institutions matched your current filter combination.
          </p>
          <button onClick={resetFilters} className="mt-3 text-xs font-semibold text-brand-600 hover:underline">
            Clear filters to explore all {filters ? formatNumber(filters.total_institutions) : ""} records
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {institutions.map((inst) => (
            <div
              key={inst.id}
              className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm hover:shadow-md transition-all flex flex-col justify-between"
            >
              <div>
                {/* Top badges row */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                      {TYPE_LABELS[inst.institution_type] || inst.institution_type}
                    </span>
                    {inst.control_type && (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
                        {CONTROL_LABELS[inst.control_type] || inst.control_type}
                      </span>
                    )}
                  </div>
                  {inst.is_verified && (
                    <span
                      className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1 shrink-0"
                      title={`Verified via ${SOURCE_LABELS[inst.primary_source || ""] || inst.primary_source || "Official Registry"}`}
                    >
                      <ShieldCheck className="w-3 h-3" />
                      {SOURCE_LABELS[inst.primary_source || ""] || "Verified"}
                    </span>
                  )}
                </div>

                {/* Institution Name & Location */}
                <div className="mt-3">
                  <Link href={`/universities/${inst.id}`} className="group">
                    <h3 className="text-base font-bold text-slate-900 group-hover:text-brand-600 transition-colors leading-snug">
                      {inst.official_name}
                    </h3>
                  </Link>
                  <p className="text-xs text-slate-600 mt-1">
                    {[inst.city, inst.state_province, inst.country_code].filter(Boolean).join(", ")}
                    {inst.ipeds_unit_id && (
                      <span className="ml-2 font-mono text-[10px] text-slate-500">
                        IPEDS: {inst.ipeds_unit_id}
                      </span>
                    )}
                  </p>
                </div>

                {/* Verified Metrics Grid (distinguishing Not Reported from 0) */}
                <div className="mt-4 grid grid-cols-2 gap-2.5 text-xs">
                  <div className="rounded-xl bg-slate-50 p-2.5 border border-slate-200/80">
                    <div className="text-[10px] text-slate-500 flex items-center gap-1 font-medium">
                      <DollarSign className="w-3 h-3" /> In-State Tuition
                    </div>
                    <div className={`font-semibold mt-0.5 ${inst.tuition_in_state == null ? "text-slate-500 italic font-normal" : "text-slate-900"}`}>
                      {formatMoneyOrUnavailable(inst.tuition_in_state, inst.currency)}
                    </div>
                  </div>

                  <div className="rounded-xl bg-slate-50 p-2.5 border border-slate-200/80">
                    <div className="text-[10px] text-slate-500 flex items-center gap-1 font-medium">
                      <DollarSign className="w-3 h-3" /> Out-of-State
                    </div>
                    <div className={`font-semibold mt-0.5 ${inst.tuition_out_of_state == null ? "text-slate-500 italic font-normal" : "text-slate-900"}`}>
                      {formatMoneyOrUnavailable(inst.tuition_out_of_state, inst.currency)}
                    </div>
                  </div>

                  <div className="rounded-xl bg-slate-50 p-2.5 border border-slate-200/80">
                    <div className="text-[10px] text-slate-500 flex items-center gap-1 font-medium">
                      <Users className="w-3 h-3" /> Enrollment
                    </div>
                    <div className={`font-semibold mt-0.5 ${inst.total_enrollment == null ? "text-slate-500 italic font-normal" : "text-slate-900"}`}>
                      {inst.total_enrollment == null ? "Not Reported" : formatNumber(inst.total_enrollment)}
                    </div>
                  </div>

                  <div className="rounded-xl bg-slate-50 p-2.5 border border-slate-200/80">
                    <div className="text-[10px] text-slate-500 font-medium">Acceptance Rate</div>
                    <div className={`font-semibold mt-0.5 ${inst.acceptance_rate == null ? "text-slate-500 italic font-normal" : "text-slate-900"}`}>
                      {inst.acceptance_rate == null ? "Not Reported" : `${inst.acceptance_rate}%`}
                    </div>
                  </div>
                </div>
              </div>

              {/* Footer Actions */}
              <div className="mt-5 pt-4 border-t border-slate-100 space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <Link
                    href={`/universities/${inst.id}`}
                    className="font-semibold text-brand-600 hover:underline flex items-center gap-1"
                  >
                    View Intelligence Profile <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                  {inst.official_website && (
                    <a
                      href={inst.official_website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-slate-500 hover:text-slate-900 flex items-center gap-1"
                      title="Official Website"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>

                <div className="flex gap-2">
                  {inst.accepts_transfer && (
                    <button
                      onClick={() => handleStartApplication(inst, "transfer")}
                      disabled={applyingId === inst.id}
                      className="flex-1 py-1.5 px-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-[11px] font-semibold transition-colors disabled:opacity-50"
                    >
                      {applyingId === inst.id ? "Creating..." : "Start Transfer"}
                    </button>
                  )}
                  {inst.accepts_first_year && (
                    <button
                      onClick={() => handleStartApplication(inst, "first_year")}
                      disabled={applyingId === inst.id}
                      className="flex-1 py-1.5 px-2.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-800 text-[11px] font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
                    >
                      <GraduationCap className="w-3 h-3" /> First-Year
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {total > limit && (
        <div className="flex items-center justify-between bg-white border border-slate-200 rounded-2xl px-5 py-3.5 shadow-sm">
          <div className="text-xs text-slate-600">
            Page <strong className="text-slate-900">{page}</strong> of{" "}
            <strong className="text-slate-900">{formatNumber(totalPages)}</strong>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" /> Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-40"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
