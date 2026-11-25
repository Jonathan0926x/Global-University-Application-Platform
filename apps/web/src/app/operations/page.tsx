"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  FileText,
  Globe2,
  History,
  Lock,
  RefreshCw,
  Search,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import {
  EvidenceQueueItem,
  EvidenceVaultPreview,
  RejectionReasonOption,
  RoutingQualitySummary,
  RoutingQueueItem,
  fetchEvidenceQueue,
  fetchRoutingQualitySummary,
  fetchRoutingQueue,
  fetchVerificationTaxonomies,
  inspectEvidenceDocument,
  reviewApplicationRoute,
  reviewEvidenceItem,
  runBatchRoutingVerify,
} from "@/lib/api-client";
import { useI18n } from "@/lib/i18n/context";

function formatShortDate(iso?: string | null): string {
  if (!iso) return "N/A";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().slice(0, 10);
}

export default function OperationsConsolePage() {
  const { direction } = useI18n();

  // Explicit RBAC check: default uses standard session (student -> 403).
  // In local dev mode, reviewers can select `data_verifier` or `admin` credentials in-memory to exercise reviewer queues.
  const [devRole, setDevRole] = useState<"student" | "verifier" | "admin">("student");
  const authHeaders: Record<string, string> | undefined =
    devRole === "verifier"
      ? { Authorization: "Bearer mock_verifier_ops@uniglobe.edu" }
      : devRole === "admin"
        ? { Authorization: "Bearer mock_admin_ops@uniglobe.edu" }
        : undefined;

  const [activeTab, setActiveTab] = useState<"evidence" | "routing">("evidence");
  const [rbacStatus, setRbacStatus] = useState<"ok" | "forbidden" | "error">("ok");
  const [rbacMessage, setRbacMessage] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [banner, setBanner] = useState<string | null>(null);

  // Taxonomies
  const [evidenceReasons, setEvidenceReasons] = useState<RejectionReasonOption[]>([]);
  const [routeReasons, setRouteReasons] = useState<RejectionReasonOption[]>([]);

  // Evidence queue state
  const [evidenceStatusFilter, setEvidenceStatusFilter] = useState<"pending" | "accepted" | "rejected" | "all">("pending");
  const [evidenceQueue, setEvidenceQueue] = useState<EvidenceQueueItem[]>([]);
  const [docPreviewByEv, setDocPreviewByEv] = useState<Record<string, EvidenceVaultPreview>>({});
  const [evReasonById, setEvReasonById] = useState<Record<string, string>>({});
  const [evNotesById, setEvNotesById] = useState<Record<string, string>>({});

  // Routing queue state
  const [summary, setSummary] = useState<RoutingQualitySummary | null>(null);
  const [routeStatusFilter, setRouteStatusFilter] = useState<"needs_verification" | "verified" | "unverified" | "all">(
    "needs_verification"
  );
  const [routeSearch, setRouteSearch] = useState("");
  const [routingQueue, setRoutingQueue] = useState<RoutingQueueItem[]>([]);
  const [routeUrlById, setRouteUrlById] = useState<Record<string, string>>({});
  const [routeReasonById, setRouteReasonById] = useState<Record<string, string>>({});
  const [routeNotesById, setRouteNotesById] = useState<Record<string, string>>({});

  const loadAll = useCallback(async () => {
    setLoading(true);
    setRbacStatus("ok");
    setRbacMessage("");
    const hdr =
      devRole === "verifier"
        ? { Authorization: "Bearer mock_verifier_ops@uniglobe.edu" }
        : devRole === "admin"
          ? { Authorization: "Bearer mock_admin_ops@uniglobe.edu" }
          : undefined;
    try {
      const [tax, sum, evQ, rtQ] = await Promise.all([
        fetchVerificationTaxonomies(hdr),
        fetchRoutingQualitySummary(hdr),
        fetchEvidenceQueue(evidenceStatusFilter, hdr),
        fetchRoutingQueue({ verification_status: routeStatusFilter, q: routeSearch || undefined, limit: 100 }, hdr),
      ]);
      setEvidenceReasons(tax.evidence_rejection_reasons);
      setRouteReasons(tax.route_rejection_reasons);
      setSummary(sum);
      setEvidenceQueue(evQ);
      setRoutingQueue(rtQ);
    } catch (e: unknown) {
      const status = (e as { status?: number })?.status;
      if (status === 403 || status === 401) {
        setRbacStatus("forbidden");
        setRbacMessage(e instanceof Error ? e.message : "Administrative or data verifier privileges required.");
      } else {
        setRbacStatus("error");
        setRbacMessage(e instanceof Error ? e.message : "Failed to load verification operations console.");
      }
    } finally {
      setLoading(false);
    }
  }, [devRole, evidenceStatusFilter, routeStatusFilter, routeSearch]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleInspectDoc = async (evidenceId: string) => {
    try {
      const preview = await inspectEvidenceDocument(evidenceId, authHeaders);
      setDocPreviewByEv((prev) => ({ ...prev, [evidenceId]: preview }));
    } catch (e) {
      setBanner(e instanceof Error ? e.message : "Could not load Document Vault preview");
    }
  };

  const handleEvidenceDecision = async (evidenceId: string, decision: "accepted" | "rejected") => {
    setBanner(null);
    const reasonCode = evReasonById[evidenceId] || "missing_confirmation_id";
    const notes = (evNotesById[evidenceId] || "").trim();
    if (decision === "rejected" && !notes) {
      setBanner("Reviewer notes are mandatory when rejecting confirmation evidence.");
      return;
    }
    try {
      await reviewEvidenceItem(
        evidenceId,
        {
          decision,
          rejection_reason_code: decision === "rejected" ? reasonCode : undefined,
          reviewer_notes:
            notes || "Verified confirmation number and SHA-256 Document Vault artifact.",
        },
        authHeaders
      );
      setBanner(`Confirmation evidence ${decision}. Immutable review audit trail updated.`);
      await loadAll();
    } catch (e) {
      setBanner(e instanceof Error ? e.message : "Failed to submit evidence decision");
    }
  };

  const handleRouteDecision = async (
    routeId: string,
    decision: "verified" | "unverified" | "needs_verification"
  ) => {
    setBanner(null);
    const reasonCode = routeReasonById[routeId] || "broken_or_404";
    const notes = (routeNotesById[routeId] || "").trim();
    const correctedUrl = (routeUrlById[routeId] || "").trim();

    if (decision === "unverified" && !notes) {
      setBanner("Verifier notes are mandatory when rejecting a routing destination.");
      return;
    }

    try {
      await reviewApplicationRoute(
        routeId,
        {
          decision,
          rejection_reason_code: decision === "unverified" ? reasonCode : undefined,
          notes: notes || "Manually inspected HTTPS portal destination and institutional affiliation.",
          corrected_url: correctedUrl || undefined,
        },
        authHeaders
      );
      setBanner(`Route updated to '${decision}' and logged to application_route_audits.`);
      await loadAll();
    } catch (e) {
      setBanner(e instanceof Error ? e.message : "Failed to review route");
    }
  };

  const handleRunBatchVerify = async () => {
    setBanner(null);
    try {
      const res = await runBatchRoutingVerify(authHeaders);
      setSummary(res.summary);
      setBanner(
        `Batch routing audit checked ${res.checked} routes: promoted ${res.promoted_to_verified}, kept ${res.kept_needs_verification} for manual verifier review.`
      );
      await loadAll();
    } catch (e) {
      setBanner(e instanceof Error ? e.message : "Batch verification failed");
    }
  };

  return (
    <div dir={direction} className="min-h-screen bg-[#fafafc] text-zinc-900 pb-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-8 space-y-6">
        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-zinc-200 pb-6">
          <div>
            <Link
              href="/applications"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-700 hover:underline"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Applications &amp; Routing
            </Link>
            <h1 className="mt-2 text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900">
              Verification &amp; Trust Operations Console
            </h1>
            <p className="mt-1 text-sm text-zinc-600 max-w-3xl">
              RBAC-protected review workflows for official university application URLs and student Document Vault
              confirmation evidence, with structured rejection taxonomies and immutable audit histories.
            </p>
          </div>

          {/* Explicit RBAC & Dev Role Switcher */}
          <div className="rounded-xl border border-zinc-200 bg-white p-3 text-xs shadow-xs space-y-1.5 shrink-0">
            <div className="font-bold text-zinc-700 flex items-center gap-1.5">
              <Lock className="h-3.5 w-3.5 text-zinc-500" />
              Reviewer Session (Dev RBAC Check)
            </div>
            <div className="flex items-center gap-1.5">
              {(
                [
                  { id: "student", label: "Student (403 Check)" },
                  { id: "verifier", label: "Data Verifier" },
                  { id: "admin", label: "Admin" },
                ] as const
              ).map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setDevRole(r.id)}
                  className={`rounded-lg px-2.5 py-1 text-[11px] font-bold border transition-colors ${
                    devRole === r.id
                      ? "bg-zinc-900 text-white border-zinc-900"
                      : "bg-zinc-50 text-zinc-700 border-zinc-200 hover:bg-zinc-100"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {banner && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-950 flex items-center justify-between">
            <span>{banner}</span>
            <button type="button" onClick={() => setBanner(null)} className="font-bold underline">
              Dismiss
            </button>
          </div>
        )}

        {/* RBAC 403 Gate */}
        {rbacStatus === "forbidden" ? (
          <div className="rounded-2xl border border-red-200 bg-red-50/70 p-8 text-center max-w-2xl mx-auto space-y-3">
            <ShieldAlert className="h-10 w-10 text-red-600 mx-auto" />
            <h2 className="text-lg font-extrabold text-red-950">Access Restricted (HTTP 403 Forbidden)</h2>
            <p className="text-xs text-red-900 leading-relaxed">
              {rbacMessage} Student accounts cannot view other students&apos; evidence queues, inspect confirmation
              documents, self-approve <code className="font-mono">submission_confirmed</code>, or mutate official routing
              verification state. Switch to <strong>Data Verifier</strong> or <strong>Admin</strong> in the Reviewer
              Session selector above to exercise privileged verification operations in local dev mode.
            </p>
          </div>
        ) : (
          <>
            {/* Routing Quality Summary Strip */}
            {summary && (
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
                <div className="rounded-xl border border-zinc-200 bg-white p-4">
                  <div className="text-[11px] font-bold uppercase text-zinc-500">Total Directory Routes</div>
                  <div className="mt-1 text-2xl font-extrabold text-zinc-900">{summary.total_routes}</div>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
                  <div className="text-[11px] font-bold uppercase text-emerald-800">Verified Official</div>
                  <div className="mt-1 text-2xl font-extrabold text-emerald-900">{summary.verified}</div>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
                  <div className="text-[11px] font-bold uppercase text-amber-800">Needs Manual Review</div>
                  <div className="mt-1 text-2xl font-extrabold text-amber-900">{summary.needs_verification}</div>
                </div>
                <div className="rounded-xl border border-zinc-200 bg-white p-4">
                  <div className="text-[11px] font-bold uppercase text-zinc-500">Domain + System Verified</div>
                  <div className="mt-1 text-xs font-semibold text-zinc-700 space-y-0.5">
                    <div>Domain Match: {summary.by_method.ipeds_domain_match || 0}</div>
                    <div>State/Central System: {summary.by_method.ipeds_state_system || 0}</div>
                  </div>
                </div>
                <div className="rounded-xl border border-zinc-200 bg-white p-4">
                  <div className="text-[11px] font-bold uppercase text-zinc-500">Confirmation Queue</div>
                  <div className="mt-1 text-2xl font-extrabold text-indigo-700">{evidenceQueue.length}</div>
                  <div className="text-[11px] text-zinc-500">Filtered ({evidenceStatusFilter})</div>
                </div>
              </div>
            )}

            {/* Operations Tabs */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="inline-flex rounded-xl border border-zinc-200 bg-white p-1">
                <button
                  type="button"
                  onClick={() => setActiveTab("evidence")}
                  className={`rounded-lg px-4 py-2 text-xs font-bold ${
                    activeTab === "evidence" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:text-zinc-900"
                  }`}
                >
                  Confirmation Evidence Queue ({evidenceQueue.length})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("routing")}
                  className={`rounded-lg px-4 py-2 text-xs font-bold ${
                    activeTab === "routing" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:text-zinc-900"
                  }`}
                >
                  Routing Data Quality Queue ({routingQueue.length})
                </button>
              </div>

              {activeTab === "routing" && (
                <button
                  type="button"
                  onClick={handleRunBatchVerify}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-indigo-700"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Run Deterministic Batch Audit
                </button>
              )}
            </div>

            {/* TAB 1: CONFIRMATION EVIDENCE QUEUE */}
            {activeTab === "evidence" && (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  {(["pending", "accepted", "rejected", "all"] as const).map((st) => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => setEvidenceStatusFilter(st)}
                      className={`rounded-full px-3 py-1 text-xs font-semibold border capitalize ${
                        evidenceStatusFilter === st
                          ? "bg-zinc-900 text-white border-zinc-900"
                          : "bg-white text-zinc-700 border-zinc-200"
                      }`}
                    >
                      {st}
                    </button>
                  ))}
                </div>

                {loading ? (
                  <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center text-xs text-zinc-500">
                    Loading confirmation evidence queue...
                  </div>
                ) : evidenceQueue.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center text-xs text-zinc-600">
                    No confirmation evidence records in &ldquo;{evidenceStatusFilter}&rdquo; state.
                  </div>
                ) : (
                  evidenceQueue.map((ev) => {
                    const docPreview = docPreviewByEv[ev.id];
                    return (
                      <div key={ev.id} className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-4 shadow-xs">
                        <div className="flex flex-col md:flex-row md:items-start justify-between gap-3 border-b border-zinc-100 pb-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="rounded-md bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[11px] font-bold uppercase text-indigo-800">
                                {ev.applicant_type.replace("_", "-")}
                              </span>
                              <span
                                className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase ${
                                  ev.review_status === "accepted"
                                    ? "bg-emerald-100 text-emerald-800"
                                    : ev.review_status === "rejected"
                                      ? "bg-red-100 text-red-800"
                                      : "bg-amber-100 text-amber-800"
                                }`}
                              >
                                {ev.review_status}
                              </span>
                              <span className="text-[11px] text-zinc-500">
                                App Status: <strong>{ev.application_status}</strong>
                              </span>
                            </div>
                            <h3 className="mt-1.5 text-base font-extrabold text-zinc-900">{ev.institution_name}</h3>
                            <p className="text-xs text-zinc-600">
                              Student: <strong>{ev.student_name || "Applicant"}</strong> (
                              <span dir="ltr">{ev.student_email || "N/A"}</span>) • Confirmation Ref:{" "}
                              <strong dir="ltr" className="font-mono">
                                {ev.external_confirmation_number || "None entered"}
                              </strong>
                            </p>
                          </div>

                          <button
                            type="button"
                            onClick={() => handleInspectDoc(ev.id)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs font-bold text-zinc-800 hover:bg-zinc-100 shrink-0"
                          >
                            <FileText className="h-3.5 w-3.5 text-indigo-600" />
                            Inspect Vault Artifact
                          </button>
                        </div>

                        <div className="rounded-lg bg-zinc-50 border border-zinc-200/80 px-3 py-2 text-xs text-zinc-700 flex flex-wrap items-center justify-between gap-2">
                          <span>
                            File: <strong>{ev.original_filename || "N/A"}</strong> ({ev.file_type || "file"})
                          </span>
                          <span dir="ltr" className="font-mono text-[11px] text-zinc-500">
                            SHA-256: {ev.document_sha256 || "Missing checksum"}
                          </span>
                        </div>

                        {docPreview && (
                          <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-3.5 text-xs space-y-1.5">
                            <div className="font-bold text-indigo-950">
                              Document Vault Extracted Content ({docPreview.original_filename})
                            </div>
                            <pre className="whitespace-pre-wrap rounded-lg bg-white border border-indigo-100 p-2.5 font-mono text-[11px] text-zinc-800 max-h-40 overflow-y-auto">
                              {docPreview.extracted_text || "Binary / image artifact verified by SHA-256 checksum."}
                            </pre>
                          </div>
                        )}

                        {ev.rejection_reason_label && (
                          <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-900">
                            <strong>Current Rejection Reason:</strong> {ev.rejection_reason_label} — {ev.reviewer_notes}
                          </div>
                        )}

                        {/* Reviewer Decision Controls */}
                        <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3.5 grid grid-cols-1 lg:grid-cols-4 gap-3 items-end">
                          <div>
                            <label className="block text-[11px] font-bold text-zinc-700 mb-1">
                              Rejection Reason Taxonomy (required if rejecting)
                            </label>
                            <select
                              aria-label="Rejection Reason Taxonomy"
                              value={evReasonById[ev.id] || evidenceReasons[0]?.code || "missing_confirmation_id"}
                              onChange={(e) => setEvReasonById((prev) => ({ ...prev, [ev.id]: e.target.value }))}
                              className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-xs"
                            >
                              {evidenceReasons.map((r) => (
                                <option key={r.code} value={r.code}>
                                  {r.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="lg:col-span-2">
                            <label className="block text-[11px] font-bold text-zinc-700 mb-1">
                              Reviewer Notes (audit trail)
                            </label>
                            <input
                              type="text"
                              value={evNotesById[ev.id] || ""}
                              onChange={(e) => setEvNotesById((prev) => ({ ...prev, [ev.id]: e.target.value }))}
                              placeholder="Explain verification outcome or what proof the student should re-upload..."
                              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs"
                            />
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => handleEvidenceDecision(ev.id, "accepted")}
                              className="flex-1 inline-flex items-center justify-center gap-1 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700"
                            >
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              Accept &amp; Confirm
                            </button>
                            <button
                              type="button"
                              onClick={() => handleEvidenceDecision(ev.id, "rejected")}
                              className="flex-1 inline-flex items-center justify-center gap-1 rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white hover:bg-red-700"
                            >
                              <XCircle className="h-3.5 w-3.5" />
                              Reject
                            </button>
                          </div>
                        </div>

                        {/* Immutable Audit Trail */}
                        {ev.audit_history && ev.audit_history.length > 0 && (
                          <div className="border-t border-zinc-100 pt-2.5 space-y-1">
                            <div className="text-[11px] font-bold uppercase text-zinc-500 flex items-center gap-1">
                              <History className="h-3 w-3" />
                              Immutable Review Audit History ({ev.audit_history.length})
                            </div>
                            {ev.audit_history.map((a) => (
                              <div key={a.id} className="text-[11px] text-zinc-700 flex items-center justify-between gap-2">
                                <span>
                                  <strong className="uppercase">{a.action}</strong> by {a.actor_role} (
                                  {a.actor_email || "system"})
                                  {a.rejection_reason_label ? ` [${a.rejection_reason_label}]` : ""} — {a.notes || ""}
                                </span>
                                <span dir="ltr" className="font-mono text-zinc-500 shrink-0">
                                  {formatShortDate(a.created_at)}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}

            {/* TAB 2: ROUTING DATA QUALITY QUEUE */}
            {activeTab === "routing" && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-3.5">
                  <div className="flex items-center gap-1.5">
                    {(["needs_verification", "verified", "unverified", "all"] as const).map((st) => (
                      <button
                        key={st}
                        type="button"
                        onClick={() => setRouteStatusFilter(st)}
                        className={`rounded-full px-3 py-1 text-xs font-semibold border capitalize ${
                          routeStatusFilter === st
                            ? "bg-zinc-900 text-white border-zinc-900"
                            : "bg-white text-zinc-700 border-zinc-200"
                        }`}
                      >
                        {st.replace(/_/g, " ")}
                      </button>
                    ))}
                  </div>

                  <div className="relative w-full sm:w-72">
                    <Search className="h-3.5 w-3.5 text-zinc-400 absolute start-3 top-2.5" />
                    <input
                      type="text"
                      value={routeSearch}
                      onChange={(e) => setRouteSearch(e.target.value)}
                      placeholder="Filter portal or university..."
                      className="w-full rounded-lg border border-zinc-300 bg-white ps-8 pe-3 py-1.5 text-xs"
                    />
                  </div>
                </div>

                {routingQueue.map((rt) => (
                  <div key={rt.id} className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-3 shadow-xs">
                    <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-0.5 text-[10px] font-bold uppercase text-zinc-700">
                            <Globe2 className="h-3 w-3" />
                            {rt.country_code} • {rt.platform_type.replace(/_/g, " ")}
                          </span>
                          <span
                            className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                              rt.verification_status === "verified"
                                ? "bg-emerald-100 text-emerald-800"
                                : rt.verification_status === "unverified"
                                  ? "bg-red-100 text-red-800"
                                  : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {rt.verification_status.replace(/_/g, " ")}
                          </span>
                          {rt.verification_method && (
                            <span className="text-[11px] font-mono text-zinc-500">
                              method: {rt.verification_method}
                            </span>
                          )}
                        </div>
                        <h3 className="mt-1.5 text-base font-extrabold text-zinc-900">
                          {rt.institution_name || rt.platform_name}
                        </h3>
                        <div dir="ltr" className="mt-1 font-mono text-xs text-indigo-700 break-all">
                          {rt.official_url}
                        </div>
                        {rt.institution_website && (
                          <div className="text-[11px] text-zinc-500 mt-0.5">
                            Official Site: <span dir="ltr">{rt.institution_website}</span>
                          </div>
                        )}
                      </div>

                      <a
                        href={rt.official_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 shrink-0"
                      >
                        Open Link <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>

                    {rt.trust_checks?.warnings && rt.trust_checks.warnings.length > 0 && (
                      <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-900 flex items-start gap-2">
                        <AlertTriangle className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
                        <span>{rt.trust_checks.warnings.join(" • ")}</span>
                      </div>
                    )}

                    <div className="grid grid-cols-1 lg:grid-cols-4 gap-2.5 items-end bg-zinc-50 rounded-xl p-3 border border-zinc-200/80">
                      <div>
                        <label className="block text-[11px] font-bold text-zinc-700 mb-1">
                          Corrected HTTPS URL (optional)
                        </label>
                        <input
                          type="url"
                          dir="ltr"
                          value={routeUrlById[rt.id] || ""}
                          onChange={(e) => setRouteUrlById((prev) => ({ ...prev, [rt.id]: e.target.value }))}
                          placeholder={rt.official_url}
                          className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
                        />
                      </div>

                      <div>
                        <label className="block text-[11px] font-bold text-zinc-700 mb-1">
                          Rejection Reason (if unverified)
                        </label>
                        <select
                          aria-label="Route Rejection Reason"
                          value={routeReasonById[rt.id] || routeReasons[0]?.code || "broken_or_404"}
                          onChange={(e) => setRouteReasonById((prev) => ({ ...prev, [rt.id]: e.target.value }))}
                          className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
                        >
                          {routeReasons.map((r) => (
                            <option key={r.code} value={r.code}>
                              {r.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-[11px] font-bold text-zinc-700 mb-1">Verifier Notes</label>
                        <input
                          type="text"
                          value={routeNotesById[rt.id] || ""}
                          onChange={(e) => setRouteNotesById((prev) => ({ ...prev, [rt.id]: e.target.value }))}
                          placeholder="Tenant confirmed on admissions site..."
                          className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs"
                        />
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleRouteDecision(rt.id, "verified")}
                          className="flex-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-700"
                        >
                          Verify URL
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRouteDecision(rt.id, "unverified")}
                          className="flex-1 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-red-700"
                        >
                          Reject
                        </button>
                      </div>
                    </div>

                    {rt.audits && rt.audits.length > 0 && (
                      <div className="border-t border-zinc-100 pt-2 space-y-1 text-[11px] text-zinc-600">
                        {rt.audits.slice(0, 3).map((a) => (
                          <div key={a.id} className="flex items-center justify-between gap-2">
                            <span>
                              <strong className="uppercase">{a.action}</strong> ({a.from_status} → {a.to_status}) by{" "}
                              {a.actor_role}: {a.notes || ""}
                            </span>
                            <span dir="ltr" className="font-mono shrink-0">
                              {formatShortDate(a.created_at)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
