"use client";

/**
 * src/components/MapView.tsx
 * -----------------------------
 * Deck.gl + Mapbox map showing each pipe_section/zone colored by its
 * current risk level. This is the visual centerpiece of the demo.
 *
 * The CSV dataset has no lat/lng, so zones are placed on a hardcoded
 * lookup table across a demo city area (fastest path for a hackathon --
 * see EXECUTION_PLAN.md).
 *
 * Zone names match the sensor→zone mapping in data-producer/producer.py:
 *   S001→Zone-A, S002→Zone-B, ..., S010→Zone-J
 */

import { useMemo, useState } from "react";
import Map from "react-map-gl";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer } from "@deck.gl/layers";
import "mapbox-gl/dist/mapbox-gl.css";
import type { RiskScore } from "@/lib/api";

// Demo city center -- San Francisco. Zones are laid out on a small grid
// around it so every pipe_section that shows up in the CSV gets a spot,
// even ones not explicitly listed below (see fallbackPosition).
const CENTER: [number, number] = [-122.4194, 37.7749];

// Zone names derived from real sensor IDs S001-S010 as mapped in producer.py.
const ZONE_POSITIONS: Record<string, [number, number]> = {
  "Zone-A": [-122.4194, 37.7749], // S001
  "Zone-B": [-122.4094, 37.7799], // S002
  "Zone-C": [-122.4294, 37.7699], // S003
  "Zone-D": [-122.4144, 37.7649], // S004
  "Zone-E": [-122.4044, 37.7849], // S005
  "Zone-F": [-122.4344, 37.7749], // S006
  "Zone-G": [-122.4194, 37.7849], // S007
  "Zone-H": [-122.4094, 37.7649], // S008
  "Zone-I": [-122.4294, 37.7849], // S009
  "Zone-J": [-122.4044, 37.7699], // S010
};

// Deterministic fallback so any pipe_section not in the lookup table
// above still lands somewhere sensible near the demo city, instead of
// silently disappearing from the map.
function fallbackPosition(pipeSection: string): [number, number] {
  let hash = 0;
  for (let i = 0; i < pipeSection.length; i++) {
    hash = (hash * 31 + pipeSection.charCodeAt(i)) % 1000;
  }
  const angle = (hash / 1000) * Math.PI * 2;
  const radius = 0.03;
  return [CENTER[0] + Math.cos(angle) * radius, CENTER[1] + Math.sin(angle) * radius];
}

function positionFor(pipeSection: string): [number, number] {
  return ZONE_POSITIONS[pipeSection] ?? fallbackPosition(pipeSection);
}

// RGB arrays matching the --risk-* hex values in globals.css, so map
// colors and SystemTickers/ActionPanel badges always agree.
const RISK_COLORS: Record<string, [number, number, number]> = {
  low: [47, 174, 96],
  medium: [224, 161, 46],
  high: [224, 103, 46],
  critical: [224, 46, 61],
};

function colorFor(riskLevel: string): [number, number, number] {
  return RISK_COLORS[riskLevel] ?? [139, 147, 167];
}

interface HoverInfo {
  x: number;
  y: number;
  pipe_section: string;
  risk_score: number;
  risk_level: string;
}

export default function MapView({ riskScores }: { riskScores: RiskScore[] }) {
  const [hoverInfo, setHoverInfo] = useState<HoverInfo | null>(null);
  const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  const data = useMemo(
    () =>
      riskScores.map((r) => ({
        ...r,
        position: positionFor(r.pipe_section),
      })),
    [riskScores]
  );

  // Memoize the layer so it's only recreated when `data` actually changes,
  // not on every parent render (e.g. the 1-second clock tick in SystemTickers).
  const layer = useMemo(
    () =>
      new ScatterplotLayer({
        id: "risk-zones",
        data,
        getPosition: (d: (typeof data)[number]) => d.position,
        getFillColor: (d: (typeof data)[number]) => colorFor(d.risk_level),
        getRadius: (d: (typeof data)[number]) => 80 + d.risk_score * 2,
        pickable: true,
        onHover: (info) => {
          if (info.object) {
            setHoverInfo({
              x: info.x,
              y: info.y,
              pipe_section: info.object.pipe_section,
              risk_score: info.object.risk_score,
              risk_level: info.object.risk_level,
            });
          } else {
            setHoverInfo(null);
          }
        },
      }),
    [data]
  );

  if (!mapboxToken) {
    return (
      <div className="map-empty-state">
        Set NEXT_PUBLIC_MAPBOX_TOKEN in frontend/.env.local to render the map
        (get a free token at account.mapbox.com).
      </div>
    );
  }

  return (
    <>
      <DeckGL
        initialViewState={{
          longitude: CENTER[0],
          latitude: CENTER[1],
          zoom: 12,
          pitch: 0,
          bearing: 0,
        }}
        controller
        layers={[layer]}
      >
        <Map mapboxAccessToken={mapboxToken} mapStyle="mapbox://styles/mapbox/dark-v11" />
      </DeckGL>
      {hoverInfo && (
        <div
          className="map-tooltip"
          style={{ left: hoverInfo.x + 12, top: hoverInfo.y + 12 }}
        >
          <div>
            <span className={`risk-dot ${hoverInfo.risk_level}`} />
            <strong>{hoverInfo.pipe_section}</strong>
          </div>
          <div>Risk score: {hoverInfo.risk_score.toFixed(1)}</div>
          <div>Level: {hoverInfo.risk_level}</div>
        </div>
      )}
    </>
  );
}
