import { FormEvent, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { jobsApi } from "../api/jobs";
import CoverLetterPanel from "../components/CoverLetterPanel";
import GenerationEventsPanel from "../components/GenerationEventsPanel";
import type { ApplicationStatus, CvGeneration, MarkAppliedRequest } from "../types/job";

function StatusPill({ status }: { status: string }) {
  return <span className="badge">{status}</span>;
}

const TERMINAL_STATUSES = ["succeeded", "failed"];

const FUNNEL_STAGES: { value: ApplicationStatus; label: string }[] = [
  { value: "applied", label: "Applied" },
  { value: "responded", label: "Responded" },
  { value: "hr_interview", label: "HR interview" },
  { value: "technical_interview", label: "Technical interview passed" },
  { value: "offer", label: "Offer" },
];

function GenerationRow({
  generation,
  expanded,
  onToggleExpanded,
}: {
  generation: CvGeneration;
  expanded: boolean;
  onToggleExpanded: () => void;
}) {
  const isActive = !TERMINAL_STATUSES.includes(generation.status);
  return (
    <>
      <tr>
        <td>v{generation.version_number}</td>
        <td>
          <StatusPill status={generation.status} />
        </td>
        <td>{generation.pdf_page_count ?? "-"}</td>
        <td>{generation.fact_check_status}</td>
        <td>{generation.total_cost_usd != null ? `$${generation.total_cost_usd.toFixed(4)}` : "-"}</td>
        <td>
          {generation.has_pdf && (
            <a href={`/api/cv-generations/${generation.id}/pdf`} target="_blank" rel="noreferrer">
              PDF
            </a>
          )}
          {generation.has_pdf && generation.has_tex && " | "}
          {generation.has_tex && (
            <a href={`/api/cv-generations/${generation.id}/tex`} target="_blank" rel="noreferrer">
              .tex
            </a>
          )}
        </td>
        <td>{generation.error_message ?? ""}</td>
        <td>
          <button className="btn secondary" onClick={onToggleExpanded}>
            {expanded ? "Hide steps" : "Steps"}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} style={{ background: "var(--bg-subtle)" }}>
            <GenerationEventsPanel generationId={generation.id} isActive={isActive} />
          </td>
        </tr>
      )}
    </>
  );
}

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showApplyForm, setShowApplyForm] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [expandedGenerationId, setExpandedGenerationId] = useState<string | null>(null);
  const [applyForm, setApplyForm] = useState<MarkAppliedRequest>({
    cv_generation_id: "",
    applied_at: new Date().toISOString().slice(0, 10),
    channel: "company_form",
    notes: "",
  });

  const jobQuery = useQuery({
    queryKey: ["jobs", jobId],
    queryFn: () => jobsApi.get(jobId!),
    enabled: !!jobId,
  });

  const generationsQuery = useQuery({
    queryKey: ["jobs", jobId, "cv-generations"],
    queryFn: () => jobsApi.listCvGenerations(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data as CvGeneration[] | undefined;
      const hasActive = data?.some((g) => !["succeeded", "failed"].includes(g.status));
      return hasActive ? 1500 : false;
    },
  });

  const generateMutation = useMutation({
    mutationFn: () => jobsApi.generateCv(jobId!),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["jobs", jobId, "cv-generations"] });
      setExpandedGenerationId(data.id);
    },
  });

  const applyMutation = useMutation({
    mutationFn: (payload: MarkAppliedRequest) => jobsApi.markApplied(jobId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      setShowApplyForm(false);
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ applicationId, status }: { applicationId: string; status: ApplicationStatus }) =>
      jobsApi.updateApplicationStatus(applicationId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const archiveMutation = useMutation({
    mutationFn: () => jobsApi.archive(jobId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => jobsApi.delete(jobId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate("/");
    },
  });

  if (jobQuery.isLoading) return <p>Loading...</p>;
  if (jobQuery.error) return <p className="error-box">Failed to load posting.</p>;
  const job = jobQuery.data!;
  const generations = generationsQuery.data ?? [];
  const succeededGenerations = generations.filter((g) => g.status === "succeeded");
  const application = job.applications[0];

  function submitApply(e: FormEvent) {
    e.preventDefault();
    applyMutation.mutate({ ...applyForm, cv_generation_id: applyForm.cv_generation_id || null });
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h2 style={{ marginBottom: 8 }}>
            {job.position_title} — {job.company_name}
          </h2>
          <StatusPill status={job.workflow_status} />
        </div>
        <div style={{ display: "inline-flex", gap: 6 }}>
          {confirmingDelete ? (
            <>
              <button
                className="btn"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? "Deleting..." : "Confirm delete"}
              </button>
              <button className="btn secondary" onClick={() => setConfirmingDelete(false)}>
                Cancel
              </button>
            </>
          ) : (
            <>
              {job.workflow_status !== "archived" && (
                <button
                  className="btn secondary"
                  onClick={() => archiveMutation.mutate()}
                  disabled={archiveMutation.isPending}
                >
                  Archive
                </button>
              )}
              <button className="btn secondary" onClick={() => setConfirmingDelete(true)}>
                Delete
              </button>
            </>
          )}
        </div>
      </div>

      <dl className="detail-grid">
        <div>
          <dt>Location</dt>
          <dd>
            {job.location_text ?? "-"} ({job.remote_mode})
          </dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>
            {job.source_name}
            {job.source_url && (
              <>
                {" "}
                (
                <a href={job.source_url} target="_blank" rel="noreferrer">
                  link
                </a>
                )
              </>
            )}
          </dd>
        </div>
        <div>
          <dt>Technologies</dt>
          <dd>{job.technologies.join(", ") || "-"}</dd>
        </div>
        <div>
          <dt>Match score</dt>
          <dd>{job.match_score ?? "-"}</dd>
        </div>
      </dl>

      <div className="section">
        <h2>Description</h2>
        <pre className="description">{job.description_clean_text}</pre>
      </div>

      {job.sources.length > 1 && (
        <div className="section">
          <h2>Sources</h2>
          <ul>
            {job.sources.map((source) => (
              <li key={source.id}>
                <span className="badge">{source.source_name}</span>{" "}
                {source.original_url ? (
                  <a href={source.original_url} target="_blank" rel="noreferrer">
                    {source.original_url}
                  </a>
                ) : (
                  "no link"
                )}{" "}
                <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>
                  ({new Date(source.fetched_at).toLocaleDateString()})
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="section">
        <h2>Cover letter</h2>
        <CoverLetterPanel jobId={jobId!} />
      </div>

      <div className="section">
        <h2>CV generations</h2>
        <button
          className="btn"
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
        >
          {generateMutation.isPending ? "Starting..." : "Generate CV"}
        </button>
        {generateMutation.isError && (
          <p className="error-box">{(generateMutation.error as Error).message}</p>
        )}
        {generations.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Status</th>
                <th>Pages</th>
                <th>Fact check</th>
                <th>Cost</th>
                <th>Artifacts</th>
                <th>Error</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {generations.map((g) => (
                <GenerationRow
                  key={g.id}
                  generation={g}
                  expanded={expandedGenerationId === g.id}
                  onToggleExpanded={() =>
                    setExpandedGenerationId(expandedGenerationId === g.id ? null : g.id)
                  }
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="section">
        <h2>Application</h2>
        {application && (
          <div style={{ marginBottom: 16 }}>
            <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginBottom: 8 }}>
              How far did this go? Click a stage to mark it reached (also works to correct a mistake).
            </p>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {FUNNEL_STAGES.map((stage, i) => {
                const currentIndex = FUNNEL_STAGES.findIndex((s) => s.value === application!.status);
                const reached = currentIndex >= i;
                return (
                  <button
                    key={stage.value}
                    type="button"
                    className={reached ? "btn" : "btn secondary"}
                    disabled={statusMutation.isPending}
                    onClick={() => statusMutation.mutate({ applicationId: application!.id, status: stage.value })}
                  >
                    {stage.label}
                  </button>
                );
              })}
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
              <button
                type="button"
                className={application.status === "rejected" ? "btn" : "btn secondary"}
                disabled={statusMutation.isPending}
                onClick={() => statusMutation.mutate({ applicationId: application!.id, status: "rejected" })}
              >
                Rejected
              </button>
              <button
                type="button"
                className={application.status === "withdrawn" ? "btn" : "btn secondary"}
                disabled={statusMutation.isPending}
                onClick={() => statusMutation.mutate({ applicationId: application!.id, status: "withdrawn" })}
              >
                Withdrawn
              </button>
            </div>
            {statusMutation.isError && (
              <p className="error-box">{(statusMutation.error as Error).message}</p>
            )}
          </div>
        )}
        {!showApplyForm && (
          <button className="btn" onClick={() => setShowApplyForm(true)} title="Mark this posting as applied">
            {application ? "Update applied CV/date" : "Mark as applied"}
          </button>
        )}
        {showApplyForm && (
          <form className="stacked" onSubmit={submitApply}>
            <label>
              CV version used
              <select
                value={applyForm.cv_generation_id ?? ""}
                onChange={(e) => setApplyForm({ ...applyForm, cv_generation_id: e.target.value })}
              >
                <option value="">No CV generated here (applied with my own)</option>
                {succeededGenerations.map((g) => (
                  <option key={g.id} value={g.id}>
                    v{g.version_number}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Date applied
              <input
                type="date"
                required
                value={applyForm.applied_at}
                onChange={(e) => setApplyForm({ ...applyForm, applied_at: e.target.value })}
              />
            </label>
            <label>
              Channel
              <select
                value={applyForm.channel}
                onChange={(e) => setApplyForm({ ...applyForm, channel: e.target.value })}
              >
                <option value="company_form">company_form</option>
                <option value="email">email</option>
                <option value="linkedin">linkedin</option>
                <option value="recruiter">recruiter</option>
                <option value="other">other</option>
              </select>
            </label>
            <label>
              Notes
              <textarea
                rows={3}
                value={applyForm.notes}
                onChange={(e) => setApplyForm({ ...applyForm, notes: e.target.value })}
              />
            </label>
            {applyMutation.isError && (
              <p className="error-box">{(applyMutation.error as Error).message}</p>
            )}
            <button className="btn" type="submit" disabled={applyMutation.isPending}>
              {applyMutation.isPending ? "Saving..." : "Confirm applied"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
