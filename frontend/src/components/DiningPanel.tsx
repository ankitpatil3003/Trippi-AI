import type { TripRecord } from "../types";

export function DiningPanel({ picks }: { picks: TripRecord["dining_picks"] }) {
  if (!picks) return null;
  return (
    <div className="panel">
      <h2>Must try dining</h2>
      <div className="dining-grid">
        {picks.local_must_try && (
          <div className="dining-card">
            <h3>Local</h3>
            <strong>{picks.local_must_try.name}</strong>
            <p className="muted">{picks.local_must_try.cuisine}</p>
            <p>{picks.local_must_try.reason}</p>
            {picks.local_must_try.grounding === "weak" && (
              <p className="muted">Grounding: weak</p>
            )}
          </div>
        )}
        {picks.fancy_must_try && (
          <div className="dining-card">
            <h3>Fancy</h3>
            <strong>{picks.fancy_must_try.name}</strong>
            <p className="muted">{picks.fancy_must_try.cuisine}</p>
            <p>{picks.fancy_must_try.reason}</p>
          </div>
        )}
      </div>
    </div>
  );
}
