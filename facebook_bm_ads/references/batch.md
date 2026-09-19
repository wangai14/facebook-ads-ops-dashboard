# 批量请求、分页处理与限速策略

## 1. 分页处理

Facebook API 在数据较多时会自动分页，响应中包含 `paging` 字段。

### 基于游标的分页（Cursor-based）

```python
import requests

def get_all_pages(initial_url, params):
    """通用分页获取函数"""
    all_data = []
    url = initial_url
    
    while url:
        response = requests.get(url, params=params).json()
        
        if "error" in response:
            raise Exception(f"API 错误: {response['error']}")
        
        all_data.extend(response.get("data", []))
        
        # 获取下一页 URL（next 已包含所有参数）
        paging = response.get("paging", {})
        url = paging.get("next")
        params = {}  # 后续请求不需要再传 params（URL 中已包含）
        
        print(f"已获取 {len(all_data)} 条数据...")
    
    return all_data

# 使用示例
TOKEN = "你的Token"
AD_ACCOUNT_ID = "act_123456789"

url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/campaigns"
params = {
    "access_token": TOKEN,
    "fields": "id,name,status",
    "limit": 100  # 每页最多 100 条
}
all_campaigns = get_all_pages(url, params)
```

### 基于偏移的分页（Offset-based，较少用）

```python
offset = 0
batch_size = 100
all_data = []

while True:
    params = {
        "access_token": TOKEN,
        "fields": "id,name",
        "limit": batch_size,
        "offset": offset
    }
    response = requests.get(url, params=params).json()
    data = response.get("data", [])
    if not data:
        break
    all_data.extend(data)
    offset += len(data)
    if len(data) < batch_size:
        break
```

---

## 2. 批量请求 (Batch API)

单次 HTTP 请求最多包含 **50 个子请求**，大幅减少网络往返次数。

```python
import json

# 同时查询多个广告账户的 Insights
accounts = ["act_111", "act_222", "act_333", "act_444"]

batch = []
for acc_id in accounts:
    batch.append({
        "method": "GET",
        "relative_url": (
            f"{acc_id}/insights"
            f"?fields=spend,impressions,clicks,ctr"
            f"&date_preset=last_30d"
            f"&level=account"
        )
    })

url = "https://graph.facebook.com/v22.0/"
response = requests.post(url, data={
    "access_token": TOKEN,
    "batch": json.dumps(batch)
}).json()

# 解析批量结果
for i, item in enumerate(response):
    if item and item["code"] == 200:
        body = json.loads(item["body"])
        data = body.get("data", [{}])[0]
        print(f"账户 {accounts[i]}: 花费={data.get('spend')}, 展示={data.get('impressions')}")
    else:
        print(f"账户 {accounts[i]} 请求失败: {item}")
```

### 批量请求内引用（依赖请求）

```python
# 先创建任务，再用 {result=$.0.id} 引用
batch = [
    {
        "method": "POST",
        "name": "create_job",
        "relative_url": f"act_{ACC_ID}/insights",
        "body": json.dumps({
            "fields": "campaign_name,spend",
            "date_preset": "last_30d",
            "async": True
        })
    },
    {
        "method": "GET",
        "relative_url": "{result=create_job:$.report_run_id}/insights",
        "depends_on": "create_job"  # 等待第一个完成
    }
]
```

---

## 3. API 限速策略

### 限速类型

| 类型 | 说明 | 限制 |
|---|---|---|
| 应用级别 | 每个应用每个账户 | 每小时 200 评分单位 |
| 账户级别 | 每个广告账户 | 动态计算 |
| BM 级别 | Business Manager | 总量限制 |

### 响应头中的限速信息

```python
response = requests.get(url, params=params)

# 检查限速头
x_business_use_case_usage = response.headers.get("x-business-use-case-usage")
x_app_usage = response.headers.get("x-app-usage")
x_ad_account_usage = response.headers.get("x-ad-account-usage")

print("应用使用量:", x_app_usage)
# 示例: {"call_count":5,"total_cputime":2,"total_time":5}
# call_count: 已使用的百分比 (0-100)

if x_app_usage:
    usage = json.loads(x_app_usage)
    if usage.get("call_count", 0) > 80:
        print("警告：API 调用量接近上限！")
```

### 应对限速的策略

```python
import time
import random

def api_request_with_retry(url, params, max_retries=5):
    """带指数退避重试的 API 请求"""
    for attempt in range(max_retries):
        response = requests.get(url, params=params)
        data = response.json()
        
        if "error" not in data:
            return data
        
        error = data["error"]
        error_code = error.get("code")
        
        # 17: 用户请求限速; 4: 应用请求限速; 32: 页面级请求限速
        if error_code in [4, 17, 32, 613]:
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            print(f"触发限速，等待 {wait_time:.1f} 秒后重试... (第{attempt+1}次)")
            time.sleep(wait_time)
            continue
        
        raise Exception(f"API 错误: {error}")
    
    raise Exception("超过最大重试次数")
```

---

## 4. 数据导出到文件

### 导出为 CSV

```python
import csv
import requests

all_data = get_all_pages(url, params)

if all_data:
    with open("facebook_insights.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=all_data[0].keys())
        writer.writeheader()
        writer.writerows(all_data)
    print(f"已导出 {len(all_data)} 条数据到 facebook_insights.csv")
```

### 导出为 JSON

```python
import json

with open("facebook_insights.json", "w", encoding="utf-8") as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)
```

### 导出到 Pandas DataFrame

```python
import pandas as pd

df = pd.DataFrame(all_data)

# 处理数值字段
numeric_cols = ["spend", "impressions", "clicks", "reach"]
df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

# actions 字段展开
def extract_action(actions, action_type):
    if not isinstance(actions, list):
        return 0
    for action in actions:
        if action.get("action_type") == action_type:
            return float(action.get("value", 0))
    return 0

df["purchases"] = df["actions"].apply(lambda x: extract_action(x, "purchase"))
df["leads"] = df["actions"].apply(lambda x: extract_action(x, "lead"))

print(df.head())
df.to_csv("output.csv", index=False, encoding="utf-8-sig")
```

---

## 5. 多账号并发拉取

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_account_insights(acc_id, token, date_preset="last_30d"):
    """拉取单账户洞察数据"""
    url = f"https://graph.facebook.com/v22.0/{acc_id}/insights"
    params = {
        "access_token": token,
        "fields": "spend,impressions,clicks,reach,conversions",
        "date_preset": date_preset,
        "level": "account"
    }
    try:
        response = requests.get(url, params=params).json()
        if "error" in response:
            return acc_id, None, response["error"]
        return acc_id, response.get("data", []), None
    except Exception as e:
        return acc_id, None, str(e)

accounts = ["act_111", "act_222", "act_333", "act_444", "act_555"]

results = {}
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(fetch_account_insights, acc, TOKEN): acc
        for acc in accounts
    }
    for future in as_completed(futures):
        acc_id, data, error = future.result()
        if error:
            print(f"账户 {acc_id} 失败: {error}")
        else:
            results[acc_id] = data

print(f"成功获取 {len(results)} 个账户的数据")
```

---

## 6. 定时任务示例

```python
import schedule
import time

def daily_report():
    """每日数据报表任务"""
    print("开始拉取昨日数据...")
    url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/insights"
    params = {
        "access_token": TOKEN,
        "fields": "campaign_name,spend,impressions,clicks,conversions",
        "date_preset": "yesterday",
        "level": "campaign"
    }
    data = get_all_pages(url, params)
    # 存入数据库或发送报告...
    print(f"完成，共 {len(data)} 条数据")

# 每天早上 8:00 执行
schedule.every().day.at("08:00").do(daily_report)

while True:
    schedule.run_pending()
    time.sleep(60)
```
