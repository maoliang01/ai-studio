"""测试 KG 状态字段迁移的幂等性"""
import os
import sqlite3
import tempfile
import importlib.util
from pathlib import Path


def test_migrate_kg_status_is_idempotent():
    """连续跑两次迁移不应报错,且字段只存在一份"""
    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # 初始化一个空 articles 表(仅主键)
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE articles (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                content TEXT,
                status TEXT DEFAULT 'pending',
                content_hash TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        # 把 DATABASE_URL 指向临时库
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

        # 动态加载迁移脚本
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "migrate_kg_status.py"
        spec = importlib.util.spec_from_file_location("migrate_kg_status", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 跑两次
        module.run_migration()
        module.run_migration()  # 必须不报错

        # 验证字段
        conn = sqlite3.connect(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
        conn.close()

        assert "kg_status" in cols
        assert "kg_processed_at" in cols
        assert "kg_content_hash" in cols
        assert "kg_error_message" in cols
    finally:
        os.unlink(db_path)
