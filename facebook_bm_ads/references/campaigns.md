# 广告系列、广告组、广告数据查询指南

## 1. 广告系列 (Campaigns)

### 获取账户下所有广告系列

```python
import requests

TOKEN = "你的Access_Token"
AD_ACCOUNT_ID = "act_123456789"

url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/campaigns"
params = {
    "access_token": TOKEN,
    "fields": "id,name,status,effective_status,objective,daily_budget,lifetime_budget,start_time,stop_time,created_time,updated_time,buying_type",
    "limit": 200
}
response = requests.get(url, params=params).json()
campaigns = response.get("data", [])
print(f"广告系列数量: {len(campaigns)}")
```

### 广告系列状态过滤

```python
params = {
    "access_token": TOKEN,
    "fields": "id,name,status,effective_status",
    "effective_status": '["ACTIVE","PAUSED"]',  # 只返回活跃和暂停的
    "limit": 200
}
# effective_status 可选值：
# ACTIVE / PAUSED / DELETED / ARCHIVED
# PENDING_REVIEW / DISAPPROVED / PREAPPROVED
# PENDING_BILLING_INFO / CAMPAIGN_PAUSED / IN_PROCESS / WITH_ISSUES
```

### 广告系列目标 (Objective) 说明

| Objective | 含义 |
|---|---|
| `OUTCOME_AWARENESS` | 品牌知名度 |
| `OUTCOME_TRAFFIC` | 流量 |
| `OUTCOME_ENGAGEMENT` | 互动 |
| `OUTCOME_LEADS` | 潜在客户 |
| `OUTCOME_APP_PROMOTION` | 应用推广 |
| `OUTCOME_SALES` | 销售/转化 |

---

## 2. 广告组 (AdSets)

### 获取账户下所有广告组

```python
url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/adsets"
params = {
    "access_token": TOKEN,
    "fields": ",".join([
        "id", "name", "status", "effective_status",
        "campaign_id", "campaign",
        "daily_budget", "lifetime_budget",
        "optimization_goal", "billing_event",
        "bid_strategy", "bid_amount",
        "targeting", "start_time", "end_time",
        "attribution_spec", "promoted_object"
    ]),
    "limit": 200
}
response = requests.get(url, params=params).json()
```

### 获取某广告系列下的所有广告组

```python
CAMPAIGN_ID = "你的Campaign_ID"
url = f"https://graph.facebook.com/v22.0/{CAMPAIGN_ID}/adsets"
params = {
    "access_token": TOKEN,
    "fields": "id,name,status,daily_budget,optimization_goal",
    "limit": 100
}
```

### 常用字段说明

| 字段 | 说明 |
|---|---|
| `optimization_goal` | 优化目标（REACH/LINK_CLICKS/CONVERSIONS/...） |
| `billing_event` | 计费事件（IMPRESSIONS/LINK_CLICKS/...） |
| `bid_strategy` | 竞价策略（LOWEST_COST_WITHOUT_CAP/COST_CAP/BID_CAP/...） |
| `bid_amount` | 竞价金额（分） |
| `targeting` | 定向设置（JSON对象，含年龄/地区/兴趣等） |
| `promoted_object` | 推广对象（像素事件/App/主页等） |

### 解析定向信息

```python
adset = response["data"][0]
targeting = adset.get("targeting", {})

print("年龄范围:", targeting.get("age_min"), "~", targeting.get("age_max"))
print("地区:", targeting.get("geo_locations", {}).get("countries", []))
print("兴趣:", [i["name"] for i in targeting.get("interests", [])])
print("自定义受众:", targeting.get("custom_audiences", []))
```

---

## 3. 广告 (Ads)

### 获取账户下所有广告

```python
url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/ads"
params = {
    "access_token": TOKEN,
    "fields": ",".join([
        "id", "name", "status", "effective_status",
        "campaign_id", "adset_id",
        "creative", "creative{id,name,thumbnail_url,effective_object_story_id,body,title,image_url,video_id}",
        "tracking_specs", "conversion_specs",
        "created_time", "updated_time"
    ]),
    "limit": 200
}
response = requests.get(url, params=params).json()
```

### 获取广告素材 (Creative)

```python
CREATIVE_ID = "你的Creative_ID"
url = f"https://graph.facebook.com/v22.0/{CREATIVE_ID}"
params = {
    "access_token": TOKEN,
    "fields": ",".join([
        "id", "name", "title", "body",
        "image_url", "thumbnail_url", "video_id",
        "object_story_spec", "asset_feed_spec",
        "call_to_action_type", "link_url",
        "effective_object_story_id"
    ])
}
creative = requests.get(url, params=params).json()
```

---

## 4. 联合查询：Insights 附带元数据

在 Insights 请求中同时获取广告状态、预算等元数据：

```python
url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/ads"
params = {
    "access_token": TOKEN,
    "fields": "id,name,status,adset{name,daily_budget,optimization_goal},campaign{name,objective},"
              "insights{spend,impressions,clicks,ctr,cpc,conversions}",
    "date_preset": "last_30d",
    "limit": 100
}
response = requests.get(url, params=params).json()

for ad in response.get("data", []):
    insights = ad.get("insights", {}).get("data", [{}])[0]
    campaign = ad.get("campaign", {})
    adset = ad.get("adset", {})
    print(f"广告: {ad['name']}")
    print(f"  系列: {campaign.get('name')} | 目标: {campaign.get('objective')}")
    print(f"  组: {adset.get('name')} | 日预算: {adset.get('daily_budget')}")
    print(f"  花费: {insights.get('spend')} | CTR: {insights.get('ctr')}")
```

---

## 5. 批量状态管理

```python
# 暂停多个广告（需要 ads_management 权限）
ad_ids = ["1111", "2222", "3333"]
batch = []
for ad_id in ad_ids:
    batch.append({
        "method": "POST",
        "relative_url": f"{ad_id}",
        "body": "status=PAUSED"
    })

import json
url = "https://graph.facebook.com/v22.0/"
response = requests.post(url, data={
    "access_token": TOKEN,
    "batch": json.dumps(batch)
})
print(response.json())
```

---

## 6. 各层级查询端点汇总

| 操作 | 端点 |
|---|---|
| 账户下所有系列 | `GET /act_{id}/campaigns` |
| 系列下所有组 | `GET /{campaign_id}/adsets` |
| 账户下所有组 | `GET /act_{id}/adsets` |
| 组下所有广告 | `GET /{adset_id}/ads` |
| 账户下所有广告 | `GET /act_{id}/ads` |
| 广告 Insights | `GET /{ad_id}/insights` |
| 系列 Insights | `GET /{campaign_id}/insights` |
| 组 Insights | `GET /{adset_id}/insights` |
| 账户 Insights | `GET /act_{id}/insights` |
