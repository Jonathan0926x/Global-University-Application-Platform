"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  ExternalLink,
  ShieldCheck,
  DollarSign,
  Users,
  GraduationCap,
  BookOpen,
  Award,
  Database,
  Clock,
  MapPin,
  Calculator
} from "lucide-react";
import {
  fetchInstitutionDetail,
  fetchInstitutionProvenance,
  createApplication,
  InstitutionDetail,
  DataProvenanceItem
} from "@/lib/api-client";
import { useI18n } from "@/lib/i18n/context";

export default function InstitutionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { formatNumber } = useI18n();
  const institutionId = params?.id as string;

  const [inst, setInst] = useState<InstitutionDetail | null>(null);
  const [provenanceHistory, setProvenanceHistory] = useState<DataProvenanceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creatingApp, setCreatingApp] = useState(false);

  useEffect(() => {
    if (!institutionId) return;
    async function load() {
      try {
        const [detail, prov] = await Promise.all([
          fetchInstitutionDetail(institutionId),
          fetchInstitutionProvenance(institutionId),
        ]);
        setInst(detail);
        setProvenanceHistory(prov);
      } catch (err) {
        console.error(err);
        setError("Unable to load institution details.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [institutionId]);

  const handleStartApp = async (pathway: "first_year" | "transfer") => {
    if (!inst) return;
    setCreatingApp(true);
    try {
      await createApplication(inst.id, pathway, "Undecided");
      router.push(pathway === "transfer" ? "/transfer" : "/first-year");
    } catch (err) {
      console.error(err);
      setCreatingApp(false);
    }
  };

  const renderMoney = (val?: number | null, currency: string = "USD") => {
    if (val === null || val === undefined) {
      return <span className="text-slate-500 italic font-normal">Not Reported</span>;
    }
    return `${currency === "USD" ? "$" : `${currency} `}${formatNumber(Math.round(val))}`;
  };

  const renderPct = (val?: number | null) => {
    if (val === null || val === undefined) {
      return <span className="text-slate-500 italic font-normal">Not Reported</span>;
    }
    return `${val}%`;
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-12">
        <div className="h-48 rounded-2xl bg-slate-100 animate-pulse" />
      </div>
    );
  }

  if (error || !inst) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center space-y-4">
        <Building2 className="w-12 h-12 text-slate-400 mx-auto" />
        <h1 className="text-xl font-bold text-slate-900">{error || "Institution not found"}</h1>
        <Link href="/universities" className="inline-flex items-center gap-2 text-sm text-brand-600 hover:underline">
          <ArrowLeft className="w-4 h-4" /> Back to Global University Catalog
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div>
        <Link
          href="/universities"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 mb-4"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Global University Catalog
        </Link>

        {/* Top Institution Intelligence Banner */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700">
                  {inst.institution_type.replace(/_/g, " ")}
                </span>
                {inst.control_type && (
                  <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
                    {inst.control_type.replace(/_/g, " ")}
                  </span>
                )}
                {!inst.is_main_campus && (
                  <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                    Branch Campus
                  </span>
                )}
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Verified ({inst.data_reporting_year || "2023-2024"})
                </span>
              </div>

              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                {inst.official_name}
              </h1>

              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600">
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  {[inst.city, inst.state_province, inst.postal_code, inst.country_code].filter(Boolean).join(", ")}
                </span>
                {inst.carnegie_classification && (
                  <span>&bull; {inst.carnegie_classification}</span>
                )}
                {inst.accrediting_body && (
                  <span className="flex items-center gap-1">
                    &bull; <Award className="w-3.5 h-3.5 text-emerald-600" /> Accredited by {inst.accrediting_body}
                  </span>
                )}
              </div>

              {/* Official External Identifiers */}
              <div className="flex flex-wrap gap-2 pt-1 text-[11px] font-mono text-slate-600">
                {inst.ipeds_unit_id && <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200/60">IPEDS: {inst.ipeds_unit_id}</span>}
                {inst.ope_id && <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200/60">OPEID: {inst.ope_id}</span>}
                {inst.ror_id && <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200/60">ROR: {inst.ror_id}</span>}
                {inst.openalex_id && <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200/60">OpenAlex: {inst.openalex_id}</span>}
              </div>

              {inst.parent_institution_id && (
                <div className="text-xs text-brand-600">
                  <Link href={`/universities/${inst.parent_institution_id}`} className="hover:underline">
                    &rarr; View Parent Main Campus Profile
                  </Link>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col gap-2.5 min-w-[220px]">
              {inst.accepts_transfer && (
                <button
                  onClick={() => handleStartApp("transfer")}
                  disabled={creatingApp}
                  className="px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-colors"
                >
                  Start Transfer Application
                </button>
              )}
              {inst.accepts_first_year && (
                <button
                  onClick={() => handleStartApp("first_year")}
                  disabled={creatingApp}
                  className="px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-800 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
                >
                  <GraduationCap className="w-4 h-4" /> Start First-Year Application
                </button>
              )}
              <div className="flex flex-wrap gap-2 pt-1 text-xs">
                {inst.official_website && (
                  <a
                    href={inst.official_website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-brand-600 hover:underline"
                  >
                    Website <ExternalLink className="w-3 h-3" />
                  </a>
                )}
                {(inst.application_portal_url || inst.admissions_website) && (
                  <a
                    href={inst.application_portal_url || inst.admissions_website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-brand-600 hover:underline"
                  >
                    Admissions Portal <ExternalLink className="w-3 h-3" />
                  </a>
                )}
                {inst.net_price_calculator_url && (
                  <a
                    href={inst.net_price_calculator_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-emerald-700 hover:underline"
                  >
                    <Calculator className="w-3 h-3" /> Net Price Calculator
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Key Metrics Panels */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Panel 1: Tuition & Cost Intelligence */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4 shadow-sm">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-emerald-600" /> Cost & Affordability
          </h2>
          <dl className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-600">In-State Tuition & Fees</dt>
              <dd className="font-semibold text-slate-900">{renderMoney(inst.tuition_in_state, inst.currency)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Out-of-State / Intl Tuition</dt>
              <dd className="font-semibold text-slate-900">{renderMoney(inst.tuition_out_of_state, inst.currency)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Total Cost of Attendance</dt>
              <dd className="font-semibold text-slate-900">{renderMoney(inst.cost_of_attendance, inst.currency)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Avg. Net Price (Federal)</dt>
              <dd className="font-semibold text-emerald-700">{renderMoney(inst.avg_net_price, inst.currency)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Undergrad Application Fee</dt>
              <dd className="font-semibold text-slate-900">{renderMoney(inst.undergrad_application_fee, inst.currency)}</dd>
            </div>
          </dl>
        </div>

        {/* Panel 2: Admissions & Benchmarks */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4 shadow-sm">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 flex items-center gap-2">
            <GraduationCap className="w-4 h-4 text-indigo-600" /> Admissions Benchmarks
          </h2>
          <dl className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-600">Acceptance Rate</dt>
              <dd className="font-semibold text-slate-900">{renderPct(inst.acceptance_rate)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Open Admissions</dt>
              <dd className="font-semibold text-slate-900">
                {inst.open_admissions === null || inst.open_admissions === undefined
                  ? <span className="text-slate-500 italic font-normal">Not Reported</span>
                  : inst.open_admissions ? "Yes (Open Access)" : "Selective"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Academic Calendar</dt>
              <dd className="font-semibold text-slate-900 capitalize">
                {inst.calendar_system ? inst.calendar_system.replace(/_/g, " ") : <span className="text-slate-500 italic font-normal">Not Reported</span>}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">SAT Math (25th–75th)</dt>
              <dd className="font-semibold text-slate-900">
                {inst.sat_math_25 && inst.sat_math_75 ? `${inst.sat_math_25}–${inst.sat_math_75}` : <span className="text-slate-500 italic font-normal">Not Reported</span>}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">ACT Composite (25th–75th)</dt>
              <dd className="font-semibold text-slate-900">
                {inst.act_composite_25 && inst.act_composite_75 ? `${inst.act_composite_25}–${inst.act_composite_75}` : <span className="text-slate-500 italic font-normal">Not Reported</span>}
              </dd>
            </div>
          </dl>
        </div>

        {/* Panel 3: Enrollment & Graduation Outcomes */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4 shadow-sm">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 flex items-center gap-2">
            <Users className="w-4 h-4 text-sky-600" /> Enrollment & Outcomes
          </h2>
          <dl className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-600">Total Enrollment</dt>
              <dd className="font-semibold text-slate-900">
                {inst.total_enrollment == null ? <span className="text-slate-500 italic font-normal">Not Reported</span> : formatNumber(inst.total_enrollment)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">4-Year / Less-than-4-Yr Completion</dt>
              <dd className="font-semibold text-slate-900">
                {renderPct(inst.completion_rate_4yr ?? inst.completion_rate_less_4yr)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">First-Year Retention Rate</dt>
              <dd className="font-semibold text-slate-900">{renderPct(inst.retention_rate)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">10-Year Median Earnings</dt>
              <dd className="font-semibold text-slate-900">{renderMoney(inst.median_earnings_10yr, inst.currency)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">International Students %</dt>
              <dd className="font-semibold text-slate-900">{renderPct(inst.pct_international)}</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Branch Campuses (if any) */}
      {inst.campuses && inst.campuses.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4 shadow-sm">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600">
            Associated Campuses ({inst.campuses.length})
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {inst.campuses.map((c) => (
              <Link
                key={c.id}
                href={`/universities/${c.id}`}
                className="p-3 rounded-xl border border-slate-200 bg-slate-50 hover:border-brand-500 hover:bg-white text-xs transition-colors"
              >
                <div className="font-bold text-slate-900">{c.official_name}</div>
                <div className="text-slate-600 mt-0.5">{[c.city, c.state_province, c.country_code].filter(Boolean).join(", ")}</div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Academic Programs & Versioned Costs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4 shadow-sm">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-brand-600" /> Academic Program Classifications ({inst.programs.length})
          </h2>
          {inst.programs.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {inst.programs.map((p) => (
                <span
                  key={p.id}
                  className="text-xs px-2.5 py-1 rounded-lg bg-slate-50 border border-slate-200 text-slate-800"
                >
                  {p.cip_code ? <span className="font-mono text-slate-500 mr-1.5">CIP {p.cip_code}</span> : null}
                  {p.program_name}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">Program classifications not reported in current dataset.</p>
          )}
        </div>

        {/* Versioned Cost Breakdown */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4 shadow-sm">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 flex items-center gap-2">
            <Database className="w-4 h-4 text-emerald-600" /> Published Cost Breakdowns ({inst.costs.length})
          </h2>
          {inst.costs.length > 0 ? (
            <div className="space-y-3">
              {inst.costs.map((cost) => (
                <div key={cost.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                  <div className="flex justify-between font-bold text-slate-900">
                    <span className="capitalize">{cost.student_type.replace(/_/g, " ")} ({cost.academic_year})</span>
                    <span>Total Est: {renderMoney(cost.total_estimated_cost, cost.currency)}</span>
                  </div>
                  <div className="text-slate-600 flex flex-wrap gap-x-4 gap-y-1">
                    <span>Tuition: {renderMoney(cost.tuition, cost.currency)}</span>
                    <span>Fees: {renderMoney(cost.mandatory_fees, cost.currency)}</span>
                    <span>Room/Board: {renderMoney(cost.room_board, cost.currency)}</span>
                    <span>Books: {renderMoney(cost.books_supplies, cost.currency)}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">Itemized cost tables not reported.</p>
          )}
        </div>
      </div>

      {/* Data Provenance & Verification Audit Trail */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4 shadow-sm">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600 flex items-center gap-2">
          <Clock className="w-4 h-4 text-indigo-600" /> Data Provenance & Verification Trail
        </h2>
        {provenanceHistory.length > 0 ? (
          <div className="space-y-2.5">
            {provenanceHistory.map((p) => (
              <div
                key={p.id}
                className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-900">{p.source_name}</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {p.confidence_level}
                    </span>
                    {p.is_current && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-brand-50 text-brand-700 border border-brand-200">
                        Current Snapshot
                      </span>
                    )}
                  </div>
                  <div className="text-slate-600 mt-1 flex flex-wrap gap-3">
                    <span>Method: {p.collection_method}</span>
                    {p.academic_year && <span>Cycle: {p.academic_year}</span>}
                    <span>Retrieved: {new Date(p.retrieved_at).toLocaleDateString()}</span>
                    {p.data_hash && <span className="font-mono">SHA-256: {p.data_hash.slice(0, 12)}...</span>}
                  </div>
                </div>
                {p.source_url && (
                  <a
                    href={p.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-brand-600 hover:underline font-medium shrink-0"
                  >
                    Source Dataset <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic">No provenance snapshots recorded yet.</p>
        )}
      </div>
    </div>
  );
}
