import type { AgentStatus } from "../types";

const ORDER = ["planner", "researcher", "weather", "packager", "dining", "validator"];

export function AgentChips({ agents }: { agents: AgentStatus[] }) {
  const byName = Object.fromEntries(agents.map((a) => [a.agent, a]));
  return (
    <div className="status-row" aria-label="Agent progress">
      {ORDER.map((name) => {
        const item = byName[name];
        const status = item?.status || "pending";
        return (
          <span key={name} className={`chip ${status}`} title={item?.message || ""}>
            {name}: {status}
          </span>
        );
      })}
    </div>
  );
}
