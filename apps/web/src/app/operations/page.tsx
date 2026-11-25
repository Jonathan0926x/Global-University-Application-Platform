"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileText,
  Globe2,
  History,
  Lock,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  EvidenceQueueItem,
  EvidenceVaultPreview,
  RejectionReasonOption,
  RoutingQualitySummary,
  RoutingQueueItem,
  expireStaleRoutes,
  fetchEvidenceQueue,
  fetchRoutingQualitySummary,
  fetchRoutingQueue,
  fetchVerificationTaxonomies,
  inspectEvidenceDocument,
  reviewApplicationRoute,
  reviewEvidenceItem,
  runBatchRouteHealthChecks,
  runBatchRoutingVerify,
  runRouteHealthCheck,
  verifyRoutePathway,
} from "@/lib/api-client";
import { useI18n } from "@/lib/i18n/context";

function formatShortDate(iso?: string | null): string {
  if (!iso) return "N/A";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().slice(0, 10);
}

export default function OperationsConsolePage() {
  const { t, direction, language } = useI18n();

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
  const [routeStatusFilter, setRouteStatusFilter] = useState<
    "manual_review" | "needs_verification" | "verified" | "expired" | "unverified" | "all"
  >("manual_review");
  const [routeSearch, setRouteSearch] = useState("");
  const [routingQueue, setRoutingQueue] = useState<RoutingQueueItem[]>([]);
  const [routeUrlById, setRouteUrlById] = useState<Record<string, string>>({});
  const [routeReasonById, setRouteReasonById] = useState<Record<string, string>>({});
  const [routeNotesById, setRouteNotesById] = useState<Record<string, string>>({});
  const [routePathwayById, setRoutePathwayById] = useState<Record<string, string>>({});
  const [healthCheckingId, setHealthCheckingId] = useState<string | null>(null);
  const [batchHealthRunning, setBatchHealthRunning] = useState(false);

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
        fetchRoutingQueue({ verification_status: routeStatusFilter, q: routeSearch || undefined, limit: 500 }, hdr),
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

  const statusLabel = (raw: string): string => {
    switch (raw) {
      case "verified":
        return t("ops.rt_filter_verified", "Verified");
      case "needs_verification":
        return t("ops.rt_filter_needs_verif", "Needs Verification");
      case "unverified":
        return t("ops.rt_filter_unverified", "Unverified");
      case "pending":
        return t("ops.filter_pending", "Pending");
      case "accepted":
        return t("ops.filter_accepted", "Accepted");
      case "rejected":
        return t("ops.filter_rejected", "Rejected");
      default:
        return raw.replace(/_/g, " ");
    }
  };

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

  const handleSingleHealthCheck = async (routeId: string) => {
    setBanner(null);
    setHealthCheckingId(routeId);
    try {
      const updated = await runRouteHealthCheck(routeId, authHeaders);
      setBanner(
        `Link health check: ${updated.last_health_check_status || "checked"} (HTTP ${updated.last_health_check_http_code ?? "N/A"})` +
          (updated.final_redirect_url ? ` → ${updated.final_redirect_url}` : "")
      );
      await loadAll();
    } catch (e) {
      setBanner(e instanceof Error ? e.message : "Link health check failed");
    } finally {
      setHealthCheckingId(null);
    }
  };

  const handleBatchHealthCheck = async () => {
    setBanner(null);
    setBatchHealthRunning(true);
    try {
      const res = await runBatchRouteHealthChecks({ limit: 15, only_stale: true }, authHeaders);
      setSummary(res.summary);
      setBanner(
        `Health-checked ${res.checked} routes: ${res.by_status.healthy || 0} healthy, ${res.by_status.redirected || 0} redirected, ${res.by_status.unreachable || 0} unreachable.`
      );
      await loadAll();
    } catch (e) {
      setBanner(e instanceof Error ? e.message : "Batch link health check failed");
    } finally {
      setBatchHealthRunning(false);
    }
  };

  const handleExpireStaleRoutes = async () => {
    setBanner(null);
    try {
      const res = await expireStaleRoutes(authHeaders);
      setSummary(res.summary);
      setBanner(
        `Checked expired verifications: flagged ${res.flagged_for_reverification} expired route(s) for reverification.`
      );
      await loadAll();
    } catch (e) {
      setBanner(e instanceof Error ? e.message : "Failed to expire stale routes");
    }
  };

  const handleVerifyPathway = async (rt: RoutingQueueItem) => {
    setBanner(null);
    const chosenType = routePathwayById[rt.id] || rt.applicant_type;
    const notes = (routeNotesById[rt.id] || "").trim();
    try {
      await verifyRoutePathway(
        rt.id,
        {
          pathway_verified: true,
          applicant_type: chosenType,
          notes: notes || `Verified applicant pathway applicability (${chosenType}).`,
        },
        authHeaders
      );
      setBanner(`Pathway verified for ${rt.institution_name || rt.platform_name} (${chosenType}).`);
      await loadAll();
    } catch (e) {
      setBanner(e instanceof Error ? e.message : "Failed to verify route pathway");
    }
  };

  return (
    <div dir={direction} lang={language.tag} className="min-h-screen bg-[#fafafc] text-zinc-900 pb-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-8 space-y-6">
        {/* Header */}
        <header className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-zinc-200 pb-6">
          <div>
            <Link
              href="/applications"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 rounded"
            >
              <ArrowLeft className="h-3.5 w-3.5 rtl:rotate-180" aria-hidden="true" />
              {t("ops.back_to_apps", "Back to Applications & Routing")}
            </Link>
            <h1 className="mt-2 text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900">
              {t("ops.title", "Verification & Trust Operations Console")}
            </h1>
            <p className="mt-1 text-sm text-zinc-600 max-w-3xl">
              {t(
                "ops.subtitle",
                "RBAC-protected review workflows for official university application URLs and student Document Vault confirmation evidence, with structured rejection taxonomies and immutable audit histories."
              )}
            </p>
          </div>

          {/* Explicit RBAC & Dev Role Switcher */}
          <div
            role="group"
            aria-label={t("ops.rbac_title", "Reviewer Session (Dev RBAC Check)")}
            className="rounded-xl border border-zinc-200 bg-white p-3 text-xs shadow-xs space-y-1.5 shrink-0"
          >
            <div className="font-bold text-zinc-700 flex items-center gap-1.5">
              <Lock className="h-3.5 w-3.5 text-zinc-500" aria-hidden="true" />
              {t("ops.rbac_title", "Reviewer Session (Dev RBAC Check)")}
            </div>
            <div className="flex items-center gap-1.5">
              {(
                [
                  { id: "student", label: t("ops.role_student", "Student (403 Check)") },
                  { id: "verifier", label: t("ops.role_verifier", "Data Verifier") },
                  { id: "admin", label: t("ops.role_admin", "Admin") },
                ] as const
              ).map((r) => (
                <button
                  key={r.id}
                  type="button"
                  aria-pressed={devRole === r.id}
                  onClick={() => setDevRole(r.id)}
                  className={`rounded-lg px-2.5 py-1 text-[11px] font-bold border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 ${
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
        </header>

        {banner && (
          <div
            role="status"
            aria-live="polite"
            className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-950 flex items-center justify-between gap-3"
          >
            <span>{banner}</span>
            <button
              type="button"
              onClick={() => setBanner(null)}
              className="font-bold underline focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 rounded"
            >
              {t("ops.dismiss", "Dismiss")}
            </button>
          </div>
        )}

        {/* RBAC 403 Gate */}
        {rbacStatus === "forbidden" ? (
          <div
            role="alert"
            className="rounded-2xl border border-red-200 bg-red-50/70 p-8 text-center max-w-2xl mx-auto space-y-3"
          >
            <ShieldAlert className="h-10 w-10 text-red-600 mx-auto" aria-hidden="true" />
            <h2 className="text-lg font-extrabold text-red-950">
              {t("ops.forbidden_title", "Access Restricted (HTTP 403 Forbidden)")}
            </h2>
            <p className="text-xs text-red-900 leading-relaxed">
              {rbacMessage}{" "}
              {t(
                "ops.forbidden_body",
                "Student accounts cannot view other students' evidence queues, inspect confirmation documents, self-approve submission_confirmed, or mutate official routing verification state. Switch to Data Verifier or Admin in the Reviewer Session selector above to run verification operations."
              )}
            </p>
          </div>
        ) : (
          <>
            {/* Routing Quality Summary Strip */}
            {summary && (
              <section
                aria-label={t("ops.summary_total", "Total Directory Routes")}
                className="grid grid-cols-2 lg:grid-cols-5 gap-3"
              >
                <div className="rounded-xl border border-zinc-200 bg-white p-4">
                  <div className="text-[11px] font-bold uppercase text-zinc-500">
                    {t("ops.summary_total", "Total Directory Routes")}
                  </div>
                  <div className="mt-1 text-2xl font-extrabold text-zinc-900">{summary.total_routes}</div>
                  <div className="text-[11px] text-zinc-500">
                    {t("ops.summary_domain_match", "Domain Match")}: {summary.by_method.ipeds_domain_match || 0} •{" "}
                    {t("ops.summary_system", "System")}: {summary.by_method.ipeds_state_system || 0}
                  </div>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
                  <div className="text-[11px] font-bold uppercase text-emerald-800">
                    {t("ops.summary_verified", "Verified Official")}
                  </div>
                  <div className="mt-1 text-2xl font-extrabold text-emerald-900">{summary.verified}</div>
                  <div className="text-[11px] text-emerald-800/80">
                    {t("ops.summary_expired", "Expired")}: {summary.health?.verification_expired || 0} •{" "}
                    {t("ops.summary_expiring", "Expiring <30d")}: {summary.health?.verification_expiring_soon_30d || 0}
                  </div>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 flex flex-col justify-between">
                  <div>
                    <div className="text-[11px] font-bold uppercase text-amber-800">
                      {t("ops.summary_manual_queue", "Manual Review Queue")}
                    </div>
                    <div className="mt-1 text-2xl font-extrabold text-amber-900">{summary.needs_verification}</div>
                    <div className="text-[11px] text-amber-900/80">
                      {t("ops.summary_pending", "Pending")}: {summary.needs_verification} •{" "}
                      {t("ops.summary_manually_reviewed", "Manually Reviewed")}: {summary.manually_reviewed_count || 0}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab("routing");
                      setRouteStatusFilter("manual_review");
                    }}
                    className="mt-1.5 text-start text-[11px] font-bold text-amber-900 underline hover:text-amber-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-700 rounded"
                  >
                    {t("ops.summary_open_manual", "Open Manual Review Queue →")}
                  </button>
                </div>
                <div className="rounded-xl border border-zinc-200 bg-white p-4">
                  <div className="text-[11px] font-bold uppercase text-zinc-500">
                    {t("ops.summary_health_pathways", "Link Health & Pathways")}
                  </div>
                  <div className="mt-1 text-xs font-semibold text-zinc-700 space-y-0.5">
                    <div>
                      {t("ops.summary_healthy", "Healthy")}: {summary.health?.health_check_status?.healthy || 0} •{" "}
                      {t("ops.summary_redirected", "Redirected")}: {summary.health?.health_check_status?.redirected || 0}
                    </div>
                    <div>
                      {t("ops.summary_unreachable", "Unreachable")}:{" "}
                      {(summary.health?.health_check_status?.unreachable || 0) +
                        (summary.health?.health_check_status?.error || 0)}{" "}
                      • {t("ops.summary_pathways_verified", "Pathways Verified")}: {summary.health?.pathway_verified || 0}
                    </div>
                    {summary.health?.automated_sweep && (
                      <div className="text-[10px] text-zinc-500">
                        {t("ops.summary_auto_sweep", "Auto Expiry Sweep")}:{" "}
                        {summary.health.automated_sweep.enabled ? "ON" : "OFF"} (
                        {summary.health.automated_sweep.runs_completed})
                      </div>
                    )}
                  </div>
                </div>
                <div className="rounded-xl border border-zinc-200 bg-white p-4">
                  <div className="text-[11px] font-bold uppercase text-zinc-500">
                    {t("ops.summary_confirmation_queue", "Confirmation Queue")}
                  </div>
                  <div className="mt-1 text-2xl font-extrabold text-indigo-700">{evidenceQueue.length}</div>
                  <div className="text-[11px] text-zinc-500">
                    {t("ops.summary_filtered", "Filtered")} ({statusLabel(evidenceStatusFilter)})
                  </div>
                </div>
              </section>
            )}

            {/* Operations Tabs */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div role="tablist" aria-label={t("ops.title", "Verification & Trust Operations Console")} className="inline-flex rounded-xl border border-zinc-200 bg-white p-1">
                <button
                  id="ops-tab-evidence"
                  role="tab"
                  aria-selected={activeTab === "evidence"}
                  aria-controls="ops-panel-evidence"
                  type="button"
                  onClick={() => setActiveTab("evidence")}
                  className={`rounded-lg px-4 py-2 text-xs font-bold focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 ${
                    activeTab === "evidence" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:text-zinc-900"
                  }`}
                >
                  {t("ops.tab_evidence", "Confirmation Evidence Queue")} ({evidenceQueue.length})
                </button>
                <button
                  id="ops-tab-routing"
                  role="tab"
                  aria-selected={activeTab === "routing"}
                  aria-controls="ops-panel-routing"
                  type="button"
                  onClick={() => setActiveTab("routing")}
                  className={`rounded-lg px-4 py-2 text-xs font-bold focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 ${
                    activeTab === "routing" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:text-zinc-900"
                  }`}
                >
                  {t("ops.tab_routing", "Routing Data Quality Queue")} ({routingQueue.length})
                </button>
              </div>

              {activeTab === "routing" && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={handleBatchHealthCheck}
                    disabled={batchHealthRunning}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-300 bg-white px-3 py-2 text-xs font-bold text-zinc-800 hover:bg-zinc-50 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                  >
                    <Activity className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
                    {batchHealthRunning
                      ? t("ops.btn_checking_links", "Checking Links...")
                      : t("ops.btn_check_health_batch", "Check Link Health (15)")}
                  </button>
                  <button
                    type="button"
                    onClick={handleExpireStaleRoutes}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-300 bg-white px-3 py-2 text-xs font-bold text-zinc-800 hover:bg-zinc-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                  >
                    <Clock className="h-3.5 w-3.5 text-amber-600" aria-hidden="true" />
                    {t("ops.btn_flag_expired", "Flag Expired")}
                  </button>
                  <button
                    type="button"
                    onClick={handleRunBatchVerify}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                  >
                    <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                    {t("ops.btn_batch_audit", "Run Deterministic Batch Audit")}
                  </button>
                </div>
              )}
            </div>

            {/* TAB 1: CONFIRMATION EVIDENCE QUEUE */}
            {activeTab === "evidence" && (
              <section id="ops-panel-evidence" role="tabpanel" aria-labelledby="ops-tab-evidence" className="space-y-4">
                <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t("ops.tab_evidence", "Confirmation Evidence Queue")}>
                  {(
                    [
                      { id: "pending", label: t("ops.filter_pending", "Pending") },
                      { id: "accepted", label: t("ops.filter_accepted", "Accepted") },
                      { id: "rejected", label: t("ops.filter_rejected", "Rejected") },
                      { id: "all", label: t("ops.filter_all", "All") },
                    ] as const
                  ).map((st) => (
                    <button
                      key={st.id}
                      type="button"
                      aria-pressed={evidenceStatusFilter === st.id}
                      onClick={() => setEvidenceStatusFilter(st.id)}
                      className={`rounded-full px-3 py-1 text-xs font-semibold border focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 ${
                        evidenceStatusFilter === st.id
                          ? "bg-zinc-900 text-white border-zinc-900"
                          : "bg-white text-zinc-700 border-zinc-200"
                      }`}
                    >
                      {st.label}
                    </button>
                  ))}
                </div>

                {loading ? (
                  <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center text-xs text-zinc-500">
                    {t("ops.loading_evidence", "Loading confirmation evidence queue...")}
                  </div>
                ) : evidenceQueue.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center text-xs text-zinc-600">
                    {t("ops.empty_evidence", "No confirmation evidence records match this status.")}
                  </div>
                ) : (
                  evidenceQueue.map((ev) => {
                    const docPreview = docPreviewByEv[ev.id];
                    const reasonSelectId = `ev-reason-${ev.id}`;
                    const notesInputId = `ev-notes-${ev.id}`;
                    return (
                      <article key={ev.id} className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-4 shadow-xs">
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
                                {statusLabel(ev.review_status)}
                              </span>
                              <span className="text-[11px] text-zinc-500">
                                {t("ops.app_status", "App Status")}: <strong>{ev.application_status}</strong>
                              </span>
                            </div>
                            <h3 className="mt-1.5 text-base font-extrabold text-zinc-900">{ev.institution_name}</h3>
                            <p className="text-xs text-zinc-600">
                              {t("ops.student_label", "Student")}: <strong>{ev.student_name || "Applicant"}</strong> (
                              <span dir="ltr">{ev.student_email || "N/A"}</span>) •{" "}
                              {t("ops.confirmation_ref", "Confirmation Ref")}:{" "}
                              <strong dir="ltr" className="font-mono">
                                {ev.external_confirmation_number || t("ops.none_entered", "None entered")}
                              </strong>
                            </p>
                          </div>

                          <button
                            type="button"
                            onClick={() => handleInspectDoc(ev.id)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs font-bold text-zinc-800 hover:bg-zinc-100 shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                          >
                            <FileText className="h-3.5 w-3.5 text-indigo-600" aria-hidden="true" />
                            {t("ops.inspect_vault", "Inspect Vault Artifact")}
                          </button>
                        </div>

                        <div className="rounded-lg bg-zinc-50 border border-zinc-200/80 px-3 py-2 text-xs text-zinc-700 flex flex-wrap items-center justify-between gap-2">
                          <span>
                            {t("ops.file_label", "File")}: <strong>{ev.original_filename || "N/A"}</strong> (
                            {ev.file_type || "file"})
                          </span>
                          <span dir="ltr" className="font-mono text-[11px] text-zinc-500">
                            SHA-256: {ev.document_sha256 || t("ops.missing_checksum", "Missing checksum")}
                          </span>
                        </div>

                        {docPreview && (
                          <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-3.5 text-xs space-y-1.5">
                            <div className="font-bold text-indigo-950">
                              {t("ops.vault_preview_title", "Document Vault Extracted Content")} ({docPreview.original_filename})
                            </div>
                            <pre
                              dir="ltr"
                              className="whitespace-pre-wrap rounded-lg bg-white border border-indigo-100 p-2.5 font-mono text-[11px] text-zinc-800 max-h-40 overflow-y-auto"
                            >
                              {docPreview.extracted_text ||
                                t("ops.vault_binary_verified", "Binary / image artifact verified by SHA-256 checksum.")}
                            </pre>
                          </div>
                        )}

                        {ev.rejection_reason_label && (
                          <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-900">
                            <strong>{t("ops.current_rejection", "Current Rejection Reason")}:</strong>{" "}
                            {ev.rejection_reason_label} — {ev.reviewer_notes}
                          </div>
                        )}

                        {/* Reviewer Decision Controls */}
                        <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3.5 grid grid-cols-1 lg:grid-cols-4 gap-3 items-end">
                          <div>
                            <label htmlFor={reasonSelectId} className="block text-[11px] font-bold text-zinc-700 mb-1">
                              {t("ops.rejection_taxonomy_label", "Rejection Reason Taxonomy (required if rejecting)")}
                            </label>
                            <select
                              id={reasonSelectId}
                              value={evReasonById[ev.id] || evidenceReasons[0]?.code || "missing_confirmation_id"}
                              onChange={(e) => setEvReasonById((prev) => ({ ...prev, [ev.id]: e.target.value }))}
                              className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-2 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                            >
                              {evidenceReasons.map((r) => (
                                <option key={r.code} value={r.code}>
                                  {r.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="lg:col-span-2">
                            <label htmlFor={notesInputId} className="block text-[11px] font-bold text-zinc-700 mb-1">
                              {t("ops.reviewer_notes_label", "Reviewer Notes (audit trail)")}
                            </label>
                            <input
                              id={notesInputId}
                              type="text"
                              value={evNotesById[ev.id] || ""}
                              onChange={(e) => setEvNotesById((prev) => ({ ...prev, [ev.id]: e.target.value }))}
                              placeholder={t(
                                "ops.reviewer_notes_placeholder",
                                "Explain verification outcome or what proof the student should re-upload..."
                              )}
                              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                            />
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => handleEvidenceDecision(ev.id, "accepted")}
                              className="flex-1 inline-flex items-center justify-center gap-1 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700"
                            >
                              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                              {t("ops.btn_accept_confirm", "Accept & Confirm")}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleEvidenceDecision(ev.id, "rejected")}
                              className="flex-1 inline-flex items-center justify-center gap-1 rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-700"
                            >
                              <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
                              {t("ops.btn_reject", "Reject")}
                            </button>
                          </div>
                        </div>

                        {/* Immutable Audit Trail */}
                        {ev.audit_history && ev.audit_history.length > 0 && (
                          <div className="border-t border-zinc-100 pt-2.5 space-y-1">
                            <div className="text-[11px] font-bold uppercase text-zinc-500 flex items-center gap-1">
                              <History className="h-3 w-3" aria-hidden="true" />
                              {t("ops.audit_history_title", "Immutable Review Audit History")} ({ev.audit_history.length})
                            </div>
                            {ev.audit_history.map((a) => (
                              <div key={a.id} className="text-[11px] text-zinc-700 flex items-center justify-between gap-2">
                                <span>
                                  <strong className="uppercase">{a.action}</strong> by {a.actor_role} (
                                  <span dir="ltr">{a.actor_email || "system"}</span>)
                                  {a.rejection_reason_label ? ` [${a.rejection_reason_label}]` : ""} — {a.notes || ""}
                                </span>
                                <span dir="ltr" className="font-mono text-zinc-500 shrink-0">
                                  {formatShortDate(a.created_at)}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </article>
                    );
                  })
                )}
              </section>
            )}

            {/* TAB 2: ROUTING DATA QUALITY QUEUE */}
            {activeTab === "routing" && (
              <section id="ops-panel-routing" role="tabpanel" aria-labelledby="ops-tab-routing" className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-3.5">
                  <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={t("ops.tab_routing", "Routing Data Quality Queue")}>
                    {(
                      [
                        { id: "manual_review", label: t("ops.rt_filter_manual_review", "Manual Review & Pending") },
                        {
                          id: "needs_verification",
                          label: `${t("ops.rt_filter_needs_verif", "Needs Verification")} (${summary?.needs_verification ?? 0})`,
                        },
                        { id: "verified", label: t("ops.rt_filter_verified", "Verified") },
                        { id: "expired", label: t("ops.rt_filter_expired", "Expired") },
                        { id: "unverified", label: t("ops.rt_filter_unverified", "Unverified") },
                        { id: "all", label: t("ops.filter_all", "All") },
                      ] as const
                    ).map((st) => (
                      <button
                        key={st.id}
                        type="button"
                        aria-pressed={routeStatusFilter === st.id}
                        onClick={() => setRouteStatusFilter(st.id)}
                        className={`rounded-full px-3 py-1 text-xs font-semibold border focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 ${
                          routeStatusFilter === st.id
                            ? "bg-zinc-900 text-white border-zinc-900"
                            : "bg-white text-zinc-700 border-zinc-200"
                        }`}
                      >
                        {st.label}
                      </button>
                    ))}
                  </div>

                  <div className="relative w-full sm:w-72">
                    <label htmlFor="route-search-input" className="sr-only">
                      {t("ops.search_placeholder", "Filter portal or university...")}
                    </label>
                    <Search className="h-3.5 w-3.5 text-zinc-400 absolute start-3 top-2.5" aria-hidden="true" />
                    <input
                      id="route-search-input"
                      type="text"
                      value={routeSearch}
                      onChange={(e) => setRouteSearch(e.target.value)}
                      placeholder={t("ops.search_placeholder", "Filter portal or university...")}
                      className="w-full rounded-lg border border-zinc-300 bg-white ps-8 pe-3 py-1.5 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                    />
                  </div>
                </div>

                {routingQueue.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-8 text-center text-xs text-zinc-600">
                    {t("ops.empty_routing", "No routing records match this filter.")}
                  </div>
                ) : (
                  routingQueue.map((rt) => {
                    const isExpired = Boolean(
                      rt.verification_expires_at && new Date(rt.verification_expires_at).getTime() <= Date.now()
                    );
                    const urlInputId = `route-url-${rt.id}`;
                    const pathwaySelectId = `route-pathway-${rt.id}`;
                    const reasonSelectId = `route-reason-${rt.id}`;
                    const notesInputId = `route-notes-${rt.id}`;
                    return (
                      <article key={rt.id} className="rounded-2xl border border-zinc-200 bg-white p-5 space-y-3 shadow-xs">
                        <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-0.5 text-[10px] font-bold uppercase text-zinc-700">
                                <Globe2 className="h-3 w-3" aria-hidden="true" />
                                <span dir="ltr">{rt.country_code}</span> • {rt.platform_type.replace(/_/g, " ")}
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
                                {statusLabel(rt.verification_status)}
                              </span>
                              {rt.verification_method && (
                                <span className="text-[11px] font-mono text-zinc-500">
                                  {t("ops.method_label", "method")}: <span dir="ltr">{rt.verification_method}</span>
                                </span>
                              )}
                              <span
                                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                  rt.pathway_verified
                                    ? "bg-indigo-100 text-indigo-800"
                                    : "bg-zinc-100 text-zinc-600"
                                }`}
                              >
                                <ShieldCheck className="h-3 w-3" aria-hidden="true" />
                                {rt.pathway_verified
                                  ? `${t("ops.pathway_verified", "Pathway Verified")}: ${rt.applicant_type}`
                                  : `${t("ops.pathway_unverified", "Pathway Unverified")} (${rt.applicant_type})`}
                              </span>
                              {rt.last_health_check_status ? (
                                <span
                                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                    rt.last_health_check_status === "healthy"
                                      ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                                      : rt.last_health_check_status === "redirected"
                                        ? "bg-blue-50 text-blue-800 border border-blue-200"
                                        : "bg-red-50 text-red-800 border border-red-200"
                                  }`}
                                >
                                  <Activity className="h-3 w-3" aria-hidden="true" />
                                  <span dir="ltr">
                                    {rt.last_health_check_status.toUpperCase()}
                                    {rt.last_health_check_http_code ? ` (${rt.last_health_check_http_code})` : ""}
                                  </span>
                                </span>
                              ) : (
                                <span className="rounded-full bg-zinc-50 border border-zinc-200 px-2 py-0.5 text-[10px] text-zinc-500">
                                  {t("ops.health_unchecked", "Link health unchecked")}
                                </span>
                              )}
                              {rt.verification_expires_at && (
                                <span
                                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                                    isExpired ? "bg-red-100 text-red-800" : "bg-zinc-100 text-zinc-700"
                                  }`}
                                >
                                  <Clock className="h-3 w-3" aria-hidden="true" />
                                  {isExpired ? (
                                    t("ops.status_expired", "EXPIRED")
                                  ) : (
                                    <>
                                      {t("ops.status_expires", "Expires")}{" "}
                                      <span dir="ltr">{formatShortDate(rt.verification_expires_at)}</span>
                                    </>
                                  )}
                                </span>
                              )}
                            </div>
                            <h3 className="mt-1.5 text-base font-extrabold text-zinc-900">
                              {rt.institution_name || rt.platform_name}
                            </h3>
                            <div dir="ltr" className="mt-1 font-mono text-xs text-indigo-700 break-all">
                              {rt.official_url}
                            </div>
                            {rt.final_redirect_url && rt.final_redirect_url !== rt.official_url && (
                              <div className="mt-0.5 text-[11px] text-blue-700 break-all">
                                {t("ops.redirect_dest", "Redirected destination")} ({rt.redirect_chain_length ?? 1}):{" "}
                                <span dir="ltr" className="font-mono">
                                  {rt.final_redirect_url}
                                </span>
                              </div>
                            )}
                            {rt.institution_website && (
                              <div className="text-[11px] text-zinc-500 mt-0.5">
                                {t("ops.official_site", "Official Site")}: <span dir="ltr">{rt.institution_website}</span>
                              </div>
                            )}
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              type="button"
                              onClick={() => handleSingleHealthCheck(rt.id)}
                              disabled={healthCheckingId === rt.id}
                              className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                            >
                              <Activity className="h-3 w-3 text-emerald-600" aria-hidden="true" />
                              {healthCheckingId === rt.id
                                ? t("ops.btn_checking", "Checking...")
                                : t("ops.btn_check_health", "Check Health")}
                            </button>
                            <a
                              href={rt.official_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                            >
                              {t("ops.btn_open_link", "Open Link")} <ExternalLink className="h-3 w-3" aria-hidden="true" />
                            </a>
                          </div>
                        </div>

                        {rt.trust_checks?.warnings && rt.trust_checks.warnings.length > 0 && (
                          <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-900 flex items-start gap-2">
                            <AlertTriangle className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" aria-hidden="true" />
                            <span>{rt.trust_checks.warnings.join(" • ")}</span>
                          </div>
                        )}

                        <div className="grid grid-cols-1 lg:grid-cols-5 gap-2.5 items-end bg-zinc-50 rounded-xl p-3 border border-zinc-200/80">
                          <div>
                            <label htmlFor={urlInputId} className="block text-[11px] font-bold text-zinc-700 mb-1">
                              {t("ops.label_corrected_url", "Corrected HTTPS URL (optional)")}
                            </label>
                            <input
                              id={urlInputId}
                              type="url"
                              dir="ltr"
                              value={routeUrlById[rt.id] || ""}
                              onChange={(e) => setRouteUrlById((prev) => ({ ...prev, [rt.id]: e.target.value }))}
                              placeholder={rt.official_url}
                              className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                            />
                          </div>

                          <div>
                            <label htmlFor={pathwaySelectId} className="block text-[11px] font-bold text-zinc-700 mb-1">
                              {t("ops.label_pathway", "Applicant Pathway Applicability")}
                            </label>
                            <div className="flex items-center gap-1.5">
                              <select
                                id={pathwaySelectId}
                                value={routePathwayById[rt.id] || rt.applicant_type}
                                onChange={(e) => setRoutePathwayById((prev) => ({ ...prev, [rt.id]: e.target.value }))}
                                className="flex-1 rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                              >
                                <option value="all">{t("ops.pathway_all", "All Undergraduate")}</option>
                                <option value="first_year">{t("ops.pathway_first_year", "First-Year Only")}</option>
                                <option value="transfer">{t("ops.pathway_transfer", "Transfer Only")}</option>
                                <option value="international_first_year">
                                  {t("ops.pathway_intl_fy", "Intl First-Year")}
                                </option>
                                <option value="international_transfer">
                                  {t("ops.pathway_intl_tr", "Intl Transfer")}
                                </option>
                              </select>
                              <button
                                type="button"
                                onClick={() => handleVerifyPathway(rt)}
                                className="rounded-lg bg-indigo-600 px-2.5 py-1.5 text-[11px] font-bold text-white hover:bg-indigo-700 shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                              >
                                {t("ops.btn_verify_pathway", "Verify Pathway")}
                              </button>
                            </div>
                          </div>

                          <div>
                            <label htmlFor={reasonSelectId} className="block text-[11px] font-bold text-zinc-700 mb-1">
                              {t("ops.label_route_rejection", "Rejection Reason (if unverified)")}
                            </label>
                            <select
                              id={reasonSelectId}
                              value={routeReasonById[rt.id] || routeReasons[0]?.code || "broken_or_404"}
                              onChange={(e) => setRouteReasonById((prev) => ({ ...prev, [rt.id]: e.target.value }))}
                              className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                            >
                              {routeReasons.map((r) => (
                                <option key={r.code} value={r.code}>
                                  {r.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div>
                            <label htmlFor={notesInputId} className="block text-[11px] font-bold text-zinc-700 mb-1">
                              {t("ops.label_verifier_notes", "Verifier Notes")}
                            </label>
                            <input
                              id={notesInputId}
                              type="text"
                              value={routeNotesById[rt.id] || ""}
                              onChange={(e) => setRouteNotesById((prev) => ({ ...prev, [rt.id]: e.target.value }))}
                              placeholder={t(
                                "ops.placeholder_verifier_notes",
                                "Confirmed tenant on admissions site..."
                              )}
                              className="w-full rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"
                            />
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => handleRouteDecision(rt.id, "verified")}
                              className="flex-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700"
                            >
                              {t("ops.btn_verify_url", "Verify URL")}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleRouteDecision(rt.id, "unverified")}
                              className="flex-1 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-700"
                            >
                              {t("ops.btn_reject", "Reject")}
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
                      </article>
                    );
                  })
                )}
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
