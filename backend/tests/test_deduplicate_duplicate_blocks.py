"""
备用爬取器 - 重复段落去重单元测试

背景：cas.cn 等使用 TRS_UEDITOR 的站点，会在 HTML 中同时输出两套正文：
  1. <div class="xl_content"> 下用 <p> 标签格式化的多段版本
  2. <p id="_content"> 一整段扁平拼接的版本（用于打印/无障碍/SEO）
Mozilla Readability 把两个容器都识别为"主内容"并全部纳入 summary()，
导致 final text 出现完整的二次重复。

本测试覆盖的 `_deduplicate_duplicate_blocks` 函数负责在拿到 readability
输出之后做一次结构性去重：检测是否存在"某个块的内容 == 其余所有块拼接"
的情况，有则删除该副本块。

测试目标：
1. cas.cn 形态：4 段格式化 + 1 段扁平拼接副本 → 删除副本
2. 没有重复时不改动
3. 文本只有单段时不改动
4. 完全相同的两段 → 删除其中一段
5. 空文本 → 原文返回
"""

import unittest
import sys
from pathlib import Path

# 将 backend 加入 import path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.alternate_scraper import (  # noqa: E402
    _deduplicate_duplicate_blocks,
)


# ============================================================
# 重复段去重
# ============================================================

class TestDeduplicateDuplicateBlocks(unittest.TestCase):
    def test_cas_cn_trs_ueditor_pattern(self):
        """模拟 cas.cn 抓取结果：4 段格式化正文 + 1 段扁平拼接副本"""
        para1 = "6月8日，中国科学院党组召开理论学习中心组集体学习会，深入学习领会习近平总书记关于科技创新和发展新质生产力的重要论述，院长侯建国主持会议。"
        para2 = "学习会上，与会人员围绕脑机接口领域前沿发展态势进行了深入交流研讨。"
        para3 = "侯建国在总结讲话中强调，脑机接口技术是推动拓展生命认知边界、促进人类健康福祉的颠覆性前沿技术，对培育未来产业具有重要意义。"
        para4 = "中央纪委国家监委驻中国科学院纪检监察组、院机关各部门负责人列席会议。"

        formatted = "\n\n".join([para1, para2, para3, para4])
        # 扁平副本：把 4 段连起来（去掉 \n\n 换行），作为一整段
        flat_duplicate = "".join([para1, para2, para3, para4])

        raw = formatted + "\n\n" + flat_duplicate

        result = _deduplicate_duplicate_blocks(raw)

        # 期望：只剩 4 段格式化的版本，扁平副本被删除
        self.assertNotIn(flat_duplicate, result,
                         "扁平副本应被删除")
        self.assertIn(para1, result)
        self.assertIn(para2, result)
        self.assertIn(para3, result)
        self.assertIn(para4, result)
        # 不应包含合并后的整段扁平串
        # 4 段都出现 + 没有任何"\n\n"把整段扁平串保留 → 长度应小于原长度
        self.assertLess(len(result), len(raw),
                        f"去重后应比原文短: len={len(result)} vs {len(raw)}")
        # 段与段之间仍然保留换行结构
        self.assertIn("\n", result, "格式化版本应保留换行分隔")

    def test_no_duplicate_returns_unchanged(self):
        """没有重复的文本应原样返回"""
        text = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        result = _deduplicate_duplicate_blocks(text)
        self.assertEqual(result, text)

    def test_single_block_returns_unchanged(self):
        """单段文本无需去重"""
        text = "这是一段很长的纯文字内容。" * 20
        result = _deduplicate_duplicate_blocks(text)
        self.assertEqual(result, text)

    def test_empty_text_returns_unchanged(self):
        """空文本直接返回"""
        self.assertEqual(_deduplicate_duplicate_blocks(""), "")
        self.assertEqual(_deduplicate_duplicate_blocks(None), None)

    def test_two_exact_duplicates_keeps_first(self):
        """完全相同的两段：保留第一段，删除第二段"""
        # 构造长度 >= 50 的段落，避免被长度阈值过滤
        para = "完全相同的段落内容。" * 10  # 80 字符
        raw = para + "\n\n" + para
        result = _deduplicate_duplicate_blocks(raw)
        # 只应出现一次
        self.assertEqual(result.count(para), 1, "完全相同的副本应被删除一次")

    def test_flat_duplicate_in_middle(self):
        """扁平副本在中间的情况也能被检测到"""
        para1 = "开头段落内容A。" * 5
        para2 = "结尾段落内容C。" * 5
        flat = "".join([para1, para2])  # 扁平副本 = 前后两块拼接

        raw = para1 + "\n\n" + flat + "\n\n" + para2
        result = _deduplicate_duplicate_blocks(raw)
        # 扁平副本应被删除
        self.assertNotIn(flat, result, "中间位置的扁平副本应被删除")

    def test_readability_single_newline_separator(self):
        """Readability 输出用单 \\n 分段（不是 \\n\\n），函数必须能正确识别扁平副本。

        这是 cas.cn 真实抓取结果的还原：4 段段落用单 \\n 隔开，
        后面紧跟一段扁平拼接副本。
        """
        para1 = "6月8日，院长主持会议。" * 3
        para2 = "与会人员深入研讨。" * 3
        para3 = "会议强调加快抢占科技制高点。" * 3
        para4 = "中央列席会议。" * 3
        flat = "".join([para1, para2, para3, para4])

        # 注意：用单 \n 隔开，模拟 readability 真实输出
        raw = "\n".join([para1, para2, para3, para4, flat])

        result = _deduplicate_duplicate_blocks(raw)

        # 扁平副本应被删除
        self.assertNotIn(flat, result, "Readability 输出格式下的扁平副本应被删除")
        # 4 段格式化内容都应保留
        for para in [para1, para2, para3, para4]:
            self.assertIn(para, result, f"段落应保留: {para[:30]}...")

    def test_crawl4ai_markdown_with_separator_in_first_copy_only(self):
        """Crawl4AI markdown 格式:第一段含 \\n 分段,第二段扁平拼接,块级 dedup 检测不出

        重复内容: "6月8日...作交流发言。\\n学习会上..." (中间有 \\n)
        同样内容扁平版: "6月8日...作交流发言。学习会上..." (无 \\n)
        → 块级按 \\n+ 切后,扁平版是一个超长块,跟其他块都不等
        → 必须用 SequenceMatcher 找出子串级重复
        """
        para1_p1 = "6月8日，中国科学院党组召开理论学习中心组集体学习会，深入学习领会习近平总书记关于科技创新和发展新质生产力的重要论述。"
        para1_p2 = "学习会上，与会人员围绕脑机接口领域前沿发展态势进行了深入交流研讨。"

        formatted = para1_p1 + "\n" + para1_p2
        flat = para1_p1 + para1_p2  # 去掉 \n

        # 模拟 Crawl4AI markdown 完整结构(标题 + 格式化 + 重复的扁平 + 噪声)
        raw = "## 中国科学院头条\n" + formatted + "\n## 上一篇\n" + flat + "\n扫描二维码"

        result = _deduplicate_duplicate_blocks(raw)

        # 扁平副本应被删除
        self.assertNotIn(flat, result, "Crawl4AI 风格扁平副本应被删除")
        # 格式化版本必须保留
        self.assertIn(formatted, result, "格式化版本必须保留")


if __name__ == "__main__":
    unittest.main()
