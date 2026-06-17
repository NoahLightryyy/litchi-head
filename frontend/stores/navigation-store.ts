import { create } from "zustand";

interface Breadcrumb {
  label: string;
  path: string;
}

interface RecentView {
  code: string;
  name: string;
  type: "stock" | "sector";
  time: number;
}

interface NavigationState {
  /* ── 面包屑 ── */
  breadcrumbs: Breadcrumb[];
  pushBreadcrumb: (label: string, path: string) => void;
  popBreadcrumb: () => void;
  setBreadcrumbs: (crumbs: Breadcrumb[]) => void;

  /* ── 最近浏览 ── */
  recentViews: RecentView[];
  addRecentView: (item: RecentView) => void;
  clearRecentViews: () => void;
}

export const useNavigationStore = create<NavigationState>((set) => ({
  /* 面包屑 */
  breadcrumbs: [{ label: "宏观总览", path: "/" }],
  pushBreadcrumb: (label, path) =>
    set((state) => ({
      breadcrumbs: [...state.breadcrumbs, { label, path }],
    })),
  popBreadcrumb: () =>
    set((state) => ({
      breadcrumbs: state.breadcrumbs.slice(0, -1),
    })),
  setBreadcrumbs: (crumbs) => set({ breadcrumbs: crumbs }),

  /* 最近浏览 */
  recentViews: [],
  addRecentView: (item) =>
    set((state) => ({
      recentViews: [
        item,
        ...state.recentViews.filter((v) => v.code !== item.code),
      ].slice(0, 10), // 最多 10 条
    })),
  clearRecentViews: () => set({ recentViews: [] }),
}));
