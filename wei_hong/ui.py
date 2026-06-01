"""微红 - 小红书 & 公众号文章搜索工具 主界面"""

import logging
import os
import sys
import threading
from tkinter import ttk
from typing import Optional

logger = logging.getLogger(__name__)

# 尝试导入 customtkinter
try:
    import customtkinter as ctk
except ImportError:
    print("请先安装依赖: pip install -r requirements.txt")
    print("依赖包: customtkinter, httpx, wechatsogou, Pillow")
    sys.exit(1)

from .models import ArticleItem
from .wechat_searcher import WechatSearcher
from .xhs_searcher import XHSSearcher
from .mediacrawler_bridge import MediaCrawlerBridge


class App(ctk.CTk):
    """微红 - 主应用程序窗口"""

    def __init__(self):
        super().__init__()

        # ── 窗口配置 ──
        self.title("微红 · 小红书 & 公众号搜索")
        self.geometry("1200x750")
        self.minsize(900, 600)

        # 图标
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
            if os.path.isfile(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        # ── 颜色主题 ──
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # ── 搜索器实例 ──
        self.wechat_searcher = WechatSearcher()
        self.xhs_searcher = XHSSearcher()
        self.mc_bridge = MediaCrawlerBridge()

        # ── 状态 ──
        self._searching = False
        self._all_results: list[ArticleItem] = []

        # ── 构建 UI ──
        self._build_ui()

        # ── 启动后检测环境 ──
        self.after(500, self._check_environment)

    # ======================== UI 构建 ========================

    def _build_ui(self):
        """构建界面布局"""

        # ── 顶部工具栏 ──
        self._build_toolbar()

        # ── 主内容区 ──
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # 左侧面板
        self._build_sidebar(main)

        # 右侧主面板
        self._build_main_panel(main)

        # ── 状态栏 ──
        self._build_statusbar()

    def _build_toolbar(self):
        """顶部工具栏"""
        toolbar = ctk.CTkFrame(self, height=50, corner_radius=0)
        toolbar.pack(fill="x", padx=0, pady=0)
        toolbar.pack_propagate(False)

        # Logo / 标题
        title = ctk.CTkLabel(
            toolbar, text="  微红",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.pack(side="left", padx=(15, 5), pady=10)

        subtitle = ctk.CTkLabel(
            toolbar, text="小红书 × 公众号 文章搜索",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        subtitle.pack(side="left", pady=10)

    def _build_sidebar(self, parent):
        """左侧设置面板"""
        sidebar = ctk.CTkScrollableFrame(
            parent, width=280, corner_radius=10,
        )
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        # sidebar.grid_propagate(False)  # CTkScrollableFrame does not support grid_propagate

        # ── 平台选择 ──
        ctk.CTkLabel(
            sidebar, text="搜索平台",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        self.platform_var = ctk.StringVar(value="all")
        platforms = [
            ("全部 (公众号 + 小红书)", "all"),
            ("公众号", "wechat"),
            ("小红书", "xiaohongshu"),
        ]
        for text, val in platforms:
            ctk.CTkRadioButton(
                sidebar, text=text, variable=self.platform_var,
                value=val,
            ).pack(anchor="w", padx=15, pady=2)

        # ── 分隔线 ──
        ctk.CTkFrame(sidebar, height=1, fg_color="gray30").pack(
            fill="x", padx=10, pady=(15, 10))

        # ── 公众号配置 ──
        ctk.CTkLabel(
            sidebar, text="公众号 (搜狗微信)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(0, 5))

        self.wx_status = ctk.CTkLabel(
            sidebar, text="✅ 无需配置，直接可用",
            font=ctk.CTkFont(size=11),
            text_color="green",
        )
        self.wx_status.pack(anchor="w", padx=15, pady=2)

        # ── 小红书配置 ──
        ctk.CTkFrame(sidebar, height=1, fg_color="gray30").pack(
            fill="x", padx=10, pady=(15, 10))

        ctk.CTkLabel(
            sidebar, text="小红书 (Web API)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(0, 5))

        ctk.CTkLabel(
            sidebar, text="需要登录 cookie，点击下方按钮设置",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=250,
        ).pack(anchor="w", padx=15, pady=2)

        self.xhs_status = ctk.CTkLabel(
            sidebar, text="❌ 未配置",
            font=ctk.CTkFont(size=11),
            text_color="orange",
        )
        self.xhs_status.pack(anchor="w", padx=15, pady=2)

        ctk.CTkButton(
            sidebar, text="设置 Cookie", command=self._open_cookie_dialog,
            width=200,
        ).pack(anchor="w", padx=15, pady=(5, 2))

        ctk.CTkButton(
            sidebar, text="测试连接", command=self._test_xhs_connection,
            width=200, fg_color="transparent", border_width=1,
        ).pack(anchor="w", padx=15, pady=2)

        # ── 代理配置 ──
        ctk.CTkFrame(sidebar, height=1, fg_color="gray30").pack(
            fill="x", padx=10, pady=(15, 10))

        ctk.CTkLabel(
            sidebar, text="代理 (可选)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(0, 5))

        self.proxy_var = ctk.StringVar(value="")
        ctk.CTkEntry(
            sidebar, textvariable=self.proxy_var,
            placeholder_text="如: http://127.0.0.1:7890",
        ).pack(fill="x", padx=15, pady=2)

        # ── MediaCrawler 集成 ──
        ctk.CTkFrame(sidebar, height=1, fg_color="gray30").pack(
            fill="x", padx=10, pady=(15, 10))

        ctk.CTkLabel(
            sidebar, text="MediaCrawler 集成 (可选)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(0, 5))

        if self.mc_bridge.is_available:
            status_text = f"✅ 已找到 ({(self.mc_bridge.mc_dir or '')[:40]}...)"
            status_color = "green"
        else:
            status_text = "❌ 未安装"
            status_color = "gray"

        self.mc_status = ctk.CTkLabel(
            sidebar, text=status_text,
            font=ctk.CTkFont(size=11),
            text_color=status_color,
            wraplength=250,
        )
        self.mc_status.pack(anchor="w", padx=15, pady=2)

    def _build_main_panel(self, parent):
        """右侧主面板"""
        panel = ctk.CTkFrame(parent, corner_radius=10)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        # ── 搜索栏 ──
        search_frame = ctk.CTkFrame(panel)
        search_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        search_frame.grid_columnconfigure(0, weight=1)

        self.keyword_var = ctk.StringVar()
        keyword_entry = ctk.CTkEntry(
            search_frame, textvariable=self.keyword_var,
            placeholder_text="输入关键词搜索...",
            height=40,
            font=ctk.CTkFont(size=14),
        )
        keyword_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        keyword_entry.bind("<Return>", lambda e: self._do_search())

        self.search_btn = ctk.CTkButton(
            search_frame, text="🔍  搜索", height=40, width=120,
            font=ctk.CTkFont(size=14),
            command=self._do_search,
        )
        self.search_btn.grid(row=0, column=1)

        # ── 结果数量控制 ──
        count_frame = ctk.CTkFrame(search_frame)
        count_frame.grid(row=1, column=0, sticky="w", pady=(8, 0))

        ctk.CTkLabel(
            count_frame, text="每页:",
            font=ctk.CTkFont(size=11),
        ).pack(side="left")

        self.page_size_var = ctk.StringVar(value="20")
        page_size_menu = ctk.CTkOptionMenu(
            count_frame, values=["10", "20", "30", "50"],
            variable=self.page_size_var, width=60,
        )
        page_size_menu.pack(side="left", padx=5)

        self.page_var = ctk.IntVar(value=1)
        ctk.CTkLabel(
            count_frame, text="  页码:",
            font=ctk.CTkFont(size=11),
        ).pack(side="left")

        self.page_label = ctk.CTkLabel(
            count_frame, text="1",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="blue",
        )
        self.page_label.pack(side="left", padx=5)

        ctk.CTkButton(
            count_frame, text="← 上一页", width=80,
            command=self._prev_page,
        ).pack(side="left", padx=(10, 5))
        ctk.CTkButton(
            count_frame, text="下一页 →", width=80,
            command=self._next_page,
        ).pack(side="left")

        # ── 结果表格 ──
        self._build_results_table(panel)

    def _build_results_table(self, parent):
        """结果表格"""
        table_frame = ctk.CTkFrame(parent, corner_radius=8)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # 列定义
        columns = ("platform", "title", "author", "time", "abstract")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            selectmode="browse",
        )

        # 列头
        self.tree.heading("platform", text="平台")
        self.tree.heading("title", text="标题")
        self.tree.heading("author", text="作者/来源")
        self.tree.heading("time", text="时间")
        self.tree.heading("abstract", text="摘要")

        # 列宽
        self.tree.column("platform", width=60, minwidth=60, anchor="center")
        self.tree.column("title", width=350, minwidth=200)
        self.tree.column("author", width=120, minwidth=80)
        self.tree.column("time", width=140, minwidth=100)
        self.tree.column("abstract", width=300, minwidth=150)

        # 滚动条
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # 双击事件
        self.tree.bind("<Double-1>", self._on_item_double_click)

        # 标签样式
        style = ttk.Style()
        style.configure("Treeview", rowheight=28, font=("微软雅黑", 10))
        style.configure("Treeview.Heading", font=("微软雅黑", 11, "bold"))

    def _build_statusbar(self):
        """底部状态栏"""
        self.status_bar = ctk.CTkFrame(self, height=30, corner_radius=0)
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_bar, text="就绪",
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.status_label.pack(side="left", padx=10)

        self.count_label = ctk.CTkLabel(
            self.status_bar, text="",
            font=ctk.CTkFont(size=11),
            anchor="e",
        )
        self.count_label.pack(side="right", padx=10)

    # ======================== 核心功能 ========================

    def _do_search(self):
        """执行搜索"""
        keyword = self.keyword_var.get().strip()
        if not keyword:
            self._set_status("请输入关键词")
            return

        if self._searching:
            self._set_status("正在搜索中，请等待...")
            return

        platform = self.platform_var.get()
        page = self.page_var.get()
        page_size = int(self.page_size_var.get())

        # 验证 XHS cookie
        if platform == "xiaohongshu" and not self.xhs_searcher.has_cookies:
            self._set_status("请先在小红书设置中粘贴 cookie")
            return

        self._set_searching(True)
        self._all_results = []

        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)

        def search_thread():
            try:
                results: list[ArticleItem] = []

                # 按平台搜索
                if platform in ("wechat", "all"):
                    self._set_status(f"正在搜索公众号: {keyword}...")
                    try:
                        wx_results = self.wechat_searcher.search_articles(
                            keyword, page=page
                        )
                        results.extend(wx_results)
                    except Exception as e:
                        logger.warning("公众号搜索失败: %s", e)
                        self._log_error(f"公众号: {e}")

                if platform in ("xiaohongshu", "all"):
                    self._set_status(f"正在搜索小红书: {keyword}...")
                    try:
                        # 优先使用 MediaCrawler
                        if self.mc_bridge.is_available and platform == "xiaohongshu":
                            try:
                                xhs_results = self.mc_bridge.search_xhs(
                                    keyword, limit=page_size
                                )
                                results.extend(xhs_results)
                            except Exception as e:
                                logger.warning("MediaCrawler 搜索失败, 回退到 API: %s", e)
                                xhs_results = self.xhs_searcher.search_notes(
                                    keyword, page=page, page_size=page_size
                                )
                                results.extend(xhs_results)
                        else:
                            xhs_results = self.xhs_searcher.search_notes(
                                keyword, page=page, page_size=page_size
                            )
                            results.extend(xhs_results)
                    except Exception as e:
                        logger.warning("小红书搜索失败: %s", e)
                        if not self.xhs_searcher.has_cookies:
                            self._log_error("小红书: 请先设置 cookie")
                        else:
                            self._log_error(f"小红书: {e}")

                # 去重（按 URL）
                seen = set()
                unique_results = []
                for r in results:
                    if r.url and r.url not in seen:
                        seen.add(r.url)
                        unique_results.append(r)

                self._all_results = unique_results

                # 更新 UI
                self.after(0, self._display_results, unique_results)

            finally:
                self.after(0, lambda: self._set_searching(False))

        threading.Thread(target=search_thread, daemon=True).start()

    def _display_results(self, results: list[ArticleItem]):
        """在表格中显示结果"""
        self.tree.delete(*self.tree.get_children())

        for i, item in enumerate(results):
            platform_tag = "📕" if item.platform == "xiaohongshu" else "💬"
            title = item.title or "(无标题)"
            if len(title) > 50:
                title = title[:50] + "..."

            abstract = item.abstract or ""
            if len(abstract) > 60:
                abstract = abstract[:60] + "..."

            self.tree.insert(
                "", "end",
                values=(
                    platform_tag,
                    title,
                    item.author or item.source_name or "-",
                    item.publish_time or "-",
                    abstract,
                ),
                tags=(item.url, item.note_id, item.platform),
            )

        # 更新状态
        self._set_status(
            f"搜索完成，共 {len(results)} 条结果"
            if results else "未搜索到结果"
        )
        self.count_label.configure(
            text=f"共 {len(results)} 条结果"
        )

    def _on_item_double_click(self, event):
        """双击打开文章链接"""
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        tags = self.tree.item(item, "tags")
        if not tags or len(tags) < 1:
            return

        url = tags[0]
        if url and url.startswith("http"):
            import webbrowser
            webbrowser.open(url)

    def _prev_page(self):
        if self.page_var.get() > 1:
            self.page_var.set(self.page_var.get() - 1)
            self.page_label.configure(text=str(self.page_var.get()))
            self._do_search()

    def _next_page(self):
        self.page_var.set(self.page_var.get() + 1)
        self.page_label.configure(text=str(self.page_var.get()))
        self._do_search()

    # ======================== 小红书 Cookie 管理 ========================

    def _open_cookie_dialog(self):
        """打开 Cookie 设置对话框"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("设置小红书 Cookie")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="从浏览器获取 Cookie",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=15, pady=(15, 5))

        # 操作说明
        instructions = (
            "操作步骤：\n"
            "1. 在 Chrome/Edge 中登录 xiaohongshu.com\n"
            "2. 按 F12 打开开发者工具\n"
            "3. 切换到 Application -> Cookies -> xiaohongshu.com\n"
            "4. 分别复制 a1 和 web_session 的值\n\n"
            "或者直接粘贴完整的 Cookie 字符串到下方："
        )
        ctk.CTkLabel(
            dialog, text=instructions,
            font=ctk.CTkFont(size=11),
            justify="left",
            wraplength=460,
        ).pack(anchor="w", padx=15, pady=5)

        # Cookie 输入框
        ctk.CTkLabel(
            dialog, text="a1 cookie:",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=15, pady=(10, 2))

        a1_entry = ctk.CTkEntry(
            dialog, placeholder_text="粘贴 a1 的值",
        )
        a1_entry.pack(fill="x", padx=15, pady=2)
        a1_entry.insert(0, self.xhs_searcher._cookies.get("a1", ""))

        ctk.CTkLabel(
            dialog, text="web_session cookie:",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=15, pady=(10, 2))

        ws_entry = ctk.CTkEntry(
            dialog, placeholder_text="粘贴 web_session 的值",
        )
        ws_entry.pack(fill="x", padx=15, pady=2)
        ws_entry.insert(0, self.xhs_searcher._cookies.get("web_session", ""))

        ctk.CTkLabel(
            dialog, text="或粘贴完整 Cookie 字符串:",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=15, pady=(10, 2))

        full_cookie = ctk.CTkTextbox(dialog, height=80)
        full_cookie.pack(fill="x", padx=15, pady=2)

        def save_cookies():
            a1 = a1_entry.get().strip()
            ws = ws_entry.get().strip()
            fc = full_cookie.get("1.0", "end-1c").strip()

            self.xhs_searcher.set_cookies(
                a1=a1, web_session=ws, cookie_str=fc
            )

            if self.xhs_searcher.has_cookies:
                self.xhs_status.configure(
                    text="✅ Cookie 已配置",
                    text_color="green",
                )
                self._set_status("小红书 Cookie 已保存")
            else:
                self._set_status("请至少填写 a1 或 web_session")

            dialog.destroy()

        ctk.CTkButton(
            dialog, text="保存", command=save_cookies,
        ).pack(pady=15)

    def _test_xhs_connection(self):
        """测试小红书连接"""
        if not self.xhs_searcher.has_cookies:
            self._set_status("请先设置小红书 Cookie")
            return

        self._set_status("测试小红书连接中...")

        def test():
            result = self.xhs_searcher.test_connection()
            self.after(0, lambda: (
                self.xhs_status.configure(
                    text=result,
                    text_color="green" if "成功" in result else "red",
                ),
                self._set_status(f"连接测试: {result}"),
            ))

        threading.Thread(target=test, daemon=True).start()

    # ======================== 辅助方法 ========================

    def _check_environment(self):
        """启动时检查环境"""
        # 检查 MediaCrawler
        env = self.mc_bridge.check_environment()
        if env["available"]:
            self.mc_status.configure(
                text=f"✅ 已就绪",
                text_color="green",
            )

    def _set_searching(self, searching: bool):
        self._searching = searching
        if searching:
            self.search_btn.configure(state="disabled", text="搜索中...")
            self._set_status("正在搜索...")
        else:
            self.search_btn.configure(state="normal", text="🔍  搜索")

    def _set_status(self, text: str):
        self.status_label.configure(text=text)

    def _log_error(self, text: str):
        """记录错误到状态栏（带前缀）"""
        current = self.status_label.cget("text")
        if current != "就绪" and "错误" not in current:
            text = f"{current} | ❌ {text}"
        self._set_status(f"❌ {text}")
        logger.error(text)

    def run(self):
        """运行应用"""
        self.mainloop()
