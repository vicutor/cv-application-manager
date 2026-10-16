import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { jobsApi } from "../api/jobs";
import type { BulkImportReport } from "../types/job";

const STATUS_LABEL: Record<string, string> = {
  imported: "Imported",
  duplicate: "Already imported",
  skipped_no_structured_data: "Skipped (no structured data)",
  failed: "Failed",
};

// pracuj.pl isn't offered as a preset here: the whole domain sits behind a
// Cloudflare managed challenge (even the homepage 403s a plain request), so
// there's no board-API-friendly URL to build -- that's a deliberate
// anti-bot posture, not a gap to work around.
const BOARD_PRESETS: { label: string; buildUrl: (keyword: string) => string }[] = [
  {
    label: "JustJoin.it",
    buildUrl: (keyword) =>
      `https://justjoin.it/job-offers/remote${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ""}`,
  },
  {
    label: "RocketJobs.pl",
    buildUrl: (keyword) =>
      `https://rocketjobs.pl/oferty-pracy/praca-zdalna?data-publikacji=1${
        keyword ? `&keyword=${encodeURIComponent(keyword)}` : ""
      }`,
  },
];

export default function ListingImportForm() {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("project manager");
  const [listingUrl, setListingUrl] = useState("https://justjoin.it/job-offers/remote?keyword=project+manager");
  const [report, setReport] = useState<BulkImportReport | null>(null);

  const importMutation = useMutation({
    mutationFn: (url: string) => jobsApi.importListing({ listing_url: url }),
    onSuccess: (data) => {
      setReport(data);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  function runImport(e: FormEvent) {
    e.preventDefault();
    setReport(null);
    importMutation.mutate(listingUrl);
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <label>
          Keyword (used by the preset buttons below)
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="e.g. project manager"
          />
        </label>
        <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
          {BOARD_PRESETS.map((board) => (
            <button
              key={board.label}
              type="button"
              className="btn secondary"
              onClick={() => setListingUrl(board.buildUrl(keyword))}
            >
              {board.label}
            </button>
          ))}
        </div>
        <p style={{ color: "var(--muted)", fontSize: "0.8rem", marginTop: 4 }}>
          pracuj.pl isn't offered here — the whole site sits behind a Cloudflare bot challenge, so
          there's no URL this can fetch directly.
        </p>
      </div>
      <form className="stacked" onSubmit={runImport}>
        <label>
          Listing page URL
          <input
            required
            type="url"
            placeholder="https://justjoin.it/job-offers/remote/devops?keyword=gcp"
            value={listingUrl}
            onChange={(e) => setListingUrl(e.target.value)}
          />
        </label>
        <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
          Imports every posting shown on that search/listing page — category (e.g. <code>/remote/devops</code>)
          and <code>?keyword=</code> both work. Already-imported postings are detected and skipped, so
          it's safe to just re-run this periodically instead of filtering by date. (justjoin.it quirk:
          combining <code>remote</code> + a category + <code>keyword</code> + <code>published-date</code> all
          at once returns an empty page on their end — drop <code>published-date</code> if you're also
          using <code>keyword</code>.)
        </p>
        {importMutation.isError && (
          <p className="error-box">{(importMutation.error as Error).message}</p>
        )}
        <button className="btn" type="submit" disabled={importMutation.isPending}>
          {importMutation.isPending ? "Importing..." : "Import listing"}
        </button>
      </form>

      {report && (
        <div style={{ marginTop: 20 }}>
          <p>
            Found <strong>{report.discovered_count}</strong> posting(s) &mdash;{" "}
            <strong>{report.imported_count}</strong> imported, <strong>{report.duplicate_count}</strong>{" "}
            already known.
          </p>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {report.items.map((item) => (
                <tr key={item.url} style={{ borderTop: "1px solid var(--border)" }}>
                  <td style={{ padding: "6px 8px" }}>
                    {item.company_name && item.position_title
                      ? `${item.position_title} @ ${item.company_name}`
                      : item.url}
                  </td>
                  <td style={{ padding: "6px 8px", whiteSpace: "nowrap" }}>
                    {STATUS_LABEL[item.status] ?? item.status}
                  </td>
                  <td style={{ padding: "6px 8px" }}>
                    {item.status === "imported" || item.status === "duplicate" ? (
                      item.job_posting_id && <a href={`/jobs/${item.job_posting_id}`}>Open</a>
                    ) : (
                      <a href={item.url} target="_blank" rel="noreferrer">
                        View posting
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
