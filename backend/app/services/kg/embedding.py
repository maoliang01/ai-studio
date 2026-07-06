"""
向量生成服务

使用 sentence-transformers 生成文本向量
用于语义检索
"""
import os
import logging
from typing import List, Optional, Dict, Any
from functools import lru_cache

logger = logging.getLogger("ai-studio")

# 模型配置
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384  # MiniLM-L12-v2 的向量维度


class EmbeddingService:
    """向量生成服务"""

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        device: Optional[str] = None,
        cache_folder: Optional[str] = None
    ):
        """
        初始化向量服务

        Args:
            model_name: 模型名称
            device: 设备（"cpu", "cuda", "mps"）
            cache_folder: 模型缓存目录
        """
        self.model_name = model_name
        self.device = device or self._detect_device()
        self.cache_folder = cache_folder or os.path.join(
            os.path.expanduser("~"),
            ".cache",
            "huggingface"
        )
        self._model = None

    def _detect_device(self) -> str:
        """检测可用设备"""
        import torch
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _load_model(self):
        """懒加载模型"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"加载 Embedding 模型: {self.model_name}, 设备: {self.device}")

                os.makedirs(self.cache_folder, exist_ok=True)

                self._model = SentenceTransformer(
                    self.model_name,
                    device=self.device,
                    cache_folder=self.cache_folder
                )
                logger.info(f"Embedding 模型加载完成: {self.model_name}")
            except ImportError:
                raise ImportError(
                    "sentence-transformers 未安装。请运行: pip install sentence-transformers"
                )

    async def encode(self, texts: List[str], normalize: bool = True) -> List[List[float]]:
        """
        将文本列表转换为向量

        Args:
            texts: 文本列表
            normalize: 是否归一化向量

        Returns:
            List[List[float]]: 向量列表
        """
        if not texts:
            return []

        self._load_model()

        try:
            # 编码
            embeddings = self._model.encode(
                texts,
                normalize_embeddings=normalize,
                show_progress_bar=False,
                convert_to_numpy=True
            )

            # 转换为 Python 列表
            return embeddings.tolist()

        except Exception as e:
            logger.error(f"向量编码失败: {e}")
            raise

    async def encode_single(self, text: str, normalize: bool = True) -> List[float]:
        """
        将单个文本转换为向量

        Args:
            text: 文本
            normalize: 是否归一化

        Returns:
            List[float]: 向量
        """
        result = await self.encode([text], normalize)
        return result[0] if result else []

    def get_dimension(self) -> int:
        """获取向量维度"""
        return EMBEDDING_DIM


class VectorStore:
    """向量存储服务（使用 pgvector）"""

    def __init__(self, db_session):
        """
        初始化向量存储

        Args:
            db_session: SQLAlchemy 数据库会话
        """
        self.db = db_session

    def init_table(self) -> bool:
        """初始化向量存储表"""
        from sqlalchemy import text

        try:
            # 确保 pgvector 扩展已启用
            self.db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # 创建向量存储表
            self.db.execute(text("""
                CREATE TABLE IF NOT EXISTS article_embeddings (
                    article_id VARCHAR(36) PRIMARY KEY,
                    title_vector VECTOR(384),
                    content_vector VECTOR(384),
                    summary_vector VECTOR(384),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
                )
            """))

            # 创建索引
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_article_embeddings_title
                ON article_embeddings USING HNSW (title_vector vector_cosine_ops)
            """))

            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_article_embeddings_content
                ON article_embeddings USING HNSW (content_vector vector_cosine_ops)
            """))

            self.db.commit()
            logger.info("向量存储表初始化完成")
            return True

        except Exception as e:
            logger.error(f"向量存储表初始化失败: {e}")
            self.db.rollback()
            return False

    def save_embeddings(
        self,
        article_id: str,
        title_vector: List[float],
        content_vector: List[float],
        summary_vector: Optional[List[float]] = None
    ) -> bool:
        """保存文章向量"""
        from sqlalchemy import text

        try:
            # 确保向量格式正确
            title_vec_str = "[" + ",".join(str(v) for v in title_vector) + "]"
            content_vec_str = "[" + ",".join(str(v) for v in content_vector) + "]"
            summary_vec_str = None
            if summary_vector:
                summary_vec_str = "[" + ",".join(str(v) for v in summary_vector) + "]"

            query = text("""
                INSERT INTO article_embeddings (article_id, title_vector, content_vector, summary_vector)
                VALUES (:article_id, :title_vector, :content_vector, :summary_vector)
                ON CONFLICT (article_id) DO UPDATE SET
                    title_vector = EXCLUDED.title_vector,
                    content_vector = EXCLUDED.content_vector,
                    summary_vector = EXCLUDED.summary_vector,
                    updated_at = CURRENT_TIMESTAMP
            """)

            self.db.execute(query, {
                "article_id": article_id,
                "title_vector": title_vec_str,
                "content_vector": content_vec_str,
                "summary_vector": summary_vec_str
            })

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"保存向量失败: {e}")
            self.db.rollback()
            return False

    def search_by_vector(
        self,
        query_vector: List[float],
        limit: int = 10,
        field: str = "content_vector",
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """通过向量搜索相似文章"""
        from sqlalchemy import text

        try:
            vec_str = "[" + ",".join(str(v) for v in query_vector) + "]"

            query = text(f"""
                SELECT
                    e.article_id,
                    a.title,
                    a.url,
                    a.summary,
                    1 - (e.{field} <=> CAST(:vector AS VECTOR(384))) as similarity
                FROM article_embeddings e
                JOIN articles a ON e.article_id = a.id
                WHERE 1 - (e.{field} <=> CAST(:vector AS VECTOR(384))) > :threshold
                ORDER BY e.{field} <=> CAST(:vector AS VECTOR(384))
                LIMIT :limit
            """)

            result = self.db.execute(query, {
                "vector": vec_str,
                "threshold": threshold,
                "limit": limit
            })

            return [
                {
                    "article_id": row[0],
                    "title": row[1],
                    "url": row[2],
                    "summary": row[3],
                    "similarity": float(row[4])
                }
                for row in result.fetchall()
            ]

        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []

    def get_embeddings(self, article_id: str) -> Optional[Dict[str, List[float]]]:
        """获取文章向量"""
        from sqlalchemy import text

        try:
            query = text("""
                SELECT title_vector, content_vector, summary_vector
                FROM article_embeddings
                WHERE article_id = :article_id
            """)

            result = self.db.execute(query, {"article_id": article_id})
            row = result.fetchone()

            if row:
                def parse_vector(vec):
                    if vec is None:
                        return None
                    # 格式: [0.1,0.2,0.3]
                    import re
                    numbers = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', str(vec))
                    return [float(n) for n in numbers]

                return {
                    "title_vector": parse_vector(row[0]),
                    "content_vector": parse_vector(row[1]),
                    "summary_vector": parse_vector(row[2])
                }

            return None

        except Exception as e:
            logger.error(f"获取向量失败: {e}")
            return None

    def delete_embeddings(self, article_id: str) -> bool:
        """删除文章向量"""
        from sqlalchemy import text

        try:
            query = text("DELETE FROM article_embeddings WHERE article_id = :article_id")
            self.db.execute(query, {"article_id": article_id})
            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            self.db.rollback()
            return False


# 全局向量服务实例（延迟初始化，torch 未安装时不会报错）
_embedding_service_instance = None

def get_embedding_service() -> EmbeddingService:
    """获取 Embedding 服务实例（懒加载）"""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance