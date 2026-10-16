export interface JobPostingListItem {
  id: string;
  company_name: string;
  position_title: string;
  location_text: string | null;
  remote_mode: string;
  source_name: string;
  workflow_status: string;
  match_score: number | null;
  has_cv: boolean;
  applied: boolean;
  applied_at: string | null;
  created_at: string;
}

export interface JobPostingDetail {
  id: string;
  source_type: string;
  source_name: string;
  source_url: string | null;
  company_name: string;
  position_title: string;
  location_text: string | null;
  remote_mode: string;
  employment_types: string[];
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  description_raw_text: string;
  description_clean_text: string;
  requirements: unknown[];
  responsibilities: unknown[];
  nice_to_have: unknown[];
  technologies: string[];
  benefits: unknown[];
  workflow_status: string;
  match_score: number | null;
  match_summary: string | null;
  created_at: string;
  updated_at: string;
  sources: JobSource[];
  applications: Application[];
}

export interface JobImportTextRequest {
  raw_text: string;
  source_url?: string;
  company_name: string;
  position_title: string;
  location_text?: string;
  remote_mode: string;
  technologies: string[];
  allow_duplicate: boolean;
}

export interface DuplicateInfo {
  job_posting_id: string;
  match_level: "exact" | "likely";
  company_name: string;
  position_title: string;
}

export interface JobImportUrlRequest {
  url: string;
}

export interface JobImportHtmlRequest {
  html: string;
  source_url: string;
}

export interface JobImportUrlPreviewResponse {
  extraction_method: "json_ld" | "manual";
  canonical_url: string;
  source_name: string;
  staging_token: string;
  company_name: string;
  position_title: string;
  location_text: string | null;
  remote_mode: string;
  employment_types: string[];
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  salary_period: string | null;
  description_raw_text: string;
  description_clean_text: string;
  published_at: string | null;
  expires_at: string | null;
  external_job_id: string | null;
  technologies: string[];
  duplicate: DuplicateInfo | null;
}

export interface JobImportListingRequest {
  listing_url: string;
}

export interface BulkImportItem {
  url: string;
  status: "imported" | "duplicate" | "skipped_no_structured_data" | "failed";
  job_posting_id: string | null;
  company_name: string | null;
  position_title: string | null;
  reason: string | null;
}

export interface BulkImportReport {
  listing_url: string;
  discovered_count: number;
  imported_count: number;
  duplicate_count: number;
  items: BulkImportItem[];
}

export interface AttachSourceRequest {
  canonical_url: string;
  staging_token: string;
  source_name: string;
  external_job_id: string | null;
}

export interface JobSource {
  id: string;
  source_name: string;
  original_url: string | null;
  canonical_url: string | null;
  fetch_method: string;
  fetched_at: string;
}

export interface JobImportUrlConfirmRequest {
  canonical_url: string;
  staging_token: string;
  external_job_id: string | null;
  company_name: string;
  position_title: string;
  location_text: string;
  remote_mode: string;
  employment_types: string[];
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  salary_period: string | null;
  description_raw_text: string;
  description_clean_text: string;
  published_at: string | null;
  expires_at: string | null;
  technologies: string[];
  allow_duplicate: boolean;
}

export type CvGenerationStatus =
  | "queued"
  | "analyzing"
  | "matching"
  | "drafting"
  | "fact_checking"
  | "ats_checking"
  | "style"
  | "writing_latex"
  | "compiling"
  | "validating"
  | "succeeded"
  | "failed";

export interface CvGeneration {
  id: string;
  job_posting_id: string;
  version_number: number;
  language: string;
  target_pages: number;
  status: CvGenerationStatus;
  pdf_page_count: number | null;
  fact_check_status: string;
  error_stage: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  has_pdf: boolean;
  has_tex: boolean;
  model_provider: string | null;
  model_name: string | null;
  total_cost_usd: number | null;
  total_input_tokens: number | null;
  total_output_tokens: number | null;
}

export type CoverLetterStatus = "drafting" | "ai_check" | "succeeded" | "failed";

export interface CoverLetter {
  id: string;
  job_posting_id: string;
  version_number: number;
  language: string;
  status: CoverLetterStatus;
  content_text: string | null;
  word_count: number | null;
  sounds_ai_flagged: boolean;
  ai_check_notes: string | null;
  pdf_path: string | null;
  latex_path: string | null;
  has_pdf: boolean;
  has_tex: boolean;
  error_stage: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  total_cost_usd: number;
}

export type GenerationEventStatus = "running" | "succeeded" | "failed" | "skipped";

export interface GenerationEvent {
  id: string;
  stage: string;
  status: GenerationEventStatus;
  message: string | null;
  started_at: string;
  completed_at: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  model: string | null;
}

export interface UsageBreakdownItem {
  key: string;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  calls: number;
}

export interface UsageDayItem {
  date: string;
  cost_usd: number;
  calls: number;
}

export interface UsageSummary {
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_calls: number;
  failed_calls: number;
  by_stage: UsageBreakdownItem[];
  by_model: UsageBreakdownItem[];
  by_day: UsageDayItem[];
}

export interface Application {
  id: string;
  job_posting_id: string;
  cv_generation_id: string | null;
  applied_at: string;
  channel: string;
  status: string;
  notes: string | null;
}

export interface MarkAppliedRequest {
  cv_generation_id?: string | null;
  applied_at: string;
  channel: string;
  notes?: string;
}

export type ApplicationStatus =
  | "applied"
  | "responded"
  | "hr_interview"
  | "technical_interview"
  | "offer"
  | "rejected"
  | "withdrawn";

export interface ApplicationStatusUpdateRequest {
  status: ApplicationStatus;
  notes?: string;
}
