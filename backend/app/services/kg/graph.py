"""
Neo4j 图数据库服务

提供实体和关系的增删改查操作
"""
import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from neo4j import AsyncGraphDatabase, AsyncDriver, Record

logger = logging.getLogger("ai-studio")

# Neo4j 配置
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


@dataclass
class EntityNode:
    """实体节点"""
    name: str
    entity_type: str
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


@dataclass
class Relationship:
    """关系边"""
    source: str
    target: str
    rel_type: str
    properties: Optional[Dict[str, Any]] = None


class Neo4jService:
    """Neo4j 图数据库服务"""

    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver: Optional[AsyncDriver] = None

    async def connect(self) -> None:
        """建立数据库连接"""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            logger.info(f"Neo4j 连接已建立: {self.uri}")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j 连接已关闭")

    async def verify_connection(self) -> bool:
        """验证连接是否正常"""
        try:
            if not self._driver:
                await self.connect()
            async with self._driver.session() as session:
                result = await session.run("RETURN 1 as test")
                await result.single()
            return True
        except Exception as e:
            logger.error(f"Neo4j 连接验证失败: {e}")
            return False

    async def init_schema(self) -> None:
        """初始化图谱模式（创建约束和索引）"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            # 创建唯一性约束
            constraints = [
                "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (a:Article) REQUIRE a.id IS UNIQUE",
                "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            ]
            # 创建索引
            indexes = [
                "CREATE INDEX article_title IF NOT EXISTS FOR (a:Article) ON (a.title)",
                "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
                "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            ]

            for cql in constraints + indexes:
                try:
                    await session.run(cql)
                except Exception as e:
                    # 忽略已存在的约束/索引错误
                    logger.debug(f"约束/索引创建: {e}")

            logger.info("Neo4j 模式初始化完成")

    async def create_article_node(
        self,
        article_id: str,
        title: str,
        url: str,
        summary: Optional[str] = None
    ) -> bool:
        """创建文章节点"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MERGE (a:Article {id: $article_id})
            SET a.title = $title,
                a.url = $url,
                a.summary = $summary,
                a.updated_at = datetime()
            RETURN a
            """
            try:
                await session.run(query, {
                    "article_id": article_id,
                    "title": title,
                    "url": url,
                    "summary": summary
                })
                return True
            except Exception as e:
                logger.error(f"创建文章节点失败: {e}")
                return False

    async def create_entity_node(
        self,
        name: str,
        entity_type: str,
        description: Optional[str] = None
    ) -> bool:
        """创建实体节点"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MERGE (e:Entity {name: $name})
            SET e.entity_type = $entity_type,
                e.description = $description,
                e.updated_at = datetime()
            RETURN e
            """
            try:
                await session.run(query, {
                    "name": name,
                    "entity_type": entity_type,
                    "description": description
                })
                return True
            except Exception as e:
                logger.error(f"创建实体节点失败: {e}")
                return False

    async def link_article_to_entity(
        self,
        article_id: str,
        entity_name: str,
        confidence: float = 1.0
    ) -> bool:
        """建立文章与实体的关联"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MATCH (a:Article {id: $article_id})
            MATCH (e:Entity {name: $entity_name})
            MERGE (a)-[r:CONTAINS_ENTITY]->(e)
            SET r.confidence = $confidence,
                r.updated_at = datetime()
            RETURN r
            """
            try:
                await session.run(query, {
                    "article_id": article_id,
                    "entity_name": entity_name,
                    "confidence": confidence
                })
                return True
            except Exception as e:
                logger.error(f"建立文章-实体关联失败: {e}")
                return False

    async def link_entities(
        self,
        source_entity: str,
        target_entity: str,
        rel_type: str,
        confidence: float = 1.0
    ) -> bool:
        """建立实体之间的关系"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MATCH (s:Entity {name: $source_entity})
            MATCH (t:Entity {name: $target_entity})
            MERGE (s)-[r:RELATES_TO]->(t)
            SET r.rel_type = $rel_type,
                r.confidence = $confidence,
                r.updated_at = datetime()
            RETURN r
            """
            try:
                await session.run(query, {
                    "source_entity": source_entity,
                    "target_entity": target_entity,
                    "rel_type": rel_type,
                    "confidence": confidence
                })
                return True
            except Exception as e:
                logger.error(f"建立实体关联失败: {e}")
                return False

    async def batch_create_entities_and_relations(
        self,
        article_id: str,
        entities: List[EntityNode],
        relations: List[Relationship]
    ) -> Dict[str, int]:
        """批量创建实体和关系"""
        if not self._driver:
            await self.connect()

        stats = {"entities_created": 0, "relations_created": 0}

        async with self._driver.session() as session:
            # 批量创建实体
            for entity in entities:
                success = await self.create_entity_node(
                    name=entity.name,
                    entity_type=entity.entity_type,
                    description=entity.description
                )
                if success:
                    stats["entities_created"] += 1

            # 批量建立文章-实体关联
            for entity in entities:
                await self.link_article_to_entity(article_id, entity.name)

            # 批量建立实体间关系
            for rel in relations:
                success = await self.link_entities(
                    source_entity=rel.source,
                    target_entity=rel.target,
                    rel_type=rel.rel_type,
                    confidence=rel.properties.get("confidence", 1.0) if rel.properties else 1.0
                )
                if success:
                    stats["relations_created"] += 1

        return stats

    async def search_entities(
        self,
        query: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """搜索实体"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            if query:
                cql = """
                MATCH (e:Entity)
                WHERE e.name CONTAINS $query
                """
                params = {"query": query, "limit": limit}
            else:
                cql = "MATCH (e:Entity)"
                params = {"limit": limit}

            if entity_type:
                cql += " WHERE e.entity_type = $entity_type" if "WHERE" in cql else " AND e.entity_type = $entity_type"

            cql += " RETURN e ORDER BY e.name LIMIT $limit"

            try:
                result = await session.run(cql, params)
                records = await result.data()
                return [dict(record["e"]) for record in records]
            except Exception as e:
                logger.error(f"搜索实体失败: {e}")
                return []

    async def get_article_entities(self, article_id: str) -> List[Dict[str, Any]]:
        """获取文章关联的所有实体"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MATCH (a:Article {id: $article_id})-[:CONTAINS_ENTITY]->(e:Entity)
            RETURN e
            """
            try:
                result = await session.run(query, {"article_id": article_id})
                records = await result.data()
                return [dict(record["e"]) for record in records]
            except Exception as e:
                logger.error(f"获取文章实体失败: {e}")
                return []

    async def get_entity_neighbors(
        self,
        entity_name: str,
        depth: int = 1
    ) -> List[Dict[str, Any]]:
        """获取实体的邻居节点和关系"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = f"""
            MATCH path = (e:Entity {{name: $entity_name}})-[r*1..{depth}]-(connected)
            UNWIND nodes(path) as node
            UNWIND relationships(path) as rel
            WITH collect(DISTINCT node) as nodes, collect(DISTINCT rel) as rels
            RETURN nodes, rels
            """
            try:
                result = await session.run(query, {"entity_name": entity_name})
                record = await result.single()
                if record:
                    nodes = [dict(n) for n in record["nodes"]]
                    rels = [dict(r) for r in record["rels"]]
                    return {"nodes": nodes, "relations": rels}
                return {"nodes": [], "relations": []}
            except Exception as e:
                logger.error(f"获取邻居节点失败: {e}")
                return {"nodes": [], "relations": []}

    async def get_graph_stats(self) -> Dict[str, int]:
        """获取图谱统计信息"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            stats = {}
            queries = {
                "articles": "MATCH (a:Article) RETURN count(a) as count",
                "entities": "MATCH (e:Entity) RETURN count(e) as count",
                "article_entity_links": "MATCH ()-[r:CONTAINS_ENTITY]->() RETURN count(r) as count",
                "entity_relations": "MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count",
            }

            for key, cql in queries.items():
                try:
                    result = await session.run(cql)
                    record = await result.single()
                    stats[key] = record["count"] if record else 0
                except Exception as e:
                    logger.debug(f"统计查询 {key} 失败: {e}")
                    stats[key] = 0

            return stats

    async def delete_article_kg(self, article_id: str) -> bool:
        """删除文章关联的知识图谱数据（保留文章节点）"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            query = """
            MATCH (a:Article {id: $article_id})-[r:CONTAINS_ENTITY]->(e:Entity)
            DELETE r
            WITH a, e
            WHERE NOT (e)<-[:CONTAINS_ENTITY]-()
            DETACH DELETE e
            """
            try:
                await session.run(query, {"article_id": article_id})
                return True
            except Exception as e:
                logger.error(f"删除文章知识图谱失败: {e}")
                return False

    async def export_graph_data(self, limit: int = 1000) -> Dict[str, Any]:
        """导出图谱数据（用于可视化）"""
        if not self._driver:
            await self.connect()

        async with self._driver.session() as session:
            # 导出节点
            nodes_query = """
            MATCH (n) WHERE 'Article' IN labels(n) OR 'Entity' IN labels(n)
            RETURN n, labels(n) as labels
            LIMIT $limit
            """
            # 导出边
            edges_query = """
            MATCH ()-[r]->()
            WHERE type(r) IN ['CONTAINS_ENTITY', 'RELATES_TO']
            RETURN r, startNode(r) as source, endNode(r) as target
            LIMIT $limit
            """

            try:
                nodes_result = await session.run(nodes_query, {"limit": limit})
                nodes_records = await nodes_result.data()

                edges_result = await session.run(edges_query, {"limit": limit})
                edges_records = await edges_result.data()

                # Neo4j 5.x 返回 dict 格式，需要手动处理
                nodes = []
                for record in nodes_records:
                    node_dict = record["n"]
                    labels = record["labels"]
                    node_id = str(node_dict.get("id", "")) or node_dict.get("name", "")
                    nodes.append({
                        "id": node_id,
                        "label": node_dict.get("title", "") or node_dict.get("name", ""),
                        "type": labels[0] if labels else "Unknown",
                        "data": node_dict
                    })

                edges = []
                for record in edges_records:
                    # Neo4j 返回的关系格式: (start_node, type, end_node) 元组
                    rel_tuple = record["r"]
                    if isinstance(rel_tuple, tuple) and len(rel_tuple) == 3:
                        source_dict, rel_type, target_dict = rel_tuple
                    else:
                        source_dict = record.get("source", {})
                        target_dict = record.get("target", {})
                        rel_type = rel_tuple.get("type", "RELATES_TO") if isinstance(rel_tuple, dict) else "RELATES_TO"

                    edges.append({
                        "source": str(source_dict.get("id", "")) or source_dict.get("name", ""),
                        "target": str(target_dict.get("id", "")) or target_dict.get("name", ""),
                        "type": rel_type,
                        "data": {"type": rel_type}
                    })

                return {"nodes": nodes, "edges": edges}
            except Exception as e:
                logger.error(f"导出图谱数据失败: {e}")
                return {"nodes": [], "edges": []}


# 全局服务实例
neo4j_service = Neo4jService()