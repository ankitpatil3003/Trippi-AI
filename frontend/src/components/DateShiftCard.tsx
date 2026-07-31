import type { DateShiftSuggestion } from "../types";

export function WeatherOutlook({ suggestion }: { suggestion: DateShiftSuggestion }) {
  const wetness = suggestion.wetness ?? suggestion.original_rain_ratio;
  const threshold = suggestion.threshold ?? 0.35;
  const pops = suggestion.daily_pops ?? [];
  const dates = suggestion.daily_dates ?? [];

  return (
    <div className="panel">
      <h2>Weather outlook</h2>
      <p className="muted">
        Wetness {(wetness * 100).toFixed(0)}% (threshold {(threshold * 100).toFixed(0)}%). Scores use mean daily
        precip probability from the Weather service.
      </p>
      {pops.length > 0 && (
        <ul className="outlook-list">
          {pops.map((pop, i) => (
            <li key={`${dates[i] || i}-${pop}`}>
              <span>{dates[i] || `Day ${i + 1}`}</span>
              <span>{(pop * 100).toFixed(0)}% precip</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function DateShiftCard({
  suggestion,
  onRebuild,
  loading,
}: {
  suggestion: DateShiftSuggestion;
  onRebuild: () => void;
  loading: boolean;
}) {
  if (suggestion.direction === "none") {
    return null;
  }

  return (
    <div className="panel">
      <h2>Date shift suggestion</h2>
      <p>{suggestion.reason}</p>
      <p className="muted">
        Direction: {suggestion.direction}. Suggested {suggestion.suggested_start} through {suggestion.suggested_end}{" "}
        (wetness {((suggestion.suggested_wetness ?? suggestion.suggested_rain_ratio) * 100).toFixed(0)}%).
      </p>
      <div className="shift-actions">
        <button className="cta" type="button" onClick={onRebuild} disabled={loading}>
          Accept and re-plan for suggested dates
        </button>
      </div>
    </div>
  );
}
