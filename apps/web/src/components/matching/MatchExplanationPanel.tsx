"use client";

import React from "react";
import Link from "next/link";
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  ExternalLink,
  Calendar,
  Calculator,
  MinusCircle,
  BookOpen,
  DollarSign,
  ArrowRightLeft,
} from "lucide-react";
import type {
  FactorStatus,
  UniversityMatchRecommendation,
} from "@/lib/api-client";

export function factorStatusBadge(status: FactorStatus) {
  switch (status) {
    case "verified_match":
      return {
        label: "Verified Match",
        cls: "bg-emerald-50 text-emerald-800 border-emerald-200",
        Icon: CheckCircle2,
      };
    case "partial_match":
      return {
        label: "Partial Match",
        cls: "bg-sky-50 text-sky-800 border-sky-200",
        Icon: BookOpen,
      };
    case "potential_concern":
      return {
        label: "Potential Concern",
        cls: "bg-rose-50 text-rose-800 border-rose-200",
        Icon: AlertTriangle,
      };
    case "insufficient_information":
      return {
        label: "Insufficient Info",
        cls: "bg-amber-50 text-amber-800 border-amber-200",
        Icon: HelpCircle,
      };
    default:
      return {
        label: "Not Applicable",
        cls: "bg-zinc-100 text-zinc-700 border-zinc-200",
        Icon: MinusCircle,
      };
  }
}

export function MatchExplanationPanel({
  rec,
}: {
  rec: UniversityMatchRecommendation;
}) {
  return (
    <div className="mt-5 border-t border-zinc-200 pt-5 space-y-5 text-start">
      {/* Transparent Formula + Published vs Estimated Cost Basis */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
        <div className="lg:col-span-8 rounded-xl border border-zinc-200 bg-zinc-50 p-3.5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-700">
            <Calculator className="h-4 w-4 text-indigo-600 shrink-0" />
            <span>Exact Scoring Formula & Weight Audit</span>
          </div>
          <p dir="ltr" className="mt-1.5 font-mono text-xs text-zinc-800 break-words">
            {rec.calculation_formula}
          </p>
        </div>

        <div className="lg:col-span-4 rounded-xl border border-zinc-200 bg-zinc-50 p-3.5 text-xs">
          <div className="flex items-center justify-between gap-2 font-semibold text-zinc-800">
            <span className="inline-flex items-center gap-1.5">
              <DollarSign className="h-3.5 w-3.5 text-indigo-600" />
              Cost & Funding Basis
            </span>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                rec.cost_is_estimated
                  ? "bg-amber-50 text-amber-800 border-amber-200"
                  : "bg-emerald-50 text-emerald-800 border-emerald-200"
              }`}
            >
              {rec.cost_is_estimated ? "Estimated / Composite" : "Official Published"}
            </span>
          </div>
          <p className="mt-1.5 text-zinc-700">
            {rec.estimated_net_cost !== null && rec.estimated_net_cost !== undefined
              ? `Annual estimate: $${Math.round(rec.estimated_net_cost).toLocaleString()} USD`
              : "Cost schedule not yet verified"}
            {rec.published_tuition !== null && rec.published_tuition !== undefined
              ? ` (Tuition: $${Math.round(rec.published_tuition).toLocaleString()})`
              : ""}
          </p>
          {rec.cost_basis && (
            <p className="mt-0.5 text-[11px] text-zinc-500">{rec.cost_basis}</p>
          )}
        </div>
      </div>

      {/* Factor-by-Factor Breakdown per Dimension */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {rec.dimensions.map((dim) => {
          const dimBadge = factorStatusBadge(dim.status);
          return (
            <div
              key={dim.key}
              className="rounded-xl border border-zinc-200 bg-white p-4 flex flex-col gap-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className="text-sm font-semibold text-zinc-900">
                    {dim.label}
                  </h4>
                  <p className="text-xs text-zinc-600 mt-0.5">{dim.summary}</p>
                </div>
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium shrink-0 ${dimBadge.cls}`}
                >
                  <dimBadge.Icon className="h-3 w-3" />
                  {dimBadge.label}
                </span>
              </div>

              <div className="flex items-center justify-between text-xs text-zinc-600 border-y border-zinc-100 py-1.5">
                <span>
                  Applied weight:{" "}
                  <strong className="text-zinc-900">
                    {(dim.weight_applied * 100).toFixed(1)}%
                  </strong>
                </span>
                <span>
                  Configured weight:{" "}
                  <strong className="text-zinc-900">
                    {(dim.weight_configured * 100).toFixed(0)}%
                  </strong>
                </span>
              </div>

              <ul className="space-y-2.5">
                {dim.factors.map((f, idx) => {
                  const badge = factorStatusBadge(f.status);
                  return (
                    <li
                      key={`${dim.key}-factor-${idx}`}
                      className="rounded-lg bg-zinc-50 border border-zinc-200/70 p-2.5 text-xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-zinc-900">
                          {f.name}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium shrink-0 ${badge.cls}`}
                        >
                          <badge.Icon className="h-2.5 w-2.5" />
                          {badge.label}
                        </span>
                      </div>
                      <p className="mt-1 text-zinc-700 leading-relaxed">
                        {f.detail}
                      </p>
                      {(f.source_name || f.source_url) && (
                        <div className="mt-1.5 flex items-center gap-2 text-[11px] text-zinc-600">
                          <span>Source: {f.source_name || "Official Record"}</span>
                          {f.source_url && (
                            <a
                              href={f.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-0.5 text-indigo-700 hover:underline font-medium"
                            >
                              Verify
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>

      {/* Categorized Takeaways */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-3.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-900">
            <CheckCircle2 className="h-4 w-4 text-emerald-700" />
            Positive Alignment Factors ({rec.positive_factors.length})
          </div>
          {rec.positive_factors.length > 0 ? (
            <ul className="mt-2 space-y-1.5 text-xs text-emerald-900 list-disc ps-4">
              {rec.positive_factors.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-emerald-800/80">
              No verified positive criteria recorded yet.
            </p>
          )}
        </div>

        <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-3.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-900">
            <HelpCircle className="h-4 w-4 text-amber-700" />
            Missing Information ({rec.missing_information.length})
          </div>
          {rec.missing_information.length > 0 ? (
            <ul className="mt-2 space-y-1.5 text-xs text-amber-900 list-disc ps-4">
              {rec.missing_information.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-amber-800/80">
              All core profile and institutional inputs are present.
            </p>
          )}
        </div>

        <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-3.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-900">
            <AlertTriangle className="h-4 w-4 text-rose-700" />
            Requirements & Concerns ({rec.unsatisfied_requirements.length + rec.financial_concerns.length})
          </div>
          {rec.unsatisfied_requirements.length + rec.financial_concerns.length > 0 ? (
            <ul className="mt-2 space-y-1.5 text-xs text-rose-900 list-disc ps-4">
              {rec.unsatisfied_requirements.map((item, i) => (
                <li key={`req-${i}`}>{item}</li>
              ))}
              {rec.financial_concerns.map((item, i) => (
                <li key={`fin-${i}`} className="font-medium">
                  {item}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-rose-800/80">
              No unsatisfied mandatory requirements or budget gaps flagged.
            </p>
          )}
        </div>
      </div>

      {/* Transfer Uncertainties, Deadlines & Action Links */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 rounded-xl border border-zinc-200 bg-zinc-50 p-4">
        <div className="space-y-2 flex-1">
          {rec.transfer_uncertainties.length > 0 && (
            <div className="flex items-start gap-2 text-xs text-zinc-800">
              <ArrowRightLeft className="h-4 w-4 text-indigo-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Transfer Uncertainties: </span>
                <span>{rec.transfer_uncertainties.join(" • ")}</span>
              </div>
            </div>
          )}

          {rec.upcoming_deadlines.length > 0 && (
            <div className="flex items-start gap-2 text-xs text-zinc-800">
              <Calendar className="h-4 w-4 text-zinc-700 shrink-0 mt-0.5" />
              <div className="flex flex-wrap gap-2">
                <span className="font-semibold">Admissions Deadlines:</span>
                {rec.upcoming_deadlines.map((d, idx) => (
                  <span
                    key={idx}
                    className={`rounded-md border px-2 py-0.5 ${
                      d.passed
                        ? "bg-rose-50 text-rose-800 border-rose-200"
                        : "bg-white text-zinc-800 border-zinc-200"
                    }`}
                  >
                    {String(d.term || "Cycle")} ({String(d.deadline_type || "Regular")}):{" "}
                    <strong>{String(d.deadline_date || "Check portal")}</strong>
                    {d.passed ? " (Passed)" : ""}
                  </span>
                ))}
              </div>
            </div>
          )}

          {rec.sources && rec.sources.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-zinc-600">
              <span className="font-semibold text-zinc-700">Sources:</span>
              {rec.sources.map((s, idx) => (
                <span key={idx} className="inline-flex items-center gap-1 rounded bg-white border border-zinc-200 px-2 py-0.5">
                  {String(s.name || "Official Registry")}
                  {Boolean(s.url) && (
                    <a
                      href={String(s.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-700 hover:underline inline-flex items-center"
                    >
                      <ExternalLink className="h-2.5 w-2.5 ms-0.5" />
                    </a>
                  )}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Link
            href={`/counselor?institution_id=${rec.institution_id}&pathway=${rec.applicant_type}`}
            className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-800 hover:bg-indigo-100 transition-colors"
          >
            Ask AI Counselor
          </Link>
          <Link
            href={`/universities/${rec.institution_id}`}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-800 hover:bg-zinc-100 transition-colors"
          >
            University Profile
          </Link>
          <Link
            href={`/applications?institution_id=${rec.institution_id}&pathway=${rec.applicant_type}`}
            className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800 hover:bg-emerald-100 transition-colors"
          >
            Route &amp; Apply
          </Link>
          {rec.applicant_type === "transfer" ? (
            <Link
              href={`/transfer?institution=${rec.institution_id}`}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-800 hover:bg-zinc-100 transition-colors"
            >
              Transfer Credit Check
            </Link>
          ) : (
            <Link
              href={`/first-year?institution=${rec.institution_id}`}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-800 hover:bg-zinc-100 transition-colors"
            >
              First-Year Checklist
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
