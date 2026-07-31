import type {
  AssistantArtifact,
  MarketSnapshotArtifactData,
  OpportunityCheckArtifactData,
} from "@/api/client";
import { MarketSnapshotCard } from "./MarketSnapshotCard";
import { OpportunityCheckCard } from "./OpportunityCheckCard";

export function AssistantArtifactRenderer({ artifacts }: { artifacts: AssistantArtifact[] }) {
  if (artifacts.length === 0) return null;
  return (
    <div className="w-full">
      {artifacts.map((artifact) => {
        if (artifact.type === "market_snapshot") {
          return (
            <MarketSnapshotCard
              key={artifact.id}
              data={artifact.data as MarketSnapshotArtifactData}
            />
          );
        }
        if (artifact.type === "opportunity_check") {
          return (
            <OpportunityCheckCard
              key={artifact.id}
              data={artifact.data as OpportunityCheckArtifactData}
            />
          );
        }
        return null;
      })}
    </div>
  );
}
