import { apiClient } from "./client";
import type {
  Application,
  ApplicationStatusUpdateRequest,
  AttachSourceRequest,
  BulkImportReport,
  CoverLetter,
  CvGeneration,
  GenerationEvent,
  JobImportHtmlRequest,
  JobImportListingRequest,
  JobImportTextRequest,
  JobImportUrlConfirmRequest,
  JobImportUrlPreviewResponse,
  JobPostingDetail,
  JobPostingListItem,
  JobSource,
  MarkAppliedRequest,
  UsageSummary,
} from "../types/job";

export const jobsApi = {
  list: (status?: string) =>
    apiClient.get<JobPostingListItem[]>(`/jobs${status ? `?status_filter=${status}` : ""}`),
  get: (jobId: string) => apiClient.get<JobPostingDetail>(`/jobs/${jobId}`),
  importText: (payload: JobImportTextRequest) =>
    apiClient.post<JobPostingDetail>("/jobs/import-text", payload),
  previewUrl: (url: string) =>
    apiClient.post<JobImportUrlPreviewResponse>("/jobs/import-url", { url }),
  previewHtml: (payload: JobImportHtmlRequest) =>
    apiClient.post<JobImportUrlPreviewResponse>("/jobs/import-html", payload),
  confirmUrl: (payload: JobImportUrlConfirmRequest) =>
    apiClient.post<JobPostingDetail>("/jobs/import-url/confirm", payload),
  importListing: (payload: JobImportListingRequest) =>
    apiClient.post<BulkImportReport>("/jobs/import-listing", payload),
  attachSource: (jobId: string, payload: AttachSourceRequest) =>
    apiClient.post<JobSource>(`/jobs/${jobId}/sources`, payload),
  archive: (jobId: string) => apiClient.post<JobPostingDetail>(`/jobs/${jobId}/archive`),
  delete: (jobId: string) => apiClient.delete<void>(`/jobs/${jobId}`),
  listCvGenerations: (jobId: string) =>
    apiClient.get<CvGeneration[]>(`/jobs/${jobId}/cv-generations`),
  generateCv: (jobId: string) =>
    apiClient.post<CvGeneration>(`/jobs/${jobId}/cv-generations`, {}),
  listCoverLetters: (jobId: string) =>
    apiClient.get<CoverLetter[]>(`/jobs/${jobId}/cover-letters`),
  generateCoverLetter: (jobId: string) =>
    apiClient.post<CoverLetter>(`/jobs/${jobId}/cover-letters`, {}),
  markApplied: (jobId: string, payload: MarkAppliedRequest) =>
    apiClient.post<Application>(`/jobs/${jobId}/applications`, payload),
  updateApplicationStatus: (applicationId: string, payload: ApplicationStatusUpdateRequest) =>
    apiClient.patch<Application>(`/applications/${applicationId}`, payload),
  getGenerationEvents: (generationId: string) =>
    apiClient.get<GenerationEvent[]>(`/cv-generations/${generationId}/events`),
  getUsageSummary: () => apiClient.get<UsageSummary>("/usage/summary"),
};
