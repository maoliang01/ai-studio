"use client";

import { useEffect } from "react";
import { useSettingsStore } from "@/stores/settings-store";

/**
 * 应用初始化组件
 * 在应用启动时从后端同步共享配置（模型列表、爬取源）
 */
export function InitProvider({ children }: { children: React.ReactNode }) {
  const syncModelsFromBackend = useSettingsStore((s) => s.syncModelsFromBackend);
  const syncFromBackend = useSettingsStore((s) => s.syncFromBackend);

  useEffect(() => {
    // 应用启动时同步所有共享配置
    const init = async () => {
      await Promise.all([
        syncModelsFromBackend(),
        syncFromBackend(),
      ]);
    };
    init();
  }, [syncModelsFromBackend, syncFromBackend]);

  return <>{children}</>;
}