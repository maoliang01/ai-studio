"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Plus,
  Trash2,
  Play,
  Pause,
  RefreshCw,
  Settings,
  Cookie,
  Users,
  Clock,
  ExternalLink,
} from "lucide-react";
import {
  fetchWechatCookies,
  createWechatCookie,
  deleteWechatCookie,
  activateWechatCookie,
  deactivateWechatCookie,
  validateWechatCookie,
  fetchWechatAccounts,
  createWechatAccount,
  deleteWechatAccount,
  crawlWechatAccount,
  fetchWechatTasks,
  createWechatTask,
  deleteWechatTask,
  toggleWechatTask,
  runWechatTask,
  type WechatCookie,
  type WechatAccount,
  type WechatTask,
} from "@/lib/api";
import Link from "next/link";

export default function WechatPage() {
  const [activeTab, setActiveTab] = useState("accounts");

  // 数据状态
  const [cookies, setCookies] = useState<WechatCookie[]>([]);
  const [accounts, setAccounts] = useState<WechatAccount[]>([]);
  const [tasks, setTasks] = useState<WechatTask[]>([]);

  // 加载状态
  const [loadingCookies, setLoadingCookies] = useState(true);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [loadingTasks, setLoadingTasks] = useState(true);

  // Cookie 对话框状态
  const [cookieDialogOpen, setCookieDialogOpen] = useState(false);
  const [newCookie, setNewCookie] = useState({ name: "", cookieData: "" });
  const [validating, setValidating] = useState<string | null>(null);

  // 公众号对话框状态
  const [accountDialogOpen, setAccountDialogOpen] = useState(false);
  const [newAccount, setNewAccount] = useState({ name: "", wechatId: "", description: "" });
  const [crawling, setCrawling] = useState<string | null>(null);

  // 任务对话框状态
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);
  const [newTask, setNewTask] = useState({
    accountId: "",
    scheduleType: "daily",
    scheduleTime: "02:00",
    maxArticles: 20,
  });

  // 加载数据
  useEffect(() => {
    loadCookies();
    loadAccounts();
    loadTasks();
  }, []);

  const loadCookies = async () => {
    try {
      setLoadingCookies(true);
      const data = await fetchWechatCookies();
      setCookies(data);
    } catch (error) {
      console.error("加载 Cookie 列表失败:", error);
    } finally {
      setLoadingCookies(false);
    }
  };

  const loadAccounts = async () => {
    try {
      setLoadingAccounts(true);
      const data = await fetchWechatAccounts();
      setAccounts(data);
    } catch (error) {
      console.error("加载公众号列表失败:", error);
    } finally {
      setLoadingAccounts(false);
    }
  };

  const loadTasks = async () => {
    try {
      setLoadingTasks(true);
      const data = await fetchWechatTasks();
      setTasks(data);
    } catch (error) {
      console.error("加载任务列表失败:", error);
    } finally {
      setLoadingTasks(false);
    }
  };

  // Cookie 操作
  const handleCreateCookie = async () => {
    try {
      const result = await createWechatCookie({
        name: newCookie.name,
        cookieData: newCookie.cookieData,
      });
      if (result.success) {
        setCookieDialogOpen(false);
        setNewCookie({ name: "", cookieData: "" });
        loadCookies();
      }
    } catch (error) {
      console.error("创建 Cookie 失败:", error);
    }
  };

  const handleDeleteCookie = async (id: string) => {
    try {
      await deleteWechatCookie(id);
      loadCookies();
    } catch (error) {
      console.error("删除 Cookie 失败:", error);
    }
  };

  const handleActivateCookie = async (id: string) => {
    try {
      await activateWechatCookie(id);
      loadCookies();
    } catch (error) {
      console.error("激活 Cookie 失败:", error);
    }
  };

  const handleDeactivateCookie = async (id: string) => {
    try {
      await deactivateWechatCookie(id);
      loadCookies();
    } catch (error) {
      console.error("停用 Cookie 失败:", error);
    }
  };

  const handleValidateCookie = async (id: string) => {
    try {
      setValidating(id);
      const result = await validateWechatCookie(id);
      alert(result.message);
    } catch (error) {
      console.error("验证 Cookie 失败:", error);
    } finally {
      setValidating(null);
    }
  };

  // 公众号操作
  const handleCreateAccount = async () => {
    try {
      const result = await createWechatAccount({
        name: newAccount.name,
        wechatId: newAccount.wechatId,
        description: newAccount.description,
      });
      if (result.success) {
        setAccountDialogOpen(false);
        setNewAccount({ name: "", wechatId: "", description: "" });
        loadAccounts();
      }
    } catch (error) {
      console.error("创建公众号失败:", error);
    }
  };

  const handleDeleteAccount = async (id: string) => {
    try {
      await deleteWechatAccount(id);
      loadAccounts();
    } catch (error) {
      console.error("删除公众号失败:", error);
    }
  };

  const handleCrawlAccount = async (id: string) => {
    try {
      setCrawling(id);
      const result = await crawlWechatAccount(id, 10);
      alert(result.message || "爬取任务已提交");
      loadAccounts();
    } catch (error) {
      console.error("爬取公众号失败:", error);
      alert("爬取失败，请检查 Cookie 是否有效");
    } finally {
      setCrawling(null);
    }
  };

  // 任务操作
  const handleCreateTask = async () => {
    try {
      const result = await createWechatTask({
        accountId: newTask.accountId,
        scheduleType: newTask.scheduleType,
        scheduleTime: newTask.scheduleTime,
        maxArticles: newTask.maxArticles,
      });
      if (result.success) {
        setTaskDialogOpen(false);
        setNewTask({
          accountId: "",
          scheduleType: "daily",
          scheduleTime: "02:00",
          maxArticles: 20,
        });
        loadTasks();
      }
    } catch (error) {
      console.error("创建任务失败:", error);
    }
  };

  const handleDeleteTask = async (id: string) => {
    try {
      await deleteWechatTask(id);
      loadTasks();
    } catch (error) {
      console.error("删除任务失败:", error);
    }
  };

  const handleToggleTask = async (id: string) => {
    try {
      await toggleWechatTask(id);
      loadTasks();
    } catch (error) {
      console.error("切换任务状态失败:", error);
    }
  };

  const handleRunTask = async (id: string) => {
    try {
      await runWechatTask(id);
      alert("任务已启动");
    } catch (error) {
      console.error("执行任务失败:", error);
    }
  };

  return (
    <div className="container mx-auto py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">公众号爬取</h1>
          <p className="text-muted-foreground">管理微信公众号的爬取任务和配置</p>
        </div>
        <div className="flex gap-2">
          <Link href="/settings/wechat">
            <Button variant="outline">
              <Settings className="mr-2 h-4 w-4" />
              高级配置
            </Button>
          </Link>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="accounts" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            公众号管理
          </TabsTrigger>
          <TabsTrigger value="cookies" className="flex items-center gap-2">
            <Cookie className="h-4 w-4" />
            Cookie 管理
          </TabsTrigger>
          <TabsTrigger value="tasks" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            定时任务
          </TabsTrigger>
        </TabsList>

        {/* 公众号管理 */}
        <TabsContent value="accounts">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>公众号列表</CardTitle>
                  <CardDescription>管理要爬取的微信公众号</CardDescription>
                </div>
                <Dialog open={accountDialogOpen} onOpenChange={setAccountDialogOpen}>
                  <DialogTrigger>
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      添加公众号
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>添加公众号</DialogTitle>
                      <DialogDescription>添加要爬取的微信公众号</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div>
                        <Label htmlFor="accountName">公众号名称</Label>
                        <Input
                          id="accountName"
                          value={newAccount.name}
                          onChange={(e) => setNewAccount({ ...newAccount, name: e.target.value })}
                          placeholder="例如：36氪"
                        />
                      </div>
                      <div>
                        <Label htmlFor="wechatId">微信号 (可选)</Label>
                        <Input
                          id="wechatId"
                          value={newAccount.wechatId}
                          onChange={(e) => setNewAccount({ ...newAccount, wechatId: e.target.value })}
                          placeholder="例如：wow36kr"
                        />
                      </div>
                      <div>
                        <Label htmlFor="accountDesc">描述 (可选)</Label>
                        <Textarea
                          id="accountDesc"
                          value={newAccount.description}
                          onChange={(e) => setNewAccount({ ...newAccount, description: e.target.value })}
                          placeholder="公众号的简要描述"
                          rows={3}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setAccountDialogOpen(false)}>
                        取消
                      </Button>
                      <Button onClick={handleCreateAccount}>添加</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>微信号</TableHead>
                    <TableHead>文章数</TableHead>
                    <TableHead>上次爬取</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loadingAccounts ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center">
                        加载中...
                      </TableCell>
                    </TableRow>
                  ) : accounts.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-muted-foreground">
                        暂无公众号，请先添加
                      </TableCell>
                    </TableRow>
                  ) : (
                    accounts.map((account) => (
                      <TableRow key={account.id}>
                        <TableCell className="font-medium">{account.name}</TableCell>
                        <TableCell>{account.wechatId || "-"}</TableCell>
                        <TableCell>{account.articleCount}</TableCell>
                        <TableCell>
                          {account.lastCrawledAt
                            ? new Date(account.lastCrawledAt).toLocaleString()
                            : "未爬取"}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleCrawlAccount(account.id)}
                              disabled={crawling === account.id || !account.isEnabled}
                            >
                              {crawling === account.id ? (
                                <RefreshCw className="mr-1 h-3 w-3 animate-spin" />
                              ) : (
                                <Play className="mr-1 h-3 w-3" />
                              )}
                              立即爬取
                            </Button>
                            <AlertDialog>
                              <AlertDialogTrigger render={<Button variant="destructive" size="sm" />}>
                                <Trash2 className="h-4 w-4" />
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>确认删除</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    确定要删除公众号 "{account.name}" 吗？此操作不可撤销。
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>取消</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => handleDeleteAccount(account.id)}>
                                    删除
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Cookie 管理 */}
        <TabsContent value="cookies">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Cookie 管理</CardTitle>
                  <CardDescription>管理微信公众号爬取所需的 Cookie</CardDescription>
                </div>
                <Dialog open={cookieDialogOpen} onOpenChange={setCookieDialogOpen}>
                  <DialogTrigger>
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      添加 Cookie
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>添加 Cookie</DialogTitle>
                      <DialogDescription>
                        粘贴从浏览器导出的 Cookie JSON 数据
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div>
                        <Label htmlFor="cookieName">名称</Label>
                        <Input
                          id="cookieName"
                          value={newCookie.name}
                          onChange={(e) => setNewCookie({ ...newCookie, name: e.target.value })}
                          placeholder="例如：主账号"
                        />
                      </div>
                      <div>
                        <Label htmlFor="cookieData">Cookie 数据 (JSON)</Label>
                        <Textarea
                          id="cookieData"
                          value={newCookie.cookieData}
                          onChange={(e) => setNewCookie({ ...newCookie, cookieData: e.target.value })}
                          placeholder='[{"name": "xxx", "value": "xxx", ...}]'
                          rows={10}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setCookieDialogOpen(false)}>
                        取消
                      </Button>
                      <Button onClick={handleCreateCookie}>添加</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              {/* 浏览器插件推荐 */}
              <div className="mb-6 p-4 bg-muted rounded-lg">
                <h3 className="text-sm font-medium mb-2">📌 浏览器插件推荐</h3>
                <p className="text-sm text-muted-foreground mb-2">
                  推荐使用以下插件导出微信公众号后台的 Cookie：
                </p>
                <div className="flex gap-2">
                  <Button nativeButton={false} variant="outline" size="sm" render={<a href="https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg" target="_blank" rel="noopener noreferrer" />}>
                    <ExternalLink className="mr-2 h-4 w-4" />
                    EditThisCookie
                  </Button>
                  <Button nativeButton={false} variant="outline" size="sm" render={<a href="https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicpkgkpgjmnem" target="_blank" rel="noopener noreferrer" />}>
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Cookie-Editor
                  </Button>
                </div>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>过期时间</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loadingCookies ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center">
                        加载中...
                      </TableCell>
                    </TableRow>
                  ) : cookies.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-muted-foreground">
                        暂无 Cookie
                      </TableCell>
                    </TableRow>
                  ) : (
                    cookies.map((cookie) => (
                      <TableRow key={cookie.id}>
                        <TableCell>{cookie.name}</TableCell>
                        <TableCell>
                          {cookie.isActive ? (
                            <Badge variant="default">激活</Badge>
                          ) : (
                            <Badge variant="secondary">停用</Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          {cookie.expiresAt ? new Date(cookie.expiresAt).toLocaleDateString() : "-"}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleValidateCookie(cookie.id)}
                              disabled={validating === cookie.id}
                            >
                              {validating === cookie.id ? "验证中..." : "验证"}
                            </Button>
                            {cookie.isActive ? (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleDeactivateCookie(cookie.id)}
                              >
                                停用
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleActivateCookie(cookie.id)}
                              >
                                激活
                              </Button>
                            )}
                            <AlertDialog>
                              <AlertDialogTrigger render={<Button variant="destructive" size="sm" />}>
                                <Trash2 className="h-4 w-4" />
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>确认删除</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    确定要删除 Cookie "{cookie.name}" 吗？此操作不可撤销。
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>取消</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => handleDeleteCookie(cookie.id)}>
                                    删除
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 定时任务 */}
        <TabsContent value="tasks">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>定时任务</CardTitle>
                  <CardDescription>管理定时爬取任务</CardDescription>
                </div>
                <Dialog open={taskDialogOpen} onOpenChange={setTaskDialogOpen}>
                  <DialogTrigger>
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      创建任务
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>创建定时任务</DialogTitle>
                      <DialogDescription>创建定时爬取任务</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div>
                        <Label htmlFor="taskAccount">选择公众号 *</Label>
                        <select
                          id="taskAccount"
                          value={newTask.accountId}
                          onChange={(e) => setNewTask({ ...newTask, accountId: e.target.value })}
                          className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                        >
                          <option value="">请选择公众号</option>
                          {accounts.map((account) => (
                            <option key={account.id} value={account.id}>
                              {account.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <Label htmlFor="scheduleType">定时类型 *</Label>
                        <select
                          id="scheduleType"
                          value={newTask.scheduleType}
                          onChange={(e) => setNewTask({ ...newTask, scheduleType: e.target.value })}
                          className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                        >
                          <option value="daily">每天</option>
                          <option value="weekly">每周</option>
                          <option value="monthly">每月</option>
                        </select>
                      </div>
                      <div>
                        <Label htmlFor="scheduleTime">执行时间</Label>
                        <Input
                          id="scheduleTime"
                          type="time"
                          value={newTask.scheduleTime}
                          onChange={(e) => setNewTask({ ...newTask, scheduleTime: e.target.value })}
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          选择每天执行的时间
                        </p>
                      </div>
                      <div>
                        <Label htmlFor="maxArticles">最大文章数</Label>
                        <Input
                          id="maxArticles"
                          type="number"
                          value={newTask.maxArticles}
                          onChange={(e) => setNewTask({ ...newTask, maxArticles: parseInt(e.target.value) || 20 })}
                          min={1}
                          max={100}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setTaskDialogOpen(false)}>
                        取消
                      </Button>
                      <Button onClick={handleCreateTask}>创建</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>公众号</TableHead>
                    <TableHead>定时类型</TableHead>
                    <TableHead>执行时间</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>上次执行</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loadingTasks ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center">
                        加载中...
                      </TableCell>
                    </TableRow>
                  ) : tasks.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        暂无定时任务
                      </TableCell>
                    </TableRow>
                  ) : (
                    tasks.map((task) => (
                      <TableRow key={task.id}>
                        <TableCell className="font-medium">
                          {accounts.find((a) => a.id === task.accountId)?.name || "未知"}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {task.scheduleType === "daily" ? "每天" : task.scheduleType === "weekly" ? "每周" : "每月"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {task.scheduleTime || "02:00"}
                        </TableCell>
                        <TableCell>
                          {task.isEnabled ? (
                            <Badge variant="default">启用</Badge>
                          ) : (
                            <Badge variant="secondary">禁用</Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          {task.lastRunAt
                            ? new Date(task.lastRunAt).toLocaleString()
                            : "未执行"}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleRunTask(task.id)}
                            >
                              <Play className="mr-1 h-3 w-3" />
                              立即执行
                            </Button>
                            {task.isEnabled ? (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleToggleTask(task.id)}
                              >
                                <Pause className="mr-1 h-3 w-3" />
                                禁用
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleToggleTask(task.id)}
                              >
                                <Play className="mr-1 h-3 w-3" />
                                启用
                              </Button>
                            )}
                            <AlertDialog>
                              <AlertDialogTrigger render={<Button variant="destructive" size="sm" />}>
                                <Trash2 className="h-4 w-4" />
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>确认删除</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    确定要删除该任务吗？此操作不可撤销。
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>取消</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => handleDeleteTask(task.id)}>
                                    删除
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
