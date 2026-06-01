"""微信公众号文章搜索 - 基于搜狗微信搜索入口（直接 HTTP 请求 + HTML 解析）"""

import re
import time
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .models import ArticleItem

logger = logging.getLogger(__name__)

SOGOU_SEARCH_URL = "https://weixin.sogou.com/weixin"
SEARCH_TYPE_ARTICLE = 2    # 搜文章
SEARCH_TYPE_ACCOUNT = 1    # 搜公众号

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class WechatSearcher:
    """微信公众号文章搜索器

    直接请求搜狗微信搜索，解析 HTML 获取文章列表。
    无需任何登录或身份认证。
    """

    def __init__(self, proxies: Optional[dict] = None, timeout: int = 10,
                 captcha_break_time: int = 3):
        self.proxies = proxies
        self.timeout = timeout
        self.captcha_break_time = captcha_break_time

    def _request(self, url: str) -> str:
        """发送 HTTP 请求，返回 HTML 文本"""
        kwargs = dict(headers=HEADERS, timeout=self.timeout)
        if self.proxies:
            kwargs["proxies"] = self.proxies

        resp = requests.get(url, **kwargs)
        resp.raise_for_status()

        # 检查是否触发了验证码
        if "请输入验证码" in resp.text or "请输入验证码" in resp.text:
            raise RuntimeError(
                "搜狗触发了验证码，请降低请求频率或过几分钟再试"
            )

        return resp.text

    def _parse_timestamp(self, li) -> str:
        """从 <script> 标签中提取时间戳并格式化"""
        try:
            script = li.select_one(".s-p .s2 script")
            if script and script.string:
                match = re.search(r"timeConvert\(['\"]?(\d+)['\"]?\)",
                                  script.string)
                if match:
                    ts = int(match.group(1))
                    return time.strftime("%Y-%m-%d %H:%M",
                                         time.localtime(ts))
        except Exception:
            pass
        return ""

    def search_articles(self, keyword: str, page: int = 1) -> list[ArticleItem]:
        """按关键词搜索公众号文章

        Args:
            keyword: 搜索关键词
            page: 页码（从 1 开始）

        Returns:
            文章列表
        """
        params = dict(type=SEARCH_TYPE_ARTICLE, query=keyword,
                      ie="utf8", page=page)
        from urllib.parse import urlencode
        url = f"{SOGOU_SEARCH_URL}?{urlencode(params)}"

        try:
            html = self._request(url)
        except RuntimeError:
            raise
        except requests.RequestException as e:
            raise RuntimeError(f"搜索请求失败: {e}") from e

        soup = BeautifulSoup(html, "lxml")
        items_list = soup.select("ul.news-list li")

        results = []
        for li in items_list:
            try:
                # 标题
                title_el = li.select_one("h3 a[id^=sogou_vr]")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)

                # URL（搜狗跳转链接，注意转义 &amp;）
                href = title_el.get("href", "")
                if href.startswith("/"):
                    article_url = f"https://weixin.sogou.com{href}"
                else:
                    article_url = href

                # 摘要
                abs_el = li.select_one("p.txt-info")
                abstract = abs_el.get_text(strip=True) if abs_el else ""

                # 公众号名称
                acc_el = li.select_one(".s-p .all-time-y2")
                account = acc_el.get_text(strip=True) if acc_el else ""

                # 时间
                pub_time = self._parse_timestamp(li)

                # 封面图
                img_el = li.select_one(".img-box img")
                cover = img_el.get("src", "") if img_el else ""
                if cover and cover.startswith("//"):
                    cover = "https:" + cover

                results.append(ArticleItem(
                    platform="wechat",
                    title=title,
                    url=article_url,
                    abstract=abstract,
                    source_name=account,
                    author=account,
                    publish_time=pub_time,
                    cover_image=cover,
                    extra={"sogou_page": page},
                ))

            except Exception as e:
                logger.warning("解析文章条目出错: %s", e)
                continue

        return results

    def search_accounts(self, keyword: str, page: int = 1) -> list[ArticleItem]:
        """按关键词搜索公众号（返回公众号信息列表）"""
        params = dict(type=SEARCH_TYPE_ACCOUNT, query=keyword,
                      ie="utf8", page=page)
        from urllib.parse import urlencode
        url = f"{SOGOU_SEARCH_URL}?{urlencode(params)}"

        try:
            html = self._request(url)
        except RuntimeError:
            raise
        except requests.RequestException as e:
            raise RuntimeError(f"搜索公众号请求失败: {e}") from e

        soup = BeautifulSoup(html, "lxml")
        gzh_items = soup.select(".gzh-box li") or soup.select(".wx-rb")

        results = []
        for item in gzh_items:
            try:
                name_el = item.select_one(
                    ".gzh-name a, .wx-rb .gzh-name, "
                    ".s-p .all-time-y2, h3 a"
                )
                if not name_el:
                    continue

                name = name_el.get_text(strip=True)
                profile_url = name_el.get("href", "")
                if profile_url and profile_url.startswith("/"):
                    profile_url = f"https://weixin.sogou.com{profile_url}"

                intro_el = item.select_one(
                    ".gzh-intro, .txt-info, .gzh-info"
                )
                intro = intro_el.get_text(strip=True) if intro_el else ""

                img_el = item.select_one("img")
                avatar = img_el.get("src", "") if img_el else ""
                if avatar and avatar.startswith("//"):
                    avatar = "https:" + avatar

                results.append(ArticleItem(
                    platform="wechat",
                    title=name,
                    url=profile_url,
                    abstract=intro,
                    author=name,
                    author_avatar=avatar,
                    source_name=name,
                ))
            except Exception as e:
                logger.warning("解析公众号条目出错: %s", e)
                continue

        return results

    def get_history(self, wechat_name: str) -> list[ArticleItem]:
        """获取某个公众号的最近文章列表

        先通过搜狗搜索到该公众号的 profile_url，然后访问历史文章页。
        搜狗仅返回最近 10 条。
        """
        # 搜索公众号
        accounts = self.search_accounts(wechat_name)
        if not accounts:
            raise RuntimeError(f"未找到公众号: {wechat_name}")

        target = accounts[0]
        profile_url = target.url

        if not profile_url:
            raise RuntimeError(f"公众号 {wechat_name} 无 profile_url")

        # 访问历史文章页
        try:
            html = self._request(profile_url)
        except Exception as e:
            raise RuntimeError(f"获取历史文章页失败: {e}") from e

        soup = BeautifulSoup(html, "lxml")

        # 公众号信息
        gzh_name = target.source_name
        gzh_id = target.source_id or ""

        # 文章列表
        article_items = soup.select(".weui_media_box") or soup.select(
            ".mp_profile_article_list .weui_media_box"
        ) or soup.select(".mp_profile_list .weui_media_box")

        results = []
        for art in article_items:
            try:
                title_el = art.select_one(
                    ".weui_media_title, h4 a, .article_title"
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                if href and not href.startswith("http"):
                    href = "https://mp.weixin.qq.com" + href

                abs_el = art.select_one(
                    ".weui_media_desc, .article_summary, p"
                )
                abstract = abs_el.get_text(strip=True) if abs_el else ""

                time_el = art.select_one(
                    ".weui_media_extra_info, .article_date, span.time"
                )
                pub_time = time_el.get_text(strip=True) if time_el else ""

                results.append(ArticleItem(
                    platform="wechat",
                    title=title,
                    url=href,
                    abstract=abstract,
                    source_name=gzh_name,
                    author=gzh_name,
                    publish_time=pub_time,
                ))
            except Exception as e:
                logger.warning("解析历史文章出错: %s", e)
                continue

        return results

    def suggest(self, keyword: str) -> list[str]:
        """获取关键词联想（搜狗不支持此功能，返回空列表）"""
        logger.info("搜狗微信搜索不支持关键词联想")
        return []
