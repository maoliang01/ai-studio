"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  MessageSquare,
  BookOpen,
  FileText,
  Globe,
  Settings,
  Sparkles,
  ChevronDown,
  Plus,
  Bot,
  Search,
  Sliders,
  Bot as BotIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";

const navItems = [
  { href: "/", icon: MessageSquare, label: "对话" },
  { href: "/knowledge", icon: BookOpen, label: "知识库" },
  { href: "/prompts", icon: FileText, label: "提示词" },
  { href: "/scrape", icon: Globe, label: "网页爬取" },
];

const settingsSubItems = [
  { href: "/settings", icon: Sliders, label: "基础设置" },
  { href: "/settings/models", icon: BotIcon, label: "大模型配置" },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { sessions, currentSessionId, setCurrentSession } = useChatStore();
  const { toggleSidebar } = useSidebar();

  const [isChatExpanded, setIsChatExpanded] = useState(true);
  const [isSettingsExpanded, setIsSettingsExpanded] = useState(true);

  return (
    <Sidebar className="border-r border-sidebar-border">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-3 px-4 py-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
            <Sparkles className="h-4 w-4 text-primary" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold">AI Studio</span>
            <span className="text-xs text-muted-foreground">工作台</span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent className="flex flex-col">
        {/* 全局搜索 */}
        <div className="px-3 py-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="搜索..."
              className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
        </div>

        {/* 主导航 */}
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      isActive={isActive}
                      tooltip={item.label}
                      className={cn(isActive && "bg-primary/10 text-primary")}
                    >
                      <Link href={item.href} className="flex items-center gap-2 w-full">
                        <item.icon className="h-4 w-4" />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* 对话列表 */}
        <SidebarGroup className="flex-1 overflow-hidden">
          <div
            className="flex items-center justify-between px-4 py-2 cursor-pointer"
            onClick={() => setIsChatExpanded(!isChatExpanded)}
          >
            <SidebarGroupLabel className="flex items-center gap-2">
              <MessageSquare className="h-3.5 w-3.5" />
              对话
            </SidebarGroupLabel>
            <ChevronDown
              className={cn(
                "h-4 w-4 text-muted-foreground transition-transform",
                isChatExpanded && "rotate-180"
              )}
            />
          </div>
          {isChatExpanded && (
            <SidebarGroupContent className="overflow-y-auto max-h-[300px]">
              <SidebarMenu>
                {sessions.slice(0, 8).map((session) => {
                  const isActive = currentSessionId === session.id && pathname === "/";
                  return (
                    <SidebarMenuItem key={session.id}>
                      <SidebarMenuButton
                        isActive={isActive}
                        onClick={() => setCurrentSession(session.id)}
                        className={cn("w-full justify-start truncate", isActive && "bg-primary/10 text-primary")}
                      >
                        <Bot className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{session.title}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          )}
        </SidebarGroup>

        {/* 配置分组 */}
          <SidebarGroup>
            <div
              className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-sidebar-accent rounded-md mx-2"
              onClick={() => setIsSettingsExpanded(!isSettingsExpanded)}
            >
              <SidebarGroupLabel className="flex items-center gap-2">
                <Settings className="h-3.5 w-3.5" />
                配置
              </SidebarGroupLabel>
              <ChevronDown
                className={cn(
                  "h-4 w-4 text-muted-foreground transition-transform",
                  isSettingsExpanded && "rotate-180"
                )}
              />
            </div>
            {isSettingsExpanded && (
              <SidebarGroupContent className="pt-1">
                <SidebarMenu>
                  {settingsSubItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                      <SidebarMenuItem key={item.href}>
                        <SidebarMenuButton
                          isActive={isActive}
                          tooltip={item.label}
                          className={cn("pl-8", isActive && "bg-primary/10 text-primary")}
                        >
                          <Link href={item.href} className="flex items-center gap-2 w-full">
                            <item.icon className="h-4 w-4" />
                            <span>{item.label}</span>
                          </Link>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    );
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            )}
          </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        {/* 模型状态 */}
        <div className="px-3 py-2">
          <div className="rounded-lg bg-sidebar-accent p-3">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-green-500/20">
                <Bot className="h-3.5 w-3.5 text-green-500" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">GPT-4o</p>
                <p className="text-[10px] text-green-500">已连接</p>
              </div>
            </div>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}