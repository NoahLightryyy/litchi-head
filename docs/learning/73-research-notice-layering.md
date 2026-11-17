# 73 研究说明与故障提示分层

## 一句话

> 给用户说明“数据是什么、影响什么”，把重复的采集日志留在可展开详情；真正影响结论的故障仍要突出。

## 为什么需要它？

688648历史研究保存了收盘价说明和七段新闻样本覆盖记录。逐字放进一个黄色框，
用户会把“不是实时价格”“样本不完整”都当成研究失败，也更难找到真正的价格冲突。

后端仍需要完整原文用于研究上下文与诊断。前端以纯函数整理同一份结果，
区分正常研究范围、具体缺项和冲突，不通过隐藏报错来改写后端交易状态。

## 项目里的真实代码

- `frontend/lib/debate-limitations.ts`：按能力分组，生成短摘要并保留原文。冲突优先级高于休市说明。
- `frontend/components/stock/debate-data-notice.tsx`：摘要直显，原文放进不带open属性的details。
- `frontend/components/stock/debate-panel.tsx`：通过原有会话/品种身份检查后展示，按会话key重置展开状态。

```ts
const failed = (result?.analyses ?? []).filter((item) => item.success === false).length;
if (failed) highlights.push({ label: "分析完成情况", tone: "warning", message: `${failed} 位分析未成功，当前结论只包含已完成的分析。` });
```

“没有匹配新闻”只能描述取到的样本，不能改成“最近三天无新闻”。同一报道可能在多个适配器里，
匹配条数也不能相加。报价时间只从明确标注的数据时间读取，不能使用采集时间冒充；
旧格式不能可靠提取时保留原文入口。未知能力保留通用提醒，而不是假定无影响。

## 自己试试（5分钟）

1. 在frontend目录运行 `node --test tests/debate-limitations.test.mts tests/debate-data-notice.test.mts`。
2. 看七段样本记录如何产生两条简短说明；原文仍能完整取回。
3. 将报价状态改成conflicted，观察同一条休市说明不再把冲突降为普通提示。
4. 在个股页面展开来源详情，再收起；无需重新点击触发辩论。

上一篇：[72 新闻摘要与可追溯的产业影响](72-related-news-impact.md)。

下一篇：[74 产业环节与企业身份分开建模](74-chain-company-identity.md)。
