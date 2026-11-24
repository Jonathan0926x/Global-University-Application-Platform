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
  title: string;
  category: "document" | "academic" | "administrative";
  importance: "required" | "optional" | "recommended";
  status: "completed" | "in_progress" | "pending" | "waived";
  notes?: string;
}

export interface ApplicationWorkspace {
  id: string;
  institution_id: string;
  applicant_type: "first_year" | "transfer";
  status: string;
  intended_major?: string;
  intended_term?: string;
  readiness_pct: number;
  institution?: Institution;
  requirements_status: ApplicationRequirement[];
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
  intendedMajor?: string
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
}

export interface CounselorMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  language: string;
  citations: Citation[];
  disclaimer: string;
  created_at: string;
}

export interface CounselorConversation {
  id: string;
  profile_id: string;
  title: string;
  primary_language: string;
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
  conversationId?: string
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


