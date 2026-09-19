# 常见错误码与解决方案

## 错误响应格式

```json
{
  "error": {
    "message": "错误描述",
    "type": "OAuthException",
    "code": 190,
    "error_subcode": 463,
    "error_user_title": "用户标题",
    "error_user_msg": "用户详细信息",
    "fbtrace_id": "追踪ID"
  }
}
```

---

## 错误码速查表

### 鉴权 & Token 错误 (code 1xx)

| 错误码 | 子码 | 含义 | 解决方案 |
|---|---|---|---|
| `190` | — | Access Token 无效或已过期 | 重新获取或刷新 Token |
| `190` | `460` | 密码已更改，Token 失效 | 重新授权 |
| `190` | `463` | Token 已过期 | 用长期 Token 或 System User Token |
| `190` | `467` | Token 被撤销 | 重新授权 |
| `190` | `492` | Token 权限不足 | 检查 Token 是否有 `ads_read` 等权限 |
| `100` | — | 参数无效或缺失 | 检查请求参数 |
| `101` | — | App ID 无效 | 确认 App ID |
| `102` | — | 会话 Token 无效 | 使用正确类型的 Token |
| `200`~`299` | — | 权限不足 | 检查 Token 权限范围 |

### 限速错误 (Rate Limit)

| 错误码 | 含义 | 解决方案 |
|---|---|---|
| `4` | 应用调用量超限 | 使用指数退避重试，检查 `x-app-usage` 头 |
| `17` | 用户调用量超限 | 减慢请求速度，等待后重试 |
| `32` | Page 级别限速 | 减少对该 Page 的请求频率 |
| `613` | 自定义限速 | 查看错误详情中的具体限速类型 |

### 权限错误

| 错误码 | 含义 | 解决方案 |
|---|---|---|
| `200` | 权限拒绝，无操作权限 | 确认 Token 有对应权限；System User 需要分配账户权限 |
| `275` | 广告账户无权限 | BM 中给 System User 分配账户访问权 |
| `10` | 权限被拒绝 | 申请必要的 App 权限并通过审核 |

### 数据错误

| 错误码 | 含义 | 解决方案 |
|---|---|---|
| `2` | 服务器内部错误 | 稍后重试 |
| `1` | 未知错误 | 稍后重试，检查 fbtrace_id |
| `368` | 账户或 BM 受到限制 | 检查账户合规状态 |
| `803` | 对象不存在 | 确认 ID 正确 |

---

## 常见问题与解决方案

### 问题 1：Token 过期

**错误示例：**
```json
{"error": {"code": 190, "error_subcode": 463, "message": "Error validating access token: Session has expired"}}
```

**解决方案：**
```python
# 使用 System User Token（永不过期）
# 或在 Token 过期前自动刷新

def refresh_token_if_needed(token, app_id, app_secret):
    """检查 Token 有效性并刷新"""
    url = "https://graph.facebook.com/debug_token"
    params = {
        "input_token": token,
        "access_token": f"{app_id}|{app_secret}"
    }
    info = requests.get(url, params=params).json().get("data", {})
    
    if not info.get("is_valid"):
        # Token 无效，需要重新授权
        raise Exception("Token 已失效，请重新授权")
    
    # 检查是否即将过期（7天内）
    expires_at = info.get("expires_at", 0)
    if expires_at > 0 and expires_at - time.time() < 7 * 86400:
        print("Token 即将在7天内过期，建议更新")
    
    return token
```

---

### 问题 2：权限不足（error code 200 或 275）

**错误示例：**
```json
{"error": {"code": 275, "message": "(#275) Cannot determine the admins of this ad account"}}
```

**解决方案：**
1. 检查 System User 是否被分配了广告账户权限：
   - BM → 设置 → 系统用户 → 点击用户 → "分配资产" → 选择广告账户 → 开启"查看广告表现"
2. 确认 Token 包含 `ads_read` 权限
3. 检查 BM 和广告账户的关联关系

```python
# 调试权限
url = "https://graph.facebook.com/debug_token"
params = {
    "input_token": TOKEN,
    "access_token": f"{APP_ID}|{APP_SECRET}"
}
info = requests.get(url, params=params).json()["data"]
print("权限列表:", info.get("scopes"))
```

---

### 问题 3：触发 API 限速

**错误示例：**
```json
{"error": {"code": 17, "message": "User request limit reached"}}
```

**解决方案：**
```python
import time
import random

def fetch_with_backoff(url, params, max_retries=5):
    for attempt in range(max_retries):
        response = requests.get(url, params=params)
        
        # 检查限速头
        app_usage = response.headers.get("x-app-usage", "{}")
        usage = json.loads(app_usage)
        if usage.get("call_count", 0) > 70:
            print(f"API 使用量 {usage['call_count']}%，主动降速...")
            time.sleep(30)
        
        data = response.json()
        if "error" not in data:
            return data
        
        code = data["error"].get("code")
        if code in [4, 17, 32, 613]:
            wait = min(300, (2 ** attempt) * 10 + random.uniform(0, 5))
            print(f"限速错误，等待 {wait:.0f} 秒...")
            time.sleep(wait)
        else:
            raise Exception(f"不可重试的错误: {data['error']}")
    
    raise Exception("超过最大重试次数")
```

---

### 问题 4：Insights 数据延迟

**现象：** 当天或昨天的数据与广告管理器不一致

**原因：** Facebook Insights 数据有 **30分钟 ~ 3小时** 的延迟

**解决方案：**
```python
# 不要查询当天数据，或明确标注为"预估数据"
# 查询 2 天前的数据更可靠
from datetime import datetime, timedelta

yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

# 推荐使用前天作为"已确认"数据
params = {
    "time_range": f'{{"since":"{two_days_ago}","until":"{two_days_ago}"}}'
}
```

---

### 问题 5：字段在响应中缺失

**现象：** 请求了某个字段，但响应中没有该字段

**原因：**
- 该对象没有该字段的数据（如0值不返回）
- 该字段需要特定权限
- 字段名拼写错误

**解决方案：**
```python
# 使用 .get() 安全访问，并提供默认值
spend = float(data.get("spend", 0))
conversions_list = data.get("conversions", [])

# 验证字段是否被支持
test_url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/insights"
test_params = {
    "access_token": TOKEN,
    "fields": "spend,nonexistent_field",  # 会在错误信息中指出无效字段
    "limit": 1
}
test_response = requests.get(test_url, params=test_params).json()
```

---

### 问题 6：异步任务失败

```python
# 任务状态为 "Job Failed" 时，获取失败原因
if status.get("async_status") == "Job Failed":
    error_info = status.get("error", {})
    print(f"错误码: {error_info.get('code')}")
    print(f"错误信息: {error_info.get('message')}")
    
    # 常见失败原因：
    # - 时间范围太大（超过37个月）
    # - 字段组合不兼容
    # - breakdown 与 level 不兼容
```

---

## 错误处理最佳实践

```python
class FacebookAPIError(Exception):
    def __init__(self, code, message, subcode=None):
        self.code = code
        self.message = message
        self.subcode = subcode
        super().__init__(f"Facebook API Error {code}: {message}")

def safe_api_call(url, params):
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            error = data["error"]
            raise FacebookAPIError(
                code=error.get("code"),
                message=error.get("message"),
                subcode=error.get("error_subcode")
            )
        
        return data
        
    except requests.exceptions.Timeout:
        raise Exception("请求超时，请稍后重试")
    except requests.exceptions.ConnectionError:
        raise Exception("网络连接错误")
```
