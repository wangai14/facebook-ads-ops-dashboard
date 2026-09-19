# 完整代码示例

## 示例 1：Python — 拉取 BM 下所有账户的昨日数据

```python
#!/usr/bin/env python3
"""
Facebook BM 广告数据拉取完整示例
功能：获取 BM 下所有广告账户昨日的 Campaign 级别投放数据，并保存为 CSV
"""

import os
import json
import time
import random
import requests
import csv
from datetime import datetime, timedelta

# ====== 配置 ======
BM_ID = os.environ.get("FB_BM_ID", "你的BM_ID")
TOKEN = os.environ.get("FB_ACCESS_TOKEN", "你的Token")
BASE_URL = "https://graph.facebook.com/v22.0"

# ====== 工具函数 ======

def api_get(endpoint, params, max_retries=5):
    """GET 请求，含指数退避重试"""
    url = f"{BASE_URL}/{endpoint}"
    params["access_token"] = TOKEN
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            
            if "error" in data:
                error = data["error"]
                code = error.get("code")
                if code in [4, 17, 32, 613]:
                    wait = min(300, (2 ** attempt) * 5 + random.uniform(0, 2))
                    print(f"  限速，等待 {wait:.0f}s...")
                    time.sleep(wait)
                    continue
                raise Exception(f"API error {code}: {error.get('message')}")
            
            return data
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise e
    
    raise Exception("超过最大重试次数")


def paginate(endpoint, params):
    """自动分页，返回所有数据"""
    results = []
    url = f"{BASE_URL}/{endpoint}"
    current_params = params.copy()
    current_params["access_token"] = TOKEN
    
    while url:
        response = requests.get(url, params=current_params, timeout=30).json()
        if "error" in response:
            raise Exception(f"API error: {response['error']}")
        results.extend(response.get("data", []))
        url = response.get("paging", {}).get("next")
        current_params = {}  # next URL 已含所有参数
    
    return results


# ====== 主逻辑 ======

def get_bm_accounts():
    """获取 BM 下所有广告账户"""
    print(f"正在获取 BM {BM_ID} 下的广告账户...")
    accounts = paginate(f"{BM_ID}/owned_ad_accounts", {
        "fields": "id,name,account_status,currency",
        "limit": 200
    })
    active = [a for a in accounts if a.get("account_status") == 1]
    print(f"  共 {len(accounts)} 个账户，{len(active)} 个正常")
    return active


def get_campaign_insights(acc_id, date_since, date_until):
    """获取单账户广告系列投放数据（同步模式）"""
    data = api_get(f"{acc_id}/insights", {
        "fields": ",".join([
            "campaign_id", "campaign_name",
            "spend", "impressions", "clicks", "reach",
            "ctr", "cpc", "cpm",
            "actions", "conversions"
        ]),
        "time_range": json.dumps({"since": date_since, "until": date_until}),
        "level": "campaign",
        "time_increment": "all_days",
        "limit": 500
    })
    return data.get("data", [])


def extract_action_value(actions, action_type):
    """从 actions 数组中提取指定类型的值"""
    if not isinstance(actions, list):
        return 0
    for action in actions:
        if action.get("action_type") == action_type:
            return float(action.get("value", 0))
    return 0


def main():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"\n=== Facebook BM 广告数据报表 [{yesterday}] ===\n")
    
    accounts = get_bm_accounts()
    all_rows = []
    
    for acc in accounts:
        acc_id = acc["id"]
        acc_name = acc["name"]
        print(f"正在拉取账户: {acc_name} ({acc_id})")
        
        try:
            campaigns = get_campaign_insights(acc_id, yesterday, yesterday)
            for c in campaigns:
                row = {
                    "account_id": acc_id,
                    "account_name": acc_name,
                    "campaign_id": c.get("campaign_id"),
                    "campaign_name": c.get("campaign_name"),
                    "date": yesterday,
                    "spend": float(c.get("spend", 0)),
                    "impressions": int(c.get("impressions", 0)),
                    "clicks": int(c.get("clicks", 0)),
                    "reach": int(c.get("reach", 0)),
                    "ctr": float(c.get("ctr", 0)),
                    "cpc": float(c.get("cpc", 0)),
                    "cpm": float(c.get("cpm", 0)),
                    "purchases": extract_action_value(c.get("actions"), "purchase"),
                    "leads": extract_action_value(c.get("actions"), "lead"),
                }
                all_rows.append(row)
            print(f"  ✓ {len(campaigns)} 个广告系列")
        except Exception as e:
            print(f"  ✗ 失败: {e}")
        
        time.sleep(0.5)  # 避免触发限速
    
    # 保存 CSV
    if all_rows:
        output_file = f"fb_report_{yesterday}.csv"
        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\n✅ 报表已保存: {output_file} ({len(all_rows)} 条数据)")
    else:
        print("\n⚠️ 没有数据可导出")


if __name__ == "__main__":
    main()
```

---

## 示例 2：JavaScript — 使用 Fetch API 查询 Insights

```javascript
/**
 * Facebook Marketing API - Node.js 示例
 * 功能：获取指定广告账户的广告系列数据
 */

const TOKEN = process.env.FB_ACCESS_TOKEN;
const AD_ACCOUNT_ID = process.env.FB_AD_ACCOUNT_ID; // "act_123456789"
const API_VERSION = "v22.0";
const BASE_URL = `https://graph.facebook.com/${API_VERSION}`;

/**
 * 通用 API GET 请求
 */
async function apiGet(endpoint, params = {}) {
  const url = new URL(`${BASE_URL}/${endpoint}`);
  url.searchParams.set("access_token", TOKEN);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));

  const response = await fetch(url.toString());
  const data = await response.json();

  if (data.error) {
    throw new Error(`API Error ${data.error.code}: ${data.error.message}`);
  }
  return data;
}

/**
 * 自动分页获取所有数据
 */
async function paginate(endpoint, params = {}) {
  const results = [];
  let nextUrl = null;

  do {
    const url = nextUrl || `${BASE_URL}/${endpoint}`;
    const fullUrl = nextUrl
      ? nextUrl
      : (() => {
          const u = new URL(url);
          u.searchParams.set("access_token", TOKEN);
          Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, v));
          return u.toString();
        })();

    const response = await fetch(fullUrl);
    const data = await response.json();

    if (data.error) throw new Error(`API Error: ${JSON.stringify(data.error)}`);

    results.push(...(data.data || []));
    nextUrl = data.paging?.next || null;
  } while (nextUrl);

  return results;
}

/**
 * 主函数
 */
async function main() {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const dateStr = yesterday.toISOString().split("T")[0];

  console.log(`\n获取 ${dateStr} 的广告数据...\n`);

  // 获取所有广告系列 + Insights
  const campaigns = await paginate(`${AD_ACCOUNT_ID}/campaigns`, {
    fields: [
      "id",
      "name",
      "status",
      "objective",
      `insights.date_preset(yesterday){spend,impressions,clicks,ctr,cpc,conversions}`,
    ].join(","),
    effective_status: JSON.stringify(["ACTIVE", "PAUSED"]),
    limit: "100",
  });

  // 汇总数据
  let totalSpend = 0;
  let totalImpressions = 0;
  let totalClicks = 0;

  for (const campaign of campaigns) {
    const ins = campaign.insights?.data?.[0] || {};
    const spend = parseFloat(ins.spend || 0);
    totalSpend += spend;
    totalImpressions += parseInt(ins.impressions || 0);
    totalClicks += parseInt(ins.clicks || 0);

    console.log(`📊 ${campaign.name}`);
    console.log(`   状态: ${campaign.status} | 目标: ${campaign.objective}`);
    console.log(
      `   花费: $${spend.toFixed(2)} | 展示: ${ins.impressions || 0} | CTR: ${ins.ctr || 0}%`
    );
  }

  console.log("\n=== 汇总 ===");
  console.log(`总花费: $${totalSpend.toFixed(2)}`);
  console.log(`总展示: ${totalImpressions.toLocaleString()}`);
  console.log(`总点击: ${totalClicks.toLocaleString()}`);
  if (totalImpressions > 0) {
    console.log(
      `综合CTR: ${((totalClicks / totalImpressions) * 100).toFixed(2)}%`
    );
  }
}

main().catch(console.error);
```

---

## 示例 3：cURL — 快速查询命令示例

```bash
#!/bin/bash
# 设置变量
TOKEN="你的Access_Token"
BM_ID="你的BM_ID"
ACC_ID="act_123456789"
VERSION="v22.0"
DATE_SINCE="2024-01-01"
DATE_UNTIL="2024-01-31"

# 1. 获取BM下的广告账户列表
echo "=== BM广告账户列表 ==="
curl -s "https://graph.facebook.com/${VERSION}/${BM_ID}/owned_ad_accounts
  ?access_token=${TOKEN}
  &fields=id,name,account_status,amount_spent
  &limit=100" | python3 -m json.tool

# 2. 获取广告系列
echo "=== 广告系列列表 ==="
curl -s "https://graph.facebook.com/${VERSION}/${ACC_ID}/campaigns
  ?access_token=${TOKEN}
  &fields=id,name,status,objective
  &limit=50" | python3 -m json.tool

# 3. 获取 Campaign 级 Insights
echo "=== Campaign Insights ==="
curl -s "https://graph.facebook.com/${VERSION}/${ACC_ID}/insights
  ?access_token=${TOKEN}
  &fields=campaign_name,spend,impressions,clicks,ctr,cpc,cpm,conversions
  &time_range={\"since\":\"${DATE_SINCE}\",\"until\":\"${DATE_UNTIL}\"}
  &level=campaign
  &time_increment=1
  &limit=100" | python3 -m json.tool

# 4. 调试 Token
echo "=== Token 信息 ==="
APP_ID="你的App_ID"
APP_SECRET="你的App_Secret"
curl -s "https://graph.facebook.com/debug_token
  ?input_token=${TOKEN}
  &access_token=${APP_ID}|${APP_SECRET}" | python3 -m json.tool
```

---

## 示例 4：Python — 多账户聚合报表（适合代理商）

```python
"""
代理商多账户聚合报表
功能：并发拉取多个客户账户的广告数据，生成汇总报表
"""

import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

TOKEN = "System_User_Token"
BM_ID = "你的BM_ID"


def get_all_accounts():
    """获取 BM 下所有正常账户"""
    accounts = []
    url = f"https://graph.facebook.com/v22.0/{BM_ID}/owned_ad_accounts"
    params = {
        "access_token": TOKEN,
        "fields": "id,name,currency,account_status",
        "limit": 200
    }
    while url:
        resp = requests.get(url, params=params).json()
        accounts.extend([a for a in resp.get("data", []) if a.get("account_status") == 1])
        url = resp.get("paging", {}).get("next")
        params = {}
    return accounts


def fetch_account_data(account, date_since, date_until):
    """拉取单账户数据"""
    acc_id = account["id"]
    acc_name = account["name"]
    
    try:
        url = f"https://graph.facebook.com/v22.0/{acc_id}/insights"
        resp = requests.get(url, params={
            "access_token": TOKEN,
            "fields": "spend,impressions,clicks,reach,conversions,purchase_roas",
            "time_range": json.dumps({"since": date_since, "until": date_until}),
            "level": "account",
            "time_increment": "all_days"
        }, timeout=30).json()
        
        if "error" in resp:
            return {"account_id": acc_id, "account_name": acc_name, "error": resp["error"]["message"]}
        
        data = resp.get("data", [{}])[0]
        roas_list = data.get("purchase_roas", [])
        roas = float(roas_list[0]["value"]) if roas_list else 0
        
        return {
            "account_id": acc_id,
            "account_name": acc_name,
            "currency": account.get("currency"),
            "spend": float(data.get("spend", 0)),
            "impressions": int(data.get("impressions", 0)),
            "clicks": int(data.get("clicks", 0)),
            "reach": int(data.get("reach", 0)),
            "conversions": int(data.get("conversions", 0)),
            "roas": roas,
            "error": None
        }
    except Exception as e:
        return {"account_id": acc_id, "account_name": acc_name, "error": str(e)}


def main():
    date_until = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    date_since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    print(f"报表期间：{date_since} ~ {date_until}\n")
    
    accounts = get_all_accounts()
    print(f"共 {len(accounts)} 个账户，开始并发拉取...\n")
    
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_account_data, acc, date_since, date_until): acc
            for acc in accounts
        }
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            if result.get("error"):
                print(f"[{i}/{len(accounts)}] ✗ {result['account_name']}: {result['error']}")
            else:
                print(f"[{i}/{len(accounts)}] ✓ {result['account_name']}: 花费={result['spend']:.2f}")
    
    # 打印汇总
    success = [r for r in results if not r.get("error")]
    total_spend = sum(r["spend"] for r in success)
    total_impressions = sum(r["impressions"] for r in success)
    total_conversions = sum(r["conversions"] for r in success)
    
    print(f"\n========= 汇总 ({len(success)}/{len(results)} 账户成功) =========")
    print(f"总花费:     {total_spend:,.2f}")
    print(f"总展示:     {total_impressions:,}")
    print(f"总转化:     {total_conversions:,}")
    if total_spend > 0:
        print(f"整体 CPA:   {total_spend / max(total_conversions, 1):.2f}")
    
    # 按花费排序
    print("\n--- Top 10 账户（按花费） ---")
    for r in sorted(success, key=lambda x: x["spend"], reverse=True)[:10]:
        print(f"  {r['account_name']}: ${r['spend']:,.2f} | ROAS: {r['roas']:.2f}x")

if __name__ == "__main__":
    main()
```
