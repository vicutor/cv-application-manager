import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { jobsApi } from "../api/jobs";
import type { CoverLetter } from "../types/job";

function StatusPill({ status }: { status: string }) {
  return <span className="badge">{status}</span>;
}

export default function CoverLetterPanel({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const lettersQuery = useQuery({
    queryKey: ["jobs", jobId, "cover-letters"],
    queryFn: () => jobsApi.listCoverLetters(jobId),
  });

  const generateMutation = useMutation({
    mutationFn: () => jobsApi.generateCoverLetter(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", jobId, "cover-letters"] });
    },
  });

  async function copyText(letter: CoverLetter) {
    if (!letter.content_text) return;
    await navigator.clipboard.writeText(letter.content_text);
    setCopiedId(letter.id);
    setTimeout(() => setCopiedId((id) => (id === letter.id ? null : id)), 2000);
  }

  const letters = lettersQuery.data ?? [];
  const latest = letters[0];

  return (
    <div>
      <button className="btn" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
        {generateMutation.isPending ? "Writing..." : letters.length > 0 ? "Regenerate cover letter" : "Generate cover letter"}
      </button>
      {generateMutation.isError && (
        <p className="error-box">{(generateMutation.error as Error).message}</p>
      )}

      {latest && (
        <div style={{ marginTop: 16 }}>
          <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
            v{latest.version_number} &middot; <StatusPill status={latest.status} /> &middot; {latest.word_count ?? 0} words
            {latest.total_cost_usd > 0 && ` · $${latest.total_cost_usd.toFixed(4)}`}
          </p>

          {latest.status === "failed" && (
            <p className="error-box">
              {latest.error_stage}: {latest.error_message}
            </p>
          )}

          {latest.content_text && (
            <>
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  fontFamily: "inherit",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  padding: 12,
                }}
              >
                {latest.content_text}
              </pre>
              <button className="btn secondary" onClick={() => copyText(latest)}>
                {copiedId === latest.id ? "Copied" : "Copy text"}
              </button>{" "}
              {latest.has_pdf && (
                <a href={`/api/cover-letters/${latest.id}/pdf`} target="_blank" rel="noreferrer">
                  PDF
                </a>
              )}
              {latest.has_pdf && latest.has_tex && " | "}
              {latest.has_tex && (
                <a href={`/api/cover-letters/${latest.id}/tex`} target="_blank" rel="noreferrer">
                  .tex
                </a>
              )}
              <p style={{ color: "var(--muted)", fontSize: "0.8rem", marginTop: 8 }}>
                AI-sounding check: {latest.sounds_ai_flagged ? "flagged and rewritten" : "passed, no rewrite needed"}
                {latest.ai_check_notes && ` — ${latest.ai_check_notes}`}
              </p>
            </>
          )}
        </div>
      )}

      {letters.length > 1 && (
        <details style={{ marginTop: 12 }}>
          <summary style={{ cursor: "pointer", color: "var(--muted)", fontSize: "0.85rem" }}>
            {letters.length - 1} earlier version(s)
          </summary>
          {letters.slice(1).map((letter) => (
            <div key={letter.id} style={{ marginTop: 8 }}>
              <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                v{letter.version_number} &middot; <StatusPill status={letter.status} />
              </p>
              {letter.content_text && (
                <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{letter.content_text}</pre>
              )}
            </div>
          ))}
        </details>
      )}
    </div>
  );
}
