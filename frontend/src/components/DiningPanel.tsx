import type { DiningPick, TripRecord } from "../types";

function PickCard({ label, pick }: { label: string; pick: DiningPick }) {
  return (
    <div className="dining-card">
      <h3>{label}</h3>
      <strong>{pick.name}</strong>
      <p className="muted">{pick.cuisine}</p>
      <p>{pick.reason}</p>
      <p className="muted">
        {pick.provenance === "live" ? "Live source" : "Recorded source"}
        {pick.grounding === "weak" ? " · grounding: weak" : ""}
      </p>
    </div>
  );
}

export function DiningPanel({ picks }: { picks: TripRecord["dining_picks"] }) {
  if (!picks) return null;

  const hasAny = picks.local_must_try || picks.fancy_must_try;
  return (
    <div className="panel">
      <h2>Must try dining</h2>
      {!hasAny && (
        <p className="muted">
          No restaurants could be sourced for this destination, so no dining picks are shown.
        </p>
      )}
      <div className="dining-grid">
        {picks.local_must_try && <PickCard label="Local" pick={picks.local_must_try} />}
        {picks.fancy_must_try && <PickCard label="Fancy" pick={picks.fancy_must_try} />}
      </div>
    </div>
  );
}
