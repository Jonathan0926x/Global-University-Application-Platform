"use client";

import React from "react";
import Link from "next/link";
import { X, Scale, ExternalLink, AlertTriangle, CheckCircle2, HelpCircle } from "lucide-react";
import type { UniversityMatchRecommendation } from "@/lib/api-client";

export function ComparisonPanel({
  items,
  onRemove,
  onClear,
}: {
  items: UniversityMatchRecommendation[];
  onRemove: (institutionId: string) => void;
  onClear: () => void;
}) {
  if (items.length === 0) return null;

  return (
    <section
      aria-label="Side-by-Side University Comparison"
      className="rounded-2xl border border-indigo-200 bg-white shadow-sm overflow-hidden"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 bg-indigo-50/70 px-5 py-3.5">
        <div className="flex items-center gap-2">
          <Scale className="h-5 w-5 text-indigo-700" />
          <h2 className="text-base font-semibold text-zinc-900">
            Side-by-Side Comparison ({items.length} of 4)
          </h2>
        </div>
        <button
          type="button"
          onClick={onClear}
          className="rounded-lg border border-zinc-300 bg-white px-3 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100"
        >
          Clear Selection
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-start border-collapse text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50">
              <th className="p-3.5 text-xs font-semibold uppercase tracking-wide text-zinc-600 w-48 text-start">
                Dimension / Criterion
              </th>
              {items.map((item) => (
                <th
                  key={item.institution_id}
                  className="p-3.5 text-start align-top border-s border-zinc-200"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <Link
                        href={`/universities/${item.institution_id}`}
                        className="font-semibold text-zinc-900 hover:text-indigo-700 inline-flex items-center gap-1"
                      >
                        {item.institution.official_name}
                        <ExternalLink className="h-3.5 w-3.5 text-zinc-500" />
                      </Link>
                      <p className="text-xs font-normal text-zinc-600 mt-0.5">
                        {[
                          item.institution.city,
                          item.institution.state_province,
                          item.institution.country_code,
                        ]
                          .filter(Boolean)
                          .join(", ")}{" "}
                        • {item.institution.control_type || item.institution.institution_type}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onRemove(item.institution_id)}
                      aria-label={`Remove ${item.institution.official_name} from comparison`}
                      className="rounded-md p-1 text-zinc-500 hover:bg-zinc-200/70 hover:text-zinc-900"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-zinc-200 text-xs">
            <tr>
              <td className="p-3.5 font-semibold text-zinc-800 bg-zinc-50/50">
                Composite Alignment & Category
              </td>
              {items.map((item) => (
                <td key={item.institution_id} className="p-3.5 border-s border-zinc-200">
                  <div className="flex items-center gap-2">
                    <span className="text-base font-bold text-zinc-900">
                      {item.composite_score.toFixed(1)} / 100
                    </span>
                    <span className="rounded-full border border-zinc-300 bg-zinc-100 px-2 py-0.5 font-semibold uppercase text-[10px] text-zinc-800">
                      {item.match_category.replace("_", " ")}
                    </span>
                  </div>
                  <p className="mt-1 text-zinc-600">
                    Data confidence: {Math.round(item.data_confidence_score * 100)}%
                  </p>
                </td>
              ))}
            </tr>

            {["academic", "financial", "readiness", "transfer"].map((dimKey) => (
              <tr key={dimKey}>
                <td className="p-3.5 font-semibold text-zinc-800 bg-zinc-50/50 capitalize">
                  {dimKey === "academic"
                    ? "Academic Fit"
                    : dimKey === "financial"
                    ? "Financial Compatibility"
                    : dimKey === "readiness"
                    ? "Admissions Readiness"
                    : "Transfer & Credit Compatibility"}
                </td>
                {items.map((item) => {
                  const dim = item.dimensions.find((d) => d.key === dimKey);
                  if (!dim) {
                    return (
                      <td key={item.institution_id} className="p-3.5 border-s border-zinc-200 text-zinc-500">
                        —
                      </td>
                    );
                  }
                  const isNa = dim.status === "not_applicable";
                  return (
                    <td key={item.institution_id} className="p-3.5 border-s border-zinc-200 align-top">
                      <div className="font-semibold text-zinc-900">
                        {isNa ? "Not Applicable" : `${dim.score.toFixed(1)} / 100`}
                        <span className="ms-1.5 font-normal text-zinc-500">
                          ({(dim.weight_applied * 100).toFixed(0)}% wt)
                        </span>
                      </div>
                      <p className="mt-1 text-zinc-600 leading-relaxed">{dim.summary}</p>
                    </td>
                  );
                })}
              </tr>
            ))}

            <tr>
              <td className="p-3.5 font-semibold text-zinc-800 bg-zinc-50/50">
                Estimated Cost Basis
              </td>
              {items.map((item) => (
                <td key={item.institution_id} className="p-3.5 border-s border-zinc-200 align-top">
                  <div className="font-semibold text-zinc-900">
                    {item.estimated_net_cost !== null && item.estimated_net_cost !== undefined
                      ? `$${Math.round(item.estimated_net_cost).toLocaleString()} / yr`
                      : "Unverified"}
                  </div>
                  <p className="text-[11px] text-zinc-600 mt-0.5">
                    {item.cost_basis || (item.cost_is_estimated ? "Estimated" : "Official")}
                  </p>
                </td>
              ))}
            </tr>

            <tr>
              <td className="p-3.5 font-semibold text-zinc-800 bg-zinc-50/50">
                Key Strengths vs. Gaps
              </td>
              {items.map((item) => (
                <td key={item.institution_id} className="p-3.5 border-s border-zinc-200 align-top space-y-2">
                  <div className="flex items-center gap-1.5 text-emerald-800 font-medium">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    <span>{item.positive_factors.length} positive signals</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-amber-800 font-medium">
                    <HelpCircle className="h-3.5 w-3.5 shrink-0" />
                    <span>{item.missing_information.length} missing inputs</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-rose-800 font-medium">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    <span>
                      {item.unsatisfied_requirements.length + item.financial_concerns.length} concerns / requirements
                    </span>
                  </div>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
