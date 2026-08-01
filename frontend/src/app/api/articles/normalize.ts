export function toCamelCase(obj: unknown): unknown {
  if (obj === null || typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map(toCamelCase);

  return Object.keys(obj as Record<string, unknown>).reduce((acc, key) => {
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    const value = (obj as Record<string, unknown>)[key];
    acc[camelKey] = toCamelCase(value);
    return acc;
  }, {} as Record<string, unknown>);
}

export function normalizeArticleItem(item: Record<string, unknown>): Record<string, unknown> {
  const converted = toCamelCase(item) as Record<string, unknown>;
  return {
    ...converted,
    sourceId: item.source_id ?? converted.sourceId,
    sourceName: item.source_name ?? converted.sourceName,
    sourceType: item.source_type ?? converted.sourceType,
    categoryId: item.category_id ?? converted.categoryId,
    categoryName: item.category_name ?? converted.categoryName,
    publishedAt: item.published_at ?? converted.publishedAt,
    scrapedAt: item.scraped_at ?? converted.scrapedAt,
    wordCount: item.word_count ?? converted.wordCount,
    contentHash: item.content_hash ?? converted.contentHash,
    errorMessage: item.error_message ?? converted.errorMessage,
    kgStatus: item.kg_status ?? converted.kgStatus,
    kgProcessedAt: item.kg_processed_at ?? converted.kgProcessedAt,
    kgContentHash: item.kg_content_hash ?? converted.kgContentHash,
    kgErrorMessage: item.kg_error_message ?? converted.kgErrorMessage,
  };
}

export function normalizeArticleResponse(data: Record<string, unknown>): Record<string, unknown> {
  const converted = toCamelCase(data) as Record<string, unknown>;
  if (Array.isArray(data.items)) {
    converted.items = data.items.map((item) => normalizeArticleItem(item as Record<string, unknown>));
  }
  if (typeof data.page_size !== "undefined") {
    converted.pageSize = data.page_size;
  }
  return converted;
}
