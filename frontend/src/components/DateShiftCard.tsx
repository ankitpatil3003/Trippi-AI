import type { TripRecord } from "../types";

type Suggestion = NonNullable<TripRecord["date_shift_suggestion"]>;

export function DateShiftCard({
  suggestion,
  onRebuild,
  loading,
}: {
  suggestion: Suggestion;
  onRebuild: () => void;
  loading: boolean;
}) {
  return (
    <div className="panel">
      <h2>Date shift suggestion</h2>
      <p>{suggestion.reason}</p>
      <p className="muted">
        Direction: {suggestion.direction}. Original rain ratio {(suggestion.original_rain_ratio * 100).toFixed(0)}%.
        Suggested {suggestion.suggested_start} through {suggestion.suggested_end} (
        {(suggestion.suggested_rain_ratio * 100).toFixed(0)}% rain).
      </p>
      <div className="shift-actions">
        <button className="cta" type="button" onClick={onRebuild} disabled={loading}>
          Rebuild for suggested dates
        </button>
      </div>
    </div>
  );
}
