import { Link, Route, Routes } from "react-router-dom";
import JobListPage from "./pages/JobListPage";
import NewJobPage from "./pages/NewJobPage";
import JobDetailPage from "./pages/JobDetailPage";
import UsagePage from "./pages/UsagePage";

export default function App() {
  return (
    <div className="app-shell">
      <div className="app-nav">
        <h1>
          <Link to="/" style={{ color: "inherit", textDecoration: "none" }}>
            CV Application Manager
          </Link>
        </h1>
        <div style={{ display: "inline-flex", gap: 8 }}>
          <Link className="btn secondary" to="/usage">
            Usage & cost
          </Link>
          <Link className="btn" to="/jobs/new">
            Add posting
          </Link>
        </div>
      </div>
      <Routes>
        <Route path="/" element={<JobListPage />} />
        <Route path="/jobs/new" element={<NewJobPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        <Route path="/usage" element={<UsagePage />} />
      </Routes>
    </div>
  );
}
