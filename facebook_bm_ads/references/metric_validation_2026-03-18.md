# Meta 广告字段口径验证报告（2026-03-18）

## 验证目的
确认 `facebook_bm_ads` Skill 优化后的字段口径是否与真实 API 返回一致，避免重复计算转化。

---

## 验证方法

### 数据源
- 账户：`act_123456789` / `act_987654321`
- 时间：`date_preset=today`
- 层级：`level=ad`
- 字段：`actions`, `action_values`, `purchase_roas`

### 验证重点
1. 同一个广告里，多个 purchase alias 是否同时存在
2. 如果同时存在，数值是否相同（判断是否为同一事件的重复映射）
3. `purchase_roas` 的返回格式是否与文档描述一致

---

## 验证结果

### 1. Purchase Alias 重复映射问题

**发现：同一个广告里，以下 4 个 alias 同时存在且数值完全相同**

| 广告 | web_in_store_purchase | omni_purchase | purchase | onsite_web_purchase |
|------|----------------------|---------------|----------|---------------------|
| 图片 2 | 1 | 1 | 1 | 1 |
| 1343107-新品 - 牛仔裤 -0304-ssj-2.mp4 | 2 | 2 | 2 | 2 |
| 1344548-西装裙 -0310-01-clx.mp4 | 1 | 1 | 1 | 1 |
| 1342141-连衣裙 -0227ssj-2-细节款-clx-02.mp4 | 1 | 1 | 1 | 1 |
| 1343107-新品 - 牛仔裤---ssj-1.mp4 | 1 | 1 | 1 | 1 |

**结论：这 4 个 alias 是同一笔订单在不同口径下的映射，绝对不能累加。**

如果累加，会导致：
- 实际 7 单 → 被算成 28 单
- ROAS / CPA 全部失真
- 诊断结论建立在错误数据上

---

### 2. Purchase ROAS 返回格式

**发现：`purchase_roas` 返回的是 JSON 数组，带 action_type**

```json
"purchase_roas": [
  {"action_type": "omni_purchase", "value": 2.716276}
]
```

**结论：提取 ROAS 时需要先遍历数组，按 action_type 匹配，不能直接取第一个值。**

---

### 3. Action Values 字段结构

**发现：`action_values` 也是 JSON 数组，包含多种口径的价值**

```json
"action_values": [
  {"action_type": "onsite_web_app_purchase", "value": 79.94},
  {"action_type": "onsite_web_app_add_to_cart", "value": 149.88},
  {"action_type": "onsite_web_initiate_checkout", "value": 229.82},
  {"action_type": "add_payment_info", "value": 79.94}
]
```

**结论：提取 purchase_value 时同样需要按 alias 优先级匹配，不要累加。**

---

## 优化建议（已实施）

基于以上验证，我们已对 `facebook_bm_ads` Skill 做了以下优化：

### 1. SKILL.md
- 新增"报表口径安全规则"章节
- 明确警告不要把多个 purchase alias 直接累加
- 明确警告不要把 `conversions` 直接当购买数

### 2. references/insights.md
- 扩展 action_type 列表，补充 `omni_*` / `onsite_web_*` / `offsite_conversion.*`
- 新增"电商逐广告报表推荐字段"章节
- 明确推荐提取顺序（按优先级取单一主口径）

### 3. references/analytics.md
- 新增 PURCHASE_ALIASES / ADD_TO_CART_ALIASES 等常量定义
- 新增 `extract_action_metric_prefer_first` 函数，按优先级提取
- 修改 `extract_conversions` 不再 fallback 到 `conversions` 泛字段
- 修改数据抓取字段，移除 `conversions` / `cost_per_result`

### 4. 新增文件
- `references/ecommerce_ad_diagnosis_template.md`：逐广告电商诊断模板
- `references/metric_validation_2026-03-18.md`：本次验证报告（本文件）

---

## 验证结论

| 问题 | 验证前风险 | 验证后状态 |
|------|-----------|-----------|
| 多 alias 累加导致重复计算 | 🔴 高风险 | ✅ 已修复 |
| conversions 被误用为 purchase | 🔴 高风险 | ✅ 已警告 |
| purchase_roas 提取逻辑 | 🟡 中风险 | ✅ 已优化 |
| action_values 提取逻辑 | 🟡 中风险 | ✅ 已优化 |
| 诊断脚本依赖 cost_per_result | 🟡 中风险 | ✅ 已移除 |

---

## 后续建议

1. **每日诊断报表**优先使用 `actions` + `action_values` + `purchase_roas`
2. **购买数提取**按优先级：`omni_purchase` → `purchase` → `onsite_web_purchase`
3. **不要直接使用** `conversions` / `cost_per_conversion` 作为电商 KPI
4. **定期验证**口径是否变化（Meta 可能新增/调整 alias）

---

## 附录：验证脚本

```powershell
$token = (Get-Content '..\data\facebook_token.txt' -Raw).Trim()
$api = "https://graph.facebook.com/v22.0"
$actId = "act_123456789"
$url = "$api/$actId/insights?date_preset=today&level=ad&fields=ad_name,actions,action_values,purchase_roas&limit=200&access_token=$([uri]::EscapeDataString($token))"
$data = Invoke-RestMethod -Uri $url -Method Get

foreach ($row in $data.data) {
    if ($row.actions) {
        foreach ($a in $row.actions) {
            if ($a.action_type -in @('omni_purchase','purchase','onsite_web_purchase','web_in_store_purchase')) {
                Write-Host "$($row.ad_name): $($a.action_type) = $($a.value)"
            }
        }
    }
}
```
