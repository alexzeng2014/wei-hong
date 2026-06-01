from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ArticleItem:
    """统一搜索结果模型"""
    platform: str              # "wechat" | "xiaohongshu"
    title: str
    url: str
    abstract: str = ""
    author: str = ""
    author_avatar: str = ""
    publish_time: str = ""
    cover_image: str = ""
    source_name: str = ""      # 公众号名称 / 小红书作者昵称
    source_id: str = ""        # 微信号 / 小红书用户ID
    note_id: str = ""          # 小红书笔记ID
    extra: dict = field(default_factory=dict)
