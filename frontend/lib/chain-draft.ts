export type DraftGraph = {map_kind:'industry_chain'|'concept_structure';scope:string;
  nodes:{id:string;label:string;role:string;verify:string}[];
  edges:{source:string;target:string;explanation:string}[]};
export type ChainDraft = {schema_version:1;sector_code:string;sector_name:string;graph:DraftGraph;
  generated_at:string;model:string;cached:boolean;review_status:'ai_inferred_unverified'};
const object = (v:unknown):Record<string,unknown> => {
  if(!v || typeof v!=='object' || Array.isArray(v)) throw new Error('AI草图格式无效');
  return v as Record<string,unknown>;
};
const text = (v:unknown,max:number) => typeof v==='string' && v.trim().length>0 && v.length<=max;
export function parseChainDraft(value:unknown,code:string,name:string):ChainDraft {
  const r=object(value),g=object(r.graph);
  if(r.schema_version!==1 || r.sector_code!==code || r.sector_name!==name
    || r.review_status!=='ai_inferred_unverified' || typeof r.cached!=='boolean'
    || !text(r.model,100) || typeof r.generated_at!=='string' || !Number.isFinite(Date.parse(r.generated_at))
    || !['industry_chain','concept_structure'].includes(String(g.map_kind)) || !text(g.scope,500)
    || !Array.isArray(g.nodes) || g.nodes.length<2 || g.nodes.length>8
    || !Array.isArray(g.edges) || g.edges.length<1 || g.edges.length>12) throw new Error('AI草图身份或结构校验失败');
  const ids=new Set<string>(),pairs=new Set<string>();
  for(const raw of g.nodes){const n=object(raw);
    if(typeof n.id!=='string' || !/^[a-z0-9_]{1,24}$/.test(n.id) || ids.has(n.id)
      || !text(n.label,60) || !text(n.role,250) || !text(n.verify,250)) throw new Error('AI草图节点无效');
    ids.add(n.id);
  }
  for(const raw of g.edges){const e=object(raw),key=JSON.stringify([e.source,e.target]);
    if(typeof e.source!=='string' || typeof e.target!=='string' || !ids.has(e.source) || !ids.has(e.target)
      || e.source===e.target || pairs.has(key) || !text(e.explanation,200)) throw new Error('AI草图关系无效');
    pairs.add(key);
  }
  return r as unknown as ChainDraft;
}
