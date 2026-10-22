# 公司解读：按阶段报错与有界纠正

一句话：生成、校验、保存是三个不同的失败阶段；只重试可修复的输出错误，不放宽证据要求。

真实代码：`backend/routers/company_research.py` 的 `generate_research`。共享LLM层可能把网络异常包装成ValueError，需检查异常原因再决定是否进入格式纠正；每次纠正重新传入原始证据和允许引用ID。两次尝试共享75秒预算，失败不覆盖旧记录。

前端历史按钮必须由实际保存结果决定，不能由错误文案推断“有历史”。错误状态和首次使用引导互斥。

自己试试：
1. 运行 `tests/test_backend/test_company_research.py` 的无效引用修复测试。
2. 把第二次输出也换成无效引用，确认502且没有保存。
3. 模拟存储错误，确认503、旧记录不变。

关联：[错误契约](../06-departments/08-backend-api/COMPANY-RESEARCH-ERRORS.md) · [学习索引](README.md)。
