"""MediaCrawler 桥接模块 - 可选依赖

如果用户在本机安装了 MediaCrawler，可以通过此模块调用其搜索功能。
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Optional

from .models import ArticleItem

logger = logging.getLogger(__name__)

# MediaCrawler 可能的位置
MC_CANDIDATE_DIRS = [
    os.path.expanduser("~/MediaCrawler"),
    os.path.expanduser("~/Documents/MediaCrawler"),
    os.path.expanduser("~/Downloads/MediaCrawler"),
    r"C:\MediaCrawler",
]


class MediaCrawlerBridge:
    """MediaCrawler 桥接器

    如果用户安装了 MediaCrawler（https://github.com/NanmiCoder/MediaCrawler），
    可以将其搜索结果集成到本工具中。

    MediaCrawler 使用 Playwright + Chrome CDP 模式进行浏览器自动化，
    支持 QR 码登录，可以获取更完整的小红书数据（含评论、互动量等）。
    """

    def __init__(self, mc_dir: Optional[str] = None):
        self.mc_dir = mc_dir or self._find_mc_dir()

    # ── 路径检测 ──────────────────────────────────

    @staticmethod
    def _find_mc_dir() -> Optional[str]:
        """自动查找 MediaCrawler 目录"""
        for d in MC_CANDIDATE_DIRS:
            main_py = os.path.join(d, "main.py")
            if os.path.isfile(main_py):
                return d

        # 尝试从环境变量读取
        env_dir = os.environ.get("MEDIA_CRAWLER_DIR", "")
        if env_dir and os.path.isfile(os.path.join(env_dir, "main.py")):
            return env_dir

        return None

    @property
    def is_available(self) -> bool:
        if not self.mc_dir:
            return False
        main_py = os.path.join(self.mc_dir, "main.py")
        return os.path.isfile(main_py)

    def check_environment(self) -> dict:
        """检查 MediaCrawler 运行环境"""
        result = {"available": self.is_available, "detail": {}}

        if not self.is_available:
            result["detail"]["error"] = (
                f"未找到 MediaCrawler，已搜索路径: {', '.join(MC_CANDIDATE_DIRS)}"
            )
            return result

        # 检查 uv
        try:
            r = subprocess.run(["uv", "--version"],
                               capture_output=True, text=True, timeout=5)
            result["detail"]["uv"] = r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            result["detail"]["uv"] = "NOT_FOUND"

        # 检查 Python 虚拟环境
        venv_dir = os.path.join(self.mc_dir, ".venv")
        result["detail"]["venv"] = "PRESENT" if os.path.isdir(venv_dir) else "MISSING"

        # 检查配置文件
        config_exists = os.path.isfile(os.path.join(self.mc_dir,
                                                     "config", "base_config.py"))
        result["detail"]["config"] = "PRESENT" if config_exists else "MISSING"

        return result

    # ── 搜索 ──────────────────────────────────────

    def search_xhs(self, keyword: str, limit: int = 20,
                   timeout: int = 300) -> list[ArticleItem]:
        """通过 MediaCrawler 搜索小红书笔记

        Args:
            keyword: 搜索关键词
            limit: 搜索数量
            timeout: 超时时间（秒），MediaCrawler 需要登录可能较慢

        Returns:
            笔记列表
        """
        if not self.is_available:
            raise RuntimeError(
                f"MediaCrawler 未安装\n"
                f"请先从 https://github.com/NanmiCoder/MediaCrawler 克隆项目\n"
                f"执行: git clone https://github.com/NanmiCoder/MediaCrawler.git"
            )

        # 临时修改 MediaCrawler 配置
        import tempfile
        import shutil

        config_dir = os.path.join(self.mc_dir, "config")
        config_file = os.path.join(config_dir, "base_config.py")
        backup_file = config_file + ".bak"

        # 备份原配置
        if os.path.isfile(config_file):
            shutil.copy2(config_file, backup_file)

        try:
            # 写入临时配置
            config_content = f'''
# MediaCrawler 临时配置 - 由 wei-hong 工具生成
PLATFORM = "xhs"
KEYWORDS = ["{keyword}"]
CRAWLER_TYPE = "search"
LOGIN_TYPE = "qrcode"
SAVE_DATA_OPTION = "json"
COOKIES = []
SCAN_NOTE_COMMENTS = False
ENABLE_GET_COMMENTS = False
ENABLE_GET_WORDCLOUD = False
START_PAGE = 1
CRAWLER_MAX_NOTES_COUNT = {limit}
'''
            with open(config_file, "w", encoding="utf-8") as f:
                f.write(config_content)

            # 运行 MediaCrawler
            logger.info("启动 MediaCrawler 搜索: keyword=%s, limit=%d",
                        keyword, limit)

            # 尝试多种命令
            cmds = [
                ["uv", "run", "main.py"],
                ["python", "main.py"],
                ["python3", "main.py"],
            ]

            stdout, stderr = "", ""
            for cmd in cmds:
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=self.mc_dir,
                        capture_output=True, text=True,
                        timeout=timeout,
                        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                    )
                    stdout, stderr = result.stdout, result.stderr
                    if result.returncode == 0:
                        break
                except FileNotFoundError:
                    continue

            # 读取输出文件
            items = self._read_output_files(keyword)

            if not items:
                logger.warning("MediaCrawler 未生成结果文件\nstdout: %s\nstderr: %s",
                               stdout[:500] if stdout else "",
                               stderr[:500] if stderr else "")
                if "请使用二维码登录" in stderr or "login" in stderr.lower():
                    raise RuntimeError(
                        "MediaCrawler 需要登录小红书\n"
                        "请先单独运行 MediaCrawler 完成登录:\n"
                        f"cd {self.mc_dir} && uv run main.py --platform xhs "
                        f"--lt qrcode --type search"
                    )
                if not items:
                    raise RuntimeError(
                        f"MediaCrawler 搜索未返回结果\n"
                        f"stderr: {stderr[:300] if stderr else '无输出'}"
                    )

            return items

        finally:
            # 恢复原配置
            if os.path.isfile(backup_file):
                shutil.move(backup_file, config_file)

            # 清理输出文件
            self._clean_output_files()

    def _read_output_files(self, keyword: str) -> list[ArticleItem]:
        """读取 MediaCrawler 的输出文件"""
        import glob

        data_dirs = [
            os.path.join(self.mc_dir, "data"),
            os.path.join(self.mc_dir, "output"),
        ]

        items = []
        for data_dir in data_dirs:
            if not os.path.isdir(data_dir):
                continue

            # 查找最近的 JSON 文件
            json_files = glob.glob(os.path.join(data_dir, "xhs_search_*.json"))
            json_files.sort(key=os.path.getmtime, reverse=True)

            for json_file in json_files[:3]:
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if isinstance(data, list):
                        records = data
                    elif isinstance(data, dict):
                        records = data.get("data", data.get("items", [data]))
                    else:
                        continue

                    for record in records:
                        if isinstance(record, dict):
                            item = self._parse_mc_record(record)
                            if item:
                                items.append(item)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning("读取 MediaCrawler 输出文件失败 %s: %s",
                                   json_file, e)
                    continue

        return items

    def _parse_mc_record(self, record: dict) -> Optional[ArticleItem]:
        """解析 MediaCrawler 的一条记录"""
        try:
            note_id = record.get("note_id", "")
            title = record.get("title", record.get("display_title", ""))
            desc = record.get("desc", "")
            cover = record.get("cover_url", "")
            create_time = record.get("create_time", 0)
            pub_time = ""
            if create_time:
                import time as tmod
                pub_time = tmod.strftime("%Y-%m-%d %H:%M",
                                         tmod.localtime(create_time))

            user_info = record.get("user_info", {}) or {}
            user_name = user_info.get("nickname", "")
            user_avatar = user_info.get("avatar", "")

            return ArticleItem(
                platform="xiaohongshu",
                title=title,
                url=f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else "",
                abstract=desc,
                author=user_name,
                author_avatar=user_avatar,
                publish_time=pub_time,
                cover_image=cover,
                source_name=user_name,
                note_id=note_id,
                extra={
                    "liked_count": record.get("liked_count", ""),
                    "collected_count": record.get("collected_count", ""),
                    "comment_count": record.get("comment_count", ""),
                }
            )
        except Exception as e:
            logger.warning("解析 MediaCrawler 记录出错: %s", e)
            return None

    def _clean_output_files(self):
        """清理临时输出文件"""
        import glob
        import shutil

        data_dirs = [
            os.path.join(self.mc_dir, "data"),
            os.path.join(self.mc_dir, "output"),
        ]
        for data_dir in data_dirs:
            if os.path.isdir(data_dir):
                try:
                    for f in glob.glob(os.path.join(data_dir, "xhs_*.json")):
                        os.remove(f)
                except OSError:
                    pass
