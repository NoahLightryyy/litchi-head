"use client";

const NAV_ITEMS = [
  { href: "/", icon: "🏠", label: "宏观总览" },
  { href: "/", icon: "📊", label: "板块排行", anchor: true },
  { href: "/", icon: "🔍", label: "搜索", anchor: true },
];

/** 侧边栏导航：Logo + 菜单 + 最近浏览 */
export function SidebarNav() {
  return (
    <aside className="w-56 border-r border-bg-tertiary bg-bg-secondary p-4 flex flex-col gap-6">
      {/* Logo */}
      <div className="flex items-center gap-2 px-2">
        <span className="text-2xl">🍒</span>
        <span className="font-bold text-lg text-text-primary tracking-tight">
          litchi-head
        </span>
      </div>

      {/* 导航菜单 */}
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => (
          <a
            key={item.label}
            href={item.href}
            className="flex items-center gap-3 px-3 py-2 rounded-md text-text-secondary hover:bg-bg-tertiary hover:text-text-primary transition-colors text-sm"
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </a>
        ))}
      </nav>

      {/* 最近浏览 */}
      <div className="mt-auto">
        <div className="px-3 py-2 text-xs text-text-muted uppercase tracking-wider">
          最近浏览
        </div>
        <div className="px-3 py-4 text-xs text-text-muted text-center">
          暂无记录
        </div>
      </div>
    </aside>
  );
}
