import { useQuery } from "@tanstack/react-query";
import { jobsApi } from "../api/jobs";

function formatUsd(value: number): string {
  return `$${value.toFixed(4)}`;
}

export default function UsagePage() {
  const usageQuery = useQuery({
    queryKey: ["usage"],
    queryFn: () => jobsApi.getUsageSummary(),
  });

  if (usageQuery.isLoading) return <p>Loading...</p>;
  if (usageQuery.error) return <p className="error-box">Failed to load usage data.</p>;
  const usage = usageQuery.data!;

  return (
    <div>
      <h2>LLM usage & cost</h2>

      <dl className="detail-grid">
        <div>
          <dt>Total cost</dt>
          <dd>{formatUsd(usage.total_cost_usd)}</dd>
        </div>
        <div>
          <dt>Total calls</dt>
          <dd>
            {usage.total_calls}
            {usage.failed_calls > 0 && ` (${usage.failed_calls} failed)`}
          </dd>
        </div>
        <div>
          <dt>Input tokens</dt>
          <dd>{usage.total_input_tokens.toLocaleString()}</dd>
        </div>
        <div>
          <dt>Output tokens</dt>
          <dd>{usage.total_output_tokens.toLocaleString()}</dd>
        </div>
      </dl>

      <div className="section">
        <h2>By stage</h2>
        {usage.by_stage.length === 0 ? (
          <p className="step-message">No LLM calls recorded yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Stage</th>
                <th>Calls</th>
                <th>Input tokens</th>
                <th>Output tokens</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {usage.by_stage.map((item) => (
                <tr key={item.key}>
                  <td>{item.key}</td>
                  <td>{item.calls}</td>
                  <td>{item.input_tokens.toLocaleString()}</td>
                  <td>{item.output_tokens.toLocaleString()}</td>
                  <td>{formatUsd(item.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="section">
        <h2>By model</h2>
        {usage.by_model.length === 0 ? (
          <p className="step-message">No LLM calls recorded yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Calls</th>
                <th>Input tokens</th>
                <th>Output tokens</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {usage.by_model.map((item) => (
                <tr key={item.key}>
                  <td>{item.key}</td>
                  <td>{item.calls}</td>
                  <td>{item.input_tokens.toLocaleString()}</td>
                  <td>{item.output_tokens.toLocaleString()}</td>
                  <td>{formatUsd(item.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="section">
        <h2>By day</h2>
        {usage.by_day.length === 0 ? (
          <p className="step-message">No LLM calls recorded yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Calls</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {[...usage.by_day].reverse().map((item) => (
                <tr key={item.date}>
                  <td>{item.date}</td>
                  <td>{item.calls}</td>
                  <td>{formatUsd(item.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
