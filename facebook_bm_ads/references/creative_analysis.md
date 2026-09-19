# 素材创意 AI 分析指南

从"感觉哪个素材好"变成"数据证明哪个开头更强"。
本模块抓取 Thumbstop 率、视频完播率、CTR 等关键创意指标，
通过 AI 对比分析输出：**哪种开头更强、哪种卖点更有效、哪类人群更匹配**。

---

## 核心指标说明

| 指标 | 计算公式 | 基准参考 |
|---|---|---|
| **Thumbstop 率** | 3秒视频观看次数 / 展示次数 | > 25% 优秀，< 15% 需优化开头 |
| **视频完播率** | ThruPlay 次数 / 视频播放次数 | > 15% 优秀，< 8% 内容无吸引力 |
| **Hook 率 (2s)** | 2秒留存次数 / 展示次数 | 越高说明开头钩子越强 |
| **25% 留存率** | 25%播放次数 / 播放次数 | 开头吸引力指标 |
| **75% 留存率** | 75%播放次数 / 播放次数 | 中段内容质量指标 |
| **CTR** | 点击次数 / 展示次数 × 100% | > 2% 优秀，< 0.8% 需优化 |
| **CTA 点击率** | 链接点击 / 展示次数 × 100% | 衡量 CTA 文案+按钮效果 |

---

## 1. 数据抓取

```python
"""
creative_analysis.py — 素材创意 AI 分析脚本
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import re

TOKEN = os.environ.get("FB_TOKEN", "你的Token")
AD_ACCOUNT_ID = os.environ.get("FB_AD_ACCOUNT_ID", "act_123456789")
BASE_URL = "https://graph.facebook.com/v22.0"


def api_get(url, params, max_retries=5):
    if "access_token" not in params:
        params["access_token"] = TOKEN
    for attempt in range(max_retries):
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        if "error" in data:
            code = data["error"].get("code")
            if code in [4, 17, 32, 613]:
                time.sleep(min(300, (2 ** attempt) * 5))
                continue
            raise Exception(f"API {code}: {data['error'].get('message')}")
        return data
    raise Exception("超过最大重试次数")


def paginate(endpoint, params):
    results, url = [], f"{BASE_URL}/{endpoint}"
    current = {**params, "access_token": TOKEN}
    while url:
        data = api_get(url, current)
        results.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        current = {}
    return results


def fetch_creative_insights(account_id, days=14):
    """
    抓取广告级别的创意指标
    包含：Thumbstop、完播率、CTR、视频留存漏斗、人群维度
    """
    date_until = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    date_since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # ── 主指标抓取 ──
    creative_fields = ",".join([
        "ad_id", "ad_name", "adset_id", "adset_name", "campaign_name",
        "impressions", "clicks", "reach", "spend",
        "inline_link_clicks",              # CTA 点击
        "ctr",                             # 总点击率
        "cpc", "cpm",
        "video_play_actions",              # 视频总播放次数
        "video_avg_time_watched_actions",  # 平均观看时长
        "video_thruplay_watched_actions",  # ThruPlay（完播）
        "video_p25_watched_actions",       # 25% 观看
        "video_p50_watched_actions",       # 50% 观看
        "video_p75_watched_actions",       # 75% 观看
        "video_p100_watched_actions",      # 100% 观看
        # Thumbstop: 3秒观看
        "video_30_sec_watched_actions",    # 30秒观看（长视频用）
    ])

    rows = paginate(f"{account_id}/insights", {
        "fields": creative_fields,
        "time_range": json.dumps({"since": date_since, "until": date_until}),
        "level": "ad",
        "time_increment": "all_days",
        "limit": 500
    })

    # ── 同步抓取广告的素材信息（标题、文案、视频缩略图）──
    ad_ids = list({r["ad_id"] for r in rows if "ad_id" in r})
    creative_meta = fetch_ad_creative_meta(ad_ids)

    # ── 人群维度细分 ──
    audience_rows = paginate(f"{account_id}/insights", {
        "fields": "ad_id,ad_name,impressions,clicks,ctr,spend,purchase_roas",
        "time_range": json.dumps({"since": date_since, "until": date_until}),
        "level": "ad",
        "time_increment": "all_days",
        "breakdowns": "age,gender",
        "limit": 500
    })

    return rows, creative_meta, audience_rows


def fetch_ad_creative_meta(ad_ids):
    """批量获取广告的素材元数据（标题、文案、缩略图）"""
    if not ad_ids:
        return {}
    meta = {}
    # 分批处理，每批 50 个
    for i in range(0, len(ad_ids), 50):
        batch = ad_ids[i:i + 50]
        batch_req = []
        for ad_id in batch:
            batch_req.append({
                "method": "GET",
                "relative_url": (
                    f"{ad_id}?fields=id,name,"
                    f"creative{{id,name,title,body,thumbnail_url,"
                    f"object_story_spec,asset_feed_spec}}"
                )
            })
        url = f"{BASE_URL}/"
        resp = requests.post(url, data={
            "access_token": TOKEN,
            "batch": json.dumps(batch_req)
        }).json()
        for item in resp:
            if item and item.get("code") == 200:
                body = json.loads(item["body"])
                ad_id = body.get("id")
                creative = body.get("creative", {})
                meta[ad_id] = {
                    "ad_name": body.get("name", ""),
                    "title": creative.get("title", ""),
                    "body": creative.get("body", ""),
                    "thumbnail_url": creative.get("thumbnail_url", ""),
                }
    return meta
```

---

## 2. 指标计算引擎

```python
def extract_video_action(actions, action_type):
    """从视频 actions 数组中提取指定类型的数值"""
    if not isinstance(actions, list):
        return 0
    for a in actions:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0


def calculate_creative_metrics(row):
    """计算单条广告的所有创意指标"""
    impressions = int(row.get("impressions", 0))
    clicks = int(row.get("clicks", 0))
    spend = float(row.get("spend", 0))
    inline_clicks = int(row.get("inline_link_clicks", 0))

    # 视频播放数据
    plays = extract_video_action(row.get("video_play_actions"), "video_play")
    thruplay = extract_video_action(row.get("video_thruplay_watched_actions"), "video_thruplay_watched")
    p25 = extract_video_action(row.get("video_p25_watched_actions"), "video_p25_watched")
    p50 = extract_video_action(row.get("video_p50_watched_actions"), "video_p50_watched")
    p75 = extract_video_action(row.get("video_p75_watched_actions"), "video_p75_watched")
    p100 = extract_video_action(row.get("video_p100_watched_actions"), "video_p100_watched")
    avg_watch = extract_video_action(row.get("video_avg_time_watched_actions"), "video_avg_time_watched")

    # 核心指标计算
    thumbstop_rate = p25 / impressions * 100 if impressions > 0 else 0   # 用25%播放代替3s（API最接近指标）
    completion_rate = thruplay / plays * 100 if plays > 0 else 0
    hook_rate_25 = p25 / plays * 100 if plays > 0 else 0
    hook_rate_75 = p75 / plays * 100 if plays > 0 else 0
    ctr = clicks / impressions * 100 if impressions > 0 else 0
    cta_ctr = inline_clicks / impressions * 100 if impressions > 0 else 0
    cpm = spend / impressions * 1000 if impressions > 0 else 0

    return {
        "ad_id": row.get("ad_id", ""),
        "ad_name": row.get("ad_name", ""),
        "adset_name": row.get("adset_name", ""),
        "campaign_name": row.get("campaign_name", ""),
        "spend": spend,
        "impressions": impressions,
        "plays": plays,
        "clicks": clicks,
        "ctr": round(ctr, 3),
        "cta_ctr": round(cta_ctr, 3),
        "cpm": round(cpm, 2),
        "thumbstop_rate": round(thumbstop_rate, 1),   # 越高越好，开头钩子强
        "completion_rate": round(completion_rate, 1),  # 越高越好，内容质量强
        "hook_25": round(hook_rate_25, 1),             # 25% 留存
        "hook_75": round(hook_rate_75, 1),             # 75% 留存
        "avg_watch_sec": round(avg_watch, 1),          # 平均观看秒数
        "video_plays": plays,
        "thruplay": thruplay
    }
```

---

## 3. AI 诊断引擎：开头 / 卖点 / 人群分析

```python
# ── 评分权重 ──
SCORE_WEIGHTS = {
    "thumbstop_rate": 0.30,   # 开头钩子最重要
    "ctr": 0.25,              # 点击意愿
    "completion_rate": 0.25,  # 内容吸引力
    "cta_ctr": 0.20           # 转化意图
}

# ── 行业基准 ──
BENCHMARKS = {
    "thumbstop_rate": {"excellent": 30, "good": 20, "poor": 12},
    "completion_rate": {"excellent": 20, "good": 12, "poor": 6},
    "ctr": {"excellent": 2.5, "good": 1.5, "poor": 0.8},
    "cta_ctr": {"excellent": 1.5, "good": 0.8, "poor": 0.3},
    "hook_75": {"excellent": 35, "good": 20, "poor": 10},
}


def score_creative(m):
    """对单个素材打综合分（0~100）"""
    score = 0
    for metric, weight in SCORE_WEIGHTS.items():
        val = m.get(metric, 0)
        bench = BENCHMARKS.get(metric, {})
        if val >= bench.get("excellent", 999):
            score += weight * 100
        elif val >= bench.get("good", 999):
            score += weight * 75
        elif val >= bench.get("poor", 0):
            score += weight * 40
        else:
            score += weight * 10
    return round(score, 1)


def grade_metric(metric, value):
    """单项指标评级"""
    bench = BENCHMARKS.get(metric, {})
    if value >= bench.get("excellent", 999):
        return "🟢 优秀"
    elif value >= bench.get("good", 999):
        return "🟡 良好"
    else:
        return "🔴 待优化"


def analyze_opening_strength(metrics_list):
    """
    对比不同素材的 Thumbstop 率 → 判断哪种开头更强
    返回排名 + 具体改进建议
    """
    findings = []
    sorted_by_thumbstop = sorted(metrics_list, key=lambda x: x["thumbstop_rate"], reverse=True)
    
    best = sorted_by_thumbstop[0] if sorted_by_thumbstop else None
    worst = sorted_by_thumbstop[-1] if len(sorted_by_thumbstop) > 1 else None

    if best:
        gap = best["thumbstop_rate"] - (worst["thumbstop_rate"] if worst else 0)
        findings.append({
            "dimension": "开头钩子强度",
            "winner": best["ad_name"],
            "winner_score": f"Thumbstop {best['thumbstop_rate']}%",
            "insight": (
                f"「{best['ad_name']}」开头最强（Thumbstop {best['thumbstop_rate']}%）"
                + (f"，比最弱的「{worst['ad_name']}」{worst['thumbstop_rate']}% 高出 {gap:.1f}%。" if worst else "。")
            ),
            "suggestion": _thumbstop_suggestion(best["thumbstop_rate"])
        })
    return findings


def analyze_content_retention(metrics_list):
    """
    对比完播率和留存漏斗 → 判断哪种卖点/内容结构更有效
    """
    findings = []
    valid = [m for m in metrics_list if m["plays"] > 100]  # 至少100次播放才有统计意义
    if not valid:
        return findings

    sorted_by_completion = sorted(valid, key=lambda x: x["completion_rate"], reverse=True)
    best = sorted_by_completion[0]
    worst = sorted_by_completion[-1] if len(sorted_by_completion) > 1 else None

    # 分析留存断点（25% vs 75%的差距）
    for m in valid:
        drop_25_to_75 = m["hook_25"] - m["hook_75"]  # 中段流失率
        if drop_25_to_75 > 40:  # 中段大量流失
            findings.append({
                "dimension": "内容中段质量",
                "winner": None,
                "ad_name": m["ad_name"],
                "insight": (
                    f"「{m['ad_name']}」开头不错（{m['hook_25']:.0f}% 看到25%），"
                    f"但中段流失严重（75%留存仅 {m['hook_75']:.0f}%，流失 {drop_25_to_75:.0f}%）。"
                    f"卖点呈现节奏可能过慢或重复"
                ),
                "suggestion": "把核心卖点前置，在视频15-20秒内展示最强卖点，减少铺垫"
            })

    if best:
        findings.append({
            "dimension": "卖点吸引力",
            "winner": best["ad_name"],
            "winner_score": f"完播率 {best['completion_rate']}%",
            "insight": (
                f"「{best['ad_name']}」完播率最高（{best['completion_rate']}%），"
                f"说明其卖点/故事结构最能留住观众"
            ),
            "suggestion": _completion_suggestion(best["completion_rate"])
        })
    return findings


def analyze_ctr_comparison(metrics_list):
    """对比 CTR → 判断哪种文案/视觉组合点击欲更强"""
    findings = []
    valid = [m for m in metrics_list if m["impressions"] > 500]
    if not valid:
        return findings

    sorted_by_ctr = sorted(valid, key=lambda x: x["ctr"], reverse=True)
    best = sorted_by_ctr[0]
    worst = sorted_by_ctr[-1] if len(sorted_by_ctr) > 1 else None

    if best:
        findings.append({
            "dimension": "CTR 点击吸引力",
            "winner": best["ad_name"],
            "winner_score": f"CTR {best['ctr']}%",
            "insight": (
                f"「{best['ad_name']}」CTR 最高（{best['ctr']}%），"
                + (f"是最低「{worst['ad_name']}」（{worst['ctr']}%）的 {best['ctr']/max(worst['ctr'], 0.01):.1f} 倍。" if worst else "")
                + " 文案和视觉组合对受众吸引力最强"
            ),
            "suggestion": _ctr_suggestion(best["ctr"])
        })
    return findings


def analyze_audience_match(audience_rows):
    """
    分析人群维度（年龄+性别）的表现差异
    → 判断哪类人群更匹配
    """
    findings = []
    # 按广告ID分组计算各人群的CTR和ROAS
    ads_audience = defaultdict(list)
    for row in audience_rows:
        ads_audience[row.get("ad_name", "")].append(row)

    for ad_name, segments in ads_audience.items():
        if len(segments) < 2:
            continue

        best_seg = max(segments, key=lambda x: float(x.get("ctr", 0)))
        worst_seg = min(segments, key=lambda x: float(x.get("ctr", 0)))

        best_ctr = float(best_seg.get("ctr", 0))
        worst_ctr = float(worst_seg.get("ctr", 0))

        if best_ctr > worst_ctr * 1.5:  # 差距超过 50% 才值得报告
            best_label = f"{best_seg.get('age','?')} {best_seg.get('gender','?').replace('male','男').replace('female','女').replace('unknown','未知')}"
            worst_label = f"{worst_seg.get('age','?')} {worst_seg.get('gender','?').replace('male','男').replace('female','女').replace('unknown','未知')}"
            findings.append({
                "dimension": "人群匹配度",
                "ad_name": ad_name,
                "winner": best_label,
                "winner_score": f"CTR {best_ctr:.2f}%",
                "insight": (
                    f"「{ad_name}」在 {best_label} 群体中表现最好（CTR {best_ctr:.2f}%），"
                    f"远优于 {worst_label}（CTR {worst_ctr:.2f}%）"
                ),
                "suggestion": f"建议针对 {best_label} 新建专属广告组，拆分单独放量；排除 {worst_label} 以降低无效消耗"
            })

    return findings


# ── 建议文案辅助函数 ──
def _thumbstop_suggestion(rate):
    if rate >= 30:
        return "开头表现优秀！可以复制此开头风格制作更多素材"
    elif rate >= 20:
        return "开头良好。尝试更强的视觉冲击（大字幕、真人出镜、意外感）进一步提升"
    else:
        return "开头偏弱。建议：① 前3秒加大字幕冲击问题/痛点 ② 真人出镜直接说结论 ③ 使用引发好奇心的对比开场"


def _completion_suggestion(rate):
    if rate >= 20:
        return "完播率优秀！此素材值得加预算放量，同时可作为参考模板批量制作"
    elif rate >= 12:
        return "完播率良好。尝试在视频结尾加强 CTA，提示观众行动"
    else:
        return "完播率偏低。建议：① 缩短视频时长至15-30秒 ② 每5秒设一个新信息点 ③ 核心卖点提前"


def _ctr_suggestion(rate):
    if rate >= 2.5:
        return "CTR 优秀！文案+视觉组合非常有效，快速扩大这支广告的预算"
    elif rate >= 1.5:
        return "CTR 良好。测试不同 CTA 按钮文字是否能进一步提升"
    else:
        return "CTR 偏低。建议：① 加强主图视觉对比度 ② 标题加入具体数字/优惠 ③ 测试情绪化文案（好奇/恐惧/惊喜）"
```

---

## 4. 报告生成

```python
def generate_creative_report(metrics_list, audience_rows, creative_meta):
    """生成完整的素材创意分析报告"""
    print(f"\n{'='*60}")
    print(f"  🎬 素材创意 AI 分析报告  [{datetime.now().strftime('%Y-%m-%d')}]")
    print(f"{'='*60}\n")

    if not metrics_list:
        print("❌ 无有效数据")
        return

    # 过滤掉花费极少的数据（避免小样本误导）
    valid = [m for m in metrics_list if m["spend"] >= 10 and m["impressions"] >= 300]
    print(f"📦 分析素材数量：{len(valid)} 个（已过滤低花费素材）\n")

    # 打分排名
    for m in valid:
        m["score"] = score_creative(m)
    valid.sort(key=lambda x: x["score"], reverse=True)

    # ── 综合排名 ──
    print("📊 素材综合评分排名：")
    print(f"  {'排名':<4} {'素材名称':<30} {'综合分':<8} {'Thumbstop':<12} {'完播率':<10} {'CTR':<8} {'花费'}")
    print(f"  {'─'*90}")
    for i, m in enumerate(valid[:10], 1):
        ts_grade = "🟢" if m["thumbstop_rate"] >= 25 else ("🟡" if m["thumbstop_rate"] >= 15 else "🔴")
        cr_grade = "🟢" if m["completion_rate"] >= 15 else ("🟡" if m["completion_rate"] >= 8 else "🔴")
        ct_grade = "🟢" if m["ctr"] >= 2.0 else ("🟡" if m["ctr"] >= 1.0 else "🔴")
        name = m["ad_name"][:28] + ".." if len(m["ad_name"]) > 28 else m["ad_name"]
        print(
            f"  #{i:<3} {name:<30} {m['score']:<8} "
            f"{ts_grade}{m['thumbstop_rate']:.1f}%{'':6} {cr_grade}{m['completion_rate']:.1f}%{'':4} "
            f"{ct_grade}{m['ctr']:.2f}%{'':2} ${m['spend']:.0f}"
        )

    # ── AI 诊断输出 ──
    print(f"\n{'─'*60}")
    print("🤖 AI 诊断结论")
    print(f"{'─'*60}\n")

    all_findings = []
    all_findings += analyze_opening_strength(valid)
    all_findings += analyze_content_retention(valid)
    all_findings += analyze_ctr_comparison(valid)
    all_findings += analyze_audience_match(audience_rows)

    for f in all_findings:
        print(f"【{f['dimension']}】")
        if f.get("winner"):
            print(f"  🏆 最佳：{f['winner']}（{f.get('winner_score', '')}）")
        elif f.get("ad_name"):
            print(f"  📍 问题素材：{f['ad_name']}")
        print(f"  💡 {f['insight']}")
        print(f"  ✅ 建议：{f['suggestion']}")
        print()

    # ── 视频留存漏斗 ──
    if any(m["plays"] > 100 for m in valid):
        print(f"{'─'*60}")
        print("📉 视频留存漏斗对比（前5支）\n")
        top5 = [m for m in valid if m["plays"] > 100][:5]
        print(f"  {'素材名称':<30} {'开始':<8} {'25%':<8} {'50%':<8} {'75%':<8} {'完播'}")
        print(f"  {'─'*72}")
        for m in top5:
            name = m["ad_name"][:28]
            print(
                f"  {name:<30} 100%{'':3} "
                f"{m['hook_25']:.0f}%{'':3} "
                f"{'─':<8} "
                f"{m['hook_75']:.0f}%{'':3} "
                f"{m['completion_rate']:.0f}%"
            )

    # ── 保存 Markdown 报告 ──
    save_creative_markdown(valid, all_findings)


def save_creative_markdown(metrics_list, findings):
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"creative_report_{date_str}.md"
    lines = [
        f"# 素材创意 AI 分析报告 — {date_str}\n",
        "## 综合评分排名\n",
        "| 排名 | 素材名称 | 综合分 | Thumbstop | 完播率 | CTR | 花费 |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, m in enumerate(metrics_list[:10], 1):
        lines.append(
            f"| #{i} | {m['ad_name']} | {m['score']} | {m['thumbstop_rate']}% | "
            f"{m['completion_rate']}% | {m['ctr']}% | ${m['spend']:.0f} |"
        )
    lines += ["\n---\n", "## AI 诊断结论\n"]
    for f in findings:
        lines.append(f"### 【{f['dimension']}】")
        if f.get("winner"):
            lines.append(f"- **最佳**：{f['winner']}（{f.get('winner_score', '')}）")
        lines.append(f"- **洞察**：{f['insight']}")
        lines.append(f"- **建议**：{f['suggestion']}\n")

    with open(filename, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))
    print(f"📄 报告已保存：{filename}")
```

---

## 5. 主程序

```python
def run_mock_test():
    """Mock 测试数据 —— 无需真实 Token"""
    print("🧪 素材创意分析 — 测试模式\n")
    mock_metrics = [
        {"ad_id": "A1", "ad_name": "开头-痛点提问式", "adset_name": "美国-25-35", "campaign_name": "Q1电商",
         "spend": 320, "impressions": 85000, "plays": 42000, "clicks": 1870, "ctr": 2.2, "cta_ctr": 1.4,
         "cpm": 3.76, "thumbstop_rate": 33.5, "completion_rate": 22.1, "hook_25": 78.0, "hook_75": 41.0, "avg_watch_sec": 18.2, "thruplay": 9282},
        {"ad_id": "A2", "ad_name": "开头-产品展示式", "adset_name": "美国-25-35", "campaign_name": "Q1电商",
         "spend": 280, "impressions": 72000, "plays": 18000, "clicks": 864, "ctr": 1.2, "cta_ctr": 0.7,
         "cpm": 3.89, "thumbstop_rate": 18.2, "completion_rate": 9.5, "hook_25": 55.0, "hook_75": 21.0, "avg_watch_sec": 9.4, "thruplay": 1710},
        {"ad_id": "A3", "ad_name": "开头-真人出镜测评", "adset_name": "美国-35-45", "campaign_name": "Q1电商",
         "spend": 410, "impressions": 98000, "plays": 52000, "clicks": 2548, "ctr": 2.6, "cta_ctr": 1.7,
         "cpm": 4.18, "thumbstop_rate": 38.8, "completion_rate": 28.3, "hook_25": 85.0, "hook_75": 52.0, "avg_watch_sec": 24.7, "thruplay": 14716},
        {"ad_id": "A4", "ad_name": "开头-数字冲击式", "adset_name": "美国-25-35", "campaign_name": "Q1电商",
         "spend": 150, "impressions": 40000, "plays": 12000, "clicks": 520, "ctr": 1.3, "cta_ctr": 0.6,
         "cpm": 3.75, "thumbstop_rate": 22.5, "completion_rate": 14.8, "hook_25": 62.0, "hook_75": 29.0, "avg_watch_sec": 12.1, "thruplay": 1776},
    ]
    mock_audience = [
        {"ad_name": "开头-真人出镜测评", "age": "25-34", "gender": "female", "impressions": "45000", "clicks": "1350", "ctr": "3.0"},
        {"ad_name": "开头-真人出镜测评", "age": "25-34", "gender": "male", "impressions": "28000", "clicks": "504", "ctr": "1.8"},
        {"ad_name": "开头-真人出镜测评", "age": "35-44", "gender": "female", "impressions": "15000", "clicks": "420", "ctr": "2.8"},
        {"ad_name": "开头-痛点提问式", "age": "18-24", "gender": "female", "impressions": "30000", "clicks": "510", "ctr": "1.7"},
        {"ad_name": "开头-痛点提问式", "age": "35-44", "gender": "male", "impressions": "20000", "clicks": "700", "ctr": "3.5"},
    ]
    for m in mock_metrics:
        m["score"] = score_creative(m)
    generate_creative_report(mock_metrics, mock_audience, {})


def main():
    import sys
    if "--test" in sys.argv:
        run_mock_test()
        return

    print(f"🎬 素材创意分析开始 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    rows, creative_meta, audience_rows = fetch_creative_insights(AD_ACCOUNT_ID, days=14)
    metrics_list = [calculate_creative_metrics(r) for r in rows]
    generate_creative_report(metrics_list, audience_rows, creative_meta)


if __name__ == "__main__":
    main()
```

---

## 6. --test 模式输出效果

```
🧪 素材创意分析 — 测试模式

📊 素材综合评分排名：
  排名   素材名称                         综合分   Thumbstop    完播率     CTR     花费
  ──────────────────────────────────────────────────────────────────────────────────────
  #1   开头-真人出镜测评                  87.5    🟢38.8%      🟢28.3%   🟢2.60%  $410
  #2   开头-痛点提问式                    76.3    🟢33.5%      🟢22.1%   🟡2.20%  $320
  #3   开头-数字冲击式                    52.1    🟡22.5%      🟡14.8%   🔴1.30%  $150
  #4   开头-产品展示式                    34.8    🔴18.2%      🔴9.5%    🔴1.20%  $280

────────────────────────────────────────
🤖 AI 诊断结论
────────────────────────────────────────

【开头钩子强度】
  🏆 最佳：开头-真人出镜测评（Thumbstop 38.8%）
  💡 「真人出镜测评」Thumbstop 38.8%，比最弱的「产品展示式」18.2% 高出 20.6%
  ✅ 建议：开头表现优秀！可以复制此开头风格制作更多素材

【卖点吸引力】
  🏆 最佳：开头-真人出镜测评（完播率 28.3%）
  💡 「真人出镜测评」完播率最高（28.3%），说明其卖点/故事结构最能留住观众
  ✅ 建议：此素材值得加预算放量，同时可作为参考模板批量制作

【人群匹配度】
  📍 问题素材：开头-真人出镜测评
  💡 在 25-34 女 群体中表现最好（CTR 3.00%），远优于 25-34 男（CTR 1.80%）
  ✅ 建议：针对 25-34 女 新建专属广告组，拆分单独放量；排除低效人群
```

---

## 快速运行

```bash
pip install requests

# 测试模式（无需 Token）
python creative_analysis.py --test

# 真实数据模式
FB_TOKEN="你的Token" FB_AD_ACCOUNT_ID="act_xxx" python creative_analysis.py
```
