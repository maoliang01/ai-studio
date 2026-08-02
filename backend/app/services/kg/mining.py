"""不依赖 Neo4j GDS 的轻量知识挖掘算法。"""

from collections import Counter
from difflib import SequenceMatcher
import math
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Set

import networkx as nx
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize


def normalize_entity_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name or "").casefold()
    return re.sub(r"[\s\-_·•（）()《》]+", "", normalized)


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set, right_set = set(left), set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0


def find_relation_evidence(
    content: str,
    source: str,
    target: str,
    max_length: int = 500,
) -> str:
    """只返回同时包含关系两端实体的原文句子。"""
    if not content or not source or not target:
        return ""
    normalized = re.sub(r"\s+", " ", content).strip()
    sentences = re.split(r"(?<=[。！？!?；;])\s*", normalized)
    for sentence in sentences:
        if source in sentence and target in sentence:
            return sentence.strip()[:max_length]
    return ""


def discover_alias_candidates(
    entities: List[Dict[str, Any]],
    min_shared_articles: int = 2,
    min_score: float = 0.32,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """根据名称和跨文档覆盖重叠生成待人工确认的别名候选。"""
    candidates = []
    for index, left in enumerate(entities):
        left_articles = set(left.get("article_ids") or [])
        if not left_articles:
            continue
        for right in entities[index + 1:]:
            if left.get("entity_type") != right.get("entity_type"):
                continue
            explicit_types = {
                relation.get("rel_type")
                for relation in left.get("related_entities", [])
                if relation.get("name") == right.get("name")
            }
            if explicit_types - {None, "", "related_to"}:
                continue
            right_articles = set(right.get("article_ids") or [])
            shared = sorted(left_articles & right_articles)
            if len(shared) < min_shared_articles:
                continue

            left_name = normalize_entity_name(left.get("name", ""))
            right_name = normalize_entity_name(right.get("name", ""))
            name_similarity = SequenceMatcher(None, left_name, right_name).ratio()
            article_overlap = _jaccard(left_articles, right_articles)
            containment = bool(
                min(len(left_name), len(right_name)) >= 3
                and (left_name in right_name or right_name in left_name)
            )
            score = 0.62 * article_overlap + 0.28 * name_similarity
            if containment:
                score += 0.1
            if score < min_score:
                continue

            reasons = [f"共同出现于 {len(shared)} 篇文章"]
            if article_overlap >= 0.5:
                reasons.append("文章来源高度重叠")
            if containment:
                reasons.append("名称存在包含关系")
            elif name_similarity >= 0.6:
                reasons.append("名称相似")
            candidates.append({
                "left": left,
                "right": right,
                "score": round(min(score, 1.0), 4),
                "shared_articles": shared,
                "name_similarity": round(name_similarity, 4),
                "article_overlap": round(article_overlap, 4),
                "reasons": reasons,
            })

    candidates.sort(
        key=lambda item: (item["score"], len(item["shared_articles"])),
        reverse=True,
    )
    return candidates[:limit]


def louvain_entity_communities(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    min_size: int = 3,
    resolution: float = 1.2,
) -> List[Dict[str, Any]]:
    """使用 NetworkX Louvain 发现紧密实体群。"""
    node_by_name = {node["name"]: node for node in nodes}
    graph = nx.Graph()
    graph.add_nodes_from(node_by_name)
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if source not in node_by_name or target not in node_by_name or source == target:
            continue
        weight = float(edge.get("weight") or 1.0)
        previous = graph.get_edge_data(source, target, {}).get("weight", 0.0)
        graph.add_edge(source, target, weight=previous + weight)

    partitions = nx.community.louvain_communities(
        graph,
        weight="weight",
        resolution=resolution,
        seed=42,
    ) if graph.number_of_edges() else []

    communities = []
    weighted_degree = dict(graph.degree(weight="weight"))
    for partition in partitions:
        members = sorted(partition)
        if len(members) < min_size:
            continue
        member_set = set(members)
        internal_edges = sum(
            1 for edge in edges
            if edge.get("source") in member_set and edge.get("target") in member_set
        )
        article_ids = sorted({
            article_id
            for member in members
            for article_id in node_by_name[member].get("article_ids", [])
        })
        types = Counter(node_by_name[member].get("entity_type") or "OTHER" for member in members)
        ranked_members = sorted(
            members,
            key=lambda item: (-weighted_degree.get(item, 0.0), item),
        )
        possible_edges = len(members) * (len(members) - 1) / 2
        max_degree = max((weighted_degree.get(member, 0.0) for member in members), default=1.0)
        core_entities = [
            {
                "name": name,
                "score": round(weighted_degree.get(name, 0.0) / max_degree, 4)
                if max_degree else 0.0,
            }
            for name in ranked_members[:3]
        ]
        dominant_types = [name for name, _ in types.most_common(2)]
        communities.append({
            "label": "、".join(ranked_members[:3]),
            "size": len(members),
            "members": [node_by_name[name] for name in ranked_members],
            "article_ids": article_ids,
            "article_count": len(article_ids),
            "internal_edges": internal_edges,
            "density": round(internal_edges / possible_edges, 4) if possible_edges else 0.0,
            "entity_types": dict(types),
            "core_entities": core_entities,
            "bridge_entities": [],
            "summary": (
                f"以{'、'.join(ranked_members[:3])}为核心，"
                f"包含{len(members)}个实体，覆盖{len(article_ids)}篇文章，"
                f"主要类型为{'、'.join(dominant_types)}。"
            ),
        })

    communities.sort(
        key=lambda item: (item["size"], item["internal_edges"], item["article_count"]),
        reverse=True,
    )
    for index, community in enumerate(communities, start=1):
        community["id"] = f"community-{index}"
    community_by_member = {
        member["name"]: community["id"]
        for community in communities
        for member in community["members"]
    }
    bridge_counts: Dict[str, int] = Counter()
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        source_community = community_by_member.get(source)
        target_community = community_by_member.get(target)
        if source_community and target_community and source_community != target_community:
            bridge_counts[source] += 1
            bridge_counts[target] += 1
    for community in communities:
        community["bridge_entities"] = [
            {"name": member["name"], "external_connections": bridge_counts[member["name"]]}
            for member in community["members"]
            if bridge_counts[member["name"]] > 0
        ][:5]
    return communities


def discover_transitive_inferences(
    edges: List[Dict[str, Any]],
    relation_types: Optional[Set[str]] = None,
    max_hops: int = 3,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Discover explainable transitive candidates without writing inferred edges."""
    allowed = relation_types or {"part_of", "located_in", "precedes", "succeeds"}
    max_hops = max(2, min(int(max_hops), 5))
    candidates = []
    for relation_type in sorted(allowed):
        relation_edges = [edge for edge in edges if edge.get("rel_type") == relation_type]
        graph = nx.DiGraph()
        direct_pairs = set()
        edge_by_pair = {}
        for edge in relation_edges:
            source, target = edge.get("source"), edge.get("target")
            if not source or not target or source == target:
                continue
            graph.add_edge(source, target)
            direct_pairs.add((source, target))
            edge_by_pair[(source, target)] = edge

        for source in sorted(graph.nodes):
            lengths = nx.single_source_shortest_path_length(graph, source, cutoff=max_hops)
            for target, hops in sorted(lengths.items()):
                if hops < 2 or (source, target) in direct_pairs:
                    continue
                path = nx.shortest_path(graph, source, target)
                evidence_edges = [
                    edge_by_pair[(path[index], path[index + 1])]
                    for index in range(len(path) - 1)
                ]
                confidence = math.prod(
                    max(0.0, min(float(edge.get("confidence") or 0.6), 1.0))
                    for edge in evidence_edges
                )
                article_ids = sorted({
                    article_id
                    for edge in evidence_edges
                    for article_id in edge.get("source_articles", [])
                })
                candidates.append({
                    "source": source,
                    "target": target,
                    "rel_type": relation_type,
                    "path": path,
                    "hops": hops,
                    "confidence": round(confidence, 4),
                    "source_articles": article_ids,
                    "evidence_edges": evidence_edges,
                    "rule": f"{relation_type} 传递规则",
                })

    candidates.sort(key=lambda item: (-item["confidence"], item["hops"], item["source"], item["target"]))
    return candidates[:limit]


def predict_structural_links(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    min_common_neighbors: int = 2,
    min_score: float = 0.2,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Rank explainable missing links using local graph structure."""
    node_by_name = {
        node["name"]: node
        for node in nodes
        if node.get("name") and node.get("entity_type") != "DATE"
    }
    graph = nx.Graph()
    graph.add_nodes_from(node_by_name)
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if source in node_by_name and target in node_by_name and source != target:
            graph.add_edge(source, target)

    candidates = []
    for source, target in nx.non_edges(graph):
        common = sorted(nx.common_neighbors(graph, source, target))
        if len(common) < min_common_neighbors:
            continue
        union_size = len(set(graph[source]) | set(graph[target]))
        jaccard = len(common) / union_size if union_size else 0.0
        adamic_adar = sum(
            1.0 / math.log(graph.degree(neighbor))
            for neighbor in common
            if graph.degree(neighbor) > 1
        )
        resource_allocation = sum(
            1.0 / graph.degree(neighbor)
            for neighbor in common
            if graph.degree(neighbor) > 0
        )
        score = (
            0.45 * jaccard
            + 0.35 * min(adamic_adar / 3.0, 1.0)
            + 0.20 * min(len(common) / 5.0, 1.0)
        )
        if score < min_score:
            continue
        candidates.append({
            "source": source,
            "source_type": node_by_name[source].get("entity_type"),
            "target": target,
            "target_type": node_by_name[target].get("entity_type"),
            "score": round(score, 4),
            "common_neighbors": common,
            "common_neighbor_count": len(common),
            "jaccard": round(jaccard, 4),
            "adamic_adar": round(adamic_adar, 4),
            "resource_allocation": round(resource_allocation, 4),
            "reasons": [
                f"共享 {len(common)} 个邻居",
                f"Jaccard {jaccard:.2f}",
                f"Adamic-Adar {adamic_adar:.2f}",
            ],
        })

    candidates.sort(
        key=lambda item: (-item["score"], -item["common_neighbor_count"], item["source"], item["target"])
    )
    return candidates[:limit]


def build_spectral_embeddings(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    dimensions: int = 16,
) -> Dict[str, List[float]]:
    """Create deterministic normalized structural embeddings with TruncatedSVD."""
    names = sorted({node.get("name") for node in nodes if node.get("name")})
    if len(names) < 2:
        return {name: [0.0] for name in names}
    index = {name: position for position, name in enumerate(names)}
    rows, columns, values = [], [], []
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if source not in index or target not in index or source == target:
            continue
        weight = max(float(edge.get("weight") or 1.0), 0.01)
        rows.extend((index[source], index[target]))
        columns.extend((index[target], index[source]))
        values.extend((weight, weight))
    matrix = csr_matrix((values, (rows, columns)), shape=(len(names), len(names)))
    component_count = max(1, min(int(dimensions), len(names) - 1))
    embedding = TruncatedSVD(n_components=component_count, random_state=42).fit_transform(matrix)
    embedding = normalize(embedding, norm="l2", axis=1)
    return {
        name: [round(float(value), 8) for value in embedding[index[name]].tolist()]
        for name in names
    }


def rank_embedding_similarities(
    entity_name: str,
    embeddings: Dict[str, List[float]],
    node_by_name: Dict[str, Dict[str, Any]],
    limit: int = 20,
    same_type: bool = False,
    min_score: float = 0.0,
) -> List[Dict[str, Any]]:
    """Rank cosine similarity for already normalized graph embeddings."""
    if entity_name not in embeddings:
        return []
    source_vector = np.asarray(embeddings[entity_name], dtype=float)
    source_type = node_by_name.get(entity_name, {}).get("entity_type")
    results = []
    for name, raw_vector in embeddings.items():
        if name == entity_name:
            continue
        node = node_by_name.get(name, {})
        if same_type and node.get("entity_type") != source_type:
            continue
        vector = np.asarray(raw_vector, dtype=float)
        if vector.shape != source_vector.shape:
            continue
        score = float(np.dot(source_vector, vector))
        if score < min_score:
            continue
        results.append({
            "name": name,
            "entity_type": node.get("entity_type"),
            "subtype": node.get("subtype"),
            "score": round(score, 4),
        })
    results.sort(key=lambda item: (-item["score"], item["name"]))
    return results[:limit]


def evaluate_embedding_quality(
    embeddings: Dict[str, List[float]],
    edges: List[Dict[str, Any]],
    k: int = 5,
) -> Dict[str, Any]:
    """Measure how often structural neighbors are recovered by cosine ranking."""
    k = max(1, int(k))
    adjacency: Dict[str, Set[str]] = {name: set() for name in embeddings}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in adjacency and target in adjacency and source != target:
            adjacency[source].add(target)
            adjacency[target].add(source)

    precisions = []
    recalls = []
    neighbor_scores = []
    for name, neighbors in adjacency.items():
        if not neighbors:
            continue
        source_vector = np.asarray(embeddings[name], dtype=float)
        ranked = sorted(
            (
                (other, float(np.dot(source_vector, np.asarray(vector, dtype=float))))
                for other, vector in embeddings.items()
                if other != name and len(vector) == len(source_vector)
            ),
            key=lambda item: (-item[1], item[0]),
        )
        top_names = {other for other, _ in ranked[:k]}
        hits = len(top_names & neighbors)
        precisions.append(hits / min(k, len(ranked)) if ranked else 0.0)
        recalls.append(hits / min(k, len(neighbors)))
        neighbor_scores.extend(score for other, score in ranked if other in neighbors)

    evaluated = len(precisions)
    return {
        "k": k,
        "embedded_entities": len(embeddings),
        "evaluated_entities": evaluated,
        "coverage": round(evaluated / len(embeddings), 4) if embeddings else 0.0,
        "precision_at_k": round(sum(precisions) / evaluated, 4) if evaluated else 0.0,
        "recall_at_k": round(sum(recalls) / evaluated, 4) if evaluated else 0.0,
        "mean_neighbor_similarity": round(
            sum(neighbor_scores) / len(neighbor_scores), 4
        ) if neighbor_scores else 0.0,
    }


CAUSAL_MARKERS = {
    "causes": ("导致", "引发", "造成", "致使", "使得"),
    "enables": ("推动", "促进", "支撑", "助力", "有助于"),
}


def discover_historical_causal_claims(
    articles: List[Dict[str, Any]],
    entities_by_article: Dict[str, List[Dict[str, Any]]],
    max_distance: int = 180,
) -> List[Dict[str, Any]]:
    """Build low-confidence causal evidence records from article sentences.

    Both endpoints must already be entities linked to the same article, and the
    marker must occur between their mentions. Results remain review candidates;
    this function never materializes graph relationships.
    """
    marker_relations = {
        marker: relation_type
        for relation_type, markers in CAUSAL_MARKERS.items()
        for marker in markers
    }
    records: List[Dict[str, Any]] = []
    for article in articles:
        article_id = str(article.get("id") or article.get("article_id") or "").strip()
        text = " ".join(
            value.strip()
            for value in (str(article.get("content") or ""), str(article.get("summary") or ""))
            if value.strip()
        )
        raw_entities = entities_by_article.get(article_id, [])
        names = sorted(
            {
                str(entity.get("name") if isinstance(entity, dict) else entity).strip()
                for entity in raw_entities
                if (entity.get("name") if isinstance(entity, dict) else entity)
            },
            key=lambda name: (-len(name), name),
        )
        if not text or len(names) < 2:
            continue

        for sentence in re.split(r"(?<=[。！？!?；;])|\n+", text):
            sentence = re.sub(r"\s+", " ", sentence).strip()
            if not sentence:
                continue
            mentions = []
            for name in names:
                start = 0
                while True:
                    index = sentence.find(name, start)
                    if index < 0:
                        break
                    mentions.append((index, index + len(name), name))
                    start = index + len(name)
            if len(mentions) < 2:
                continue

            for marker, rel_type in marker_relations.items():
                marker_start = 0
                while True:
                    marker_index = sentence.find(marker, marker_start)
                    if marker_index < 0:
                        break
                    marker_end = marker_index + len(marker)
                    before = [item for item in mentions if item[1] <= marker_index]
                    after = [item for item in mentions if item[0] >= marker_end]
                    if before and after:
                        source_mention = max(before, key=lambda item: (item[1], item[0]))
                        target_mention = min(after, key=lambda item: (item[0], -item[1]))
                        distance = marker_index - source_mention[1] + target_mention[0] - marker_end
                        if source_mention[2] != target_mention[2] and distance <= max_distance:
                            confidence = round(max(0.45, 0.68 - min(distance, 150) * 0.0015), 4)
                            records.append({
                                "source": source_mention[2],
                                "target": target_mention[2],
                                "rel_type": rel_type,
                                "evidence": sentence[:500],
                                "confidence": confidence,
                                "article_id": article_id,
                                "discovery_source": "historical_article",
                                "marker": marker,
                                "mention_distance": distance,
                            })
                    marker_start = marker_end
    return records


def discover_causal_candidates(
    claims: List[Dict[str, Any]],
    existing_relations: Optional[Set[tuple[str, str, str]]] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Extract conservative causal candidates from explicit lexical evidence."""
    existing = existing_relations or set()
    grouped: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    for claim in claims:
        source = str(claim.get("source") or "").strip()
        target = str(claim.get("target") or "").strip()
        evidence = re.sub(r"\s+", " ", str(claim.get("evidence") or "")).strip()
        if not source or not target or source not in evidence or target not in evidence:
            continue
        requested_type = str(claim.get("rel_type") or "").strip()
        causal_type = requested_type if requested_type in CAUSAL_MARKERS else next(
            (
                relation_type
                for relation_type, markers in CAUSAL_MARKERS.items()
                if any(marker in evidence for marker in markers)
            ),
            None,
        )
        if not causal_type or (source, target, causal_type) in existing:
            continue
        key = (source, target, causal_type)
        item = grouped.setdefault(key, {
            "source": source,
            "target": target,
            "rel_type": causal_type,
            "evidence_samples": [],
            "source_articles": [],
            "support_count": 0,
            "confidence": 0.0,
            "markers": [],
            "discovery_sources": [],
        })
        matched_markers = [
            marker for marker in CAUSAL_MARKERS[causal_type] if marker in evidence
        ]
        if evidence not in item["evidence_samples"]:
            item["evidence_samples"].append(evidence[:500])
        article_id = claim.get("article_id")
        if article_id and article_id not in item["source_articles"]:
            item["source_articles"].append(article_id)
        item["markers"] = sorted(set(item["markers"]) | set(matched_markers))
        discovery_source = str(claim.get("discovery_source") or "claim_evidence")
        item["discovery_sources"] = sorted(
            set(item["discovery_sources"]) | {discovery_source}
        )
        item["support_count"] = len(item["evidence_samples"])
        base_confidence = max(0.0, min(float(claim.get("confidence") or 0.6), 1.0))
        item["confidence"] = round(
            min(1.0, max(item["confidence"], base_confidence * 0.7 + 0.2) + 0.03 * (item["support_count"] - 1)),
            4,
        )

    candidates = list(grouped.values())
    candidates.sort(
        key=lambda item: (-item["confidence"], -item["support_count"], item["source"], item["target"])
    )
    return candidates[:limit]
