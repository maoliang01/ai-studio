"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
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
import { Plus, Trash2, Download, Link2, Loader2, ScanSearch } from "lucide-react";
import {
  fetchWechatAccounts,
  createWechatAccount,
  createWechatAccountFromArticle,
  deleteWechatAccount,
  type WechatAccount,
} from "@/lib/api";

export default function WechatAccountPage() {
  const router = useRouter();
  const [accounts, setAccounts] = useState<WechatAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newAccount, setNewAccount] = useState({ name: "", wechatId: "", description: "" });
  const [sampleArticleUrl, setSampleArticleUrl] = useState("");
  const [identifying, setIdentifying] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // 加载公众号列表
  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      setLoading(true);
      const data = await fetchWechatAccounts();
      setAccounts(data);
    } catch (error) {
      console.error("加载公众号列表失败:", error);
    } finally {
      setLoading(false);
    }
  };

  // 创建公众号
  const handleCreate = async () => {
    try {
      const result = await createWechatAccount({
        name: newAccount.name,
        wechatId: newAccount.wechatId || undefined,
        description: newAccount.description || undefined,
      });
      if (result.success) {
        setDialogOpen(false);
        setNewAccount({ name: "", wechatId: "", description: "" });
        loadAccounts();
        if (result.item?.id) router.push(`/settings/wechat?mode=account&accountId=${encodeURIComponent(result.item.id)}`);
      }
    } catch (error) {
      console.error("创建公众号失败:", error);
    }
  };

  const handleCreateFromArticle = async () => {
    setCreateError(null);
    if (!/^https?:\/\/mp\.weixin\.qq\.com\/s(?:\/|\?|$)/i.test(sampleArticleUrl.trim())) {
      setCreateError("请输入有效的 mp.weixin.qq.com/s/... 公众号文章链接。");
      return;
    }
    try {
      setIdentifying(true);
      const result = await createWechatAccountFromArticle(sampleArticleUrl.trim());
      if (!result.item?.id) throw new Error("识别成功，但未生成公众号档案");
      setDialogOpen(false);
      setSampleArticleUrl("");
      setCreateError(null);
      await loadAccounts();
      router.push(`/settings/wechat?mode=account&accountId=${encodeURIComponent(result.item.id)}`);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "从文章识别公众号失败");
    } finally {
      setIdentifying(false);
    }
  };

  // 删除公众号
  const handleDelete = async (id: string) => {
    try {
      await deleteWechatAccount(id);
      loadAccounts();
    } catch (error) {
      console.error("删除公众号失败:", error);
    }
  };

  // 立即爬取
  const handleCrawl = (id: string) => {
    router.push(`/settings/wechat?mode=account&accountId=${encodeURIComponent(id)}`);
  };

  return (
    <div className="container mx-auto py-6">
      <Card>
        <CardHeader>
          <CardTitle>公众号管理</CardTitle>
          <CardDescription>管理要爬取的微信公众号</CardDescription>
        </CardHeader>
        <CardContent>
          {/* 操作栏 */}
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-medium">公众号列表</h3>
            <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) setCreateError(null); }}>
              <DialogTrigger render={<Button />}>
                <Plus className="mr-2 h-4 w-4" />
                添加公众号
              </DialogTrigger>
              <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                  <DialogTitle>从典型文章创建公众号档案</DialogTitle>
                  <DialogDescription>
                    粘贴该公众号发布过的一篇公开文章，系统会读取页面显示的准确公众号名称并保存档案。
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-5">
                  <div className="space-y-2">
                    <Label htmlFor="sampleArticleUrl">典型文章链接 *</Label>
                    <div className="relative">
                      <Link2 className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input
                        id="sampleArticleUrl"
                        className="pl-9"
                        value={sampleArticleUrl}
                        onChange={(event) => setSampleArticleUrl(event.target.value)}
                        placeholder="https://mp.weixin.qq.com/s/..."
                        disabled={identifying}
                      />
                    </div>
                    <p className="text-xs leading-5 text-muted-foreground">请使用已经正式发布、在浏览器中可以正常打开的文章链接，不要使用预览链接。</p>
                  </div>

                  {createError && <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{createError}</div>}

                  <Button className="w-full" onClick={handleCreateFromArticle} disabled={identifying || !sampleArticleUrl.trim()}>
                    {identifying ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ScanSearch className="mr-2 h-4 w-4" />}
                    {identifying ? "正在识别公众号…" : "识别并创建档案"}
                  </Button>

                  <details className="rounded-md border px-4 py-3">
                    <summary className="cursor-pointer text-sm font-medium">无法识别？改为手工填写</summary>
                    <div className="mt-4 space-y-4">
                  <div>
                    <Label htmlFor="name">公众号名称 *</Label>
                    <Input
                      id="name"
                      value={newAccount.name}
                      onChange={(e) => setNewAccount({ ...newAccount, name: e.target.value })}
                      placeholder="例如：人民日报"
                    />
                  </div>
                  <div>
                    <Label htmlFor="wechatId">公众号 ID (可选)</Label>
                    <Input
                      id="wechatId"
                      value={newAccount.wechatId}
                      onChange={(e) => setNewAccount({ ...newAccount, wechatId: e.target.value })}
                      placeholder="例如：gh_xxxxxxxxxxxx"
                    />
                  </div>
                  <div>
                    <Label htmlFor="description">描述 (可选)</Label>
                    <Textarea
                      id="description"
                      value={newAccount.description}
                      onChange={(e) => setNewAccount({ ...newAccount, description: e.target.value })}
                      placeholder="公众号描述"
                      rows={3}
                    />
                  </div>
                    <Button variant="outline" className="w-full" onClick={handleCreate} disabled={!newAccount.name.trim()}>保存手工档案</Button>
                    </div>
                  </details>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setDialogOpen(false)}>
                    取消
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          {/* 公众号列表表格 */}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>公众号名称</TableHead>
                <TableHead>ID</TableHead>
                <TableHead>文章数</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center">
                    加载中...
                  </TableCell>
                </TableRow>
              ) : accounts.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    暂无公众号
                  </TableCell>
                </TableRow>
              ) : (
                accounts.map((account) => (
                  <TableRow key={account.id}>
                    <TableCell className="font-medium">{account.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {account.wechatId || "-"}
                    </TableCell>
                    <TableCell>{account.articleCount}</TableCell>
                    <TableCell>
                      {account.isEnabled ? (
                        <Badge variant="default">启用</Badge>
                      ) : (
                        <Badge variant="secondary">禁用</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleCrawl(account.id)}
                        >
                          <Download className="mr-1 h-4 w-4" />
                          配置爬取
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
                              <AlertDialogAction onClick={() => handleDelete(account.id)}>
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
