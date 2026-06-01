#!/usr/bin/env python3
"""微红 - 小红书 & 公众号文章搜索工具

同时搜索小红书笔记和微信公众号文章，在统一的桌面界面中展示。

使用:
    pip install -r requirements.txt
    python main.py

依赖:
    - customtkinter: 桌面 UI
    - httpx: HTTP 客户端（小红书 API）
    - wechatsogou: 搜狗微信搜索接口（公众号）
    - Pillow: 图片处理
    - Node.js (可选): 小红书签名生成
    - MediaCrawler (可选): 增强的小红书搜索

配置:
    - 公众号: 无需配置，直接可用
    - 小红书: 需要从浏览器复制 cookie（a1 + web_session）
"""

import logging
import os
import sys

# 确保项目根目录在 path 中
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# 配置日志
log_file = os.path.join(PROJECT_DIR, "wei_hong.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("main")


def main():
    logger.info("启动微红工具...")
    logger.info("项目目录: %s", PROJECT_DIR)

    try:
        from wei_hong.ui import App
    except ImportError as e:
        print(f"\n导入失败: {e}")
        print("\n请先安装依赖:")
        print("  pip install -r requirements.txt")
        print("\n如果 customtkinter 安装失败，请尝试:")
        print("  pip install customtkinter")
        sys.exit(1)

    app = App()
    app.run()


if __name__ == "__main__":
    main()
