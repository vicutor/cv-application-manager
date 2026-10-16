import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { jobsApi } from "../api/jobs";
import { ApiError } from "../api/client";
import type { DuplicateInfo, JobImportUrlConfirmRequest, JobImportUrlPreviewResponse } from "../types/job";

function toConfirmPayload(
  preview: JobImportUrlPreviewResponse,
  technologiesInput: string,
  allowDuplicate: boolean
): JobImportUrlConfirmRequest {
  return {
    canonical_url: preview.canonical_url,
    staging_token: preview.staging_token,
    external_job_id: preview.external_job_id,
    company_name: preview.company_name,
    position_title: preview.position_title,
    location_text: preview.location_text ?? "",
    remote_mode: preview.remote_mode,
    employment_types: preview.employment_types,
    salary_min: preview.salary_min,
    salary_max: preview.salary_max,
    salary_currency: preview.salary_currency,
    salary_period: preview.salary_period,
    description_raw_text: preview.description_raw_text,
    description_clean_text: preview.description_clean_text,
    published_at: preview.published_at,
    expires_at: preview.expires_at,
    technologies: technologiesInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean),
    allow_duplicate: allowDuplicate,
  };
}

export default function UrlImportForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [showPasteHtml, setShowPasteHtml] = useState(false);
  const [pasteSourceUrl, setPasteSourceUrl] = useState("");
  const [pasteHtml, setPasteHtml] = useState("");
  const [preview, setPreview] = useState<JobImportUrlPreviewResponse | null>(null);
  const [duplicate, setDuplicate] = useState<DuplicateInfo | null>(null);
  const [technologiesInput, setTechnologiesInput] = useState("");

  const previewMutation = useMutation({
    mutationFn: (u: string) => jobsApi.previewUrl(u),
    onSuccess: (data) => {
      setDuplicate(data.duplicate);
      setPreview(data);
      setTechnologiesInput(data.technologies.join(", "));
    },
  });

  const previewHtmlMutation = useMutation({
    mutationFn: () => jobsApi.previewHtml({ html: pasteHtml, source_url: pasteSourceUrl }),
    onSuccess: (data) => {
      setDuplicate(data.duplicate);
      setPreview(data);
      setTechnologiesInput(data.technologies.join(", "));
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (payload: JobImportUrlConfirmRequest) => jobsApi.confirmUrl(payload),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/jobs/${job.id}`);
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError && err.status === 409) {
        setDuplicate(err.detail as DuplicateInfo);
      }
    },
  });

  const attachMutation = useMutation({
    mutationFn: () => {
      if (!preview || !duplicate) throw new Error("nothing to attach");
      return jobsApi.attachSource(duplicate.job_posting_id, {
        canonical_url: preview.canonical_url,
        staging_token: preview.staging_token,
        source_name: preview.source_name,
        external_job_id: preview.external_job_id,
      });
    },
    onSuccess: () => {
      if (!duplicate) return;
      queryClient.invalidateQueries({ queryKey: ["jobs", duplicate.job_posting_id] });
      navigate(`/jobs/${duplicate.job_posting_id}`);
    },
  });

  function fetchPreview(e: FormEvent) {
    e.preventDefault();
    setDuplicate(null);
    setPreview(null);
    previewMutation.mutate(url);
  }

  function fetchPreviewFromHtml(e: FormEvent) {
    e.preventDefault();
    setDuplicate(null);
    setPreview(null);
    previewHtmlMutation.mutate();
  }

  function updatePreview(patch: Partial<JobImportUrlPreviewResponse>) {
    if (!preview) return;
    setPreview({ ...preview, ...patch });
  }

  function save(e: FormEvent, allowDuplicate = false) {
    e.preventDefault();
    if (!preview) return;
    setDuplicate(null);
    confirmMutation.mutate(toConfirmPayload(preview, technologiesInput, allowDuplicate));
  }

  return (
    <div>
      <form className="stacked" onSubmit={fetchPreview}>
        <label>
          Job posting URL
          <input
            required
            type="url"
            placeholder="https://justjoin.it/job-offer/..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </label>
        {previewMutation.isError && (
          <p className="error-box">{(previewMutation.error as Error).message}</p>
        )}
        <button className="btn" type="submit" disabled={previewMutation.isPending}>
          {previewMutation.isPending ? "Fetching..." : "Fetch"}
        </button>
      </form>

      <button
        type="button"
        className="btn secondary"
        style={{ marginTop: 10 }}
        onClick={() => setShowPasteHtml((v) => !v)}
      >
        {showPasteHtml ? "Hide" : "Can't fetch this one? Paste the page HTML instead"}
      </button>

      {showPasteHtml && (
        <form className="stacked" style={{ marginTop: 10 }} onSubmit={fetchPreviewFromHtml}>
          <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
            For boards that block automated fetching (e.g. pracuj.pl's bot-protection
            challenge): open the posting in your own browser, View Source (Cmd+Option+U
            in Chrome), copy the whole HTML, and paste it below. We parse it locally —
            nothing gets fetched over the network.
          </p>
          <label>
            Posting URL (for reference &amp; dedup)
            <input
              required
              type="url"
              placeholder="https://www.pracuj.pl/praca/..."
              value={pasteSourceUrl}
              onChange={(e) => setPasteSourceUrl(e.target.value)}
            />
          </label>
          <label>
            Page HTML (View Source)
            <textarea
              required
              rows={8}
              placeholder="<html>...</html>"
              value={pasteHtml}
              onChange={(e) => setPasteHtml(e.target.value)}
            />
          </label>
          {previewHtmlMutation.isError && (
            <p className="error-box">{(previewHtmlMutation.error as Error).message}</p>
          )}
          <button className="btn" type="submit" disabled={previewHtmlMutation.isPending}>
            {previewHtmlMutation.isPending ? "Parsing..." : "Parse pasted HTML"}
          </button>
        </form>
      )}

      {preview && (
        <form className="stacked" style={{ marginTop: 20 }} onSubmit={(e) => save(e, false)}>
          <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
            Extracted via {preview.extraction_method === "json_ld" ? "structured job data" : "manual review"}{" "}
            from {preview.source_name}. Review and correct before saving.
          </p>
          <label>
            Company name
            <input
              required
              value={preview.company_name}
              onChange={(e) => updatePreview({ company_name: e.target.value })}
            />
          </label>
          <label>
            Position title
            <input
              required
              value={preview.position_title}
              onChange={(e) => updatePreview({ position_title: e.target.value })}
            />
          </label>
          <label>
            Location
            <input
              value={preview.location_text ?? ""}
              onChange={(e) => updatePreview({ location_text: e.target.value })}
            />
          </label>
          <label>
            Remote mode
            <select
              value={preview.remote_mode}
              onChange={(e) => updatePreview({ remote_mode: e.target.value })}
            >
              <option value="unknown">unknown</option>
              <option value="remote">remote</option>
              <option value="hybrid">hybrid</option>
              <option value="onsite">onsite</option>
            </select>
          </label>
          <label>
            Technologies (comma-separated)
            <input value={technologiesInput} onChange={(e) => setTechnologiesInput(e.target.value)} />
          </label>
          <label>
            Description
            <textarea
              required
              rows={10}
              value={preview.description_clean_text}
              onChange={(e) =>
                updatePreview({
                  description_clean_text: e.target.value,
                  description_raw_text: e.target.value,
                })
              }
            />
          </label>

          {confirmMutation.isError && !duplicate && (
            <p className="error-box">{(confirmMutation.error as Error).message}</p>
          )}

          {duplicate && (
            <div className="error-box">
              <p>
                This looks like a {duplicate.match_level === "exact" ? "duplicate" : "likely duplicate"} of
                an existing posting: <strong>{duplicate.company_name}</strong> — {duplicate.position_title}.
              </p>
              <p style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                Same job, found on another board? Attach this link as an additional source instead of
                creating a new posting.
              </p>
              {attachMutation.isError && (
                <p className="error-box">{(attachMutation.error as Error).message}</p>
              )}
              <button
                type="button"
                className="btn secondary"
                onClick={() => navigate(`/jobs/${duplicate.job_posting_id}`)}
              >
                Open existing posting
              </button>{" "}
              <button
                type="button"
                className="btn secondary"
                onClick={() => attachMutation.mutate()}
                disabled={attachMutation.isPending}
              >
                {attachMutation.isPending ? "Attaching..." : "Attach as another source"}
              </button>{" "}
              <button type="button" className="btn" onClick={(e) => save(e, true)}>
                Save as separate posting anyway
              </button>
            </div>
          )}

          <button className="btn" type="submit" disabled={confirmMutation.isPending}>
            {confirmMutation.isPending ? "Saving..." : "Save posting"}
          </button>
        </form>
      )}
    </div>
  );
}
