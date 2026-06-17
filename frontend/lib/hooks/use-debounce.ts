"use client";

import { useState, useEffect } from "react";

/**
 * 防抖工具 Hook
 *
 * 在 delay 毫秒内值未变化才返回最新值。
 * 适用于搜索输入等高频触发场景。
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
