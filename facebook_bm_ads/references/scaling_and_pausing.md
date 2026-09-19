# 扩量与关停判定（Facebook Ads）

本篇用于在 **Campaign / AdSet / Ad（素材）** 三个粒度上，基于 Facebook Insights 数据做两类决策：

- **是否扩量（加预算/复制/放量）**
- **是否关停（暂停广告/广告组/素材止损）**

> 重要原则：
> 1) **先对齐口径**（BM列名/归因窗口/时区/unified attribution），否则“BM有下单但 API=0”会导致错误决策。
> 2) **数据不足不做强决策**：花费太少、点击太少、或转化回传不稳定时，只输出“观察/补数据/排查追踪”。
> 3) 本 Skill 默认只输出**建议**，不自动修改投放（除非你明确要求接入 ads_management 并启用自动化）。

---

## 0) 建议你固定拉取的字段（用于扩量/关停判定）

### 必备指标（看板/成本）
- spend, impressions, reach, frequency
- cpm, ctr, cpc
- **cpa_link_click**（单次链接点击费用；若无可用 spend/inline_link_clicks 备算）
- **cpa_landing_page_view**（LPV 费用）

### 漏斗事件（actions/action_values 展平）
（按你当前项目，建议主 KPI 先统一为单一 purchase 主口径；按优先级取第一项，不要把多个 alias 相加）
- act_view_content
- act_landing_page_view
- act_add_to_cart
- act_initiate_checkout
- **act_offsite_conversion.fb_pixel_purchase**（购买/下单）
- purchase_roas（如可用）

### 拉数建议
- 时间：最近 14 天（baseline） + 最近 3 天（recent），用于趋势对比
- `time_increment=1`：排查归因延迟/隔天补数
- `use_unified_attribution_setting=true`
- 必要时对 actions 加：`action_breakdowns=action_type`

---

## 1) 数据充分性（不满足则不做“扩量/关停”硬结论）

在任意粒度（campaign/adset/ad）上，建议满足至少其一：

- **花费阈值**：spend ≥ max(目标 CPA × 1.5, 10)
- **点击阈值**：inline_link_clicks ≥ 20（或 clicks ≥ 50）
- **漏斗阈值**：LPV ≥ 10（否则 LPV 成本波动很大）

若 pixel/CAPI 转化回传不稳定（purchase=0 但 BM 有下单）：
- 扩量只看“强前置指标”（LPV、VC、ATC、IC）时，默认 **保守扩量**（小幅 +10%~20%）
- 同时必须把“追踪/归因对账”列为最高优先级任务

---

## 2) 扩量判定（Scale Up）

扩量不是“看到 CTR 高就加钱”，而是：**利润指标/目标达标 + 表现稳定 + 还有可放大空间**。

### 2.1 强扩量（建议加预算 20%~30%）
满足以下条件（以最近 3 天 recent 为主，必要时对比 baseline）：

1) **有有效转化**
- purchase ≥ 2（或你业务能接受的最小样本），且不集中在单一异常时段

2) **效率达标**（二选一）
- ROAS ≥ 目标 ROAS × 1.2
- 或 CPA ≤ 目标 CPA × 0.9

3) **稳定性 OK**
- CTR 近 3 天未出现连续下滑（例如相对 baseline 下滑 < 30%）
- CPM 未出现明显抬升（例如相对 baseline 上升 < 20%）

4) **尚未明显疲劳/受限**
- frequency < 2.5（冷启动/拓量阶段尤其重要）
- learning_stage_info 不为 LEARNING_LIMITED（如果能拿到该字段）

> 执行方式建议：
> - 同一 AdSet：**每日加 20%~30%**，观察 24h；避免一次翻倍导致学习重置
> - 或复制 AdSet：复制到新 AdSet（新预算）保持原 AdSet 稳定

### 2.2 温和扩量（建议加预算 10%~20% / 先复制再放量）
适用于 purchase 样本不足但漏斗很强的情况：

- LPV 成本低（cpa_landing_page_view 显著优于其他组/素材）
- 且 LPV→VC、VC→ATC、ATC→IC 比例健康（至少不差于 baseline）
- CPM 稳定、frequency 低

> 注意：如果 purchase 始终 0，同时 BM 显示有下单——优先解决归因/回传对账，不要盲目扩量。

---

## 3) 关停判定（Pause / Kill）

关停分两类：
- **止损关停**：花钱买不到漏斗/转化
- **疲劳关停**：素材/人群打穿，继续投边际效率恶化

### 3.1 止损关停（强建议暂停）
满足其一即可进入“暂停候选”，满足两条基本可直接暂停：

- spend ≥ 目标 CPA × 2 且 purchase = 0
- spend ≥ 10 且 LPV = 0（落地页打不开/加载慢/受众不匹配/链路有问题）
- inline_link_clicks 有，但 LPV 很少（点击→落地页掉的很厉害，优先排查页面速度/跳转/像素事件）

> 素材粒度（Ad）止损：
> - 同一 AdSet 内对比：若某条 Ad 的 **LPV 成本 ≥ 最优 Ad 的 1.5 倍**，且 spend ≥ 5~10（按你的单价调整）→ 优先暂停该 Ad，保留更优者。

### 3.2 疲劳关停（建议换素材/换人群或暂停）
- frequency ≥ 2.5~3.0
- 同时 CTR 相对 baseline 下滑 ≥ 30%
- 且 CPM 上升明显（例如 ≥ 20%）
- 且漏斗事件（LPV/VC/ATC）也同步变差

> 处理优先级：
> 1) 先“换素材”或加素材分支；
> 2) 再考虑关停整个 AdSet（除非 AdSet 已经没有任何素材能跑出好漏斗）。

---

## 4) 三层级的决策口径（避免误杀/误扩）

### Campaign 粒度
- 用于判断：整体是否该扩预算、是否该切结构（新 Campaign/新目标）
- 不建议仅凭 Campaign 粒度关停（容易误杀某个强 AdSet）

### AdSet 粒度（最关键）
- 扩量/关停的主决策层
- 结合学习状态、受众、出价/版位，做“放量”或“止损”

### Ad（素材）粒度
- 用于素材胜负判断：同一 AdSet 内“谁该保留、谁该关”
- 核心看：CTR、LPV成本、漏斗效率（LPV→VC→ATC→IC）以及疲劳（frequency + CTR下滑）

---

## 5) 输出建议模板（你每天10点的自动报表可以直接用）

### ✅ 扩量建议（示例格式）
- 对象：AdSet/Ad
- 结论：建议扩量（+20%）/温和扩量（+10%）/先复制再放量
- 依据：最近3天 vs 基线（CPA/ROAS/CTR/CPM/frequency/LPV成本/ATC/IC）
- 风险提示：是否 learning limited；是否 purchase 回传异常

### ⛔ 关停建议（示例格式）
- 对象：AdSet/Ad
- 结论：建议暂停 / 建议换素材 / 建议继续观察
- 依据：止损（花费阈值 + 0转化/0漏斗）或疲劳（frequency + CTR下滑 + CPM抬升）
- 下一步：给出 1~2 个可执行动作（换素材卖点/加新人群/检查落地页/检查像素事件）

---

## 6) 实操参数建议（保守但可执行）

- 扩量步幅：
  - 稳定跑量：每天 +20%~30%
  - 不稳定/回传异常：每天 +10%~20%，优先复制结构分流风险

- 关停步幅：
  - 先关差素材（Ad）→ 再关差广告组（AdSet）→ 最后才关 Campaign

- 避免“误杀 3/1 出过单”的情况：
  - 对历史曾出单的 AdSet：除非达到明确止损条件（spend ≥ 目标CPA×2 且 purchase=0），否则优先降预算/换素材而不是直接关停。
