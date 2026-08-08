"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  Header,
  HeaderLeft,
  HeaderRight,
} from "@/components/ui/header";
import { Button } from "@/components/ui/button";
import {
  Sun,
  Moon,
  Menu,
  Bell,
  User,
  Home,
} from "lucide-react";
import { useSidebar } from "@/components/ui/sidebar";
import { useSettingsStore } from "@/stores/settings-store";

const pageTitles: Record<string, string> = {
  "/": "对话",
  "/knowledge": "知识库",
  "/prompts": "提示词管理",
  "/scrape": "网页爬取",
  "/settings": "设置",
};

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { toggleSidebar } = useSidebar();
  const { settings, setTheme } = useSettingsStore();

  const title = pageTitles[pathname] || "Find Out";

  const toggleTheme = () => {
    const themes: Array<"light" | "dark" | "system"> = ["light", "dark", "system"];
    const currentIndex = themes.indexOf(settings.theme);
    setTheme(themes[(currentIndex + 1) % themes.length]);
  };

  return (
    <Header>
      <HeaderLeft>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className="h-8 w-8"
        >
          <Menu className="h-4 w-4" />
        </Button>
        {/* 非首页时显示"返回首页"按钮 */}
        {pathname !== "/" && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/")}
            className="gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <Home className="h-4 w-4" />
            返回首页
          </Button>
        )}
        <h1 className="text-lg font-semibold">{title}</h1>
      </HeaderLeft>

      <HeaderRight>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          className="h-8 w-8"
        >
          {settings.theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </Button>

        <Button variant="ghost" size="icon" className="h-8 w-8 relative">
          <Bell className="h-4 w-4" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" />
        </Button>

        <Button variant="ghost" size="icon" className="h-8 w-8">
          <User className="h-4 w-4" />
        </Button>
      </HeaderRight>
    </Header>
  );
}