# 微红 - 小红书 & 公众号文章搜索工具

同时搜索**小红书笔记**和**微信公众号文章**，在统一的桌面界面中展示。

```
         __        __        _           _   ____
  \ \      / /__  ___| |__   __ _| |_/ ___|  ___   __ _  ___  _   _
   \ \ /\ / / _ \/ __| '_ \ / _` | __\___ \ / _ \ / _` |/ _ \| | | |
    \ V  V /  __/ (__| | | | (_| | |_ ___) | (_) | (_| | (_) | |_| |
     \_/\_/ \___|\___|_| |_|\__,_|\__|____/ \___/ \__, |\___/ \__,_|
                                                   |___/
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
python main.py
```

## 功能

| 平台 | 搜索方式 | 是否需要配置 | 实现方案 |
|------|---------|-------------|---------|
| 💬 公众号 | 按关键词搜索文章 | ❌ 无需配置 | [wechatsogou](https://github.com/chyroc/WechatSogou) (搜狗微信搜索) |
| 📕 小红书 | 按关键词搜索笔记 | ✅ 需要 Cookie | XHS Web API (httpx + Node.js 签名) |

## 公众号（可直接使用）

**无需任何配置**，直接输入关键词即可搜索。底层使用 [WechatSogou](https://github.com/chyroc/WechatSogou)（6,291 ⭐），通过**搜狗微信搜索**入口获取文章列表。

**注意**：
- 搜狗对频繁请求会触发验证码，降低请求频率即可
- 返回的文章链接为临时链接，有效期约 2 小时
- 搜狗索引可能不完整，部分文章可能无法搜到

## 小红书（需配置 Cookie）

小红书 API 需要登录状态的 cookie 签名，配置步骤如下：

1. 在 Chrome/Edge 中打开并登录 [xiaohongshu.com](https://www.xiaohongshu.com)
2. 按 `F12` 打开开发者工具
3. 切换到 `Application` → `Cookies` → `xiaohongshu.com`
4. 找到 `a1` 和 `web_session` 两个 cookie，复制其值
5. 在微红左侧面板中点击「设置 Cookie」，粘贴保存

**关于签名算法**：
- XHS API 需要 `X-T` / `X-S` 签名头
- 工具内置了 Python 版和 Node.js 版两种签名生成方式
- **推荐安装 Node.js**（性能更好，签名更准确）
- Node.js 安装: https://nodejs.org/ (版本 >= 16)
- 签名脚本: `wei_hong/xhs_sign.js`

## 高级用法

### 配置代理

如果搜狗被屏蔽，可以在左侧面板的「代理」输入框中配置，如：
```
http://127.0.0.1:7890
```

### MediaCrawler 集成

如果安装了 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)（50k ⭐），可以启用它来获取更完整的小红书数据（含评论、互动量等）。

1. 克隆 MediaCrawler：`git clone https://github.com/NanmiCoder/MediaCrawler.git`
2. 安装依赖并完成初始登录（扫码登录一次即可缓存登录态）
3. 微红会自动检测到 MediaCrawler 并启用集成

支持的 MediaCrawler 安装位置：
- `~/MediaCrawler`
- `~/Documents/MediaCrawler`
- `~/Downloads/MediaCrawler`
- `C:\MediaCrawler`
- 通过环境变量 `MEDIA_CRAWLER_DIR` 指定

## 项目结构

```
E:\1\wei-hong\
├── main.py                    # 入口文件
├── requirements.txt           # Python 依赖
├── wei_hong/
│   ├── __init__.py
│   ├── ui.py                  # CustomTkinter 桌面界面
│   ├── models.py              # 统一数据模型
│   ├── wechat_searcher.py     # 公众号搜索（wechatsogou）
│   ├── xhs_searcher.py        # 小红书搜索（Web API）
│   ├── xhs_sign.js            # 小红书签名脚本（Node.js）
│   └── mediacrawler_bridge.py # MediaCrawler 集成桥接
```

## 技术选型

| 模块 | 实现 | 参考项目 |
|------|------|---------|
| 公众号搜索 | `wechatsogou` Python 库 | [chyroc/WechatSogou](https://github.com/chyroc/WechatSogou) ⭐6,291 |
| 小红书搜索 | httpx + Cookie + Node.js 签名 | [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) ⭐50k |
| 桌面 UI | CustomTkinter | 原生模块 |

## 依赖

```
customtkinter>=5.2.0  # 现代桌面 UI
Pillow>=10.0.0        # 图片处理
httpx>=0.27.0         # HTTP 客户端
wechatsogou>=4.5.0    # 搜狗微信搜索接口
lxml>=5.0.0           # HTML 解析
bs4>=0.0.2            # BeautifulSoup
```

## 许可

仅供学习参考使用。使用爬虫功能时请遵守目标平台的服务条款和相关法律法规。
