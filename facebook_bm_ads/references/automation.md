# 广告自动化与智能规则指南

## 1. 自动化规则 (Automated Rules)

Facebook 支持基于条件触发的自动化规则，可以自动暂停/启动广告、调整预算。

### 创建自动化规则

```python
import requests
import json

TOKEN = "你的Token"
AD_ACCOUNT_ID = "act_123456789"
BASE_URL = "https://graph.facebook.com/v22.0"


def create_automated_rule(name, conditions, actions, evaluation_schedule="DAILY",
                           entity_type="ADSET", apply_to="ACTIVE"):
    """
    创建自动化规则
    
    evaluation_schedule: DAILY / HOURLY / EVERY_30_MIN
    entity_type: CAMPAIGN / ADSET / AD / ALL_ACTIVE_AD_SETS / ALL_ACTIVE_ADS
    apply_to: ACTIVE / ANY
    """
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/adrules_library"
    data = {
        "access_token": TOKEN,
        "name": name,
        "trigger_type": evaluation_schedule,
        "entity_type": entity_type,
        "filters": json.dumps(conditions),   # 触发条件
        "actions": json.dumps(actions),       # 执行动作
        "evaluation_type": apply_to,
        "status": "ENABLED"
    }
    response = requests.post(url, data=data).json()
    if "error" in response:
        raise Exception(f"规则创建失败: {response['error']}")
    print(f"✓ 自动化规则创建成功: {response['id']}")
    return response["id"]


# ====== 常用规则示例 ======

# 规则1：CPA 超标自动暂停广告组
rule_pause_high_cpa = create_automated_rule(
    name="CPA超$50自动暂停",
    evaluation_schedule="DAILY",
    entity_type="ADSET",
    conditions=[
        {
            "field": "cost_per_result",          # 每次结果成本（即CPA）
            "value": 50,
            "operator": "GREATER_THAN",
            "time_preset": "LAST_7_DAYS"         # 基于过去7天数据
        },
        {
            "field": "spend",                    # 需要花够一定金额才判断
            "value": 20,
            "operator": "GREATER_THAN",
            "time_preset": "LAST_7_DAYS"
        }
    ],
    actions=[
        {"type": "PAUSE"}
    ]
)

# 规则2：ROAS 达标自动加预算 20%
rule_increase_budget = create_automated_rule(
    name="ROAS>3自动增预算20%",
    evaluation_schedule="DAILY",
    entity_type="ADSET",
    conditions=[
        {
            "field": "purchase_roas",
            "value": 3,
            "operator": "GREATER_THAN",
            "time_preset": "LAST_7_DAYS"
        }
    ],
    actions=[
        {
            "type": "INCREASE_DAILY_BUDGET",
            "value": 20,                        # 增加 20%
            "currency": "USD"
        }
    ]
)

# 规则3：CTR 过低自动暂停广告
rule_pause_low_ctr = create_automated_rule(
    name="CTR低于0.5%暂停广告",
    evaluation_schedule="DAILY",
    entity_type="AD",
    conditions=[
        {
            "field": "ctr",
            "value": 0.005,                     # 0.5%
            "operator": "LESS_THAN",
            "time_preset": "LAST_3_DAYS"
        },
        {
            "field": "impressions",
            "value": 1000,
            "operator": "GREATER_THAN",
            "time_preset": "LAST_3_DAYS"
        }
    ],
    actions=[
        {"type": "PAUSE"}
    ]
)
```

### 常用条件字段

| field | 说明 | 常用 operator |
|---|---|---|
| `spend` | 花费 | GREATER_THAN / LESS_THAN |
| `impressions` | 展示次数 | GREATER_THAN |
| `ctr` | 点击率 | GREATER_THAN / LESS_THAN |
| `cpc` | 每次点击成本 | GREATER_THAN / LESS_THAN |
| `cpm` | 千次展示成本 | GREATER_THAN / LESS_THAN |
| `cost_per_result` | CPA | GREATER_THAN / LESS_THAN |
| `purchase_roas` | ROAS | GREATER_THAN / LESS_THAN |
| `frequency` | 频率 | GREATER_THAN |
| `reach` | 触达人数 | GREATER_THAN |
| `daily_budget` | 当前日预算 | GREATER_THAN / LESS_THAN |

### 可用动作类型

| action type | 说明 |
|---|---|
| `PAUSE` | 暂停 |
| `UNPAUSE` | 启动 |
| `INCREASE_DAILY_BUDGET` | 增加日预算（%） |
| `DECREASE_DAILY_BUDGET` | 减少日预算（%） |
| `SET_DAILY_BUDGET` | 设置为指定日预算 |
| `INCREASE_BID` | 提高竞价（%） |
| `DECREASE_BID` | 降低竞价（%） |
| `SEND_NOTIFICATION` | 发送通知邮件 |

---

## 2. 预算自动优化脚本

结合 Insights 数据自动调整预算的 Python 脚本：

```python
import time
from datetime import datetime, timedelta


def get_adset_performance(adset_ids, days=7):
    """批量获取广告组过去N天的表现数据"""
    import json
    batch = []
    for adset_id in adset_ids:
        date_since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        date_until = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        batch.append({
            "method": "GET",
            "relative_url": (
                f"{adset_id}/insights"
                f"?fields=adset_id,adset_name,spend,conversions,purchase_roas,cost_per_result,ctr"
                f"&time_range={{\"since\":\"{date_since}\",\"until\":\"{date_until}\"}}"
                f"&time_increment=all_days"
            )
        })
    
    url = f"{BASE_URL}/"
    response = requests.post(url, data={
        "access_token": TOKEN,
        "batch": json.dumps(batch)
    }).json()
    
    results = {}
    for i, item in enumerate(response):
        if item and item["code"] == 200:
            body = json.loads(item["body"])
            data = body.get("data", [{}])
            if data:
                results[adset_ids[i]] = data[0]
    return results


def auto_optimize_budgets(adset_ids, target_roas=3.0, max_budget=500.0):
    """
    基于 ROAS 自动优化广告组预算：
    - ROAS > target * 1.2 → 预算 +30%
    - ROAS > target       → 预算 +15%
    - ROAS < target * 0.5 → 暂停
    - ROAS < target * 0.8 → 预算 -20%
    """
    print(f"\n=== 自动预算优化 (目标ROAS: {target_roas}x) ===")
    performance = get_adset_performance(adset_ids)
    
    for adset_id in adset_ids:
        data = performance.get(adset_id)
        if not data:
            print(f"  {adset_id}: 无数据，跳过")
            continue
        
        spend = float(data.get("spend", 0))
        roas_list = data.get("purchase_roas", [])
        roas = float(roas_list[0]["value"]) if roas_list else 0
        conversions = int(data.get("conversions", 0))
        
        adset_name = data.get("adset_name", adset_id)
        print(f"\n  [{adset_name}] 花费: ${spend:.2f} | ROAS: {roas:.2f}x | 转化: {conversions}")
        
        # 获取当前预算
        current_info = requests.get(f"{BASE_URL}/{adset_id}",
                                    params={"access_token": TOKEN, "fields": "daily_budget,status"}).json()
        current_budget = int(current_info.get("daily_budget", 0)) / 100  # 分→元/美元
        status = current_info.get("status")
        
        if spend < 10:  # 花费太少，数据不够参考
            print(f"    → 花费不足 $10，数据不可靠，跳过")
            continue
        
        if roas < target_roas * 0.5:
            print(f"    → ROAS 过低（{roas:.2f}x），执行暂停")
            requests.post(f"{BASE_URL}/{adset_id}", data={"access_token": TOKEN, "status": "PAUSED"})
        
        elif roas < target_roas * 0.8:
            new_budget = max(10, current_budget * 0.8)
            print(f"    → ROAS 偏低，预算 ${current_budget:.0f} → ${new_budget:.0f} (-20%)")
            requests.post(f"{BASE_URL}/{adset_id}", data={
                "access_token": TOKEN,
                "daily_budget": int(new_budget * 100)
            })
        
        elif roas > target_roas * 1.2:
            new_budget = min(max_budget, current_budget * 1.3)
            print(f"    → ROAS 优秀，预算 ${current_budget:.0f} → ${new_budget:.0f} (+30%)")
            requests.post(f"{BASE_URL}/{adset_id}", data={
                "access_token": TOKEN,
                "daily_budget": int(new_budget * 100)
            })
        
        elif roas > target_roas:
            new_budget = min(max_budget, current_budget * 1.15)
            print(f"    → ROAS 达标，预算 ${current_budget:.0f} → ${new_budget:.0f} (+15%)")
            requests.post(f"{BASE_URL}/{adset_id}", data={
                "access_token": TOKEN,
                "daily_budget": int(new_budget * 100)
            })
        
        else:
            print(f"    → ROAS 正常，维持预算 ${current_budget:.0f}")
        
        time.sleep(0.3)  # 避免限速
```

---

## 3. 广告自动复制 (Duplicate)

```python
def duplicate_campaign(campaign_id, new_name=None, new_status="PAUSED"):
    """复制整个广告系列（含所有广告组和广告）"""
    url = f"{BASE_URL}/{campaign_id}/copies"
    data = {
        "access_token": TOKEN,
        "status_option": "PAUSED",    # PAUSED / ACTIVE / INHERITED_FROM_SOURCE
        "deep_copy": True              # 同时复制广告组和广告
    }
    if new_name:
        data["rename_options"] = json.dumps({"rename_suffix": f" - {new_name}"})
    
    response = requests.post(url, data=data).json()
    if "error" in response:
        raise Exception(f"复制失败: {response['error']}")
    
    new_campaign_id = response.get("copied_campaign_id")
    print(f"✓ 系列复制成功: {new_campaign_id}")
    return new_campaign_id


def duplicate_adset(adset_id, campaign_id=None, new_name=None):
    """复制广告组"""
    url = f"{BASE_URL}/{adset_id}/copies"
    data = {
        "access_token": TOKEN,
        "status_option": "PAUSED",
        "deep_copy": True
    }
    if campaign_id:
        data["campaign_id"] = campaign_id
    
    response = requests.post(url, data=data).json()
    if "error" in response:
        raise Exception(f"广告组复制失败: {response['error']}")
    return response.get("copied_adset_id")
```

---

## 4. A/B 测试自动化

```python
def create_ab_test(base_adset_id, variants):
    """
    基于现有广告组创建 A/B 测试变体
    variants: 变体配置列表，如修改定向或预算
    """
    results = []
    
    # 复制基础广告组
    for i, variant in enumerate(variants):
        new_adset_id = duplicate_adset(base_adset_id)
        
        # 更新变体配置
        update_data = {"access_token": TOKEN}
        if "name" in variant:
            update_data["name"] = variant["name"]
        if "targeting" in variant:
            update_data["targeting"] = json.dumps(variant["targeting"])
        if "daily_budget" in variant:
            update_data["daily_budget"] = int(variant["daily_budget"] * 100)
        
        requests.post(f"{BASE_URL}/{new_adset_id}", data=update_data)
        print(f"✓ A/B变体 {i+1} 创建完成: {new_adset_id}")
        results.append(new_adset_id)
    
    return results


# 示例：测试不同年龄段定向
ab_variants = [
    {
        "name": "AB测试-18~24岁",
        "daily_budget": 50.0,
        "targeting": {"geo_locations": {"countries": ["US"]}, "age_min": 18, "age_max": 24}
    },
    {
        "name": "AB测试-25~34岁",
        "daily_budget": 50.0,
        "targeting": {"geo_locations": {"countries": ["US"]}, "age_min": 25, "age_max": 34}
    },
    {
        "name": "AB测试-35~44岁",
        "daily_budget": 50.0,
        "targeting": {"geo_locations": {"countries": ["US"]}, "age_min": 35, "age_max": 44}
    }
]
# ab_results = create_ab_test("基础广告组ID", ab_variants)
```

---

## 5. 定时投放控制脚本

配合系统定时任务（cron / Windows Task Scheduler）实现按时段投放：

```python
#!/usr/bin/env python3
"""
分时段投放控制
工作时间（8:00~22:00）启动广告，其余时间暂停
"""
from datetime import datetime

def dayparting_control(adset_ids, active_hours=(8, 22), timezone_offset=8):
    """
    adset_ids: 要控制的广告组 ID 列表
    active_hours: (开始小时, 结束小时)，UTC 时间
    """
    now_hour = (datetime.utcnow().hour + timezone_offset) % 24
    should_be_active = active_hours[0] <= now_hour < active_hours[1]
    target_status = "ACTIVE" if should_be_active else "PAUSED"
    
    print(f"当前时间: {now_hour}:00 | 应该: {'投放' if should_be_active else '暂停'}")
    
    for adset_id in adset_ids:
        # 获取当前状态
        current = requests.get(f"{BASE_URL}/{adset_id}",
                               params={"access_token": TOKEN, "fields": "status"}).json()
        current_status = current.get("status")
        
        if current_status != target_status:
            requests.post(f"{BASE_URL}/{adset_id}", data={
                "access_token": TOKEN,
                "status": target_status
            })
            print(f"  {adset_id}: {current_status} → {target_status}")
        else:
            print(f"  {adset_id}: 状态正确，无需更改")
        
        time.sleep(0.2)


# 在系统 cron 中每小时执行一次：
# 0 * * * * python3 /path/to/dayparting.py
if __name__ == "__main__":
    ADSET_IDS = ["广告组ID_1", "广告组ID_2"]
    dayparting_control(ADSET_IDS, active_hours=(9, 23), timezone_offset=8)
```

---

## 6. 获取并管理现有自动化规则

```python
# 获取账户下所有规则
def list_automated_rules():
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/adrules_library"
    response = requests.get(url, params={
        "access_token": TOKEN,
        "fields": "id,name,status,trigger_type,entity_type,filters,actions"
    }).json()
    return response.get("data", [])


# 启用/暂停/删除规则
def update_rule(rule_id, status):
    """status: ENABLED / DISABLED / DELETED"""
    response = requests.post(f"{BASE_URL}/{rule_id}", data={
        "access_token": TOKEN,
        "status": status
    }).json()
    return response


# 手动触发规则立即执行
def trigger_rule(rule_id):
    response = requests.post(f"{BASE_URL}/{rule_id}/execute", data={
        "access_token": TOKEN
    }).json()
    return response
```
