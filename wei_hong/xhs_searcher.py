"""小红书笔记搜索 - 基于 XHS Web API + 用户 Cookie"""

import json
import logging
import re
import subprocess
import sys
import time
import os
from typing import Optional
from urllib.parse import urlencode

import httpx

from .models import ArticleItem

logger = logging.getLogger(__name__)

# XHS API 基础 URL
XHS_BASE = "https://edith.xiaohongshu.com"
XHS_SEARCH_URL = f"{XHS_BASE}/api/sns/web/v1/search/notes"

# 默认的 x-s-common 值（来自 XHS web 应用的静态资源）
# 实际使用时建议从最新版 XHS 页面中提取
X_S_COMMON = (
    "3.5.9.1.1.9.11.10.2.1.4.2.11.1.2.1.10.2.1.1.1.10.2.1.4.4.2."
    "1.1.2.1.10.2.1.9.4.6.2.2.4.11.11.1.3.2.1.1.1.4.2.1.9.4.6.8."
    "1.2.2.1.1.2.1.10.2.1.3.1.2.5.3.4.10.2.2.3.11.10.2.2.5.4.2.6."
    "1.2.4.2.7.1.2.7"
)


class XHSSearcher:
    """小红书笔记搜索器

    通过 XHS 的 Web API 按关键词搜索笔记，需要：
    1. 用户提供 cookie（a1 + web_session），从浏览器登录后复制
    2. 签名算法（x-s / x-t），通过 Node.js 或 Playwright 生成

    使用流程：
    1. 在浏览器中登录 xiaohongshu.com
    2. 打开 DevTools -> Application -> Cookies
    3. 复制 a1 和 web_session 的值
    4. 传入 searcher.set_cookies(a1, web_session)
    5. 调用 search_notes(keyword)
    """

    def __init__(self):
        self._cookies: dict[str, str] = {}
        self._sign_script_path = self._find_sign_script()
        self._node_available = self._check_node()

    # ── Cookie 管理 ────────────────────────────────

    def set_cookies(self, a1: str = "", web_session: str = "",
                    cookie_str: str = ""):
        """设置用户登录 cookie

        Args:
            a1: a1 cookie 值
            web_session: web_session cookie 值
            cookie_str: 完整的 cookie 字符串（可选，会从中解析 a1/web_session）
        """
        if cookie_str:
            for part in cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    self._cookies[k] = v
        if a1:
            self._cookies["a1"] = a1
        if web_session:
            self._cookies["web_session"] = web_session

    @property
    def has_cookies(self) -> bool:
        return bool(self._cookies.get("a1") and self._cookies.get("web_session"))

    def get_cookie_string(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self._cookies.items())

    # ── 签名生成 ──────────────────────────────────

    def _find_sign_script(self) -> str:
        """查找 xhs_sign.js 文件路径"""
        # 搜索可能的路径
        candidates = [
            os.path.join(os.path.dirname(__file__), "xhs_sign.js"),
            os.path.join(os.path.dirname(__file__), "..", "xhs_sign.js"),
        ]
        for path in candidates:
            resolved = os.path.abspath(path)
            if os.path.isfile(resolved):
                return resolved
        return candidates[0]

    def _check_node(self) -> bool:
        """检查 Node.js 是否可用（Windows 安全版）"""
        candidates = []

        # 1. Try where.exe to find node path
        try:
            r = subprocess.run(
                ["where.exe", "node"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                candidates.extend(
                    [line.strip() for line in r.stdout.splitlines()
                     if line.strip()]
                )
        except (FileNotFoundError, PermissionError, OSError):
            pass

        # 2. Also try direct "node" command
        candidates.append("node")

        for candidate in candidates:
            try:
                # Try running a tiny JS expression to verify it actually works
                r = subprocess.run(
                    [candidate, "-e", "console.log('ok')"],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0 and "ok" in r.stdout:
                    return True
            except (FileNotFoundError, PermissionError,
                    subprocess.TimeoutExpired, OSError):
                continue

        return False

    def _sign_with_node(self, path: str, params: dict) -> tuple[str, str]:
        """使用 Node.js 脚本生成 x-s / x-t 签名"""
        script = self._sign_script_path
        if not os.path.isfile(script):
            raise FileNotFoundError(
                f"签名脚本不存在: {script}\n"
                f"请参考 README 放置 xhs_sign.js 文件"
            )

        result = subprocess.run(
            ["node", script, path, json.dumps(params)],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(f"签名脚本执行失败: {result.stderr}")

        data = json.loads(result.stdout.strip())
        return data["x_s"], data["x_t"]

    def _sign_with_python(self, path: str, params: dict) -> tuple[str, str]:
        """Python 版签名生成（简化版，作为 Node.js 的 fallback）

        注意：XHS 的签名算法会频繁更新，这里的简化版本可能在某些版本下失效。
        建议优先使用 Node.js 版本。
        """
        import hashlib

        x_t = str(int(time.time() * 1000))
        # 排序参数并拼接
        sorted_qs = urlencode(sorted(params.items(), key=lambda x: x[0]))
        sign_str = f"{path}?{sorted_qs}WSUDD{x_t}"
        x_s = hashlib.md5(sign_str.encode()).hexdigest()
        return x_s, x_t

    def generate_sign(self, path: str, params: dict) -> tuple[str, str]:
        """生成 x-s / x-t 签名

        Returns:
            (x_s, x_t)
        """
        if self._node_available and os.path.isfile(self._sign_script_path):
            return self._sign_with_node(path, params)
        else:
            return self._sign_with_python(path, params)

    # ── 搜索 ──────────────────────────────────────

    def search_notes(self, keyword: str, page: int = 1,
                     page_size: int = 20, sort: str = "general",
                     note_type: int = 0) -> list[ArticleItem]:
        """按关键词搜索小红书笔记

        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量（最大 20）
            sort: 排序方式 general/ time_desc/ popularity_desc
            note_type: 笔记类型 0=全部 1=图文 2=视频

        Returns:
            笔记列表
        """
        if not self.has_cookies:
            raise RuntimeError(
                "请先设置小红书 cookie（a1 + web_session）\n"
                "操作步骤：\n"
                "1. 在 Chrome 中登录 xiaohongshu.com\n"
                "2. F12 -> Application -> Cookies -> xiaohongshu.com\n"
                "3. 复制 a1 和 web_session 的值\n"
                "4. 在 UI 的「Cookie 管理」中粘贴"
            )

        params = {
            "keyword": keyword,
            "page": str(page),
            "page_size": str(page_size),
            "sort": sort,
            "note_type": str(note_type),
        }
        path = "/api/sns/web/v1/search/notes"

        try:
            x_s, x_t = self.generate_sign(path, params)
        except Exception as e:
            logger.warning("签名生成失败, 尝试简化模式: %s", e)
            x_s = ""
            x_t = str(int(time.time() * 1000))

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Origin": "https://www.xiaohongshu.com",
            "Referer": "https://www.xiaohongshu.com/",
            "Content-Type": "application/json;charset=UTF-8",
            "x-s": x_s,
            "x-t": x_t,
            "x-s-common": X_S_COMMON,
        }

        url = f"{XHS_SEARCH_URL}?{urlencode(params)}"

        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(
                    url,
                    headers=headers,
                    cookies=self._cookies,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 or e.response.status_code == 403:
                raise RuntimeError(
                    "小红书 API 鉴权失败，可能原因：\n"
                    "1. cookie 已过期，请重新登录获取\n"
                    "2. 签名算法已更新，请更新 xhs_sign.js\n"
                    "3. IP 被限制，请稍后再试"
                ) from e
            raise RuntimeError(f"HTTP 请求失败: {e.response.status_code}") from e
        except httpx.TimeoutException as e:
            raise RuntimeError("请求超时，请检查网络连接") from e
        except Exception as e:
            raise RuntimeError(f"请求异常: {e}") from e

        # 解析返回数据
        items = self._parse_search_result(data)
        return items

    def _parse_search_result(self, data: dict) -> list[ArticleItem]:
        """解析 XHS 搜索 API 返回结果"""
        items = []

        try:
            items_data = data.get("data", {}).get("items", [])
        except AttributeError:
            logger.warning("返回数据结构异常: %s", str(data)[:200])
            return []

        for item in items_data:
            try:
                note = item.get("note_card", {}) or item
                user = item.get("user", {}) or note.get("user", {})

                note_id = note.get("note_id", "")
                display_title = note.get("display_title", "")
                title = note.get("title", "")
                desc = note.get("desc", display_title or title)
                cover = (note.get("cover", {}) or {}).get("url_default", "")
                create_time = note.get("time", 0)
                pub_time = ""
                if create_time:
                    pub_time = time.strftime(
                        "%Y-%m-%d %H:%M", time.localtime(create_time)
                    )

                user_name = user.get("nickname", "")
                user_avatar = (user.get("avatar", {}) or {}).get("url", "")

                items.append(ArticleItem(
                    platform="xiaohongshu",
                    title=display_title or title,
                    url=f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else "",
                    abstract=desc,
                    author=user_name,
                    author_avatar=user_avatar,
                    publish_time=pub_time,
                    cover_image=cover,
                    source_name=user_name,
                    note_id=note_id,
                    extra={
                        "liked_count": note.get("liked_count", ""),
                        "collected_count": note.get("collected_count", ""),
                        "comment_count": note.get("comment_count", ""),
                        "type": note.get("type", ""),
                    }
                ))
            except Exception as e:
                logger.warning("解析笔记数据出错: %s, data=%s", e,
                               str(item)[:100])
                continue

        return items

    def test_connection(self) -> str:
        """测试 XHS API 连接是否正常"""
        if not self.has_cookies:
            return "未设置 cookie"

        try:
            results = self.search_notes("测试", page=1, page_size=1)
            if results:
                return f"连接成功（获取到 {len(results)} 条结果）"
            else:
                return "连接成功（无搜索结果）"
        except RuntimeError as e:
            return f"连接失败: {str(e)}"
        except Exception as e:
            return f"异常: {str(e)}"
