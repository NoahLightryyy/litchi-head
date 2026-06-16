"use client";

import type { ChainStage } from "@/lib/types/market";

interface ChainMapProps {
  stages: ChainStage[];
}

/** 产业链地图：上游 → 中游 → 下游，关键节点标记瓶颈 */
export function ChainMap({ stages }: ChainMapProps) {
  return (
    <div className="flex flex-col gap-4">
      {stages.map((stage, i) => (
        <div key={stage.stage}>
          {/* 阶段标题 */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-medium text-accent-blue bg-accent-blue/10 px-2 py-0.5 rounded">
              {stage.stage}
            </span>
            <span className="text-xs text-text-muted">{stage.description}</span>
            {i < stages.length - 1 && (
              <span className="text-text-muted ml-auto text-xs">↓</span>
            )}
          </div>
          {/* 节点网格 */}
          <div className="grid grid-cols-2 gap-2">
            {stage.nodes.map((node) => (
              <div
                key={node.name}
                className={`p-3 rounded-md border ${
                  node.is_bottleneck
                    ? "border-accent-gold/30 bg-accent-gold/5"
                    : "border-bg-tertiary bg-bg-primary/50"
                }`}
              >
                <div className="flex items-center gap-1 mb-1">
                  <span className="text-sm font-medium text-text-primary">{node.name}</span>
                  {node.is_bottleneck && (
                    <span className="text-xs text-accent-gold">⭐ 瓶颈</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1">
                  {node.companies.map((c) => (
                    <span
                      key={c}
                      className="text-xs text-accent-blue"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
