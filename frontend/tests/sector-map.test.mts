import test from "node:test";
import assert from "node:assert/strict";
import { mapMatchesSector, type MapView } from "../lib/sector-map.ts";

test("地图响应必须归属当前板块，内外身份不能不一致", () => {
  const response = { current: { sector_code: "BK1325", evidence: { sector_code: "BK1325" } } } as MapView;
  assert.equal(mapMatchesSector(response, "BK1325"), true);
  assert.equal(mapMatchesSector(response, "BK1106"), false);
  response.current!.evidence.sector_code = "BK1106";
  assert.equal(mapMatchesSector(response, "BK1325"), false);
  assert.equal(mapMatchesSector({ current: null, history: [], automatic_updates: false }, "BK1325"), true);
});
