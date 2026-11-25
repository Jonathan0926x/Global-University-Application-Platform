"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Award,
  Calculator,
  CheckCircle2,
  Coins,
  ExternalLink,
  HelpCircle,
  ShieldAlert,
  Sparkles,
  XCircle,
} from "lucide-react";
import {
  Institution,
  NetPriceCalculationResponse,
  ScholarshipMatchResponse,
  calculateNetPrice,
  fetchInstitutions,
  matchScholarships,
} from "@/lib/api-client";
import { useI18n } from "@/lib/i18n/context";

function fmtMoney(val?: number | null, currency = "USD"): string {
  if (val === null || val === undefined) return "—";
  if (currency === "USD") {
    return `$${Math.round(val).toLocaleString("en-US")}`;
  }
  return `${Math.round(val).toLocaleString("en-US")} ${currency}`;
}

export default function FinancialIntelligencePage() {
  const { t, direction, language } = useI18n();
  const [activeTab, setActiveTab] = useState<"scholarships" | "net_price">("scholarships");

  // Shared student inputs (kept distinct: citizenship !== residence)
  const [citizenship, setCitizenship] = useState("HT");
  const [residenceCountry, setResidenceCountry] = useState("HT");
  const [residencyState, setResidencyState] = useState("");
  const [applicantType, setApplicantType] = useState<"first_year" | "transfer">("first_year");
  const [degreeLevel, setDegreeLevel] = useState<"bachelors" | "masters" | "doctoral">("bachelors");
  const [gpa4, setGpa4] = useState("3.85");
  const [needLevel, setNeedLevel] = useState<"high" | "moderate" | "low">("high");
  const [householdIncome, setHouseholdIncome] = useState("35000");
  const [destinationCountry, setDestinationCountry] = useState("");
  const [showIneligible, setShowIneligible] = useState(true);

  // Scholarship Matcher state
  const [schLoading, setSchLoading] = useState(false);
  const [schResult, setSchResult] = useState<ScholarshipMatchResponse | null>(null);

  // Net Price Calculator state
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [selectedInstId, setSelectedInstId] = useState("");
  const [residencyClass, setResidencyClass] = useState<"in_state" | "out_of_state" | "international">("international");
  const [housingPref, setHousingPref] = useState<"on_campus" | "off_campus" | "with_family">("on_campus");
  const [annualBudget, setAnnualBudget] = useState("25000");
  const [includeCompetitive, setIncludeCompetitive] = useState(true);
  const [netLoading, setNetLoading] = useState(false);
  const [netResult, setNetResult] = useState<NetPriceCalculationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const statusLabel = (st: string): string => {
    const map: Record<string, string> = {
      eligible: t("fin.stat_eligible", "Eligible"),
      conditionally_eligible: t("fin.stat_conditional", "Conditionally Eligible"),
      insufficient_information: t("fin.stat_insufficient", "Insufficient Info"),
      requires_manual_review: t("fin.stat_review", "Manual Review"),
      ineligible: t("fin.stat_ineligible", "Ineligible"),
    };
    return map[st] || st.replace(/_/g, " ");
  };

  const freshnessLabel = (st?: string): string => {
    const key = st || "requires_manual_review";
    const fallbacks: Record<string, string> = {
      current: "Current",
      approaching_expiration: "Approaching Expiration",
      expired: "Expired",
      source_unavailable: "Source Unavailable",
      conflicting_information: "Conflicting Data",
      requires_manual_review: "Requires Manual Review",
    };
    return t(`fin.fresh_${key}`, fallbacks[key] || key);
  };

  const cycleLabel = (st?: string): string => {
    const key = st || "unspecified";
    const fallbacks: Record<string, string> = {
      open: "Open",
      closed: "Cycle Closed",
      rolling: "Rolling",
      cyclical_check_official: "Annual Cycle",
      unspecified: "Check Official Site",
    };
    return t(`fin.cycle_${key}`, fallbacks[key] || key.replace(/_/g, " "));
  };

  const affordabilityLabel = (st: string): string => {
    const fallbacks: Record<string, string> = {
      within_budget: "Within Budget",
      reachable_with_competitive_aid: "Reachable With Competitive Aid",
      exceeds_budget: "Exceeds Budget",
      missing_cost_data: "Missing Cost Data",
    };
    return t(`fin.afford_${st}`, fallbacks[st] || st.replace(/_/g, " "));
  };

  const runScholarshipMatch = useCallback(async () => {
    setSchLoading(true);
    setError(null);
    try {
      const parsedGpa = parseFloat(gpa4);
      const parsedInc = parseFloat(householdIncome);
      const res = await matchScholarships({
        citizenship_country: citizenship || undefined,
        country_of_residence: residenceCountry || undefined,
        residency_state: residencyState || undefined,
        applicant_type: applicantType,
        degree_level: degreeLevel,
        gpa_4: Number.isNaN(parsedGpa) ? undefined : parsedGpa,
        financial_need_level: needLevel,
        household_income_usd: Number.isNaN(parsedInc) ? undefined : parsedInc,
        destination_country: destinationCountry || undefined,
        include_ineligible: showIneligible,
      });
      setSchResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to run scholarship evaluation");
    } finally {
      setSchLoading(false);
    }
  }, [
    citizenship,
    residenceCountry,
    residencyState,
    applicantType,
    degreeLevel,
    gpa4,
    needLevel,
    householdIncome,
    destinationCountry,
    showIneligible,
  ]);

  const runNetCalculator = useCallback(
    async (instIdOverride?: string) => {
      const targetId = instIdOverride || selectedInstId;
      if (!targetId) return;
      setNetLoading(true);
      setError(null);
      try {
        const parsedGpa = parseFloat(gpa4);
        const parsedInc = parseFloat(householdIncome);
        const parsedBudget = parseFloat(annualBudget);
        const res = await calculateNetPrice({
          institution_id: targetId,
          residency_classification: residencyClass,
          housing_preference: housingPref,
          applicant_type: applicantType,
          degree_level: degreeLevel,
          citizenship_country: citizenship || undefined,
          country_of_residence: residenceCountry || undefined,
          residency_state: residencyState || undefined,
          gpa_4: Number.isNaN(parsedGpa) ? undefined : parsedGpa,
          financial_need_level: needLevel,
          household_income_usd: Number.isNaN(parsedInc) ? undefined : parsedInc,
          annual_budget_usd: Number.isNaN(parsedBudget) ? undefined : parsedBudget,
          program_years: applicantType === "transfer" ? 2 : 4,
          include_competitive_aid: includeCompetitive,
        });
        setNetResult(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to calculate net price");
      } finally {
        setNetLoading(false);
      }
    },
    [
      selectedInstId,
      residencyClass,
      housingPref,
      applicantType,
      degreeLevel,
      citizenship,
      residenceCountry,
      residencyState,
      gpa4,
      needLevel,
      householdIncome,
      annualBudget,
      includeCompetitive,
    ]
  );

  useEffect(() => {
    runScholarshipMatch();
    fetchInstitutions()
      .then((list) => {
        setInstitutions(list);
        const mit = list.find((i) => i.official_name.includes("Massachusetts Institute of Technology")) || list[0];
        if (mit) {
          setSelectedInstId(mit.id);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedInstId && activeTab === "net_price" && !netResult) {
      runNetCalculator(selectedInstId);
    }
  }, [selectedInstId, activeTab, netResult, runNetCalculator]);

  const unverifiedOrPotentialList = netResult
    ? [
        ...(netResult.review_required_aid || []),
        ...(netResult.insufficient_info_aid || []),
        ...(netResult.unallocated_potential_aid || []),
      ]
    : [];

  return (
    <div dir={direction} lang={language.tag} className="min-h-screen bg-[#fafafc] text-zinc-900 pb-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-8 space-y-6">
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-zinc-200 pb-6">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-[11px] font-bold text-emerald-800">
              <Coins className="h-3.5 w-3.5" aria-hidden="true" />
              {t("fin.badge", "Phase 4 Financial Intelligence")}
            </div>
            <h1 className="mt-2 text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900">
              {t("fin.title", "Global Scholarships & Net Price Intelligence")}
            </h1>
            <p className="mt-1 text-sm text-zinc-600 max-w-3xl">
              {t(
                "fin.subtitle",
                "Deterministic scholarship rule matching and transparent component-allocated Cost of Attendance vs. Net Price estimates from published sources."
              )}
            </p>
          </div>
          <Link
            href="/credentials"
            className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3.5 py-2 text-xs font-bold text-zinc-800 hover:bg-zinc-50 shrink-0"
          >
            <Award className="h-3.5 w-3.5 text-indigo-600" aria-hidden="true" />
            {t("nav.credentials", "Credentials")}
          </Link>
        </header>

        {/* Tabs */}
        <div role="tablist" className="inline-flex rounded-xl border border-zinc-200 bg-white p-1">
          <button
            role="tab"
            aria-selected={activeTab === "scholarships"}
            type="button"
            onClick={() => setActiveTab("scholarships")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold ${
              activeTab === "scholarships" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            {t("fin.tab_scholarships", "Scholarship Eligibility Matcher")}
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "net_price"}
            type="button"
            onClick={() => setActiveTab("net_price")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold ${
              activeTab === "net_price" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            <Calculator className="h-3.5 w-3.5" aria-hidden="true" />
            {t("fin.tab_net_price", "Net Price Calculator")}
          </button>
        </div>

        {error && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-900">
            {error}
          </div>
        )}

        {/* Profile / Eligibility Inputs Card */}
        <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 items-end">
            <div>
              <label htmlFor="fin-citizenship" className="block text-[11px] font-bold text-zinc-700 mb-1">
                {t("fin.label_citizenship", "Citizenship")}
              </label>
              <select
                id="fin-citizenship"
                value={citizenship}
                onChange={(e) => setCitizenship(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              >
                <option value="HT">HT</option>
                <option value="NG">NG</option>
                <option value="GH">GH</option>
                <option value="KE">KE</option>
                <option value="ZA">ZA</option>
                <option value="ET">ET</option>
                <option value="RW">RW</option>
                <option value="SN">SN</option>
                <option value="CI">CI</option>
                <option value="JM">JM</option>
                <option value="TT">TT</option>
                <option value="BB">BB</option>
                <option value="BS">BS</option>
                <option value="DO">DO</option>
                <option value="US">US</option>
                <option value="FR">FR</option>
                <option value="IN">IN</option>
                <option value="BR">BR</option>
                <option value="CA">CA</option>
                <option value="GB">GB</option>
                <option value="DE">DE</option>
                <option value="MX">MX</option>
              </select>
            </div>
            <div>
              <label htmlFor="fin-residence" className="block text-[11px] font-bold text-zinc-700 mb-1">
                {t("fin.label_residence", "Residence Country")}
              </label>
              <select
                id="fin-residence"
                value={residenceCountry}
                onChange={(e) => setResidenceCountry(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              >
                <option value="HT">HT</option>
                <option value="NG">NG</option>
                <option value="GH">GH</option>
                <option value="KE">KE</option>
                <option value="ZA">ZA</option>
                <option value="ET">ET</option>
                <option value="RW">RW</option>
                <option value="SN">SN</option>
                <option value="CI">CI</option>
                <option value="JM">JM</option>
                <option value="TT">TT</option>
                <option value="BB">BB</option>
                <option value="BS">BS</option>
                <option value="DO">DO</option>
                <option value="US">US</option>
                <option value="FR">FR</option>
                <option value="IN">IN</option>
                <option value="BR">BR</option>
                <option value="CA">CA</option>
                <option value="GB">GB</option>
                <option value="DE">DE</option>
                <option value="MX">MX</option>
              </select>
            </div>
            <div>
              <label htmlFor="fin-state" className="block text-[11px] font-bold text-zinc-700 mb-1">
                {t("fin.label_state", "US State (optional)")}
              </label>
              <input
                id="fin-state"
                dir="ltr"
                type="text"
                maxLength={2}
                placeholder="CA / MI"
                value={residencyState}
                onChange={(e) => setResidencyState(e.target.value.toUpperCase())}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              />
            </div>
            <div>
              <label htmlFor="fin-pathway" className="block text-[11px] font-bold text-zinc-700 mb-1">
                {t("fin.label_pathway", "Pathway")}
              </label>
              <select
                id="fin-pathway"
                value={applicantType}
                onChange={(e) => setApplicantType(e.target.value as "first_year" | "transfer")}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              >
                <option value="first_year">{t("fin.pathway_first_year", "First-Year")}</option>
                <option value="transfer">{t("fin.pathway_transfer", "Transfer")}</option>
              </select>
            </div>
            <div>
              <label htmlFor="fin-gpa" className="block text-[11px] font-bold text-zinc-700 mb-1">
                {t("fin.label_gpa", "GPA (4.0 eq.)")}
              </label>
              <input
                id="fin-gpa"
                dir="ltr"
                type="number"
                step="0.05"
                min="0"
                max="4"
                value={gpa4}
                onChange={(e) => setGpa4(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              />
            </div>
            <div>
              <label htmlFor="fin-need" className="block text-[11px] font-bold text-zinc-700 mb-1">
                {t("fin.label_need", "Financial Need")}
              </label>
              <select
                id="fin-need"
                value={needLevel}
                onChange={(e) => setNeedLevel(e.target.value as "high" | "moderate" | "low")}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              >
                <option value="high">{t("fin.need_high", "High Need")}</option>
                <option value="moderate">{t("fin.need_moderate", "Moderate Need")}</option>
                <option value="low">{t("fin.need_low", "Low / No Need")}</option>
              </select>
            </div>
            <div>
              <label htmlFor="fin-income" className="block text-[11px] font-bold text-zinc-700 mb-1">
                {t("fin.label_income", "Family Income (USD)")}
              </label>
              <input
                id="fin-income"
                dir="ltr"
                type="number"
                value={householdIncome}
                onChange={(e) => setHouseholdIncome(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              />
            </div>
            <div>
              <label htmlFor="fin-dest" className="block text-[11px] font-bold text-zinc-700 mb-1">
                {t("fin.label_dest", "Destination Filter")}
              </label>
              <select
                id="fin-dest"
                value={destinationCountry}
                onChange={(e) => setDestinationCountry(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              >
                <option value="">{t("fin.all_dest", "All Destinations")}</option>
                <option value="US">US</option>
                <option value="CA">CA</option>
                <option value="GB">GB</option>
                <option value="DE">DE</option>
                <option value="FR">FR</option>
                <option value="AU">AU</option>
                <option value="JP">JP</option>
                <option value="ZA">ZA</option>
                <option value="GH">GH</option>
                <option value="NG">NG</option>
                <option value="BB">BB</option>
                <option value="JM">JM</option>
                <option value="DO">DO</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            {activeTab === "scholarships" ? (
              <>
                <div className="flex flex-wrap items-center gap-4">
                  <label className="inline-flex items-center gap-2 text-xs text-zinc-700">
                    <span>{t("fin.degree_level", "Degree Level")}:</span>
                    <select
                      id="fin-degree-level"
                      value={degreeLevel}
                      onChange={(e) => setDegreeLevel(e.target.value as "bachelors" | "masters" | "doctoral")}
                      className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1 text-xs font-semibold text-zinc-900"
                    >
                      <option value="bachelors">{t("fin.degree_bachelors", "Bachelor's (Undergraduate)")}</option>
                      <option value="masters">{t("fin.degree_masters", "Master's (Graduate)")}</option>
                      <option value="doctoral">{t("fin.degree_doctoral", "Doctoral / PhD")}</option>
                    </select>
                  </label>
                  <label className="inline-flex items-center gap-2 text-xs text-zinc-700">
                    <input
                      type="checkbox"
                      checked={showIneligible}
                      onChange={(e) => setShowIneligible(e.target.checked)}
                      className="rounded border-zinc-300"
                    />
                    {t("fin.show_ineligible", "Show ineligible awards with rule failure reasons")}
                  </label>
                </div>
                <button
                  type="button"
                  onClick={runScholarshipMatch}
                  disabled={schLoading}
                  className="rounded-xl bg-zinc-900 px-4 py-2 text-xs font-bold text-white hover:bg-zinc-800 disabled:opacity-60"
                >
                  {schLoading ? t("fin.evaluating", "Evaluating...") : t("fin.run_match", "Run Deterministic Eligibility Match")}
                </button>
              </>
            ) : (
              <div className="w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 items-end border-t border-zinc-100 pt-3">
                <div className="lg:col-span-2">
                  <label htmlFor="net-inst" className="block text-[11px] font-bold text-zinc-700 mb-1">
                    {t("fin.net_target_inst", "Target University")}
                  </label>
                  <select
                    id="net-inst"
                    value={selectedInstId}
                    onChange={(e) => setSelectedInstId(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
                  >
                    {institutions.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.official_name} ({i.country_code})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="net-degree-level" className="block text-[11px] font-bold text-zinc-700 mb-1">
                    {t("fin.degree_level", "Degree Level")}
                  </label>
                  <select
                    id="net-degree-level"
                    value={degreeLevel}
                    onChange={(e) => setDegreeLevel(e.target.value as "bachelors" | "masters" | "doctoral")}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
                  >
                    <option value="bachelors">{t("fin.degree_bachelors", "Bachelor's (Undergraduate)")}</option>
                    <option value="masters">{t("fin.degree_masters", "Master's (Graduate)")}</option>
                    <option value="doctoral">{t("fin.degree_doctoral", "Doctoral / PhD")}</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="net-res" className="block text-[11px] font-bold text-zinc-700 mb-1">
                    {t("fin.net_tuition_class", "Tuition Classification")}
                  </label>
                  <select
                    id="net-res"
                    value={residencyClass}
                    onChange={(e) => setResidencyClass(e.target.value as "in_state" | "out_of_state" | "international")}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
                  >
                    <option value="international">{t("fin.net_res_intl", "International Student")}</option>
                    <option value="in_state">{t("fin.net_res_in", "In-State Resident")}</option>
                    <option value="out_of_state">{t("fin.net_res_out", "Out-of-State Domestic")}</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="net-budget" className="block text-[11px] font-bold text-zinc-700 mb-1">
                    {t("fin.net_budget", "Annual Budget (USD)")}
                  </label>
                  <input
                    id="net-budget"
                    dir="ltr"
                    type="number"
                    value={annualBudget}
                    onChange={(e) => setAnnualBudget(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => runNetCalculator()}
                  disabled={netLoading}
                  className="rounded-xl bg-emerald-700 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-800 disabled:opacity-60"
                >
                  {netLoading ? t("fin.calculating", "Calculating...") : t("fin.net_calculate_btn", "Calculate Net Price")}
                </button>
                <div className="lg:col-span-6 flex flex-wrap items-center gap-4 text-xs text-zinc-700">
                  <label className="inline-flex items-center gap-1.5">
                    {t("fin.net_housing", "Housing")}:
                    <select
                      value={housingPref}
                      onChange={(e) => setHousingPref(e.target.value as "on_campus" | "off_campus" | "with_family")}
                      className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs"
                    >
                      <option value="on_campus">{t("fin.net_housing_campus", "On Campus")}</option>
                      <option value="off_campus">{t("fin.net_housing_off", "Off Campus")}</option>
                      <option value="with_family">{t("fin.net_housing_family", "With Family ($0 housing)")}</option>
                    </select>
                  </label>
                  <label className="inline-flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={includeCompetitive}
                      onChange={(e) => setIncludeCompetitive(e.target.checked)}
                    />
                    {t("fin.net_include_comp", "Include verified competitive awards alongside statutory aid")}
                  </label>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* TAB 1: SCHOLARSHIP MATCHER */}
        {activeTab === "scholarships" && schResult && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="rounded-xl border border-zinc-200 bg-white p-4">
                <div className="text-[11px] font-bold uppercase text-zinc-500">{t("fin.stat_verified", "Verified Programs")}</div>
                <div className="mt-1 text-2xl font-extrabold">{schResult.total_scholarships}</div>
              </div>
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
                <div className="text-[11px] font-bold uppercase text-emerald-800">{t("fin.stat_eligible", "Eligible")}</div>
                <div className="mt-1 text-2xl font-extrabold text-emerald-900">{schResult.eligible_count}</div>
              </div>
              <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
                <div className="text-[11px] font-bold uppercase text-amber-800">{t("fin.stat_conditional", "Conditionally Eligible")}</div>
                <div className="mt-1 text-2xl font-extrabold text-amber-900">{schResult.conditionally_eligible_count}</div>
              </div>
              <div className="rounded-xl border border-sky-200 bg-sky-50/70 p-4">
                <div className="text-[11px] font-bold uppercase text-sky-800">{t("fin.stat_insufficient", "Insufficient Info")}</div>
                <div className="mt-1 text-2xl font-extrabold text-sky-900">{schResult.insufficient_information_count ?? 0}</div>
              </div>
              <div className="rounded-xl border border-purple-200 bg-purple-50/70 p-4">
                <div className="text-[11px] font-bold uppercase text-purple-800">{t("fin.stat_review", "Manual Review")}</div>
                <div className="mt-1 text-2xl font-extrabold text-purple-900">{schResult.requires_manual_review_count ?? 0}</div>
              </div>
              <div className="rounded-xl border border-zinc-200 bg-white p-4">
                <div className="text-[11px] font-bold uppercase text-zinc-500">{t("fin.stat_ineligible", "Ineligible")}</div>
                <div className="mt-1 text-2xl font-extrabold text-zinc-700">{schResult.ineligible_count}</div>
              </div>
            </div>

            <div className="space-y-3">
              {schResult.results.map((s) => (
                <article key={s.id} className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-3 shadow-xs">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                            s.eligibility_status === "eligible"
                              ? "bg-emerald-100 text-emerald-900"
                              : s.eligibility_status === "conditionally_eligible"
                                ? "bg-amber-100 text-amber-900"
                                : s.eligibility_status === "insufficient_information"
                                  ? "bg-sky-100 text-sky-900"
                                  : s.eligibility_status === "requires_manual_review"
                                    ? "bg-purple-100 text-purple-900"
                                    : "bg-red-100 text-red-900"
                          }`}
                        >
                          {statusLabel(s.eligibility_status)}
                        </span>
                        <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-[10px] font-bold uppercase text-zinc-700">
                          {s.country_code} • {s.provider_type} • {s.funding_type.replace(/_/g, " ")}
                        </span>
                        <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold text-zinc-700">
                          {t("fin.freshness_label", "Freshness")}: {freshnessLabel(s.freshness_status)}
                        </span>
                        {s.application_cycle_status && s.application_cycle_status !== "unspecified" && (
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              s.application_cycle_status === "closed"
                                ? "bg-rose-50 border border-rose-200 text-rose-800"
                                : "bg-sky-50 border border-sky-200 text-sky-800"
                            }`}
                          >
                            {t("fin.cycle_label", "Cycle")}
                            {s.academic_year ? ` (${s.academic_year})` : ""}: {cycleLabel(s.application_cycle_status)}
                          </span>
                        )}
                        {s.covers_international && (
                          <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[10px] font-bold text-indigo-800">
                            {t("fin.badge_intl", "International Eligible")}
                          </span>
                        )}
                        {s.is_guaranteed_statutory && (
                          <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                            {t("fin.badge_statutory", "Statutory / Published Policy")}
                          </span>
                        )}
                      </div>
                      <h2 className="mt-1.5 text-base font-extrabold text-zinc-900">{s.title}</h2>
                      {s.sponsoring_institution && (
                        <div className="text-[11px] font-medium text-zinc-500 mt-0.5">
                          {t("fin.sponsor_label", "Sponsor")}: {s.sponsoring_institution}
                        </div>
                      )}
                      <p className="text-xs text-zinc-600 mt-1">{s.eligibility_summary}</p>
                      {(s.funding_scope?.length || s.duration_renewal_summary) && (
                        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-zinc-600">
                          {s.funding_scope && s.funding_scope.length > 0 && (
                            <span className="rounded bg-zinc-100 px-2 py-0.5 font-mono text-[10px]">
                              {s.funding_scope.join(", ")}
                            </span>
                          )}
                          {s.duration_renewal_summary && (
                            <span>
                              {t("fin.badge_duration", "Duration & Renewal")}: {s.duration_renewal_summary}
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="shrink-0 text-start md:text-end space-y-1">
                      <div dir="ltr" className="text-sm font-extrabold text-zinc-900">
                        {s.native_amount_min !== null &&
                        s.native_amount_min !== undefined &&
                        s.award_currency &&
                        s.award_currency !== "USD"
                          ? s.native_amount_max !== null &&
                            s.native_amount_max !== undefined &&
                            s.native_amount_max !== s.native_amount_min
                            ? `${fmtMoney(s.native_amount_min, s.award_currency)} – ${fmtMoney(s.native_amount_max, s.award_currency)}`
                            : fmtMoney(s.native_amount_min, s.award_currency)
                          : s.award_amount_min_usd !== null && s.award_amount_max_usd !== null
                            ? s.award_amount_min_usd === s.award_amount_max_usd
                              ? fmtMoney(s.award_amount_min_usd, s.award_currency)
                              : `${fmtMoney(s.award_amount_min_usd, s.award_currency)} – ${fmtMoney(s.award_amount_max_usd, s.award_currency)}`
                            : `${t("fin.amount_unpublished", "Amount varies / not published")} — ${s.max_award_info}`}
                      </div>
                      <a
                        href={s.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-700 hover:underline"
                      >
                        {s.source_name} <ExternalLink className="h-3 w-3" aria-hidden="true" />
                      </a>
                    </div>
                  </div>

                  {/* Deterministic Rule Provenance */}
                  {s.rule_evaluations.length > 0 && (
                    <div className="rounded-xl bg-zinc-50 border border-zinc-200/80 p-3 space-y-1.5">
                      <div className="text-[11px] font-bold uppercase text-zinc-500">
                        {t("fin.rule_breakdown", "Deterministic Rule Breakdown")}
                      </div>
                      {s.rule_evaluations.map((r, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-xs">
                          {r.status === "eligible" || r.status === "pass" ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0 mt-0.5" />
                          ) : r.status === "ineligible" || r.status === "fail" ? (
                            <XCircle className="h-3.5 w-3.5 text-red-600 shrink-0 mt-0.5" />
                          ) : r.status === "requires_manual_review" ? (
                            <ShieldAlert className="h-3.5 w-3.5 text-purple-600 shrink-0 mt-0.5" />
                          ) : (
                            <HelpCircle className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
                          )}
                          <span>
                            <strong>{r.human_label}:</strong> {r.detail}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              ))}
            </div>
            <p className="text-[11px] text-zinc-500">{schResult.disclaimer}</p>
          </div>
        )}

        {/* TAB 2: NET PRICE CALCULATOR */}
        {activeTab === "net_price" && netResult && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div className="rounded-xl border border-zinc-200 bg-white p-4">
                <div className="text-[11px] font-bold uppercase text-zinc-500">{t("fin.net_coa", "Gross Total COA")}</div>
                <div dir="ltr" className="mt-1 text-2xl font-extrabold text-zinc-900">
                  {fmtMoney(netResult.total_coa_usd, netResult.currency)}
                </div>
                <div className="text-[11px] text-zinc-500">
                  {t("fin.net_direct_short", "Direct")}: {fmtMoney(netResult.gross_direct_cost_usd, netResult.currency)} •{" "}
                  {t("fin.net_indirect_short", "Indirect")}: {fmtMoney(netResult.gross_indirect_cost_usd, netResult.currency)}
                </div>
              </div>
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
                <div className="text-[11px] font-bold uppercase text-emerald-800">{t("fin.net_aid_applied", "Verified Applicable Aid")}</div>
                <div dir="ltr" className="mt-1 text-2xl font-extrabold text-emerald-900">
                  {fmtMoney(netResult.eligible_aid_min_usd, netResult.currency)} – {fmtMoney(netResult.eligible_aid_max_usd, netResult.currency)}
                </div>
                <div className="text-[11px] text-emerald-800/80">
                  {t("fin.net_guar_short", "Guaranteed")}: {fmtMoney(netResult.guaranteed_aid_max_usd, netResult.currency)} •{" "}
                  {t("fin.net_comp_short", "Competitive")}: {fmtMoney(netResult.competitive_aid_max_usd, netResult.currency)}
                </div>
              </div>
              <div className="rounded-xl border border-indigo-200 bg-indigo-50/70 p-4">
                <div className="text-[11px] font-bold uppercase text-indigo-900">{t("fin.net_est_price", "Est. Annual Net Price (Not Guaranteed)")}</div>
                <div dir="ltr" className="mt-1 text-2xl font-extrabold text-indigo-950">
                  {fmtMoney(netResult.estimated_net_price_min_usd, netResult.currency)} –{" "}
                  {fmtMoney(netResult.estimated_net_price_max_usd, netResult.currency)}
                </div>
                <div dir="ltr" className="text-[11px] text-indigo-800">
                  {t("fin.net_multi_short", "Multi-yr Est.")} ({applicantType === "transfer" ? "2yr" : "4yr"}):{" "}
                  {fmtMoney(netResult.multi_year_net_min_usd, netResult.currency)} – {fmtMoney(netResult.multi_year_net_max_usd, netResult.currency)}
                </div>
              </div>
              <div className="rounded-xl border border-zinc-200 bg-white p-4">
                <div className="text-[11px] font-bold uppercase text-zinc-500">{t("fin.net_verdict", "Affordability Verdict")}</div>
                <div className="mt-1 text-base font-extrabold uppercase text-zinc-900">
                  {affordabilityLabel(netResult.affordability_status)}
                </div>
                <div className="text-[11px] text-zinc-500">
                  {t("fin.net_conf_short", "Confidence")}: {netResult.data_confidence}
                </div>
              </div>
            </div>

            {netResult.warnings.length > 0 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-950 flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
                <div className="space-y-0.5">
                  {netResult.warnings.map((w, i) => (
                    <div key={i}>{w}</div>
                  ))}
                </div>
              </div>
            )}

            {/* Component-level Category Breakdown Table */}
            {netResult.category_breakdown && netResult.category_breakdown.length > 0 && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-3 overflow-x-auto">
                <h2 className="text-sm font-extrabold text-zinc-900">{t("fin.net_cat_table", "Category-Level Cost & Award Allocation")}</h2>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-zinc-200 text-start text-[11px] font-bold uppercase text-zinc-500">
                      <th className="py-2 pe-4 text-start">{t("fin.net_col_cat", "Cost Category")}</th>
                      <th className="py-2 px-3 text-end">{t("fin.net_col_orig", "Published Cost")}</th>
                      <th className="py-2 px-3 text-end">{t("fin.net_col_aid", "Applied Aid")}</th>
                      <th className="py-2 ps-3 text-end">{t("fin.net_col_rem", "Remaining Net Cost")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {netResult.category_breakdown.map((row) => (
                      <tr key={row.category_key}>
                        <td className="py-2 pe-4 font-semibold text-zinc-900">{row.label}</td>
                        <td dir="ltr" className="py-2 px-3 text-end font-mono text-zinc-700">
                          {fmtMoney(row.original_cost_usd, netResult.currency)}
                        </td>
                        <td dir="ltr" className="py-2 px-3 text-end font-mono text-emerald-700">
                          {row.applied_verified_max_usd > 0
                            ? `-${fmtMoney(row.applied_verified_min_usd, netResult.currency)}..-${fmtMoney(row.applied_verified_max_usd, netResult.currency)}`
                            : "—"}
                        </td>
                        <td dir="ltr" className="py-2 ps-3 text-end font-mono font-bold text-zinc-900">
                          {row.remaining_cost_min_usd !== null && row.remaining_cost_min_usd !== undefined
                            ? `${fmtMoney(row.remaining_cost_min_usd, netResult.currency)} – ${fmtMoney(row.remaining_cost_max_usd, netResult.currency)}`
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-3">
                <h2 className="text-sm font-extrabold text-zinc-900">{t("fin.net_verified_sec", "Verified & Applicable Funding")}</h2>
                {netResult.aid_offsets.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-zinc-300 p-4 text-xs text-zinc-600 flex items-start gap-2">
                    <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                    {t("fin.net_none_verified", "No verified and current institutional/statutory awards reduced net price under current criteria.")}
                  </div>
                ) : (
                  <div className="space-y-2">
                    {netResult.aid_offsets.map((a) => (
                      <div key={a.scholarship_id} className="rounded-xl border border-zinc-200 p-3 text-xs flex items-center justify-between gap-3">
                        <div>
                          <div className="font-bold text-zinc-900">{a.title}</div>
                          <div className="text-[11px] text-zinc-500">
                            {a.is_guaranteed_statutory ? t("fin.badge_statutory", "Statutory / Published Policy") : t("fin.net_comp_short", "Competitive")} • {a.provider_type}
                          </div>
                        </div>
                        <div dir="ltr" className="font-mono font-bold text-emerald-800 shrink-0">
                          -{fmtMoney(a.estimated_min_usd, netResult.currency)} .. -{fmtMoney(a.estimated_max_usd, netResult.currency)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {netResult.conditional_aid && netResult.conditional_aid.length > 0 && (
                  <div className="pt-2 space-y-2">
                    <h3 className="text-xs font-extrabold uppercase text-amber-800">{t("fin.net_cond_sec", "Conditional Funding")}</h3>
                    {netResult.conditional_aid.map((c) => (
                      <div key={c.scholarship_id} className="rounded-xl border border-amber-200 bg-amber-50/40 p-3 text-xs">
                        <div className="font-bold text-zinc-900">{c.title}</div>
                        <div className="text-[11px] text-amber-900">{c.reason}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-3">
                <h2 className="text-sm font-extrabold text-zinc-900">
                  {t("fin.net_review_sec", "Requires Verification / Unallocated Potential Funding")}
                </h2>
                {unverifiedOrPotentialList.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-zinc-300 p-4 text-xs text-zinc-600">
                    {t("fin.net_none_review", "None flagged for review or missing information.")}
                  </div>
                ) : (
                  <div className="space-y-2">
                    {unverifiedOrPotentialList.map((u, idx) => (
                      <div key={`${u.scholarship_id}-${idx}`} className="rounded-xl border border-purple-200 bg-purple-50/30 p-3 text-xs space-y-1">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-bold text-zinc-900">{u.title}</span>
                          <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-bold text-purple-900">
                            {freshnessLabel(u.freshness_status)}
                          </span>
                        </div>
                        {u.reason && <div className="text-[11px] text-zinc-600">{u.reason}</div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <p className="text-[11px] text-zinc-500">{netResult.disclaimer}</p>
          </div>
        )}
      </div>
    </div>
  );
}
