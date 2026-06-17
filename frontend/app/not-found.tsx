import Link from "next/link";

/** 404 页面 */
export default function NotFound() {
  return (
    <div className="flex items-center justify-center min-h-[60vh] bg-bg-primary">
      <div className="text-center max-w-md p-8">
        <div className="text-4xl mb-4">🔍</div>
        <h2 className="text-lg font-semibold text-text-primary mb-2">页面不存在</h2>
        <p className="text-sm text-text-muted mb-6">
          你访问的页面不存在或已被移除
        </p>
        <Link
          href="/"
          className="inline-block px-4 py-2 rounded-md bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/90 transition-colors"
        >
          返回首页
        </Link>
      </div>
    </div>
  );
}
