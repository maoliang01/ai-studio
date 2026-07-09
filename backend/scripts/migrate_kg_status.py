"""
为 articles 表添加 KG 同步状态字段
- kg_status: pending / processing / success / failed / skipped
- kg_processed_at: 最近一次抽取完成时间
- kg_content_hash: 抽取时的内容哈希,用于检测内容变化
- kg_error_message: 最近一次失败的错误信息

支持 SQLite 与 PostgreSQL(根据 DATABASE_URL 协议头自动检测)
"""
import os
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_kg_status")

# 待新增字段定义:(列名, SQL 类型)
NEW_COLUMNS = [
    ("kg_status", "VARCHAR(20) DEFAULT 'pending' NOT NULL"),
    ("kg_processed_at", "TIMESTAMP"),
    ("kg_content_hash", "VARCHAR(64)"),
    ("kg_error_message", "TEXT"),
]

# 为已有字段加索引(可选,后续 reconcile 用)
NEW_INDEXES = [
    ("idx_articles_kg_status", "kg_status"),
]


def _column_exists(engine, table: str, column: str) -> bool:
    insp = inspect(engine)
    return column in {c["name"] for c in insp.get_columns(table)}


def _index_exists(engine, index_name: str) -> bool:
    insp = inspect(engine)
    return index_name in {i["name"] for i in insp.get_indexes("articles")}


def run_migration():
    """执行迁移,幂等"""
    db_url = os.getenv("DATABASE_URL", "sqlite:///./ai_studio.db")
    engine = create_engine(db_url)

    with engine.begin() as conn:
        for col_name, col_type in NEW_COLUMNS:
            if _column_exists(engine, "articles", col_name):
                logger.info(f"列 {col_name} 已存在,跳过")
                continue
            try:
                conn.execute(text(
                    f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}"
                ))
                logger.info(f"新增列: {col_name}")
            except (OperationalError, ProgrammingError) as e:
                logger.warning(f"列 {col_name} 添加失败(可能已存在): {e}")

        for idx_name, idx_col in NEW_INDEXES:
            if _index_exists(engine, idx_name):
                logger.info(f"索引 {idx_name} 已存在,跳过")
                continue
            try:
                conn.execute(text(
                    f"CREATE INDEX {idx_name} ON articles ({idx_col})"
                ))
                logger.info(f"新增索引: {idx_name}")
            except (OperationalError, ProgrammingError) as e:
                logger.warning(f"索引 {idx_name} 创建失败: {e}")

        # 回填 kg_content_hash = content_hash(已有字段)
        try:
            result = conn.execute(text("""
                UPDATE articles
                SET kg_content_hash = content_hash
                WHERE kg_content_hash IS NULL AND content_hash IS NOT NULL
            """))
            logger.info(f"回填 kg_content_hash 完成,影响 {result.rowcount} 行")
        except (OperationalError, ProgrammingError) as e:
            logger.warning(f"回填 kg_content_hash 失败: {e}")

    logger.info("迁移完成")


if __name__ == "__main__":
    run_migration()
