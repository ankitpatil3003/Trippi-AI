import type { AgentStatus } from "../types";

const ORDER = ["planner", "researcher", "weather", "packager", "dining", "validator"] as const;

const LABELS: Record<(typeof ORDER)[number], string> = {
  planner: "Planner",
  researcher: "Research service",
  weather: "Weather service",
  packager: "Packager",
  dining: "Dining service",
  validator: "Validator",
};

export function AgentChips({
  agents,
  planCycle = 1,
}: {
  agents: AgentStatus[];
  planCycle?: number;
}) {
  const byName = Object.fromEntries(agents.map((a) => [a.agent, a]));
  return (
    <div className="status-block">
      {planCycle > 1 && (
        <div className="cycle-badge" aria-label={`Re-plan cycle ${planCycle}`}>
          Re-plan cycle {planCycle}
        </div>
      )}
      <div className="status-row" aria-label="Agent progress">
        {ORDER.map((name) => {
          const item = byName[name];
          const status = item?.status || "pending";
          return (
            <span key={name} className={`chip ${status}`} title={item?.message || ""}>
              {LABELS[name]}: {status}
            </span>
          );
        })}
      </div>
    </div>
  );
}
