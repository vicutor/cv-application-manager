import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { jobsApi } from "../api/jobs";
import type { JobPostingListItem } from "../types/job";

function RowActions({ job }: { job: JobPostingListItem }) {
  const queryClient = useQueryClient();
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const archiveMutation = useMutation({
    mutationFn: () => jobsApi.archive(job.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => jobsApi.delete(job.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });

  if (confirmingDelete) {
    return (
      <span style={{ display: "inline-flex", gap: 6 }}>
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
      </span>
    );
  }

  return (
    <span style={{ display: "inline-flex", gap: 6 }}>
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
    </span>
  );
}

export default function JobListPage() {
  const [showArchived, setShowArchived] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => jobsApi.list(),
  });

  if (isLoading) return <p>Loading...</p>;
  if (error) return <p className="error-box">Failed to load postings: {String(error)}</p>;

  const jobs = (data ?? []).filter((job) => showArchived || job.workflow_status !== "archived");
  const archivedCount = (data ?? []).filter((job) => job.workflow_status === "archived").length;

  if (!data || data.length === 0) {
    return (
      <p>
        No postings yet. <Link to="/jobs/new">Add one</Link>.
      </p>
    );
  }

  return (
    <div>
      {archivedCount > 0 && (
        <label style={{ display: "block", marginBottom: 12, fontSize: "0.85rem" }}>
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(e) => setShowArchived(e.target.checked)}
          />{" "}
          Show archived ({archivedCount})
        </label>
      )}
      {jobs.length === 0 ? (
        <p>No postings to show.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th>Position</th>
              <th>Location</th>
              <th>Source</th>
              <th>Status</th>
              <th>CV</th>
              <th>Applied</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>
                  <Link to={`/jobs/${job.id}`}>{job.company_name}</Link>
                </td>
                <td>{job.position_title}</td>
                <td>
                  {job.location_text ?? "-"} <span className="badge">{job.remote_mode}</span>
                </td>
                <td>{job.source_name}</td>
                <td>
                  <span className="badge">{job.workflow_status}</span>
                </td>
                <td>{job.has_cv ? "yes" : "-"}</td>
                <td>
                  {job.applied ? (
                    <span className="badge applied">
                      {job.applied_at ? new Date(job.applied_at).toLocaleDateString() : "applied"}
                    </span>
                  ) : (
                    "-"
                  )}
                </td>
                <td>
                  <RowActions job={job} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
