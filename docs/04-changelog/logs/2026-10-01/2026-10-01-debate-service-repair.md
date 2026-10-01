# 2026-10-01 辩论服务故障定位与前置修复

## 事实与根因

用户在3001/stock/300199触发辩论后看到通用错误。只读检查主窗口日志，
21:55:29及21:55:50均在 `run_sync(resolve_stock_name)` 15秒超时；原实现
调用 `get_all_stocks()` 下载全市场目录。模型推理尚未启动。

另查明本机项目.env、worktree、用户/机器环境及项目凭据管理器没有可用
DEEPSEEK_API_KEY。用户表示曾配置，已继续查找关联项目、Documents提取目录、
备份与下载目录；未发现可用配置。没有读取聊天/浏览器密钥库，没有输出密钥，
未创建或覆盖凭据。找不到不能等同于从未配置。

## 改动

- 独立 `codex/debate-service-repair` / 同名worktree，基线1298ea4。
- 名称查询复用现有新浪/东财单股适配器，只投影身份，不改变研究证据门禁。
  成功缓存300秒/256项，最多4个同步请求，超时归入stock_identity 503。
- 模型配置检查先于数据准备；缺配置返回ANALYSIS_NOT_CONFIGURED 503，
  明确不可通过重试恢复。六位代码校验422。新增OpenAPI错误模型。
- 后端冻结后前端消费新错误；不展示旧结论或假分析。
- API_PROXY_TARGET支持独立预览API，默认8000保持不变。

## 验收

最终后端与LLM专项69 passed；全库Ruff、Pyright src/backend零错误；前端专项1 passed，
ESLint、Next生产构建通过。实网单股300199→翰宇药业约1.9秒。
独立8002 API在缺配置时0.056秒返回503和冻结错误；3002生产前端实点
“触发辩论”显示明确配置缺失原因，截图logs/debate-preflight-verified.png。
源码搜索已清理旧全市场名称解析实现/导入，目录搜索仍保留其独立用途。

## 当前边界与接手

TD-088保持开放：代码修复与缺配置诊断已验收，真实DeepSeek研究闭环未验收。
后续用户提供新密钥并明确要求保存，已存Windows凭据管理器litchi-head服务，
名称DEEPSEEK_API_KEY；禁止在本文/代码/日志写入值。模型列表接口200约0.32秒，
返回deepseek-flash、deepseek-v4-pro。原先找不到凭据的阻塞已解除。

继续实测发现utils/llm.py检查了settings密钥却没有传给ChatDeepSeek，SDK只读
环境导致ValidationError；已显式传递SecretStr并补无环境变量的真实SDK构造测试。
旧deepseek-chat及试用deepseek-flash生成请求分别30/45秒超时，不能称模型生成成功。
官方更新日志确认旧chat/reasoner名称7月24日停用；当前模型默认启用思考，
需显式thinking disabled维持原快速模式。已请求用户确认迁移默认模型，待答复。
依据：https://api-docs.deepseek.com/updates/ 与 https://api-docs.deepseek.com/guides/thinking_mode/。
本分支未合并、未推送、未替换主窗口3001/8000，避免干扰图表开发。
独立预览3002（Next受控会话44876）、8002（后端已重启PID40796）。
确认模型迁移后先通过src/utils/llm.py验证生成，再跑300199完整分析并核验结果、
限制和复盘；若发现后续链路问题继续修，不可仅凭前置成功关闭TD-088。
集成时取本分支的辩论修复提交，保留主窗口尚未提交的图表改动。

学习卡片58已补充轻量身份查询、前置配置检查和分阶段验收。
