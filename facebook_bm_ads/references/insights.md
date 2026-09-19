# 广告投放数据 (Insights) 获取指南

## 1. Insights 基础查询

```python
import requests

TOKEN = "你的Access_Token"
AD_ACCOUNT_ID = "act_123456789"

url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/insights"
params = {
    "access_token": TOKEN,
    "fields": "campaign_name,adset_name,ad_name,spend,impressions,clicks,reach,ctr,cpc,cpm",
    "time_range": '{"since":"2024-01-01","until":"2024-01-31"}',
    "level": "ad",          # account / campaign / adset / ad
    "time_increment": 1,    # 按天分组；"monthly"=按月；"all_days"=汇总
    "limit": 500
}
response = requests.get(url, params=params).json()
print(response)
```

---

## 2. 层级 (level) 与时间粒度 (time_increment)

### level 参数

| 值 | 说明 |
|---|---|
| `account` | 账户汇总 |
| `campaign` | 广告系列级 |
| `adset` | 广告组级 |
| `ad` | 广告级（最细，数据量最大） |

### time_increment 参数

| 值 | 说明 |
|---|---|
| `1` | 按天（最常用） |
| `7` | 按周 |
| `monthly` | 按月 |
| `all_days` | 整个时间区间汇总（单行数据） |
| `2`~`90` | 自定义天数 |

---

## 3. 常用指标字段

### 流量与展示

```
impressions           # 展示次数
reach                 # 触达人数（去重）
frequency             # 频率 = 展示/触达
clicks                # 点击次数（所有点击）
unique_clicks         # 独立点击人数
inline_link_clicks    # 链接点击次数
outbound_clicks       # 外部链接点击次数
```

### 成本指标

```
spend                 # 广告花费
cpm                   # 千次展示成本
cpc                   # 每次点击成本
cpp                   # 千人触达成本
ctr                   # 点击率 = clicks/impressions
cost_per_unique_click # 每唯一点击成本
```

### 转化与 ROAS

```
actions                            # 所有行动（JSON数组，推荐作为主入口）
action_values                      # 各行动价值（JSON数组，推荐用于 purchase value）
purchase_roas                      # 购买ROAS（返回JSON数组）
website_purchase_roas              # 网站购买ROAS
conversions                        # 总转化次数（⚠️ 泛字段，不要默认当作购买数）
cost_per_conversion                # 每次转化成本（⚠️ 泛字段，不要默认当作购买CPA）
conversion_values                  # 转化价值（⚠️ 需确认对应转化类型）
```

> 电商报表建议：优先使用 `actions` + `action_values` + `purchase_roas`。
> 不要直接把 `conversions` / `cost_per_conversion` 当成 purchase / CPA。

### 视频指标

```
video_avg_time_watched_actions     # 平均观看时长（JSON数组）
video_thruplay_watched_actions     # ThruPlay次数
video_p25_watched_actions          # 观看25%次数
video_p50_watched_actions          # 观看50%次数
video_p75_watched_actions          # 观看75%次数
video_p95_watched_actions          # 观看95%次数
video_p100_watched_actions         # 完整观看次数
video_play_actions                 # 视频播放次数
```

### 互动指标

```
actions                            # 所有行动数（JSON数组）
post_engagement                    # 帖子互动次数
page_engagement                    # 主页互动次数
post_reactions                     # 表情回应次数
post_comments                      # 评论次数
post_shares                        # 分享次数
```

---

## 4. 使用 action_breakdowns 细分转化

```python
params = {
    "access_token": TOKEN,
    "fields": "actions,conversions,conversion_values",
    "time_range": '{"since":"2024-01-01","until":"2024-01-31"}',
    "level": "campaign",
    "action_breakdowns": "action_type",  # 按转化类型细分
}
response = requests.get(url, params=params).json()

# actions 字段是一个 JSON 数组，需要解析
for campaign in response.get("data", []):
    for action in campaign.get("actions", []):
        print(f"  {action['action_type']}: {action['value']}")
```

常见 action_type：

| action_type | 含义 |
|---|---|
| `omni_purchase` / `purchase` / `web_in_store_purchase` / `onsite_web_purchase` / `onsite_web_app_purchase` / `offsite_conversion.fb_pixel_purchase` / `offsite_conversion.purchase` / `app_custom_event.fb_mobile_purchase` | 购买 |
| `omni_add_to_cart` / `add_to_cart` / `onsite_web_add_to_cart` / `onsite_web_app_add_to_cart` / `offsite_conversion.fb_pixel_add_to_cart` / `offsite_conversion.add_to_cart` / `app_custom_event.fb_mobile_add_to_cart` | 加入购物车 |
| `omni_initiated_checkout` / `initiate_checkout` / `onsite_web_initiate_checkout` / `onsite_web_app_initiate_checkout` / `offsite_conversion.fb_pixel_initiate_checkout` / `offsite_conversion.initiate_checkout` / `app_custom_event.fb_mobile_initiated_checkout` | 发起结账 |
| `omni_add_payment_info` / `add_payment_info` / `onsite_web_add_payment_info` / `onsite_web_app_add_payment_info` / `offsite_conversion.fb_pixel_add_payment_info` / `offsite_conversion.add_payment_info` | 添加支付信息 |
| `view_content` / `omni_view_content` / `onsite_web_view_content` / `offsite_conversion.fb_pixel_view_content` | 浏览内容 |
| `landing_page_view` | 落地页浏览 |
| `link_click` | 链接点击 |
| `post_engagement` | 帖子互动 |

> ⚠️ 注意：这些 action_type 很多可能是**同一事件的不同口径映射**，默认不要把多个 alias 直接累加。
> 推荐做法：按优先级取单一主口径，例如 `omni_purchase` → `purchase` → `web_in_store_purchase` → `onsite_web_purchase`。

---

## 5. 使用 breakdowns 细分投放维度

```python
params = {
    "access_token": TOKEN,
    "fields": "spend,impressions,clicks,reach",
    "time_range": '{"since":"2024-01-01","until":"2024-01-31"}',
    "level": "campaign",
    "breakdowns": "age,gender",     # 按年龄+性别细分
}

# breakdowns 常用选项：
# age               年龄段
# gender            性别
# country           国家
# region            地区
# dma               美国市场区域
# device_platform   设备平台 (mobile / desktop)
# publisher_platform 投放渠道 (facebook / instagram / messenger / audience_network)
# impression_device 展示设备
# placement         版位
# platform_position 版位位置
# product_id        商品ID（DPA广告）
```

> **注意**：`breakdowns` 不能与某些 `level` 组合使用，且会显著增加数据量。

---

## 6. 异步 Insights 查询（大数据量必用）

当查询跨度超过 **7 天 + ad 级别** 时，建议使用异步模式：

```python
import time

# 1. 创建异步任务
url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/insights"
params = {
    "access_token": TOKEN,
    "fields": "campaign_name,adset_name,ad_name,spend,impressions,clicks,ctr,cpc,conversions",
    "time_range": '{"since":"2024-01-01","until":"2024-12-31"}',
    "level": "ad",
    "time_increment": 1,
    "limit": 500,
    "async": True
}
job_response = requests.post(url, params=params).json()
job_id = job_response["report_run_id"]
print(f"任务已创建，Job ID: {job_id}")

# 2. 轮询任务状态
def wait_for_job(job_id, token, max_wait=300):
    start = time.time()
    while time.time() - start < max_wait:
        status_url = f"https://graph.facebook.com/v22.0/{job_id}"
        status = requests.get(status_url, params={"access_token": token}).json()
        pct = status.get("async_percent_completion", 0)
        job_status = status.get("async_status", "")
        print(f"进度: {pct}% - 状态: {job_status}")
        
        if job_status == "Job Completed":
            return True
        elif job_status in ["Job Failed", "Job Skipped"]:
            raise Exception(f"任务失败: {status}")
        time.sleep(10)
    raise Exception("任务超时")

wait_for_job(job_id, TOKEN)

# 3. 分页获取所有结果
all_data = []
result_url = f"https://graph.facebook.com/v22.0/{job_id}/insights"
result_params = {"access_token": TOKEN, "limit": 500}

while result_url:
    response = requests.get(result_url, params=result_params).json()
    all_data.extend(response.get("data", []))
    result_url = response.get("paging", {}).get("next")
    result_params = {}

print(f"共获取 {len(all_data)} 条数据")
```

---

## 7. 预设时间范围

除 `time_range` 外，也可以使用 `date_preset`：

```python
params = {
    "date_preset": "last_30d"   # 预设时间范围
}

# 可用值：
# today / yesterday
# this_week_sun_today / this_week_mon_today
# last_week_sun_sat / last_week_mon_sun
# this_month / last_month
# this_quarter / last_quarter
# last_7d / last_14d / last_28d / last_30d / last_90d
# this_year / last_year
# maximum        # 全部时间（最长37个月）
```

---

## 8. 过滤 (filtering) 参数

```python
import json

# 只查询花费大于0的广告
params = {
    "access_token": TOKEN,
    "fields": "campaign_name,spend,impressions",
    "date_preset": "last_30d",
    "level": "campaign",
    "filtering": json.dumps([
        {"field": "spend", "operator": "GREATER_THAN", "value": "0"}
    ])
}

# 常用 operator：
# EQUAL / NOT_EQUAL
# GREATER_THAN / LESS_THAN
# IN / NOT_IN          (value 为数组)
# CONTAIN / NOT_CONTAIN
# ANY / ALL
```

---

## 9. 电商逐广告报表推荐字段

如果目标是拉“每个广告一行”的电商经营报表，推荐优先请求：

```python
fields = [
    "date_start", "date_stop",
    "campaign_id", "campaign_name",
    "adset_id", "adset_name",
    "ad_id", "ad_name",
    "impressions", "clicks", "reach", "frequency",
    "ctr", "cpc", "cpm", "spend",
    "actions", "action_values", "purchase_roas"
]
```

推荐额外参数：

```python
params.update({
    "level": "ad",
    "action_report_time": "conversion",
    "time_increment": "all_days",
    "use_unified_attribution_setting": "true",
})
```

推荐提取顺序（不要多 alias 累加）：
- purchases: `omni_purchase` → `purchase` → `web_in_store_purchase` → `onsite_web_purchase` → `onsite_web_app_purchase` → `offsite_conversion.fb_pixel_purchase` → `offsite_conversion.purchase` → `app_custom_event.fb_mobile_purchase`
- add_to_cart: `omni_add_to_cart` → `add_to_cart` → `onsite_web_add_to_cart` → `onsite_web_app_add_to_cart` → `offsite_conversion.fb_pixel_add_to_cart` → `offsite_conversion.add_to_cart` → `app_custom_event.fb_mobile_add_to_cart`
- initiate_checkout: `omni_initiated_checkout` → `initiate_checkout` → `onsite_web_initiate_checkout` → `onsite_web_app_initiate_checkout` → `offsite_conversion.fb_pixel_initiate_checkout` → `offsite_conversion.initiate_checkout` → `app_custom_event.fb_mobile_initiated_checkout`
- add_payment_info: `omni_add_payment_info` → `add_payment_info` → `onsite_web_add_payment_info` → `onsite_web_app_add_payment_info` → `offsite_conversion.fb_pixel_add_payment_info` → `offsite_conversion.add_payment_info`

推荐额外拉状态字段，辅助解释“为什么没花 / 为什么学习受限”：

```python
campaign_fields = "id,name,status,effective_status,objective,daily_budget,lifetime_budget"
adset_fields = "id,name,status,effective_status,learning_stage_info,daily_budget,lifetime_budget,bid_strategy,optimization_goal,billing_event"
ad_fields = "id,name,status,effective_status,creative{id,name,thumbnail_url,video_id,image_hash}"
```

## 10. 完整字段参考

### 账号/系列/组/广告 ID 字段

```
account_id / account_name
campaign_id / campaign_name
adset_id / adset_name
ad_id / ad_name
date_start / date_stop
```

### 转化窗口说明

Facebook 默认转化窗口：**点击后7天 + 浏览后1天**

可在请求中指定：

```python
"action_attribution_windows": ["1d_click", "7d_click", "1d_view", "28d_click"]
```
