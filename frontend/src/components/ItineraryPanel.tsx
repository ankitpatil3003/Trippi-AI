import type { ItineraryDay } from "../types";

export function ItineraryPanel({
  itinerary,
  city,
}: {
  itinerary: ItineraryDay[];
  city?: string;
}) {
  return (
    <div className="panel">
      <h2>{city ? `${city} itinerary` : "Itinerary"}</h2>
      {itinerary.map((day) => (
        <article className="day" key={day.date}>
          <div className="day-head">
            <strong>{day.date}</strong>
            {day.weather && <span className={`weather-badge ${day.weather}`}>{day.weather}</span>}
            {day.weather_summary && <span className="muted">{day.weather_summary}</span>}
          </div>
          {day.blocks.map((block, idx) => (
            <div className={`block ${block.kind === "meal" ? "meal" : ""}`} key={`${day.date}-${idx}`}>
              <time>
                {block.start_time} to {block.end_time}
              </time>
              <div>
                <div>{block.title}</div>
                <p className="muted">
                  {block.setting}
                  {block.fallback ? " · fallback" : ""}
                  {block.notes ? ` · ${block.notes}` : ""}
                </p>
              </div>
            </div>
          ))}
        </article>
      ))}
    </div>
  );
}
