# 组件体系

> 分层组件架构：原子组件 → 布局组件 → 页面组件 → 全局组件。
> 基于 shadcn/ui + Tailwind CSS v4 构建。

## 组件树

```
<AppShell>                          ← 全局外壳（Sidebar + Header + Main）
├── <SidebarNav />                  ← 侧边栏导航
├── <Header />                      ← 顶部栏（Logo + Search + 面包屑）
└── <main>                          ← 页面内容（由路由驱动）
    │
    ├── [Page 1] <MacroPage>        ← 宏观总览
    │   ├── <MarketIndices />       ←   指数卡片
    │   ├── <SectorRanking />       ←   板块排行
    │   ├── <MacroBrief />          ←   AI 简报
    │   └── <HotNews />             ←   热点快讯
    │
    ├── [Page 2] <SectorPage>       ← 产业链分析
    │   ├── <SectorHeader />        ←   板块头部
    │   ├── <ChainMap />            ←   产业链地图
    │   ├── <StockList />           ←   个股列表
    │   └── <ChainAnalysis />       ←   AI 产业链分析
    │
    └── [Page 3] <StockPage>        ← 个股决策
        ├── <QuoteCard />           ←   行情卡片
        ├── <KlineChart />          ←   K 线图
        ├── <Tabs>                  ←   Tab 切换
        │   ├── <TechnicalPanel />  ←   技术分析
        │   ├── <CapitalFlow />     ←   资金流向
        │   ├── <DebatePanel />     ←   AI 辩论
        │   └── <TrustPanel />      ←   信任度看板
        └── <NewsFeed />            ←   关联新闻
```

## 组件分类

### 原子组件 (components/ui/)

shadcn/ui 官方组件，通过 CLI 安装，不手动修改：

```
button      — 按钮
card        — 卡片容器
tabs        — 标签页
table       — 表格
badge       — 徽章/标签
sidebar     — 侧边栏（官方 Sidebar Block）
input       — 输入框
select      — 下拉选择
skeleton    — 骨架屏
dialog      — 弹窗
tooltip     — 提示
separator   — 分割线
scroll-area — 滚动区域
```

### 布局组件 (components/layout/)

| 组件 | 职责 | 状态 |
|:-----|:-----|:----:|
| `AppShell` | 全局布局外壳：Sidebar + Header + main | 无状态（只读路由） |
| `SidebarNav` | 侧边栏：导航菜单 + 最近浏览 | 读取 navigation-store |
| `Header` | 顶部栏：Logo + 搜索框 + 面包屑 | 无状态 |
| `Breadcrumbs` | 自动路由面包屑 | 读取 navigation-store |

### 页面组件 (components/macro/ / sector/ / stock/)

每个组件遵循规则：
1. **纯展示组件**（没有 `useEffect`/`useState` 副作用）
2. 数据通过 props 或 hooks 获取
3. 错误态、加载态、空态三态覆盖

### 全局组件 (components/global/)

| 组件 | 职责 |
|:-----|:-----|
| `SearchDialog` | 全局搜索弹窗（Cmd+K 触发） |
| `ThemeToggle` | 暗色/亮色切换 |
| `LoadingIndicator` | 辩论加载进度指示器 |

## 数据流

```
┌──────────┐   props/context    ┌──────────┐   fetch    ┌──────────┐
│  页面     │ ────────────────→ │  Hooks    │ ────────→ │  API     │
│ (page.tsx)│                  │ (hook.ts) │           │ (api.ts) │
│           │ ←─────────────── │           │ ←──────── │          │
│           │   data / loading  │           │   JSON    │          │
└──────────┘                   └──────────┘           └──────────┘
```

## UI 规范

### 暗色主题 Token

CSS 变量在 `globals.css` 中定义，参照 `FRONTEND_VISION.md §2.2`：

```css
--bg-primary:   #0D1117;
--bg-secondary: #161B22;
--bg-tertiary:  #21262D;
--chart-bull:   #26A69A;
--chart-bear:   #EF5350;
```

### 排版层级

| 类名 | 字号 | 行高 | 用途 |
|:-----|:----:|:----:|:-----|
| `.text-price` | 2.5rem | 1.2 | 主价格数字 |
| `.text-kpi` | 1.5rem | 1.3 | KPI 数字（成交量/市值） |
| `.text-change` | 1.125rem | 1.4 | 涨跌幅 |
| `.text-label` | 0.75rem | 1.5 | 标签/脚注 |

### 间隔系统

| Token | 值 | 用途 |
|:------|:--:|:-----|
| `--gap-xs` | 4px | 紧凑内联元素 |
| `--gap-sm` | 8px | 标签与值 |
| `--gap-md` | 16px | 卡片内间距 |
| `--gap-lg` | 24px | 卡片间间距 |
| `--gap-xl` | 32px | 区块间间距 |
