"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Award, CheckCircle2, Coins, ExternalLink, FileCheck2, Globe2, Info, ShieldAlert } from "lucide-react";
import {
  CredentialEvaluationResponse,
  GradingSystemOption,
  evaluateInternationalCredential,
  fetchGradingSystems,
} from "@/lib/api-client";
import { useI18n } from "@/lib/i18n/context";

export default function CredentialsEvaluationPage() {
  const { t, direction, language } = useI18n();
  const [systems, setSystems] = useState<GradingSystemOption[]>([]);
  const [systemKey, setSystemKey] = useState("ht_20");
  const [rawGrade, setRawGrade] = useState("15.2");
  const [destCountry, setDestCountry] = useState("US");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CredentialEvaluationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedSystem = systems.find((s) => s.grading_system_key === systemKey);

  const runEvaluation = useCallback(
    async (overrideKey?: string, overrideGrade?: string) => {
      const k = overrideKey || systemKey;
      const g = overrideGrade !== undefined ? overrideGrade : rawGrade;
      const sys = systems.find((s) => s.grading_system_key === k);
      const srcCountry = sys?.source_country_code || (k.split("_")[0] || "HT").toUpperCase();
      setLoading(true);
      setError(null);
      try {
        const res = await evaluateInternationalCredential({
          source_country_code: srcCountry,
          grading_system_key: k,
          raw_grade: g,
          destination_country_code: destCountry,
          academic_level: sys?.academic_level || "secondary",
        });
        setResult(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to evaluate credential");
      } finally {
        setLoading(false);
      }
    },
    [systemKey, rawGrade, destCountry, systems]
  );

  useEffect(() => {
    fetchGradingSystems()
      .then((list) => {
        setSystems(list);
        const first = list.find((s) => s.grading_system_key === "ht_20") || list[0];
        if (first) {
          setSystemKey(first.grading_system_key);
          const sample = first.sample_values[1] || first.sample_values[0] || "14.2";
          setRawGrade(sample);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load grading scales"));
  }, []);

  useEffect(() => {
    if (systems.length > 0 && !result) {
      runEvaluation();
    }
  }, [systems, result, runEvaluation]);

  return (
    <div dir={direction} lang={language.tag} className="min-h-screen bg-[#fafafc] text-zinc-900 pb-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-8 space-y-6">
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-zinc-200 pb-6">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 border border-indigo-200 px-3 py-1 text-[11px] font-bold text-indigo-800">
              <Globe2 className="h-3.5 w-3.5" aria-hidden="true" />
              Dual-View Academic Credential Engine
            </div>
            <h1 className="mt-2 text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900">
              {t("cred.title", "International Credential & Grade Evaluation Intelligence")}
            </h1>
            <p className="mt-1 text-sm text-zinc-600 max-w-3xl">
              {t(
                "cred.subtitle",
                "Dual-view academic representation preserving your native grading scale alongside transparent approximate benchmarks and official evaluation/translation gatekeeping rules."
              )}
            </p>
          </div>
          <Link
            href="/financial"
            className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3.5 py-2 text-xs font-bold text-zinc-800 hover:bg-zinc-50 shrink-0"
          >
            <Coins className="h-3.5 w-3.5 text-emerald-700" aria-hidden="true" />
            {t("nav.financial", "Financial & Aid")}
          </Link>
        </header>

        {error && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-900">
            {error}
          </div>
        )}

        {/* Evaluation Controls */}
        <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
            <div className="sm:col-span-2">
              <label htmlFor="cred-system" className="block text-[11px] font-bold text-zinc-700 mb-1">
                Native Grading System &amp; Qualification Scale
              </label>
              <select
                id="cred-system"
                value={systemKey}
                onChange={(e) => {
                  const nextKey = e.target.value;
                  setSystemKey(nextKey);
                  const nextSys = systems.find((s) => s.grading_system_key === nextKey);
                  const sample = nextSys?.sample_values[1] || nextSys?.sample_values[0] || "";
                  if (sample) setRawGrade(sample);
                  runEvaluation(nextKey, sample || rawGrade);
                }}
                className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-xs"
              >
                {systems.map((s) => (
                  <option key={s.grading_system_key} value={s.grading_system_key}>
                    [{s.source_country_code}] {s.scale_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="cred-grade" className="block text-[11px] font-bold text-zinc-700 mb-1">
                Native Grade / Score
              </label>
              <input
                id="cred-grade"
                dir="ltr"
                type="text"
                value={rawGrade}
                onChange={(e) => setRawGrade(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs font-mono"
              />
            </div>
            <div>
              <label htmlFor="cred-dest" className="block text-[11px] font-bold text-zinc-700 mb-1">
                Destination Country
              </label>
              <div className="flex items-center gap-2">
                <select
                  id="cred-dest"
                  value={destCountry}
                  onChange={(e) => setDestCountry(e.target.value)}
                  className="flex-1 rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-xs"
                >
                  <option value="US">United States (US)</option>
                  <option value="CA">Canada (CA)</option>
                  <option value="GB">United Kingdom (GB)</option>
                  <option value="FR">France (FR)</option>
                  <option value="DE">Germany (DE)</option>
                </select>
                <button
                  type="button"
                  onClick={() => runEvaluation()}
                  disabled={loading}
                  className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-700 shrink-0 disabled:opacity-60"
                >
                  {loading ? "Evaluating..." : "Evaluate"}
                </button>
              </div>
            </div>
          </div>

          {selectedSystem && selectedSystem.sample_values.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-600">
              <span>Quick samples:</span>
              {selectedSystem.sample_values.map((sv) => (
                <button
                  key={sv}
                  type="button"
                  onClick={() => {
                    setRawGrade(sv);
                    runEvaluation(systemKey, sv);
                  }}
                  className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-0.5 font-mono text-[11px] hover:bg-zinc-100"
                >
                  {sv}
                </button>
              ))}
            </div>
          )}
        </section>

        {result && (
          <>
            {/* Dual-View Side-by-Side Comparison */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-2 shadow-xs">
                <div className="text-[11px] font-bold uppercase text-zinc-500 flex items-center gap-1.5">
                  <Award className="h-3.5 w-3.5 text-zinc-700" aria-hidden="true" />
                  1. Original Native Record (Never Flattened)
                </div>
                <div className="text-xl font-extrabold text-zinc-900">
                  <span dir="ltr">{result.conversion.native_record.raw_input}</span> —{" "}
                  {result.conversion.native_record.classification}
                </div>
                <div className="text-xs text-zinc-600">
                  Scale: <strong>{result.conversion.native_record.scale_name}</strong> (
                  {result.conversion.native_record.country_code})
                </div>
                <div className="pt-1 flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                      result.conversion.native_record.is_passing
                        ? "bg-emerald-100 text-emerald-800"
                        : result.conversion.native_record.is_passing === false
                          ? "bg-red-100 text-red-800"
                          : "bg-zinc-100 text-zinc-700"
                    }`}
                  >
                    {result.conversion.native_record.is_passing
                      ? "Meets Passing Standard"
                      : result.conversion.native_record.is_passing === false
                        ? "Below Passing Threshold"
                        : "Unmatched Input"}
                  </span>
                  {result.conversion.native_record.is_inverted_scale && (
                    <span className="rounded-full bg-amber-50 border border-amber-200 px-2.5 py-0.5 text-[10px] font-bold text-amber-800">
                      Inverted Scale (Lower Numeric = Higher Merit)
                    </span>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-indigo-200 bg-indigo-50/40 p-5 space-y-2 shadow-xs">
                <div className="text-[11px] font-bold uppercase text-indigo-800 flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5" aria-hidden="true" />
                  2. Informational Approximate Benchmark
                </div>
                <div dir="ltr" className="text-xl font-extrabold text-indigo-950">
                  {result.conversion.informational_equivalency.us_4_0_point !== null &&
                  result.conversion.informational_equivalency.us_4_0_point !== undefined
                    ? `${result.conversion.informational_equivalency.us_4_0_point.toFixed(2)} / 4.0 US Equiv (${result.conversion.informational_equivalency.us_letter_equivalent})`
                    : "Unavailable"}
                </div>
                <div className="text-xs text-indigo-900 space-y-1">
                  {result.conversion.informational_equivalency.us_4_0_low !== null && (
                    <div>
                      US Band Range:{" "}
                      <strong dir="ltr">
                        {result.conversion.informational_equivalency.us_4_0_low?.toFixed(2)} –{" "}
                        {result.conversion.informational_equivalency.us_4_0_high?.toFixed(2)}
                      </strong>
                      {result.conversion.informational_equivalency.german_bavarian_equivalent !== null &&
                        result.conversion.informational_equivalency.german_bavarian_equivalent !== undefined && (
                          <span>
                            {" "}
                            • German Bavarian Formula:{" "}
                            <strong dir="ltr">
                              {result.conversion.informational_equivalency.german_bavarian_equivalent.toFixed(2)}
                            </strong>
                          </span>
                        )}
                    </div>
                  )}
                  <div>
                    Methodology: <strong>{result.conversion.informational_equivalency.methodology}</strong> (
                    {result.conversion.informational_equivalency.methodology_citation})
                  </div>
                  {result.conversion.informational_equivalency.percentile_note && (
                    <div className="text-indigo-950/90">{result.conversion.informational_equivalency.percentile_note}</div>
                  )}
                </div>
              </div>
            </div>

            {/* Destination Gatekeeping Rules */}
            <section className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-4">
              <h2 className="text-sm font-extrabold text-zinc-900 flex items-center gap-1.5">
                <FileCheck2 className="h-4 w-4 text-indigo-600" aria-hidden="true" />
                Destination Recognition &amp; Document Gatekeeping ({result.conversion.native_record.country_code} → {destCountry})
              </h2>
              {result.recognition_rules.length === 0 ? (
                <div className="rounded-xl border border-dashed border-zinc-300 p-4 text-xs text-zinc-600">
                  No direct bilateral rule record cached for {result.conversion.native_record.country_code} → {destCountry}; see official country qualifications below or verify with the destination institution.
                </div>
              ) : (
                <div className="space-y-3">
                  {result.recognition_rules.map((r) => (
                    <div key={r.id} className="rounded-xl border border-zinc-200 p-4 space-y-2 text-xs">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="font-bold text-sm text-zinc-900">{r.source_credential_name}</div>
                        <a
                          href={r.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 font-semibold text-indigo-700 hover:underline"
                        >
                          {r.source_name} <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[10px] font-bold text-emerald-800">
                          <CheckCircle2 className="h-3 w-3" />
                          {r.is_directly_recognized ? "Directly Recognized Secondary/Degree" : "Requires Bridge / Pre-Assessment"}
                        </span>
                        <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-[10px] font-bold text-zinc-700">
                          {r.requires_external_evaluation
                            ? `External Eval: ${r.accepted_evaluation_agencies.join(", ")}`
                            : "In-House University Evaluation"}
                        </span>
                        <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-[10px] font-bold text-zinc-700">
                          {r.requires_official_translation ? "Official Translation Required" : "No Translation Needed"}
                        </span>
                      </div>
                      <p className="text-zinc-700 leading-relaxed">{r.pathway_notes}</p>
                      {r.translation_requirements && (
                        <div className="text-zinc-600">
                          <strong>Translation:</strong> {r.translation_requirements}
                        </div>
                      )}
                      {r.english_waiver_policy && (
                        <div className="text-zinc-600">
                          <strong>Language Policy:</strong> {r.english_waiver_policy}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Non-Official Evaluation Boundary Disclaimer */}
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-950 flex items-start gap-2">
              <ShieldAlert className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" aria-hidden="true" />
              <span>{result.advisory_disclaimer}</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
