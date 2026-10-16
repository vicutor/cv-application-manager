import { useState } from "react";
import ListingImportForm from "../components/ListingImportForm";
import PasteTextForm from "../components/PasteTextForm";
import UrlImportForm from "../components/UrlImportForm";

type Mode = "url" | "text" | "listing";

export default function NewJobPage() {
  const [mode, setMode] = useState<Mode>("url");

  return (
    <div>
      <h2>Add job posting</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button
          type="button"
          className={mode === "url" ? "btn" : "btn secondary"}
          onClick={() => setMode("url")}
        >
          Import from URL
        </button>
        <button
          type="button"
          className={mode === "text" ? "btn" : "btn secondary"}
          onClick={() => setMode("text")}
        >
          Paste text
        </button>
        <button
          type="button"
          className={mode === "listing" ? "btn" : "btn secondary"}
          onClick={() => setMode("listing")}
        >
          Import from listing page
        </button>
      </div>
      {mode === "url" && <UrlImportForm />}
      {mode === "text" && <PasteTextForm />}
      {mode === "listing" && <ListingImportForm />}
    </div>
  );
}
