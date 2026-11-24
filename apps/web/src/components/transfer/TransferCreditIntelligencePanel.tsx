"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  Award,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  FileText,
  FlaskConical,
  Layers,
  Scale,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
} from "lucide-react";
import {
  attachSyllabusToCourse,
  DegreeApplicabilitySummary,
  evaluateCourseEquivalency,
  EvaluatedCourseResult,
  fetchTransferProfileSummary,
  Institution,
  searchInstitutions,
  uploadDocument,
} from "@/lib/api-client";

interface Props {
  selectedTargetId: string;
  intendedMajor: string;
  targetOptions: Institution[];
}

const TIER_STYLES: Record<string, string> = {
  "1": "bg-emerald-50 text-emerald-800 border-emerald-200",
  "2": "bg-amber-50 text-amber-800 border-amber-200",
  "3": "bg-indigo-50 text-indigo-800 border-indigo-200",
  unverified: "bg-slate-100 text-slate-700 border-slate-200",
};

const BUCKET_LABELS: Record<string, { label: string; style: string }> = {
  major_and_ge: { label: "Major + GE", style: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  major: { label: "Major Req", style: "bg-sky-50 text-sky-700 border-sky-200" },
  ge: { label: "General Ed", style: "bg-teal-50 text-teal-700 border-teal-200" },
  elective_only: { label: "Elective Units Only", style: "bg-amber-50 text-amber-800 border-amber-200" },
  non_applicable: { label: "Non-Applicable / Duplicate", style: "bg-rose-50 text-rose-700 border-rose-200" },
  unverified: { label: "Unverified", style: "bg-slate-100 text-slate-600 border-slate-200" },
};

export function TransferCreditIntelligencePanel({
  selectedTargetId,
  intendedMajor,
  targetOptions,
}: Props) {
  const [summary, setSummary] = useState<DegreeApplicabilitySummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploadingCourseId, setUploadingCourseId] = useState<string | null>(null);

  // Ad-hoc single course tester
  const [sendingInstId, setSendingInstId] = useState<string>("");
  const [sendingOptions, setSendingOptions] = useState<Array<{ id: string; name: string }>>([]);
  const [testCode, setTestCode] = useState("ECON 2");
  const [testName, setTestName] = useState("Principles of Microeconomics");
  const [testCredits, setTestCredits] = useState("4.0");
  const [testCreditSys, setTestCreditSys] = useState("us_quarter");
  const [testDesc, setTestDesc] = useState("");
  const [testResult, setTestResult] = useState<EvaluatedCourseResult | null>(null);
  const [testing, setTesting] = useState(false);

  const loadSummary = async () => {
    if (!selectedTargetId) return;
    setLoading(true);
    const data = await fetchTransferProfileSummary(selectedTargetId, intendedMajor);
    setSummary(data);
    setLoading(false);
  };

  useEffect(() => {
    loadSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTargetId, intendedMajor]);

  useEffect(() => {
    async function loadSending() {
      const [da, smc] = await Promise.all([
        searchInstitutions({ q: "De Anza College", limit: 1 }),
        searchInstitutions({ q: "Santa Monica College", limit: 1 }),
      ]);
      const opts: Array<{ id: string; name: string }> = [];
      if (da.items[0]) opts.push({ id: da.items[0].id, name: da.items[0].official_name });
      if (smc.items[0]) opts.push({ id: smc.items[0].id, name: smc.items[0].official_name });
      setSendingOptions(opts);
      if (opts[0]) setSendingInstId(opts[0].id);
    }
    loadSending();
  }, []);

  const handleSyllabusUpload = async (courseId: string, file: File) => {
    setUploadingCourseId(courseId);
    try {
      const uploaded = await uploadDocument(file, "syllabus");
      await attachSyllabusToCourse(courseId, uploaded.id);
      await loadSummary();
    } catch (err) {
      console.error("Failed to attach syllabus:", err);
    } finally {
      setUploadingCourseId(null);
    }
  };

  const handleTestCourse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTargetId || !testCode.trim()) return;
    setTesting(true);
    const res = await evaluateCourseEquivalency({
      source_institution_id: sendingInstId || undefined,
      source_course_code: testCode.trim(),
      source_course_name: testName.trim() || testCode.trim(),
      source_description: testDesc.trim() || undefined,
      source_credits: parseFloat(testCredits) || undefined,
      source_credit_system: testCreditSys,
      target_institution_id: selectedTargetId,
      intended_major: intendedMajor,
    });
    setTestResult(res);
    setTesting(false);
  };

  const targetName =
    summary?.target_institution_name ||
    targetOptions.find((t) => t.id === selectedTargetId)?.official_name ||
    "Target University";

  return (
    <div className="mt-10 space-y-8">
      {/* Section 1: Student Transfer Audit & Degree Applicability */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-100 pb-4">
          <div>
            <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-sky-700">
              <Layers className="w-4 h-4" /> 3-Tier Transfer Credit & Degree Applicability Engine
            </div>
            <h2 className="text-xl font-extrabold text-zinc-900 mt-1">
              Coursework Audit for {targetName} ({intendedMajor || "General"})
            </h2>
            <p className="text-xs text-zinc-600 mt-0.5">
              Separates officially verified units (Tier 1), historical patterns (Tier 2), AI content matches (Tier 3), and unverified coursework — never equating total units with graduation applicability.
            </p>
          </div>
          <button
            type="button"
            onClick={loadSummary}
            disabled={loading}
            className="rounded-xl border border-zinc-200 bg-zinc-50 hover:bg-zinc-100 px-3.5 py-2 text-xs font-semibold text-zinc-800 shrink-0"
          >
            {loading ? "Evaluating..." : "Re-Run Credit Audit"}
          </button>
        </div>

        {/* Summary KPI Cards */}
        {summary && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200">
                <div className="text-[11px] font-semibold text-emerald-800">Officially Transferable (Tier 1)</div>
                <div className="text-2xl font-extrabold text-emerald-900 mt-1">
                  {summary.officially_transferable_credits} <span className="text-xs font-semibold">sem eq</span>
                </div>
                <div className="text-[11px] text-emerald-700">{summary.officially_verified_count} course(s)</div>
              </div>

              <div className="p-3.5 rounded-xl bg-indigo-50 border border-indigo-200">
                <div className="text-[11px] font-semibold text-indigo-800">Potentially Transferable (T2/T3)</div>
                <div className="text-2xl font-extrabold text-indigo-900 mt-1">
                  {summary.potentially_transferable_credits} <span className="text-xs font-semibold">sem eq</span>
                </div>
                <div className="text-[11px] text-indigo-700">
                  {summary.historically_observed_count} historical &bull; {summary.ai_predicted_count} AI-predicted
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-sky-50 border border-sky-200">
                <div className="text-[11px] font-semibold text-sky-800">Counts Toward Major / GE</div>
                <div className="text-2xl font-extrabold text-sky-900 mt-1">
                  {summary.major_applicable_credits} <span className="text-xs font-semibold">major</span> /{" "}
                  {summary.ge_applicable_credits} <span className="text-xs font-semibold">GE</span>
                </div>
                <div className="text-[11px] text-sky-700">
                  Elective-only: {summary.elective_only_credits} sem eq
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200">
                <div className="text-[11px] font-semibold text-amber-900">Unverified / Needs Syllabus</div>
                <div className="text-2xl font-extrabold text-amber-950 mt-1">
                  {summary.unverified_course_count} <span className="text-xs font-semibold">courses</span>
                </div>
                <div className="text-[11px] text-amber-800">
                  {summary.unverified_credits} sem eq &bull; {summary.missing_syllabus_count} missing syllabi
                </div>
              </div>
            </div>

            {/* Credit Systems & Progress Split */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-4 rounded-xl bg-zinc-50 border border-zinc-200 space-y-2">
                <div className="font-bold text-zinc-900 flex items-center gap-1.5">
                  <Award className="w-4 h-4 text-emerald-600" /> Major Prerequisite & GE Progress
                </div>
                <div>
                  <span className="font-semibold text-zinc-700">Major Satisfied ({summary.major_prerequisites_satisfied.length}): </span>
                  {summary.major_prerequisites_satisfied.length > 0 ? (
                    <span className="text-emerald-700">{summary.major_prerequisites_satisfied.join("; ")}</span>
                  ) : (
                    <span className="text-zinc-500 italic">None verified yet</span>
                  )}
                </div>
                <div>
                  <span className="font-semibold text-zinc-700">Remaining Major Prereqs: </span>
                  {summary.major_prerequisites_remaining.length > 0 ? (
                    <span className="text-rose-700 font-medium">{summary.major_prerequisites_remaining.join(", ")}</span>
                  ) : (
                    <span className="text-zinc-500 italic">None flagged / select a specific major</span>
                  )}
                </div>
                <div>
                  <span className="font-semibold text-zinc-700">GE Areas Matched: </span>
                  {summary.ge_areas_satisfied.length > 0 ? (
                    <span className="text-teal-700">{summary.ge_areas_satisfied.join(" • ")}</span>
                  ) : (
                    <span className="text-zinc-500 italic">None verified yet</span>
                  )}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-zinc-50 border border-zinc-200 space-y-2">
                <div className="font-bold text-zinc-900 flex items-center gap-1.5">
                  <Scale className="w-4 h-4 text-indigo-600" /> Credit Systems & Official Warnings
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(summary.total_original_credits_by_system).map(([sys, val]) => (
                    <span key={sys} className="px-2 py-0.5 rounded bg-white border border-zinc-200 font-semibold text-zinc-800">
                      Original {sys}: {val}
                    </span>
                  ))}
                  {Object.keys(summary.total_original_credits_by_system).length === 0 && (
                    <span className="text-zinc-500 italic">No completed post-secondary courses recorded on Universal Profile yet.</span>
                  )}
                </div>
                {summary.warnings.map((w, i) => (
                  <div key={i} className="text-amber-800 flex items-start gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Evaluated Course Rows */}
            {summary.evaluated_courses.length > 0 && (
              <div className="space-y-2.5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                  Evaluated Course-by-Course Breakdown ({summary.evaluated_courses.length})
                </h3>
                {summary.evaluated_courses.map((ev, idx) => {
                  const tierKey = ev.equivalency_tier ? String(ev.equivalency_tier) : "unverified";
                  const bucket = BUCKET_LABELS[ev.applicability_bucket] || BUCKET_LABELS.unverified;
                  return (
                    <div key={`${ev.source_course_code}-${idx}`} className="p-4 rounded-xl bg-zinc-50 border border-zinc-200 space-y-2 text-xs">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${TIER_STYLES[tierKey]}`}>
                            {ev.equivalency_tier ? `Tier ${ev.equivalency_tier}: ` : ""}{ev.tier_label}
                          </span>
                          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${bucket.style}`}>
                            {bucket.label}
                          </span>
                          <span className="font-bold text-zinc-900">
                            {ev.source_course_code} — {ev.source_course_name}
                          </span>
                          {ev.original_credits !== undefined && ev.original_credits !== null && (
                            <span className="text-[11px] text-zinc-600 font-mono">
                              ({ev.original_credits} {ev.original_credit_system} → {ev.credits_transferable} transferable sem eq)
                            </span>
                          )}
                        </div>
                        {ev.source_url && (
                          <a href={ev.source_url} target="_blank" rel="noreferrer" className="text-sky-700 font-semibold hover:underline inline-flex items-center gap-1 shrink-0">
                            Source <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>

                      {ev.target_course_name && (
                        <div className="text-zinc-800 font-medium">
                          Equivalent Target: <span className="font-bold">{ev.target_course_code || "Elective"}</span> — {ev.target_course_name}
                          {ev.confidence_score > 0 && <span className="ml-2 text-zinc-500">(Confidence: {Math.round(ev.confidence_score * 100)}%)</span>}
                        </div>
                      )}

                      <p className="text-zinc-600">{ev.supporting_evidence}</p>
                      <p className="text-[11px] text-zinc-500 italic">{ev.disclaimer}</p>

                      {ev.requires_syllabus && ev.student_course_id && (
                        <div className="pt-1">
                          <label className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-zinc-300 hover:bg-zinc-100 text-[11px] font-semibold text-zinc-800 cursor-pointer">
                            <Upload className="w-3.5 h-3.5 text-sky-600" />
                            {uploadingCourseId === ev.student_course_id ? "Uploading & Re-evaluating..." : "Upload Syllabus for Tier 3 Matching"}
                            <input
                              type="file"
                              accept=".txt,.pdf,.md,.doc,.docx"
                              className="hidden"
                              onChange={(e) => {
                                const f = e.target.files?.[0];
                                if (f && ev.student_course_id) handleSyllabusUpload(ev.student_course_id, f);
                              }}
                            />
                          </label>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {/* Section 2: Interactive 3-Tier Equivalency Lookup Explorer */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs space-y-4">
        <div>
          <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-indigo-700">
            <FlaskConical className="w-4 h-4" /> Course-Level Articulation Simulator
          </div>
          <h3 className="text-base font-extrabold text-zinc-900 mt-1">
            Look Up Official Agreements or Test International / Out-of-State Courses
          </h3>
          <p className="text-xs text-zinc-600">
            Check published ASSIST equivalencies (De Anza / Santa Monica College) or test course descriptions & learning outcomes across ECTS, UK CATS, Canadian FCE, and US credits.
          </p>
        </div>

        <form onSubmit={handleTestCourse} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 text-xs">
          <select
            aria-label="Sending institution"
            value={sendingInstId}
            onChange={(e) => setSendingInstId(e.target.value)}
            className="rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-zinc-800"
          >
            {sendingOptions.map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
            <option value="">International / Other Institution</option>
          </select>

          <input
            type="text"
            value={testCode}
            onChange={(e) => setTestCode(e.target.value)}
            placeholder="Course Code (e.g. ECON 2)"
            className="rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-zinc-800"
          />

          <input
            type="text"
            value={testName}
            onChange={(e) => setTestName(e.target.value)}
            placeholder="Course Title"
            className="rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-zinc-800 lg:col-span-2"
          />

          <div className="flex gap-2">
            <input
              type="number"
              step="0.5"
              value={testCredits}
              onChange={(e) => setTestCredits(e.target.value)}
              placeholder="Units"
              className="w-20 rounded-lg border border-zinc-300 bg-white px-2 py-2 text-zinc-800"
            />
            <select
              aria-label="Credit system"
              value={testCreditSys}
              onChange={(e) => setTestCreditSys(e.target.value)}
              className="flex-1 rounded-lg border border-zinc-300 bg-white px-2 py-2 text-zinc-800"
            >
              <option value="us_quarter">US Quarter</option>
              <option value="us_semester">US Semester</option>
              <option value="ects">ECTS (Europe)</option>
              <option value="ca_credit">Canadian FCE</option>
              <option value="uk_cat">UK CATS</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={testing || !selectedTargetId}
            className="rounded-lg bg-zinc-900 hover:bg-zinc-800 text-white font-semibold px-3 py-2 flex items-center justify-center gap-1.5"
          >
            <Search className="w-3.5 h-3.5" /> {testing ? "Checking..." : "Evaluate"}
          </button>

          <input
            type="text"
            value={testDesc}
            onChange={(e) => setTestDesc(e.target.value)}
            placeholder="Optional syllabus description or learning outcomes (for Tier 3 content matching when unmapped)..."
            className="sm:col-span-2 lg:col-span-6 rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-zinc-800"
          />
        </form>

        {testResult && (
          <div className="p-4 rounded-xl bg-zinc-50 border border-zinc-200 space-y-1.5 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${TIER_STYLES[testResult.equivalency_tier ? String(testResult.equivalency_tier) : "unverified"]}`}>
                {testResult.equivalency_tier ? `Tier ${testResult.equivalency_tier}: ` : ""}{testResult.tier_label}
              </span>
              <span className="font-bold text-zinc-900">
                {testResult.source_course_code} ({testResult.original_credits} {testResult.original_credit_system})
                {testResult.target_course_code ? ` → ${testResult.target_course_code}: ${testResult.target_course_name}` : ""}
              </span>
              {testResult.source_url && (
                <a href={testResult.source_url} target="_blank" rel="noreferrer" className="text-sky-700 font-semibold hover:underline inline-flex items-center gap-1">
                  Verified Source <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
            <p className="text-zinc-700">{testResult.supporting_evidence}</p>
            <p className="text-[11px] text-zinc-500 italic">{testResult.disclaimer}</p>
          </div>
        )}
      </div>
    </div>
  );
}
