# LLM 结构化输出

## HTTP 200，但 `Structured tool output missing` 或返回 `NoneType`

2026-10-26 相关资料解读实测：两次 DeepSeek 请求均返回 HTTP 200，日志为
`schema=RelatedInterpretationDraft`、`finish_reason=tool_calls`，但 LangChain 返回
`parsed=None`、`parsing_error=None`，最终得到 `RELATED_INTERPRETATION_GENERATION_FAILED`。
此前同日 `InvestmentAnalysis` 也有两次相同症状，因此不能只归咎于本次新 schema。

已查本地 `PydanticToolsParser`：未知工具名会产生解析错误；参数 JSON 或 Pydantic 字段
不合格也会产生解析错误；没有可识别工具调用时可以返回 `None` 而不报解析错。
本次工具名与 schema 类名一致，转换后 schema 还小于此前成功的公司解读。
这些证据更符合“没有识别到标准工具调用”，并不能说明供应商原始响应具体缺失了什么。
本次未保存 raw，模型端、返回封装与解析适配之间的具体根因仍未知。

排查顺序：

1. 区分 HTTP 状态、`finish_reason`、`parsed`、`parsing_error`，不要仅看 HTTP 200。
2. 检查 `src/utils/llm.py` 的实际 `output_method`、模型名、思考模式和提示版本。
3. 本地检查工具 schema 名称以及解析器错误路径；不要把空解析误写成字段校验失败。
4. 若保留了原始消息，检查标准工具调用数量、工具名、参数类型、非法调用数量与内容长度。
   不将 API 密钥、完整用户资料或未脱敏响应写进共享日志。
5. 没有原始响应时明确证据缺口；避免重复付费盲试相同模式。

## 当前局部处理：显式 JSON 模式

相关资料解读通过统一入口 `llm_service.invoke_structured(..., output_method="json_mode")`
生成，`PROMPT_VERSION` 为 `related-materials-v2-json`。默认 `function_calling` 保留，
其他功能没有自动切换；本模式也不是工具调用失败后的付费重试兜底。

统一层执行：

- 用 `bind(response_format={"type": "json_object"})` 请求 JSON 对象。
- 在系统消息中注入 `output_model.model_json_schema()`，来源材料仍作为资料传入。
- 收到消息后记录模型用量，再检查消息内容与结束原因。
- 使用 `output_model.model_validate_json(raw.content)` 校验完整 JSON 和输出模型。
- 返回业务层继续执行来源 ID、引用原句、资料归属和快照一致性检查。

没有 JSON、普通文本、Markdown 围栏、非法 JSON、缺字段或 `finish_reason=length` 都不能
保存为成功。不得补全括号、删除报错字段、容忍未知引用或把普通文字硬转成成功结果。
Pydantic 结构校验也不证明政策解读的语义正确；引用存在不等于事实已核验。

JSON 解析失败不自动再生成；网络异常仍沿用统一层既有的有限重试，并受业务总时限约束。
记录到的失败响应仍可能产生费用。相关资料刷新失败时保留上次成功快照，GET 只读、不会付费。

官方格式说明：[DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)。
该协议说明不能代替对本次响应的检查，也不证明此次根因已经定位。

## 本地验证，不调用真实模型

```bash
python -m pytest tests/test_utils/test_utils_llm.py -k explicit_json_output
python -m pytest tests/test_backend/test_related_interpretation.py
```

首组使用 mock 消息覆盖完整 JSON 成功、空字符串、普通文本、缺右括号、缺字段和输出截断，
并验证只有一次解析生成尝试、失败消息也记录用量。第二组覆盖业务来源和引用校验、同键缓存、
默认复用、显式刷新、并发限制及失败保留旧结果。真实模型的产业归因质量仍需单独检查，
不从 mock 测试通过推断所有真实解读正确。
