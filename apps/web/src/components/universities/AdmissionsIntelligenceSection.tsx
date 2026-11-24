"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Bot,
  Calendar,
  CheckCircle2,
  ClipboardCheck,
  ExternalLink,
  FileWarning,
  Globe2,
  GraduationCap,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  ChecklistItemEvaluation,
  DynamicChecklistResponse,
  fetchInstitutionRequirements,
  fetchPersonalizedChecklist,
  InstitutionAdmissionsSummary,
  InstitutionRequirementItem,
} from "@/lib/api-client";

interface Props {
  institutionId: string;
  institutionName: string;
  acceptsTransfer: boolean;
  acceptsFirstYear: boolean;
}

type ActiveTab = "first_year" | "transfer" | "international" | "deadlines" | "checklist";

const STATUS_BADGE: Record<string, string> = {
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  in_progress: "bg-sky-50 text-sky-700 border-sky-200",
  missing: "bg-rose-50 text-rose-700 border-rose-200",
  needs_verification: "bg-amber-50 text-amber-800 border-amber-200",
  pending: "bg-slate-100 text-slate-700 border-slate-200",
  not_applicable: "bg-slate-50 text-slate-500 border-slate-200",
  waived: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

const ELIGIBILITY_LABELS: Record<string, { label: string; style: string }> = {
  eligible_preliminary: {
    label: "Preliminary Criteria Met",
    style: "bg-emerald-50 text-emerald-800 border-emerald-200",
  },
  in_progress: {
    label: "In Progress",
    style: "bg-sky-50 text-sky-800 border-sky-200",
  },
  needs_information: {
    label: "Needs Profile Information",
    style: "bg-amber-50 text-amber-800 border-amber-200",
  },
  concerns_identified: {
    label: "Eligibility / Prereq Gaps Flagged",
    style: "bg-rose-50 text-rose-800 border-rose-200",
  },
  requirements_unverified: {
    label: "Detailed Rules Unverified",
    style: "bg-slate-100 text-slate-700 border-slate-200",
  },
};

export function AdmissionsIntelligenceSection({
  institutionId,
  institutionName,
  acceptsTransfer,
  acceptsFirstYear,
}: Props) {
  const [activeTab, setActiveTab] = useState<ActiveTab>(acceptsFirstYear ? "first_year" : "transfer");
  const [majorFilter, setMajorFilter] = useState("");
  const [checklistPathway, setChecklistPathway] = useState<"first_year" | "transfer">(
    acceptsTransfer ? "transfer" : "first_year"
  );
  const [summary, setSummary] = useState<InstitutionAdmissionsSummary | null>(null);
  const [checklist, setChecklist] = useState<DynamicChecklistResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      const [sumData, chkData] = await Promise.all([
        fetchInstitutionRequirements(institutionId, {
          major: majorFilter.trim() || undefined,
        }),
        fetchPersonalizedChecklist(institutionId, {
          applicant_type: checklistPathway,
          major: majorFilter.trim() || undefined,
        }),
      ]);
      if (active) {
        setSummary(sumData);
        setChecklist(chkData);
        setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [institutionId, majorFilter, checklistPathway]);

  const filterReqsForTab = (reqs: InstitutionRequirementItem[]) => {
    if (activeTab === "first_year") {
      return reqs.filter((r) => r.applicant_type === "first_year" || r.applicant_type === "all");
    }
    if (activeTab === "transfer") {
      return reqs.filter((r) => r.applicant_type === "transfer" || r.applicant_type === "all");
    }
    if (activeTab === "international") {
      return reqs.filter(
        (r) =>
          r.importance === "conditional" ||
          r.applicant_type.startsWith("international") ||
          ["english_proficiency", "language_proficiency", "credential_evaluation", "certified_translation", "financial_documentation", "national_exam", "secondary_qualification"].includes(r.requirement_type)
      );
    }
    return reqs;
  };

  const renderRequirementCard = (req: InstitutionRequirementItem) => (
    <div key={req.id} className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-slate-200 text-slate-800">
              {req.category}
            </span>
            <span
              className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${
                req.importance === "not_accepted"
                  ? "bg-indigo-50 text-indigo-800 border-indigo-200"
                  : req.importance === "conditional"
                  ? "bg-amber-50 text-amber-800 border-amber-200"
                  : "bg-white text-slate-700 border-slate-300"
              }`}
            >
              {req.importance.replace(/_/g, " ")}
            </span>
            {req.program_name_filter && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200">
                Major: {req.program_name_filter}
              </span>
            )}
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
              <ShieldCheck className="w-3 h-3" />
              {req.verification_status} ({req.academic_year})
            </span>
          </div>
          <h3 className="text-sm font-bold text-slate-900">{req.title}</h3>
        </div>

        <a
          href={req.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:underline shrink-0"
        >
          {req.source_name} <ExternalLink className="w-3 h-3" />
        </a>
      </div>

      {(req.minimum_value || req.maximum_value || req.fee_amount !== null && req.fee_amount !== undefined) && (
        <div className="flex flex-wrap gap-3 text-xs text-slate-700 font-medium">
          {req.minimum_value && (
            <span className="px-2 py-0.5 rounded bg-white border border-slate-200">
              Minimum / Threshold: <strong>{req.minimum_value}</strong>
            </span>
          )}
          {req.maximum_value && (
            <span className="px-2 py-0.5 rounded bg-white border border-slate-200">
              Maximum Cap: <strong>{req.maximum_value}</strong>
            </span>
          )}
          {req.fee_amount !== null && req.fee_amount !== undefined && (
            <span className="px-2 py-0.5 rounded bg-white border border-slate-200">
              Fee: <strong>{req.fee_amount} {req.fee_currency || "USD"}</strong>
              {req.fee_waiver_available ? " (Waiver available)" : ""}
            </span>
          )}
        </div>
      )}

      {req.institution_specific_notes && (
        <p className="text-xs text-slate-600 leading-relaxed">{req.institution_specific_notes}</p>
      )}
    </div>
  );

  const renderChecklistRow = (item: ChecklistItemEvaluation) => (
    <div key={item.requirement_id} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row sm:items-start justify-between gap-2 text-xs">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${STATUS_BADGE[item.status] || STATUS_BADGE.pending}`}>
            {item.status.replace(/_/g, " ")}
          </span>
          <span className="font-bold text-slate-900">{item.title}</span>
          <span className="text-[10px] text-slate-500 uppercase">({item.effective_importance.replace(/_/g, " ")})</span>
        </div>
        {item.explanation && <p className="text-slate-600">{item.explanation}</p>}
        {item.matched_evidence.length > 0 && (
          <p className="text-emerald-700 font-medium">Evidence: {item.matched_evidence.join(", ")}</p>
        )}
        {item.missing_items.length > 0 && (
          <p className="text-rose-700 font-medium">Missing / Needed: {item.missing_items.join(", ")}</p>
        )}
      </div>
      <a
        href={item.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-brand-600 hover:underline font-medium shrink-0"
      >
        Source <ExternalLink className="w-3 h-3" />
      </a>
    </div>
  );

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-6 shadow-sm">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-brand-600">
            <ClipboardCheck className="w-4 h-4" /> Global Admissions Requirements Intelligence
          </div>
          <h2 className="text-lg font-extrabold text-slate-900 mt-1">
            Verified Eligibility, Deadlines & Personalized Checklist
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={majorFilter}
            onChange={(e) => setMajorFilter(e.target.value)}
            placeholder="Filter major (e.g. Economics, CS)..."
            className="w-56 sm:w-64 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <button
            type="button"
            onClick={() => setMajorFilter("Economics")}
            className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-[11px] font-semibold text-slate-700"
          >
            Economics
          </button>
          <button
            type="button"
            onClick={() => setMajorFilter("Computer Science")}
            className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-[11px] font-semibold text-slate-700"
          >
            Computer Science
          </button>
          <Link
            href={`/counselor?institution_id=${institutionId}&pathway=${checklistPathway}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold"
          >
            <Bot className="w-3.5 h-3.5" /> Ask AI Counselor
          </Link>
        </div>
      </div>

      {/* Interactive Tabs */}
      <div className="flex flex-wrap gap-2">
        {[
          { id: "first_year", label: "First-Year Requirements" },
          { id: "transfer", label: "Transfer Requirements" },
          { id: "international", label: "International & Language" },
          { id: "deadlines", label: `Deadlines (${summary?.deadlines.length ?? 0})` },
          { id: "checklist", label: "My Readiness Checklist" },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id as ActiveTab)}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors ${
              activeTab === tab.id
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="h-32 rounded-xl bg-slate-100 animate-pulse" />
      ) : !summary?.has_verified_requirements ? (
        <div className="p-5 rounded-xl bg-amber-50 border border-amber-200 space-y-3 text-xs text-amber-900">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Institutional Admissions Requirements Not Yet Verified</p>
              <p className="mt-1">{summary?.coverage_notice}</p>
            </div>
          </div>
          {summary && summary.country_qualifications.length > 0 && (
            <div className="pt-2 border-t border-amber-200/80 space-y-2">
              <div className="font-bold text-slate-900 flex items-center gap-1.5">
                <Globe2 className="w-4 h-4 text-brand-600" /> National Higher-Education Qualification Framework ({summary.country_code})
              </div>
              {summary.country_qualifications.map((q) => (
                <div key={q.id} className="p-2.5 rounded-lg bg-white border border-amber-200/70 text-slate-700">
                  <div className="font-bold text-slate-900">{q.qualification_name}</div>
                  {q.grading_scale && <div>Scale: {q.grading_scale}</div>}
                  {q.equivalency_notes && <div className="text-slate-600 mt-0.5">{q.equivalency_notes}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : activeTab === "deadlines" ? (
        <div className="space-y-3">
          {summary.deadlines.length === 0 ? (
            <p className="text-xs text-slate-500 italic">No fixed term deadlines curated yet; consult the official portal for rolling or faculty dates.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {summary.deadlines.map((d) => (
                <div key={d.id} className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex justify-between items-start gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
                        {d.applicant_type.replace(/_/g, " ")}
                      </span>
                      <span className="text-xs font-bold text-slate-900">
                        {d.intake_term} &bull; {d.deadline_type.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div className="text-sm font-extrabold text-slate-900 flex items-center gap-1.5">
                      <Calendar className="w-4 h-4 text-brand-600" />
                      {d.deadline_date || "Rolling / See Official Portal"}
                      {d.deadline_time ? ` (${d.deadline_time})` : ""}
                    </div>
                    {d.notes && <p className="text-xs text-slate-600">{d.notes}</p>}
                    <a
                      href={d.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-600 hover:underline"
                    >
                      {d.source_name} <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                  {d.days_remaining !== null && d.days_remaining !== undefined && (
                    <span
                      className={`text-[11px] font-bold px-2.5 py-1 rounded-full shrink-0 border ${
                        d.is_past
                          ? "bg-slate-100 text-slate-600 border-slate-200"
                          : "bg-emerald-50 text-emerald-700 border-emerald-200"
                      }`}
                    >
                      {d.is_past ? `${Math.abs(d.days_remaining)}d ago` : `${d.days_remaining}d left`}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : activeTab === "checklist" && checklist ? (
        <div className="space-y-5">
          {/* Pathway switch + Readiness Header */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-bold text-slate-900">Evaluate as:</span>
                {acceptsFirstYear && (
                  <button
                    type="button"
                    onClick={() => setChecklistPathway("first_year")}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${
                      checklistPathway === "first_year" ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-700"
                    }`}
                  >
                    First-Year
                  </button>
                )}
                {acceptsTransfer && (
                  <button
                    type="button"
                    onClick={() => setChecklistPathway("transfer")}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${
                      checklistPathway === "transfer" ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-700"
                    }`}
                  >
                    Transfer
                  </button>
                )}
                <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${(ELIGIBILITY_LABELS[checklist.eligibility_status] || ELIGIBILITY_LABELS.needs_information).style}`}>
                  {(ELIGIBILITY_LABELS[checklist.eligibility_status] || ELIGIBILITY_LABELS.needs_information).label}
                </span>
              </div>
              <p className="text-xs text-slate-600">
                Checklist evaluated dynamically from your Universal Student Profile and Document Vault for{" "}
                <strong>{institutionName}</strong>{checklist.intended_major ? ` (${checklist.intended_major})` : ""}.
              </p>
            </div>

            <div className="text-right shrink-0">
              <div className="text-[11px] font-medium text-slate-500">Required Readiness</div>
              <div className="text-2xl font-extrabold text-slate-900">{checklist.readiness_pct}%</div>
            </div>
          </div>

          {checklist.eligibility_concerns.length > 0 && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 space-y-1.5 text-xs text-rose-900">
              <div className="font-bold flex items-center gap-1.5">
                <FileWarning className="w-4 h-4 text-rose-700" /> Eligibility & Profile Verification Concerns
              </div>
              <ul className="list-disc list-inside space-y-1">
                {checklist.eligibility_concerns.map((c, idx) => (
                  <li key={idx}>{c}</li>
                ))}
              </ul>
            </div>
          )}

          {checklist.next_actions.length > 0 && (
            <div className="p-4 rounded-xl bg-indigo-50 border border-indigo-200 space-y-1.5 text-xs text-indigo-950">
              <div className="font-bold flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-indigo-700" /> Required Next Actions
              </div>
              <ul className="list-disc list-inside space-y-1">
                {checklist.next_actions.map((a, idx) => (
                  <li key={idx}>{a}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="space-y-3">
            {[
              { title: "Missing Documents & Financial Proofs", rows: checklist.missing_documents },
              { title: "Outstanding Academic & Course Prerequisites", rows: checklist.outstanding_prerequisites },
              { title: "Exam & Administrative Steps", rows: checklist.other_requirements },
              { title: "Completed & Auto-Verified Requirements", rows: checklist.completed_requirements },
              { title: "Not Applicable / Test-Blind / Waived", rows: checklist.not_applicable_requirements },
            ].map(
              (group) =>
                group.rows.length > 0 && (
                  <div key={group.title} className="space-y-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      {group.title} ({group.rows.length})
                    </h4>
                    {group.rows.map(renderChecklistRow)}
                  </div>
                )
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="space-y-3">
            {filterReqsForTab(summary.requirements).length === 0 ? (
              <p className="text-xs text-slate-500 italic">
                No specific {activeTab.replace(/_/g, " ")} rules recorded for this institution under the current filter.
              </p>
            ) : (
              filterReqsForTab(summary.requirements).map(renderRequirementCard)
            )}
          </div>

          {summary.country_qualifications.length > 0 && (
            <div className="pt-4 border-t border-slate-100 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                <GraduationCap className="w-4 h-4 text-brand-600" /> Recognized Qualification & Grading Framework ({summary.country_code})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {summary.country_qualifications.map((q) => (
                  <div key={q.id} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-slate-900">{q.qualification_name}</span>
                      <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-600">
                        {q.qualification_type.replace(/_/g, " ")}
                      </span>
                    </div>
                    {q.grading_scale && <div className="text-slate-600">Scale: {q.grading_scale}</div>}
                    {q.passing_threshold && <div className="text-slate-600">Threshold: {q.passing_threshold}</div>}
                    {q.equivalency_notes && <p className="text-slate-600 pt-0.5">{q.equivalency_notes}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
