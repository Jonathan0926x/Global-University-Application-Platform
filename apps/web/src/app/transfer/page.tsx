"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRightLeft,
  CheckCircle2,
  AlertCircle,
  FileText,
  Building2,
  Plus,
  BookOpen,
  Send,
  Sparkles,
} from "lucide-react";
import {
  fetchInstitutions,
  fetchApplications,
  createApplication,
  Institution,
  ApplicationWorkspace,
} from "@/lib/api-client";

export default function TransferPortalPage() {
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [applications, setApplications] = useState<ApplicationWorkspace[]>([]);
  const [selectedInstId, setSelectedInstId] = useState<string>("");
  const [major, setMajor] = useState("Computer Science");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        const [instList, appList] = await Promise.all([
          fetchInstitutions({ accepts_transfer: true }),
          fetchApplications("transfer"),
        ]);
        setInstitutions(instList);
        setApplications(appList);
        if (instList.length > 0) {
          setSelectedInstId(instList[0].id);
        }
      } catch (err) {
        console.error("Error loading transfer data:", err);
      }
    }
    loadData();
  }, []);

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInstId) return;
    setSubmitting(true);
    try {
      const newApp = await createApplication(selectedInstId, "transfer", major);
      setApplications([newApp, ...applications]);
    } catch (err) {
      console.error("Failed to create workspace:", err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Transfer Header Banner */}
      <div className="rounded-2xl border border-sky-100 bg-gradient-to-r from-sky-50 via-white to-indigo-50 p-6 sm:p-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-md bg-sky-100/80 px-2.5 py-1 text-xs font-semibold text-sky-800 mb-3">
              <ArrowRightLeft className="h-4 w-4" /> Dedicated Transfer Admissions Intelligence
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-zinc-900 tracking-tight">
              Transfer Application Portal
            </h1>
            <p className="mt-2 text-sm text-zinc-600 max-w-2xl">
              Transferring from a community college, a 4-year university, or an international institution? Built with a specialized architecture for college transcript evaluation, course articulation, and 60-unit prerequisite milestones.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <Link
              href="/profile"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-white border border-zinc-200 px-4 py-2.5 text-xs font-semibold text-zinc-800 shadow-xs hover:bg-zinc-50"
            >
              <BookOpen className="h-4 w-4 text-sky-600" />
              Manage Coursework & Credits
            </Link>
          </div>
        </div>
      </div>

      <div className="mt-10 grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Create New Transfer Workspace */}
        <div className="lg:col-span-1">
          <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-xs sticky top-24">
            <h2 className="text-base font-bold text-zinc-900 flex items-center gap-2">
              <Plus className="h-4 w-4 text-sky-600" />
              Add Transfer Target Destination
            </h2>
            <p className="mt-1 text-xs text-zinc-500">
              Initializes a transfer workspace with course articulation audits.
            </p>

            <form onSubmit={handleCreateWorkspace} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Target Destination University
                </label>
                <select
                  value={selectedInstId}
                  onChange={(e) => setSelectedInstId(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-800 focus:border-sky-600 focus:outline-hidden"
                >
                  {institutions.map((inst) => (
                    <option key={inst.id} value={inst.id}>
                      {inst.official_name} ({inst.state_province})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Intended Major
                </label>
                <input
                  type="text"
                  value={major}
                  onChange={(e) => setMajor(e.target.value)}
                  placeholder="e.g. Computer Science"
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-800 focus:border-sky-600 focus:outline-hidden"
                />
              </div>

              <div className="rounded-lg bg-sky-50/60 p-3 text-[11px] text-sky-800 border border-sky-100 flex items-start gap-2">
                <Sparkles className="h-4 w-4 shrink-0 text-sky-600 mt-0.5" />
                <span>
                  The Transfer Intelligence Engine will automatically compare your completed units against the receiving institution's degree requirements.
                </span>
              </div>

              <button
                type="submit"
                disabled={submitting || !selectedInstId}
                className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-zinc-800 disabled:opacity-50 transition-colors"
              >
                {submitting ? "Initializing..." : "Create Transfer Workspace"}
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Transfer Workspaces & Checklists */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-zinc-900">
              Active Transfer Workspaces ({applications.length})
            </h2>
            <span className="text-xs text-zinc-500">Auto-evaluates credit mobility</span>
          </div>

          {applications.length === 0 ? (
            <div className="rounded-xl border border-dashed border-zinc-300 bg-white p-10 text-center">
              <ArrowRightLeft className="mx-auto h-8 w-8 text-zinc-400" />
              <p className="mt-2 text-sm font-semibold text-zinc-700">No transfer workspaces active.</p>
              <p className="text-xs text-zinc-500">Add a destination university on the left to start evaluating your transfer credits.</p>
            </div>
          ) : (
            applications.map((app) => (
              <div
                key={app.id}
                className="rounded-xl border border-zinc-200 bg-white p-6 shadow-xs"
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-zinc-100 pb-4 gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-md bg-sky-50 border border-sky-100 px-2 py-0.5 text-[10px] font-bold text-sky-700 uppercase">
                        Transfer Pathway
                      </span>
                      <h3 className="text-base font-bold text-zinc-900">
                        {app.institution?.official_name || "Target Institution"}
                      </h3>
                    </div>
                    <p className="mt-1 text-xs text-zinc-500">
                      Major: <span className="font-semibold text-zinc-700">{app.intended_major}</span> • Target: {app.intended_term || "Fall 2027"}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-zinc-500">Transfer Readiness:</span>
                    <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-extrabold text-emerald-700 border border-emerald-200">
                      {app.readiness_pct}%
                    </span>
                  </div>
                </div>

                {/* Transfer Requirement Checklist */}
                <div className="mt-4">
                  <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                    Transfer Admission Requirements
                  </span>
                  <div className="mt-3 space-y-2.5">
                    {app.requirements_status.map((req) => (
                      <div
                        key={req.id}
                        className="flex items-center justify-between rounded-lg border border-zinc-100 bg-zinc-50/60 p-3 text-xs"
                      >
                        <div className="flex items-center gap-2.5">
                          <CheckCircle2
                            className={`h-4 w-4 ${
                              req.status === "completed" ? "text-emerald-600" : "text-zinc-300"
                            }`}
                          />
                          <div>
                            <span className="font-semibold text-zinc-900">{req.title}</span>
                            <span className="ml-2 rounded-full bg-zinc-200 px-1.5 py-0.2 text-[9px] font-medium text-zinc-700 uppercase">
                              {req.importance}
                            </span>
                          </div>
                        </div>

                        <span className="font-medium capitalize text-zinc-500 text-[11px]">
                          {req.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Course Articulation Advisory */}
                <div className="mt-5 rounded-lg bg-sky-50/50 border border-sky-100 p-3 text-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div className="flex items-center gap-2 text-sky-900">
                    <Building2 className="h-4 w-4 text-sky-600 shrink-0" />
                    <span>Official Articulation Data: Verified against ASSIST.org agreements</span>
                  </div>
                  <a
                    href="https://assist.org"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-semibold text-sky-700 hover:text-sky-800 text-[11px]"
                  >
                    Check ASSIST.org <Send className="h-3 w-3" />
                  </a>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
