"""
批量修复历史文档缺失的元数据字段（文体、分类、来源）

使用方法：
cd backend
python scripts/fix_missing_metadata.py [--dry-run] [--batch-size 10] [--limit 100]

参数说明：
  --dry-run        仅显示会修改的内容，不实际执行
  --batch-size     每批处理的文章数量（默认 10）
  --limit          最多处理的文章数量（默认 100）
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime
from typing import List, Optional, Tuple

# 本地运行时覆盖数据库主机（Docker 容器名在本地无法解析）
if not os.getenv("DB_HOST"):
    os.environ["DB_HOST"] = "localhost"

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_session_local
from app.models.article import Article, Category, ScrapeSource
from app.services.scraper import get_scraper


def get_articles_missing_style(limit: int = 100) -> List[Article]:
    """获取缺失文体字段的文章"""
    db = get_session_local()()
    try:
        articles = db.query(Article).filter(
            Article.style.is_(None) | (Article.style == ""),
            Article.status == "success",
            Article.word_count >= 50,  # 内容足够才分析
            Article.content.isnot(None),
            Article.content != ""
        ).limit(limit).all()

        # 避免懒加载问题，提前加载关联对象
        for article in articles:
            _ = article.source
            _ = article.category

        return articles
    finally:
        db.close()


def get_articles_missing_category(limit: int = 100) -> List[Article]:
    """获取缺失分类字段的文章"""
    db = get_session_local()()
    try:
        articles = db.query(Article).filter(
            Article.category_id.is_(None),
            Article.status == "success",
            Article.content.isnot(None),
            Article.content != ""
        ).limit(limit).all()

        # 避免懒加载问题，提前加载关联对象
        for article in articles:
            _ = article.source
            _ = article.category

        return articles
    finally:
        db.close()


async def analyze_style(title: str, content: str) -> Optional[str]:
    """使用 LLM 分析文章文体"""
    try:
        scraper = get_scraper()
        style = await scraper._extract_style_with_llm(title, content)
        return style
    except Exception as e:
        print(f"  [ERROR] 文体分析失败: {e}")
        return None


def infer_category_from_url(url: str, categories: List[Category]) -> Optional[str]:
    """根据 URL 推断分类"""
    url_lower = url.lower()

    # 简单的 URL 模式匹配
    category_patterns = {
        "gov": ["政策", "政务", "政府"],
        "news": ["新闻", "资讯"],
        "tech": ["科技", "技术"],
        "finance": ["财经", "金融"],
        "edu": ["教育", "学术"],
        "health": ["健康", "医疗"],
    }

    for pattern, keywords in category_patterns.items():
        if pattern in url_lower:
            for cat in categories:
                if any(kw in cat.name for kw in keywords):
                    return cat.id

    return None


async def fix_missing_metadata(
    dry_run: bool = False,
    batch_size: int = 10,
    limit: int = 100
):
    """批量修复缺失的元数据"""
    print("=" * 60)
    print("批量修复历史文档缺失元数据")
    print("=" * 60)

    # 1. 获取缺失文体的文章
    print("\n[INFO] 统计缺失字段的文章...")
    articles_missing_style = get_articles_missing_style(limit)
    articles_missing_category = get_articles_missing_category(limit)

    print(f"  - 缺失文体: {len(articles_missing_style)} 篇")
    print(f"  - 缺失分类: {len(articles_missing_category)} 篇")

    if not articles_missing_style and not articles_missing_category:
        print("\n[OK] 所有文章的元数据都已完整，无需修复")
        return

    # 2. 获取所有分类（用于推断）
    db = get_session_local()()
    try:
        categories = db.query(Category).all()
    finally:
        db.close()

    # 3. 修复文体缺失
    if articles_missing_style:
        print(f"\n[INFO] 开始修复文体字段 ({len(articles_missing_style)} 篇)...")

        fixed_style_count = 0
        failed_style_count = 0

        for i, article in enumerate(articles_missing_style):
            print(f"\n[{i+1}/{len(articles_missing_style)}] {article.title[:50]}...")
            print(f"  URL: {article.url[:60]}...")

            if dry_run:
                print(f"  [DRY RUN] 将分析文体...")
                continue

            # 分析文体
            style = await analyze_style(article.title, article.content)

            if style:
                print(f"  [OK] 检测到文体: {style}")

                # 更新数据库
                db = get_session_local()()
                try:
                    db_article = db.query(Article).filter(Article.id == article.id).first()
                    if db_article:
                        db_article.style = style
                        db.commit()
                        fixed_style_count += 1
                        print(f"  [OK] 已保存到数据库")
                finally:
                    db.close()
            else:
                failed_style_count += 1
                print(f"  [FAIL] 无法识别文体")

            # 每批次之间暂停，避免 API 限流
            if (i + 1) % batch_size == 0 and i < len(articles_missing_style) - 1:
                print(f"\n  [PAUSE] 暂停 2 秒...")
                await asyncio.sleep(2)

        print(f"\n[STATS] 文体修复完成:")
        print(f"  - 成功: {fixed_style_count} 篇")
        print(f"  - 失败: {failed_style_count} 篇")

    # 4. 修复分类缺失（基于 URL 推断）
    if articles_missing_category and categories:
        print(f"\n[INFO] 开始修复分类字段 ({len(articles_missing_category)} 篇)...")

        fixed_category_count = 0

        for article in articles_missing_category:
            category_id = infer_category_from_url(article.url, categories)

            if category_id and not dry_run:
                db = get_session_local()()
                try:
                    db_article = db.query(Article).filter(Article.id == article.id).first()
                    if db_article:
                        db_article.category_id = category_id
                        db.commit()
                        fixed_category_count += 1
                        cat_name = next((c.name for c in categories if c.id == category_id), "未知")
                        print(f"  [OK] {article.title[:40]}... -> {cat_name}")
                finally:
                    db.close()
            elif dry_run:
                print(f"  [DRY RUN] {article.title[:40]}... -> 推断分类: {category_id or '未匹配'}")

        print(f"\n[STATS] 分类修复完成:")
        print(f"  - 成功: {fixed_category_count} 篇")

    print("\n" + "=" * 60)
    print("[DONE] 修复完成！")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="批量修复历史文档缺失的元数据字段")
    parser.add_argument("--dry-run", action="store_true", help="仅显示会修改的内容，不实际执行")
    parser.add_argument("--batch-size", type=int, default=10, help="每批处理的文章数量")
    parser.add_argument("--limit", type=int, default=100, help="最多处理的文章数量")

    args = parser.parse_args()

    asyncio.run(fix_missing_metadata(
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        limit=args.limit
    ))


if __name__ == "__main__":
    main()
