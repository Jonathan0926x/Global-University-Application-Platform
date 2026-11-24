"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Sparkles,
  GraduationCap,
  ArrowRightLeft,
  Sliders,
  Bookmark,
  BookmarkCheck,
  ChevronDown,
  ChevronUp,
  Search,
  Scale,
  Info,
  RefreshCw,
  ShieldCheck,
  Building2,
} from "lucide-react";
import { useI18n } from "@/lib/i18n/context";
import {
  fetchProfile,
  fetchMatchingPreferences,
  updateMatchingPreferences,
  runMatchingDiscovery,
  evaluateInstitutionMatch,
  toggleShortlistInstitution,
  fetchMatchingShortlist,
  compareInstitutions,
  searchInstitutions,
  type MatchCategory,
  type UniversityMatchRecommendation,
  type InstitutionV3,
} from "@/lib/api-client";
import {
  MatchExplanationPanel,
  factorStatusBadge,
} from "@/components/matching/MatchExplanationPanel";
import { ComparisonPanel } from "@/components/matching/ComparisonPanel";

type CategoryTab = "all" | MatchCategory | "shortlist";

function categoryBadgeStyle(cat: MatchCategory) {
  switch (cat) {
    case "likely":
      return {
        label: "Likely Match",
        cls: "bg-emerald-50 text-emerald-800 border-emerald-200",
      };
    case "target":
      return {
        label: "Target Match",
        cls: "bg-sky-50 text-sky-800 border-sky-200",
      };
    case "reach":
      return {
        label: "Reach",
        cls: "bg-indigo-50 text-indigo-800 border-indigo-200",
      };
    default:
      return {
        label: "Insufficient Data",
        cls: "bg-amber-50 text-amber-800 border-amber-200",
      };
  }
}

function dimensionBarColor(score: number, isNa: boolean) {
  if (isNa) return "bg-zinc-300";
  if (score >= 78) return "bg-emerald-600";
  if (score >= 58) return "bg-sky-600";
  if (score >= 42) return "bg-amber-500";
  return "bg-rose-500";
}

export default function MatchingDashboardPage() {
  const { direction, t } = useI18n();

  const [applicantType, setApplicantType] = useState<"first_year" | "transfer">("transfer");
  const [intendedMajor, setIntendedMajor] = useState("Computer Science");
  const [maxAnnualBudget, setMaxAnnualBudget] = useState<string>("45000");
  const [countryFilter, setCountryFilter] = useState<string>("ALL");
  const [instTypeFilter, setInstTypeFilter] = useState<string>("ALL");

  const [weightAcademic, setWeightAcademic] = useState(30);
  const [weightFinancial, setWeightFinancial] = useState(25);
  const [weightReadiness, setWeightReadiness] = useState(25);
  const [weightTransfer, setWeightTransfer] = useState(20);

  const [recommendations, setRecommendations] = useState<UniversityMatchRecommendation[]>([]);
  const [shortlist, setShortlist] = useState<UniversityMatchRecommendation[]>([]);
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({});
  const [activeTab, setActiveTab] = useState<CategoryTab>("all");
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [comparedItems, setComparedItems] = useState<UniversityMatchRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusNote, setStatusNote] = useState<string | null>(null);

  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogResults, setCatalogResults] = useState<InstitutionV3[]>([]);
  const [evaluatingId, setEvaluatingId] = useState<string | null>(null);

  const totalRawWeights = useMemo(
    () =>
      weightAcademic +
      weightFinancial +
      weightReadiness +
      (applicantType === "first_year" ? 0 : weightTransfer),
    [weightAcademic, weightFinancial, weightReadiness, weightTransfer, applicantType]
  );

  const buildPayload = useCallback(
    (overrideType?: "first_year" | "transfer") => {
      const pathway = overrideType || applicantType;
      const sum =
        weightAcademic + weightFinancial + weightReadiness + weightTransfer || 100;
      const budgetNum = maxAnnualBudget.trim() ? Number(maxAnnualBudget) : null;

      return {
        applicant_type: pathway,
        intended_major: intendedMajor.trim() || null,
        countries: countryFilter !== "ALL" ? [countryFilter] : [],
        states: [],
        institution_types: instTypeFilter !== "ALL" ? [instTypeFilter] : [],
        max_annual_budget: Number.isFinite(budgetNum) ? budgetNum : null,
        weight_academic: Number((weightAcademic / sum).toFixed(4)),
        weight_financial: Number((weightFinancial / sum).toFixed(4)),
        weight_readiness: Number((weightReadiness / sum).toFixed(4)),
        weight_transfer: Number((weightTransfer / sum).toFixed(4)),
        limit: 24,
        persist: true,
      };
    },
    [
      applicantType,
      intendedMajor,
      maxAnnualBudget,
      countryFilter,
      instTypeFilter,
      weightAcademic,
      weightFinancial,
      weightReadiness,
      weightTransfer,
    ]
  );

  const executeRun = useCallback(
    async (customType?: "first_year" | "transfer", persistPrefs = false) => {
      setLoading(true);
      setErrorMsg(null);
      try {
        const payload = buildPayload(customType);
        if (persistPrefs) {
          setSavingPrefs(true);
          await updateMatchingPreferences({
            preferred_countries: payload.countries.length ? payload.countries : ["US"],
            preferred_states_provinces: [],
            preferred_institution_types: payload.institution_types,
            max_annual_budget: payload.max_annual_budget,
            weight_academic: payload.weight_academic,
            weight_financial: payload.weight_financial,
            weight_readiness: payload.weight_readiness,
            weight_transfer: payload.weight_transfer,
          });
          setSavingPrefs(false);
        }

        const [runRes, savedList] = await Promise.all([
          runMatchingDiscovery(payload),
          fetchMatchingShortlist(),
        ]);
        setRecommendations(runRes.recommendations);
        setCategoryCounts(runRes.counts_by_category || {});
        setShortlist(savedList);
        if (runRes.recommendations.length > 0) {
          setExpandedIds((prev) =>
            Object.keys(prev).length === 0
              ? { [runRes.recommendations[0].institution_id]: true }
              : prev
          );
        }
        setStatusNote(
          `Evaluated ${runRes.total_evaluated} institutions under ${
            payload.applicant_type === "first_year" ? "First-Year" : "Transfer"
          } rules.`
        );
      } catch (err) {
        setErrorMsg(
          err instanceof Error ? err.message : "Failed to compute match results"
        );
      } finally {
        setLoading(false);
        setSavingPrefs(false);
      }
    },
    [buildPayload]
  );

  useEffect(() => {
    let active = true;
    (async () => {
      const [profile, prefs] = await Promise.all([
        fetchProfile().catch(() => null),
        fetchMatchingPreferences(),
      ]);
      if (!active) return;

      const initialType: "first_year" | "transfer" =
        profile?.applicant_type === "first_year" ? "first_year" : "transfer";
      const initialMajor = profile?.intended_major || "Computer Science";
      setApplicantType(initialType);
      setIntendedMajor(initialMajor);

      if (prefs) {
        if (prefs.max_annual_budget !== null && prefs.max_annual_budget !== undefined) {
          setMaxAnnualBudget(String(prefs.max_annual_budget));
        }
        if (prefs.preferred_institution_types?.length) {
          setInstTypeFilter(prefs.preferred_institution_types[0]);
        }
        setWeightAcademic(Math.round((prefs.weight_academic ?? 0.3) * 100));
        setWeightFinancial(Math.round((prefs.weight_financial ?? 0.25) * 100));
        setWeightReadiness(Math.round((prefs.weight_readiness ?? 0.25) * 100));
        setWeightTransfer(Math.round((prefs.weight_transfer ?? 0.2) * 100));
      }

      try {
        const [runRes, savedList] = await Promise.all([
          runMatchingDiscovery({
            applicant_type: initialType,
            intended_major: initialMajor,
            countries: [],
            institution_types: prefs?.preferred_institution_types || [],
            max_annual_budget: prefs?.max_annual_budget ?? 45000,
            weight_academic: prefs?.weight_academic ?? 0.3,
            weight_financial: prefs?.weight_financial ?? 0.25,
            weight_readiness: prefs?.weight_readiness ?? 0.25,
            weight_transfer: prefs?.weight_transfer ?? 0.2,
            limit: 24,
            persist: true,
          }),
          fetchMatchingShortlist(),
        ]);
        if (!active) return;
        setRecommendations(runRes.recommendations);
        setCategoryCounts(runRes.counts_by_category || {});
        setShortlist(savedList);
        if (runRes.recommendations.length > 0) {
          setExpandedIds({ [runRes.recommendations[0].institution_id]: true });
        }
      } catch {
        if (active) setErrorMsg("Unable to connect to the Matching Engine backend.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const q = catalogQuery.trim();
    if (q.length < 2) {
      setCatalogResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await searchInstitutions({ q, limit: 6 });
        setCatalogResults(res.items || []);
      } catch {
        setCatalogResults([]);
      }
    }, 220);
    return () => clearTimeout(timer);
  }, [catalogQuery]);

  const handleEvaluateSingle = async (inst: InstitutionV3) => {
    setEvaluatingId(inst.id);
    setErrorMsg(null);
    try {
      const rec = await evaluateInstitutionMatch(
        inst.id,
        applicantType,
        intendedMajor.trim() || undefined
      );
      if (rec) {
        setRecommendations((prev) => {
          const without = prev.filter((r) => r.institution_id !== rec.institution_id);
          return [rec, ...without];
        });
        setExpandedIds((prev) => ({ ...prev, [rec.institution_id]: true }));
        setCatalogQuery("");
        setCatalogResults([]);
        setActiveTab("all");
        setStatusNote(`Evaluated ${rec.institution.official_name} individually.`);
      }
    } catch {
      setErrorMsg(`Failed to evaluate ${inst.official_name}.`);
    } finally {
      setEvaluatingId(null);
    }
  };

  const handleToggleShortlist = async (rec: UniversityMatchRecommendation) => {
    const nextSaved = !rec.is_saved_by_student;
    setRecommendations((prev) =>
      prev.map((r) =>
        r.institution_id === rec.institution_id
          ? { ...r, is_saved_by_student: nextSaved }
          : r
      )
    );
    try {
      await toggleShortlistInstitution(rec.institution_id, nextSaved);
      const updatedShortlist = await fetchMatchingShortlist();
      setShortlist(updatedShortlist);
    } catch {
      setRecommendations((prev) =>
        prev.map((r) =>
          r.institution_id === rec.institution_id
            ? { ...r, is_saved_by_student: !nextSaved }
            : r
        )
      );
    }
  };

  const handleToggleCompare = (institutionId: string) => {
    setCompareIds((prev) => {
      if (prev.includes(institutionId)) {
        return prev.filter((id) => id !== institutionId);
      }
      if (prev.length >= 4) return prev;
      return [...prev, institutionId];
    });
  };

  const handleRunCompare = async () => {
    if (compareIds.length === 0) return;
    try {
      const res = await compareInstitutions({
        institution_ids: compareIds,
        applicant_type: applicantType,
        intended_major: intendedMajor.trim() || null,
      });
      setComparedItems(res);
    } catch {
      setErrorMsg("Unable to load side-by-side comparison.");
    }
  };

  const handleSwitchPathway = (nextType: "first_year" | "transfer") => {
    setApplicantType(nextType);
    setComparedItems([]);
    executeRun(nextType, true);
  };

  const handleResetWeights = () => {
    setWeightAcademic(30);
    setWeightFinancial(25);
    setWeightReadiness(25);
    setWeightTransfer(20);
  };

  const displayedList = useMemo(() => {
    if (activeTab === "shortlist") return shortlist;
    if (activeTab === "all") return recommendations;
    return recommendations.filter((r) => r.match_category === activeTab);
  }, [activeTab, recommendations, shortlist]);

  return (
    <div dir={direction} className="min-h-screen bg-[#fafafc] text-zinc-900 pb-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-8 space-y-6">
        <section className="flex flex-col gap-4">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
            <div className="space-y-2 max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-800">
                <Sparkles className="h-3.5 w-3.5" />
                <span>Phase 3 • Explainable Intelligence</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-zinc-900">
                {t("matching.title", "Four-Dimensional University Matching Engine")}
              </h1>
              <p className="text-sm text-zinc-600 leading-relaxed">
                {t(
                  "matching.subtitle",
                  "Transparent, evidence-based university discovery evaluating Academic Fit, Financial Compatibility, Admissions Readiness, and Transfer & Credit Compatibility — never black-box admission odds."
                )}
              </p>
            </div>

            <div
              role="group"
              aria-label="Applicant Pathway Mode"
              className="inline-flex rounded-xl border border-zinc-200 bg-white p-1 shadow-xs self-start"
            >
              <button
                type="button"
                onClick={() => handleSwitchPathway("first_year")}
                className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-colors ${
                  applicantType === "first_year"
                    ? "bg-zinc-900 text-white"
                    : "text-zinc-700 hover:bg-zinc-100"
                }`}
              >
                <GraduationCap className="h-4 w-4" />
                First-Year Applicant
              </button>
              <button
                type="button"
                onClick={() => handleSwitchPathway("transfer")}
                className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-colors ${
                  applicantType === "transfer"
                    ? "bg-zinc-900 text-white"
                    : "text-zinc-700 hover:bg-zinc-100"
                }`}
              >
                <ArrowRightLeft className="h-4 w-4" />
                Transfer Applicant
              </button>
            </div>
          </div>

          <div className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-xs text-amber-900">
            <ShieldCheck className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              {t(
                "matching.disclaimer",
                "Advisory Decision Support Only: Scores reflect transparent criteria alignment from your Universal Profile and verified institutional records — never admission probabilities or guarantees."
              )}{" "}
              {applicantType === "first_year" && (
                <strong className="font-semibold">
                  First-Year Mode active: Transfer & Credit Compatibility is marked Not Applicable and never penalizes your score.
                </strong>
              )}
            </p>
          </div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-8 rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sliders className="h-4 w-4 text-indigo-700" />
                <h2 className="text-sm font-semibold text-zinc-900">
                  Student Criteria & Dimension Priorities
                </h2>
              </div>
              <button
                type="button"
                onClick={handleResetWeights}
                className="text-xs font-medium text-indigo-700 hover:underline"
              >
                Reset Default Weights (30 / 25 / 25 / 20)
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">
                  Intended Major
                </label>
                <input
                  type="text"
                  value={intendedMajor}
                  onChange={(e) => setIntendedMajor(e.target.value)}
                  placeholder="e.g. Computer Science"
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">
                  Max Annual Budget (USD)
                </label>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  value={maxAnnualBudget}
                  onChange={(e) => setMaxAnnualBudget(e.target.value)}
                  placeholder="e.g. 45000"
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">
                  Country Scope
                </label>
                <select
                  value={countryFilter}
                  onChange={(e) => setCountryFilter(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 focus:border-indigo-500 focus:outline-none"
                >
                  <option value="ALL">All Countries (Global)</option>
                  <option value="US">United States (US)</option>
                  <option value="DE">Germany (DE)</option>
                  <option value="CA">Canada (CA)</option>
                  <option value="GB">United Kingdom (GB)</option>
                  <option value="FR">France (FR)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">
                  Institution Type
                </label>
                <select
                  value={instTypeFilter}
                  onChange={(e) => setInstTypeFilter(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 focus:border-indigo-500 focus:outline-none"
                >
                  <option value="ALL">All Types</option>
                  <option value="university">Universities (4-Year+)</option>
                  <option value="community_college">Community Colleges</option>
                  <option value="technical_vocational">Technical / Vocational</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2 border-t border-zinc-100">
              {[
                {
                  label: "Academic Fit",
                  val: weightAcademic,
                  set: setWeightAcademic,
                  disabled: false,
                },
                {
                  label: "Financial Fit",
                  val: weightFinancial,
                  set: setWeightFinancial,
                  disabled: false,
                },
                {
                  label: "Admissions Readiness",
                  val: weightReadiness,
                  set: setWeightReadiness,
                  disabled: false,
                },
                {
                  label: "Transfer Compatibility",
                  val: weightTransfer,
                  set: setWeightTransfer,
                  disabled: applicantType === "first_year",
                },
              ].map((slider) => {
                const effectivePct = slider.disabled
                  ? 0
                  : totalRawWeights > 0
                  ? Math.round((slider.val / totalRawWeights) * 100)
                  : 0;
                return (
                  <div
                    key={slider.label}
                    className={`rounded-xl border border-zinc-200 p-3 ${
                      slider.disabled ? "bg-zinc-50 opacity-70" : "bg-white"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="font-medium text-zinc-800">{slider.label}</span>
                      <span className="font-semibold text-indigo-700">
                        {slider.disabled ? "N/A" : `${effectivePct}%`}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={5}
                      max={70}
                      disabled={slider.disabled}
                      value={slider.val}
                      onChange={(e) => slider.set(Number(e.target.value))}
                      aria-label={`${slider.label} weight`}
                      className="w-full accent-indigo-600 cursor-pointer"
                    />
                  </div>
                );
              })}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <div className="text-xs text-zinc-600">
                {statusNote ? (
                  <span>{statusNote}</span>
                ) : (
                  <span>
                    Adjust priorities or update your{" "}
                    <Link href="/profile" className="text-indigo-700 font-medium hover:underline">
                      Universal Student Profile
                    </Link>{" "}
                    and re-run.
                  </span>
                )}
              </div>

              <button
                type="button"
                disabled={loading || savingPrefs}
                onClick={() => executeRun(undefined, true)}
                className="inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-4 py-2 text-xs font-semibold text-white hover:bg-zinc-800 disabled:opacity-50 transition-colors"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                {loading
                  ? "Evaluating Matches..."
                  : t("matching.run_button", "Run Match Analysis")}
              </button>
            </div>
          </div>

          <div className="lg:col-span-4 rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs flex flex-col justify-between gap-4">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-indigo-700" />
                <h2 className="text-sm font-semibold text-zinc-900">
                  Evaluate Any Institution
                </h2>
              </div>
              <p className="text-xs text-zinc-600">
                Look up any institution across the global 6,699+ registry to compute an instant four-dimensional audit.
              </p>

              <div className="relative">
                <input
                  type="text"
                  value={catalogQuery}
                  onChange={(e) => setCatalogQuery(e.target.value)}
                  placeholder="Search e.g. Berkeley, TUM, UCLA, MIT..."
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              {catalogResults.length > 0 && (
                <ul className="divide-y divide-zinc-200 rounded-xl border border-zinc-200 bg-zinc-50 overflow-hidden">
                  {catalogResults.map((inst) => (
                    <li
                      key={inst.id}
                      className="flex items-center justify-between gap-2 px-3 py-2 text-xs"
                    >
                      <div className="min-w-0">
                        <p className="font-semibold text-zinc-900 truncate">
                          {inst.official_name}
                        </p>
                        <p className="text-[11px] text-zinc-600">
                          {[inst.city, inst.state_province, inst.country_code]
                            .filter(Boolean)
                            .join(", ")}
                        </p>
                      </div>
                      <button
                        type="button"
                        disabled={evaluatingId === inst.id}
                        onClick={() => handleEvaluateSingle(inst)}
                        className="shrink-0 rounded-lg border border-indigo-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-indigo-700 hover:bg-indigo-50"
                      >
                        {evaluatingId === inst.id ? "..." : "Evaluate"}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-[11px] text-zinc-700 flex items-start gap-2">
              <Info className="h-4 w-4 text-zinc-500 shrink-0 mt-0.5" />
              <span>
                Missing student or institutional inputs are flagged as{" "}
                <strong>Insufficient Info</strong> instead of being penalized silently.
              </span>
            </div>
          </div>
        </section>

        {errorMsg && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-800">
            {errorMsg}
          </div>
        )}

        {compareIds.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-xs">
            <div className="flex items-center gap-2 font-medium text-indigo-950">
              <Scale className="h-4 w-4 text-indigo-700" />
              <span>
                {compareIds.length} institution{compareIds.length === 1 ? "" : "s"} selected for comparison (up to 4).
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleRunCompare}
                className="rounded-lg bg-indigo-700 px-3.5 py-1.5 font-semibold text-white hover:bg-indigo-800"
              >
                Compare Selected Side-by-Side
              </button>
              <button
                type="button"
                onClick={() => {
                  setCompareIds([]);
                  setComparedItems([]);
                }}
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 font-medium text-zinc-700 hover:bg-zinc-100"
              >
                Clear
              </button>
            </div>
          </div>
        )}

        <ComparisonPanel
          items={comparedItems}
          onRemove={(id) => {
            setCompareIds((prev) => prev.filter((x) => x !== id));
            setComparedItems((prev) => prev.filter((x) => x.institution_id !== id));
          }}
          onClear={() => {
            setCompareIds([]);
            setComparedItems([]);
          }}
        />

        <section className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 pb-3">
          <div className="flex flex-wrap items-center gap-2">
            {(
              [
                { id: "all", label: `All Results (${recommendations.length})` },
                { id: "likely", label: `Likely (${categoryCounts.likely ?? 0})` },
                { id: "target", label: `Target (${categoryCounts.target ?? 0})` },
                { id: "reach", label: `Reach (${categoryCounts.reach ?? 0})` },
                {
                  id: "insufficient_data",
                  label: `Insufficient Data (${categoryCounts.insufficient_data ?? 0})`,
                },
                { id: "shortlist", label: `Saved Shortlist (${shortlist.length})` },
              ] as { id: CategoryTab; label: string }[]
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                  activeTab === tab.id
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-100"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          {loading ? (
            <div className="rounded-2xl border border-zinc-200 bg-white p-10 text-center text-sm text-zinc-600">
              Running four-dimensional evaluation across institutional requirements, costs, and articulation paths...
            </div>
          ) : displayedList.length === 0 ? (
            <div className="rounded-2xl border border-zinc-200 bg-white p-10 text-center space-y-2">
              <Building2 className="h-8 w-8 text-zinc-400 mx-auto" />
              <p className="text-sm font-semibold text-zinc-900">
                No matching institutions in this filter view
              </p>
              <p className="text-xs text-zinc-600">
                Try switching tabs, broadening Country/Type filters, or searching for a specific institution above.
              </p>
            </div>
          ) : (
            displayedList.map((rec) => {
              const cat = categoryBadgeStyle(rec.match_category);
              const isExpanded = Boolean(expandedIds[rec.institution_id]);
              const isCompared = compareIds.includes(rec.institution_id);

              return (
                <article
                  key={rec.institution_id}
                  className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs transition-shadow hover:shadow-md"
                >
                  <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                    <div className="space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${cat.cls}`}
                        >
                          {cat.label}
                        </span>
                        <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-0.5 text-[11px] font-medium text-zinc-700">
                          Data Confidence: {Math.round(rec.data_confidence_score * 100)}%
                        </span>
                        <span className="text-[11px] font-medium text-zinc-500 uppercase">
                          {rec.applicant_type === "first_year" ? "First-Year" : "Transfer"}
                        </span>
                      </div>

                      <h3 className="text-lg font-bold text-zinc-900">
                        <Link
                          href={`/universities/${rec.institution_id}`}
                          className="hover:text-indigo-700 transition-colors"
                        >
                          {rec.institution.official_name}
                        </Link>
                      </h3>

                      <p className="text-xs text-zinc-600">
                        {[
                          rec.institution.city,
                          rec.institution.state_province,
                          rec.institution.country_code,
                        ]
                          .filter(Boolean)
                          .join(", ")}{" "}
                        •{" "}
                        <span className="capitalize">
                          {rec.institution.control_type || "Institution"}
                        </span>{" "}
                        {rec.institution.institution_type.replace("_", " ")}
                        {rec.intended_major && ` • Major: ${rec.intended_major}`}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 shrink-0">
                      <div className="text-end pe-3 border-e border-zinc-200">
                        <div dir="ltr" className="text-2xl font-bold text-zinc-900 tabular-nums">
                          {rec.composite_score.toFixed(1)}
                          <span className="text-xs font-normal text-zinc-500"> / 100</span>
                        </div>
                        <div className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                          Alignment Score
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleToggleCompare(rec.institution_id)}
                        className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                          isCompared
                            ? "border-indigo-300 bg-indigo-50 text-indigo-800"
                            : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-100"
                        }`}
                      >
                        <Scale className="h-3.5 w-3.5" />
                        {isCompared ? "Selected" : "Compare"}
                      </button>

                      <button
                        type="button"
                        onClick={() => handleToggleShortlist(rec)}
                        className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                          rec.is_saved_by_student
                            ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                            : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-100"
                        }`}
                      >
                        {rec.is_saved_by_student ? (
                          <BookmarkCheck className="h-3.5 w-3.5" />
                        ) : (
                          <Bookmark className="h-3.5 w-3.5" />
                        )}
                        {rec.is_saved_by_student ? "Shortlisted" : "Save"}
                      </button>

                      <button
                        type="button"
                        onClick={() =>
                          setExpandedIds((prev) => ({
                            ...prev,
                            [rec.institution_id]: !prev[rec.institution_id],
                          }))
                        }
                        className="inline-flex items-center gap-1 rounded-xl bg-zinc-900 px-3 py-2 text-xs font-semibold text-white hover:bg-zinc-800 transition-colors"
                      >
                        {isExpanded ? "Hide Audit" : "Explain Match"}
                        {isExpanded ? (
                          <ChevronUp className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    {rec.dimensions.map((dim) => {
                      const isNa = dim.status === "not_applicable";
                      const badge = factorStatusBadge(dim.status);
                      const widthPct = isNa
                        ? 0
                        : Math.max(4, Math.min(100, dim.score || 0));

                      return (
                        <div
                          key={dim.key}
                          className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3 space-y-2"
                        >
                          <div className="flex items-center justify-between gap-2 text-xs">
                            <span className="font-semibold text-zinc-800 truncate">
                              {dim.label}
                            </span>
                            <span className="font-bold text-zinc-900 tabular-nums shrink-0">
                              {isNa ? "N/A" : dim.score.toFixed(1)}
                            </span>
                          </div>

                          <div className="h-2 w-full rounded-full bg-zinc-200 overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all ${dimensionBarColor(
                                dim.score,
                                isNa
                              )}`}
                              style={{ width: `${widthPct}%` }}
                            />
                          </div>

                          <div className="flex items-center justify-between gap-1 text-[10px]">
                            <span
                              className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 font-medium ${badge.cls}`}
                            >
                              {badge.label}
                            </span>
                            <span className="text-zinc-500">
                              {(dim.weight_applied * 100).toFixed(0)}% weight
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {!isExpanded && (
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-zinc-600">
                      <span className="font-medium text-emerald-800">
                        +{rec.positive_factors.length} positive
                      </span>
                      <span>•</span>
                      <span className="font-medium text-amber-800">
                        {rec.missing_information.length} missing info
                      </span>
                      <span>•</span>
                      <span className="font-medium text-rose-800">
                        {rec.unsatisfied_requirements.length + rec.financial_concerns.length} concerns
                      </span>
                    </div>
                  )}

                  {isExpanded && <MatchExplanationPanel rec={rec} />}
                </article>
              );
            })
          )}
        </section>
      </div>
    </div>
  );
}
