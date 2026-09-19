#!/usr/bin/env python3
r"""Facebook / Meta ads pull + ecommerce diagnosis.

Usage examples:
  python fb_pull_report.py --token-path ..\..\data\facebook_token.txt --date-preset last_30d
  python fb_pull_report.py --token-path C:\...\token.txt --since 2026-03-01 --until 2026-03-31 --levels campaign,adset,ad
  python fb_pull_report.py --mock

Design rules:
- Never sum purchase/add-to-cart/checkout aliases. Pick one canonical alias by priority.
- Prefer action_report_time=conversion and use_unified_attribution_setting=true.
- If the requested preset has zero spend, optionally backfill last_30d/last_90d/maximum to find the latest active period.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import requests
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: pip install requests") from exc

DEFAULT_API_VERSION = "v22.0"
RATE_LIMIT_CODES = {4, 17, 32, 613, 80004}
DEFAULT_TARGET_CPA = 50.0
DEFAULT_TARGET_ROAS = 2.5
DEFAULT_MIN_SPEND_TO_DIAGNOSE = 20.0
DEFAULT_MIN_LINK_CLICKS_TO_DIAGNOSE = 20.0
DEFAULT_FATIGUE_FREQUENCY = 2.5

METRIC_ALIASES: Dict[str, List[str]] = {
    "purchase": [
        "omni_purchase",
        "purchase",
        "web_in_store_purchase",
        "onsite_web_purchase",
        "onsite_web_app_purchase",
        "offsite_conversion.fb_pixel_purchase",
        "offsite_conversion.purchase",
        "app_custom_event.fb_mobile_purchase",
    ],
    "add_to_cart": [
        "omni_add_to_cart",
        "add_to_cart",
        "onsite_web_add_to_cart",
        "onsite_web_app_add_to_cart",
        "offsite_conversion.fb_pixel_add_to_cart",
        "offsite_conversion.add_to_cart",
        "app_custom_event.fb_mobile_add_to_cart",
    ],
    "checkout": [
        "omni_initiated_checkout",
        "initiate_checkout",
        "onsite_web_initiate_checkout",
        "onsite_web_app_initiate_checkout",
        "offsite_conversion.fb_pixel_initiate_checkout",
        "offsite_conversion.initiate_checkout",
        "app_custom_event.fb_mobile_initiated_checkout",
    ],
    "add_payment_info": [
        "omni_add_payment_info",
        "add_payment_info",
        "onsite_web_add_payment_info",
        "onsite_web_app_add_payment_info",
        "offsite_conversion.fb_pixel_add_payment_info",
        "offsite_conversion.add_payment_info",
        "app_custom_event.fb_mobile_add_payment_info",
    ],
    "view_content": [
        "omni_view_content",
        "view_content",
        "onsite_web_view_content",
        "offsite_conversion.fb_pixel_view_content",
    ],
    "landing_page_view": [
        "landing_page_view",
    ],
}

INSIGHT_BASE_FIELDS = [
    "date_start", "date_stop",
    "spend", "impressions", "reach", "frequency", "clicks", "inline_link_clicks",
    "ctr", "cpc", "cpm", "actions", "action_values", "purchase_roas",
]
LEVEL_FIELDS = {
    "account": INSIGHT_BASE_FIELDS,
    "campaign": ["campaign_id", "campaign_name"] + INSIGHT_BASE_FIELDS,
    "adset": ["campaign_id", "campaign_name", "adset_id", "adset_name"] + INSIGHT_BASE_FIELDS,
    "ad": ["campaign_id", "campaign_name", "adset_id", "adset_name", "ad_id", "ad_name"] + INSIGHT_BASE_FIELDS,
}
STATUS_FIELDS = {
    "campaign": "id,name,status,effective_status,objective,daily_budget,lifetime_budget,buying_type,created_time,updated_time",
    "adset": "id,name,campaign_id,status,effective_status,learning_stage_info,daily_budget,lifetime_budget,bid_strategy,optimization_goal,billing_event,created_time,updated_time",
    "ad": "id,name,campaign_id,adset_id,status,effective_status,creative{id,name,thumbnail_url,video_id,image_hash},created_time,updated_time",
}
CSV_COLUMNS = [
    "account_id", "account_name", "level", "date_start", "date_stop",
    "campaign_id", "campaign_name", "adset_id", "adset_name", "ad_id", "ad_name",
    "spend", "impressions", "reach", "frequency", "clicks", "inline_link_clicks",
    "ctr", "cpc", "cpm", "purchase", "purchase_alias", "purchase_value", "purchase_value_alias",
    "roas", "roas_source", "cpa", "add_to_cart", "atc_alias", "checkout", "checkout_alias",
    "add_payment_info", "api_alias", "view_content", "landing_page_view",
    "effective_status", "status", "learning_status", "daily_budget", "optimization_goal",
]
REPORT_FINDING_COLUMNS = [
    "account_id", "account_name", "level", "entity", "category", "name", "entity_id",
    "reason", "action",
]
REPORT_ACCOUNT_COLUMNS = [
    "account_id", "account_name", "preset", "spend", "impressions", "clicks",
    "purchase", "roas", "critical", "warning", "opportunity", "info",
]


def num(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def as_int(value: Any) -> int:
    return int(round(num(value)))


def redact_secret_text(text: Any) -> str:
    redacted = str(text)
    redacted = re.sub(r"(access_token=)[^&\s]+", r"\1<redacted>", redacted)
    redacted = re.sub(r"(access_token['\"]?\s*[:=]\s*['\"]?)[^,'\"\s}]+", r"\1<redacted>", redacted)
    return redacted


def load_decision_config(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if path is None:
        return {"defaults": {}, "accounts": {}}
    if not path.exists():
        raise SystemExit(f"Decision config not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Decision config must be a JSON object: {path}")
    if "defaults" in data or "accounts" in data:
        defaults = data.get("defaults", {})
        accounts = data.get("accounts", {})
    else:
        defaults = data
        accounts = {}
    if not isinstance(defaults, dict) or not isinstance(accounts, dict):
        raise SystemExit(f"Decision config sections must be JSON objects: {path}")
    return {"defaults": defaults, "accounts": accounts}


def resolve_settings(args: argparse.Namespace, account: Dict[str, Any], decision_config: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    settings: Dict[str, float] = {
        "target_cpa": float(args.target_cpa),
        "target_roas": float(args.target_roas),
        "min_spend_to_diagnose": float(args.min_spend_to_diagnose),
        "min_link_clicks_to_diagnose": float(args.min_link_clicks_to_diagnose),
        "fatigue_frequency": float(args.fatigue_frequency),
    }

    def apply_overrides(overrides: Any) -> None:
        if not isinstance(overrides, dict):
            return
        for key in settings:
            if key in overrides:
                settings[key] = num(overrides[key])

    apply_overrides(decision_config.get("defaults"))
    account_overrides = decision_config.get("accounts", {})
    if isinstance(account_overrides, dict):
        apply_overrides(account_overrides.get(account.get("id")))
        apply_overrides(account_overrides.get(account.get("name")))
    return settings


def entity_label(row: Dict[str, Any], level: str, account: Dict[str, Any]) -> Tuple[str, str]:
    if level == "account":
        entity_id = str(account.get("id", ""))
        name = str(account.get("name") or entity_id or "account")
    else:
        entity_id = str(row.get(f"{level}_id") or "")
        name = str(row.get(f"{level}_name") or row.get("name") or entity_id or level)
    return name, entity_id


class MetaClient:
    def __init__(self, token: str, api_version: str = DEFAULT_API_VERSION, timeout: int = 60):
        self.token = token.strip()
        self.api_version = api_version.strip().lstrip("/")
        self.base = f"https://graph.facebook.com/{self.api_version}"
        self.timeout = timeout

    def get(self, endpoint_or_url: str, params: Optional[Dict[str, Any]] = None, retries: int = 5) -> Dict[str, Any]:
        url = endpoint_or_url if endpoint_or_url.startswith("http") else f"{self.base}/{endpoint_or_url.lstrip('/')}"
        current = dict(params or {})
        if "access_token" not in current and "access_token=" not in url:
            current["access_token"] = self.token
        for attempt in range(retries):
            try:
                resp = requests.get(url, params=current, timeout=self.timeout)
            except requests.exceptions.RequestException as exc:
                if attempt < retries - 1:
                    wait = min(120, (2 ** attempt) * 3 + random.random() * 2)
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Meta API request failed after retries: {type(exc).__name__}: {redact_secret_text(exc)}") from exc
            try:
                data = resp.json()
            except Exception:
                data = {"error": {"message": resp.text[:1000], "code": resp.status_code}}
            if resp.status_code < 400 and "error" not in data:
                return data
            err = data.get("error", {}) if isinstance(data, dict) else {}
            code = err.get("code")
            if code in RATE_LIMIT_CODES and attempt < retries - 1:
                wait = min(300, (2 ** attempt) * 5 + random.random() * 3)
                time.sleep(wait)
                continue
            raise RuntimeError(json.dumps(data, ensure_ascii=False)[:2500])
        raise RuntimeError("Meta API retry exhausted")

    def pages(self, endpoint: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        url: Optional[str] = endpoint
        current: Dict[str, Any] = dict(params)
        while url:
            data = self.get(url, current)
            rows.extend(data.get("data", []))
            url = data.get("paging", {}).get("next")
            current = {}
        return rows


def action_map(items: Any) -> Dict[str, float]:
    if not isinstance(items, list):
        return {}
    out: Dict[str, float] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        action_type = item.get("action_type")
        if action_type:
            out[action_type] = num(item.get("value"))
    return out


def pick_metric(items: Any, metric: str) -> Tuple[float, str]:
    values = action_map(items)
    for alias in METRIC_ALIASES[metric]:
        if alias in values:
            return values[alias], alias
    return 0.0, ""


def pick_purchase_roas(items: Any) -> Tuple[float, str]:
    values = action_map(items)
    for alias in METRIC_ALIASES["purchase"]:
        if alias in values:
            return values[alias], alias
    if values:
        first_alias = next(iter(values))
        return values[first_alias], first_alias
    return 0.0, ""


def enrich_row(row: Dict[str, Any], account: Dict[str, Any], level: str, status_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    purchase, purchase_alias = pick_metric(row.get("actions"), "purchase")
    atc, atc_alias = pick_metric(row.get("actions"), "add_to_cart")
    checkout, checkout_alias = pick_metric(row.get("actions"), "checkout")
    api, api_alias = pick_metric(row.get("actions"), "add_payment_info")
    vc, _ = pick_metric(row.get("actions"), "view_content")
    lpv, _ = pick_metric(row.get("actions"), "landing_page_view")
    purchase_value, value_alias = pick_metric(row.get("action_values"), "purchase")
    spend = num(row.get("spend"))
    roas = purchase_value / spend if spend and purchase_value else 0.0
    roas_source = "action_values/spend" if roas else ""
    if not roas:
        roas, roas_alias = pick_purchase_roas(row.get("purchase_roas"))
        roas_source = f"purchase_roas:{roas_alias}" if roas_alias else ""
    cpa = spend / purchase if purchase else 0.0

    entity_id = row.get(f"{level}_id") if level != "account" else account.get("id")
    status = status_index.get(str(entity_id or ""), {})
    learning_info = status.get("learning_stage_info") or {}
    if isinstance(learning_info, dict):
        learning_status = learning_info.get("status", "")
    else:
        learning_status = ""

    enriched = dict(row)
    enriched.update({
        "account_id": account.get("id", ""),
        "account_name": account.get("name", ""),
        "level": level,
        "spend": spend,
        "impressions": as_int(row.get("impressions")),
        "reach": as_int(row.get("reach")),
        "frequency": num(row.get("frequency")),
        "clicks": as_int(row.get("clicks")),
        "inline_link_clicks": as_int(row.get("inline_link_clicks")),
        "ctr": num(row.get("ctr")),
        "cpc": num(row.get("cpc")),
        "cpm": num(row.get("cpm")),
        "purchase": purchase,
        "purchase_alias": purchase_alias,
        "purchase_value": purchase_value,
        "purchase_value_alias": value_alias,
        "roas": roas,
        "roas_source": roas_source,
        "cpa": cpa,
        "add_to_cart": atc,
        "atc_alias": atc_alias,
        "checkout": checkout,
        "checkout_alias": checkout_alias,
        "add_payment_info": api,
        "api_alias": api_alias,
        "view_content": vc,
        "landing_page_view": lpv,
        "effective_status": status.get("effective_status", ""),
        "status": status.get("status", ""),
        "learning_status": learning_status,
        "daily_budget": status.get("daily_budget", ""),
        "optimization_goal": status.get("optimization_goal", ""),
    })
    return enriched


def flatten_for_csv(row: Dict[str, Any]) -> Dict[str, Any]:
    return {col: row.get(col, "") for col in CSV_COLUMNS}


def write_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(flatten_for_csv(row))


def write_csv_with_columns(path: Path, rows: Iterable[Dict[str, Any]], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def preset_params(args: argparse.Namespace, preset: Optional[str] = None) -> Dict[str, Any]:
    if args.since and args.until:
        return {"time_range": json.dumps({"since": args.since, "until": args.until}, ensure_ascii=False)}
    return {"date_preset": preset or args.date_preset}


def sum_spend(rows: Iterable[Dict[str, Any]]) -> float:
    return sum(num(r.get("spend")) for r in rows)


def find_effective_preset(client: MetaClient, account_id: str, args: argparse.Namespace) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]]]:
    """If current preset is empty, backfill to find the latest useful preset."""
    fields = ",".join(LEVEL_FIELDS["account"])
    first_params = {
        **preset_params(args),
        "fields": fields,
        "action_report_time": "conversion",
        "use_unified_attribution_setting": "true",
        "limit": 10,
    }
    try:
        rows = client.pages(f"/{account_id}/insights", first_params)
    except RuntimeError:
        first_params.pop("use_unified_attribution_setting", None)
        rows = client.pages(f"/{account_id}/insights", first_params)
    if sum_spend(rows) > 0 or not args.auto_backfill or args.since:
        return args.date_preset, first_params, rows

    for preset in ["last_30d", "last_90d", "maximum"]:
        params = {
            "date_preset": preset,
            "fields": fields,
            "action_report_time": "conversion",
            "use_unified_attribution_setting": "true",
            "limit": 10,
        }
        try:
            rows = client.pages(f"/{account_id}/insights", params)
        except RuntimeError:
            params.pop("use_unified_attribution_setting", None)
            rows = client.pages(f"/{account_id}/insights", params)
        if sum_spend(rows) > 0:
            return preset, params, rows
    return args.date_preset, first_params, rows


def fetch_status_index(client: MetaClient, account_id: str, level: str) -> Dict[str, Dict[str, Any]]:
    if level == "account":
        return {}
    try:
        rows = client.pages(f"/{account_id}/{level}s", {"fields": STATUS_FIELDS[level], "limit": 500})
    except RuntimeError:
        return {}
    return {str(row.get("id")): row for row in rows if row.get("id")}


def fetch_insights(client: MetaClient, account: Dict[str, Any], level: str, args: argparse.Namespace, effective_preset: str) -> List[Dict[str, Any]]:
    params = {
        **({"date_preset": effective_preset} if not (args.since and args.until) else preset_params(args)),
        "level": level,
        "fields": ",".join(LEVEL_FIELDS[level]),
        "time_increment": args.time_increment,
        "action_report_time": "conversion",
        "use_unified_attribution_setting": "true",
        "limit": args.limit,
    }
    if level == "account":
        params.pop("level", None)
    try:
        rows = client.pages(f"/{account['id']}/insights", params)
    except RuntimeError:
        params.pop("use_unified_attribution_setting", None)
        rows = client.pages(f"/{account['id']}/insights", params)
    status_index = fetch_status_index(client, account["id"], level)
    return [enrich_row(row, account, level, status_index) for row in rows]


def get_accounts(client: MetaClient, account_ids: List[str]) -> List[Dict[str, Any]]:
    if account_ids:
        accounts = []
        for account_id in account_ids:
            account_id = account_id if account_id.startswith("act_") else f"act_{account_id}"
            try:
                data = client.get(f"/{account_id}", {"fields": "id,account_id,name,account_status,currency,timezone_name"})
            except RuntimeError:
                data = {"id": account_id, "name": account_id}
            accounts.append(data)
        return accounts
    return client.pages("/me/adaccounts", {
        "fields": "id,account_id,name,account_status,currency,timezone_name,amount_spent,business{name,id}",
        "limit": 200,
    })


def diagnose(rows_by_level: Dict[str, List[Dict[str, Any]]], account: Dict[str, Any], settings: Dict[str, float]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    ad_rows = rows_by_level.get("ad", [])
    adset_rows = rows_by_level.get("adset", [])
    account_rows = rows_by_level.get("account", [])
    total_spend = sum_spend(account_rows or adset_rows or ad_rows)
    target_cpa = num(settings.get("target_cpa", DEFAULT_TARGET_CPA))
    target_roas = num(settings.get("target_roas", DEFAULT_TARGET_ROAS))
    min_spend_to_diagnose = num(settings.get("min_spend_to_diagnose", DEFAULT_MIN_SPEND_TO_DIAGNOSE))
    min_link_clicks = num(settings.get("min_link_clicks_to_diagnose", DEFAULT_MIN_LINK_CLICKS_TO_DIAGNOSE))
    fatigue_frequency = num(settings.get("fatigue_frequency", DEFAULT_FATIGUE_FREQUENCY))

    if total_spend == 0:
        label, entity_id = entity_label({}, "account", account)
        findings.append({
            "level": "info",
            "category": "无消耗",
            "entity": "account",
            "name": label,
            "entity_id": entity_id,
            "reason": "所选时间范围 spend=0，不能判断 CPA/ROAS/素材疲劳。",
            "action": "检查 campaign/adset/ad 是否暂停；如需回看历史，显式开启 --auto-backfill。",
        })

    for row in adset_rows:
        if row.get("learning_status") == "LEARNING_LIMITED":
            label, entity_id = entity_label(row, "adset", account)
            findings.append({
                "level": "warning",
                "category": "学习受限",
                "entity": "adset",
                "name": label,
                "entity_id": entity_id,
                "reason": "AdSet learning_stage_info=LEARNING_LIMITED。",
                "action": "减少频繁修改，合并碎片广告组，保证预算和转化量；先确认事件回传正常。",
            })

    for row in ad_rows:
        spend = num(row.get("spend"))
        link_clicks = num(row.get("inline_link_clicks") or row.get("clicks"))
        purchase = num(row.get("purchase"))
        atc = num(row.get("add_to_cart"))
        roas = num(row.get("roas"))
        freq = num(row.get("frequency"))
        ctr = num(row.get("ctr"))
        label, entity_id = entity_label(row, "ad", account)

        if spend < min_spend_to_diagnose and link_clicks < min_link_clicks and purchase == 0:
            continue

        if spend >= target_cpa * 2 and purchase == 0:
            findings.append({
                "level": "critical", "category": "强关停候选", "entity": "ad", "name": label, "entity_id": entity_id,
                "reason": f"花费 {spend:.2f} ≥ 目标 CPA×2 且 purchase=0。",
                "action": "暂停该广告；优先排查素材承诺、落地页首屏、像素/CAPI 回传。",
            })
        elif purchase == 0 and ((link_clicks >= min_link_clicks and atc == 0) or (spend >= min_spend_to_diagnose and atc == 0)):
            findings.append({
                "level": "warning", "category": "有点击无加购", "entity": "ad", "name": label, "entity_id": entity_id,
                "reason": f"link_clicks={link_clicks:.0f}, ATC=0，素材/落地页承接可能错位。",
                "action": "先停低质素材或换首屏卖点；检查商品页加载、价格、CTA 与事件回传。",
            })
        if purchase >= 2 and roas >= target_roas * 1.2 and freq < fatigue_frequency:
            findings.append({
                "level": "opportunity", "category": "放量候选", "entity": "ad", "name": label, "entity_id": entity_id,
                "reason": f"purchase={purchase:.0f}, ROAS={roas:.2f} ≥ 目标×1.2，frequency={freq:.2f}。",
                "action": "预算逐日 +20%~30%；同步复制测试新素材，避免单素材疲劳。",
            })
        if purchase >= 1 and spend >= min_spend_to_diagnose and roas > 0 and roas < target_roas:
            findings.append({
                "level": "warning", "category": "低ROAS观察", "entity": "ad", "name": label, "entity_id": entity_id,
                "reason": f"ROAS={roas:.2f} < 目标 ROAS {target_roas:.2f}，但已有转化。",
                "action": "先观察同组内更优广告；若连续 2 天低于目标，降预算或暂停。",
            })
        if freq >= fatigue_frequency and ctr < 1.5 and spend >= min_spend_to_diagnose:
            findings.append({
                "level": "warning", "category": "素材疲劳/低点击", "entity": "ad", "name": label, "entity_id": entity_id,
                "reason": f"frequency={freq:.2f} 且 CTR={ctr:.2f}%。",
                "action": "换开头 3 秒、主图/标题；同受众下用新素材接量。",
            })
    return findings


def markdown_report(path: Path, accounts: List[Dict[str, Any]], effective_presets: Dict[str, str], rows_by_account: Dict[str, Dict[str, List[Dict[str, Any]]]], findings: List[Dict[str, Any]], args: argparse.Namespace, decision_config_path: Optional[str], max_items_per_level: int = 0) -> None:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    limit_label = "全量" if max_items_per_level <= 0 else f"每组前 {max_items_per_level} 条"
    lines = [
        f"# Facebook 广告拉数诊断报告",
        "",
        f"生成时间：{now}",
        f"API：{args.api_version}",
        f"时间范围：{args.since + ' ~ ' + args.until if args.since and args.until else args.date_preset}",
        f"自动回溯：{'开启' if args.auto_backfill else '关闭'}",
        f"明细展示：{limit_label}",
        f"目标配置：{decision_config_path or '未使用'}",
        "",
        "## 1. 结论",
    ]
    by_level = {"critical": [], "warning": [], "opportunity": [], "info": []}
    for f in findings:
        by_level.setdefault(f.get("level", "warning"), []).append(f)
    if not findings:
        lines.append("- 未发现明确关停/放量/学习受限信号。")
    else:
        lines.append(f"- 🔴 严重：{len(by_level.get('critical', []))} 项")
        lines.append(f"- 🟡 警告：{len(by_level.get('warning', []))} 项")
        lines.append(f"- 🟢 机会：{len(by_level.get('opportunity', []))} 项")
        lines.append(f"- ⚪ 信息：{len(by_level.get('info', []))} 项")
    lines += ["", "## 2. 账户汇总", "", "| 账户 | 使用范围 | 花费 | 展示 | 点击 | 购买 | ROAS |", "|---|---:|---:|---:|---:|---:|---:|"]
    for acc in accounts:
        account_rows = rows_by_account.get(acc["id"], {}).get("account", [])
        row = account_rows[0] if account_rows else {}
        lines.append(
            f"| {acc.get('name', acc['id'])} ({acc['id']}) | {effective_presets.get(acc['id'], '')} | "
            f"{num(row.get('spend')):.2f} | {as_int(row.get('impressions'))} | {as_int(row.get('clicks'))} | "
            f"{num(row.get('purchase')):.0f} | {num(row.get('roas')):.2f} |"
        )
    lines += ["", "## 3. 问题定位与建议"]
    icon = {"critical": "🔴", "warning": "🟡", "opportunity": "🟢", "info": "⚪"}
    for level in ["critical", "warning", "opportunity", "info"]:
        items = by_level.get(level, [])
        if not items:
            continue
        lines.append(f"\n### {icon[level]} {level}（{len(items)}）")
        display_items = items if max_items_per_level <= 0 else items[:max_items_per_level]
        for f in display_items:
            entity_id = f.get("entity_id")
            suffix = f" `{entity_id}`" if entity_id else ""
            lines.append(f"- **[{f['category']}] {f['name']}{suffix}**：{f['reason']} 建议：{f['action']}")
        if max_items_per_level > 0 and len(items) > max_items_per_level:
            lines.append(f"- ... 还有 {len(items) - max_items_per_level} 条未展示，完整明细见 `findings.csv`")
    lines += ["", "## 4. 输出文件", "", f"- CSV/JSON 目录：`{path.parent}`"]
    path.write_text("\n".join(lines), encoding="utf-8")


def build_finding_rows(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{
        "account_id": f.get("account_id", ""),
        "account_name": f.get("account_name", ""),
        "level": f.get("level", ""),
        "entity": f.get("entity", ""),
        "category": f.get("category", ""),
        "name": f.get("name", ""),
        "entity_id": f.get("entity_id", ""),
        "reason": f.get("reason", ""),
        "action": f.get("action", ""),
    } for f in findings]


def build_account_summary_rows(accounts: List[Dict[str, Any]], effective_presets: Dict[str, str], rows_by_account: Dict[str, Dict[str, List[Dict[str, Any]]]], findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts_by_account: Dict[str, Counter] = {}
    for finding in findings:
        account_id = str(finding.get("account_id", ""))
        counts_by_account.setdefault(account_id, Counter())[str(finding.get("level", "warning"))] += 1

    rows: List[Dict[str, Any]] = []
    for account in accounts:
        account_rows = rows_by_account.get(account["id"], {}).get("account", [])
        row = account_rows[0] if account_rows else {}
        counts = counts_by_account.get(account["id"], Counter())
        rows.append({
            "account_id": account.get("id", ""),
            "account_name": account.get("name", ""),
            "preset": effective_presets.get(account.get("id", ""), ""),
            "spend": f"{num(row.get('spend')):.2f}",
            "impressions": as_int(row.get("impressions")),
            "clicks": as_int(row.get("clicks")),
            "purchase": f"{num(row.get('purchase')):.0f}",
            "roas": f"{num(row.get('roas')):.2f}",
            "critical": counts.get("critical", 0),
            "warning": counts.get("warning", 0),
            "opportunity": counts.get("opportunity", 0),
            "info": counts.get("info", 0),
        })
    return rows


def run_mock(args: argparse.Namespace) -> None:
    mock_account = {"id": "act_mock", "name": "mock-account"}
    settings = {
        "target_cpa": num(getattr(args, "target_cpa", DEFAULT_TARGET_CPA)),
        "target_roas": num(getattr(args, "target_roas", DEFAULT_TARGET_ROAS)),
        "min_spend_to_diagnose": num(getattr(args, "min_spend_to_diagnose", DEFAULT_MIN_SPEND_TO_DIAGNOSE)),
        "min_link_clicks_to_diagnose": num(getattr(args, "min_link_clicks_to_diagnose", DEFAULT_MIN_LINK_CLICKS_TO_DIAGNOSE)),
        "fatigue_frequency": num(getattr(args, "fatigue_frequency", DEFAULT_FATIGUE_FREQUENCY)),
    }
    rows_by_level = {
        "account": [enrich_row({"spend": "120", "impressions": "10000", "clicks": "300", "actions": [{"action_type": "omni_purchase", "value": "2"}], "action_values": [{"action_type": "omni_purchase", "value": "360"}]}, mock_account, "account", {})],
        "ad": [
            enrich_row({"ad_id": "ad1", "ad_name": "good-ad", "spend": "60", "impressions": "5000", "clicks": "180", "inline_link_clicks": "120", "frequency": "1.8", "ctr": "3.6", "actions": [{"action_type": "omni_purchase", "value": "2"}], "action_values": [{"action_type": "omni_purchase", "value": "360"}]}, mock_account, "ad", {}),
            enrich_row({"ad_id": "ad2", "ad_name": "bad-click-no-atc", "spend": "25", "impressions": "3000", "clicks": "90", "inline_link_clicks": "35", "frequency": "1.4", "ctr": "3.0", "actions": []}, mock_account, "ad", {}),
        ],
        "adset": [],
    }
    findings = diagnose(rows_by_level, mock_account, settings)
    print(json.dumps({"mock_ok": True, "findings": findings}, ensure_ascii=False, indent=2))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Pull Meta ads insights and generate ecommerce diagnosis.")
    parser.add_argument("--token-path", help="Path to file containing access token")
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    parser.add_argument("--accounts", default="", help="Comma-separated ad account IDs. Empty = /me/adaccounts")
    parser.add_argument("--date-preset", default="last_7d", help="today/yesterday/last_7d/last_30d/last_90d/maximum")
    parser.add_argument("--since", help="YYYY-MM-DD; requires --until")
    parser.add_argument("--until", help="YYYY-MM-DD; requires --since")
    parser.add_argument("--levels", default="account,campaign,adset,ad")
    parser.add_argument("--time-increment", default="all_days")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output-dir", default="reports/fb_pull_report")
    parser.add_argument("--report-item-limit", type=int, default=0, help="Markdown findings shown per level. 0 = show all.")
    parser.add_argument("--target-cpa", type=float, default=DEFAULT_TARGET_CPA)
    parser.add_argument("--target-roas", type=float, default=DEFAULT_TARGET_ROAS)
    parser.add_argument("--min-spend-to-diagnose", type=float, default=DEFAULT_MIN_SPEND_TO_DIAGNOSE)
    parser.add_argument("--min-link-clicks-to-diagnose", type=float, default=DEFAULT_MIN_LINK_CLICKS_TO_DIAGNOSE)
    parser.add_argument("--fatigue-frequency", type=float, default=DEFAULT_FATIGUE_FREQUENCY)
    parser.add_argument("--decision-config", help="Optional JSON config with defaults/accounts overrides for targets")
    parser.add_argument("--auto-backfill", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--mock", action="store_true", help="Run local mock self-test without API/token")
    args = parser.parse_args(argv)

    if args.mock:
        run_mock(args)
        return 0
    if bool(args.since) != bool(args.until):
        parser.error("--since and --until must be provided together")
    if not args.token_path:
        parser.error("--token-path is required unless --mock is used")
    token_path = Path(args.token_path)
    if not token_path.exists():
        raise SystemExit(f"Token file not found: {token_path}")
    token = token_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not token:
        raise SystemExit(f"Token file is empty: {token_path}")

    client = MetaClient(token, args.api_version)
    decision_config = load_decision_config(Path(args.decision_config)) if args.decision_config else load_decision_config(None)
    account_ids = [x.strip() for x in args.accounts.split(",") if x.strip()]
    levels = [x.strip() for x in args.levels.split(",") if x.strip()]
    bad_levels = [x for x in levels if x not in LEVEL_FIELDS]
    if bad_levels:
        parser.error(f"Unsupported levels: {bad_levels}")

    out_root = Path(args.output_dir) / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root.mkdir(parents=True, exist_ok=True)

    accounts = get_accounts(client, account_ids)
    rows_by_account: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    effective_presets: Dict[str, str] = {}
    all_findings: List[Dict[str, Any]] = []
    resolved_settings: Dict[str, Dict[str, float]] = {}

    for account in accounts:
        acc_id = account["id"]
        effective_preset, _, _ = find_effective_preset(client, acc_id, args)
        effective_presets[acc_id] = effective_preset
        settings = resolve_settings(args, account, decision_config)
        resolved_settings[acc_id] = settings
        rows_by_level: Dict[str, List[Dict[str, Any]]] = {}
        acc_dir = out_root / acc_id
        for level in levels:
            rows = fetch_insights(client, account, level, args, effective_preset)
            rows_by_level[level] = rows
            write_json(acc_dir / f"{level}.json", rows)
            write_csv(acc_dir / f"{level}.csv", rows)
        rows_by_account[acc_id] = rows_by_level
        for finding in diagnose(rows_by_level, account, settings):
            finding["account_id"] = acc_id
            finding["account_name"] = account.get("name", "")
            all_findings.append(finding)

    summary = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "api_version": args.api_version,
        "token_path": str(token_path),
        "decision_config": args.decision_config or "",
        "accounts": accounts,
        "effective_presets": effective_presets,
        "resolved_settings": resolved_settings,
        "findings": all_findings,
    }
    write_json(out_root / "summary.json", summary)
    write_csv_with_columns(out_root / "findings.csv", build_finding_rows(all_findings), REPORT_FINDING_COLUMNS)
    write_csv_with_columns(out_root / "account_summary.csv", build_account_summary_rows(accounts, effective_presets, rows_by_account, all_findings), REPORT_ACCOUNT_COLUMNS)
    markdown_report(out_root / "diagnosis.md", accounts, effective_presets, rows_by_account, all_findings, args, args.decision_config, args.report_item_limit)
    print(json.dumps({"ok": True, "accounts": len(accounts), "out_dir": str(out_root), "findings": len(all_findings)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
