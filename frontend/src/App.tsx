import { FormEvent, useEffect, useMemo, useState } from "react";
import { getStatus, getTrip, planTrip, rebuildTrip } from "./api";
import type { TripRecord } from "./types";
import { AgentChips } from "./components/AgentChips";
import { DiningPanel } from "./components/DiningPanel";
import { ItineraryPanel } from "./components/ItineraryPanel";
import { DateShiftCard, WeatherOutlook } from "./components/DateShiftCard";

const defaultStart = "2026-07-21";
const defaultEnd = "2026-07-23";

export default function App() {
  const [prompt, setPrompt] = useState(
    "3 days in New York, love views and pizza, prefer museums if it rains",
  );
  const [city, setCity] = useState("New York");
  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(defaultEnd);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tripId, setTripId] = useState<string | null>(null);
  const [trip, setTrip] = useState<TripRecord | null>(null);

  const showShift = useMemo(
    () => trip?.date_shift_suggestion && trip.date_shift_suggestion.direction !== "none",
    [trip],
  );

  // Buffer blocks carry no provenance. If nothing in the trip has a source,
  // no real place was found and the schedule is placeholder time only.
  const noSourcedPlaces = useMemo(
    () =>
      !!trip &&
      trip.itinerary.length > 0 &&
      trip.itinerary.every((day) => day.blocks.every((b) => !b.provenance)),
    [trip],
  );

  useEffect(() => {
    if (!tripId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const status = await getStatus(tripId);
        if (cancelled) return;
        if (status.status === "completed" || status.status === "failed") {
          const full = await getTrip(tripId);
          if (!cancelled) {
            setTrip(full);
            setLoading(false);
          }
          return;
        }
        const partial = await getTrip(tripId);
        if (!cancelled) setTrip(partial);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Polling failed");
          setLoading(false);
        }
      }
    };
    tick();
    const id = window.setInterval(tick, 900);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [tripId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setTrip(null);
    try {
      const res = await planTrip({
        prompt,
        city,
        start_date: startDate,
        end_date: endDate,
        preferences: ["views", "food", "museums"],
      });
      setTripId(res.trip_id);
    } catch (err) {
      setLoading(false);
      setError(err instanceof Error ? err.message : "Plan failed");
    }
  }

  async function onRebuild() {
    if (!trip?.date_shift_suggestion || !tripId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await rebuildTrip(
        tripId,
        trip.date_shift_suggestion.suggested_start,
        trip.date_shift_suggestion.suggested_end,
      );
      setTripId(res.trip_id);
      setTrip(null);
    } catch (err) {
      setLoading(false);
      setError(err instanceof Error ? err.message : "Rebuild failed");
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <p className="brand">Trippi-AI</p>
        <p className="tagline">
          Multi-agent itineraries orchestrated over your Weather, Research, and Dining MCP services: adapt to the
          forecast, soft-recommend better dates when it looks wet, and land one local bite plus one special dinner.
        </p>
      </header>

      <form className="planner-card" onSubmit={onSubmit}>
        <label>
          Trip prompt
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} required />
        </label>
        <div className="grid-2">
          <label>
            City
            <input value={city} onChange={(e) => setCity(e.target.value)} required />
          </label>
          <label>
            Party size
            <input type="number" min={1} defaultValue={2} readOnly />
          </label>
          <label>
            Start
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
          </label>
          <label>
            End
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
          </label>
        </div>
        <button className="cta" type="submit" disabled={loading}>
          {loading ? "Planning…" : "Plan my trip"}
        </button>
      </form>

      {error && <div className="banner error">{error}</div>}
      {trip && !trip.weather_available && (
        <div className="banner">Weather service was unavailable. Itinerary used a degraded forecast path.</div>
      )}
      {trip && trip.research_available === false && (
        <div className="banner">
          Research service unavailable or stubbed. Places came from the recorded corpus, not a live search.
        </div>
      )}
      {trip && trip.dining_available === false && (
        <div className="banner">
          Dining service unavailable or stubbed. Restaurants came from the recorded corpus, not a live search.
        </div>
      )}
      {trip && trip.itinerary.length > 0 && noSourcedPlaces && (
        <div className="banner">
          No real places could be sourced for {trip.constraints?.city ?? "this destination"}. Trippi does not
          invent recommendations, so the schedule below is generic placeholder time only.
        </div>
      )}
      {trip && trip.errors?.length > 0 && (
        <div className="banner">
          <strong>Planner notes</strong>
          <ul className="error-list">
            {trip.errors.map((e) => (
              <li key={e.code}>
                {e.message}
                {e.retryable ? " (retryable)" : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {trip && (
        <section className="results">
          <AgentChips agents={trip.agent_status} planCycle={trip.plan_cycle ?? 1} />
          {trip.date_shift_suggestion && <WeatherOutlook suggestion={trip.date_shift_suggestion} />}
          {showShift && trip.date_shift_suggestion && (
            <DateShiftCard suggestion={trip.date_shift_suggestion} onRebuild={onRebuild} loading={loading} />
          )}
          <ItineraryPanel itinerary={trip.itinerary} city={trip.constraints?.city} />
          <DiningPanel picks={trip.dining_picks} />
        </section>
      )}
    </div>
  );
}
