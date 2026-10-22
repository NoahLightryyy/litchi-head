# 2026-10-18 修正产业链自动生成的失败恢复

用户反馈仍需主动提醒才生成。发现前轮虽然首次自动POST，但同时关闭retry/refetchOnMount/refetchOnReconnect，失败查询会留在缓存并阻止返回页面时恢复。

新增frontend/lib/chain-draft-query.ts：成功缓存Infinity，挂载及联网恢复启用；繁忙最多6次、网络/429最多2次、模型超时/失败最多1次，间隔5–15秒。参数/存储/解析错误不自动循环。组件展示恢复中状态，异常类型安全处理；保留耗尽后的手动重试。后端字段和生成契约不变，未重启后端、未额外付费生成。

QueryObserver真实行为回归3项：失败缓存重挂载会请求、成功缓存不重复请求、繁忙后成功、离线恢复继续。全前端143通过。check.py后端2067 passed/5 skipped/19 deselected，Ruff/Pyright/lint通过；首次前端类型检查因retry unknown导致error类型变化失败，修正instanceof Error保护后单独type-check/lint复查通过。git diff --check通过。

浏览器离开BK0917到行业页再返回，无点击绘图即可恢复已保存结果，生成时间不变。截图/private/tmp/litchi-chain-recovery.png。故障恢复分支由QueryObserver模拟验证，没有断开用户网络或破坏生产缓存。

同步接口文档、链图规格、前端README、知识卡68；债务CHAIN-RECOVERY-001登记并关闭，开放数不变。旧日志作为历史保留。未提交、未推送。
