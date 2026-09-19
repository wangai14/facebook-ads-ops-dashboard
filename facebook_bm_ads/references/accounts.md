# 广告账户 (Ad Accounts) 查询指南

## 1. 获取 BM 下的所有广告账户

### 自有广告账户

```python
import requests

BM_ID = "你的BM_ID"
TOKEN = "你的Access_Token"

url = f"https://graph.facebook.com/v22.0/{BM_ID}/owned_ad_accounts"
params = {
    "access_token": TOKEN,
    "fields": "id,name,account_status,currency,timezone_name,amount_spent,balance,spend_cap,business",
    "limit": 200
}

all_accounts = []
while url:
    response = requests.get(url, params=params).json()
    all_accounts.extend(response.get("data", []))
    url = response.get("paging", {}).get("next")
    params = {}

print(f"共找到 {len(all_accounts)} 个广告账户")
for acc in all_accounts:
    print(f"ID: {acc['id']}, 名称: {acc['name']}, 状态: {acc['account_status']}")
```

### 客户广告账户（代理商模式）

```python
# 获取 BM 管理的客户账户
url = f"https://graph.facebook.com/v22.0/{BM_ID}/client_ad_accounts"
params = {
    "access_token": TOKEN,
    "fields": "id,name,account_status,currency,business",
    "limit": 200
}
response = requests.get(url, params=params).json()
print(response)
```

---

## 2. 账户状态码含义

| 状态码 | 含义 |
|---|---|
| `1` | 正常 (ACTIVE) |
| `2` | 已禁用 (DISABLED) |
| `3` | 未验证 (UNSETTLED) |
| `7` | 待审核 (PENDING_REVIEW) |
| `8` | E1法规限制 (IN_GRACE_PERIOD) |
| `9` | 超出花费上限 (PENDING_CLOSURE) |
| `100` | 已关闭 (CLOSED) |
| `101` | 任意合作伙伴 (ANY) |
| `201` | 已停用 (CLOSED) |

```python
ACCOUNT_STATUS = {
    1: "正常",
    2: "已禁用",
    3: "未验证",
    7: "待审核",
    9: "超出花费上限",
    100: "已关闭",
}
```

---

## 3. 查询单个广告账户详情

```python
AD_ACCOUNT_ID = "act_123456789"  # 注意：必须带 act_ 前缀

url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}"
params = {
    "access_token": TOKEN,
    "fields": ",".join([
        "id", "name", "account_status", "currency", "timezone_name",
        "timezone_offset_hours_utc", "amount_spent", "balance",
        "spend_cap", "daily_spend_limit", "age", "created_time",
        "business", "owner", "funding_source_details", "disable_reason"
    ])
}
response = requests.get(url, params=params).json()
print(response)
```

---

## 4. 获取账户的花费限额与余额

```python
url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}"
params = {
    "access_token": TOKEN,
    "fields": "amount_spent,balance,spend_cap,daily_spend_limit"
}
data = requests.get(url, params=params).json()

# amount_spent 单位是分 (cent)，需要除以 100
print(f"累计花费: {int(data['amount_spent']) / 100:.2f}")
print(f"账户余额: {int(data.get('balance', 0)) / 100:.2f}")
print(f"花费上限: {int(data.get('spend_cap', 0)) / 100:.2f}")
```

---

## 5. 获取账户下的用户列表

```python
url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/users"
params = {
    "access_token": TOKEN,
    "fields": "id,name,email,role"
}
response = requests.get(url, params=params).json()
print(response)
```

---

## 6. 多账户并发查询（使用 Batch API）

当需要同时查询多个账户时，使用批量请求效率更高：

```python
import json

accounts = ["act_111", "act_222", "act_333"]
batch = []
for acc_id in accounts:
    batch.append({
        "method": "GET",
        "relative_url": f"{acc_id}?fields=id,name,amount_spent,account_status"
    })

url = "https://graph.facebook.com/v22.0/"
response = requests.post(url, data={
    "access_token": TOKEN,
    "batch": json.dumps(batch)
}).json()

for item in response:
    if item["code"] == 200:
        body = json.loads(item["body"])
        print(body)
```

---

## 7. 账户字段速查表

| 字段 | 说明 | 类型 |
|---|---|---|
| `id` | 账户ID (带 act_ 前缀) | string |
| `name` | 账户名称 | string |
| `account_status` | 账户状态 | int |
| `currency` | 货币代码 (如 USD, CNY) | string |
| `timezone_name` | 时区 (如 Asia/Shanghai) | string |
| `timezone_offset_hours_utc` | UTC偏移小时数 | int |
| `amount_spent` | 全部时间累计花费(分) | string |
| `balance` | 账户余额(分) | string |
| `spend_cap` | 花费上限(分) | string |
| `daily_spend_limit` | 日花费上限(分) | string |
| `business` | 所属BM信息 | object |
| `created_time` | 创建时间 | string |
| `disable_reason` | 禁用原因 | int |
| `funding_source_details` | 付款方式信息 | object |
