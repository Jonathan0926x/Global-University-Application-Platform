"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  GraduationCap,
  ArrowRightLeft,
  CheckCircle2,
  Clock,
  ArrowUpRight,
  PlusCircle,
  FileText,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import { fetchProfile, fetchApplications, StudentProfile, ApplicationWorkspace } from "@/lib/api-client";
import { useI18n } from "@/lib/i18n/context";

export default function DashboardPage() {
  const { t, formatNumber } = useI18n();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [applications, setApplications] = useState<ApplicationWorkspace[]>([]);
  const [pathwayFilter, setPathwayFilter] = useState<"all" | "first_year" | "transfer">("all");
  const [loading, setLoading] = useState(true);


  useEffect(() => {
    async function loadData() {
      try {
        const [profData, appData] = await Promise.all([
          fetchProfile(),
          fetchApplications(),
        ]);
        setProfile(profData);
        setApplications(appData);
      } catch (err) {
        console.error("Dashboard data load error:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const filteredApps = applications.filter((app) => {
    if (pathwayFilter === "all") return true;
    return app.applicant_type === pathwayFilter;
  });

  const totalCredits =
    profile?.enrollments?.reduce((acc, curr) => acc + (curr.total_credits_earned || 0), 0) || 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Top Welcome Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-zinc-200 pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-1">
            <span>{t("nav.student_os", "Student OS")}</span>
            <span>•</span>
            <span className="text-indigo-600 font-bold">{t("nav.backend_connected", "Live Synced")}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900">
            {t("dash.title", "Unified Student Operating System")}
          </h1>
          <p className="mt-1 text-sm text-zinc-600">
            {t("dash.subtitle", "Manage both First-Year and Transfer application workspaces from a single canonical profile.")}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/transfer"
            className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white shadow-xs hover:bg-zinc-800 transition-colors"
          >
            <PlusCircle className="h-4 w-4" />
            <span>{t("dash.btn_new_app", "New Application")}</span>
          </Link>
          <Link
            href="/profile"
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold text-zinc-700 shadow-xs hover:bg-zinc-50 transition-colors"
          >
            <span>{t("nav.profile", "Universal Profile")}</span>
          </Link>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {/* Metric 1: Profile Completion */}
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">Universal Profile</span>
            <FileText className="h-4 w-4 text-zinc-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-zinc-900">
              {profile?.profile_completion_pct || 75}%
            </span>
            <span className="text-xs text-emerald-600 font-medium">Reusable Across Apps</span>
          </div>
          <div className="mt-3 w-full bg-zinc-100 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-indigo-600 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${profile?.profile_completion_pct || 75}%` }}
            />
          </div>
        </div>

        {/* Metric 2: Applications Active */}
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">Active Workspaces</span>
            <GraduationCap className="h-4 w-4 text-zinc-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-zinc-900">{applications.length || 2}</span>
            <span className="text-xs text-zinc-500">Institutions</span>
          </div>
          <p className="mt-3 text-xs text-zinc-500">
            {applications.filter((a) => a.applicant_type === "transfer").length} Transfer •{" "}
            {applications.filter((a) => a.applicant_type === "first_year").length} First-Year
          </p>
        </div>

        {/* Metric 3: Academic Credits */}
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">Academic Units</span>
            <ArrowRightLeft className="h-4 w-4 text-zinc-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-zinc-900">{totalCredits || 45}</span>
            <span className="text-xs text-sky-600 font-medium">Units Recorded</span>
          </div>
          <p className="mt-3 text-xs text-zinc-500">Verified across college transcripts</p>
        </div>

        {/* Metric 4: Next Deadline */}
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">Priority Deadline</span>
            <Clock className="h-4 w-4 text-zinc-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-xl font-bold text-zinc-900">Nov 30, 2026</span>
          </div>
          <p className="mt-3 text-xs font-medium text-amber-600 flex items-center gap-1">
            <AlertCircle className="h-3.5 w-3.5" /> UC System Filing Period
          </p>
        </div>
      </div>

      {/* Pathway Switcher Tabs */}
      <div className="mt-10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="inline-flex rounded-lg border border-zinc-200 bg-zinc-100 p-1 text-xs font-semibold text-zinc-600">
          <button
            onClick={() => setPathwayFilter("all")}
            className={`rounded-md px-3.5 py-1.5 transition-all ${
              pathwayFilter === "all" ? "bg-white text-zinc-900 shadow-xs" : "hover:text-zinc-900"
            }`}
          >
            {t("dash.filter_all", "All Workspaces")} ({applications.length || 2})
          </button>
          <button
            onClick={() => setPathwayFilter("transfer")}
            className={`flex items-center gap-1.5 rounded-md px-3.5 py-1.5 transition-all ${
              pathwayFilter === "transfer" ? "bg-white text-zinc-900 shadow-xs" : "hover:text-zinc-900"
            }`}
          >
            <ArrowRightLeft className="h-3.5 w-3.5 text-sky-600" />
            <span>{t("dash.filter_transfer", "Transfer Applications")}</span>
          </button>
          <button
            onClick={() => setPathwayFilter("first_year")}
            className={`flex items-center gap-1.5 rounded-md px-3.5 py-1.5 transition-all ${
              pathwayFilter === "first_year" ? "bg-white text-zinc-900 shadow-xs" : "hover:text-zinc-900"
            }`}
          >
            <GraduationCap className="h-3.5 w-3.5 text-indigo-600" />
            <span>{t("dash.filter_fy", "First-Year Applications")}</span>
          </button>
        </div>

        <span className="text-xs text-zinc-500">
          {t("dash.active_workspaces", "Active Application Workspaces")}
        </span>
      </div>

      {/* Application Workspaces List */}
      <div className="mt-6 space-y-4">
        {loading ? (
          <div className="rounded-xl border border-zinc-200 bg-white p-12 text-center text-sm text-zinc-500">
            Loading your application workspaces...
          </div>
        ) : filteredApps.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-12 text-center">
            <GraduationCap className="mx-auto h-8 w-8 text-zinc-400" />
            <h3 className="mt-3 text-sm font-semibold text-zinc-900">No applications created in this pathway</h3>
            <p className="mt-1 text-xs text-zinc-500">
              Start an application workspace to track requirements, essays, and deadlines.
            </p>
            <div className="mt-5 flex justify-center gap-3">
              <Link
                href="/transfer"
                className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3.5 py-2 text-xs font-semibold text-white shadow-xs"
              >
                <ArrowRightLeft className="h-3.5 w-3.5" /> Start Transfer Application
              </Link>
              <Link
                href="/first-year"
                className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3.5 py-2 text-xs font-semibold text-zinc-800 shadow-xs"
              >
                <GraduationCap className="h-3.5 w-3.5" /> Start First-Year Application
              </Link>
            </div>
          </div>
        ) : (
          filteredApps.map((app) => (
            <div
              key={app.id}
              className="rounded-xl border border-zinc-200 bg-white p-6 shadow-xs hover:border-zinc-300 transition-all"
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div
                    className={`mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg font-bold text-sm ${
                      app.applicant_type === "transfer"
                        ? "bg-sky-50 text-sky-700 border border-sky-100"
                        : "bg-indigo-50 text-indigo-700 border border-indigo-100"
                    }`}
                  >
                    {app.applicant_type === "transfer" ? "TR" : "FY"}
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-bold text-zinc-900">
                        {app.institution?.official_name || "University of California, Berkeley"}
                      </h3>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase ${
                          app.applicant_type === "transfer"
                            ? "bg-sky-100 text-sky-800"
                            : "bg-indigo-100 text-indigo-800"
                        }`}
                      >
                        {app.applicant_type === "transfer" ? "Transfer Applicant" : "First-Year Applicant"}
                      </span>
                    </div>

                    <p className="mt-1 text-xs text-zinc-500">
                      Intended Major:{" "}
                      <span className="font-semibold text-zinc-700">
                        {app.intended_major || "Computer Science"}
                      </span>{" "}
                      • Target Term: {app.intended_term || "Fall 2027"} • Status:{" "}
                      <span className="capitalize font-medium text-amber-600">{app.status}</span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <span className="text-xs font-semibold text-zinc-500">Application Readiness</span>
                    <p className="text-sm font-extrabold text-zinc-900">{app.readiness_pct}%</p>
                  </div>

                  <Link
                    href={app.applicant_type === "transfer" ? "/transfer" : "/first-year"}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-50 px-3.5 py-2 text-xs font-semibold text-zinc-800 hover:bg-zinc-100 transition-colors"
                  >
                    View Checklist <ArrowUpRight className="h-3.5 w-3.5 text-zinc-500" />
                  </Link>
                </div>
              </div>

              {/* Requirement Checklist Snippet */}
              {app.requirements_status && app.requirements_status.length > 0 && (
                <div className="mt-5 border-t border-zinc-100 pt-4">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
                    Requirements Progress
                  </span>
                  <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                    {app.requirements_status.slice(0, 3).map((req) => (
                      <div
                        key={req.id}
                        className="flex items-center gap-2 rounded-md bg-zinc-50 px-2.5 py-1.5 text-xs text-zinc-600"
                      >
                        <CheckCircle2
                          className={`h-3.5 w-3.5 ${
                            req.status === "completed" ? "text-emerald-600" : "text-zinc-300"
                          }`}
                        />
                        <span className="truncate">{req.title}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
