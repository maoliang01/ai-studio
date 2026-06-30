"""
页签识别相关的数据模型
用于定义页签分析请求和响应的数据结构
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class TabNodeModel(BaseModel):
    """页签节点模型"""
    id: str = Field(..., description="节点唯一ID")
    label: str = Field(..., description="节点显示名称")
    url: str = Field(..., description="跳转URL")
    children: Optional[List["TabNodeModel"]] = Field(default_factory=list)
    level: int = Field(ge=0, description="节点层级，0=顶级")
    type: Literal["nav", "tab", "breadcrumb"] = Field(description="节点类型: nav=导航菜单, tab=内容区Tab, breadcrumb=面包屑")
    expandable: bool = Field(default=False, description="是否可展开")
    url_pattern: Optional[str] = Field(None, description="URL模式说明")


class TabTreeModel(BaseModel):
    """页签树结构"""
    domain: str = Field(description="所属网站域名")
    site_title: str = Field(description="网站标题")
    root: TabNodeModel = Field(description="根节点")
    all_nodes: List[TabNodeModel] = Field(default_factory=list, description="所有节点列表（扁平化）")
    generated_at: str = Field(description="生成时间 ISO格式")
    total_count: int = Field(description="节点总数")


class TabAnalyzeRequest(BaseModel):
    """页签识别请求"""
    url: str = Field(..., description="要分析的URL")
    include_nav: bool = Field(default=True, description="是否识别导航栏")
    include_tabs: bool = Field(default=True, description="是否识别内容区Tab")
    include_breadcrumb: bool = Field(default=False, description="是否识别面包屑")
    max_depth: int = Field(default=3, ge=1, le=5, description="最大递归深度")


class TabAnalyzeResponse(BaseModel):
    """页签识别响应"""
    success: bool = Field(description="是否成功")
    tree: Optional[TabTreeModel] = Field(None, description="页签树结构")
    error: Optional[str] = Field(None, description="错误信息")
    duration: int = Field(description="耗时（毫秒）")


class MultiCategoryScrapeRequest(BaseModel):
    """多分类爬取请求"""
    selected_node_ids: List[str] = Field(..., description="选中的节点ID列表")
    node_urls: dict[str, str] = Field(..., description="节点ID到URL的映射")
    max_articles_per_category: int = Field(default=10, ge=1, le=100, description="每个分类最多爬取文章数")
    extract_content: bool = Field(default=True, description="是否提取正文")
    timeout: int = Field(default=30, ge=10, le=300, description="超时时间（秒）")


# 前向引用 - 确保递归模型正确解析
TabNodeModel.model_rebuild()