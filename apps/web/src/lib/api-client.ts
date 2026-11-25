/**
 * Typed API Client for FastAPI Backend Communication
 */

import { auth } from "./auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export interface StudentProfile {
  id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  preferred_first_name?: string;
  name_format: string;
  applicant_type: "first_year" | "transfer" | "both" | "undecided";
  intended_major?: string;
  intended_enrollment_term?: string;
  country_code?: string;
  country_of_residence?: string;
  profile_completion_pct: number;
  enrollments?: Array<{
    id: string;
    institution_name_manual?: string;
    enrollment_type: string;
    cumulative_gpa?: number;
    total_credits_earned?: number;
    courses?: Array<{
      id: string;
      course_name: string;
      course_code?: string;
      grade?: string;
      credit_hours?: number;
    }>;
  }>;
}

export interface Institution {
  id: string;
  official_name: string;
  abbreviation?: string;
  country_code: string;
  state_province?: string;
  city?: string;
  institution_type: string;
  accepts_transfer?: boolean;
  accepts_first_year?: boolean;
}

export interface ApplicationRequirement {
  id: string;
  institution_requirement_id?: string;
  title: string;
  category: "document" | "academic" | "administrative" | "exam" | "financial" | string;
  importance: "required" | "strongly_recommended" | "recommended" | "optional" | "conditional" | "not_accepted" | string;
  status: "completed" | "in_progress" | "pending" | "not_applicable" | "waived" | "needs_verification" | "missing" | string;
  notes?: string;
  satisfied_by_document_id?: string;
  satisfied_by_profile_field?: string;
  auto_matched?: boolean;
  verification_status?: string;
  source_url?: string;
}

export interface ApplicationRouteItem {
  id: string;
  institution_id?: string | null;
  institution_name?: string | null;
  platform_name: string;
  platform_type: string;
  country_code: string;
  applicant_type: string;
  official_url: string;
  international_instructions?: string | null;
  notes?: string | null;
  source_name: string;
  source_url?: string | null;
  verification_status: string;
  confidence_level: string;
  verified_at?: string | null;
  verification_expires_at?: string | null;
  last_health_check_at?: string | null;
  last_health_check_status?: string | null;
  last_health_check_http_code?: number | null;
  pathway_verified?: boolean | null;
  final_redirect_url?: string | null;
  redirect_chain_length?: number | null;
  last_checked_at: string;
  is_active: boolean;
}

export interface InstitutionRoutingResolution {
  institution_id: string;
  institution_name: string;
  applicant_type: string;
  routing_status: "verified_available" | "needs_verification_only" | "no_verified_destination" | string;
  has_verified_destination: boolean;
  verified_routes: ApplicationRouteItem[];
  needs_verification_routes: ApplicationRouteItem[];
  excluded_unverified: Array<{ platform_name: string; reason: string; verification_status: string }>;
  notice?: string | null;
}

export interface DeadlineCountdownItem {
  id: string;
  intake_term: string;
  deadline_type: string;
  deadline_date?: string | null;
  days_remaining?: number | null;
  is_passed: boolean;
  is_urgent: boolean;
  verification_status: string;
  source_name: string;
  source_url?: string | null;
  notes?: string | null;
}

export interface StatusHistoryItem {
  id: string;
  from_status?: string | null;
  to_status: string;
  actor_role: string;
  reason?: string | null;
  metadata_json: Record<string, unknown>;
  changed_at: string;
}

export interface EvidenceReviewAuditItem {
  id: string;
  evidence_id: string;
  application_id: string;
  from_review_status?: string | null;
  to_review_status: string;
  action: string;
  actor_role: string;
  actor_email?: string | null;
  rejection_reason_code?: string | null;
  rejection_reason_label?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface SubmissionEvidenceItem {
  id: string;
  application_id: string;
  document_id?: string | null;
  original_filename?: string | null;
  document_sha256?: string | null;
  evidence_type: string;
  external_confirmation_number?: string | null;
  submitted_note?: string | null;
  review_status: "pending" | "accepted" | "rejected" | string;
  rejection_reason_code?: string | null;
  rejection_reason_label?: string | null;
  reviewer_notes?: string | null;
  submitted_at: string;
  reviewed_at?: string | null;
  audit_history?: EvidenceReviewAuditItem[];
}

export interface RejectionReasonOption {
  code: string;
  label: string;
  description: string;
}

export interface AutomatedSweepStatus {
  enabled: boolean;
  interval_seconds: number;
  last_run_at?: string | null;
  last_expired_checked: number;
  last_flagged: number;
  runs_completed: number;
  last_error?: string | null;
}

export interface RouteHealthSummary {
  total_active_routes: number;
  health_check_status: Record<string, number>;
  verification_expired: number;
  verification_expiring_soon_30d: number;
  pathway_verified: number;
  pathway_assumed: number;
  routes_with_redirect_tracking: number;
  automated_sweep?: AutomatedSweepStatus;
}

export interface RoutingQualitySummary {
  total_routes: number;
  verified: number;
  needs_verification: number;
  unverified: number;
  by_method: Record<string, number>;
  auto_verifiable_candidates: number;
  manual_review_remaining: number;
  manually_reviewed_count?: number;
  health?: RouteHealthSummary;
}

export interface RouteHealthCheckItem {
  route_id: string;
  status: string;
  http_code?: number | null;
  final_redirect_url?: string | null;
  redirect_chain_length?: number | null;
  cross_domain_redirect: boolean;
}

export interface ApplicationRouteAuditItem {
  id: string;
  route_id: string;
  from_status?: string | null;
  to_status: string;
  action: string;
  actor_role: string;
  actor_email?: string | null;
  rejection_reason_code?: string | null;
  notes?: string | null;
  checks_json: Record<string, unknown>;
  created_at: string;
}

export interface RoutingQueueItem extends ApplicationRouteItem {
  verification_method?: string | null;
  verification_notes?: string | null;
  institution_website?: string | null;
  trust_checks: Record<string, unknown> & { warnings?: string[]; auto_verifiable?: boolean };
  audits: ApplicationRouteAuditItem[];
}

export interface EvidenceQueueItem extends SubmissionEvidenceItem {
  institution_id: string;
  institution_name: string;
  applicant_type: string;
  application_status: string;
  student_email?: string | null;
  student_name?: string | null;
  file_size_bytes?: number | null;
  file_type?: string | null;
}

export interface EvidenceVaultPreview {
  document_id: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  file_sha256: string;
  document_category: string;
  extracted_text?: string | null;
  detected_language?: string | null;
  reviewed_by_role: string;
}

export interface ApplicationWorkspace {
  id: string;
  profile_id?: string;
  institution_id: string;
  applicant_type: "first_year" | "transfer";
  status: string;
  intended_major?: string;
  intended_term?: string;
  academic_year?: string;
  readiness_pct: number;
  notes?: string;
  selected_route_id?: string | null;
  external_portal_url?: string | null;
  external_platform_name?: string | null;
  redirected_at?: string | null;
  student_reported_submitted_at?: string | null;
  submission_confirmed_at?: string | null;
  external_confirmation_number?: string | null;
  submitted_via?: string | null;
  created_at?: string;
  updated_at?: string;
  institution?: Institution;
  requirements_status: ApplicationRequirement[];
  status_history?: StatusHistoryItem[];
  submission_evidence?: SubmissionEvidenceItem[];
  verified_routes?: ApplicationRouteItem[];
  needs_verification_routes?: ApplicationRouteItem[];
  routing_notice?: string | null;
  deadlines?: DeadlineCountdownItem[];
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE_URL}/health`);
  return res.json();
}

export async function fetchProfile(): Promise<StudentProfile | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/profile`, {
      headers: { ...auth.getAuthHeader() },
    });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error("Failed to fetch student profile");
    return res.json();
  } catch {
    return null;
  }
}

export async function createOrUpdateProfile(data: Partial<StudentProfile>): Promise<StudentProfile> {
  const existing = await fetchProfile();
  const method = existing ? "PATCH" : "POST";
  const res = await fetch(`${API_BASE_URL}/profile`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to save student profile");
  return res.json();
}

export async function addEnrollment(enrollmentData: {
  institution_name_manual: string;
  institution_country?: string;
  institution_city?: string;
  enrollment_type: string;
  degree_type?: string;
  major?: string;
  cumulative_gpa?: number;
  total_credits_earned?: number;
  is_current_institution?: boolean;
}) {
  const res = await fetch(`${API_BASE_URL}/profile/enrollments`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify(enrollmentData),
  });
  if (!res.ok) throw new Error("Failed to add enrollment record");
  return res.json();
}

export async function addCourse(enrollmentId: string, courseData: {
  course_name: string;
  course_code?: string;
  department?: string;
  credit_hours?: number;
  grade?: string;
  status?: string;
  academic_term?: string;
}) {
  const res = await fetch(`${API_BASE_URL}/profile/enrollments/${enrollmentId}/courses`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify(courseData),
  });
  if (!res.ok) throw new Error("Failed to add course record");
  return res.json();
}


export async function fetchInstitutions(filter?: {
  accepts_transfer?: boolean;
  accepts_first_year?: boolean;
}): Promise<Institution[]> {
  const params = new URLSearchParams();
  if (filter?.accepts_transfer !== undefined) {
    params.append("accepts_transfer", String(filter.accepts_transfer));
  }
  if (filter?.accepts_first_year !== undefined) {
    params.append("accepts_first_year", String(filter.accepts_first_year));
  }
  const res = await fetch(`${API_BASE_URL}/institutions?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch institutions");
  return res.json();
}

export async function fetchApplications(applicantType?: string): Promise<ApplicationWorkspace[]> {
  const url = applicantType
    ? `${API_BASE_URL}/applications?applicant_type=${applicantType}`
    : `${API_BASE_URL}/applications`;
  const res = await fetch(url, {
    headers: { ...auth.getAuthHeader() },
  });
  if (!res.ok) throw new Error("Failed to fetch applications");
  return res.json();
}

export async function createApplication(
  institutionId: string,
  applicantType: "first_year" | "transfer",
  intendedMajor?: string,
  intendedTerm?: string,
  routeId?: string
): Promise<ApplicationWorkspace> {
  const res = await fetch(`${API_BASE_URL}/applications`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify({
      institution_id: institutionId,
      applicant_type: applicantType,
      intended_major: intendedMajor,
      intended_term: intendedTerm,
      route_id: routeId,
    }),
  });
  if (!res.ok) throw new Error("Failed to create application workspace");
  return res.json();
}


export interface Citation {
  title: string;
  url: string;
  institution: string;
  verified_at: string;
  summary?: string;
  source_type?: string;
  epistemic_tier?: "official" | "historical" | "ai_interpretation" | "student_vault" | string;
  retrieval_score?: number;
}

export interface WorkflowSuggestion {
  label: string;
  href: string;
  workflow_type: string;
}

export interface EpistemicBreakdown {
  official_facts?: string[];
  historical_facts?: string[];
  ai_interpretation?: string[];
  missing_or_conflicting?: string[];
  student_context_used?: string[];
  context_institution_id?: string | null;
  context_institution_name?: string | null;
  context_applicant_type?: string | null;
  active_topic?: string | null;
  retrieval_stats?: Record<string, unknown>;
  suggested_workflows?: WorkflowSuggestion[];
}

export interface CounselorMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  language: string;
  citations: Citation[];
  epistemic_breakdown?: EpistemicBreakdown | null;
  disclaimer: string;
  created_at: string;
}

export interface CounselorConversation {
  id: string;
  profile_id: string;
  title: string;
  primary_language: string;
  active_institution_id?: string | null;
  active_applicant_type?: string | null;
  active_topic?: string | null;
  created_at: string;
  updated_at: string;
  messages: CounselorMessage[];
}

export interface DocumentSummary {
  id: string;
  profile_id: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  file_sha256: string;
  detected_language: string;
  document_category: string;
  uploaded_at: string;
  has_extraction: boolean;
  has_translation: boolean;
}

export interface DocumentDetail {
  id: string;
  profile_id: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  file_sha256: string;
  storage_path: string;
  detected_language: string;
  document_category: string;
  uploaded_at: string;
  extraction?: {
    id: string;
    extracted_text: string;
    detected_institution?: string;
    detected_qualification?: string;
    detected_grading_scale?: string;
    extracted_data_json: any;
    extraction_confidence: string;
    extraction_warnings: string[];
    extracted_at: string;
  };
  translations: Array<{
    id: string;
    target_language: string;
    translated_text: string;
    translated_data_json: any;
    translation_engine: string;
    translation_confidence: string;
    translation_disclaimer: string;
    is_human_reviewed: boolean;
    human_reviewer_notes?: string;
    translated_at: string;
  }>;
}

export async function askCounselor(
  message: string,
  language?: string,
  conversationId?: string,
  institutionId?: string,
  applicantType?: string
): Promise<CounselorMessage> {
  const res = await fetch(`${API_BASE_URL}/counselor/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify({
      message,
      language,
      conversation_id: conversationId,
      institution_id: institutionId,
      applicant_type: applicantType,
    }),
  });
  if (!res.ok) throw new Error("Failed to converse with counselor");
  return res.json();
}

export async function fetchCounselorHistory(): Promise<CounselorConversation[]> {
  const res = await fetch(`${API_BASE_URL}/counselor/history`, {
    headers: { ...auth.getAuthHeader() },
  });
  if (!res.ok) return [];
  return res.json();
}

export async function deleteCounselorConversation(conversationId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/counselor/conversations/${conversationId}`, {
    method: "DELETE",
    headers: { ...auth.getAuthHeader() },
  });
  return res.ok;
}

export async function uploadDocument(
  file: File,
  category: string = "transcript"
): Promise<DocumentDetail> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_category", category);

  const res = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: "POST",
    headers: {
      ...auth.getAuthHeader(),
    },
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to upload document");
  return res.json();
}

export async function fetchDocuments(): Promise<DocumentSummary[]> {
  const res = await fetch(`${API_BASE_URL}/documents`, {
    headers: { ...auth.getAuthHeader() },
  });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchDocumentDetail(documentId: string): Promise<DocumentDetail> {
  const res = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
    headers: { ...auth.getAuthHeader() },
  });
  if (!res.ok) throw new Error("Failed to load document details");
  return res.json();
}

export async function translateDocument(
  documentId: string,
  targetLanguage: string = "en-US"
) {
  const res = await fetch(`${API_BASE_URL}/documents/${documentId}/translate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify({ target_language: targetLanguage }),
  });
  if (!res.ok) throw new Error("Failed to translate document");
  return res.json();
}

// ============================================================================
// Phase 3: Global University Intelligence Engine Types & APIs
// ============================================================================

export interface CountryItem {
  code: string;
  name: string;
  name_local?: string;
  region?: string;
  currency_code?: string;
  primary_languages: string[];
  higher_ed_ministry?: string;
  accreditation_body?: string;
}

export interface InstitutionV3 {
  id: string;
  official_name: string;
  alternative_names: string[];
  abbreviation?: string;
  campus_name?: string;
  is_main_campus: boolean;
  parent_institution_id?: string;
  country_code: string;
  state_province?: string;
  city?: string;
  institution_type: string;
  control_type?: string;
  carnegie_classification?: string;
  official_website?: string;
  admissions_website?: string;
  total_enrollment?: number;
  undergraduate_enrollment?: number;
  acceptance_rate?: number;
  tuition_in_state?: number;
  tuition_out_of_state?: number;
  avg_net_price?: number;
  cost_of_attendance?: number;
  currency?: string;
  ipeds_unit_id?: string;
  ope_id?: string;
  ope6_id?: string;
  ror_id?: string;
  openalex_id?: string;
  accepts_transfer: boolean;
  accepts_first_year: boolean;
  accepts_international: boolean;
  data_completeness_score?: number;
  data_reporting_year?: string;
  primary_source?: string;
  is_verified: boolean;
  last_verified_at?: string;
}

export interface AcademicProgramItem {
  id: string;
  program_name: string;
  degree_level: string;
  degree_type?: string;
  cip_code?: string;
  academic_year?: string;
  verification_status?: string;
}

export interface InstitutionCostItem {
  id: string;
  academic_year: string;
  student_type: string;
  degree_level?: string;
  tuition?: number;
  mandatory_fees?: number;
  room_board?: number;
  books_supplies?: number;
  personal_expenses?: number;
  total_estimated_cost?: number;
  currency?: string;
  is_current: boolean;
  source_url?: string;
  verification_status?: string;
}

export interface DataProvenanceItem {
  id: string;
  entity_type: string;
  entity_id: string;
  field_name?: string;
  source_type: string;
  source_url?: string;
  source_name: string;
  collection_method: string;
  retrieved_at: string;
  verified_at?: string;
  academic_year?: string;
  confidence_level: string;
  data_hash?: string;
  previous_value?: Record<string, any>;
  is_current: boolean;
}

export interface InstitutionDetail extends InstitutionV3 {
  postal_code?: string;
  latitude?: number;
  longitude?: number;
  financial_aid_website?: string;
  international_admissions_website?: string;
  net_price_calculator_url?: string;
  application_portal_url?: string;
  accreditation_status?: string;
  accrediting_body?: string;
  open_admissions?: boolean;
  calendar_system?: string;
  undergrad_application_fee?: number;
  graduate_enrollment?: number;
  student_faculty_ratio?: string;
  sat_math_25?: number;
  sat_math_75?: number;
  sat_ebrw_25?: number;
  sat_ebrw_75?: number;
  act_composite_25?: number;
  act_composite_75?: number;
  gpa_25?: number;
  gpa_75?: number;
  completion_rate_4yr?: number;
  completion_rate_less_4yr?: number;
  retention_rate?: number;
  median_earnings_10yr?: number;
  median_debt?: number;
  pct_international?: number;
  pct_pell?: number;
  student_demographics: Record<string, any>;
  ucas_code?: string;
  external_ids: Record<string, any>;
  programs: AcademicProgramItem[];
  costs: InstitutionCostItem[];
  campuses: InstitutionV3[];
  provenance_summary: DataProvenanceItem[];
}

export interface InstitutionSearchResponse {
  items: InstitutionV3[];
  total: number;
  page: number;
  limit: number;
}

export interface InstitutionFilterOptions {
  total_institutions: number;
  us_institutions: number;
  countries: Array<{ code: string; count: number }>;
  us_states: string[];
  institution_types: Array<{ type: string; count: number }>;
}

export async function fetchCountries(): Promise<CountryItem[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/countries`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function fetchInstitutionFilters(): Promise<InstitutionFilterOptions | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/institutions/filters`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function searchInstitutions(params: {
  q?: string;
  country?: string;
  state?: string;
  type?: string;
  control?: string;
  accepts_transfer?: boolean;
  accepts_first_year?: boolean;
  tuition_max?: number;
  enrollment_min?: number;
  sort?: string;
  page?: number;
  limit?: number;
}): Promise<InstitutionSearchResponse> {
  const qs = new URLSearchParams();
  if (params.q) qs.append("q", params.q);
  if (params.country) qs.append("country", params.country);
  if (params.state) qs.append("state", params.state);
  if (params.type) qs.append("type", params.type);
  if (params.control) qs.append("control", params.control);
  if (params.accepts_transfer !== undefined) qs.append("accepts_transfer", String(params.accepts_transfer));
  if (params.accepts_first_year !== undefined) qs.append("accepts_first_year", String(params.accepts_first_year));
  if (params.tuition_max !== undefined) qs.append("tuition_max", String(params.tuition_max));
  if (params.enrollment_min !== undefined) qs.append("enrollment_min", String(params.enrollment_min));
  if (params.sort) qs.append("sort", params.sort);
  qs.append("page", String(params.page || 1));
  qs.append("limit", String(params.limit || 24));

  const res = await fetch(`${API_BASE_URL}/institutions/search?${qs.toString()}`);
  if (!res.ok) throw new Error("Failed to search institutions");
  return res.json();
}

export async function fetchInstitutionDetail(id: string): Promise<InstitutionDetail> {
  const res = await fetch(`${API_BASE_URL}/institutions/${id}`);
  if (!res.ok) throw new Error("Failed to load institution details");
  return res.json();
}

export async function fetchInstitutionProvenance(id: string): Promise<DataProvenanceItem[]> {
  const res = await fetch(`${API_BASE_URL}/institutions/${id}/provenance`);
  if (!res.ok) return [];
  return res.json();
}

// ============================================================================
// Phase 3 Milestone 3: Global Admissions Requirements Intelligence Engine
// ============================================================================

export interface RequirementConditionItem {
  id: string;
  condition_type: string;
  condition_field: string;
  condition_operator: string;
  condition_value: any;
  result_importance: string;
  explanation?: string;
}

export interface InstitutionRequirementItem {
  id: string;
  institution_id: string;
  program_id?: string;
  program_name_filter?: string;
  cip_code?: string;
  applicant_type: string;
  importance: string;
  requirement_type: string;
  requirement_subtype?: string;
  category: string;
  title: string;
  description?: string;
  institution_specific_notes?: string;
  quantity?: number;
  minimum_value?: string;
  maximum_value?: string;
  fee_amount?: number;
  fee_currency?: string;
  fee_waiver_available?: boolean;
  academic_year: string;
  source_name: string;
  source_type: string;
  source_url: string;
  verified_at?: string;
  confidence_level: string;
  verification_status: string;
  conditions: RequirementConditionItem[];
}

export interface DeadlineItem {
  id: string;
  institution_id: string;
  program_name_filter?: string;
  applicant_type: string;
  deadline_type: string;
  intake_term: string;
  deadline_date?: string;
  deadline_time?: string;
  timezone?: string;
  is_firm: boolean;
  notification_date?: string;
  academic_year: string;
  notes?: string;
  days_remaining?: number;
  is_past?: boolean;
  source_name: string;
  source_url: string;
  verified_at?: string;
  verification_status: string;
  confidence_level: string;
}

export interface CountryQualificationItem {
  id: string;
  country_code: string;
  qualification_name: string;
  qualification_type: string;
  grading_scale?: string;
  passing_threshold?: string;
  equivalency_notes?: string;
  recognition_rules: Record<string, any>;
  source_name: string;
  source_url: string;
  verified_at?: string;
  verification_status: string;
}

export interface InstitutionAdmissionsSummary {
  institution_id: string;
  official_name: string;
  country_code: string;
  academic_year: string;
  has_verified_requirements: boolean;
  coverage_notice?: string;
  admissions_website?: string;
  application_portal_url?: string;
  net_price_calculator_url?: string;
  open_admissions?: boolean;
  undergrad_application_fee?: number;
  requirements: InstitutionRequirementItem[];
  deadlines: DeadlineItem[];
  country_qualifications: CountryQualificationItem[];
}

export interface ChecklistItemEvaluation {
  requirement_id: string;
  title: string;
  category: string;
  requirement_type: string;
  program_name_filter?: string;
  original_importance: string;
  effective_importance: string;
  status: string;
  explanation?: string;
  minimum_value?: string;
  maximum_value?: string;
  satisfied_by_document_id?: string;
  satisfied_by_profile_field?: string;
  matched_evidence: string[];
  missing_items: string[];
  auto_matched: boolean;
  source_name: string;
  source_url: string;
  verified_at?: string;
  verification_status: string;
}

export interface DynamicChecklistResponse {
  institution_id: string;
  official_name: string;
  country_code: string;
  applicant_type: string;
  is_international_for_target?: boolean;
  intended_major?: string;
  academic_year: string;
  has_verified_requirements: boolean;
  eligibility_status: string;
  readiness_pct: number;
  summary_notice?: string;
  completed_requirements: ChecklistItemEvaluation[];
  missing_documents: ChecklistItemEvaluation[];
  outstanding_prerequisites: ChecklistItemEvaluation[];
  other_requirements: ChecklistItemEvaluation[];
  not_applicable_requirements: ChecklistItemEvaluation[];
  eligibility_concerns: string[];
  upcoming_deadlines: DeadlineItem[];
  next_actions: string[];
  applicable_qualifications: CountryQualificationItem[];
}

export async function fetchInstitutionRequirements(
  id: string,
  params?: { applicant_type?: string; major?: string; academic_year?: string }
): Promise<InstitutionAdmissionsSummary | null> {
  try {
    const qs = new URLSearchParams();
    if (params?.applicant_type) qs.append("applicant_type", params.applicant_type);
    if (params?.major) qs.append("major", params.major);
    if (params?.academic_year) qs.append("academic_year", params.academic_year);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    const res = await fetch(`${API_BASE_URL}/institutions/${id}/requirements${suffix}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchPersonalizedChecklist(
  id: string,
  params?: { applicant_type?: string; major?: string; academic_year?: string }
): Promise<DynamicChecklistResponse | null> {
  try {
    const qs = new URLSearchParams();
    if (params?.applicant_type) qs.append("applicant_type", params.applicant_type);
    if (params?.major) qs.append("major", params.major);
    if (params?.academic_year) qs.append("academic_year", params.academic_year);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    const res = await fetch(`${API_BASE_URL}/institutions/${id}/checklist${suffix}`, {
      headers: { ...auth.getAuthHeader() },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function refreshApplicationChecklist(applicationId: string): Promise<ApplicationWorkspace | null> {
  const res = await fetch(`${API_BASE_URL}/applications/${applicationId}/refresh-checklist`, {
    method: "POST",
    headers: { ...auth.getAuthHeader() },
  });
  if (!res.ok) return null;
  return res.json();
}

// ============================================================================
// Phase 3 Milestone 4: 3-Tier Transfer Articulation & Credit Intelligence
// ============================================================================

export interface EvaluatedCourseResult {
  student_course_id?: string;
  source_institution_name?: string;
  source_course_code: string;
  source_course_name: string;
  original_credits?: number;
  original_credit_system: string;
  normalized_semester_credits?: number;
  credits_transferable: number;
  equivalency_tier?: number | null;
  tier_label: string;
  equivalency_type: string;
  confidence_score: number;
  target_course_code?: string;
  target_course_name?: string;
  applicability_bucket: string;
  satisfies_major_requirement: boolean;
  satisfies_ge_requirement: boolean;
  ge_category?: string;
  satisfies_prerequisite: boolean;
  elective_only: boolean;
  is_duplicate: boolean;
  requires_syllabus: boolean;
  syllabus_document_id?: string;
  supporting_evidence: string;
  disclaimer: string;
  source_name?: string;
  source_url?: string;
  verified_at?: string;
}

export interface DegreeApplicabilitySummary {
  target_institution_id: string;
  target_institution_name: string;
  intended_major?: string;
  total_courses_evaluated: number;
  officially_verified_count: number;
  historically_observed_count: number;
  ai_predicted_count: number;
  unverified_course_count: number;
  missing_syllabus_count: number;
  duplicate_course_count: number;
  total_original_credits_by_system: Record<string, number>;
  normalized_semester_credits_attempted: number;
  officially_transferable_credits: number;
  potentially_transferable_credits: number;
  unverified_credits: number;
  major_applicable_credits: number;
  ge_applicable_credits: number;
  elective_only_credits: number;
  non_applicable_or_duplicate_credits: number;
  ge_areas_satisfied: string[];
  major_prerequisites_satisfied: string[];
  major_prerequisites_remaining: string[];
  warnings: string[];
  disclaimer: string;
  evaluated_courses: EvaluatedCourseResult[];
}

export async function fetchTransferProfileSummary(
  targetInstitutionId: string,
  intendedMajor?: string
): Promise<DegreeApplicabilitySummary | null> {
  try {
    const qs = new URLSearchParams({ target_institution_id: targetInstitutionId });
    if (intendedMajor) qs.append("intended_major", intendedMajor);
    const res = await fetch(`${API_BASE_URL}/transfer/profile-summary?${qs.toString()}`, {
      headers: { ...auth.getAuthHeader() },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function evaluateCourseEquivalency(payload: {
  source_institution_id?: string;
  source_course_code: string;
  source_course_name: string;
  source_description?: string;
  source_learning_outcomes?: string[];
  source_credits?: number;
  source_credit_system?: string;
  target_institution_id: string;
  intended_major?: string;
}): Promise<EvaluatedCourseResult | null> {
  const res = await fetch(`${API_BASE_URL}/transfer/equivalencies/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function attachSyllabusToCourse(
  courseId: string,
  documentId: string
) {
  const res = await fetch(`${API_BASE_URL}/transfer/courses/${courseId}/attach-syllabus`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify({ document_id: documentId }),
  });
  if (!res.ok) throw new Error("Failed to attach syllabus to course");
  return res.json();
}

// --- Milestone 5: Four-Dimensional Explainable Matching Engine Types & APIs ---

export type FactorStatus =
  | "verified_match"
  | "partial_match"
  | "potential_concern"
  | "insufficient_information"
  | "not_applicable";

export type MatchCategory = "reach" | "target" | "likely" | "insufficient_data";

export interface MatchFactor {
  name: string;
  status: FactorStatus;
  score_impact?: number | null;
  detail: string;
  source_name?: string | null;
  source_url?: string | null;
  verified_at?: string | null;
}

export interface DimensionEvaluation {
  key: "academic" | "financial" | "readiness" | "transfer";
  label: string;
  score: number;
  weight_configured: number;
  weight_applied: number;
  status: FactorStatus;
  summary: string;
  factors: MatchFactor[];
}

export interface InstitutionMatchSummaryInfo {
  id: string;
  official_name: string;
  country_code: string;
  state_province?: string | null;
  city?: string | null;
  institution_type: string;
  control_type?: string | null;
  acceptance_rate?: number | null;
  tuition_in_state?: number | null;
  tuition_out_of_state?: number | null;
  avg_net_price?: number | null;
  cost_of_attendance?: number | null;
  currency?: string | null;
  total_enrollment?: number | null;
  official_website?: string | null;
  admissions_website?: string | null;
  application_portal_url?: string | null;
  primary_source?: string | null;
  last_verified_at?: string | null;
}

export interface UniversityMatchRecommendation {
  id: string;
  institution_id: string;
  institution: InstitutionMatchSummaryInfo;
  applicant_type: string;
  intended_major?: string | null;
  match_category: MatchCategory;
  composite_score: number;
  score_academic: number;
  score_financial: number;
  score_readiness: number;
  score_transfer: number;
  data_confidence_score: number;
  calculation_formula: string;
  dimensions: DimensionEvaluation[];
  positive_factors: string[];
  missing_information: string[];
  unsatisfied_requirements: string[];
  financial_concerns: string[];
  transfer_uncertainties: string[];
  upcoming_deadlines: Array<Record<string, unknown>>;
  sources: Array<Record<string, unknown>>;
  estimated_net_cost?: number | null;
  published_tuition?: number | null;
  estimated_living_expenses?: number | null;
  cost_basis?: string | null;
  cost_is_estimated: boolean;
  is_saved_by_student: boolean;
  is_dismissed: boolean;
  disclaimer: string;
  computed_at: string;
}

export interface MatchingPreferences {
  id: string;
  profile_id: string;
  preferred_countries: string[];
  preferred_states_provinces: string[];
  preferred_institution_types: string[];
  preferred_languages: string[];
  max_annual_budget?: number | null;
  currency: string;
  requires_full_aid: boolean;
  requires_merit_scholarships: boolean;
  weight_academic: number;
  weight_financial: number;
  weight_readiness: number;
  weight_transfer: number;
  updated_at?: string | null;
}

export interface MatchingRunResponse {
  applicant_type: string;
  intended_major?: string | null;
  total_evaluated: number;
  counts_by_category: Record<string, number>;
  weights_used: Record<string, number>;
  recommendations: UniversityMatchRecommendation[];
  disclaimer: string;
}

export async function fetchMatchingPreferences(): Promise<MatchingPreferences | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/matching/preferences`, {
      headers: { ...auth.getAuthHeader() },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function updateMatchingPreferences(
  payload: Partial<Omit<MatchingPreferences, "id" | "profile_id" | "updated_at">>
): Promise<MatchingPreferences> {
  const res = await fetch(`${API_BASE_URL}/matching/preferences`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to save matching preferences");
  return res.json();
}

export async function runMatchingDiscovery(payload: {
  applicant_type?: "first_year" | "transfer";
  intended_major?: string | null;
  countries?: string[];
  states?: string[];
  institution_types?: string[];
  max_annual_budget?: number | null;
  weight_academic?: number;
  weight_financial?: number;
  weight_readiness?: number;
  weight_transfer?: number;
  limit?: number;
  persist?: boolean;
}): Promise<MatchingRunResponse> {
  const res = await fetch(`${API_BASE_URL}/matching/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to run matching discovery");
  return res.json();
}

export async function evaluateInstitutionMatch(
  institutionId: string,
  applicantType?: "first_year" | "transfer",
  intendedMajor?: string
): Promise<UniversityMatchRecommendation | null> {
  const qs = new URLSearchParams();
  if (applicantType) qs.append("applicant_type", applicantType);
  if (intendedMajor) qs.append("intended_major", intendedMajor);
  const res = await fetch(
    `${API_BASE_URL}/matching/evaluate/${institutionId}${qs.toString() ? `?${qs.toString()}` : ""}`,
    {
      method: "POST",
      headers: { ...auth.getAuthHeader() },
    }
  );
  if (!res.ok) return null;
  return res.json();
}

export async function toggleShortlistInstitution(
  institutionId: string,
  saved: boolean
): Promise<{ institution_id: string; is_saved_by_student: boolean }> {
  const res = await fetch(
    `${API_BASE_URL}/matching/recommendations/${institutionId}/save?saved=${saved}`,
    {
      method: "POST",
      headers: { ...auth.getAuthHeader() },
    }
  );
  if (!res.ok) throw new Error("Failed to update shortlist status");
  return res.json();
}

export async function fetchMatchingShortlist(): Promise<UniversityMatchRecommendation[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/matching/shortlist`, {
      headers: { ...auth.getAuthHeader() },
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function compareInstitutions(payload: {
  institution_ids: string[];
  applicant_type?: "first_year" | "transfer";
  intended_major?: string | null;
}): Promise<UniversityMatchRecommendation[]> {
  const res = await fetch(`${API_BASE_URL}/matching/compare`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to compare institutions");
  return res.json();
}

// ============================================================================
// Phase 3 Milestone 7: Official Application Routing & External Confirmation Flow
// ============================================================================

export async function fetchRoutingDirectory(params?: {
  q?: string;
  country?: string;
  applicant_type?: string;
  platform_type?: string;
  verified_only?: boolean;
  limit?: number;
}): Promise<ApplicationRouteItem[]> {
  const qs = new URLSearchParams();
  if (params?.q) qs.append("q", params.q);
  if (params?.country) qs.append("country", params.country);
  if (params?.applicant_type && params.applicant_type !== "all") qs.append("applicant_type", params.applicant_type);
  if (params?.platform_type) qs.append("platform_type", params.platform_type);
  if (params?.verified_only) qs.append("verified_only", "true");
  if (params?.limit) qs.append("limit", String(params.limit));

  const res = await fetch(`${API_BASE_URL}/routing/directory${qs.toString() ? `?${qs.toString()}` : ""}`);
  if (!res.ok) throw new Error("Failed to fetch application routing directory");
  return res.json();
}

export async function fetchInstitutionRouting(
  institutionId: string,
  applicantType: "first_year" | "transfer" = "first_year"
): Promise<InstitutionRoutingResolution | null> {
  const res = await fetch(
    `${API_BASE_URL}/routing/institutions/${institutionId}?applicant_type=${applicantType}`
  );
  if (!res.ok) return null;
  return res.json();
}

export async function updateRequirementItemStatus(
  applicationId: string,
  requirementStatusId: string,
  itemStatus: "pending" | "in_progress" | "completed"
): Promise<ApplicationWorkspace> {
  const res = await fetch(
    `${API_BASE_URL}/applications/${applicationId}/requirements/${requirementStatusId}?item_status=${itemStatus}`,
    {
      method: "POST",
      headers: { ...auth.getAuthHeader() },
    }
  );
  if (!res.ok) throw new Error("Failed to update checklist item");
  return res.json();
}

export async function updateApplicationStatus(
  applicationId: string,
  status: string,
  reason?: string
): Promise<ApplicationWorkspace> {
  const res = await fetch(`${API_BASE_URL}/applications/${applicationId}/status`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify({ status, reason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to update application status");
  }
  return res.json();
}

export async function recordExternalRedirect(
  applicationId: string,
  payload: { route_id?: string; target_url?: string; acknowledge_unverified?: boolean }
): Promise<{
  application: ApplicationWorkspace;
  redirect_url: string;
  verified_route: boolean;
  notice: string;
}> {
  const res = await fetch(`${API_BASE_URL}/applications/${applicationId}/redirect`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to record external portal redirect");
  }
  return res.json();
}

export async function reportExternalSubmission(
  applicationId: string,
  payload: { external_confirmation_number?: string; submitted_via?: string; note?: string }
): Promise<ApplicationWorkspace> {
  const res = await fetch(`${API_BASE_URL}/applications/${applicationId}/report-submission`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...auth.getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to report external submission");
  }
  return res.json();
}

export async function uploadSubmissionEvidence(
  applicationId: string,
  params: {
    file?: File;
    document_id?: string;
    evidence_type?: string;
    external_confirmation_number?: string;
    submitted_note?: string;
  }
): Promise<SubmissionEvidenceItem> {
  const formData = new FormData();
  formData.append("evidence_type", params.evidence_type || "portal_screenshot");
  if (params.external_confirmation_number) {
    formData.append("external_confirmation_number", params.external_confirmation_number);
  }
  if (params.submitted_note) {
    formData.append("submitted_note", params.submitted_note);
  }
  if (params.document_id) {
    formData.append("document_id", params.document_id);
  }
  if (params.file) {
    formData.append("file", params.file);
  }

  const res = await fetch(`${API_BASE_URL}/applications/${applicationId}/evidence`, {
    method: "POST",
    headers: { ...auth.getAuthHeader() },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to upload submission evidence");
  }
  return res.json();
}

export async function deleteApplicationWorkspace(applicationId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/applications/${applicationId}`, {
    method: "DELETE",
    headers: { ...auth.getAuthHeader() },
  });
  if (!res.ok) throw new Error("Failed to remove application workspace");
}

// ============================================================================
// Phase 3 Milestone 7.1: Routing Data Quality & Confirmation Verification Ops
// ============================================================================

async function opsFetch(path: string, init?: RequestInit, authHeaders?: Record<string, string>) {
  const headers = {
    ...(init?.headers || {}),
    ...(authHeaders || auth.getAuthHeader()),
  };
  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const e = new Error(err.detail || `Request failed (${res.status})`) as Error & { status?: number };
    e.status = res.status;
    throw e;
  }
  return res.json();
}

export async function fetchVerificationTaxonomies(
  authHeaders?: Record<string, string>
): Promise<{ evidence_rejection_reasons: RejectionReasonOption[]; route_rejection_reasons: RejectionReasonOption[] }> {
  return opsFetch("/admin/verification/taxonomies", undefined, authHeaders);
}

export async function fetchRoutingQualitySummary(
  authHeaders?: Record<string, string>
): Promise<RoutingQualitySummary> {
  return opsFetch("/admin/routing/summary", undefined, authHeaders);
}

export async function fetchRoutingQueue(
  params?: { verification_status?: string; q?: string; limit?: number },
  authHeaders?: Record<string, string>
): Promise<RoutingQueueItem[]> {
  const qs = new URLSearchParams();
  if (params?.verification_status) qs.append("verification_status", params.verification_status);
  if (params?.q) qs.append("q", params.q);
  if (params?.limit) qs.append("limit", String(params.limit));
  return opsFetch(`/admin/routing/queue${qs.toString() ? `?${qs.toString()}` : ""}`, undefined, authHeaders);
}

export async function runBatchRoutingVerify(
  authHeaders?: Record<string, string>
): Promise<{
  checked: number;
  promoted_to_verified: number;
  kept_needs_verification: number;
  flagged_unverified: number;
  by_method: Record<string, number>;
  summary: RoutingQualitySummary;
}> {
  return opsFetch("/admin/routing/verify-batch", { method: "POST" }, authHeaders);
}

export async function reviewApplicationRoute(
  routeId: string,
  payload: {
    decision: "verified" | "unverified" | "needs_verification";
    rejection_reason_code?: string;
    notes?: string;
    corrected_url?: string;
    international_instructions?: string;
    pathway_verified?: boolean;
    applicant_type?: string;
  },
  authHeaders?: Record<string, string>
): Promise<RoutingQueueItem> {
  return opsFetch(
    `/admin/routing/${routeId}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    authHeaders
  );
}

export async function runRouteHealthCheck(
  routeId: string,
  authHeaders?: Record<string, string>
): Promise<RoutingQueueItem> {
  return opsFetch(`/admin/routing/${routeId}/health-check`, { method: "POST" }, authHeaders);
}

export async function runBatchRouteHealthChecks(
  params?: { limit?: number; only_stale?: boolean },
  authHeaders?: Record<string, string>
): Promise<{
  checked: number;
  by_status: Record<string, number>;
  results: RouteHealthCheckItem[];
  summary: RoutingQualitySummary;
}> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.append("limit", String(params.limit));
  if (params?.only_stale !== undefined) qs.append("only_stale", String(params.only_stale));
  return opsFetch(
    `/admin/routing/health-check${qs.toString() ? `?${qs.toString()}` : ""}`,
    { method: "POST" },
    authHeaders
  );
}

export async function expireStaleRoutes(
  authHeaders?: Record<string, string>
): Promise<{
  expired_checked: number;
  flagged_for_reverification: number;
  summary: RoutingQualitySummary;
}> {
  return opsFetch("/admin/routing/expire-stale", { method: "POST" }, authHeaders);
}

export async function verifyRoutePathway(
  routeId: string,
  payload: {
    pathway_verified: boolean;
    applicant_type?: string;
    notes?: string;
  },
  authHeaders?: Record<string, string>
): Promise<RoutingQueueItem> {
  return opsFetch(
    `/admin/routing/${routeId}/pathway`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    authHeaders
  );
}

export async function fetchEvidenceQueue(
  reviewStatus: string = "pending",
  authHeaders?: Record<string, string>
): Promise<EvidenceQueueItem[]> {
  return opsFetch(`/admin/evidence/queue?review_status=${encodeURIComponent(reviewStatus)}`, undefined, authHeaders);
}

export async function inspectEvidenceDocument(
  evidenceId: string,
  authHeaders?: Record<string, string>
): Promise<EvidenceVaultPreview> {
  return opsFetch(`/admin/evidence/${evidenceId}/document`, undefined, authHeaders);
}

export async function reviewEvidenceItem(
  evidenceId: string,
  payload: {
    decision: "accepted" | "rejected";
    rejection_reason_code?: string;
    reviewer_notes?: string;
  },
  authHeaders?: Record<string, string>
): Promise<EvidenceQueueItem> {
  return opsFetch(
    `/admin/evidence/${evidenceId}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    authHeaders
  );
}





// ---------------------------------------------------------------------------
// Phase 4: Verified Scholarships, Net Price Calculator & Credential Evaluation
// ---------------------------------------------------------------------------
export interface ScholarshipRuleEvaluation {
  dimension: string;
  human_label: string;
  status: string;
  outcome?: string;
  category?: string;
  detail: string;
  is_mandatory: boolean;
}

export interface ScholarshipEligibilityResult {
  id: string;
  institution_id?: string | null;
  institution_name?: string | null;
  country_code: string;
  title: string;
  provider_type: string;
  award_type: string;
  applicant_type: string;
  funding_type: string;
  covers_international: boolean;
  award_amount_min_usd?: number | null;
  award_amount_max_usd?: number | null;
  award_fixed_usd?: number | null;
  award_currency?: string;
  native_amount_min?: number | null;
  native_amount_max?: number | null;
  max_award_info?: string | null;
  eligibility_summary: string;
  covers_tuition: boolean;
  covers_fees: boolean;
  covers_housing: boolean;
  covers_meals: boolean;
  covers_health_insurance: boolean;
  covers_travel?: boolean;
  provides_living_stipend: boolean;
  is_renewable: boolean;
  funding_duration_years?: number | null;
  max_funding_periods?: number | null;
  renewal_conditions?: string | null;
  is_guaranteed_statutory: boolean;
  application_deadline_date?: string | null;
  is_deadline_rolling: boolean;
  min_gpa_4?: number | null;
  requires_financial_need: boolean;
  eligible_citizenships: string[];
  eligible_residency_states: string[];
  eligible_destination_countries: string[];
  degree_levels?: string[];
  eligibility_status:
    | "eligible"
    | "conditionally_eligible"
    | "insufficient_information"
    | "requires_manual_review"
    | "ineligible"
    | string;
  funding_bucket?: string;
  match_score: number;
  rule_evaluations: ScholarshipRuleEvaluation[];
  renewal_evaluations?: ScholarshipRuleEvaluation[];
  missing_requirements: string[];
  conditional_requirements?: string[];
  manual_review_reasons?: string[];
  failed_reasons: string[];
  funding_scope?: string[];
  duration_renewal_summary?: string | null;
  freshness_status?: string;
  application_cycle_status?: string;
  claim_freshness?: Record<string, string>;
  freshness_warnings?: string[];
  verification_expires_at?: string | null;
  sponsoring_institution?: string | null;
  academic_year?: string | null;
  source_name: string;
  source_url: string;
  verified_at: string;
}

export interface ScholarshipMatchResponse {
  evaluated_profile: Record<string, unknown>;
  total_scholarships: number;
  eligible_count: number;
  conditionally_eligible_count: number;
  insufficient_information_count?: number;
  requires_manual_review_count?: number;
  ineligible_count: number;
  aggregation_precedence?: string[];
  results: ScholarshipEligibilityResult[];
  disclaimer: string;
}

export interface CostLineItem {
  key: string;
  label: string;
  category: string;
  amount_usd?: number | null;
  currency?: string;
  is_published: boolean;
  notes?: string | null;
}

export interface CategoryAllocationRow {
  category_key: string;
  label: string;
  cost_group: string;
  original_cost_usd?: number | null;
  applied_verified_min_usd: number;
  applied_verified_max_usd: number;
  applied_conditional_max_usd: number;
  remaining_cost_min_usd?: number | null;
  remaining_cost_max_usd?: number | null;
}

export interface AidOffsetItem {
  scholarship_id: string;
  title: string;
  provider_type: string;
  award_type?: string;
  eligibility_status: string;
  funding_bucket?: string;
  freshness_status?: string;
  is_guaranteed_statutory: boolean;
  award_currency?: string;
  native_amount_min?: number | null;
  native_amount_max?: number | null;
  funding_scope?: string[];
  allocated_categories?: Record<string, number>;
  estimated_min_usd: number;
  estimated_max_usd: number;
  funding_duration_years?: number | null;
  is_renewable?: boolean;
  renewal_conditions?: string | null;
  reason?: string | null;
  source_url: string;
}

export interface NetPriceCalculationResponse {
  institution_id: string;
  institution_name: string;
  country_code: string;
  residency_classification: string;
  housing_preference: string;
  applicant_type: string;
  degree_level?: string;
  academic_year?: string | null;
  currency: string;
  direct_billable_items: CostLineItem[];
  indirect_living_items: CostLineItem[];
  category_breakdown?: CategoryAllocationRow[];
  gross_direct_cost_usd?: number | null;
  gross_indirect_cost_usd?: number | null;
  total_coa_usd?: number | null;
  guaranteed_aid_min_usd: number;
  guaranteed_aid_max_usd: number;
  competitive_aid_min_usd: number;
  competitive_aid_max_usd: number;
  eligible_aid_min_usd: number;
  eligible_aid_max_usd: number;
  estimated_net_price_min_usd?: number | null;
  estimated_net_price_max_usd?: number | null;
  multi_year_net_min_usd?: number | null;
  multi_year_net_max_usd?: number | null;
  annual_budget_usd?: number | null;
  budget_gap_min_usd?: number | null;
  budget_gap_max_usd?: number | null;
  affordability_status: string;
  aid_offsets: AidOffsetItem[];
  verified_applicable_aid?: AidOffsetItem[];
  conditional_aid?: AidOffsetItem[];
  insufficient_info_aid?: AidOffsetItem[];
  review_required_aid?: AidOffsetItem[];
  unallocated_potential_aid?: AidOffsetItem[];
  data_confidence: string;
  warnings: string[];
  sources: Array<{ name?: string | null; url?: string | null }>;
  disclaimer: string;
}

export interface GradingSystemOption {
  source_country_code: string;
  grading_system_key: string;
  scale_name: string;
  academic_level: string;
  is_inverted_scale: boolean;
  methodology: string;
  sample_values: string[];
}

export interface CredentialRecognitionRule {
  id: string;
  source_country_code: string;
  destination_country_code: string;
  source_credential_name: string;
  is_directly_recognized: boolean;
  requires_external_evaluation: boolean;
  accepted_evaluation_agencies: string[];
  requires_official_translation: boolean;
  translation_requirements?: string | null;
  requires_apostille_or_legalization: boolean;
  requires_direct_institutional_dispatch: boolean;
  english_waiver_policy?: string | null;
  pathway_notes: string;
  source_name: string;
  source_url: string;
  verified_at: string;
}

export interface CredentialEvaluationResponse {
  conversion: {
    native_record: {
      country_code: string;
      grading_system_key: string;
      scale_name: string;
      raw_input: string;
      classification: string;
      is_passing?: boolean | null;
      is_inverted_scale: boolean;
      academic_level: string;
    };
    informational_equivalency: {
      us_4_0_point?: number | null;
      us_4_0_low?: number | null;
      us_4_0_high?: number | null;
      us_letter_equivalent: string;
      german_bavarian_equivalent?: number | null;
      methodology: string;
      methodology_citation: string;
      percentile_note?: string | null;
      confidence_level: string;
    };
  };
  recognition_rules: CredentialRecognitionRule[];
  country_qualifications: Array<{
    country_code: string;
    qualification_name: string;
    qualification_type: string;
    grading_scale: string;
    passing_threshold: string;
    equivalency_notes: string;
    source_name: string;
    source_url: string;
  }>;
  advisory_disclaimer: string;
}

export interface ProfileEnrollmentCredentialItem {
  enrollment_id: string;
  institution_name: string;
  institution_country: string;
  enrollment_type: string;
  cumulative_gpa?: number | null;
  gpa_scale?: number | null;
  inferred_system_key: string;
  evaluation: CredentialEvaluationResponse;
}

export interface ProfileCredentialEvaluationResponse {
  has_profile: boolean;
  destination_country_code: string;
  enrollments_evaluated: ProfileEnrollmentCredentialItem[];
  advisory_disclaimer: string;
}

export async function matchScholarships(payload: {
  citizenship_country?: string;
  country_of_residence?: string;
  dual_citizenship?: boolean;
  residency_state?: string;
  applicant_type?: string;
  degree_level?: string;
  gpa_4?: number;
  financial_need_level?: string;
  household_income_usd?: number;
  destination_country?: string;
  institution_id?: string;
  include_ineligible?: boolean;
}): Promise<ScholarshipMatchResponse> {
  const res = await fetch(`${API_BASE_URL}/financial/scholarships/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth.getAuthHeader() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to evaluate scholarship eligibility");
  return res.json();
}

export async function calculateNetPrice(payload: {
  institution_id: string;
  residency_classification: string;
  housing_preference: string;
  applicant_type: string;
  degree_level?: string;
  citizenship_country?: string;
  country_of_residence?: string;
  residency_state?: string;
  gpa_4?: number;
  financial_need_level?: string;
  household_income_usd?: number;
  annual_budget_usd?: number;
  program_years?: number;
  include_competitive_aid?: boolean;
}): Promise<NetPriceCalculationResponse> {
  const res = await fetch(`${API_BASE_URL}/financial/net-price`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth.getAuthHeader() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to calculate institutional net price");
  return res.json();
}

export async function fetchGradingSystems(): Promise<GradingSystemOption[]> {
  const res = await fetch(`${API_BASE_URL}/credentials/systems`);
  if (!res.ok) throw new Error("Failed to fetch international grading systems");
  return res.json();
}

export async function evaluateInternationalCredential(payload: {
  source_country_code: string;
  grading_system_key: string;
  raw_grade: string;
  destination_country_code: string;
  academic_level?: string;
}): Promise<CredentialEvaluationResponse> {
  const res = await fetch(`${API_BASE_URL}/credentials/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to evaluate international credential");
  return res.json();
}

export async function evaluateProfileCredentials(
  destinationCountry = "US"
): Promise<ProfileCredentialEvaluationResponse> {
  const res = await fetch(
    `${API_BASE_URL}/credentials/profile-evaluate?destination_country=${encodeURIComponent(destinationCountry)}`,
    { headers: { ...auth.getAuthHeader() } }
  );
  if (!res.ok) throw new Error("Failed to evaluate student profile credentials");
  return res.json();
}
