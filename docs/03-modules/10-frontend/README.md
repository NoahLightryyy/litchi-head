# 前端模块 — litchi-head

> 基于 React + Next.js + Tailwind CSS + shadcn/ui 的专业交易看板。
> 三页自上而下决策漏斗：宏观总览 → 产业链分析 → 个股决策。

## 快速导航

| 文档 | 说明 |
|:-----|:-----|
| [SPEC.md](SPEC.md) | 完整功能规格、组件树、数据流 |
| [ROUTING.md](ROUTING.md) | 路由设计、参数约定、导航逻辑 |
| [COMPONENTS.md](COMPONENTS.md) | 组件体系、UI 规范、最佳实践 |
| [API.md](API.md) | API 接口、请求/响应格式、错误码 |
| `../../02-requirements/FRONTEND_VISION.md` | 调研报告与视觉设计方案 |

## 技术栈

| 层 | 技术 | 版本 |
|:---|:-----|:----:|
| 框架 | Next.js | 16.x |
| 渲染库 | React | 19.x |
| 语言 | TypeScript | 5.x |
| 样式 | Tailwind CSS | 4.x |
| UI 组件 | shadcn/ui | latest |
| K 线图 | Lightweight Charts | 4.x |
| 辅助图表 | ECharts | 5.x |
| 数据获取 | TanStack Query | 5.x |

## 目录结构

```
frontend/
├── app/                      # Next.js App Router 页面
│   ├── layout.tsx            # 根布局（暗色主题 + Sidebar）
│   ├── page.tsx              # Page 1: 宏观总览    /
│   ├── sector/[id]/page.tsx  # Page 2: 产业链分析  /sector/[id]
│   └── stock/[code]/page.tsx # Page 3: 个股决策    /stock/[code]
├── components/               # UI 组件
│   ├── ui/                   # shadcn/ui 原子组件
│   ├── layout/               # 布局外壳组件
│   ├── macro/                # Page 1 组件
│   ├── sector/               # Page 2 组件
│   └── stock/                # Page 3 组件
├── lib/                      # 业务逻辑
│   ├── api/                  # API 封装
│   ├── hooks/                # React Hooks
│   ├── types/                # TypeScript 类型
│   └── utils.ts              # 工具函数
├── stores/                   # Zustand 全局状态
├── public/                   # 静态资源
└── 配置文件                   # package.json, next.config 等
```

## 快速开始

```bash
# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev

# 构建
pnpm build
```

> **依赖**：前端需要 `backend/` 桥接层 API 运行（见 `../11-fastapi-bridge/README.md`）
> **关联模块**：`src/data/` · `src/debate/` · `src/memory/`
