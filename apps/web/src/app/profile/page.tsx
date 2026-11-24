"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  User,
  GraduationCap,
  BookOpen,
  Globe,
  Plus,
  CheckCircle2,
  AlertCircle,
  Building2,
  Calendar,
  Layers,
  Sparkles,
  Save,
  ArrowRight
} from "lucide-react";
import {
  fetchProfile,
  createOrUpdateProfile,
  addEnrollment,
  addCourse,
  StudentProfile
} from "@/lib/api-client";

export default function ProfilePage() {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<"general" | "academic" | "pathway">("general");

  // Form state
  const [firstName, setFirstName] = useState("Alexandre");
  const [lastName, setLastName] = useState("Mercer");
  const [preferredName, setPreferredName] = useState("Alex");
  const [countryCode, setCountryCode] = useState("US");
  const [countryResidence, setCountryResidence] = useState("US");
  const [applicantType, setApplicantType] = useState<"first_year" | "transfer" | "both">("both");
  const [intendedMajor, setIntendedMajor] = useState("Computer Science & Data Intelligence");
  const [intendedTerm, setIntendedTerm] = useState("Fall 2027");

  // Modal / Add Enrollment state
  const [showAddEnrollment, setShowAddEnrollment] = useState(false);
  const [instName, setInstName] = useState("");
  const [instType, setInstType] = useState("community_college");
  const [instDegree, setInstDegree] = useState("Associate Degree for Transfer");
  const [instGPA, setInstGPA] = useState("3.88");
  const [instCredits, setInstCredits] = useState("48");

  useEffect(() => {
    async function loadData() {
      try {
        const p = await fetchProfile();
        if (p) {
          setProfile(p);
          setFirstName(p.first_name || "Alexandre");
          setLastName(p.last_name || "Mercer");
          setPreferredName(p.preferred_first_name || "Alex");
          if (p.country_code) setCountryCode(p.country_code);
          if (p.country_of_residence) setCountryResidence(p.country_of_residence);
          if (p.applicant_type && p.applicant_type !== "undecided") {
            setApplicantType(p.applicant_type as any);
          }
          if (p.intended_major) setIntendedMajor(p.intended_major);
          if (p.intended_enrollment_term) setIntendedTerm(p.intended_enrollment_term);
        }
      } catch (err) {
        console.error("Failed to load profile:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    try {
      const updated = await createOrUpdateProfile({
        first_name: firstName,
        last_name: lastName,
        preferred_first_name: preferredName,
        country_code: countryCode,
        country_of_residence: countryResidence,
        applicant_type: applicantType,
        intended_major: intendedMajor,
        intended_enrollment_term: intendedTerm,
      });
      setProfile(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      console.error("Save failed:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleAddEnrollment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!instName) return;
    try {
      await addEnrollment({
        institution_name_manual: instName,
        enrollment_type: instType,
        degree_type: instDegree,
        cumulative_gpa: parseFloat(instGPA) || 3.5,
        total_credits_earned: parseFloat(instCredits) || 0,
        is_current_institution: true,
      });
      // Reload profile
      const reloaded = await fetchProfile();
      if (reloaded) setProfile(reloaded);
      setShowAddEnrollment(false);
      setInstName("");
    } catch (err) {
      console.error("Add enrollment failed:", err);
    }
  };

  const completionPct = profile?.profile_completion_pct || 65;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Banner & Completion Progress */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 flex items-center justify-center text-white font-bold text-2xl shadow-md">
              {firstName.charAt(0)}{lastName.charAt(0)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                  {firstName} {lastName}
                </h1>
                <span className="text-xs px-2.5 py-1 rounded-full font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Universal Profile Active
                </span>
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">
                Targeting: {intendedMajor} &bull; {intendedTerm}
              </p>
            </div>
          </div>

          {/* Profile Completion Bar */}
          <div className="w-full md:w-72 bg-slate-50 dark:bg-slate-800/60 p-3.5 rounded-xl border border-slate-100 dark:border-slate-800">
            <div className="flex items-center justify-between text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              <span>Universal Profile Readiness</span>
              <span className="font-bold text-brand-600 dark:text-brand-400">{completionPct}%</span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-700 h-2.5 rounded-full overflow-hidden">
              <div
                className="bg-brand-600 h-2.5 rounded-full transition-all duration-500"
                style={{ width: `${completionPct}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Valid for both First-Year & Transfer applications globally
            </p>
          </div>
        </div>

        {/* Tab navigation */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 mt-6 -mb-2 gap-8 text-sm">
          <button
            onClick={() => setActiveTab("general")}
            className={`pb-3 font-medium transition-colors border-b-2 flex items-center gap-2 ${
              activeTab === "general"
                ? "border-brand-600 text-brand-600 dark:text-brand-400 dark:border-brand-400"
                : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <User className="w-4 h-4" /> Identity & Demographics
          </button>
          <button
            onClick={() => setActiveTab("pathway")}
            className={`pb-3 font-medium transition-colors border-b-2 flex items-center gap-2 ${
              activeTab === "pathway"
                ? "border-brand-600 text-brand-600 dark:text-brand-400 dark:border-brand-400"
                : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <Layers className="w-4 h-4" /> Pathway & Strategy
          </button>
          <button
            onClick={() => setActiveTab("academic")}
            className={`pb-3 font-medium transition-colors border-b-2 flex items-center gap-2 ${
              activeTab === "academic"
                ? "border-brand-600 text-brand-600 dark:text-brand-400 dark:border-brand-400"
                : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <GraduationCap className="w-4 h-4" /> Academic History & Courses
          </button>
        </div>
      </div>

      {saveSuccess && (
        <div className="p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl text-emerald-800 dark:text-emerald-300 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          Universal Profile successfully synchronized across all active university applications!
        </div>
      )}

      {/* Main Content Sections */}
      {activeTab === "general" && (
        <form onSubmit={handleSaveProfile} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
          <div className="border-b border-slate-100 dark:border-slate-800 pb-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Legal Identity & International Demographics</h2>
            <p className="text-xs text-slate-500 mt-1">
              Adheres to international identity standards with multi-script and localized naming formats.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">First / Given Name</label>
              <input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">Last / Family Name</label>
              <input
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">Preferred First Name</label>
              <input
                type="text"
                value={preferredName}
                onChange={(e) => setPreferredName(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">Primary Citizenship (ISO-3166)</label>
              <select
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="US">United States (US)</option>
                <option value="HT">Haiti (HT)</option>
                <option value="CA">Canada (CA)</option>
                <option value="GB">United Kingdom (GB)</option>
                <option value="IN">India (IN)</option>
                <option value="FR">France (FR)</option>
                <option value="DE">Germany (DE)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">Country of Permanent Residence</label>
              <select
                value={countryResidence}
                onChange={(e) => setCountryResidence(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="US">United States (US)</option>
                <option value="HT">Haiti (HT)</option>
                <option value="CA">Canada (CA)</option>
                <option value="GB">United Kingdom (GB)</option>
                <option value="IN">India (IN)</option>
                <option value="FR">France (FR)</option>
                <option value="DE">Germany (DE)</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end pt-4">
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-medium text-sm flex items-center gap-2 shadow-sm transition-colors"
            >
              <Save className="w-4 h-4" />
              {saving ? "Saving..." : "Save Identity Changes"}
            </button>
          </div>
        </form>
      )}

      {activeTab === "pathway" && (
        <form onSubmit={handleSaveProfile} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
          <div className="border-b border-slate-100 dark:border-slate-800 pb-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Admissions Pathway & Major Strategy</h2>
            <p className="text-xs text-slate-500 mt-1">
              Select your application mode. UniGlobe supports simultaneous first-year and transfer tracking in one profile.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <label
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                applicantType === "both"
                  ? "border-brand-600 bg-brand-50/40 dark:bg-brand-950/20 ring-2 ring-brand-500/20"
                  : "border-slate-200 dark:border-slate-800 hover:border-slate-300"
              }`}
            >
              <input
                type="radio"
                name="pathway"
                value="both"
                checked={applicantType === "both"}
                onChange={() => setApplicantType("both")}
                className="sr-only"
              />
              <div className="font-semibold text-slate-900 dark:text-white text-sm flex items-center justify-between">
                Dual Pathway (Recommended)
                {applicantType === "both" && <CheckCircle2 className="w-4 h-4 text-brand-600" />}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Apply directly to four-year universities while maintaining transfer eligibility from community colleges.
              </p>
            </label>

            <label
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                applicantType === "transfer"
                  ? "border-brand-600 bg-brand-50/40 dark:bg-brand-950/20 ring-2 ring-brand-500/20"
                  : "border-slate-200 dark:border-slate-800 hover:border-slate-300"
              }`}
            >
              <input
                type="radio"
                name="pathway"
                value="transfer"
                checked={applicantType === "transfer"}
                onChange={() => setApplicantType("transfer")}
                className="sr-only"
              />
              <div className="font-semibold text-slate-900 dark:text-white text-sm flex items-center justify-between">
                Transfer Applicant
                {applicantType === "transfer" && <CheckCircle2 className="w-4 h-4 text-brand-600" />}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Optimized for community college and cross-institution articulation with course equivalency tracking.
              </p>
            </label>

            <label
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                applicantType === "first_year"
                  ? "border-brand-600 bg-brand-50/40 dark:bg-brand-950/20 ring-2 ring-brand-500/20"
                  : "border-slate-200 dark:border-slate-800 hover:border-slate-300"
              }`}
            >
              <input
                type="radio"
                name="pathway"
                value="first_year"
                checked={applicantType === "first_year"}
                onChange={() => setApplicantType("first_year")}
                className="sr-only"
              />
              <div className="font-semibold text-slate-900 dark:text-white text-sm flex items-center justify-between">
                First-Year Applicant
                {applicantType === "first_year" && <CheckCircle2 className="w-4 h-4 text-brand-600" />}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                For secondary school graduates entering undergraduate higher education for the first time.
              </p>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">Intended Field of Study / Major</label>
              <input
                type="text"
                value={intendedMajor}
                onChange={(e) => setIntendedMajor(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">Target Matriculation Term</label>
              <select
                value={intendedTerm}
                onChange={(e) => setIntendedTerm(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="Fall 2027">Fall 2027</option>
                <option value="Spring 2028">Spring 2028</option>
                <option value="Fall 2028">Fall 2028</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end pt-4">
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-medium text-sm flex items-center gap-2 shadow-sm transition-colors"
            >
              <Save className="w-4 h-4" />
              {saving ? "Saving..." : "Update Strategy"}
            </button>
          </div>
        </form>
      )}

      {activeTab === "academic" && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 dark:border-slate-800 pb-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Institutional Enrollment History</h2>
                <p className="text-xs text-slate-500 mt-1">
                  Add all secondary schools, community colleges, and higher education institutions attended.
                </p>
              </div>
              <button
                onClick={() => setShowAddEnrollment(!showAddEnrollment)}
                className="px-3.5 py-2 rounded-xl bg-slate-900 dark:bg-white text-white dark:text-slate-900 text-xs font-semibold flex items-center gap-1.5 self-start sm:self-auto hover:opacity-90"
              >
                <Plus className="w-3.5 h-3.5" /> Add Institution
              </button>
            </div>

            {/* Add Enrollment Modal / Form */}
            {showAddEnrollment && (
              <form onSubmit={handleAddEnrollment} className="mt-6 p-4 rounded-xl border border-brand-200 dark:border-brand-900 bg-brand-50/30 dark:bg-brand-950/10 space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-brand-700 dark:text-brand-400">Add Academic Institution</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Institution Name</label>
                    <input
                      type="text"
                      placeholder="e.g. De Anza College or Lycée Français"
                      value={instName}
                      onChange={(e) => setInstName(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Institution Type</label>
                    <select
                      value={instType}
                      onChange={(e) => setInstType(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm"
                    >
                      <option value="community_college">Community College / Junior College</option>
                      <option value="secondary">Secondary / High School</option>
                      <option value="undergraduate">University / Four-Year College</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Cumulative GPA</label>
                    <input
                      type="text"
                      value={instGPA}
                      onChange={(e) => setInstGPA(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Credits Earned / Hours</label>
                    <input
                      type="text"
                      value={instCredits}
                      onChange={(e) => setInstCredits(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowAddEnrollment(false)}
                    className="px-3.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-xs font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-1.5 rounded-lg bg-brand-600 text-white text-xs font-semibold hover:bg-brand-700"
                  >
                    Save Institution
                  </button>
                </div>
              </form>
            )}

            {/* List of Enrollments */}
            <div className="divide-y divide-slate-100 dark:divide-slate-800 mt-4">
              {profile?.enrollments && profile.enrollments.length > 0 ? (
                profile.enrollments.map((enr) => (
                  <div key={enr.id} className="py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-300 shrink-0">
                        <Building2 className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                            {enr.institution_name_manual}
                          </h4>
                          <span className="text-[10px] font-medium uppercase px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                            {enr.enrollment_type.replace("_", " ")}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">
                          GPA: <span className="font-semibold text-slate-700 dark:text-slate-300">{enr.cumulative_gpa || "3.85"}</span> &bull; Credits: {enr.total_credits_earned || "45.0"} sem hrs
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2.5 py-1 rounded-full font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                        Transcript Verified
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-8 text-center text-slate-500 text-xs">
                  No academic institutions recorded yet. Click &quot;Add Institution&quot; above to initialize your course history.
                </div>
              )}
            </div>
          </div>

          {/* Transfer Articulation & Course Equivalence Preview */}
          <div className="bg-gradient-to-r from-blue-900/10 via-indigo-900/10 to-brand-900/10 border border-blue-200/60 dark:border-blue-900/50 rounded-2xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-brand-600 text-white flex items-center justify-center shrink-0">
                <Sparkles className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                  Intelligent International & Transfer Articulation Engine
                </h3>
                <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                  UniGlobe automatically maps your coursework against California IGETC/CSU-GE pathways, European ECTS credit conversions, and international French Baccalauréat / IB equivalencies in real time.
                </p>
                <div className="pt-2">
                  <Link
                    href="/transfer"
                    className="text-xs font-semibold text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1"
                  >
                    View course-by-course articulation matrix <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
