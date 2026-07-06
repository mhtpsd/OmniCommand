"use client";

/**
 * src/app/page.tsx
 * -------------------
 * Main dashboard. Fetches the initial risk-score snapshot over REST,
 * then keeps it live via the WebSocket, and renders the three main
 * components: MapView, SystemTickers, ActionPanel.
 */

import { useEffect, useState } from "react";
import MapView from "@/components/MapView";
import SystemTickers from "@/components/SystemTickers";
import ActionPanel from "@/components/ActionPanel";
import { fetchRiskScores, openLiveSocket, RiskScore, TriageResponse } from "@/lib/api";

export default function DashboardPage() {
  const [riskScores, setRiskScores] = useState<RiskScore[]>([]);
  const [alerts, setAlerts] = useState<TriageResponse[]>([]);

  useEffect(() => {
    fetchRiskScores()
      .then(setRiskScores)
      .catch((err) => console.error("Failed to fetch initial risk scores", err));

    const socket = openLiveSocket((message) => {
      if (message.type === "risk_update") {
        setRiskScores(message.data as RiskScore[]);
      } else if (message.type === "triage_alert") {
        setAlerts((prev) => [message.data as TriageResponse, ...prev]);
      }
    });

    return () => socket.close();
  }, []);

  return (
    <div className="dashboard">
      <SystemTickers riskScores={riskScores} />
      <div className="map-panel">
        <MapView riskScores={riskScores} />
      </div>
      <ActionPanel alerts={alerts} />
    </div>
  );
}
