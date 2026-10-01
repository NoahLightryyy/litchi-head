import assert from "node:assert/strict";
import test from "node:test";
import {prepareNews, summarizeNews} from "../lib/news-topics.ts";
const now = Date.parse("2026-10-01T12:00:00+08:00");
const news = (title: string, date: string | null = "2026-10-01T09:00:00+08:00", url = "https://example.com/article") => ({title, date, source: "测试来源", url});

test("排除nan/空标题；坏时间保持未知；拒绝脚本链接", () => {
  const result = prepareNews([news('nan'), news(' null '), news(''), news('人工智能订单增长', 'nan', 'javascript:alert(1)')], now);
  assert.equal(result.invalid, 3);
  assert.equal(result.items.length, 1);
  assert.equal(result.items[0].publishedAt, null);
  assert.equal(result.items[0].url, null);
});
test("同标题跨源去重，保留最早发布时间；一文重复关键词只计一次", () => {
  const result = prepareNews([news('AI、人工智能与大模型订单增加'), news('AI 人工智能与大模型订单增加', '2026-09-29T09:00:00+08:00')], now);
  assert.equal(result.duplicates, 1);
  const all = summarizeNews(result.items, 'all', now);
  assert.deepEqual(all.topics.find(x => x.label === '人工智能')?.ids, [result.items[0].id]);
  assert.equal(summarizeNews(result.items, '24h', now).sample.length, 0);
});
test("时间窗仅纳入确定时间，边界准确；未来/无时区/非法日期不伪造", () => {
  const input = [news('芯片订单', '2026-09-30T12:00:00+08:00'), news('新能源车订单', '2026-09-30T11:59:59+08:00'),
    news('黄金风险', null), news('石油消息', '2026-10-02T09:00:00+08:00'), news('光伏消息', '2026-10-01 09:00:00'), news('金融消息', '2026-02-30T09:00:00+08:00')];
  const result = summarizeNews(prepareNews(input, now).items, '24h', now);
  assert.equal(result.sample.length, 1);
  assert.equal(result.unknownDates, 4);
  assert.equal(summarizeNews(prepareNews(input, now).items, '7d', now).sample.length, 2);
});
test("主题别名归并，关注点可追溯，不给出买卖或正负结论", () => {
  const result = summarizeNews(prepareNews([news('AI服务器扩产订单增加'), news('大模型研发取得技术进展'), news('化工供需缺口扩大，监管调查')], now).items, 'all', now);
  assert.equal(result.topics.find(x => x.label === '人工智能')?.ids.length, 2);
  assert.equal(result.topics.find(x => x.label === '算力')?.ids.length, 1);
  assert.equal(result.focuses.find(x => x.label === '供需变化')?.ids.length, 2);
  assert.equal(result.focuses.find(x => x.label === '风险事件')?.ids.length, 1);
  for (const topic of [...result.topics, ...result.focuses]) assert.ok(topic.ids.every(id => result.sample.some(item => item.id === id)));
});
test("空输入和纯无效输入不产生默认热点", () => {
  assert.equal(summarizeNews([], 'all', now).topics.length, 0);
  assert.equal(summarizeNews(prepareNews([news('nan')], now).items, 'all', now).topics.length, 0);
});
test("过滤泛词噪声但保留领域主题与重复实体", () => {
  const result = summarizeNews(prepareNews([news('关键问题开始出现，美国美债收益率上行，特朗普发表讲话'), news('关键问题导致压力，美国债券收益率回落，特朗普回应')], now).items, 'all', now);
  assert.ok(result.topics.some(x => x.label === '债券' && x.ids.length === 2));
  assert.ok(result.topics.every(x => !['关键', '开始', '美国', '收益', '压力'].includes(x.label)));
});
