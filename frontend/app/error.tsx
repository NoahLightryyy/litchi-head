"use client";

/** 全局错误边界 — 组件崩溃后显示重试界面 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex items-center justify-center min-h-[60vh] bg-bg-primary">
      <div className="text-center max-w-md p-8">
        <div className="text-4xl mb-4">⚠️</div>
        <h2 className="text-lg font-semibold text-text-primary mb-2">页面渲染出错</h2>
        <p className="text-sm text-text-muted mb-6">
          遇到意外错误，请尝试重新加载
        </p>
        <button
          onClick={reset}
          className="px-4 py-2 rounded-md bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/90 transition-colors"
        >
          重新加载
        </button>
      </div>
    </div>
  );
}
