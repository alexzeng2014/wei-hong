/**
 * 小红书 X-T / X-S 签名生成脚本
 * 
 * 用法: node xhs_sign.js <path> <params_json>
 * 输出: {"x_s": "...", "x_t": "..."}
 *
 * 注意：XHS 签名算法会不定期更新。如果发现签名失效，
 * 请从最新版 xiaohongshu.com 页面的静态 JS 中提取最新的 sign 函数。
 */

// =========================================================================
// XHS sign 算法实现
//
// 当前已知算法（截至 2025-2026）：
// x_t = Date.now()
// x_s = md5(path + sorted_query_string + salt + x_t)
// 
// salt 值 "WSUDD" 来自 XHS 前端代码的逆向
// =========================================================================

const crypto = require("crypto");

function sortedQueryString(params) {
    const keys = Object.keys(params).sort();
    return keys.map(k => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`).join("&");
}

/**
 * 生成 X-S / X-T 签名
 * @param {string} path - API 路径，如 /api/sns/web/v1/search/notes
 * @param {object} params - URL 查询参数
 * @returns {{ x_s: string, x_t: string }}
 */
function sign(path, params) {
    const x_t = String(Date.now());
    const qs = sortedQueryString(params);
    const salt = "WSUDD";  // 已知 salt 值

    // x_s = md5(path + "?" + qs + salt + x_t)
    const raw = `${path}?${qs}${salt}${x_t}`;
    const x_s = crypto.createHash("md5").update(raw, "utf8").digest("hex");

    return { x_s, x_t };
}

// ── CLI 入口 ──────────────────────────────────────
if (require.main === module) {
    const [path, paramsStr] = process.argv.slice(2);

    if (!path) {
        console.error("用法: node xhs_sign.js <path> <params_json>");
        process.exit(1);
    }

    let params;
    try {
        params = paramsStr ? JSON.parse(paramsStr) : {};
    } catch (e) {
        console.error(`参数解析失败: ${e.message}`);
        process.exit(1);
    }

    const result = sign(path, params);
    console.log(JSON.stringify(result));
}

module.exports = { sign, sortedQueryString };
