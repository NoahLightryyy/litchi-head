import test from "node:test";
import assert from "node:assert/strict";
import { horizonView, horizonConsensus } from "../lib/research-horizon.ts";
import type { AgentAnalysis } from "../lib/types/debate.ts";
const now = new Date("2026-10-06T12:00:00Z");
const agent = (name="one"): AgentAnalysis => ({agent_name:name,skill_id:name,skill_name:name,rating:"看涨",score:70,summary:"",analysis:"",confidence:.8,direction:"Bullish",success:true,latency_ms:1,research_generated_at:"2026-10-06T10:00:00Z",horizons:(["short","medium","long"] as const).map(horizon=>({horizon,status:"supported",direction:"Bullish",thesis:"条件性价格观点",assumptions:["财报兑现"],invalidation:["盈利下修"],review_on:"2026-10-07",review_trigger:"新公告",evidence:["9月30日报价"],limitations:"单源"}))});
test("legacy, duplicate, blank and invalid dates cannot supply direction",()=>{
 const a=agent(); delete a.horizons; assert.equal(horizonView(a,"short",now).eligible,false);
 for(const value of ["bad","2026-99-99","2026-10-32","2026-10-05","2027-10-06"]){const b=agent();b.horizons![0].review_on=value;assert.equal(horizonView(b,"short",now).eligible,false);}
 const b=agent(); b.horizons![1].horizon="short";assert.equal(horizonView(b,"short",now).eligible,false);
 const c=agent();c.horizons![0].assumptions=[" "];assert.equal(horizonView(c,"short",now).eligible,false);
});
test("only five complete same-period opinions can agree; insufficient never becomes neutral",()=>{
 const all=Array.from({length:5},(_,i)=>agent(String(i)));
 assert.equal(horizonConsensus(all,"short",now),"条件性一致：看涨");
 all[0].horizons![0].direction="Bearish";assert.equal(horizonConsensus(all,"short",now),"流派存在分歧");
 assert.equal(horizonConsensus(all,"long",now),"条件性一致：看涨");
 all[0].horizons![0].status="insufficient";all[0].horizons![0].direction=null;
 assert.equal(horizonView(all[0],"short",now).eligible,false);
 assert.match(horizonConsensus(all,"short",now),/不形成/);
 assert.equal(horizonView(agent(),"short",new Date("2026-10-08T12:00:00Z")).eligible,false);
});

test("partial views remain visible without converting missing evidence into neutral or probability", async () => {
 const { horizonDistribution } = await import("../lib/research-horizon.ts");
 const all=Array.from({length:5},(_,i)=>agent(String(i)));
 for(const a of all) { a.horizons![0].status="insufficient";a.horizons![0].direction=null; }
 all[0].horizons![0].status="supported";all[0].horizons![0].direction="Bearish";
 assert.deepEqual(horizonDistribution(all,"short",now),{counts:{Bullish:0,Bearish:1,Neutral:0},unavailable:4,total:5,eligible:1});
 assert.match(horizonConsensus(all,"short",now),/不形成/);
 assert.equal(horizonDistribution(all,"short",new Date("2026-10-08T12:00:00Z")).eligible,0);
 assert.equal(horizonDistribution([agent(),agent()],"short",now).eligible,0);
 assert.equal(horizonDistribution([],"short",now).total,0);
});
