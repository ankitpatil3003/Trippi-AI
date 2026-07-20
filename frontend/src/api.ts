import type { TripRecord } from "./types";

const API_BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, "") || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export function planTrip(body: {
  prompt: string;
  city?: string;
  start_date?: string;
  end_date?: string;
  party_size?: number;
  preferences?: string[];
}) {
  return request<{ trip_id: string }>("/api/trips/plan", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getTrip(tripId: string) {
  return request<TripRecord>(`/api/trips/${tripId}`);
}

export function getStatus(tripId: string) {
  return request<{ trip_id: string; status: string; agent_status: TripRecord["agent_status"] }>(
    `/api/trips/${tripId}/status`,
  );
}

export function rebuildTrip(tripId: string, start: string, end: string) {
  return request<{ trip_id: string }>(`/api/trips/${tripId}/rebuild`, {
    method: "POST",
    body: JSON.stringify({ start, end }),
  });
}
