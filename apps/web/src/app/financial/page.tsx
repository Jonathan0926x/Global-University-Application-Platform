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

function fmtUsd(val?: number | null): string {
  if (val === null || val === undefined) return "Not published";
  return `$${Math.round(val).toLocaleString("en-US")}`;
}

export default function FinancialIntelligencePage() {
  const { t, direction, language } = useI18n();
  const [activeTab, setActiveTab] = useState<"scholarships" | "net_price">("scholarships");

  // Shared student inputs
  const [citizenship, setCitizenship] = useState("HT");
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

  const runScholarshipMatch = useCallback(async () => {
    setSchLoading(true);
    setError(null);
    try {
      const parsedGpa = parseFloat(gpa4);
      const parsedInc = parseFloat(householdIncome);
      const res = await matchScholarships({
        citizenship_country: citizenship || undefined,
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
  }, [citizenship, residencyState, applicantType, degreeLevel, gpa4, needLevel, householdIncome, destinationCountry, showIneligible]);

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
          citizenship_country: citizenship || undefined,
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
    [selectedInstId, residencyClass, housingPref, applicantType, citizenship, residencyState, gpa4, needLevel, householdIncome, annualBudget, includeCompetitive]
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

  return (
    <div dir={direction} lang={language.tag} className="min-h-screen bg-[#fafafc] text-zinc-900 pb-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-8 space-y-6">
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-zinc-200 pb-6">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-[11px] font-bold text-emerald-800">
              <Coins className="h-3.5 w-3.5" aria-hidden="true" />
              Phase 4 Financial Intelligence
            </div>
            <h1 className="mt-2 text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900">
              {t("fin.title", "Global Scholarships & Net Price Intelligence")}
            </h1>
            <p className="mt-1 text-sm text-zinc-600 max-w-3xl">
              {t(
                "fin.subtitle",
                "Deterministic scholarship rule matching and transparent Total Cost of Attendance vs. Net Out-of-Pocket estimates from published institutional and government data."
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
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 items-end">
            <div>
              <label htmlFor="fin-citizenship" className="block text-[11px] font-bold text-zinc-700 mb-1">
                Citizenship
              </label>
              <select
                id="fin-citizenship"
                value={citizenship}
                onChange={(e) => setCitizenship(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              >
                <option value="HT">Haiti (HT)</option>
                <option value="US">United States (US)</option>
                <option value="FR">France (FR)</option>
                <option value="IN">India (IN)</option>
                <option value="NG">Nigeria (NG)</option>
                <option value="BR">Brazil (BR)</option>
                <option value="CA">Canada (CA)</option>
                <option value="GB">UK (GB)</option>
                <option value="DE">Germany (DE)</option>
                <option value="MX">Mexico (MX)</option>
              </select>
            </div>
            <div>
              <label htmlFor="fin-state" className="block text-[11px] font-bold text-zinc-700 mb-1">
                US State (optional)
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
                Pathway
              </label>
              <select
                id="fin-pathway"
                value={applicantType}
                onChange={(e) => setApplicantType(e.target.value as "first_year" | "transfer")}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              >
                <option value="first_year">First-Year</option>
                <option value="transfer">Transfer</option>
              </select>
            </div>
            <div>
              <label htmlFor="fin-gpa" className="block text-[11px] font-bold text-zinc-700 mb-1">
                GPA (4.0 eq.)
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
                Financial Need
              </label>
              <select
                id="fin-need"
                value={needLevel}
                onChange={(e) => setNeedLevel(e.target.value as "high" | "moderate" | "low")}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              >
                <option value="high">High Need</option>
                <option value="moderate">Moderate Need</option>
                <option value="low">Low / No Need</option>
              </select>
            </div>
            <div>
              <label htmlFor="fin-income" className="block text-[11px] font-bold text-zinc-700 mb-1">
                Family Income (USD)
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
                Destination Filter
              </label>
              <select
                id="fin-dest"
                value={destinationCountry}
                onChange={(e) => setDestinationCountry(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
              >
                <option value="">All Destinations</option>
                <option value="US">United States (US)</option>
                <option value="CA">Canada (CA)</option>
                <option value="GB">United Kingdom (GB)</option>
                <option value="DE">Germany (DE)</option>
                <option value="FR">France (FR)</option>
                <option value="AU">Australia (AU)</option>
                <option value="JP">Japan (JP)</option>
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
                    Show ineligible awards with rule failure reasons
                  </label>
                </div>
                <button
                  type="button"
                  onClick={runScholarshipMatch}
                  disabled={schLoading}
                  className="rounded-xl bg-zinc-900 px-4 py-2 text-xs font-bold text-white hover:bg-zinc-800 disabled:opacity-60"
                >
                  {schLoading ? "Evaluating..." : "Run Deterministic Eligibility Match"}
                </button>
              </>
            ) : (
              <div className="w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end border-t border-zinc-100 pt-3">
                <div className="lg:col-span-2">
                  <label htmlFor="net-inst" className="block text-[11px] font-bold text-zinc-700 mb-1">
                    Target University
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
                  <label htmlFor="net-res" className="block text-[11px] font-bold text-zinc-700 mb-1">
                    Tuition Classification
                  </label>
                  <select
                    id="net-res"
                    value={residencyClass}
                    onChange={(e) => setResidencyClass(e.target.value as "in_state" | "out_of_state" | "international")}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
                  >
                    <option value="international">International Student</option>
                    <option value="in_state">In-State Resident</option>
                    <option value="out_of_state">Out-of-State Domestic</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="net-budget" className="block text-[11px] font-bold text-zinc-700 mb-1">
                    Annual Budget (USD)
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
                  {netLoading ? "Calculating..." : "Calculate Net Price"}
                </button>
                <div className="lg:col-span-5 flex flex-wrap items-center gap-4 text-xs text-zinc-700">
                  <label className="inline-flex items-center gap-1.5">
                    Housing:
                    <select
                      value={housingPref}
                      onChange={(e) => setHousingPref(e.target.value as "on_campus" | "off_campus" | "with_family")}
                      className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs"
                    >
                      <option value="on_campus">On Campus</option>
                      <option value="off_campus">Off Campus</option>
                      <option value="with_family">With Family ($0 housing)</option>
                    </select>
                  </label>
                  <label className="inline-flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={includeCompetitive}
                      onChange={(e) => setIncludeCompetitive(e.target.checked)}
                    />
                    Include eligible competitive awards alongside guaranteed/statutory aid
                  </label>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* TAB 1: SCHOLARSHIP MATCHER */}
        {activeTab === "scholarships" && schResult && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-xl border border-zinc-200 bg-white p-4">
                <div className="text-[11px] font-bold uppercase text-zinc-500">Verified Programs</div>
                <div className="mt-1 text-2xl font-extrabold">{schResult.total_scholarships}</div>
              </div>
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
                <div className="text-[11px] font-bold uppercase text-emerald-800">Eligible</div>
                <div className="mt-1 text-2xl font-extrabold text-emerald-900">{schResult.eligible_count}</div>
              </div>
              <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
                <div className="text-[11px] font-bold uppercase text-amber-800">Conditionally Eligible</div>
                <div className="mt-1 text-2xl font-extrabold text-amber-900">{schResult.conditionally_eligible_count}</div>
              </div>
              <div className="rounded-xl border border-zinc-200 bg-white p-4">
                <div className="text-[11px] font-bold uppercase text-zinc-500">Ineligible (Excluded)</div>
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
                                : "bg-red-100 text-red-900"
                          }`}
                        >
                          {s.eligibility_status.replace(/_/g, " ")}
                        </span>
                        <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-[10px] font-bold uppercase text-zinc-700">
                          {s.country_code} • {s.provider_type} • {s.funding_type.replace(/_/g, " ")}
                        </span>
                        {s.covers_international && (
                          <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[10px] font-bold text-indigo-800">
                            International Eligible
                          </span>
                        )}
                        {s.is_guaranteed_statutory && (
                          <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                            Guaranteed / Statutory Policy
                          </span>
                        )}
                      </div>
                      <h2 className="mt-1.5 text-base font-extrabold text-zinc-900">{s.title}</h2>
                      <p className="text-xs text-zinc-600 mt-1">{s.eligibility_summary}</p>
                    </div>

                    <div className="shrink-0 text-start md:text-end space-y-1">
                      <div dir="ltr" className="text-sm font-extrabold text-zinc-900">
                        {s.award_amount_min_usd !== null && s.award_amount_max_usd !== null
                          ? `${fmtUsd(s.award_amount_min_usd)} – ${fmtUsd(s.award_amount_max_usd)}`
                          : s.max_award_info}
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
                      <div className="text-[11px] font-bold uppercase text-zinc-500">Deterministic Rule Breakdown</div>
                      {s.rule_evaluations.map((r, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-xs">
                          {r.status === "pass" ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0 mt-0.5" />
                          ) : r.status === "fail" ? (
                            <XCircle className="h-3.5 w-3.5 text-red-600 shrink-0 mt-0.5" />
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
                <div className="text-[11px] font-bold uppercase text-zinc-500">Gross Total COA</div>
                <div dir="ltr" className="mt-1 text-2xl font-extrabold text-zinc-900">
                  {fmtUsd(netResult.total_coa_usd)}
                </div>
                <div className="text-[11px] text-zinc-500">
                  Direct: {fmtUsd(netResult.gross_direct_cost_usd)} • Indirect: {fmtUsd(netResult.gross_indirect_cost_usd)}
                </div>
              </div>
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
                <div className="text-[11px] font-bold uppercase text-emerald-800">Eligible Aid Offset</div>
                <div dir="ltr" className="mt-1 text-2xl font-extrabold text-emerald-900">
                  {fmtUsd(netResult.eligible_aid_min_usd)} – {fmtUsd(netResult.eligible_aid_max_usd)}
                </div>
                <div className="text-[11px] text-emerald-800/80">
                  Guaranteed: {fmtUsd(netResult.guaranteed_aid_max_usd)} • Competitive: {fmtUsd(netResult.competitive_aid_max_usd)}
                </div>
              </div>
              <div className="rounded-xl border border-indigo-200 bg-indigo-50/70 p-4">
                <div className="text-[11px] font-bold uppercase text-indigo-900">Est. Annual Net Price</div>
                <div dir="ltr" className="mt-1 text-2xl font-extrabold text-indigo-950">
                  {fmtUsd(netResult.estimated_net_price_min_usd)} – {fmtUsd(netResult.estimated_net_price_max_usd)}
                </div>
                <div dir="ltr" className="text-[11px] text-indigo-800">
                  Multi-yr ({applicantType === "transfer" ? "2yr" : "4yr"}): {fmtUsd(netResult.multi_year_net_min_usd)} –{" "}
                  {fmtUsd(netResult.multi_year_net_max_usd)}
                </div>
              </div>
              <div className="rounded-xl border border-zinc-200 bg-white p-4">
                <div className="text-[11px] font-bold uppercase text-zinc-500">Affordability Verdict</div>
                <div className="mt-1 text-base font-extrabold uppercase text-zinc-900">
                  {netResult.affordability_status.replace(/_/g, " ")}
                </div>
                <div className="text-[11px] text-zinc-500">Confidence: {netResult.data_confidence}</div>
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

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-3">
                <h2 className="text-sm font-extrabold text-zinc-900">Direct &amp; Indirect Cost Schedule</h2>
                <div className="divide-y divide-zinc-100 text-xs">
                  {[...netResult.direct_billable_items, ...netResult.indirect_living_items].map((item) => (
                    <div key={item.key} className="py-2 flex items-start justify-between gap-3">
                      <div>
                        <div className="font-semibold text-zinc-900">{item.label}</div>
                        <div className="text-[11px] text-zinc-500">
                          {item.category.replace(/_/g, " ")} {item.notes ? `• ${item.notes}` : ""}
                        </div>
                      </div>
                      <span dir="ltr" className="font-mono font-bold text-zinc-900 shrink-0">
                        {fmtUsd(item.amount_usd)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-3">
                <h2 className="text-sm font-extrabold text-zinc-900">Matched Eligible Aid &amp; Scholarships</h2>
                {netResult.aid_offsets.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-zinc-300 p-4 text-xs text-zinc-600 flex items-start gap-2">
                    <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                    No eligible institutional or portable scholarships matched the selected residency/citizenship &amp; need criteria.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {netResult.aid_offsets.map((a) => (
                      <div key={a.scholarship_id} className="rounded-xl border border-zinc-200 p-3 text-xs flex items-center justify-between gap-3">
                        <div>
                          <div className="font-bold text-zinc-900">{a.title}</div>
                          <div className="text-[11px] text-zinc-500">
                            {a.is_guaranteed_statutory ? "Guaranteed / Statutory" : "Competitive Merit/Need"} • {a.provider_type}
                          </div>
                        </div>
                        <div dir="ltr" className="font-mono font-bold text-emerald-800 shrink-0">
                          -{fmtUsd(a.estimated_min_usd)} to -{fmtUsd(a.estimated_max_usd)}
                        </div>
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
