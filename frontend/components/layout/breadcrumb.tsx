import Link from "next/link";

interface BreadcrumbItem {
  label: string;
  path: string;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

/** 面包屑导航组件 */
export function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav className="flex items-center gap-2 text-sm">
      {items.map((item, i) => (
        <span key={item.path} className="flex items-center gap-2">
          {i > 0 && <span className="text-text-muted">/</span>}
          {i === items.length - 1 ? (
            <span className="text-text-primary font-medium">{item.label}</span>
          ) : (
            <Link href={item.path} className="text-text-secondary hover:text-text-primary transition-colors">
              {item.label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  );
}
