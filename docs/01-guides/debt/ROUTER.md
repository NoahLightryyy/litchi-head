# 🐛 技术债务路由

> 债务按类型拆分到独立文件。新增债务先在对应类型文件中登记，然后更新本路由索引。

## 类型索引

| 类型 | 文件 | 开放债务数 |
|:-----|:-----|:----------:|
| 🏛️ 架构设计 | [ARCHITECTURE.md](ARCHITECTURE.md) | 3 |
| 💻 代码实现 | [IMPLEMENTATION.md](IMPLEMENTATION.md) | 5 |
| 🧪 测试 | [TESTING.md](TESTING.md) | 1 |
| ⚙️ 基础设施 | [INFRASTRUCTURE.md](INFRASTRUCTURE.md) | 1 |
| 🗄️ 已关闭 | [CLOSED.md](CLOSED.md) | 9 |
| 📝 模板 | [TEMPLATE.md](TEMPLATE.md) | — |

## 仪表盘

```
开放债务: 10 条    已关闭: 9 条
本金总计: ~13.7 人时
紧急指数: 1.4 / 10     ← 主要来自 TD-017 反思闭环缺失
```

## 快速新增

1. 复制 `TEMPLATE.md` 内容
2. 填入新债务信息
3. 追加到对应类型文件末尾
4. 更新本路由的开放债务数
