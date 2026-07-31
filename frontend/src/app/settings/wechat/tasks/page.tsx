"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
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
import { Plus, Trash2, Play, Pause } from "lucide-react";
import {
  fetchWechatTasks,
  createWechatTask,
  deleteWechatTask,
  toggleWechatTask,
  runWechatTask,
  fetchWechatAccounts,
  type WechatTask,
  type WechatAccount,
} from "@/lib/api";

export default function WechatTaskPage() {
  const [tasks, setTasks] = useState<WechatTask[]>([]);
  const [accounts, setAccounts] = useState<WechatAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newTask, setNewTask] = useState({
    accountId: "",
    scheduleType: "daily",
    scheduleTime: "09:00",
    maxArticles: 10,
    isEnabled: true,
  });
  const [running, setRunning] = useState<string | null>(null);

  // 加载数据
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [tasksData, accountsData] = await Promise.all([
        fetchWechatTasks(),
        fetchWechatAccounts(),
      ]);
      setTasks(tasksData);
      setAccounts(accountsData);
    } catch (error) {
      console.error("加载数据失败:", error);
    } finally {
      setLoading(false);
    }
  };

  // 创建定时任务
  const handleCreate = async () => {
    try {
      const result = await createWechatTask({
        accountId: newTask.accountId,
        scheduleType: newTask.scheduleType,
        scheduleTime: newTask.scheduleTime,
        maxArticles: newTask.maxArticles,
        isEnabled: newTask.isEnabled,
      });
      if (result.success) {
        setDialogOpen(false);
        setNewTask({
          accountId: "",
          scheduleType: "daily",
          scheduleTime: "09:00",
          maxArticles: 10,
          isEnabled: true,
        });
        loadData();
      }
    } catch (error) {
      console.error("创建定时任务失败:", error);
    }
  };

  // 删除定时任务
  const handleDelete = async (id: string) => {
    try {
      await deleteWechatTask(id);
      loadData();
    } catch (error) {
      console.error("删除定时任务失败:", error);
    }
  };

  // 切换任务状态
  const handleToggle = async (id: string) => {
    try {
      await toggleWechatTask(id);
      loadData();
    } catch (error) {
      console.error("切换任务状态失败:", error);
    }
  };

  // 立即执行任务
  const handleRun = async (id: string) => {
    try {
      setRunning(id);
      const result = await runWechatTask(id);
      alert(result.message || "任务已提交执行");
      loadData();
    } catch (error) {
      console.error("执行任务失败:", error);
    } finally {
      setRunning(null);
    }
  };

  // 获取公众号名称
  const getAccountName = (accountId: string) => {
    const account = accounts.find((a) => a.id === accountId);
    return account?.name || "未知";
  };

  // 获取定时类型标签
  const getScheduleTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      daily: "每天",
      weekly: "每周",
      monthly: "每月",
    };
    return labels[type] || type;
  };

  return (
    <div className="container mx-auto py-6">
      <Card>
        <CardHeader>
          <CardTitle>定时任务</CardTitle>
          <CardDescription>管理公众号爬取的定时任务</CardDescription>
        </CardHeader>
        <CardContent>
          {/* 操作栏 */}
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-medium">任务列表</h3>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger render={<Button />}>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  创建任务
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>创建定时任务</DialogTitle>
                  <DialogDescription>
                    设置公众号爬取的定时任务
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="account">公众号 *</Label>
                    <Select
                      value={newTask.accountId}
                      onValueChange={(value) => setNewTask({ ...newTask, accountId: value || "" })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="选择公众号" />
                      </SelectTrigger>
                      <SelectContent>
                        {accounts.map((account) => (
                          <SelectItem key={account.id} value={account.id}>
                            {account.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="scheduleType">定时类型 *</Label>
                    <Select
                      value={newTask.scheduleType}
                      onValueChange={(value) => setNewTask({ ...newTask, scheduleType: value || "daily" })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="daily">每天</SelectItem>
                        <SelectItem value="weekly">每周</SelectItem>
                        <SelectItem value="monthly">每月</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="scheduleTime">执行时间</Label>
                    <Input
                      id="scheduleTime"
                      type="time"
                      value={newTask.scheduleTime}
                      onChange={(e) => setNewTask({ ...newTask, scheduleTime: e.target.value })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="maxArticles">最大文章数</Label>
                    <Input
                      id="maxArticles"
                      type="number"
                      min={1}
                      max={100}
                      value={newTask.maxArticles}
                      onChange={(e) => setNewTask({ ...newTask, maxArticles: parseInt(e.target.value) || 10 })}
                    />
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      id="isEnabled"
                      checked={newTask.isEnabled}
                      onCheckedChange={(checked) => setNewTask({ ...newTask, isEnabled: checked })}
                    />
                    <Label htmlFor="isEnabled">启用任务</Label>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setDialogOpen(false)}>
                    取消
                  </Button>
                  <Button onClick={handleCreate}>创建</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          {/* 任务列表表格 */}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>公众号</TableHead>
                <TableHead>定时类型</TableHead>
                <TableHead>执行时间</TableHead>
                <TableHead>最大文章数</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>上次执行</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center">
                    加载中...
                  </TableCell>
                </TableRow>
              ) : tasks.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground">
                    暂无定时任务
                  </TableCell>
                </TableRow>
              ) : (
                tasks.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell className="font-medium">
                      {getAccountName(task.accountId)}
                    </TableCell>
                    <TableCell>{getScheduleTypeLabel(task.scheduleType)}</TableCell>
                    <TableCell>{task.scheduleTime || "-"}</TableCell>
                    <TableCell>{task.maxArticles}</TableCell>
                    <TableCell>
                      {task.isEnabled ? (
                        <Badge variant="default">启用</Badge>
                      ) : (
                        <Badge variant="secondary">禁用</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {task.lastRunAt ? new Date(task.lastRunAt).toLocaleString() : "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRun(task.id)}
                          disabled={running === task.id}
                        >
                          <Play className="mr-1 h-4 w-4" />
                          {running === task.id ? "执行中..." : "执行"}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleToggle(task.id)}
                        >
                          {task.isEnabled ? (
                            <Pause className="h-4 w-4" />
                          ) : (
                            <Play className="h-4 w-4" />
                          )}
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger render={<Button variant="destructive" size="sm" />}>
                            <Trash2 className="h-4 w-4" />
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>确认删除</AlertDialogTitle>
                              <AlertDialogDescription>
                                确定要删除这个定时任务吗？此操作不可撤销。
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>取消</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDelete(task.id)}>
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
    </div>
  );
}
