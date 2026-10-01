# 2026-10-01 用户真实操作账本（第一原子批次）

## 本次完成

- 新增 `POST /api/user/action` 与 `GET /api/user/actions` 冻结契约。
- 新增 SQLite 不可变事件账本，覆盖幂等冲突、并发重试、用户逻辑隔离和重启恢复。
- 数量、成交价缺失保持 `null`；成交价要求显式币种；不计算账户盈亏。
- 写入成功后分发 `USER_ACTION_RECORDED`，回调失败不覆盖已落盘事实。
- 旧 `/api/retro/*` 操作/结果/刷新入口标记 deprecated，并明确旧收益是市场观察涨跌。
- 校正 DP-006 状态：大师观点镜子后端机制与用户行为镜子是两项不同能力。

## 验证

- 专项及 retro 回归：67 passed。
- `python scripts/check.py --full`：5/5 全绿；1871 passed、4 skipped、19 deselected；
  Ruff、Pyright、前端 lint 与 type-check 全部通过。
- 独立 QA 尚未接单，不宣称独立验收。

## 未决与下一步

- 主 baseline、费用、滑点、不可成交规则、收益口径、统计窗口和转段阈值待用户确认。
- 数据、记忆、回测、交易、风控、辩论/Agent 与 QA 均待各自实际承接。
- 前端仅在本批冻结提交后接线，不消费旧可变操作入口。
