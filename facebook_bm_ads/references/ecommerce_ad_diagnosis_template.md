# 逐广告电商诊断模板（实战版）

本模板用于每日/每周对 **每个广告** 做标准化诊断，输出可执行的关停/放量/观察建议。

> ⚠️ 口径提醒：本模板默认以 `actions` / `action_values` / `purchase_roas` 为主。
> 对于 purchase / add_to_cart / initiate_checkout / add_payment_info，采用**按优先级取单一主口径**，避免重复累计。

---

## 一、推荐拉取的字段（逐广告）

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

params = {
    "level": "ad",
    "action_report_time": "conversion",
    "time_increment": "all_days",
    "date_preset": "today",  # 或 time_range
    "limit": 500
}
```

---

## 二、推荐的事件提取顺序（不要多 alias 累加）

### 购买数（purchases）
按优先级取**第一个有值的**：
1. `omni_purchase`
2. `purchase`
3. `web_in_store_purchase`
4. `onsite_web_purchase`
5. `onsite_web_app_purchase`
6. `offsite_conversion.fb_pixel_purchase`
7. `offsite_conversion.purchase`
8. `app_custom_event.fb_mobile_purchase`

### 加购数（add_to_cart）
按优先级取**第一个有值的**：
1. `omni_add_to_cart`
2. `add_to_cart`
3. `onsite_web_add_to_cart`
4. `onsite_web_app_add_to_cart`
5. `offsite_conversion.fb_pixel_add_to_cart`
6. `offsite_conversion.add_to_cart`
7. `app_custom_event.fb_mobile_add_to_cart`

### 发起结账（initiate_checkout）
按优先级取**第一个有值的**：
1. `omni_initiated_checkout`
2. `initiate_checkout`
3. `onsite_web_initiate_checkout`
4. `onsite_web_app_initiate_checkout`
5. `offsite_conversion.fb_pixel_initiate_checkout`
6. `offsite_conversion.initiate_checkout`
7. `app_custom_event.fb_mobile_initiated_checkout`

### 添加支付信息（add_payment_info）
按优先级取**第一个有值的**：
1. `omni_add_payment_info`
2. `add_payment_info`
3. `onsite_web_add_payment_info`
4. `onsite_web_app_add_payment_info`
5. `offsite_conversion.fb_pixel_add_payment_info`
6. `offsite_conversion.add_payment_info`

### ROAS / purchase_value
1. purchase value 优先从 `action_values` 按 purchase alias 顺序提取
2. ROAS 优先用 `purchase_value / spend`
3. 如果没有 purchase value，再从 `purchase_roas` 数组按 purchase alias 匹配
4. 如果同一广告多个 purchase alias 同时存在，**只能取优先级最高的一个**，不要相加

---

## 三、诊断阈值模板（可根据业务调整）

### 1. 数据充分性判断
在诊断前，先判断数据是否够做决策：

| 条件 | 判断 |
|------|------|
| spend ≥ 目标 CPA × 1.5 | 数据充分 |
| inline_link_clicks ≥ 20 | 数据充分 |
| spend < 10 且 clicks < 10 | 数据不足，跳过诊断 |

### 2. 关停判定（止损）
满足**任一**即进入关停候选：

| 条件 | 建议 |
|------|------|
| spend ≥ 目标 CPA × 2 且 purchase = 0 | 🔴 强建议关停 |
| spend ≥ 20 且 ATC = 0 | 🟡 建议关停 |
| inline_link_clicks ≥ 20 且 ATC = 0 | 🟡 建议关停 |
| spend ≥ 10 且 LPV = 0 | 🟡 检查落地页 |

### 3. 放量判定（扩量）
满足**全部**即进入放量候选：

| 条件 | 建议 |
|------|------|
| purchase ≥ 2 | 有转化样本 |
| ROAS ≥ 目标 ROAS × 1.2 | 效率达标 |
| CTR 近期未连续下滑 | 素材未疲劳 |
| frequency < 2.5 | 人群未饱和 |

**放量步幅建议：**
- 稳定跑量：每日 +20%~30%
- 不稳定/回传异常：每日 +10%~20%

### 4. 素材疲劳判定
满足**任一**即进入疲劳候选：

| 条件 | 建议 |
|------|------|
| frequency ≥ 2.5 且 CTR 下滑 ≥ 30% | 🟡 建议换素材 |
| CPM 上升 ≥ 20% 且 CTR 下滑 | 🟡 建议换素材 |
| 同一 AdSet 内 CTR 最低且花费最高 | 🟡 建议暂停该 Ad |

### 5. 漏斗健康度（电商专用）
用前置事件判断转化潜力：

| 漏斗环节 | 健康阈值 |
|----------|----------|
| CTR | ≥ 2%（冷启动可放宽至 1.5%） |
| ATC 率（ATC/Clicks） | ≥ 5% |
| IC 率（IC/ATC） | ≥ 30% |
| Purchase 率（Purchase/IC） | ≥ 50% |

---

## 四、诊断输出模板（每日报表格式）

### 格式示例

```
【广告诊断日报】2026-03-18

🔴 严重问题（X 项）
────────────────────────────────────
  🔴 [建议关停] 1342141-连衣裙-0227ssj-2-细节款-clx-02.mp4
     花费：¥59.32 | 购买：1 | CPA: ¥59.32 | ROAS: 0.69
     原因：CPA 是目标的 2.4 倍，且 ROAS 低于 1
     建议：立即暂停，分析素材/落地页问题

🟡 警告（X 项）
────────────────────────────────────
  🟡 [素材疲劳] 1345037-连衣裙-0313-02-clx.mp4
     频率：2.8 | CTR 从 4.5% 降至 2.8%（下滑 38%）
     建议：更换素材或复制 AdSet 测试新创意

🟢 优化机会（X 项）
────────────────────────────────────
  🟢 [建议放量] 1343107-新品-牛仔裤-0304-ssj-2.mp4
     ROAS: 4.52x（目标 2.5x）| 购买：4 单 | 趋势向上
     建议：日预算 +20%
```

---

## 五、实战诊断流程（每日 10 分钟）

### Step 1：拉数据（2 分钟）
用修好的脚本拉今日逐广告数据：
- 两个账户
- `level=ad`
- `action_report_time=conversion`
- 字段：`actions`, `action_values`, `purchase_roas`

### Step 2：筛出有购买的广告（1 分钟）
- 按 purchase 降序
- 标记 ROAS < 1 的广告

### Step 3：筛出高花费无转化的广告（2 分钟）
- spend ≥ 20 且 purchase = 0
- spend ≥ 目标 CPA × 1.5 且 ATC = 0

### Step 4：筛出疲劳信号广告（2 分钟）
- frequency ≥ 2.5
- CTR 较昨日/基线下滑 ≥ 30%

### Step 5：输出诊断结论（3 分钟）
按上面模板输出：
- 🔴 严重问题（关停候选）
- 🟡 警告（疲劳/低效候选）
- 🟢 优化机会（放量候选）

---

## 六、常见场景诊断速查

### 场景 1：有点击无转化
**诊断顺序：**
1. 事件回传是否正常（像素/CAPI）
2. 落地页首屏是否明确卖点/价格/CTA
3. 素材是否"骗点击"（CTR 高但 ATC=0）
4. 受众是否过宽

**关停阈值：**
- Link Click ≥ 20 且 ATC=0 → 暂停该素材
- Spend ≥ 目标 CPA × 1.5 且 Purchase=0 → 暂停该广告组

### 场景 2：ROAS 突然下滑
**诊断顺序：**
1. 对比昨日/基线 CTR / CPM / frequency
2. 检查是否有大改价/改预算/改受众
3. 检查竞争环境（大促/节假日）
4. 检查像素回传是否异常

**处理建议：**
- 素材疲劳 → 换素材
- 人群饱和 → 扩人群或复制 AdSet
- 回传异常 → 先修复追踪

### 场景 3：CPA 过高但有转化
**诊断顺序：**
1. 对比账户内其他 AdSet / Ad 的 CPA
2. 检查出价策略（最低成本 vs 目标 CPA）
3. 检查受众范围是否过窄

**处理建议：**
- CPA > 目标 × 2 → 降预算或暂停
- CPA > 目标 × 1.5 但 ROAS 仍达标 → 观察
- CPA 略高但量级大 → 可接受

### 场景 4：新广告冷启动
**诊断顺序：**
1. 给足 48-72 小时学习期
2. 花费达到目标 CPA × 2 前不做关停决策
3. 关注前置事件（CTR / ATC / IC）而非只看 purchase

**处理建议：**
- 48h 后 spend ≥ 目标 CPA × 2 且 purchase=0 → 考虑关停
- 48h 内 → 观察前置漏斗

---

## 七、附录：指标计算公式

| 指标 | 公式 |
|------|------|
| CTR | clicks / impressions × 100% |
| CPC | spend / clicks |
| CPM | spend / impressions × 1000 |
| Frequency | impressions / reach |
| ATC 率 | add_to_cart / clicks × 100% |
| IC 率 | initiate_checkout / add_to_cart × 100% |
| Purchase 率 | purchase / initiate_checkout × 100% |
| CPA | spend / purchase |
| ROAS | purchase_value / spend |

---

## 八、使用建议

1. **每日固定时间跑**（如上午 10 点），避免频繁改动影响学习期
2. **先关差素材，再关差广告组**，避免误杀
3. **放量要慢**，每日 +20% 比一次性 +100% 更稳
4. **保留历史诊断记录**，方便回溯哪些决策对了/错了
5. **定期复盘阈值**，根据实际业务调整关停/放量标准
