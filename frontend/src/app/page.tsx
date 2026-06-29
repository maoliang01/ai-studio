"use client";

import { useState, useRef, useEffect } from "react";
import { useChatStore } from "@/stores/chat-store";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Send,
  Plus,
  Trash2,
  Bot,
  User,
  Copy,
  RotateCcw,
  ThumbsUp,
  MessageSquare,
  BookOpen,
  Star,
  AlertCircle,
  Square,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import type { Message } from "@/types";

export default function ChatPage() {
  const {
    sessions,
    currentSessionId,
    setCurrentSession,
    addSession,
    deleteSession,
    clearSession,
    addMessage,
    models,
    selectedModel,
    setModel,
    isStreaming,
    setStreaming,
    sendMessage,
    loadModels,
    error,
    setError,
    stopStreaming,
  } = useChatStore();

  // 初始化时加载模型列表，如果没有会话则自动创建
  useEffect(() => {
    loadModels();
    // 如果没有会话，自动创建一个
    if (sessions.length === 0) {
      addSession();
    }
  }, []);

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const currentSession = sessions.find((s) => s.id === currentSessionId);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [currentSession?.messages]);

  // 自动调整文本框高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // 处理发送消息
  const handleSend = async () => {
    if (!input.trim() || !currentSessionId || isStreaming) return;

    setError(null);
    const messageContent = input.trim();
    setInput("");

    await sendMessage(currentSessionId, messageContent);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const currentModel = models.find((m) => m.id === selectedModel);

  // 显示后端配置的所有模型
  const availableModels = models;

  return (
    <div className="flex h-full">
      {/* 左侧会话列表 */}
      <div className="w-72 border-r border-border flex flex-col bg-card/50">
        <div className="p-3 border-b border-border">
          <Button
            onClick={addSession}
            className="w-full justify-start gap-2"
            variant="default"
          >
            <Plus className="h-4 w-4" />
            新建对话
          </Button>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {sessions.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground text-sm">
                暂无对话记录
              </div>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setCurrentSession(session.id)}
                  onKeyDown={(e) => e.key === "Enter" && setCurrentSession(session.id)}
                  className={cn(
                    "w-full text-left px-3 py-2 rounded-lg text-sm transition-colors group cursor-pointer",
                    currentSessionId === session.id
                      ? "bg-primary/10 text-primary"
                      : "hover:bg-accent"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="truncate flex-1">{session.title}</span>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteSession(session.id);
                        }}
                        className="p-1 hover:text-destructive"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {new Date(session.updatedAt).toLocaleDateString("zh-CN")}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </div>

      {/* 右侧聊天区域 */}
      <div className="flex-1 flex flex-col">
        {/* 顶部工具栏 */}
        <div className="h-12 border-b border-border flex items-center justify-end px-4">
          <div className="flex items-center gap-2">
            {currentSession?.useRag && (
              <Badge variant="secondary" className="text-xs">
                <BookOpen className="h-3 w-3 mr-1" />
                RAG 模式
              </Badge>
            )}
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="px-4 py-2 bg-destructive/10 text-destructive text-sm flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {error}
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto h-6"
              onClick={() => setError(null)}
            >
              关闭
            </Button>
          </div>
        )}

        {/* 消息列表 */}
        <ScrollArea className="flex-1 p-4">
          {!currentSession || currentSession.messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <MessageSquare className="h-8 w-8 text-primary" />
              </div>
              <h2 className="text-xl font-semibold mb-2">开始新对话</h2>
              <p className="text-muted-foreground max-w-md">
                选择一个模型，开始与 AI 对话。你可以询问问题、寻求建议、或者让它帮助你完成任务。
              </p>
            </div>
          ) : (
            <div className="space-y-6 max-w-4xl mx-auto">
              {currentSession.messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    "flex gap-3 animate-message",
                    message.role === "user" && "flex-row-reverse"
                  )}
                >
                  {/* 头像 */}
                  <div
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                      message.role === "user"
                        ? "bg-primary"
                        : "bg-accent"
                    )}
                  >
                    {message.role === "user" ? (
                      <User className="h-4 w-4 text-primary-foreground" />
                    ) : (
                      <Bot className="h-4 w-4" />
                    )}
                  </div>

                  {/* 消息内容 */}
                  <div
                    className={cn(
                      "flex-1 max-w-[80%]",
                      message.role === "user" && "flex flex-col items-end"
                    )}
                  >
                    <Card
                      className={cn(
                        "p-4",
                        message.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-card"
                      )}
                    >
                      {message.role === "assistant" ? (
                        <div className="prose prose-sm dark:prose-invert max-w-none">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              code: ({ node, className, children, ...props }) => {
                                const match = /language-(\w+)/.exec(className || "");
                                const isInline = !match;
                                return isInline ? (
                                  <code className={className} {...props}>
                                    {children}
                                  </code>
                                ) : (
                                  <div className="relative group">
                                    <pre className="!mt-0 !mb-0">
                                      <code className={className} {...props}>
                                        {children}
                                      </code>
                                    </pre>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 h-8"
                                      onClick={() => {
                                        navigator.clipboard.writeText(
                                          String(children)
                                        );
                                      }}
                                    >
                                      <Copy className="h-4 w-4" />
                                    </Button>
                                  </div>
                                );
                              },
                            }}
                          >
                            {message.content}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <p className="whitespace-pre-wrap">{message.content}</p>
                      )}
                    </Card>

                    {/* 消息操作栏 */}
                    <div
                      className={cn(
                        "flex items-center gap-1 mt-1 text-xs text-muted-foreground",
                        message.role === "user" && "justify-end"
                      )}
                    >
                      <span>
                        {new Date(message.createdAt).toLocaleTimeString(
                          "zh-CN",
                          {
                            hour: "2-digit",
                            minute: "2-digit",
                          }
                        )}
                      </span>
                      {message.role === "assistant" && (
                        <>
                          <Separator orientation="vertical" className="h-3" />
                          <button className="p-1 hover:text-foreground">
                            <ThumbsUp className="h-3 w-3" />
                          </button>
                          <button
                            className="p-1 hover:text-foreground"
                            onClick={() => {
                              navigator.clipboard.writeText(message.content);
                            }}
                          >
                            <Copy className="h-3 w-3" />
                          </button>
                          <button className="p-1 hover:text-foreground">
                            <RotateCcw className="h-3 w-3" />
                          </button>
                          <button className="p-1 hover:text-foreground">
                            <Star className="h-3 w-3" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {/* 流式输出指示器 */}
              {isStreaming && (
                <div className="flex gap-3 animate-message">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent">
                    <Bot className="h-4 w-4" />
                  </div>
                  <Card className="p-4">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Bot className="h-4 w-4 animate-pulse" />
                      <span>生成中...</span>
                    </div>
                  </Card>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollArea>

        {/* 输入区域 */}
        <div className="border-t border-border p-4">
          <div className="max-w-4xl mx-auto space-y-3">
            {/* 模型选择和 RAG 开关 */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Bot className="h-4 w-4 text-muted-foreground" />
                <Select value={selectedModel} onValueChange={(value) => value && setModel(value)}>
                  <SelectTrigger className="w-[180px] h-8">
                    <SelectValue placeholder="选择模型" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableModels.length === 0 ? (
                      <div className="p-2 text-sm text-muted-foreground">
                        暂无可用模型
                      </div>
                    ) : (
                      availableModels.map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          {model.name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
                {currentModel && (
                  <span className="text-xs text-muted-foreground">
                    {currentModel.provider}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-muted-foreground" />
                <Label htmlFor="rag-mode" className="text-sm cursor-pointer">
                  RAG
                </Label>
                <Switch
                  id="rag-mode"
                  checked={currentSession?.useRag || false}
                  onCheckedChange={() =>
                    currentSessionId &&
                    useChatStore.getState().toggleRag(currentSessionId)
                  }
                  className="scale-90"
                />
              </div>
            </div>

            {/* 输入框 */}
            <Card className="p-2">
              <div className="flex items-end gap-2">
                <Textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="输入消息，Shift+Enter 换行..."
                  className="flex-1 min-h-[24px] max-h-[200px] resize-none border-0 p-0 focus-visible:ring-0 focus-visible:ring-offset-0"
                  rows={1}
                  disabled={isStreaming}
                />
                {isStreaming ? (
                  <Button
                    size="icon"
                    onClick={stopStreaming}
                    className="shrink-0 h-8 w-8 bg-destructive hover:bg-destructive/90"
                  >
                    <Square className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button
                    size="icon"
                    onClick={handleSend}
                    disabled={!input.trim() || isStreaming}
                    className="shrink-0 h-8 w-8"
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </Card>
            <p className="text-xs text-muted-foreground text-center">
              Enter 发送 · Shift+Enter 换行
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}