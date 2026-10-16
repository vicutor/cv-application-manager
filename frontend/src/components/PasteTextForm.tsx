import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { jobsApi } from "../api/jobs";
import { ApiError } from "../api/client";
import type { DuplicateInfo, JobImportTextRequest } from "../types/job";

const initialForm: JobImportTextRequest = {
  raw_text: "",
  source_url: "",
  company_name: "",
  position_title: "",
  location_text: "",
  remote_mode: "unknown",
  technologies: [],
  allow_duplicate: false,
};

export default function PasteTextForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(initialForm);
  const [duplicate, setDuplicate] = useState<DuplicateInfo | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: JobImportTextRequest) => jobsApi.importText(payload),
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

  function submit(e: FormEvent, allowDuplicate = false) {
    e.preventDefault();
    setDuplicate(null);
    mutation.mutate({ ...form, allow_duplicate: allowDuplicate });
  }

  return (
    <form className="stacked" onSubmit={(e) => submit(e, false)}>
      <label>
        Company name
        <input
          required
          value={form.company_name}
          onChange={(e) => setForm({ ...form, company_name: e.target.value })}
        />
      </label>
      <label>
        Position title
        <input
          required
          value={form.position_title}
          onChange={(e) => setForm({ ...form, position_title: e.target.value })}
        />
      </label>
      <label>
        Location
        <input
          value={form.location_text}
          onChange={(e) => setForm({ ...form, location_text: e.target.value })}
        />
      </label>
      <label>
        Remote mode
        <select
          value={form.remote_mode}
          onChange={(e) => setForm({ ...form, remote_mode: e.target.value })}
        >
          <option value="unknown">unknown</option>
          <option value="remote">remote</option>
          <option value="hybrid">hybrid</option>
          <option value="onsite">onsite</option>
        </select>
      </label>
      <label>
        Source URL (optional)
        <input
          value={form.source_url}
          onChange={(e) => setForm({ ...form, source_url: e.target.value })}
        />
      </label>
      <label>
        Pasted posting text
        <textarea
          required
          rows={10}
          minLength={20}
          value={form.raw_text}
          onChange={(e) => setForm({ ...form, raw_text: e.target.value })}
        />
      </label>

      {mutation.isError && !duplicate && (
        <p className="error-box">{(mutation.error as Error).message}</p>
      )}

      {duplicate && (
        <div className="error-box">
          <p>
            This looks like a {duplicate.match_level === "exact" ? "duplicate" : "likely duplicate"} of an
            existing posting: <strong>{duplicate.company_name}</strong> — {duplicate.position_title}.
          </p>
          <button
            type="button"
            className="btn secondary"
            onClick={() => navigate(`/jobs/${duplicate.job_posting_id}`)}
          >
            Open existing posting
          </button>{" "}
          <button type="button" className="btn" onClick={(e) => submit(e, true)}>
            Save as separate posting anyway
          </button>
        </div>
      )}

      <button className="btn" type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Saving..." : "Save posting"}
      </button>
    </form>
  );
}
