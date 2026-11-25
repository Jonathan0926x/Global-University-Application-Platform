"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowRightLeft,
  Bot,
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  Compass,
  ExternalLink,
  FileCheck2,
  FileText,
  Globe2,
  GraduationCap,
  History,
  Plus,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-react";
import {
  ApplicationRouteItem,
  ApplicationWorkspace,
  createApplication,
  deleteApplicationWorkspace,
  fetchApplications,
  fetchInstitutionRouting,
  fetchInstitutions,
  fetchRoutingDirectory,
  Institution,
  InstitutionRoutingResolution,
  recordExternalRedirect,
  refreshApplicationChecklist,
  reportExternalSubmission,
  updateApplicationStatus,
  updateRequirementItemStatus,
  uploadSubmissionEvidence,
} from "@/lib/api-client";
import { useI18n } from "@/lib/i18n/context";

const LIFECYCLE_STEPS = [
  { key: "not_started", label: "Not Started" },
  { key: "preparing", label: "Preparing" },
  { key: "ready_to_apply", label: "Ready to Apply" },
  { key: "redirected_to_external_portal", label: "Redirected to Portal" },
  { key: "student_reported_submitted", label: "Reported Submitted" },
  { key: "submission_confirmed", label: "Confirmed" },
];

const STATUS_BADGE_STYLE: Record<string, { bg: string; text: string; border: string; label: string }> = {
  not_started: {
    bg: "bg-zinc-100",
    text: "text-zinc-700",
    border: "border-zinc-200",
    label: "Not Started",
  },
  preparing: {
    bg: "bg-sky-50",
    text: "text-sky-800",
    border: "border-sky-200",
    label: "Preparing Materials",
  },
  ready_to_apply: {
    bg: "bg-indigo-50",
    text: "text-indigo-800",
    border: "border-indigo-200",
    label: "Ready to Apply",
  },
  redirected_to_external_portal: {
    bg: "bg-amber-50",
    text: "text-amber-800",
    border: "border-amber-200",
    label: "Redirected Externally (Not Yet Submitted)",
  },
  student_reported_submitted: {
    bg: "bg-violet-50",
    text: "text-violet-800",
    border: "border-violet-200",
    label: "Student-Reported Submitted (Awaiting Confirmation)",
  },
  submission_confirmed: {
    bg: "bg-emerald-50",
    text: "text-emerald-800",
    border: "border-emerald-200",
    label: "Submission Confirmed",
  },
};

function formatDateShort(iso?: string | null): string {
  if (!iso) return "N/A";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().slice(0, 10);
}

function ApplicationsWorkspaceContent() {
  const { direction, t } = useI18n();
  const searchParams = useSearchParams();

  const initialTab = searchParams.get("tab") === "directory" ? "directory" : "tracker";
  const prefillInstitutionId = searchParams.get("institution_id") || searchParams.get("institution") || "";
  const prefillPathway = (searchParams.get("pathway") === "transfer" ? "transfer" : "first_year") as
    | "first_year"
    | "transfer";

  const [activeTab, setActiveTab] = useState<"tracker" | "directory">(initialTab);
  const [applications, setApplications] = useState<ApplicationWorkspace[]>([]);
  const [pathwayFilter, setPathwayFilter] = useState<"all" | "first_year" | "transfer">("all");
  const [loadingApps, setLoadingApps] = useState(true);

  // Directory state
  const [routes, setRoutes] = useState<ApplicationRouteItem[]>([]);
  const [loadingRoutes, setLoadingRoutes] = useState(false);
  const [dirSearch, setDirSearch] = useState("");
  const [dirCountry, setDirCountry] = useState("");
  const [dirPathway, setDirPathway] = useState<"all" | "first_year" | "transfer">("all");
  const [dirVerifiedOnly, setDirVerifiedOnly] = useState(true);

  // Start New Application workspace controls
  const [catalogInstitutions, setCatalogInstitutions] = useState<Institution[]>([]);
  const [selectedInstId, setSelectedInstId] = useState(prefillInstitutionId);
  const [newPathway, setNewPathway] = useState<"first_year" | "transfer">(prefillPathway);
  const [newMajor, setNewMajor] = useState("Computer Science");
  const [newTerm, setNewTerm] = useState("Fall 2027");
  const [instResolution, setInstResolution] = useState<InstitutionRoutingResolution | null>(null);
  const [creatingApp, setCreatingApp] = useState(false);

  // Interactive per-application panels
  const [expandedHistory, setExpandedHistory] = useState<Record<string, boolean>>({});
  const [ackUnverified, setAckUnverified] = useState<Record<string, boolean>>({});
  const [selectedRouteByApp, setSelectedRouteByApp] = useState<Record<string, string>>({});
  const [submissionFormOpen, setSubmissionFormOpen] = useState<Record<string, boolean>>({});
  const [confNumByApp, setConfNumByApp] = useState<Record<string, string>>({});
  const [submittedViaByApp, setSubmittedViaByApp] = useState<Record<string, string>>({});
  const [subNoteByApp, setSubNoteByApp] = useState<Record<string, string>>({});
  const [evidenceFileByApp, setEvidenceFileByApp] = useState<Record<string, File | null>>({});
  const [evidenceTypeByApp, setEvidenceTypeByApp] = useState<Record<string, string>>({});
  const [actionBusy, setActionBusy] = useState<Record<string, boolean>>({});
  const [banner, setBanner] = useState<{ type: "info" | "warning" | "error"; text: string } | null>(null);

  const loadApplications = useCallback(async () => {
    setLoadingApps(true);
    try {
      const data = await fetchApplications();
      setApplications(data);
    } catch (e) {
      setBanner({ type: "error", text: e instanceof Error ? e.message : "Failed to load applications" });
    } finally {
      setLoadingApps(false);
    }
  }, []);

  const loadDirectory = useCallback(async () => {
    setLoadingRoutes(true);
    try {
      const data = await fetchRoutingDirectory({
        q: dirSearch || undefined,
        country: dirCountry || undefined,
        applicant_type: dirPathway,
        verified_only: dirVerifiedOnly,
        limit: 120,
      });
      setRoutes(data);
    } catch {
      setRoutes([]);
    } finally {
      setLoadingRoutes(false);
    }
  }, [dirSearch, dirCountry, dirPathway, dirVerifiedOnly]);

  useEffect(() => {
    loadApplications();
    fetchInstitutions()
      .then((list) => {
        setCatalogInstitutions(list);
        if (!prefillInstitutionId && list.length > 0) {
          const mit = list.find((i) => i.official_name.includes("Massachusetts Institute")) || list[0];
          setSelectedInstId(mit.id);
        }
      })
      .catch(() => {});
  }, [loadApplications, prefillInstitutionId]);

  useEffect(() => {
    loadDirectory();
  }, [loadDirectory]);

  useEffect(() => {
    if (!selectedInstId) {
      setInstResolution(null);
      return;
    }
    fetchInstitutionRouting(selectedInstId, newPathway)
      .then(setInstResolution)
      .catch(() => setInstResolution(null));
  }, [selectedInstId, newPathway]);

  const filteredApplications = useMemo(() => {
    if (pathwayFilter === "all") return applications;
    return applications.filter((a) => a.applicant_type === pathwayFilter);
  }, [applications, pathwayFilter]);

  const updateOneApplication = (updated: ApplicationWorkspace) => {
    setApplications((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  };

  const handleStartWorkspace = async (
    institutionId: string,
    pathway: "first_year" | "transfer",
    routeId?: string
  ) => {
    if (!institutionId) return;
    setCreatingApp(true);
    setBanner(null);
    try {
      const created = await createApplication(institutionId, pathway, newMajor || undefined, newTerm || undefined, routeId);
      setApplications((prev) => {
        const exists = prev.some((a) => a.id === created.id);
        return exists ? prev.map((a) => (a.id === created.id ? created : a)) : [created, ...prev];
      });
      setActiveTab("tracker");
      setBanner({
        type: "info",
        text: `Application workspace active for ${created.institution?.official_name || "selected university"} (${pathway.replace("_", "-")}).`,
      });
    } catch (e) {
      setBanner({ type: "error", text: e instanceof Error ? e.message : "Could not start workspace" });
    } finally {
      setCreatingApp(false);
    }
  };

  const handleExternalRedirect = async (app: ApplicationWorkspace) => {
    setActionBusy((prev) => ({ ...prev, [app.id]: true }));
    setBanner(null);
    try {
      const chosenRouteId = selectedRouteByApp[app.id] || app.verified_routes?.[0]?.id;
      const result = await recordExternalRedirect(app.id, {
        route_id: chosenRouteId,
        acknowledge_unverified: Boolean(ackUnverified[app.id]),
      });
      updateOneApplication(result.application);
      setBanner({ type: "info", text: result.notice });
      window.open(result.redirect_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setBanner({
        type: "warning",
        text: e instanceof Error ? e.message : "External redirect blocked until destination is verified.",
      });
    } finally {
      setActionBusy((prev) => ({ ...prev, [app.id]: false }));
    }
  };

  const handleReportSubmissionAndEvidence = async (app: ApplicationWorkspace) => {
    const file = evidenceFileByApp[app.id];
    const confNum = (confNumByApp[app.id] || "").trim();
    const via = (submittedViaByApp[app.id] || "").trim() || app.external_platform_name || undefined;
    const note = (subNoteByApp[app.id] || "").trim();

    if (!confNum && !file && !note) {
      setBanner({
        type: "warning",
        text: "Enter your confirmation number, note, or upload your confirmation screenshot/email receipt.",
      });
      return;
    }

    setActionBusy((prev) => ({ ...prev, [app.id]: true }));
    setBanner(null);
    try {
      let latest = await reportExternalSubmission(app.id, {
        external_confirmation_number: confNum || undefined,
        submitted_via: via,
        note: note || undefined,
      });

      if (file) {
        await uploadSubmissionEvidence(app.id, {
          file,
          evidence_type: evidenceTypeByApp[app.id] || "portal_screenshot",
          external_confirmation_number: confNum || undefined,
          submitted_note: note || undefined,
        });
        const refreshed = await fetchApplications();
        const found = refreshed.find((a) => a.id === app.id);
        if (found) latest = found;
      }

      updateOneApplication(latest);
      setEvidenceFileByApp((prev) => ({ ...prev, [app.id]: null }));
      setSubmissionFormOpen((prev) => ({ ...prev, [app.id]: false }));
      setBanner({
        type: "info",
        text: "Self-reported external submission saved cleanly (`student_reported_submitted`). Final `submission_confirmed` awaits verifier review of your Document Vault proof.",
      });
    } catch (e) {
      setBanner({ type: "error", text: e instanceof Error ? e.message : "Failed to save submission report" });
    } finally {
      setActionBusy((prev) => ({ ...prev, [app.id]: false }));
    }
  };

  return (
    <div dir={direction} className="min-h-screen bg-[#fafafc] text-zinc-900 pb-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-8">
        {/* Top Header */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-zinc-200 pb-6">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-[11px] font-semibold text-emerald-800">
              <ShieldCheck className="h-3.5 w-3.5" />
              Honest External Routing &amp; Evidence Vault
            </div>
            <h1 className="mt-2.5 text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900">
              {t("applications.title", "Application Routing & Submission Tracker")}
            </h1>
            <p className="mt-1.5 text-sm text-zinc-600 max-w-3xl">
              {t(
                "applications.subtitle",
                "Prepare documents, verify official external portals, track honest deadlines, and confirm your external submission with Document Vault proof."
              )}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <Link
              href="/matching"
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
            >
              <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
              Match Engine
            </Link>
            <Link
              href="/documents"
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
            >
              <FileText className="h-3.5 w-3.5 text-emerald-600" />
              Document Vault
            </Link>
            <Link
              href="/counselor"
              className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-2 text-xs font-semibold text-white hover:bg-zinc-800"
            >
              <Bot className="h-3.5 w-3.5" />
              AI Counselor
            </Link>
          </div>
        </div>

        {/* Honesty Banner */}
        <div className="mt-6 rounded-xl border border-indigo-200 bg-indigo-50/70 p-4 text-xs text-indigo-950 flex items-start gap-3">
          <ShieldAlert className="h-4 w-4 text-indigo-700 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">Transparent External Submission Policy:</span> UniGlobe links exclusively to
            verified official portals and centralized platforms where confirmed, never fabricates URLs, and never claims an
            application was submitted when you click an external link. External submission moves first to{" "}
            <code className="font-mono text-[11px] bg-white px-1 py-0.5 rounded border border-indigo-200">
              redirected_to_external_portal
            </code>
            , then{" "}
            <code className="font-mono text-[11px] bg-white px-1 py-0.5 rounded border border-indigo-200">
              student_reported_submitted
            </code>{" "}
            when you report it, and{" "}
            <code className="font-mono text-[11px] bg-white px-1 py-0.5 rounded border border-indigo-200">
              submission_confirmed
            </code>{" "}
            only after Document Vault confirmation proof is verified.
          </div>
        </div>

        {banner && (
          <div
            role="status"
            className={`mt-4 rounded-xl border p-3.5 text-xs font-medium flex items-center justify-between gap-3 ${
              banner.type === "error"
                ? "bg-red-50 border-red-200 text-red-900"
                : banner.type === "warning"
                  ? "bg-amber-50 border-amber-200 text-amber-900"
                  : "bg-emerald-50 border-emerald-200 text-emerald-900"
            }`}
          >
            <span>{banner.text}</span>
            <button
              type="button"
              onClick={() => setBanner(null)}
              className="text-[11px] font-bold underline shrink-0"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Primary Tabs */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <div className="inline-flex rounded-xl border border-zinc-200 bg-white p-1 shadow-xs">
            <button
              type="button"
              onClick={() => setActiveTab("tracker")}
              className={`rounded-lg px-4 py-2 text-xs font-bold transition-colors ${
                activeTab === "tracker" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:text-zinc-900"
              }`}
            >
              {t("applications.tracker_tab", "My Applications Tracker")} ({applications.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("directory")}
              className={`rounded-lg px-4 py-2 text-xs font-bold transition-colors ${
                activeTab === "directory" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:text-zinc-900"
              }`}
            >
              {t("applications.directory_tab", "Official Routing Directory")} ({routes.length})
            </button>
          </div>

          {activeTab === "tracker" && (
            <div className="flex items-center gap-1.5">
              {(
                [
                  { id: "all", label: "All Pathways" },
                  { id: "first_year", label: "First-Year" },
                  { id: "transfer", label: "Transfer" },
                ] as const
              ).map((pill) => (
                <button
                  key={pill.id}
                  type="button"
                  onClick={() => setPathwayFilter(pill.id)}
                  className={`rounded-full px-3 py-1.5 text-xs font-semibold border transition-colors ${
                    pathwayFilter === pill.id
                      ? "bg-indigo-600 text-white border-indigo-600"
                      : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-50"
                  }`}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* TAB 1: APPLICATIONS TRACKER */}
        {activeTab === "tracker" && (
          <div className="mt-6 space-y-6">
            {/* Quick Launch / Start Workspace Card */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs">
              <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 flex-1">
                  <div>
                    <label className="block text-[11px] font-bold uppercase tracking-wide text-zinc-500 mb-1">
                      Target Institution
                    </label>
                    <select
                      aria-label="Target Institution"
                      value={selectedInstId}
                      onChange={(e) => setSelectedInstId(e.target.value)}
                      className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900"
                    >
                      {catalogInstitutions.map((inst) => (
                        <option key={inst.id} value={inst.id}>
                          {inst.official_name} ({inst.country_code})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold uppercase tracking-wide text-zinc-500 mb-1">
                      Applicant Pathway
                    </label>
                    <select
                      aria-label="Applicant Pathway"
                      value={newPathway}
                      onChange={(e) => setNewPathway(e.target.value as "first_year" | "transfer")}
                      className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900"
                    >
                      <option value="first_year">First-Year Applicant</option>
                      <option value="transfer">Transfer Applicant</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold uppercase tracking-wide text-zinc-500 mb-1">
                      Intended Major
                    </label>
                    <input
                      type="text"
                      value={newMajor}
                      onChange={(e) => setNewMajor(e.target.value)}
                      placeholder="e.g. Computer Science"
                      className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold uppercase tracking-wide text-zinc-500 mb-1">
                      Intended Term
                    </label>
                    <input
                      type="text"
                      value={newTerm}
                      onChange={(e) => setNewTerm(e.target.value)}
                      placeholder="Fall 2027"
                      className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900"
                    />
                  </div>
                </div>

                <button
                  type="button"
                  disabled={!selectedInstId || creatingApp}
                  onClick={() =>
                    handleStartWorkspace(selectedInstId, newPathway, instResolution?.verified_routes?.[0]?.id)
                  }
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-2.5 text-xs font-bold text-white hover:bg-zinc-800 disabled:opacity-50 shrink-0"
                >
                  <Plus className="h-4 w-4" />
                  {creatingApp ? "Creating..." : "Start Application Workspace"}
                </button>
              </div>

              {instResolution && (
                <div className="mt-3 pt-3 border-t border-zinc-100 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-600">
                  {instResolution.has_verified_destination ? (
                    <span className="inline-flex items-center gap-1.5 text-emerald-800 font-medium">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                      Verified portal available:{" "}
                      <strong>{instResolution.verified_routes[0]?.platform_name}</strong> (
                      <span dir="ltr" className="font-mono text-[11px]">
                        {instResolution.verified_routes[0]?.official_url}
                      </span>
                      )
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-amber-800 font-medium">
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                      {instResolution.notice}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Active Applications List */}
            {loadingApps ? (
              <div className="rounded-2xl border border-zinc-200 bg-white p-10 text-center text-sm text-zinc-500">
                Loading your application workspaces...
              </div>
            ) : filteredApplications.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-zinc-300 bg-white p-10 text-center">
                <Compass className="h-8 w-8 text-zinc-400 mx-auto" />
                <p className="mt-2 text-sm font-semibold text-zinc-900">No application workspaces in this view yet</p>
                <p className="mt-1 text-xs text-zinc-500">
                  Select a target institution above or browse verified portals in the Official Routing Directory.
                </p>
              </div>
            ) : (
              filteredApplications.map((app) => {
                const badge = STATUS_BADGE_STYLE[app.status] || STATUS_BADGE_STYLE.not_started;
                const currentStepIndex = LIFECYCLE_STEPS.findIndex((s) => s.key === app.status);
                const verifiedRoutes = app.verified_routes || [];
                const needsVerifRoutes = app.needs_verification_routes || [];
                const deadlines = app.deadlines || [];
                const history = app.status_history || [];
                const evidence = app.submission_evidence || [];

                return (
                  <div
                    key={app.id}
                    data-testid={`application-card-${app.id}`}
                    className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-xs space-y-5"
                  >
                    {/* Card Header */}
                    <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4 border-b border-zinc-100 pb-4">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-bold uppercase ${
                              app.applicant_type === "transfer"
                                ? "bg-sky-50 text-sky-800 border border-sky-200"
                                : "bg-indigo-50 text-indigo-800 border border-indigo-200"
                            }`}
                          >
                            {app.applicant_type === "transfer" ? (
                              <ArrowRightLeft className="h-3 w-3" />
                            ) : (
                              <GraduationCap className="h-3 w-3" />
                            )}
                            {app.applicant_type === "transfer" ? "Transfer" : "First-Year"}
                          </span>

                          <span
                            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${badge.bg} ${badge.text} ${badge.border}`}
                          >
                            {badge.label}
                          </span>

                          <span className="text-[11px] font-semibold text-zinc-500">
                            Readiness: <strong className="text-zinc-900">{app.readiness_pct}%</strong>
                          </span>
                        </div>

                        <h2 className="mt-2 text-lg font-extrabold text-zinc-900">
                          {app.institution?.official_name || "Institution"}
                        </h2>
                        <p className="text-xs text-zinc-600 mt-0.5">
                          Major: <strong className="text-zinc-800">{app.intended_major || "Undeclared"}</strong> • Term:{" "}
                          <strong className="text-zinc-800">{app.intended_term || "Fall 2027"}</strong> • Country:{" "}
                          <span dir="ltr">{app.institution?.country_code || "—"}</span>
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={async () => {
                            const updated = await refreshApplicationChecklist(app.id);
                            if (updated) updateOneApplication(updated);
                          }}
                          className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-zinc-700 hover:bg-zinc-50"
                        >
                          Sync Checklist
                        </button>
                        <Link
                          href={`/universities/${app.institution_id}`}
                          className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-indigo-700 hover:bg-indigo-50"
                        >
                          University Requirements
                        </Link>
                        <Link
                          href={`/counselor?institution_id=${app.institution_id}&pathway=${app.applicant_type}`}
                          className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-zinc-700 hover:bg-zinc-50"
                        >
                          Ask Counselor
                        </Link>
                        <button
                          type="button"
                          aria-label={`Remove workspace ${app.institution?.official_name || ""}`}
                          onClick={async () => {
                            await deleteApplicationWorkspace(app.id);
                            setApplications((prev) => prev.filter((item) => item.id !== app.id));
                          }}
                          className="rounded-lg border border-zinc-200 bg-white p-1.5 text-zinc-500 hover:text-red-700 hover:border-red-200"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* 6-State Honest Lifecycle Stepper */}
                    <div>
                      <div className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-2">
                        Honest Application Lifecycle
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                        {LIFECYCLE_STEPS.map((step, idx) => {
                          const isCurrent = step.key === app.status;
                          const isDone = currentStepIndex >= idx && currentStepIndex !== -1;
                          return (
                            <div
                              key={step.key}
                              className={`rounded-lg border px-2.5 py-2 text-[11px] font-semibold flex items-center gap-1.5 ${
                                isCurrent
                                  ? "border-zinc-900 bg-zinc-900 text-white"
                                  : isDone
                                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                                    : "border-zinc-200 bg-zinc-50 text-zinc-500"
                              }`}
                            >
                              <span className="h-4 w-4 rounded-full bg-black/10 flex items-center justify-center text-[10px] shrink-0">
                                {idx + 1}
                              </span>
                              <span className="truncate">{step.label}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Verified Deadlines & Countdowns */}
                    {deadlines.length > 0 && (
                      <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3.5">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1.5">
                          <Calendar className="h-3.5 w-3.5" />
                          Verified Deadlines &amp; Countdowns
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                          {deadlines.map((dl) => (
                            <div
                              key={dl.id}
                              className="flex items-center justify-between gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs"
                            >
                              <div>
                                <div className="font-semibold text-zinc-900">
                                  {dl.intake_term} — {dl.deadline_type.replace(/_/g, " ")}
                                </div>
                                <div className="text-[11px] text-zinc-500">
                                  <span dir="ltr">{dl.deadline_date || "TBD"}</span> • Source: {dl.source_name}
                                </div>
                              </div>
                              <span
                                dir="ltr"
                                className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold shrink-0 ${
                                  dl.is_passed
                                    ? "bg-zinc-100 text-zinc-600"
                                    : dl.is_urgent
                                      ? "bg-red-50 text-red-700 border border-red-200"
                                      : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                }`}
                              >
                                {dl.days_remaining === null || dl.days_remaining === undefined
                                  ? "Rolling / TBD"
                                  : dl.is_passed
                                    ? `Passed (${Math.abs(dl.days_remaining)}d ago)`
                                    : `${dl.days_remaining}d left`}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Official Portal Routing & Honest Redirect Box */}
                    <div className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-4 space-y-3">
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                        <div>
                          <div className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">
                            Official External Application Destination
                          </div>
                          {verifiedRoutes.length > 0 ? (
                            <div className="mt-1 space-y-1">
                              {verifiedRoutes.length > 1 && (
                                <select
                                  aria-label="Select Verified Application Portal"
                                  value={selectedRouteByApp[app.id] || verifiedRoutes[0].id}
                                  onChange={(e) =>
                                    setSelectedRouteByApp((prev) => ({ ...prev, [app.id]: e.target.value }))
                                  }
                                  className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-900"
                                >
                                  {verifiedRoutes.map((rt) => (
                                    <option key={rt.id} value={rt.id}>
                                      {rt.platform_name} ({rt.source_name})
                                    </option>
                                  ))}
                                </select>
                              )}
                              <div className="text-xs text-zinc-800 flex flex-wrap items-center gap-2">
                                <ShieldCheck className="h-4 w-4 text-emerald-600 shrink-0" />
                                <strong>
                                  {
                                    (
                                      verifiedRoutes.find((r) => r.id === selectedRouteByApp[app.id]) ||
                                      verifiedRoutes[0]
                                    ).platform_name
                                  }
                                </strong>
                                <span dir="ltr" className="font-mono text-[11px] text-indigo-700 break-all">
                                  {
                                    (
                                      verifiedRoutes.find((r) => r.id === selectedRouteByApp[app.id]) ||
                                      verifiedRoutes[0]
                                    ).official_url
                                  }
                                </span>
                              </div>
                            </div>
                          ) : needsVerifRoutes.length > 0 ? (
                            <div className="mt-1 space-y-1.5 text-xs text-amber-900">
                              <div className="flex items-start gap-2">
                                <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                                <span>
                                  <strong>Needs Verification:</strong> Registry lists{" "}
                                  <span dir="ltr" className="font-mono text-[11px] underline">
                                    {needsVerifRoutes[0].official_url}
                                  </span>
                                  . {app.routing_notice}
                                </span>
                              </div>
                              <label className="inline-flex items-center gap-2 text-[11px] font-medium text-zinc-700 cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={Boolean(ackUnverified[app.id])}
                                  onChange={(e) =>
                                    setAckUnverified((prev) => ({ ...prev, [app.id]: e.target.checked }))
                                  }
                                />
                                I understand this registry URL is unverified and want to record navigation anyway.
                              </label>
                            </div>
                          ) : (
                            <div className="mt-1 flex items-start gap-2 text-xs text-zinc-700">
                              <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                              <span>
                                {app.routing_notice ||
                                  "No verified application URL exists yet. Check this university's admissions office directly."}
                              </span>
                            </div>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-2 shrink-0">
                          {app.status === "not_started" || app.status === "preparing" ? (
                            <button
                              type="button"
                              onClick={async () => {
                                try {
                                  const res = await updateApplicationStatus(app.id, "ready_to_apply");
                                  updateOneApplication(res);
                                } catch (e) {
                                  setBanner({
                                    type: "error",
                                    text: e instanceof Error ? e.message : "Failed to update status",
                                  });
                                }
                              }}
                              className="rounded-lg border border-indigo-200 bg-white px-3 py-2 text-xs font-bold text-indigo-700 hover:bg-indigo-50"
                            >
                              Mark Ready to Apply
                            </button>
                          ) : null}

                          <button
                            type="button"
                            disabled={
                              Boolean(actionBusy[app.id]) ||
                              (verifiedRoutes.length === 0 &&
                                !(needsVerifRoutes.length > 0 && Boolean(ackUnverified[app.id])))
                            }
                            onClick={() => handleExternalRedirect(app)}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-45"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            {t("applications.launch_portal", "Go to Official External Portal")}
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              setSubmissionFormOpen((prev) => ({ ...prev, [app.id]: !prev[app.id] }))
                            }
                            className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3.5 py-2 text-xs font-bold text-white hover:bg-zinc-800"
                          >
                            <FileCheck2 className="h-3.5 w-3.5" />
                            {t("applications.report_submitted", "I Submitted Externally")}
                          </button>
                        </div>
                      </div>

                      {app.redirected_at && (
                        <div className="text-[11px] text-zinc-600 border-t border-zinc-200/70 pt-2">
                          Last external redirect recorded: <strong dir="ltr">{formatDateShort(app.redirected_at)}</strong> via{" "}
                          <strong>{app.external_platform_name || "External Portal"}</strong>. Clicking redirect does NOT mark
                          your application submitted.
                        </div>
                      )}
                    </div>

                    {/* External Confirmation & Private Evidence Upload Drawer */}
                    {submissionFormOpen[app.id] && (
                      <div className="rounded-xl border border-violet-200 bg-violet-50/50 p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <h3 className="text-xs font-extrabold uppercase tracking-wider text-violet-950">
                            Report External Submission &amp; Upload Private Confirmation Evidence
                          </h3>
                          <span className="text-[11px] font-semibold text-violet-800">
                            Moves to Student-Reported Submitted (Proof stored in Document Vault)
                          </span>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          <div>
                            <label className="block text-[11px] font-bold text-zinc-700 mb-1">
                              External Confirmation Number (optional)
                            </label>
                            <input
                              type="text"
                              dir="ltr"
                              value={confNumByApp[app.id] ?? app.external_confirmation_number ?? ""}
                              onChange={(e) =>
                                setConfNumByApp((prev) => ({ ...prev, [app.id]: e.target.value }))
                              }
                              placeholder="e.g. CA-2027-849210"
                              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900"
                            />
                          </div>

                          <div>
                            <label className="block text-[11px] font-bold text-zinc-700 mb-1">
                              Platform / Portal Used
                            </label>
                            <input
                              type="text"
                              value={submittedViaByApp[app.id] ?? app.external_platform_name ?? ""}
                              onChange={(e) =>
                                setSubmittedViaByApp((prev) => ({ ...prev, [app.id]: e.target.value }))
                              }
                              placeholder="e.g. Common App / UCAS / MyMIT"
                              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900"
                            />
                          </div>

                          <div>
                            <label className="block text-[11px] font-bold text-zinc-700 mb-1">
                              Confirmation Proof Type
                            </label>
                            <select
                              aria-label="Confirmation Proof Type"
                              value={evidenceTypeByApp[app.id] || "portal_screenshot"}
                              onChange={(e) =>
                                setEvidenceTypeByApp((prev) => ({ ...prev, [app.id]: e.target.value }))
                              }
                              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900"
                            >
                              <option value="portal_screenshot">Portal Confirmation Screenshot</option>
                              <option value="confirmation_email">Confirmation Email / Receipt</option>
                              <option value="pdf_receipt">Downloaded Application PDF Receipt</option>
                              <option value="payment_receipt">Application Fee Receipt</option>
                            </select>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div>
                            <label className="block text-[11px] font-bold text-zinc-700 mb-1">
                              Upload Confirmation File to Private Vault (PNG, PDF, TXT)
                            </label>
                            <label className="flex items-center gap-2 rounded-lg border border-dashed border-violet-300 bg-white px-3 py-2 text-xs text-zinc-700 cursor-pointer hover:bg-violet-50/40">
                              <UploadCloud className="h-4 w-4 text-violet-700 shrink-0" />
                              <span className="truncate">
                                {evidenceFileByApp[app.id]?.name || "Choose private confirmation screenshot or PDF..."}
                              </span>
                              <input
                                type="file"
                                className="hidden"
                                onChange={(e) =>
                                  setEvidenceFileByApp((prev) => ({
                                    ...prev,
                                    [app.id]: e.target.files?.[0] || null,
                                  }))
                                }
                              />
                            </label>
                          </div>

                          <div>
                            <label className="block text-[11px] font-bold text-zinc-700 mb-1">Notes</label>
                            <input
                              type="text"
                              value={subNoteByApp[app.id] || ""}
                              onChange={(e) =>
                                setSubNoteByApp((prev) => ({ ...prev, [app.id]: e.target.value }))
                              }
                              placeholder="Optional note on submission date or fee waiver"
                              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900"
                            />
                          </div>
                        </div>

                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => setSubmissionFormOpen((prev) => ({ ...prev, [app.id]: false }))}
                            className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            disabled={Boolean(actionBusy[app.id])}
                            onClick={() => handleReportSubmissionAndEvidence(app)}
                            className="rounded-lg bg-violet-700 px-4 py-1.5 text-xs font-bold text-white hover:bg-violet-800 disabled:opacity-50"
                          >
                            {actionBusy[app.id] ? "Saving..." : "Submit Self-Report & Proof"}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Submitted Evidence Records */}
                    {evidence.length > 0 && (
                      <div className="rounded-xl border border-zinc-200 bg-white p-3.5 space-y-2">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">
                          Document Vault Confirmation Evidence ({evidence.length})
                        </div>
                        {evidence.map((ev) => (
                          <div
                            key={ev.id}
                            className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2 text-xs"
                          >
                            <div>
                              <span className="font-semibold text-zinc-900">
                                {ev.original_filename || ev.evidence_type.replace(/_/g, " ")}
                              </span>
                              {ev.external_confirmation_number && (
                                <span dir="ltr" className="ms-2 font-mono text-[11px] text-zinc-600">
                                  Ref: {ev.external_confirmation_number}
                                </span>
                              )}
                              {ev.reviewer_notes && (
                                <p className="text-[11px] text-zinc-600 mt-0.5">Reviewer note: {ev.reviewer_notes}</p>
                              )}
                            </div>
                            <span
                              className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase shrink-0 ${
                                ev.review_status === "accepted"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : ev.review_status === "rejected"
                                    ? "bg-red-100 text-red-800"
                                    : "bg-amber-100 text-amber-800"
                              }`}
                            >
                              {ev.review_status}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Interactive Checklist Preview */}
                    <div>
                      <div className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-2">
                        Preparation Requirements Checklist ({app.requirements_status.length})
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {app.requirements_status.map((req) => (
                          <div
                            key={req.id}
                            className="flex items-center justify-between gap-2 rounded-lg border border-zinc-200/80 bg-zinc-50/70 px-3 py-2 text-xs"
                          >
                            <div className="min-w-0">
                              <div className="font-semibold text-zinc-900 truncate">{req.title}</div>
                              <div className="text-[11px] text-zinc-500">
                                {req.importance} • {req.category}
                              </div>
                            </div>
                            <select
                              aria-label={`Status for ${req.title}`}
                              value={
                                req.status === "completed" || req.status === "in_progress" ? req.status : "pending"
                              }
                              onChange={async (e) => {
                                const val = e.target.value as "pending" | "in_progress" | "completed";
                                try {
                                  const updated = await updateRequirementItemStatus(app.id, req.id, val);
                                  updateOneApplication(updated);
                                } catch (err) {
                                  setBanner({
                                    type: "error",
                                    text: err instanceof Error ? err.message : "Failed to update requirement",
                                  });
                                }
                              }}
                              className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-[11px] font-semibold text-zinc-800 shrink-0"
                            >
                              <option value="pending">Pending</option>
                              <option value="in_progress">In Progress</option>
                              <option value="completed">Completed</option>
                            </select>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Expandable Status Audit History */}
                    <div className="border-t border-zinc-100 pt-3">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedHistory((prev) => ({ ...prev, [app.id]: !prev[app.id] }))
                        }
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-700 hover:text-zinc-900"
                      >
                        <History className="h-3.5 w-3.5" />
                        {expandedHistory[app.id] ? "Hide Status Audit History" : "View Status Audit History"} (
                        {history.length})
                      </button>

                      {expandedHistory[app.id] && (
                        <div className="mt-2.5 space-y-1.5">
                          {history.map((h) => (
                            <div
                              key={h.id}
                              className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 rounded-lg bg-zinc-50 border border-zinc-200/70 px-3 py-1.5 text-[11px] text-zinc-700"
                            >
                              <div>
                                <span className="font-mono font-bold text-zinc-900">
                                  {h.from_status || "new"} → {h.to_status}
                                </span>{" "}
                                <span className="text-zinc-500">({h.actor_role})</span>
                                {h.reason && <span className="ms-2 text-zinc-700">{h.reason}</span>}
                              </div>
                              <span dir="ltr" className="text-zinc-500 font-mono shrink-0">
                                {formatDateShort(h.changed_at)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* TAB 2: OFFICIAL ROUTING DIRECTORY */}
        {activeTab === "directory" && (
          <div className="mt-6 space-y-5">
            <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
              <div className="lg:col-span-2">
                <label className="block text-[11px] font-bold uppercase tracking-wide text-zinc-500 mb-1">
                  Search Institution or Centralized Platform
                </label>
                <div className="relative">
                  <Search className="h-4 w-4 text-zinc-400 absolute start-3 top-2.5" />
                  <input
                    type="text"
                    value={dirSearch}
                    onChange={(e) => setDirSearch(e.target.value)}
                    placeholder="Common App, UCAS, MIT, Berkeley, Oxford..."
                    className="w-full rounded-lg border border-zinc-300 bg-white ps-9 pe-3 py-2 text-xs text-zinc-900"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wide text-zinc-500 mb-1">
                  Country
                </label>
                <select
                  aria-label="Filter Routing by Country"
                  value={dirCountry}
                  onChange={(e) => setDirCountry(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900"
                >
                  <option value="">All Countries</option>
                  <option value="US">United States (US)</option>
                  <option value="GB">United Kingdom (GB)</option>
                  <option value="CA">Canada (CA)</option>
                  <option value="FR">France (FR)</option>
                  <option value="DE">Germany (DE)</option>
                  <option value="AU">Australia (AU)</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wide text-zinc-500 mb-1">
                  Pathway
                </label>
                <select
                  aria-label="Filter Routing by Pathway"
                  value={dirPathway}
                  onChange={(e) => setDirPathway(e.target.value as "all" | "first_year" | "transfer")}
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900"
                >
                  <option value="all">All Pathways</option>
                  <option value="first_year">First-Year</option>
                  <option value="transfer">Transfer</option>
                </select>
              </div>

              <label className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs font-semibold text-zinc-800 cursor-pointer">
                <input
                  type="checkbox"
                  checked={dirVerifiedOnly}
                  onChange={(e) => setDirVerifiedOnly(e.target.checked)}
                />
                Verified URLs Only
              </label>
            </div>

            {loadingRoutes ? (
              <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center text-sm text-zinc-500">
                Loading official destinations...
              </div>
            ) : routes.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-600">
                No official portals matched your filters. Unverified placeholder links are excluded when &ldquo;Verified URLs
                Only&rdquo; is active.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {routes.map((rt) => (
                  <div
                    key={rt.id}
                    className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-xs flex flex-col justify-between gap-4"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-0.5 text-[10px] font-bold uppercase text-zinc-700">
                          <Globe2 className="h-3 w-3" />
                          <span dir="ltr">{rt.country_code}</span> • {rt.platform_type.replace(/_/g, " ")}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                            rt.verification_status === "verified"
                              ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                              : "bg-amber-50 text-amber-800 border border-amber-200"
                          }`}
                        >
                          {rt.verification_status === "verified" ? (
                            <ShieldCheck className="h-3 w-3" />
                          ) : (
                            <Clock className="h-3 w-3" />
                          )}
                          {rt.verification_status.replace(/_/g, " ")}
                        </span>
                      </div>

                      <h3 className="mt-2.5 text-base font-extrabold text-zinc-900">{rt.platform_name}</h3>
                      <p className="text-xs font-medium text-zinc-600 mt-0.5 flex items-center gap-1.5">
                        <Building2 className="h-3.5 w-3.5 text-zinc-400" />
                        {rt.institution_name || "Centralized Regional Platform"} • Pathway:{" "}
                        <span className="capitalize">{rt.applicant_type.replace(/_/g, " ")}</span>
                      </p>

                      <div
                        dir="ltr"
                        className="mt-2 rounded-lg bg-zinc-50 border border-zinc-200/80 px-2.5 py-1.5 font-mono text-[11px] text-indigo-700 break-all"
                      >
                        {rt.official_url}
                      </div>

                      {rt.international_instructions && (
                        <p className="mt-2.5 text-xs text-zinc-700 leading-relaxed bg-sky-50/60 border border-sky-100 rounded-lg p-2.5">
                          <strong className="text-sky-900">International Guidance:</strong> {rt.international_instructions}
                        </p>
                      )}
                    </div>

                    <div className="pt-3 border-t border-zinc-100 flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-500">
                      <span>
                        Source: <strong className="text-zinc-700">{rt.source_name}</strong> • Verified:{" "}
                        <span dir="ltr">{formatDateShort(rt.verified_at || rt.last_checked_at)}</span>
                      </span>

                      <div className="flex items-center gap-2">
                        {rt.institution_id && (
                          <button
                            type="button"
                            onClick={() =>
                              handleStartWorkspace(
                                rt.institution_id as string,
                                rt.applicant_type === "transfer" ? "transfer" : "first_year",
                                rt.id
                              )
                            }
                            className="inline-flex items-center gap-1 rounded-lg bg-zinc-900 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-zinc-800"
                          >
                            <Send className="h-3 w-3" />
                            Start Workspace
                          </button>
                        )}
                        <a
                          href={rt.official_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1.5 text-[11px] font-bold text-indigo-700 hover:bg-indigo-100"
                        >
                          Official Site <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ApplicationsPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#fafafc] flex items-center justify-center text-sm text-zinc-600">
          Loading Application Routing &amp; Tracker...
        </div>
      }
    >
      <ApplicationsWorkspaceContent />
    </Suspense>
  );
}
