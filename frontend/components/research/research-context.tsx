"use client";

import { PolicyCapitalPanel } from "./policy-capital-panel";

/** Shared inline integration for sector, stock and ETF detail pages. */
export function ResearchContext(props: {
  kind: "sector" | "stock" | "etf"; code: string; name: string;
}) {
  return <PolicyCapitalPanel {...props} />;
}
