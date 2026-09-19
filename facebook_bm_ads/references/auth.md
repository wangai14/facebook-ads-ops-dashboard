# Facebook Marketing API 鉴权指南

## 1. 创建 Facebook 开发者应用

### 步骤

1. 访问 [developers.facebook.com](https://developers.facebook.com)
2. 点击 **"我的应用"** → **"创建应用"**
3. 选择应用类型：选 **"商业"** (Business)
4. 填写应用名称和联系邮箱
5. 进入应用后，添加产品 **"Marketing API"**

### 关键配置

- **App ID** (应用编号)：在应用面板首页可见
- **App Secret** (应用密钥)：在"设置 → 基本"中可见（需要保密！）
- 在"设置 → 基本"中添加**隐私政策 URL** 和**应用图标**（上架审核用）

---

## 2. Access Token 类型说明

| Token 类型 | 有效期 | 使用场景 |
|---|---|---|
| 用户短期 Token | ~1 小时 | 快速测试 |
| 用户长期 Token | ~60 天 | 开发调试 |
| System User Token | 永不过期 | **生产环境推荐** |
| App Token | 永不过期 | 仅用于应用级操作，无法访问广告账户 |

---

## 3. 获取用户短期 Token（测试用）

在 [Graph API Explorer](https://developers.facebook.com/tools/explorer/) 中：

1. 选择你的 App
2. 点击 **"生成 Access Token"**
3. 勾选权限：`ads_read`、`ads_management`、`business_management`
4. 复制生成的 Token（约 1 小时有效）

---

## 4. 将短期 Token 换成长期 Token (60天)

```python
import requests

APP_ID = "你的App_ID"
APP_SECRET = "你的App_Secret"
SHORT_TOKEN = "短期Token"

url = "https://graph.facebook.com/v22.0/oauth/access_token"
params = {
    "grant_type": "fb_exchange_token",
    "client_id": APP_ID,
    "client_secret": APP_SECRET,
    "fb_exchange_token": SHORT_TOKEN
}
response = requests.get(url, params=params)
data = response.json()
long_token = data["access_token"]
print("长期Token:", long_token)
print("过期时间(秒):", data.get("expires_in"))
```

**cURL 版本：**

```bash
curl "https://graph.facebook.com/v22.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=APP_ID
  &client_secret=APP_SECRET
  &fb_exchange_token=SHORT_TOKEN"
```

---

## 5. 创建 System User Token（生产环境推荐）

**System User** 是 BM 下的系统账户，其 Token 永不过期，最适合定时任务和服务器端应用。

### 创建步骤

1. 进入 [Business Manager](https://business.facebook.com)
2. **设置 (Settings)** → **用户 (Users)** → **系统用户 (System Users)**
3. 点击 **"添加"**，选择角色：
   - `Admin` — 全部权限
   - `Employee` — 受限权限
4. 给系统用户分配广告账户访问权限
5. 点击系统用户 → **"生成新 Token"**
6. 选择你的 App，勾选权限范围

### 推荐权限范围

```
ads_read            # 读取广告数据（只读，推荐）
ads_management      # 管理广告（需要时才开启）
business_management # 访问BM数据
read_insights       # 读取洞察数据
```

---

## 6. 验证 Token 是否有效

```python
import requests

TOKEN = "你的Token"

# 方法 1：查询 Token 信息
url = "https://graph.facebook.com/debug_token"
params = {
    "input_token": TOKEN,
    "access_token": f"{APP_ID}|{APP_SECRET}"  # 使用 App Token
}
response = requests.get(url, params=params)
info = response.json()["data"]

print("有效:", info["is_valid"])
print("用户ID:", info.get("user_id"))
print("权限:", info.get("scopes"))
print("过期时间:", info.get("expires_at"))  # 0 表示永不过期

# 方法 2：直接查询 /me
me = requests.get("https://graph.facebook.com/v22.0/me",
                  params={"access_token": TOKEN}).json()
print(me)
```

---

## 7. OAuth 2.0 标准流程（Web 应用）

适用于需要**用户授权**的 Web 应用：

```python
# Step 1: 构建授权 URL
from urllib.parse import urlencode

auth_url = "https://www.facebook.com/v22.0/dialog/oauth?" + urlencode({
    "client_id": APP_ID,
    "redirect_uri": "https://yourdomain.com/callback",
    "scope": "ads_read,business_management",
    "response_type": "code",
    "state": "随机字符串防CSRF"
})
print("引导用户访问:", auth_url)

# Step 2: 用 code 换 access_token
code = "用户授权后URL中的code"
token_url = "https://graph.facebook.com/v22.0/oauth/access_token"
params = {
    "client_id": APP_ID,
    "client_secret": APP_SECRET,
    "redirect_uri": "https://yourdomain.com/callback",
    "code": code
}
token_data = requests.get(token_url, params=params).json()
access_token = token_data["access_token"]
```

---

## 8. 常见权限说明

| 权限 | 说明 | 是否需要审核 |
|---|---|---|
| `ads_read` | 读取广告数据 | 需要 |
| `ads_management` | 创建/编辑广告 | 需要 |
| `business_management` | 访问BM资产 | 需要 |
| `read_insights` | 访问Insights数据 | 需要 |
| `pages_read_engagement` | 读取主页互动数据 | 需要 |

> **注意**：以上权限在上线前需要通过 Facebook 的 **应用审核 (App Review)**，测试账户无需审核。

---

## 9. 安全建议

- **永远不要**将 `App Secret` 和 `Access Token` 硬编码在代码中
- 使用环境变量或密钥管理服务（如 AWS Secrets Manager）
- 定期轮换 Token，设置 Token 过期告警
- 只申请必要的最小权限
- 在服务器端存储 Token，不要暴露给前端

```python
# 推荐做法：使用环境变量
import os
TOKEN = os.environ.get("FB_ACCESS_TOKEN")
APP_SECRET = os.environ.get("FB_APP_SECRET")
```
