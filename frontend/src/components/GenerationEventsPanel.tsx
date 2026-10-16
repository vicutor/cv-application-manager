import { useQuery } from "@tanstack/react-query";
import { jobsApi } from "../api/jobs";
import type { GenerationEventStatus } from "../types/job";

const STAGE_LABELS: Record<string, string> = {
  analyzing: "Analyzing job posting",
  matching: "Matching your evidence to requirements",
  drafting: "Drafting CV content",
  fact_checking: "Fact-checking bullets",
  fact_checking_recheck: "Re-checking facts after style pass",
  ats_checking: "Checking ATS keyword coverage",
  style: "Polishing writing style",
  rendering: "Rendering PDF",
};

const STAGE_ICONS: Record<GenerationEventStatus, string> = {
  running: "⟳",
  succeeded: "✓",
  failed: "✕",
  skipped: "–",
};

function formatDuration(startedAt: string, completedAt: string | null): string {
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const seconds = Math.max(0, (end - start) / 1000);
  return seconds < 1 ? "<1s" : `${seconds.toFixed(1)}s`;
}

export default function GenerationEventsPanel({
  generationId,
  isActive,
}: {
  generationId: string;
  isActive: boolean;
}) {
  const eventsQuery = useQuery({
    queryKey: ["cv-generations", generationId, "events"],
    queryFn: () => jobsApi.getGenerationEvents(generationId),
    refetchInterval: isActive ? 1500 : false,
  });

  if (eventsQuery.isLoading) {
    return <p className="step-message">Loading steps...</p>;
  }
  if (eventsQuery.error) {
    return <p className="error-box">Failed to load steps.</p>;
  }

  const events = eventsQuery.data ?? [];
  if (events.length === 0) {
    return <p className="step-message">No steps recorded yet.</p>;
  }

  return (
    <ul className="step-list">
      {events.map((event) => (
        <li key={event.id} className="step-item">
          <span className={`step-icon ${event.status}`}>{STAGE_ICONS[event.status]}</span>
          <div>
            <div>
              <strong>{STAGE_LABELS[event.stage] ?? event.stage}</strong>{" "}
              <span className="step-message" style={{ display: "inline" }}>
                {formatDuration(event.started_at, event.completed_at)}
                {event.cost_usd != null && ` · $${event.cost_usd.toFixed(4)}`}
              </span>
            </div>
            {event.message && <div className="step-message">{event.message}</div>}
          </div>
        </li>
      ))}
    </ul>
  );
}
