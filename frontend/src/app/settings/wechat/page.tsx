"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  Cookie,
  ExternalLink,
  FileText,
  Globe2,
  Info,
  Loader2,
  Pencil,
  Play,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  activateWechatCookie,
  crawlWechatArticles,
  createWechatCookie,
  deactivateWechatCookie,
  deleteWechatCookie,
  fetchWechatCookies,
  fetchWechatCrawlJob,
  fetchWechatAccounts,
  crawlWechatAccountRange,
  startWechatPublicDiscovery,
  fetchWechatPublicDiscoveryJob,
  ingestWechatPublicDiscoveryCandidates,
  validateWechatCookie,
  updateWechatCookie,
  type WechatCookie,
  type WechatCrawlJob,
  type WechatAccount,
  type WechatPublicDiscoveryJob,
} from "@/lib/api";

const WECHAT_ARTICLE_PATTERN = /^https?:\/\/mp\.weixin\.qq\.com\/s(?:\/|\?|$)/i;

function parseArticleUrls(value: string) {
  return Array.from(
    new Set(
      value
        .split(/[\n,，\s]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

export default function WechatSettingsPage() {
  const today = new Date().toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const [crawlMode, setCrawlMode] = useState<"account" | "urls" | "public">("account");
  const [accounts, setAccounts] = useState<WechatAccount[]>([]);
  const [accountId, setAccountId] = useState("");
  const [startDate, setStartDate] = useState(monthAgo);
  const [endDate, setEndDate] = useState(today);
  const [maxArticles, setMaxArticles] = useState(50);
  const [repeatIntervalMinutes, setRepeatIntervalMinutes] = useState(60);
  const [articleUrls, setArticleUrls] = useState("");
  const [publicSeedUrls, setPublicSeedUrls] = useState("");
  const [publicJob, setPublicJob] = useState<WechatPublicDiscoveryJob | null>(null);
  const [selectedPublicUrls, setSelectedPublicUrls] = useState<string[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [crawlJob, setCrawlJob] = useState<WechatCrawlJob | null>(null);

  const [cookies, setCookies] = useState<WechatCookie[]>([]);
  const [loadingCookies, setLoadingCookies] = useState(true);
  const [cookieName, setCookieName] = useState("");
  const [cookieData, setCookieData] = useState("");
  const [savingCookie, setSavingCookie] = useState(false);
  const [validatingCookie, setValidatingCookie] = useState<string | null>(null);
  const [cookieMessage, setCookieMessage] = useState<string | null>(null);
  const [editingCookieId, setEditingCookieId] = useState<string | null>(null);

  const urls = useMemo(() => parseArticleUrls(articleUrls), [articleUrls]);
  const publicSeeds = useMemo(() => parseArticleUrls(publicSeedUrls), [publicSeedUrls]);
  const invalidPublicSeeds = useMemo(() => publicSeeds.filter((url) => !WECHAT_ARTICLE_PATTERN.test(url)), [publicSeeds]);
  const invalidUrls = useMemo(() => urls.filter((url) => !WECHAT_ARTICLE_PATTERN.test(url)), [urls]);
  const selectedAccount = useMemo(() => accounts.find((item) => item.id === accountId), [accounts, accountId]);
  const activeCookie = useMemo(() => cookies.find((item) => item.isActive), [cookies]);

  const loadCookies = async () => {
    try {
      setLoadingCookies(true);
      setCookies(await fetchWechatCookies());
    } catch (error) {
      setCookieMessage(error instanceof Error ? error.message : "Cookie 列表加载失败");
    } finally {
      setLoadingCookies(false);
    }
  };

  useEffect(() => {
    void loadCookies();
    void fetchWechatAccounts().then((items) => {
      setAccounts(items);
      const params = new URLSearchParams(window.location.search);
      const selected = params.get("accountId");
      if (selected && items.some((item) => item.id === selected)) {
        setAccountId(selected);
        setRepeatIntervalMinutes(items.find((item) => item.id === selected)?.minCrawlIntervalMinutes || 60);
      } else if (items[0]) {
        setAccountId(items[0].id);
        setRepeatIntervalMinutes(items[0].minCrawlIntervalMinutes || 60);
      }
      if (params.get("mode") === "urls") setCrawlMode("urls");
    });
  }, []);

  useEffect(() => {
    if (!crawlJob || !["pending", "running"].includes(crawlJob.status)) return;
    const timer = window.setTimeout(async () => {
      try {
        setCrawlJob(await fetchWechatCrawlJob(crawlJob.job_id));
      } catch (error) {
        setSubmitMessage({ type: "error", text: error instanceof Error ? error.message : "获取爬取结果失败" });
      }
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [crawlJob]);

  useEffect(() => {
    if (!publicJob || !["pending", "running", "ingesting"].includes(publicJob.status)) return;
    const timer = window.setTimeout(async () => {
      try {
        setPublicJob(await fetchWechatPublicDiscoveryJob(publicJob.job_id));
      } catch (error) {
        setSubmitMessage({ type: "error", text: error instanceof Error ? error.message : "获取公开来源发现结果失败" });
      }
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [publicJob]);

  useEffect(() => {
    if (publicJob?.status === "completed" && selectedPublicUrls.length === 0) {
      setSelectedPublicUrls(publicJob.candidates.filter((item) => item.eligible).map((item) => item.url));
    }
  }, [publicJob?.status, publicJob?.candidates, selectedPublicUrls.length]);

  useEffect(() => {
    if (crawlJob?.status === "failed") {
      console.error("公众号爬取失败", crawlJob);
    }
  }, [crawlJob?.status]);

  const handleCrawl = async () => {
    setSubmitMessage(null);
    if (urls.length === 0) {
      setSubmitMessage({ type: "error", text: "请至少粘贴一个公众号文章链接。" });
      return;
    }
    if (invalidUrls.length > 0) {
      setSubmitMessage({ type: "error", text: `有 ${invalidUrls.length} 个链接不是 mp.weixin.qq.com 公众号文章地址。` });
      return;
    }

    try {
      setSubmitting(true);
      setCrawlJob(null);
      const result = await crawlWechatArticles({
        urls,
        categoryId: categoryId.trim() || undefined,
      });
      if (!result.success) throw new Error(result.message || "提交失败");
      const jobId = result.job_id || result.jobId;
      if (!jobId) throw new Error("后端未返回任务 ID，无法跟踪爬取结果");
      setCrawlJob({
        job_id: jobId,
        status: "pending",
        total: urls.length,
        success_count: 0,
        failed_count: 0,
        message: result.message || `已提交 ${urls.length} 篇文章的爬取任务。`,
        results: [],
      });
      setSubmitMessage({ type: "success", text: result.message || `已提交 ${urls.length} 篇文章的爬取任务。` });
    } catch (error) {
      setSubmitMessage({ type: "error", text: error instanceof Error ? error.message : "提交爬取任务失败" });
    } finally {
      setSubmitting(false);
    }
  };

  const handleAccountRangeCrawl = async () => {
    setSubmitMessage(null);
    if (!accountId) {
      setSubmitMessage({ type: "error", text: "请先选择公众号。" });
      return;
    }
    if (!startDate || !endDate || startDate > endDate) {
      setSubmitMessage({ type: "error", text: "请选择正确的起止日期。" });
      return;
    }
    try {
      setSubmitting(true);
      setCrawlJob(null);
      const result = await crawlWechatAccountRange({
        accountId,
        startDate,
        endDate,
        maxArticles,
        categoryId: categoryId.trim() || undefined,
        repeatIntervalMinutes,
      });
      if (!result.job_id) throw new Error("后端未返回任务 ID");
      setCrawlJob({
        job_id: result.job_id,
        status: "pending",
        total: result.discovered_count || 0,
        success_count: 0,
        failed_count: 0,
        message: result.message || "公众号文章已进入爬取队列",
        results: [],
      });
      setSubmitMessage({ type: "success", text: result.message || "公众号文章已进入爬取队列" });
    } catch (error) {
      setSubmitMessage({ type: "error", text: error instanceof Error ? error.message : "公众号文章发现失败" });
    } finally {
      setSubmitting(false);
      void fetchWechatAccounts().then(setAccounts);
      void loadCookies();
    }
  };

  const handlePublicDiscovery = async () => {
    setSubmitMessage(null);
    if (!accountId) {
      setSubmitMessage({ type: "error", text: "请先选择公众号档案。" });
      return;
    }
    if (!startDate || !endDate || startDate > endDate) {
      setSubmitMessage({ type: "error", text: "请选择正确的起止日期。" });
      return;
    }
    if (invalidPublicSeeds.length > 0) {
      setSubmitMessage({ type: "error", text: `有 ${invalidPublicSeeds.length} 个种子链接不是公众号文章地址。` });
      return;
    }
    try {
      setSubmitting(true);
      setPublicJob(null);
      const result = await startWechatPublicDiscovery({
        accountId,
        startDate,
        endDate,
        seedUrls: publicSeeds,
        maxArticles,
        categoryId: categoryId.trim() || undefined,
      });
      setPublicJob({
        job_id: result.job_id,
        status: "pending",
        candidate_count: 0,
        eligible_count: 0,
        verified_count: 0,
        rejected_count: 0,
        success_count: 0,
        failed_count: 0,
        message: result.message,
        sources: {},
        candidates: [],
        results: [],
        rejected: [],
      });
      setSubmitMessage({ type: "success", text: result.message });
    } catch (error) {
      setSubmitMessage({ type: "error", text: error instanceof Error ? error.message : "公开来源发现任务提交失败" });
    } finally {
      setSubmitting(false);
    }
  };

  const handlePublicIngest = async () => {
    if (!publicJob || selectedPublicUrls.length === 0) return;
    try {
      setSubmitting(true);
      const result = await ingestWechatPublicDiscoveryCandidates({
        jobId: publicJob.job_id,
        urls: selectedPublicUrls,
        categoryId: categoryId.trim() || undefined,
      });
      setPublicJob({ ...publicJob, status: "ingesting", message: result.message });
      setSubmitMessage({ type: "success", text: result.message });
    } catch (error) {
      setSubmitMessage({ type: "error", text: error instanceof Error ? error.message : "候选文章入库失败" });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveCookie = async () => {
    setCookieMessage(null);
    if (!cookieName.trim() || !cookieData.trim()) {
      setCookieMessage("Cookie 名称和 Cookie JSON 都不能为空。");
      return;
    }
    try {
      setSavingCookie(true);
      const result = editingCookieId
        ? await updateWechatCookie(editingCookieId, { name: cookieName.trim(), cookieData: cookieData.trim() })
        : await createWechatCookie({ name: cookieName.trim(), cookieData: cookieData.trim() });
      if (!result.success) throw new Error("Cookie 保存失败，请检查 JSON 格式");
      setCookieName("");
      setCookieData("");
      setEditingCookieId(null);
      setCookieMessage(editingCookieId ? "Cookie 已更新、重新启用并从现在起续期 7 天。" : "Cookie 已保存。建议点击“验证”再开始爬取。");
      await loadCookies();
    } catch (error) {
      setCookieMessage(error instanceof Error ? error.message : "Cookie 保存失败");
    } finally {
      setSavingCookie(false);
    }
  };

  const handleEditCookie = (item: WechatCookie) => {
    setEditingCookieId(item.id);
    setCookieName(item.name);
    setCookieData("");
    setCookieMessage("请重新粘贴最新的完整 Cookie JSON。出于安全考虑，系统不会把旧凭证明文回传到页面。");
    document.getElementById("cookieName")?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleCancelCookieEdit = () => {
    setEditingCookieId(null);
    setCookieName("");
    setCookieData("");
    setCookieMessage(null);
  };

  const handleValidateCookie = async (id: string) => {
    try {
      setValidatingCookie(id);
      const result = await validateWechatCookie(id);
      setCookieMessage(`${result.message}${result.hasRequiredKeys === false ? "；未检测到 appmsg_token 或 pass_ticket" : ""}`);
    } catch (error) {
      setCookieMessage(error instanceof Error ? error.message : "Cookie 验证失败");
    } finally {
      setValidatingCookie(null);
    }
  };

  return (
    <div className="container mx-auto max-w-5xl space-y-6 py-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
            <ShieldCheck className="h-4 w-4" />
            公众号爬取
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">爬取配置</h1>
          <p className="mt-1 text-sm text-muted-foreground">在一个页面完成文章链接、访问凭证和批量提交。</p>
        </div>
        <div className="flex gap-2">
          <Button nativeButton={false} variant="outline" render={<Link href="/settings/wechat/accounts" />}>公众号档案</Button>
          <Button nativeButton={false} variant="outline" render={<Link href="/settings/wechat/tasks" />}>定时任务</Button>
        </div>
      </div>

      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm">
        <div className="flex gap-3">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <div>
            <p className="font-medium">三种独立爬取方式</p>
            <p className="mt-1 text-muted-foreground">后台历史发现、公开来源发现和指定链接爬取使用各自独立的入口；公开来源模式不调用微信后台文章列表接口。</p>
          </div>
        </div>
      </div>

      <div className="inline-flex rounded-lg border bg-muted/40 p-1">
        <Button variant={crawlMode === "account" ? "default" : "ghost"} onClick={() => setCrawlMode("account")}>按公众号与时间</Button>
        <Button variant={crawlMode === "public" ? "default" : "ghost"} onClick={() => setCrawlMode("public")}>公开来源发现</Button>
        <Button variant={crawlMode === "urls" ? "default" : "ghost"} onClick={() => setCrawlMode("urls")}>按文章链接</Button>
      </div>

      {crawlMode === "account" ? (
      <Card>
        <CardHeader className="border-b">
          <CardTitle>公众号与时间范围</CardTitle>
          <CardDescription>需要有效的公众号后台 Cookie；系统将发现该时间段内的文章并批量爬取。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5 pt-6">
          <div className="space-y-2">
            <Label htmlFor="accountId">公众号 *</Label>
            <select id="accountId" value={accountId} onChange={(event) => { const id = event.target.value; setAccountId(id); setRepeatIntervalMinutes(accounts.find((item) => item.id === id)?.minCrawlIntervalMinutes || 60); }} className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm">
              <option value="">请选择公众号</option>
              {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}{account.wechatId ? `（${account.wechatId}）` : ""}</option>)}
            </select>
            {accounts.length === 0 && <p className="text-sm text-muted-foreground">还没有公众号，请先前往“公众号档案”添加。</p>}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor="startDate">开始日期 *</Label><Input id="startDate" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="endDate">结束日期 *</Label><Input id="endDate" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor="maxArticles">最多文章数</Label><Input id="maxArticles" type="number" min={1} max={100} value={maxArticles} onChange={(event) => setMaxArticles(Math.min(100, Math.max(1, Number(event.target.value) || 1)))} /></div>
            <div className="space-y-2"><Label htmlFor="accountCategoryId">分类 ID（可选）</Label><Input id="accountCategoryId" value={categoryId} onChange={(event) => setCategoryId(event.target.value)} placeholder="不填写则保存为未分类" /></div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="repeatInterval">重复访问周期</Label>
              <select id="repeatInterval" value={repeatIntervalMinutes} onChange={(event) => setRepeatIntervalMinutes(Number(event.target.value))} className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm">
                <option value={15}>15 分钟（频繁）</option>
                <option value={30}>30 分钟</option>
                <option value={60}>1 小时（推荐）</option>
                <option value={180}>3 小时</option>
                <option value={360}>6 小时</option>
                <option value={1440}>24 小时</option>
              </select>
              <p className="text-xs text-muted-foreground">周期内相同或更小日期范围复用缓存，不再访问微信后台。</p>
            </div>
            <div className="space-y-2">
              <Label>访问状态</Label>
              <div className="min-h-9 rounded-md bg-muted/60 px-3 py-2 text-xs leading-5 text-muted-foreground">
                {activeCookie?.nextDiscoveryAt ? (
                  <>
                    <span className={activeCookie.lastDiscoveryStatus === "rate_limited" ? "font-medium text-destructive" : "font-medium text-foreground"}>
                      Cookie 全局{activeCookie.lastDiscoveryStatus === "rate_limited" ? "限频冷却中" : "访问间隔中"}
                    </span>
                    <br />下次允许爬取：{new Date(activeCookie.nextDiscoveryAt).toLocaleString()}
                    <br />该时间前，所有公众号的时间范围发现都会暂停。
                  </>
                ) : selectedAccount?.nextDiscoveryAt ? (
                  <>公众号缓存周期至：{new Date(selectedAccount.nextDiscoveryAt).toLocaleString()}</>
                ) : "尚无访问记录；首次提交会访问微信后台。"}
              </div>
            </div>
          </div>
          <div className="rounded-md bg-muted/60 px-3 py-2 text-xs leading-5 text-muted-foreground">公众号后台 Cookie 必须包含有效登录会话。系统会自动获取 token、搜索公众号并按发布日期分页过滤。</div>
          {submitMessage && <div className={`rounded-md px-3 py-2 text-sm ${submitMessage.type === "success" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "bg-destructive/10 text-destructive"}`}>{submitMessage.text}</div>}
          {crawlJob && (
            <div className="rounded-md border px-4 py-3 text-sm">
              <div className="flex items-center gap-2 font-medium">
                {["pending", "running"].includes(crawlJob.status) ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : crawlJob.status === "completed" ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertCircle className="h-4 w-4 text-destructive" />}
                {crawlJob.status === "pending" ? "等待执行" : crawlJob.status === "running" ? "正在爬取" : crawlJob.status === "completed" ? "爬取完成" : "爬取失败"}
              </div>
              <p className="mt-1 text-muted-foreground">{crawlJob.message}</p>
              {!["pending", "running"].includes(crawlJob.status) && <p className="mt-1">成功 {crawlJob.success_count} 篇 · 失败 {crawlJob.failed_count} 篇</p>}
              {crawlJob.success_count > 0 && <Button nativeButton={false} className="mt-3" variant="outline" render={<Link href="/articles" />}>查看文章库</Button>}
            </div>
          )}
          <div className="flex justify-end"><Button onClick={handleAccountRangeCrawl} disabled={submitting || !accountId}>{submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}发现并批量爬取</Button></div>
        </CardContent>
      </Card>
      ) : crawlMode === "public" ? (
      <Card>
        <CardHeader className="border-b">
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2"><Globe2 className="h-5 w-5" />公开来源发现</CardTitle>
              <CardDescription className="mt-1">从公开搜索索引、典型文章中的链接和本地文章库收集候选，再逐篇验证公众号与发布日期。</CardDescription>
            </div>
            <Badge variant="outline">不使用 appmsg 接口</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 pt-6">
          <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm leading-6">
            <strong>覆盖范围说明：</strong>这是尽力发现模式，不受 Cookie 全局冷却影响，但无法保证找全未被公开索引收录的文章。
          </div>
          <div className="space-y-2">
            <Label htmlFor="publicAccountId">公众号档案 *</Label>
            <select id="publicAccountId" value={accountId} onChange={(event) => setAccountId(event.target.value)} className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm">
              <option value="">请选择公众号</option>
              {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}{account.wechatId ? `（${account.wechatId}）` : ""}</option>)}
            </select>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor="publicStartDate">开始日期 *</Label><Input id="publicStartDate" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="publicEndDate">结束日期 *</Label><Input id="publicEndDate" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="publicSeedUrls">典型文章链接（可选，建议填写 1～3 篇）</Label>
            <Textarea id="publicSeedUrls" value={publicSeedUrls} onChange={(event) => setPublicSeedUrls(event.target.value)} rows={4} placeholder="每行一个 mp.weixin.qq.com/s/... 链接" aria-invalid={invalidPublicSeeds.length > 0} />
            <p className="text-xs text-muted-foreground">系统会检查典型文章页面中出现的公众号文章链接；不填写时仅使用公开搜索索引和本地文章库。</p>
            {invalidPublicSeeds.length > 0 && <p className="text-sm text-destructive">检测到 {invalidPublicSeeds.length} 个无效种子链接。</p>}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor="publicMaxArticles">最多保存文章数</Label><Input id="publicMaxArticles" type="number" min={1} max={50} value={Math.min(maxArticles, 50)} onChange={(event) => setMaxArticles(Math.min(50, Math.max(1, Number(event.target.value) || 1)))} /></div>
            <div className="space-y-2"><Label htmlFor="publicCategoryId">分类 ID（可选）</Label><Input id="publicCategoryId" value={categoryId} onChange={(event) => setCategoryId(event.target.value)} placeholder="不填写则保存为未分类" /></div>
          </div>

          {submitMessage && <div className={`rounded-md px-3 py-2 text-sm ${submitMessage.type === "success" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "bg-destructive/10 text-destructive"}`}>{submitMessage.text}</div>}
          {publicJob && (
            <div className="rounded-md border px-4 py-3 text-sm">
              <div className="flex items-center gap-2 font-medium">
                {["pending", "running", "ingesting"].includes(publicJob.status) ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : ["completed", "ingested"].includes(publicJob.status) ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertCircle className="h-4 w-4 text-destructive" />}
                {publicJob.status === "pending" ? "等待公开来源发现" : publicJob.status === "running" ? "正在收集并逐篇验证" : publicJob.status === "completed" ? "候选文章等待选择" : publicJob.status === "ingesting" ? "正在将所选文章入库" : publicJob.status === "ingested" ? "所选文章入库完成" : "公开来源发现失败"}
              </div>
              <p className="mt-1 text-muted-foreground">{publicJob.message}</p>
              {publicJob.candidates.length > 0 && (
                <div className="mt-3">
                  <div className="flex flex-col gap-2 border-y py-3 sm:flex-row sm:items-center sm:justify-between">
                    <p>候选 {publicJob.candidate_count} 篇 · 自动符合 {publicJob.eligible_count} 篇 · 需要复核 {publicJob.rejected_count} 篇</p>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setSelectedPublicUrls(publicJob.candidates.map((item) => item.url))}>全选</Button>
                      <Button size="sm" variant="ghost" onClick={() => setSelectedPublicUrls([])}>清空</Button>
                    </div>
                  </div>
                  <div className="max-h-[420px] divide-y overflow-y-auto">
                    {publicJob.candidates.map((item) => {
                      const checked = selectedPublicUrls.includes(item.url);
                      return (
                        <label key={item.url} className="flex cursor-pointer items-start gap-3 py-3">
                          <input type="checkbox" className="mt-1 h-4 w-4 rounded border-input" checked={checked} onChange={(event) => setSelectedPublicUrls((current) => event.target.checked ? [...current, item.url] : current.filter((url) => url !== item.url))} />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate font-medium">{item.title || "未能读取文章标题"}</span>
                            <span className="mt-1 block break-all text-xs text-muted-foreground">{item.account_name || "公众号未知"}{item.published_at ? ` · ${item.published_at}` : ""} · {item.url}</span>
                            <span className={`mt-1 block text-xs ${item.eligible ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}`}>{item.reason}</span>
                          </span>
                          <Badge variant={item.eligible ? "outline" : "secondary"}>{item.eligible ? "符合条件" : "建议复核"}</Badge>
                        </label>
                      );
                    })}
                  </div>
                  <div className="flex flex-col gap-2 border-t pt-3 sm:flex-row sm:items-center sm:justify-between">
                    <span className="text-muted-foreground">已选择 {selectedPublicUrls.length} 篇；即使标记为“建议复核”，也可以手动选择入库。</span>
                    <Button onClick={handlePublicIngest} disabled={submitting || selectedPublicUrls.length === 0 || publicJob.status === "ingesting"}>{publicJob.status === "ingesting" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}将所选文章入库</Button>
                  </div>
                </div>
              )}
              {publicJob.verified_count > 0 && <Button nativeButton={false} className="mt-3" variant="outline" render={<Link href="/articles" />}>查看文章库</Button>}
            </div>
          )}
          <div className="flex justify-end"><Button onClick={handlePublicDiscovery} disabled={submitting || !accountId || invalidPublicSeeds.length > 0}>{submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Globe2 className="mr-2 h-4 w-4" />}开始公开来源发现</Button></div>
        </CardContent>
      </Card>
      ) : (
      <Card>
        <CardHeader className="border-b">
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2"><FileText className="h-5 w-5" />文章链接</CardTitle>
              <CardDescription className="mt-1">必填。每行一个链接，也可以用空格或逗号分隔。</CardDescription>
            </div>
            <Badge variant="outline">已识别 {urls.length} 篇</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 pt-6">
          <div className="space-y-2">
            <Label htmlFor="articleUrls">公众号文章 URL *</Label>
            <Textarea
              id="articleUrls"
              value={articleUrls}
              onChange={(event) => setArticleUrls(event.target.value)}
              rows={8}
              placeholder={"https://mp.weixin.qq.com/s/第一篇文章\nhttps://mp.weixin.qq.com/s/第二篇文章"}
              aria-invalid={invalidUrls.length > 0}
            />
            <div className="rounded-md bg-muted/60 px-3 py-2 text-xs leading-5 text-muted-foreground">
              <strong className="text-foreground">如何获取：</strong>在微信中打开文章 → 右上角“…” → “复制链接”；粘贴后确认域名为 mp.weixin.qq.com。
            </div>
            {invalidUrls.length > 0 && <p className="text-sm text-destructive">检测到 {invalidUrls.length} 个非公众号文章链接，请检查后再提交。</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="categoryId">分类 ID（可选）</Label>
            <Input id="categoryId" value={categoryId} onChange={(event) => setCategoryId(event.target.value)} placeholder="不填写则保存为未分类" />
          </div>

          {submitMessage && (
            <div className={`flex items-start gap-2 rounded-md px-3 py-2 text-sm ${submitMessage.type === "success" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "bg-destructive/10 text-destructive"}`}>
              {submitMessage.type === "success" ? <CheckCircle2 className="mt-0.5 h-4 w-4" /> : <AlertCircle className="mt-0.5 h-4 w-4" />}
              {submitMessage.text}
            </div>
          )}

          {crawlJob && (
            <div className="rounded-md border px-4 py-3 text-sm">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="flex items-center gap-2 font-medium">
                    {crawlJob.status === "pending" || crawlJob.status === "running" ? (
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    ) : crawlJob.status === "completed" ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-destructive" />
                    )}
                    {crawlJob.status === "pending" ? "等待执行" : crawlJob.status === "running" ? "正在爬取" : crawlJob.status === "completed" ? "爬取完成" : "爬取失败"}
                  </div>
                  <p className="mt-1 text-muted-foreground">{crawlJob.message}</p>
                  {!["pending", "running"].includes(crawlJob.status) && (
                    <p className="mt-1">成功 {crawlJob.success_count} 篇 · 失败 {crawlJob.failed_count} 篇</p>
                  )}
                </div>
                {crawlJob.success_count > 0 && (
                  <Button nativeButton={false} variant="outline" render={<Link href="/articles" />}>查看文章库</Button>
                )}
              </div>
              {crawlJob.results.length > 0 && (
                <div className="mt-3 divide-y border-t">
                  {crawlJob.results.map((item, index) => (
                    <div key={`${item.url || "result"}-${index}`} className="flex items-start justify-between gap-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate">{item.title || item.url || `文章 ${index + 1}`}</p>
                        {!item.success && item.error && <p className="mt-1 break-all text-xs text-destructive">{item.error}</p>}
                      </div>
                      <Badge variant={item.success ? "default" : "destructive"}>{item.success ? "成功" : "失败"}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end">
            <Button onClick={handleCrawl} disabled={submitting || urls.length === 0 || invalidUrls.length > 0}>
              {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
              提交批量爬取
            </Button>
          </div>
        </CardContent>
      </Card>
      )}

      <Card>
        <CardHeader className="border-b">
          <CardTitle className="flex items-center gap-2"><Cookie className="h-5 w-5" />访问 Cookie</CardTitle>
          <CardDescription>可选。公开文章建议先不配置；遇到登录或访问限制时再添加。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 pt-6">
          <div className="grid gap-4 md:grid-cols-[220px_1fr]">
            <div className="space-y-2">
              <Label htmlFor="cookieName">{editingCookieId ? "编辑 Cookie 名称" : "Cookie 名称"}</Label>
              <Input id="cookieName" value={cookieName} onChange={(event) => setCookieName(event.target.value)} placeholder="例如：公众号后台主账号" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cookieData">{editingCookieId ? "新的 Cookie JSON" : "Cookie JSON"}</Label>
              <Textarea id="cookieData" value={cookieData} onChange={(event) => setCookieData(event.target.value)} rows={6} placeholder='[{"name":"pass_ticket","value":"...","domain":".mp.weixin.qq.com","path":"/"}]' />
            </div>
          </div>

          <div className="rounded-md border bg-muted/40 px-4 py-3 text-sm leading-6 text-muted-foreground">
            <p><strong className="text-foreground">如何获取：</strong>在电脑浏览器登录公众号管理后台，确认当前地址是 mp.weixin.qq.com 且 URL 中带有 <code>token=</code>；保持在该后台页面，打开 Cookie-Editor，点击右下角“导出”按钮并选择 JSON，将完整数组粘贴到上方。不要在普通公众号文章页导出。</p>
            <p className="mt-1">Cookie 是登录凭证，请勿发送给他人或提交到 Git。后端默认按 7 天标记过期。</p>
            <Button nativeButton={false} className="mt-2 px-0" variant="link" render={<a href="https://mp.weixin.qq.com/" target="_blank" rel="noreferrer" />}>
              打开公众号平台 <ExternalLink className="ml-1 h-3.5 w-3.5" />
            </Button>
          </div>

          {editingCookieId && (
            <div className="flex items-center justify-between rounded-md border border-primary/25 bg-primary/5 px-3 py-2 text-sm">
              <span>正在更新已保存的 Cookie；保存后会自动重新启用并续期 7 天。</span>
              <Button size="sm" variant="ghost" onClick={handleCancelCookieEdit}><X className="mr-1 h-4 w-4" />取消编辑</Button>
            </div>
          )}

          <div className="flex justify-end">
            <Button variant="outline" onClick={handleSaveCookie} disabled={savingCookie || !cookieName.trim() || !cookieData.trim()}>
              {savingCookie && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editingCookieId ? "更新并续期 Cookie" : "保存 Cookie"}
            </Button>
          </div>

          {cookieMessage && <p className="rounded-md bg-muted px-3 py-2 text-sm">{cookieMessage}</p>}

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium">已保存的 Cookie</h2>
              <Badge variant="secondary">{cookies.length} 个</Badge>
            </div>
            {loadingCookies ? (
              <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />正在加载</div>
            ) : cookies.length === 0 ? (
              <div className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">尚未保存 Cookie，公开文章可直接尝试爬取。</div>
            ) : (
              <div className="divide-y rounded-md border">
                {cookies.map((item) => (
                  <div key={item.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2"><span className="truncate font-medium">{item.name}</span><Badge variant={item.isActive ? "default" : "secondary"}>{item.isActive ? "已启用" : "已停用"}</Badge></div>
                      <p className="mt-1 text-xs text-muted-foreground">过期时间：{item.expiresAt ? new Date(item.expiresAt).toLocaleString() : "未设置"}</p>
                      {item.nextDiscoveryAt && <p className={`mt-1 text-xs ${item.lastDiscoveryStatus === "rate_limited" ? "text-destructive" : "text-muted-foreground"}`}>全局下次爬取：{new Date(item.nextDiscoveryAt).toLocaleString()}{item.lastDiscoveryStatus === "rate_limited" ? "（冷却中）" : ""}</p>}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => handleEditCookie(item)}><Pencil className="mr-1 h-3.5 w-3.5" />编辑</Button>
                      <Button size="sm" variant="outline" onClick={() => handleValidateCookie(item.id)} disabled={validatingCookie === item.id}>{validatingCookie === item.id ? "验证中…" : "验证"}</Button>
                      <Button size="sm" variant="outline" onClick={async () => { item.isActive ? await deactivateWechatCookie(item.id) : await activateWechatCookie(item.id); await loadCookies(); }}>{item.isActive ? "停用" : "启用"}</Button>
                      <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={async () => { await deleteWechatCookie(item.id); await loadCookies(); }} aria-label={`删除 ${item.name}`}><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
