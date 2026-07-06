"use client";

/**
 * src/components/ActionPanel.tsx
 * ----------------------------------
 * Shows Gemini triage recommendations as they arrive, and includes the
 * "citizen uploads a photo" demo control -- this is the multimodal
 * differentiator, so make it visually obvious during a live demo.
 *
 * Note: submitting a photo here shows the immediate REST response, and
 * the backend also broadcasts the same alert over the WebSocket
 * (api/routes_triage.py). We rely on the WebSocket broadcast alone for
 * the persisted alerts list (it's the single source of truth page.tsx
 * already listens to) and only use the direct POST response locally to
 * drive the upload button's loading/error state.
 */

import { useRef, useState } from "react";
import { submitTriagePhoto } from "@/lib/api";
import type { TriageResponse } from "@/lib/api";

export default function ActionPanel({ alerts }: { alerts: TriageResponse[] }) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError("Choose a photo first.");
      return;
    }
    setError(null);
    setIsAnalyzing(true);
    try {
      // The result also arrives via the WebSocket broadcast and gets
      // added to `alerts` by page.tsx -- we just await it here so the
      // button shows a loading state for the few seconds Gemini takes.
      await submitTriagePhoto(file);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  return (
    <div className="action-panel">
      <div className="action-panel-header">
        <h2>Hazard triage</h2>
        <p>AI-assisted read on citizen photos -- confirm before dispatch.</p>
      </div>

      <div className="upload-control">
        <input ref={fileInputRef} type="file" accept="image/*" disabled={isAnalyzing} />
        <button className="upload-button" onClick={handleAnalyze} disabled={isAnalyzing}>
          {isAnalyzing ? "Analyzing photo..." : "Analyze photo"}
        </button>
        {error && <span className="upload-error">{error}</span>}
      </div>

      <div className="alert-list">
        {alerts.length === 0 && (
          <div className="alert-empty">No triage alerts yet -- upload a photo to test.</div>
        )}
        {alerts.map((alert, index) => (
          <div key={index} className={`alert-card ${index === 0 ? "is-newest" : ""}`}>
            <div className="alert-card-top">
              <span className="hazard-badge">{alert.hazard_type}</span>
              <span className="confidence-tag">confidence: {alert.confidence}</span>
            </div>
            <p className="alert-recommendation">{alert.recommendation}</p>
            {alert.estimated_water_depth_m != null && (
              <span className="alert-depth">
                Est. water depth: {alert.estimated_water_depth_m.toFixed(2)} m
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
