"""
备用爬取器 - 评分与语义裁剪单元测试

这些测试不依赖网络，使用手工构造的“真实污染样本”来验证：
1. 评分函数能区分正文 vs 导航/页脚/版权
2. 选优函数能挑出正文质量最高的那个
3. 语义尾部裁剪能从混入尾部的导航/版权里把正文截出来
"""

import unittest
import sys
from pathlib import Path

# 将 backend 加入 import path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.alternate_scraper import (  # noqa: E402
    _score_extracted_text,
    _select_best_extraction,
    strip_semantic_noise_blocks,
)


# ============================================================
# 评分函数测试
# ============================================================

class TestScoringFunction(unittest.TestCase):
    def test_empty_text_returns_neginf(self):
        self.assertEqual(_score_extracted_text(""), float("-inf"))
        self.assertEqual(_score_extracted_text("   \n\t  "), float("-inf"))

    def test_pure_content_scores_high(self):
        """纯正文：含中文标点 + 新闻体关键词，应该评分很高。"""
        text = (
            "中国科学院近日召开2026年工作会议，深入贯彻落实习近平新时代中国"
            "特色社会主义思想。会议指出，要紧紧围绕国家战略需求，加强基础研"
            "究与应用研究，推动重大科技任务落地。会议强调，要进一步加强人才队"
            "伍建设，为实现高水平科技自立自强贡献力量。院领导、各研究所主要"
            "负责人等200余人参加会议。会议要求，全院上下要以更加奋发有为的精"
            "神状态，推动各项事业高质量发展，为建设科技强国作出新的更大贡献。"
        )
        score = _score_extracted_text(text)
        # 包含多个中文标点 + 多个新闻体关键词 + 中等长度，
        # 在所有噪声模式都不命中的情况下，评分应明显高于纯导航串（< 5）。
        self.assertGreater(score, 30, f"纯正文评分应该 > 30, got {score}")

    def test_pure_navigation_scores_low(self):
        """纯导航串：只有栏目名，没有正文，应被惩罚。"""
        text = (
            "首页|走进科学院|信息公开|科技人才|院士|出版物|新闻动态|图片世界|视频世界"
        )
        score = _score_extracted_text(text)
        self.assertLess(score, 5, f"纯导航评分应该 < 5, got {score}")

    def test_copyright_heavy_scores_low(self):
        """含版权/备案/地址/电话的文本，应被强烈惩罚。"""
        text = (
            "中国科学院 版权所有 ©1996-2026 中国科学院 版权所有 "
            "京ICP备12345678号 京公网安备11010102000000号 "
            "地址：北京市西城区三里河路52号 邮编：100864 "
            "电话：86 10 68597114 邮件：cas@cas.cn"
        )
        score = _score_extracted_text(text)
        self.assertLess(score, 10, f"纯版权/备案信息评分应 < 10, got {score}")

    def test_mixed_content_prefers_cleaner_one(self):
        """混入尾部导航/页脚的版本，应明显低于纯正文版本。"""
        clean = (
            "中国科学院近日召开2026年工作会议，深入贯彻落实习近平新时代中国"
            "特色社会主义思想。会议指出，要紧紧围绕国家战略需求，加强基础研"
            "究与应用研究，推动重大科技任务落地。会议强调，要进一步加强人才队"
            "伍建设，为实现高水平科技自立自强贡献力量。"
        )
        contaminated = clean + (
            " 更多+ 科技奖励 科技期刊 科技专项 科研进展 "
            "中国科学院学部 中国科学院院部 "
            "©1996-2026 中国科学院 版权所有 "
            "京ICP备12345678号 地址：北京市西城区三里河路52号 "
            "邮编：100864 电话：86 10 68597114"
        )
        score_clean = _score_extracted_text(clean)
        score_dirty = _score_extracted_text(contaminated)
        self.assertGreater(
            score_clean, score_dirty,
            f"clean ({score_clean}) 应该 > dirty ({score_dirty})"
        )

    def test_title_consistency_bonus(self):
        """标题中含有关键词，命中正文应得奖励。"""
        text = (
            "中国科学院大学2026年开学典礼在北京举行，来自全国各地的3000余名"
            "新生参加典礼。校长在讲话中强调，希望同学们胸怀家国、勇担使命，"
            "为实现高水平科技自立自强贡献青春力量。"
        )
        title = "中国科学院大学2026年开学典礼"
        score_with_title = _score_extracted_text(text, title=title)
        score_without_title = _score_extracted_text(text, title="")
        self.assertGreater(score_with_title, score_without_title)


# ============================================================
# 选优函数测试
# ============================================================

class TestSelectBestExtraction(unittest.TestCase):
    def test_picks_cleaner_over_longer(self):
        """模拟 CAS 场景：trafilatura 更长但混入导航，
        readability 更短但更纯，应该选 readability。"""
        trafilatura = {
            "extractor": "trafilatura",
            "text": (
                "中国科学院大学2026年开学典礼在北京举行，来自全国各地的3000余名"
                "新生参加典礼。校长在讲话中强调，希望同学们胸怀家国、勇担使命，"
                "为实现高水平科技自立自强贡献青春力量。"
                " 更多+ 科技奖励 科技期刊 科技专项 科研进展 "
                "中国科学院学部 中国科学院院部 "
                "©1996-2026 中国科学院 版权所有 "
                "京ICP备12345678号 地址：北京市西城区三里河路52号 "
                "邮编：100864 电话：86 10 68597114"
            ),
            "html": "",
            "title": "中国科学院大学2026年开学典礼",
        }
        readability = {
            "extractor": "readability",
            "text": (
                "中国科学院大学2026年开学典礼在北京举行，来自全国各地的3000余名"
                "新生参加典礼。校长在讲话中强调，希望同学们胸怀家国、勇担使命，"
                "为实现高水平科技自立自强贡献青春力量。"
            ),
            "html": "",
            "title": "中国科学院大学2026年开学典礼",
        }
        best = _select_best_extraction(
            [trafilatura, readability], title="中国科学院大学2026年开学典礼"
        )
        self.assertEqual(best["extractor"], "readability")

    def test_picks_longer_when_both_clean(self):
        """两段都干净时，仍偏好信息量大的（更长）。"""
        short = {
            "extractor": "a",
            "text": "中国科学院近日召开会议。会议指出，要推动重大科技任务。",
            "html": "",
            "title": "会议",
        }
        long_ = {
            "extractor": "b",
            "text": (
                "中国科学院近日召开2026年工作会议，深入贯彻落实习近平新时代中国"
                "特色社会主义思想。会议指出，要紧紧围绕国家战略需求，加强基础研"
                "究与应用研究，推动重大科技任务落地。会议强调，要进一步加强人才"
                "队伍建设，为实现高水平科技自立自强贡献力量。"
            ),
            "html": "",
            "title": "会议",
        }
        best = _select_best_extraction([short, long_], title="会议")
        self.assertEqual(best["extractor"], "b")

    def test_skips_empty_candidates(self):
        """空候选应被跳过；如果全空则回退到第一个非空。"""
        empty = {"extractor": "x", "text": "", "html": "", "title": ""}
        valid = {"extractor": "y", "text": "中国科学院发布重要通知。", "html": "", "title": "通知"}
        best = _select_best_extraction([empty, valid], title="通知")
        self.assertEqual(best["extractor"], "y")

    def test_all_empty_returns_first(self):
        """全空时回退到第一个（调用方应当兜底处理）。"""
        cands = [
            {"extractor": "a", "text": "", "html": "", "title": ""},
            {"extractor": "b", "text": "", "html": "", "title": ""},
        ]
        best = _select_best_extraction(cands, title="")
        # 没有 text 的不应被选；最终回退到第一个非空（也是空），整体行为安全
        self.assertIn(best["extractor"], ["a", "b"])


# ============================================================
# 语义尾部裁剪测试
# ============================================================

class TestStripSemanticNoiseBlocks(unittest.TestCase):
    def test_strip_trailing_navigation(self):
        """正文 + 栏目串：应只保留正文。"""
        text = (
            "中国科学院近日召开2026年工作会议。会议指出，要推动重大科技任务。"
            " 更多+ 科技奖励 科技期刊 科技专项"
        )
        cleaned = strip_semantic_noise_blocks(text)
        self.assertNotIn("科技奖励", cleaned)
        self.assertNotIn("更多+", cleaned)
        self.assertIn("工作会议", cleaned)
        self.assertIn("推动重大科技任务", cleaned)

    def test_strip_copyright_block(self):
        """正文 + 版权/备案：应只保留正文。"""
        text = (
            "中国科学院大学2026年开学典礼在北京举行。"
            "©1996-2026 中国科学院 版权所有 京ICP备12345678号"
        )
        cleaned = strip_semantic_noise_blocks(text)
        self.assertNotIn("版权所有", cleaned)
        self.assertNotIn("京ICP备", cleaned)
        self.assertIn("开学典礼", cleaned)

    def test_strip_address_phone(self):
        """正文 + 地址/邮编/电话：应只保留正文。"""
        text = (
            "中国科学院发布2026年工作要点，全面部署下一阶段重点任务。"
            "地址：北京市西城区三里河路52号 邮编：100864 电话：86 10 68597114"
        )
        cleaned = strip_semantic_noise_blocks(text)
        self.assertNotIn("三里河路", cleaned)
        self.assertNotIn("68597114", cleaned)
        self.assertIn("工作要点", cleaned)

    def test_preserves_pure_content(self):
        """纯正文应原样保留。"""
        text = (
            "中国科学院近日召开2026年工作会议，深入贯彻落实习近平新时代中国"
            "特色社会主义思想。会议指出，要紧紧围绕国家战略需求，加强基础研"
            "究与应用研究，推动重大科技任务落地。会议强调，要进一步加强人才队"
            "伍建设，为实现高水平科技自立自强贡献力量。"
        )
        cleaned = strip_semantic_noise_blocks(text)
        self.assertIn("工作会议", cleaned)
        self.assertIn("贯彻落实", cleaned)
        self.assertIn("科技自立自强", cleaned)

    def test_handles_empty(self):
        """空文本应原样返回。"""
        self.assertEqual(strip_semantic_noise_blocks(""), "")
        self.assertEqual(strip_semantic_noise_blocks(None), None)

    def test_handles_all_noise(self):
        """整篇都是噪声时，至少返回前 200 字符作为兜底。"""
        text = (
            "首页|走进科学院|信息公开|科技人才|院士|出版物 "
            "©1996-2026 中国科学院 版权所有 京ICP备12345678号"
        )
        cleaned = strip_semantic_noise_blocks(text)
        self.assertTrue(len(cleaned) > 0, "兜底应返回非空内容")

    def test_strips_multiple_noise_types(self):
        """多种噪声混合时，应在最早出现的截断点处截断。"""
        text = (
            "正文部分：中国科学院大学举行2026年开学典礼。"
            "院部|院士|机构|学部 "
            "©1996-2026 中国科学院 版权所有 "
            "京ICP备12345678号 地址：北京市西城区三里河路52号"
        )
        cleaned = strip_semantic_noise_blocks(text)
        self.assertNotIn("版权所有", cleaned)
        self.assertNotIn("京ICP备", cleaned)
        self.assertNotIn("三里河路", cleaned)
        self.assertIn("开学典礼", cleaned)

    def test_strip_standalone_more_plus(self):
        """CAS 真实场景：正文末尾单独的"更多+"应被识别并截断。"""
        text = (
            "中国科学院是国家科学技术界最高学术机构。"
            "1949年，伴随着新中国的诞生，中国科学院成立。"
            "建院70余年来，中国科学院时刻牢记使命，为我国科技进步作出了不可替代的贡献。 更多+"
        )
        cleaned = strip_semantic_noise_blocks(text)
        self.assertNotIn("更多+", cleaned, f"剩余: {cleaned[-50:]!r}")
        self.assertIn("中国科学院是国家科学技术界最高学术机构", cleaned)

    def test_does_not_strip_legitimate_more_plus(self):
        """正文里出现"更多+xxx"这种说法，不应被误伤。"""
        text = "AI 大模型会输出更多+1 个结果，但质量参差不齐。"
        cleaned = strip_semantic_noise_blocks(text)
        # 这里 "更多+1" 不应被截断（因为后面有数字，是合法用法）
        self.assertIn("更多+1", cleaned, f"剩余: {cleaned!r}")

    def test_preserves_multiline_structure(self):
        """多行内容：尾行"更多+"应被裁剪，但前几行应保留。"""
        text = (
            "中国科学院是国家科学技术界最高学术机构、国家科学技术思想库，\n"
            "自然科学基础研究与高技术综合研究的国家战略科技力量。\n"
            "1949年，伴随着新中国的诞生，中国科学院成立。\n"
            "建院70余年来，为我国科技进步作出了不可替代的重要贡献。\n"
            "更多+"
        )
        cleaned = strip_semantic_noise_blocks(text)
        # 不应包含"更多+"
        self.assertNotIn("更多+", cleaned)
        # 应包含前几行正文
        self.assertIn("国家科学技术界最高学术机构", cleaned)
        self.assertIn("1949年", cleaned)
        self.assertIn("不可替代的重要贡献", cleaned)
        # 输出应远大于 0（保留绝大部分正文）
        self.assertGreater(len(cleaned), len(text) * 0.5)


if __name__ == "__main__":
    unittest.main()
