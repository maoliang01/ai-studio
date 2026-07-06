"""
知识图谱数据库迁移脚本

启用 pgvector 扩展并创建向量存储表
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import get_engine


def run_migration():
    """运行数据库迁移"""
    engine = get_engine()

    with engine.connect() as conn:
        print("开始数据库迁移...")

        try:
            # 1. 启用 pgvector 扩展
            print("1. 启用 pgvector 扩展...")
            result = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            if not result.fetchone():
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                print("   ✓ pgvector 扩展已启用")
            else:
                print("   ✓ pgvector 扩展已存在")

            # 2. 创建向量存储表
            print("2. 创建向量存储表...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS article_embeddings (
                    article_id VARCHAR(36) PRIMARY KEY,
                    title_vector VECTOR(384),
                    content_vector VECTOR(384),
                    summary_vector VECTOR(384),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
                )
            """))
            print("   ✓ 向量存储表已创建")

            # 3. 创建索引
            print("3. 创建向量索引...")
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_article_embeddings_title
                    ON article_embeddings USING HNSW (title_vector vector_cosine_ops)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_article_embeddings_content
                    ON article_embeddings USING HNSW (content_vector vector_cosine_ops)
                """))
                print("   ✓ 向量索引已创建")
            except Exception as e:
                print(f"   ⚠ 索引创建失败（可能是 pgvector 版本问题）: {e}")

            conn.commit()
            print("\n✅ 数据库迁移完成！")
            return True

        except Exception as e:
            conn.rollback()
            print(f"\n❌ 迁移失败: {e}")
            return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)