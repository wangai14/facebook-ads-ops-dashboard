---
name: facebook-bm-ads
description: Facebook Business Manager (BM) 广告数据获取、自动投放与 AI 智能诊断完整指南。当用户需要通过 Facebook Marketing API 获取 BM 下的广告账户、广告系列、广告组、广告、投放洞察数据、自定义受众、像素数据，或需要自动创建广告系列/广告组/广告/上传素材/设置定向/自动化规则/按ROAS自动优化预算/复制广告/A/B测试，或需要 AI 诊断哪个广告组在衰退/哪个素材疲劳/是否进入学习受限/是否需要关停或加预算，或需要分析昨天、今天、最近7天、指定日期范围的广告数据，或需要配置 ROAS/CPA/花费无转化等报警规则并通过飞书/Telegram/邮件推送报警，或遇到 API 权限/Token 问题时使用此 Skill。也适用于数据批量拉取、定时任务报表、多账户聚合分析等场景。
---

# Facebook Business Manager 广告完整 Skill

本 Skill 提供通过 **Facebook Marketing API** 从 Business Manager (BM) 获取数据、自动投放广告、以及 **AI 智能诊断**的完整操作指南。

---

## ⭐ 本地快速使用（OpenClaw 直接可跑）

> 最短路径：先用脚本拉数，再做诊断。脚本优先，文档只保留规则和入口。
> 具体日期范围默认严格按范围跑；只有明确要找“最近有效投放期”时，才打开 `--auto-backfill`。

### 一键脚本

`scripts/fb_pull_report.py`

常用方式：

```powershell
python .\scripts\fb_pull_report.py --token-path ..\data\facebook_token.txt --date-preset yesterday --no-auto-backfill
python .\scripts\fb_pull_report.py --token-path ..\data\facebook_token.txt --since 2026-03-01 --until 2026-03-31 --levels account,campaign,adset,ad
python .\scripts\fb_pull_report.py --token-path ..\data\facebook_token.txt --decision-config .\references\decision_config.example.json --date-preset last_30d
python .\scripts\fb_pull_report.py --mock
```

### 报表口径规则

1. 购买 / 加购 / 发起结账 / 添加支付信息 **不要多 alias 累加**，只取一套主口径。
2. 不要把 `conversions` / `cost_per_conversion` 直接当 purchase / CPA。
3. 电商报表默认使用 `actions` + `action_values` + `purchase_roas`。
4. 默认固定 `action_report_time=conversion`，尽量使用 `use_unified_attribution_setting=true`。
5. 如果当前范围 `spend=0`，默认只当作“无消耗信息”；只有明确需要回看历史时，才启用 `--auto-backfill`。
6. 目标 CPA / ROAS 尽量通过 `--decision-config` 或命令行显式传入，不要长期依赖默认值。

### 推荐调用顺序

1. 先拉账户级汇总，确认是否有消耗
2. 再拉 campaign / adset / ad
3. 需要诊断时，再看 `status`、`effective_status`、`learning_stage_info`、预算、素材状态

---

## 参考文档

### 📊 数据获取

| 文档 | 说明 | 你最常用 | 推荐顺序 |
|---|---|---|---|
| [auth.md](references/auth.md) | App 创建、Access Token 获取与权限申请 | ★★★ | ① |
| [accounts.md](references/accounts.md) | BM 下广告账户列表与账户详情查询 | ★★★ | ② |
| [insights.md](references/insights.md) | 广告投放数据 (Insights) 拉取，含维度、指标、时间粒度 | ★★★★ | ③ |
| [campaigns.md](references/campaigns.md) | 广告系列 (Campaign)、广告组 (AdSet)、广告 (Ad) 数据查询 | ★★★ | ④ |
| [audiences.md](references/audiences.md) | 自定义受众 (Custom Audience) 与像素 (Pixel) 数据 | ★★ | ⑥ |
| [batch.md](references/batch.md) | 批量请求 (Batch API)、分页处理、限速策略 | ★★ | ⑦ |
| [errors.md](references/errors.md) | 常见错误码与解决方案 | ★★ | ⑧ |
| [examples.md](references/examples.md) | 完整代码示例 (Python / JavaScript / cURL) | ★★ | ⑤ |

### 🚀 自动投放

| 文档 | 说明 | 你最常用 | 推荐顺序 |
|---|---|---|---|
| [ad_creation.md](references/ad_creation.md) | 创建广告系列、广告组、广告的完整流程 | ★★★ | ① |
| [creative.md](references/creative.md) | 广告素材管理（单图/轮播/视频/动态素材/上传图片） | ★★★★ | ② |
| [automation.md](references/automation.md) | 自动化规则、预算优化脚本、A/B测试、分时段投放 | ★★★ | ③ |

### 🤖 AI 智能诊断

| 文档 | 说明 | 你最常用 | 推荐顺序 |
|---|---|---|---|
| [analytics.md](references/analytics.md) | 每日自动诊断：广告组衰退、素材疲劳、学习受限、关停/加预算建议 | ★★★★ | ① |
| [scaling_and_pausing.md](references/scaling_and_pausing.md) | **扩量判断**（是否加预算/复制放量）与 **关停判断**（止损/疲劳/误杀保护）的决策口径与阈值模板 | ★★★★ | ② |
| [alerts.md](references/alerts.md) | 报警规则配置 + 飞书/Telegram/邮件推送通知 | ★★★ | ③ |
| [creative_analysis.md](references/creative_analysis.md) | 素材 AI 分析：Thumbstop率/完播率/CTR对比，判断最强开头/卖点/人群 | ★★★ | ④ |

---

## 快速开始

### 前置条件

1. 已创建 Facebook **开发者应用** (App) — 见 [auth.md](references/auth.md)
2. 拥有 BM 的 **Admin 或 Analyst** 权限
3. 获取 **长期 Access Token**（读数据用 `ads_read`；投广告需要 `ads_management`）
4. 所需权限范围：`ads_read`、`ads_management`、`business_management`

### 最常用的 API 端点

```
# 数据读取 (GET)
GET /{business_id}/owned_ad_accounts          # BM 下的广告账户
GET /{ad_account_id}/campaigns                # 广告系列
GET /{ad_account_id}/adsets                   # 广告组
GET /{ad_account_id}/ads                      # 广告
GET /{ad_account_id}/insights                 # 投放数据汇总
GET /{ad_account_id}/customaudiences          # 自定义受众
GET /{ad_account_id}/adspixels                # 像素

# 自动投放 (POST — 需要 ads_management 权限)
POST /{ad_account_id}/campaigns               # 创建广告系列
POST /{ad_account_id}/adsets                  # 创建广告组
POST /{ad_account_id}/adcreatives             # 创建广告素材
POST /{ad_account_id}/ads                     # 创建广告
POST /{ad_account_id}/adimages                # 上传图片
POST /{ad_account_id}/advideos                # 上传视频
POST /{campaign_id}/copies                    # 复制广告系列
POST /{ad_account_id}/adrules_library         # 创建自动化规则
```

基础请求格式：

```
https://graph.facebook.com/v22.0/{ENDPOINT}?access_token={TOKEN}&fields={FIELDS}
```

---

## 核心工作流程

### 0. 自动投放广告（完整流程）

```
广告账户
  └── Campaign（系列）        → 见 ad_creation.md
        └── AdSet（广告组）   → 设定受众/预算/竞价
              ├── Creative    → 见 creative.md（上传图片/视频/轮播）
              └── Ad（广告）  → 绑定广告组 + 素材

自动化：自动化规则 / 预算优化 / A/B测试 → 见 automation.md

AI 诊断：每日数据诊断（衰退/疲劳/学习受限/关停建议）→ 见 analytics.md
```

### 0.1 实战：快速诊断“有点击无转化”

> 适合当前常见场景：CTR 不低但 AddToCart/Checkout/Purchase 为 0。

**诊断顺序（从快到慢）：**
1. **事件回传是否正常**（像素/SDK/域名验证）
2. **落地页首屏承接**（5秒内是否明确卖点/价格/CTA）
3. **素材是否“骗点击”**（CTR 高但 ATC 为 0 → 素材错位）
4. **受众是否过宽**（先缩小人群+高意图）

**关停阈值模板：**
- Link Click ≥ 20 且 **ATC=0** → 暂停该素材/广告
- Spend ≥ 目标 CPA × 1.5 且 **Purchase=0** → 暂停该广告组

---

### 1. 获取 BM 下所有广告账户

```python
import requests

BM_ID = "你的BM_ID"
TOKEN = "你的Access_Token"

url = f"https://graph.facebook.com/v22.0/{BM_ID}/owned_ad_accounts"
params = {
    "access_token": TOKEN,
    "fields": "id,name,account_status,currency,timezone_name,amount_spent",
    "limit": 100
}
response = requests.get(url, params=params)
data = response.json()
print(data)
```

### 2. 获取广告投放 Insights 数据

```python
AD_ACCOUNT_ID = "act_123456789"

url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/insights"
params = {
    "access_token": TOKEN,
    "fields": "campaign_name,adset_name,ad_name,spend,impressions,clicks,ctr,cpc,cpm,reach,frequency,actions,action_values,purchase_roas,date_start,date_stop",
    "time_range": '{"since":"2024-01-01","until":"2024-01-31"}',
    "time_increment": 1,          # 按天分组
    "level": "ad",              # campaign / adset / ad
    "action_report_time": "conversion",
    "limit": 500
}
response = requests.get(url, params=params)
print(response.json())
```

> ⚠️ 不建议把 `conversions` / `cost_per_conversion` 直接当成购买数 / 购买成本。
> 做电商逐广告报表时，优先使用 `actions` + `action_values` + `purchase_roas`，再按明确 alias 提取 purchase / ATC / IC / API。

### 3. 处理分页

```python
def get_all_pages(url, params):
    results = []
    while url:
        response = requests.get(url, params=params).json()
        results.extend(response.get("data", []))
        url = response.get("paging", {}).get("next")
        params = {}  # next URL 已包含所有参数
    return results
```

---

## API 版本说明

- **脚本默认版本**：`v22.0`
- Facebook API 按季度更新，每版本支持 **2 年**
- 始终在请求中显式指定版本号

---

## 常用字段速查

### Insights 指标字段

| 字段名 | 含义 |
|---|---|
| `spend` | 花费 |
| `impressions` | 展示次数 |
| `clicks` | 点击次数 |
| `reach` | 触达人数 |
| `frequency` | 频率 |
| `ctr` | 点击率 |
| `cpc` | 每次点击成本 |
| `cpm` | 千次展示成本 |
| `cpp` | 千人触达成本 |
| `conversions` | 转化次数 |
| `cost_per_conversion` | 每次转化成本 |
| `purchase_roas` | 购买广告支出回报率 |
| `video_avg_time_watched_actions` | 平均视频观看时长 |
| `video_thruplay_watched_actions` | 完整播放次数 |

### 时间粒度 (time_increment)

| 值 | 含义 |
|---|---|
| `1` | 按天 |
| `7` | 按周 |
| `monthly` | 按月 |
| `all_days` | 汇总整个时间范围 |

### 维度层级 (level)

| 值 | 说明 |
|---|---|
| `account` | 账户级汇总 |
| `campaign` | 广告系列级 |
| `adset` | 广告组级 |
| `ad` | 广告级（最细粒度） |

---

## 异步 Insights 查询（大数据量推荐）

当数据量大时（如查询全年数据），应使用**异步**模式：

```python
# 1. 创建异步任务
url = f"https://graph.facebook.com/v22.0/{AD_ACCOUNT_ID}/insights"
params = {
    "access_token": TOKEN,
    "fields": "campaign_name,spend,impressions,clicks",
    "time_range": '{"since":"2024-01-01","until":"2024-12-31"}',
    "level": "campaign",
    "async": True
}
job = requests.post(url, params=params).json()
job_id = job["report_run_id"]

# 2. 轮询任务状态
import time
while True:
    status_url = f"https://graph.facebook.com/v22.0/{job_id}"
    status = requests.get(status_url, params={"access_token": TOKEN}).json()
    pct = status.get("async_percent_completion", 0)
    print(f"进度: {pct}%")
    if status.get("async_status") == "Job Completed":
        break
    time.sleep(5)

# 3. 获取结果
result_url = f"https://graph.facebook.com/v22.0/{job_id}/insights"
results = requests.get(result_url, params={"access_token": TOKEN, "limit": 500}).json()
```

---

## 重要限制与注意事项

- **API 调用频率限制**：每个 App 每小时最多 **200 个评分单位**，超出后返回错误码 `4` 或 `17`
- **数据延迟**：Insights 数据通常延迟 **30 分钟 ~ 3 小时**，当天数据不稳定
- **Token 有效期**：用户 Token 默认 **1 小时**；长期 Token 约 **60 天**；System User Token **永不过期**（推荐生产环境使用）
- **数据保留**：Facebook 广告数据保留 **37 个月**
- **字段限制**：单次请求字段不宜超过 **50 个**

详细见各参考文档。
