# 2026-10-26 行业页可用榜优先与提示降噪

## 本次工作

用户要求区分真实调用问题和过密提示，并直接改进。复用隔离worktree codex/market-availability；
session inspect=MATCH，基线d357cb8，原Desktop checkout未修改。

### 证据与判断

- 东财行业/概念确实502，API恢复1012条历史快照，时间2026-10-26 15:39:30+08。
- 精简请求在push2delay/push2及trust_env开关四种组合均502，不宣称切主机已解决。
- 新浪现有来源成功返回229项，无失败来源；partial是净流入、分类、服务时间说明。
- 顶部valuation empty由collector主动停用产生，不是估值网络请求失败；仍属TD-091。

### 交付

- sector-availability.ts：可用性排序、分类状态投影、北京时间范围。
- sector-funding-panels.tsx：并发查询，优先可用源；来源独立排序、刷新、分类浏览。
- market-notice.ts和market-data-notice.tsx：去重历史/缓存/延迟信息，口径中性展示，
  502和层级/单项无报价折叠；未知限制保留显式告警。
- sector-ranking.tsx：统一时间提示和离线四态。
- backend-status.tsx：全局诊断默认折叠，保留全部检查与原健康分类；区分空结果/调用失败。
- 新增来源排序/时间/渲染/分类隔离和全局诊断消费者回归。

未修改后端契约、供应商、资金计算、AI/风控门禁或缺失时间；无需新字段冻结。
同步SPEC、现有学习卡54、部门交接、债务路由与日志；历史上游证据保留。

## 验证

- 项目检查scripts/check.py通过6/6：Ruff、Pyright、README同步、前端lint/type；本轮无后端代码变更，Python测试按选择器跳过。
- 前端178项测试全部通过，包含9项新增来源/展示回归。
- webpack生产构建通过，13个静态生成步骤完成；仍使用既有node_modules软链，不改依赖。
- 实页验证：新浪229项位于前面；行业筛选48项；金融搜索排序后保留5项结果。
- 东财刷新后仍保留1012项及原时间，新浪不被阻塞；展开诊断显示两条502及层级/BK1362说明。
- 同伴复核通过：分类投影不掩盖未知范围失败；排序不重挂载清空搜索。
- 截图保存于/tmp/litchi-industry-improved.png，浏览器已保留行业页；git diff --check通过。

## 债务

FW-INDUSTRY-NOTICE-001展示体验已关闭；TD-081仍跟踪东财可用性，TD-091跟踪
估值输入与主动停用；无新增开放债务。估值恢复不混入本次行业页展示修改。

## 运行与交付

3000前端仍运行本worktree，8000保持上一轮后端；原数据目录和持久快照保留。
本轮只本地提交，不push、不合并原目录。frontend/node_modules为既有依赖软链，不入提交。
