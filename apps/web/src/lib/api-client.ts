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
