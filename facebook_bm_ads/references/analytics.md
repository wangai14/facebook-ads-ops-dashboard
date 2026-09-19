# 广告数据 AI 智能诊断指南

本模块每天自动抓取 Campaign / AdSet / Ad 三层数据，通过趋势对比和规则引擎输出诊断结论，
将"人肉看表格"变成"AI 做数据诊断"。

> ⚠️ 口径提醒：本模块默认以 `actions` / `action_values` / `purchase_roas` 为主。
> 不建议直接把 `conversions` / `cost_per_result` 当作购买数 / 购买 CPA；
> 对于 purchase / add_to_cart / initiate_checkout / add_payment_info，默认采用“按优先级取单一主口径”，避免重复累计。

---

## 诊断维度总览

| 诊断项 | 核心信号 | 严重级别 |
|---|---|---|
| 广告组衰退 | ROAS 下滑 > 20%，CPA 上升 > 25% | 🔴 严重 |
| 素材疲劳 | 频率 > 2.5，CTR 连续下滑 > 30% | 🟡 警告 |
| 进入学习受限 | `learning_stage_info` = LEARNING_LIMITED | 🟡 警告 |
| 建议关停 | CPA > 目标 × 2，且花费充足 | 🔴 严重 |
| 建议加预算 | ROAS > 目标 × 1.2，近期趋势向上 | 🟢 机会 |
| 数据不足 | 花费 < 最低阈值 | ⚪ 跳过 |

---

## 1. 数据抓取模块

```python
"""
fb_analytics.py — Facebook 广告 AI 诊断完整脚本
使用方法：
  python fb_analytics.py                  # 真实数据
  python fb_analytics.py --test           # Mock 数据测试（无需 Token）
"""

import os
import json
import time
import random
import requests
from datetime import datetime, timedelta
from collections import defaultdict

# ===== 配置区域（根据实际情况修改）=====
CONFIG = {
    "token": os.environ.get("FB_TOKEN", "你的Access_Token"),
    "bm_id": os.environ.get("FB_BM_ID", "你的BM_ID"),

    # 也可以直接指定账户列表（跳过BM查询）
    "ad_account_ids": [],  # 示例: ["act_111", "act_222"]

    # 诊断阈值（根据你的实际业务设置）
    "target_roas": 2.5,          # 目标 ROAS
    "target_cpa": 50.0,          # 目标 CPA（美元）
    "min_spend_to_diagnose": 20, # 花费低于此值跳过诊断（数据不可靠）
    "fatigue_frequency": 2.5,    # 频率超过此值判定为素材疲劳
    "ctr_drop_threshold": 0.30,  # CTR 下滑超过 30% 判定疲劳
    "roas_drop_threshold": 0.20, # ROAS 下滑超过 20% 判定衰退
    "cpa_rise_threshold": 0.25,  # CPA 上升超过 25% 判定衰退

    "api_version": "v22.0",
    "lookback_days": 14,         # 总回看天数
    "recent_days": 3,            # "近期"天数（用于趋势对比）
}

BASE_URL = f"https://graph.facebook.com/{CONFIG['api_version']}"
TOKEN = CONFIG["token"]


# ===== 工具函数 =====

def api_get(url, params, max_retries=5):
    """GET 请求，含指数退避重试"""
    if "access_token" not in params:
        params["access_token"] = TOKEN
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            if "error" in data:
                code = data["error"].get("code")
                if code in [4, 17, 32, 613]:
                    wait = min(300, (2 ** attempt) * 5 + random.uniform(0, 2))
                    print(f"  ⏳ 限速，等待 {wait:.0f}s...")
                    time.sleep(wait)
                    continue
                raise Exception(f"API 错误 {code}: {data['error'].get('message')}")
            return data
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(5)
    raise Exception("超过最大重试次数")


def paginate(endpoint, params):
    """自动分页，返回全部数据"""
    results = []
    url = f"{BASE_URL}/{endpoint}"
    current_params = {**params, "access_token": TOKEN}
    while url:
        data = api_get(url, current_params)
        results.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        current_params = {}
    return results
```

---

## 2. 核心数据抓取函数

```python
def get_ad_accounts():
    """从 BM 获取所有活跃广告账户"""
    if CONFIG["ad_account_ids"]:
        return CONFIG["ad_account_ids"]

    accounts = paginate(f"{CONFIG['bm_id']}/owned_ad_accounts", {
        "fields": "id,name,account_status",
        "limit": 200
    })
    active = [a["id"] for a in accounts if a.get("account_status") == 1]
    print(f"📋 找到 {len(active)} 个活跃账户")
    return active


def fetch_insights_two_periods(account_id):
    """
    抓取两个时段的数据用于趋势对比：
    - recent:   近 N 天（默认近3天）
    - baseline: 之前的数据（近4-14天）
    返回格式: {"recent": [...], "baseline": [...]}
    """
    today = datetime.now()
    recent_since = (today - timedelta(days=CONFIG["recent_days"])).strftime("%Y-%m-%d")
    recent_until = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    base_since = (today - timedelta(days=CONFIG["lookback_days"])).strftime("%Y-%m-%d")
    base_until = (today - timedelta(days=CONFIG["recent_days"] + 1)).strftime("%Y-%m-%d")

    fields = ",".join([
        "campaign_id", "campaign_name",
        "adset_id", "adset_name",
        "ad_id", "ad_name",
        "spend", "impressions", "clicks", "reach", "frequency",
        "ctr", "cpc", "cpm", "purchase_roas", "actions", "action_values"
    ])

    results = {}
    for period_name, since, until in [
        ("recent", recent_since, recent_until),
        ("baseline", base_since, base_until)
    ]:
        data = paginate(f"{account_id}/insights", {
            "fields": fields,
            "time_range": json.dumps({"since": since, "until": until}),
            "level": "ad",
            "time_increment": "all_days",
            "limit": 500
        })
        results[period_name] = data
        time.sleep(0.5)

    return results


def fetch_adset_learning_status(account_id):
    """
    获取广告组的学习阶段状态（检测"学习受限"）
    仅有效状态的广告组有 learning_stage_info
    """
    adsets = paginate(f"{account_id}/adsets", {
        "fields": "id,name,status,learning_stage_info,daily_budget",
        "effective_status": json.dumps(["ACTIVE", "LEARNING"]),
        "limit": 200
    })
    return {a["id"]: a for a in adsets}
```

---

## 3. AI 诊断引擎

```python
PURCHASE_ALIASES = [
    "omni_purchase",
    "purchase",
    "web_in_store_purchase",
    "onsite_web_purchase",
    "onsite_web_app_purchase",
    "offsite_conversion.fb_pixel_purchase",
    "offsite_conversion.purchase",
    "app_custom_event.fb_mobile_purchase",
]

ADD_TO_CART_ALIASES = [
    "omni_add_to_cart",
    "add_to_cart",
    "onsite_web_add_to_cart",
    "onsite_web_app_add_to_cart",
    "offsite_conversion.fb_pixel_add_to_cart",
    "offsite_conversion.add_to_cart",
    "app_custom_event.fb_mobile_add_to_cart",
]

INITIATE_CHECKOUT_ALIASES = [
    "omni_initiated_checkout",
    "initiate_checkout",
    "onsite_web_initiate_checkout",
    "onsite_web_app_initiate_checkout",
    "offsite_conversion.fb_pixel_initiate_checkout",
    "offsite_conversion.initiate_checkout",
    "app_custom_event.fb_mobile_initiated_checkout",
]

ADD_PAYMENT_INFO_ALIASES = [
    "omni_add_payment_info",
    "add_payment_info",
    "onsite_web_add_payment_info",
    "onsite_web_app_add_payment_info",
    "offsite_conversion.fb_pixel_add_payment_info",
    "offsite_conversion.add_payment_info",
]


def extract_action_metric_prefer_first(row, aliases):
    """按优先级提取单一主口径，避免重复累计同一事件。"""
    values = {}
    for action in row.get("actions", []):
        action_type = action.get("action_type")
        if not action_type:
            continue
        try:
            values[action_type] = float(action.get("value", 0))
        except (TypeError, ValueError):
            continue

    for alias in aliases:
        if alias in values:
            return values[alias]
    return 0.0


def extract_roas(row):
    """从 insights 行中提取 ROAS 数值"""
    roas_list = row.get("purchase_roas", [])
    if isinstance(roas_list, list) and roas_list:
        for alias in PURCHASE_ALIASES:
            for item in roas_list:
                if item.get("action_type") == alias:
                    return float(item.get("value", 0))
        return float(roas_list[0].get("value", 0))
    return 0.0


def extract_conversions(row):
    """按优先级提取购买数；不要把多个 purchase alias 直接相加，也不要默认用 conversions 代替购买。"""
    return extract_action_metric_prefer_first(row, PURCHASE_ALIASES)


def build_index(rows, key="adset_id"):
    """将 insights 列表构建为按 ID 索引的字典"""
    index = defaultdict(lambda: {
        "spend": 0, "impressions": 0, "clicks": 0, "reach": 0.001,
        "frequency": 0, "conversions": 0, "roas_sum": 0, "roas_count": 0,
        "cpa_sum": 0, "cpa_count": 0, "name": ""
    })
    for row in rows:
        k = row.get(key, "")
        if not k:
            continue
        d = index[k]
        d["name"] = row.get(f"{key.replace('_id','')}_name", k)
        d["account_id"] = row.get("account_id", "")
        d["spend"] += float(row.get("spend", 0))
        d["impressions"] += int(row.get("impressions", 0))
        d["clicks"] += int(row.get("clicks", 0))
        reach = float(row.get("reach", 0))
        d["reach"] += reach
        roas = extract_roas(row)
        if roas > 0:
            d["roas_sum"] += roas
            d["roas_count"] += 1
        conversions = extract_conversions(row)
        if conversions > 0:
            d["conversions"] += conversions
            d["cpa_sum"] += d["spend"] / max(d["conversions"], 1)
            d["cpa_count"] = 1
    
    # 计算 CTR、频率、平均 ROAS/CPA
    for k, d in index.items():
        d["ctr"] = d["clicks"] / max(d["impressions"], 1) * 100
        d["cpm"] = d["spend"] / max(d["impressions"], 1) * 1000
        d["frequency"] = d["impressions"] / max(d["reach"], 1)
        d["avg_roas"] = d["roas_sum"] / max(d["roas_count"], 1)
        d["avg_cpa"] = d["cpa_sum"] / max(d["cpa_count"], 1)
    return dict(index)


def diagnose(account_id, all_periods, learning_status):
    """
    主诊断函数，返回诊断结论列表
    每条结论格式: {
        "level": "critical/warning/opportunity/skip",
        "category": "衰退/疲劳/学习受限/关停/加预算",
        "entity_type": "adset/ad/campaign",
        "entity_id": "...",
        "entity_name": "...",
        "reason": "具体原因",
        "action": "建议操作",
        "metrics": {...}
    }
    """
    findings = []
    cfg = CONFIG

    recent_adsets = build_index(all_periods["recent"], key="adset_id")
    base_adsets = build_index(all_periods["baseline"], key="adset_id")
    recent_ads = build_index(all_periods["recent"], key="ad_id")
    base_ads = build_index(all_periods["baseline"], key="ad_id")

    # ── 1. 广告组维度诊断 ──────────────────────────────────
    all_adset_ids = set(recent_adsets) | set(base_adsets)

    for adset_id in all_adset_ids:
        r = recent_adsets.get(adset_id)
        b = base_adsets.get(adset_id)
        linfo = learning_status.get(adset_id, {})
        name = (r or b or {}).get("name", adset_id)

        # 学习受限检测
        lsi = linfo.get("learning_stage_info", {})
        if lsi.get("status") == "LEARNING_LIMITED":
            reasons_map = {
                "LOW_CONVERSIONS": "转化量不足（过去7天少于50次）",
                "LOW_BUDGET": "预算过低，限制了覆盖",
                "AD_APPROVAL": "有广告未通过审核",
                "CREATIVE_FATIGUE": "素材疲劳，触达重复率过高",
                "AD_SET_CHANGES": "近期频繁修改广告组设置",
            }
            sub_reasons = [
                reasons_map.get(r, r)
                for r in lsi.get("attribution_windows", [])
            ]
            findings.append({
                "level": "warning",
                "category": "学习受限",
                "entity_type": "adset",
                "entity_id": adset_id,
                "entity_name": name,
                "reason": f"广告组处于学习受限状态。原因：{', '.join(sub_reasons) or '未知'}",
                "action": "扩大预算至建议金额，减少近期修改，合并受众或广告，等待重新学习",
                "metrics": {}
            })

        # 数据不足跳过
        if not r or r["spend"] < cfg["min_spend_to_diagnose"]:
            findings.append({
                "level": "skip",
                "category": "数据不足",
                "entity_type": "adset",
                "entity_id": adset_id,
                "entity_name": name,
                "reason": f"近期花费 ${r['spend']:.2f} 低于诊断阈值 ${cfg['min_spend_to_diagnose']}，数据不可靠",
                "action": "暂不诊断，等待更多数据积累",
                "metrics": {"spend": r["spend"] if r else 0}
            })
            continue

        recent_roas = r["avg_roas"]
        base_roas = b["avg_roas"] if b else recent_roas
        recent_cpa = r["avg_cpa"]
        base_cpa = b["avg_cpa"] if b else recent_cpa

        # 广告组衰退检测
        roas_drop = (base_roas - recent_roas) / max(base_roas, 0.01)
        cpa_rise = (recent_cpa - base_cpa) / max(base_cpa, 0.01)

        if base_roas > 0 and roas_drop > cfg["roas_drop_threshold"]:
            findings.append({
                "level": "critical",
                "category": "广告组衰退",
                "entity_type": "adset",
                "entity_id": adset_id,
                "entity_name": name,
                "reason": f"ROAS 从 {base_roas:.2f}x 下滑至 {recent_roas:.2f}x（下降 {roas_drop*100:.0f}%）",
                "action": "检查素材是否疲劳，考虑更换创意或缩减预算",
                "metrics": {
                    "recent_roas": recent_roas, "base_roas": base_roas,
                    "drop_pct": f"{roas_drop*100:.0f}%",
                    "spend_recent": r["spend"]
                }
            })
        elif base_cpa > 0 and cpa_rise > cfg["cpa_rise_threshold"]:
            findings.append({
                "level": "critical",
                "category": "广告组衰退",
                "entity_type": "adset",
                "entity_id": adset_id,
                "entity_name": name,
                "reason": f"CPA 从 ${base_cpa:.2f} 上升至 ${recent_cpa:.2f}（上升 {cpa_rise*100:.0f}%）",
                "action": "评估受众是否饱和，考虑刷新素材或调整竞价策略",
                "metrics": {
                    "recent_cpa": recent_cpa, "base_cpa": base_cpa,
                    "rise_pct": f"{cpa_rise*100:.0f}%"
                }
            })

        # 建议关停（CPA 超目标 2 倍）
        if recent_cpa > cfg["target_cpa"] * 2 and r["spend"] >= cfg["min_spend_to_diagnose"] * 2:
            findings.append({
                "level": "critical",
                "category": "建议关停",
                "entity_type": "adset",
                "entity_id": adset_id,
                "entity_name": name,
                "reason": f"CPA ${recent_cpa:.2f} 是目标 ${cfg['target_cpa']} 的 {recent_cpa/cfg['target_cpa']:.1f} 倍，持续亏损",
                "action": "立即暂停该广告组，分析受众/素材/落地页问题后再重启",
                "metrics": {"cpa": recent_cpa, "target_cpa": cfg["target_cpa"], "spend": r["spend"]}
            })

        # 建议加预算（ROAS 超目标 1.2 倍）
        elif recent_roas > cfg["target_roas"] * 1.2 and roas_drop < 0:  # 趋势向上
            findings.append({
                "level": "opportunity",
                "category": "建议加预算",
                "entity_type": "adset",
                "entity_id": adset_id,
                "entity_name": name,
                "reason": f"ROAS {recent_roas:.2f}x 超过目标 {cfg['target_roas']}x × 1.2，且趋势向上",
                "action": f"建议将日预算提升 20-30%，当前约 ${r['spend']/3:.0f}/天",
                "metrics": {"roas": recent_roas, "target_roas": cfg["target_roas"]}
            })

    # ── 2. 广告维度：素材疲劳检测 ──────────────────────────
    all_ad_ids = set(recent_ads) | set(base_ads)

    for ad_id in all_ad_ids:
        r = recent_ads.get(ad_id)
        b = base_ads.get(ad_id)
        if not r or r["spend"] < cfg["min_spend_to_diagnose"] / 2:
            continue

        name = r.get("name", ad_id)
        freq = r["frequency"]
        ctr_recent = r["ctr"]
        ctr_base = b["ctr"] if b and b["ctr"] > 0 else ctr_recent
        ctr_drop = (ctr_base - ctr_recent) / max(ctr_base, 0.001)

        fatigue_reasons = []
        if freq > cfg["fatigue_frequency"]:
            fatigue_reasons.append(f"频率 {freq:.2f}（阈值 {cfg['fatigue_frequency']}）")
        if ctr_drop > cfg["ctr_drop_threshold"]:
            fatigue_reasons.append(f"CTR 从 {ctr_base:.2f}% 降至 {ctr_recent:.2f}%（下滑 {ctr_drop*100:.0f}%）")

        if fatigue_reasons:
            findings.append({
                "level": "warning",
                "category": "素材疲劳",
                "entity_type": "ad",
                "entity_id": ad_id,
                "entity_name": name,
                "reason": "素材疲劳信号：" + "；".join(fatigue_reasons),
                "action": "立即更换或测试新素材，可复制广告组并替换创意",
                "metrics": {
                    "frequency": freq, "ctr_recent": ctr_recent,
                    "ctr_base": ctr_base, "ctr_drop": f"{ctr_drop*100:.0f}%"
                }
            })

    return findings
```

---

## 4. 报告输出模块

```python
LEVEL_ICON = {
    "critical": "🔴",
    "warning": "🟡",
    "opportunity": "🟢",
    "skip": "⚪",
}

LEVEL_LABEL = {
    "critical": "严重",
    "warning": "警告",
    "opportunity": "机会",
    "skip": "跳过",
}


def print_report(all_findings, account_summary):
    """在终端输出彩色诊断报告"""
    try:
        from colorama import init, Fore, Style
        init(autoreset=True)
        RED = Fore.RED
        YELLOW = Fore.YELLOW
        GREEN = Fore.GREEN
        RESET = Style.RESET_ALL
        BOLD = Style.BRIGHT
    except ImportError:
        RED = YELLOW = GREEN = RESET = BOLD = ""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*60}")
    print(f"  📊 Facebook 广告 AI 诊断报告  [{now}]")
    print(f"{'='*60}\n")

    # 按严重级别分组统计
    by_level = defaultdict(list)
    for f in all_findings:
        by_level[f["level"]].append(f)

    print(f"🔴 严重问题: {len(by_level['critical'])} 项")
    print(f"🟡 警告:     {len(by_level['warning'])} 项")
    print(f"🟢 优化机会: {len(by_level['opportunity'])} 项")
    print(f"⚪ 数据不足: {len(by_level['skip'])} 项")
    print()

    # 按优先级输出
    for level in ["critical", "warning", "opportunity"]:
        items = by_level[level]
        if not items:
            continue
        color = RED if level == "critical" else (YELLOW if level == "warning" else GREEN)
        print(f"{color}{BOLD}{'─'*55}{RESET}")
        print(f"{color}{BOLD}  {LEVEL_ICON[level]} {LEVEL_LABEL[level]}（{len(items)} 项）{RESET}")
        print(f"{color}{BOLD}{'─'*55}{RESET}")

        for f in items:
            print(f"\n  {LEVEL_ICON[level]} [{f['category']}] {BOLD}{f['entity_name']}{RESET}")
            print(f"     📌 原因：{f['reason']}")
            print(f"     ✅ 建议：{color}{f['action']}{RESET}")
            if f.get("metrics"):
                metrics_str = " | ".join(
                    f"{k}: {v}" for k, v in f["metrics"].items()
                )
                print(f"     📈 数据：{metrics_str}")
        print()


def save_markdown_report(all_findings, output_dir="."):
    """保存 Markdown 格式报告"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{output_dir}/fb_report_{date_str}.md"

    lines = [
        f"# Facebook 广告 AI 诊断报告 — {date_str}\n",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"## 汇总\n",
    ]

    by_level = defaultdict(list)
    for f in all_findings:
        by_level[f["level"]].append(f)

    lines += [
        f"| 级别 | 数量 |",
        f"|---|---|",
        f"| 🔴 严重 | {len(by_level['critical'])} |",
        f"| 🟡 警告 | {len(by_level['warning'])} |",
        f"| 🟢 机会 | {len(by_level['opportunity'])} |",
        f"| ⚪ 跳过 | {len(by_level['skip'])} |",
        f"\n---\n",
    ]

    for level in ["critical", "warning", "opportunity"]:
        items = by_level[level]
        if not items:
            continue
        lines.append(f"\n## {LEVEL_ICON[level]} {LEVEL_LABEL[level]}\n")
        for f in items:
            lines.append(f"### [{f['category']}] {f['entity_name']}")
            lines.append(f"- **原因**：{f['reason']}")
            lines.append(f"- **建议**：{f['action']}")
            if f.get("metrics"):
                lines.append("- **数据**：" + " | ".join(f"{k}: {v}" for k, v in f["metrics"].items()))
            lines.append("")

    with open(filename, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))
    print(f"\n📄 报告已保存：{filename}")
    return filename
```

---

## 5. 主函数入口

```python
def run_with_mock_data():
    """使用 Mock 数据测试（无需真实 Token）"""
    mock_recent = [
        {"adset_id": "AS001", "adset_name": "美国-宽泛人群", "ad_id": "AD001", "ad_name": "素材A-红色",
         "spend": "150", "impressions": "50000", "clicks": "300", "reach": "20000",
         "frequency": "2.5", "ctr": "0.6", "cpm": "3.0", "conversions": "3",
         "cost_per_result": "50", "purchase_roas": [{"value": "1.2"}], "actions": []},

        {"adset_id": "AS002", "adset_name": "英国-兴趣定向", "ad_id": "AD002", "ad_name": "素材B-视频",
         "spend": "80", "impressions": "30000", "clicks": "600", "reach": "25000",
         "frequency": "1.2", "ctr": "2.0", "cpm": "2.7", "conversions": "8",
         "cost_per_result": "10", "purchase_roas": [{"value": "4.5"}], "actions": []},

        {"adset_id": "AS003", "adset_name": "再营销-购物车用户", "ad_id": "AD003", "ad_name": "素材C-轮播",
         "spend": "5", "impressions": "500", "clicks": "10", "reach": "400",
         "frequency": "1.25", "ctr": "2.0", "cpm": "10", "conversions": "0",
         "cost_per_result": "0", "purchase_roas": [], "actions": []},
    ]
    mock_baseline = [
        {"adset_id": "AS001", "adset_name": "美国-宽泛人群", "ad_id": "AD001", "ad_name": "素材A-红色",
         "spend": "400", "impressions": "100000", "clicks": "2000", "reach": "50000",
         "frequency": "2.0", "ctr": "2.0", "cpm": "4.0", "conversions": "20",
         "cost_per_result": "20", "purchase_roas": [{"value": "3.5"}], "actions": []},

        {"adset_id": "AS002", "adset_name": "英国-兴趣定向", "ad_id": "AD002", "ad_name": "素材B-视频",
         "spend": "200", "impressions": "60000", "clicks": "900", "reach": "52000",
         "frequency": "1.15", "ctr": "1.5", "cpm": "3.3", "conversions": "15",
         "cost_per_result": "13.3", "purchase_roas": [{"value": "3.8"}], "actions": []},
    ]
    mock_learning = {
        "AS001": {
            "id": "AS001",
            "name": "美国-宽泛人群",
            "learning_stage_info": {
                "status": "LEARNING_LIMITED",
                "attribution_windows": ["LOW_CONVERSIONS", "CREATIVE_FATIGUE"]
            }
        }
    }
    print("🧪 使用 Mock 数据运行测试...\n")
    findings = diagnose("act_test", {"recent": mock_recent, "baseline": mock_baseline}, mock_learning)
    print_report(findings, {})
    save_markdown_report(findings)


def main():
    import sys
    if "--test" in sys.argv:
        run_with_mock_data()
        return

    print(f"🚀 Facebook 广告 AI 诊断开始 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    accounts = get_ad_accounts()
    all_findings = []

    for acc_id in accounts:
        print(f"\n📊 分析账户: {acc_id}")
        try:
            periods = fetch_insights_two_periods(acc_id)
            learning = fetch_adset_learning_status(acc_id)
            findings = diagnose(acc_id, periods, learning)
            all_findings.extend(findings)
            print(f"   发现 {len([f for f in findings if f['level'] in ['critical','warning']])} 个需关注问题")
        except Exception as e:
            print(f"   ❌ 账户分析失败: {e}")

    print_report(all_findings, {})
    save_markdown_report(all_findings)


if __name__ == "__main__":
    main()
```

---

## 6. 快速使用

### 安装依赖

```bash
pip install requests colorama
```

### 配置

修改脚本顶部的 `CONFIG` 字典：

```python
CONFIG = {
    "token": "你的System_User_Token",   # 永不过期，推荐
    "bm_id": "你的BM_ID",
    "target_roas": 2.5,                  # 根据业务实际设置
    "target_cpa": 50.0,
    ...
}
```

### 运行

```bash
# 测试模式（无需 Token，验证脚本逻辑）
python fb_analytics.py --test

# 真实数据模式
python fb_analytics.py
```

### 定时运行（Windows 任务计划）

```powershell
# 创建每天早上 8:00 自动运行的定时任务
schtasks /create /tn "FB广告AI诊断" /tr "python d:\scripts\fb_analytics.py" /sc daily /st 08:00
```

### 定时运行（Linux / Mac cron）

```bash
# crontab -e
0 8 * * * /usr/bin/python3 /path/to/fb_analytics.py >> /var/log/fb_ads.log 2>&1
```

---

## 7. 诊断阈值调优建议

| 行业 | target_roas | target_cpa | fatigue_frequency |
|---|---|---|---|
| 电商（快消） | 3.0 ~ 5.0 | $20 ~ $40 | 2.0 |
| 电商（高客单） | 2.0 ~ 3.0 | $80 ~ $150 | 3.0 |
| 线索收集 | — | $10 ~ $30 | 2.5 |
| APP 安装 | — | $1 ~ $5 | 3.0 |
| 品牌推广 | — | — | 4.0 |
