import type { ChatResponse } from './types';

const BASE = '/api';

export async function sendChat(tripId: string, message: string): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trip_id: tripId, message }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json();
}

export async function getTrip(tripId: string) {
  const res = await fetch(`${BASE}/trip/${tripId}`);
  if (!res.ok) throw new Error(`Trip not found`);
  return res.json();
}

export async function optimizeDay(tripId: string, day: number) {
  const res = await fetch(`${BASE}/optimize?trip_id=${tripId}&day=${day}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Optimize failed`);
  return res.json();
}

export function getExportUrl(tripId: string, format: 'html' | 'pdf' = 'pdf') {
  return `${BASE}/itinerary/export?trip_id=${tripId}&format=${format}`;
}
