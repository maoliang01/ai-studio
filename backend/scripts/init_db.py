#!/usr/bin/env python3
"""
数据库初始化脚本

功能：
1. 创建所有数据表
2. 创建全文搜索索引和触发器
3. 从 settings.json 迁移配置数据（分类、爬取源）
4. 验证数据库连接
"""
import sys
import json
import logging
from pathlib import Path

# 添加 backend 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("init_db")


def load_settings() -> dict:
    """从 settings.json 加载数据"""
    config_dir = Path(__file__).parent.parent
    settings_file = config_dir / "data" / "settings.json"

    if not settings_file.exists():
        logger.warning(f"配置文件不存在: {settings_file}")
        return {}

    with open(settings_file, "r", encoding="utf-8") as f:
        return json.load(f)


def init_database():
    """初始化数据库"""
    from app.core.database import init_db, get_engine, check_db_connection
    from app.models.article import Category, ScrapeSource
    from app.core.database import get_session_local
    from sqlalchemy import text

    # 1. 检查数据库连接
    logger.info("检查数据库连接...")
    if not check_db_connection():
        logger.error("数据库连接失败，请检查配置")
        logger.info("请确保：")
        logger.info("  1. PostgreSQL 服务已启动")
        logger.info("  2. 数据库已创建: CREATE DATABASE ai_studio;")
        logger.info("  3. 配置了正确的连接信息（环境变量或 settings.json）")
        return False

    logger.info("数据库连接正常")

    # 2. 创建表结构
    logger.info("创建数据表...")
    init_db()
    logger.info("数据表创建完成")

    # 3. 创建全文搜索索引
    logger.info("创建全文搜索索引...")
    engine = get_engine()

    with engine.connect() as conn:
        try:
            # 添加 search_vector 列
            conn.execute(text("""
                ALTER TABLE articles
                ADD COLUMN IF NOT EXISTS search_vector tsvector
            """))

            # 创建 GIN 索引
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_articles_fts
                ON articles USING GIN(search_vector)
            """))

            # 创建中文分词配置（如果不存在）
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE name = 'chinese') THEN
                        CREATE TEXT SEARCH CONFIGURATION IF NOT EXISTS chinese (COPY = simple);
                    END IF;
                END
                $$;
            """))

            # 创建触发器函数
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION articles_search_trigger()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.search_vector :=
                        setweight(to_tsvector('chinese', COALESCE(NEW.title, '')), 'A') ||
                        setweight(to_tsvector('chinese', COALESCE(NEW.summary, '')), 'B') ||
                        setweight(to_tsvector('chinese', COALESCE(NEW.content, '')), 'C');
                    RETURN NEW;
                END
                $$ LANGUAGE plpgsql;
            """))

            # 创建触发器
            conn.execute(text("""
                DROP TRIGGER IF EXISTS articles_search_update ON articles;
                CREATE TRIGGER articles_search_update
                BEFORE INSERT OR UPDATE ON articles
                FOR EACH ROW EXECUTE FUNCTION articles_search_trigger()
            """))

            conn.commit()
            logger.info("全文搜索索引创建完成")

        except Exception as e:
            logger.error(f"创建全文搜索索引失败: {e}")
            try:
                conn.rollback()
            except:
                pass

    # 4. 迁移现有数据
    migrate_existing_data()

    return True


def migrate_existing_data():
    """从 settings.json 迁移现有数据"""
    from app.core.database import get_session_local
    from app.models.article import Category, ScrapeSource

    settings = load_settings()
    if not settings:
        logger.info("没有发现配置数据，跳过迁移")
        return

    session = get_session_local()
    db = session()

    try:
        # 迁移分类
        categories = settings.get("categories", {})
        if categories:
            migrated_categories = 0
            for cat_id, cat_data in categories.items():
                existing = db.query(Category).filter(Category.id == cat_id).first()
                if not existing:
                    category = Category(
                        id=cat_data["id"],
                        name=cat_data["name"],
                        color=cat_data.get("color", "#6B7280"),
                        description=cat_data.get("description", ""),
                        folder_name=cat_data.get("folder_name", cat_data["name"]),
                    )
                    db.add(category)
                    migrated_categories += 1

            if migrated_categories > 0:
                db.commit()
                logger.info(f"已迁移 {migrated_categories} 个分类")

        # 迁移爬取源
        sources = settings.get("scrape_sources", {})
        if sources:
            migrated_sources = 0
            for src_id, src_data in sources.items():
                existing = db.query(ScrapeSource).filter(ScrapeSource.id == src_id).first()
                if not existing:
                    source = ScrapeSource(
                        id=src_data["id"],
                        name=src_data["name"],
                        url=src_data["url"],
                        category_id=src_data.get("category"),
                        description=src_data.get("description", ""),
                        is_enabled=src_data.get("is_enabled", True),
                    )
                    db.add(source)
                    migrated_sources += 1

            if migrated_sources > 0:
                db.commit()
                logger.info(f"已迁移 {migrated_sources} 个爬取源")

    except Exception as e:
        logger.error(f"迁移数据失败: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="初始化 AI Studio 数据库")
    parser.add_argument("--check", action="store_true", help="仅检查数据库连接")
    args = parser.parse_args()

    if args.check:
        from app.core.database import check_db_connection
        if check_db_connection():
            logger.info("✓ 数据库连接正常")
            return 0
        else:
            logger.error("✗ 数据库连接失败")
            return 1

    logger.info("=" * 50)
    logger.info("AI Studio 数据库初始化")
    logger.info("=" * 50)

    if init_database():
        logger.info("=" * 50)
        logger.info("✓ 数据库初始化成功!")
        logger.info("=" * 50)
        return 0
    else:
        logger.error("=" * 50)
        logger.error("✗ 数据库初始化失败")
        logger.error("=" * 50)
        return 1


if __name__ == "__main__":
    sys.exit(main())