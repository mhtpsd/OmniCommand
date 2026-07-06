/**
 * src/lib/api.ts
 * ----------------
 * Thin wrapper around the analytics-engine REST + WebSocket API, so
 * components import from here instead of scattering fetch() calls and
 * env var references throughout the codebase.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL as string;
const WS_URL = process.env.NEXT_PUBLIC_WS_URL as string;

export interface RiskScore {
  pipe_section: string;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  avg_pressure: number;
  burst_count: number;
  updated_at: string;
}

export interface TriageResponse {
  zone: string | null;
  estimated_water_depth_m: number | null;
  hazard_type: string;
  recommendation: string;
  confidence: "low" | "medium" | "high";
}

export async function fetchRiskScores(): Promise<RiskScore[]> {
  const res = await fetch(`${API_BASE}/api/risk-scores`);
  if (!res.ok) {
    throw new Error(`fetchRiskScores failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchHistory(
  pipeSection: string,
  hours: number = 24
): Promise<unknown[]> {
  const res = await fetch(
    `${API_BASE}/api/history/${encodeURIComponent(pipeSection)}?hours=${hours}`
  );
  if (!res.ok) {
    throw new Error(`fetchHistory failed: ${res.status}`);
  }
  return res.json();
}

export async function submitTriagePhoto(file: File): Promise<TriageResponse> {
  const formData = new FormData();
  formData.append("file", file);

  // Don't set Content-Type manually -- the browser needs to set the
  // multipart boundary itself.
  const res = await fetch(`${API_BASE}/api/triage`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    throw new Error(`submitTriagePhoto failed: ${res.status}`);
  }
  return res.json();
}

export function openLiveSocket(
  onMessage: (message: { type: string; data: unknown }) => void
): WebSocket {
  const socket = new WebSocket(WS_URL);
  socket.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data);
      onMessage(parsed);
    } catch (err) {
      console.error("openLiveSocket: failed to parse message", err);
    }
  };
  return socket;
}
