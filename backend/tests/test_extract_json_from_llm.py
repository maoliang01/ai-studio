"""
LLM JSON 响应解析单元测试

背景：项目使用的中科院云 minimax-m27 模型在返回 JSON 之前，
几乎总会先输出 ``<think>...</think>`` 思考块，并习惯用 markdown
`````json`` 围栏包裹 JSON。当前代码用贪婪正则 ``r'\{[\s\S]*\}'``
直接匹配第一个 ``{`` 到最后一个 ``}``，导致 think 块里任意 ``{}``
也会被吃进去，每次 ``json.loads`` 必败（"Extra data: line X column 1"）。

本测试针对的 `_extract_json_from_llm_response` 函数负责：
1. 去掉 ``<think>...</think>`` 块
2. 从 markdown ```json 围栏中提取 JSON
3. 在剩余文本中寻找 ``{...}`` 块并解析
4. 全部失败时返回 None（不抛异常）

测试目标覆盖以下 4 种响应形态：
1. 纯 JSON（无 think 块、无围栏）
2. ``<think>...</think>`` + 纯 JSON
3. `````json`` 围栏 + JSON
4. ``<think>...</think>`` + `````json`` 围栏 + JSON（实际 LLM 输出）
5. 围栏前缀错误（`````JSON`` / `````JSON5``）
"""

import unittest
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.scraper import _extract_json_from_llm_response  # noqa: E402


class TestExtractJsonFromLlmResponse(unittest.TestCase):
    def test_pure_json_no_think_no_fence(self):
        """纯 JSON 响应（最简单场景）"""
        resp = '{"title": "test", "summary": "hello", "keywords": ["a", "b"]}'
        result = _extract_json_from_llm_response(resp)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "test")
        self.assertEqual(result["summary"], "hello")
        self.assertEqual(result["keywords"], ["a", "b"])

    def test_think_block_then_pure_json(self):
        """<think>...</think> 块 + 纯 JSON（没有围栏）"""
        resp = """<think>
让我分析这篇文章并提取关键信息。
标题是关于 foo bar 的。
</think>
{"title": "分析结果", "summary": "已分析"}"""
        result = _extract_json_from_llm_response(resp)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "分析结果")
        self.assertEqual(result["summary"], "已分析")

    def test_json_fence_only(self):
        """仅 ```json 围栏 + JSON（无 think 块）"""
        resp = """```json
{"title": "围栏测试", "summary": "ok", "keywords": ["x"]}
```"""
        result = _extract_json_from_llm_response(resp)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "围栏测试")
        self.assertEqual(result["keywords"], ["x"])

    def test_think_block_then_json_fence(self):
        """<think> + ```json 围栏（最常见的实际 LLM 输出）"""
        resp = """<think>
用户要求我分析文章并提取关键信息。
我需要识别标题、作者、日期、摘要、关键词。

让我开始：
1. 标题：xxx
2. 作者：yyy
3. 日期：zzz
4. 摘要：...
5. 关键词：...

现在我需要按照要求的JSON格式返回结果：
</think>

```json
{
  "title": "中国科学院的地位与贡献",
  "author": "中国科学院",
  "published_at": "",
  "summary": "中国科学院是国家科学技术界最高学术机构。",
  "keywords": ["中国科学院", "科学技术"]
}
```"""
        result = _extract_json_from_llm_response(resp)
        self.assertIsNotNone(result, "think + fence 嵌套场景必须能正确提取")
        self.assertEqual(result["title"], "中国科学院的地位与贡献")
        self.assertEqual(result["author"], "中国科学院")
        self.assertEqual(result["summary"], "中国科学院是国家科学技术界最高学术机构。")
        self.assertEqual(result["keywords"], ["中国科学院", "科学技术"])

    def test_think_block_with_brace_then_json_fence(self):
        """think 块里有 { }、后面是围栏 JSON（这就是当前代码失败的场景）"""
        resp = """<think>
文章标题：测试文章
文章内容：{这是文章里的某个引用，不是JSON}
我需要输出 JSON 格式。
```json
{
  "title": "测试文章",
  "summary": "引用包含{}的情况",
  "keywords": ["a", "b"]
}
```
"""
        result = _extract_json_from_llm_response(resp)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "测试文章")
        self.assertEqual(result["summary"], "引用包含{}的情况")

    def test_uppercase_json_fence(self):
        """大写 ```JSON 围栏也应能识别"""
        resp = """```JSON
{"title": "upper", "value": 42}
```"""
        result = _extract_json_from_llm_response(resp)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "upper")
        self.assertEqual(result["value"], 42)

    def test_unparseable_returns_none(self):
        """完全无法解析时返回 None，不抛异常"""
        resp = "这个响应里完全没有 JSON"
        result = _extract_json_from_llm_response(resp)
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        """空字符串返回 None"""
        self.assertIsNone(_extract_json_from_llm_response(""))
        self.assertIsNone(_extract_json_from_llm_response(None))

    def test_think_only_no_json_returns_none(self):
        """只有 think 块没有 JSON 时返回 None"""
        resp = """<think>
我分析了一下，但是忘了输出 JSON。
</think>"""
        result = _extract_json_from_llm_response(resp)
        self.assertIsNone(result)

    def test_json_with_extra_text_after(self):
        """JSON 后面跟着解释文字（LLM 偶尔会加）"""
        resp = """```json
{"title": "ok", "summary": "done"}
```
以上是分析结果。"""
        result = _extract_json_from_llm_response(resp)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "ok")
        self.assertEqual(result["summary"], "done")

    def test_nested_json_in_think_doesnt_break_parsing(self):
        """think 块里嵌入嵌套 JSON（更复杂的陷阱）"""
        resp = """<think>
参考一下之前的输出：
{"previous": {"nested": {"value": 1}}}
然后我开始正式输出。
</think>
{"title": "当前输出", "summary": "test"}"""
        result = _extract_json_from_llm_response(resp)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "当前输出")


if __name__ == "__main__":
    unittest.main()
