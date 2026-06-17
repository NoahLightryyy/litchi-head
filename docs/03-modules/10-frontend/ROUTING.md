# 前端路由设计

> 基于 Next.js 16 App Router 的动态路由。
> 三页漏斗 + 侧边栏导航 + 面包屑回溯。

## 路由表

```
/                            ← Page 1: 宏观总览（默认首页）
├── sector/
│   └── [id]/                ← Page 2: 产业链分析（动态板块ID）
│       └── ?sort=           ←   查询参数：排序维度
│
├── stock/
│   └── [code]/              ← Page 3: 个股决策（动态股票代码）
│       └── ?tab=            ←   查询参数：默认 Tab
│
└── _not-found                ← 404 页面
```

## 路由层级

```
宏观总览  ──点击板块──→  /sector/{板块代码}
     │                          │
     │                          └──点击个股──→  /stock/{股票代码}
     │                                              │
     └──搜索个股─────────────→  直接跳转 ────────────┘
```

## 导航组件

### 面包屑 (Breadcrumb)

自动生成：`宏观总览 > 电力设备 > 宁德时代`

实现方式：`usePathname()` 切片：
```typescript
// /sector/BK0579 → ["宏观总览", "电力设备"]
// /stock/300750  → ["宏观总览", "宁德时代"]
// /sector/BK0579 → /stock/300750 时面包屑为 "宏观总览 > 电力设备 > 宁德时代"
```

### 侧边栏 (Sidebar)

使用 shadcn/ui Sidebar Block：
- Logo + 产品名
- 导航菜单
  - 🏠 宏观总览 → `/`
  - 📊 板块排行 → `/`（锚点到板块区）
  - 🔍 搜索 → 搜索弹窗
- 最近浏览记录（Zustand store 持久化）
- 自选股列表（待实现）

### 搜索框 (SearchBox)

全局搜索，支持：
- 模糊匹配板块名称/个股代码
- 选中板块 → `/sector/[id]`
- 选中个股 → `/stock/[code]`

## 参数约定

### 板块 ID `[id]`

| 格式 | 示例 | 说明 |
|:-----|:------|:-----|
| `BK` 前缀 | `BK0579` | 东方财富板块代码 |
| `s_` 前缀 | `s_industry_1` | 行业板块分类 ID |
| `c_` 前缀 | `c_concept_5` | 概念板块分类 ID |

### 股票代码 `[code]`

| 格式 | 示例 | 说明 |
|:-----|:------|:-----|
| 6 位数字 | `000001` | A 股统一代码 |
| 前缀区分市场 | `sh600000` / `sz000001` | 可选市场前缀 |

### 查询参数

```typescript
// Page 2: 板块排序
?sort=fund_flow     // 默认：资金流向
?sort=change_pct    // 涨跌幅
?sort=ai_rating     // AI 评级

// Page 3: 默认 Tab
?tab=technical      // 技术分析
?tab=capital        // 资金流向
?tab=debate         // AI 辩论
?tab=trust          // 信任度
```

## 导航状态（Zustand）

```typescript
interface NavigationState {
  breadcrumbs: Array<{ label: string; path: string }>;
  recentViews: Array<{ code: string; name: string; type: 'stock' | 'sector'; time: number }>;
  
  // actions
  pushBreadcrumb: (label: string, path: string) => void;
  popBreadcrumb: () => void;
  addRecentView: (item: RecentViewItem) => void;
  clearRecentViews: () => void;
}
```

## 路由守卫

| 场景 | 处理 |
|:-----|:-----|
| 未知板块 ID | 显示「未找到该板块」+ 推荐列表 |
| 未知股票代码 | 显示「未找到该股票」+ 搜索跳转 |
| 辩论页面直接访问 | 如果没有缓存结果，显示「请先搜索个股」提示 |
