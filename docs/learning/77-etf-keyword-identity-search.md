# 77｜搜索词可以灵活，证券身份不能猜

## 一句话

> 用户说“广发半导体”，目录叫“半导体设备ETF广发”；匹配可以拆词换序，结果必须仍来自真实目录。

## 为什么需要它？

只写 `query in name` 会把“目录里有，但说法不同”错报成没有结果。把所有单字随意匹配又会
让不相关基金混入结果。项目在原精确/包含匹配后，只为ETF加入有约束的组合匹配。

## 项目里的真实代码

`backend/discovery_matching.py::search_match_rank` 先归一全半角和大小写，移除基金类别词，
再要求每个主题/管理人词都命中同一条目录名称。`_han_fragments_match` 用动态规划将中文
查询覆盖为至少两个汉字的连续名称片段；片段可换顺序，但不容许单字散拼。

```python
reachable[end] = any(
    reachable[start] and query[start:end] in name for start in range(end - 1)
)
```

字符计数额外防止同一名称片段被重复透支；数字词完整匹配避免将不同指数代码混为一谈。
`backend/routers/discovery.py::search` 只按匹配等级排序原SearchHit，不重写名称、不生成代码。
数据缺失与匹配失败仍由原 `failed_sources` 分开表达。没有引入分词库、收费模型或新来源。

## 自己试试（5分钟）

1. 运行 `python -m pytest tests/test_backend/test_discovery_matching.py -q --no-cov`。
2. 对比“半导体广发”“广发基金的半导体ETF”“半导体华泰”的结果。
3. 将中文最小片段从2字改为1字，观察“半广导发体”负例为什么会误匹配；随后还原。
4. 问自己：查找方式更灵活，为什么不等于有资格凭空补基金别名或投资主题？

**上一篇：[76｜自动市场观察与榜单解读](76-observation-and-ranking-context.md)**

下一篇：待新增。
