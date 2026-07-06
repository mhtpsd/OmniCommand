"use client";

/**
 * src/components/SystemTickers.tsx
 * ------------------------------------
 * Small live metric strip along the top of the dashboard -- this is
 * what visually sells "real-time" during the demo (numbers changing
 * every few seconds as new Kafka batches land).
 */

import { useEffect, useState } from "react";
import type { RiskScore } from "@/lib/api";

function relativeTime(date: Date | null): string {
  if (!date) return "--";
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

export default function SystemTickers({ riskScores }: { riskScores: RiskScore[] }) {
  // Ticks every second purely to force a re-render of the relative-time
  // label -- it needs to keep advancing even between WebSocket messages.
  const [, setClockTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setClockTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const zonesMonitored = riskScores.length;
  const avgRiskScore =
    zonesMonitored === 0
      ? 0
      : riskScores.reduce((sum, r) => sum + r.risk_score, 0) / zonesMonitored;
  const criticalZones = riskScores.filter((r) => r.risk_level === "critical").length;

  const lastUpdated = riskScores.reduce<Date | null>((latest, r) => {
    const updated = new Date(r.updated_at);
    return !latest || updated > latest ? updated : latest;
  }, null);

  return (
    <div className="tickers">
      <div className="ticker-card">
        <span className="ticker-label">Zones monitored</span>
        <span className="ticker-value">{zonesMonitored}</span>
      </div>
      <div className="ticker-card">
        <span className="ticker-label">Avg risk score</span>
        <span className="ticker-value">{avgRiskScore.toFixed(1)}</span>
      </div>
      <div className="ticker-card">
        <span className="ticker-label">Critical zones</span>
        <span className={`ticker-value ${criticalZones > 0 ? "is-critical" : ""}`}>
          {criticalZones}
        </span>
      </div>
      <div className="ticker-card">
        <span className="ticker-label">Last updated</span>
        <span className="ticker-value">{relativeTime(lastUpdated)}</span>
      </div>
    </div>
  );
}
