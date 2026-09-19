# 自定义受众 & 像素数据查询指南

## 1. 自定义受众 (Custom Audiences)

### 获取所有自定义受众

```python
import requests

TOKEN = "你的Access_Token"
AD_ACCOUNT_ID = "act_123456789"

url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/customaudiences"
params = {
    "access_token": TOKEN,
    "fields": "id,name,description,subtype,approximate_count_lower_bound,approximate_count_upper_bound,data_source,is_value_based,lookalike_spec,retention_days,rule,time_created,time_updated",
    "limit": 100
}
response = requests.get(url, params=params).json()
audiences = response.get("data", [])
print(f"自定义受众数量: {len(audiences)}")
for aud in audiences:
    print(f"  [{aud['subtype']}] {aud['name']} - 估计人数: {aud.get('approximate_count_lower_bound', '未知')}")
```

### 受众类型 (subtype) 说明

| subtype | 含义 |
|---|---|
| `CUSTOM` | 客户名单上传 |
| `WEBSITE` | 网站访客受众（需要像素） |
| `APP` | 应用活动受众 |
| `ENGAGEMENT` | 互动受众（主页/视频/表单） |
| `LOOKALIKE` | 类似受众 |
| `SAVED_AUDIENCE` | 保存的受众 |
| `OFFLINE` | 离线转化受众 |
| `CONTACT_ON_SOCIAL` | 社交联系人 |

---

## 2. 查询特定受众详情

```python
AUDIENCE_ID = "你的受众ID"

url = f"https://graph.facebook.com/v22.0/{AUDIENCE_ID}"
params = {
    "access_token": TOKEN,
    "fields": "id,name,subtype,approximate_count_lower_bound,data_source,rule,lookalike_spec,retention_days,excluded_custom_audiences,inclusions,exclusions"
}
response = requests.get(url, params=params).json()
print(response)

# 对于 WEBSITE 类型，rule 字段包含触发条件
if response.get("subtype") == "WEBSITE":
    print("规则:", response.get("rule"))

# 对于 LOOKALIKE 类型
if response.get("subtype") == "LOOKALIKE":
    spec = response.get("lookalike_spec", {})
    print(f"相似度: {spec.get('ratio')}, 国家: {spec.get('country')}, 种子受众: {spec.get('origin')}")
```

---

## 3. 获取受众使用的广告组

```python
url = f"https://graph.facebook.com/v22.0/{AUDIENCE_ID}/adsets"
params = {
    "access_token": TOKEN,
    "fields": "id,name,status,campaign{name}"
}
response = requests.get(url, params=params).json()
print("使用此受众的广告组:", response.get("data", []))
```

---

## 4. 像素 (Facebook Pixel)

### 获取账户下的像素列表

```python
url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/adspixels"
params = {
    "access_token": TOKEN,
    "fields": "id,name,code,owner_business,is_unavailable,last_fired_time,creation_time",
    "limit": 50
}
response = requests.get(url, params=params).json()
pixels = response.get("data", [])
for pixel in pixels:
    print(f"像素ID: {pixel['id']}, 名称: {pixel['name']}, 最后触发: {pixel.get('last_fired_time')}")
```

### 获取像素的事件统计

```python
PIXEL_ID = "你的像素ID"

url = f"https://graph.facebook.com/v22.0/{PIXEL_ID}/stats"
params = {
    "access_token": TOKEN,
    "start_time": 1700000000,  # Unix 时间戳
    "end_time": 1710000000,
    "aggregation": "event"    # 按事件类型聚合
}
response = requests.get(url, params=params).json()

# aggregation 可选：
# event       按事件类型
# device_os   按设备系统
# browser     按浏览器
# event_source_id  按来源
```

### 获取像素触发的标准事件

常见像素事件：

| 事件名 | 含义 |
|---|---|
| `PageView` | 页面浏览 |
| `ViewContent` | 查看商品 |
| `AddToCart` | 加入购物车 |
| `InitiateCheckout` | 发起结账 |
| `Purchase` | 购买 |
| `Lead` | 潜在客户 |
| `CompleteRegistration` | 完成注册 |
| `Search` | 搜索 |
| `AddPaymentInfo` | 添加支付信息 |
| `AddToWishlist` | 加入收藏 |

---

## 5. BM 下所有像素

```python
BM_ID = "你的BM_ID"

url = f"https://graph.facebook.com/v22.0/{BM_ID}/owned_pixels"
params = {
    "access_token": TOKEN,
    "fields": "id,name,owner_business,last_fired_time,is_unavailable",
    "limit": 100
}
response = requests.get(url, params=params).json()
print(response)
```

---

## 6. 基于像素创建网站受众

```python
import json

PIXEL_ID = "你的像素ID"

url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/customaudiences"
data = {
    "access_token": TOKEN,
    "name": "网站访客 - 近30天",
    "subtype": "WEBSITE",
    "retention_days": 30,
    "rule": json.dumps({
        "inclusions": {
            "operator": "or",
            "rules": [{
                "event_sources": [{"id": PIXEL_ID, "type": "pixel"}],
                "retention_seconds": 2592000,  # 30天
                "filter": {
                    "operator": "and",
                    "filters": [{
                        "field": "event",
                        "operator": "=",
                        "value": "PageView"
                    }]
                }
            }]
        }
    })
}
response = requests.post(url, data=data).json()
print("创建受众结果:", response)
```

---

## 7. 类似受众 (Lookalike Audience)

```python
# 基于现有受众创建类似受众
data = {
    "access_token": TOKEN,
    "name": "1% 类似受众 - 美国",
    "subtype": "LOOKALIKE",
    "origin_audience_id": "种子受众ID",
    "lookalike_spec": json.dumps({
        "ratio": 0.01,          # 1% 相似度 (0.01 ~ 0.20)
        "country": "US",        # 目标国家
        "type": "similarity"    # similarity / reach
    })
}
response = requests.post(
    f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/customaudiences",
    data=data
).json()
print(response)
```
