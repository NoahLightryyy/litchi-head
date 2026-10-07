import test from "node:test";
import assert from "node:assert/strict";
import { EN_MESSAGES, normalizeLocale, translate } from "../lib/locale.ts";

test("locale cookie values are allowlisted with Chinese fallback",()=>{
 for(const value of [undefined,null,"", "fr","EN","en<script>"]) assert.equal(normalizeLocale(value),"zh-CN");
 assert.equal(normalizeLocale("en"),"en"); assert.equal(normalizeLocale("zh-CN"),"zh-CN");
});
test("every menu destination has an English translation and Chinese is reversible",()=>{
 for(const label of ["市场总览","行业研究","选股与对比","自选与跟踪","持仓与风险","研究与复盘","数据状态","设置","最近浏览","个股","板块","技术分析","资金流向","财务分析","流派分析","信任度"]){
  assert.ok(EN_MESSAGES[label]);assert.doesNotMatch(translate("en",label),/[\u4e00-\u9fff]/);assert.equal(translate("zh-CN",label),label);
 }
});
test("dynamic source text, symbols and prices remain untouched",()=>{
 for(const text of ["三元基因","001246","25.37%","原始研究说明","toString","__proto__"]){assert.equal(translate("en",text),text);}
});
