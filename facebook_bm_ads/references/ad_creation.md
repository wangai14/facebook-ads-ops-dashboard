# 创建广告系列、广告组和广告指南

> ⚠️ 所有写操作需要 `ads_management` 权限。建议先在测试账户操作，确认无误后再用于正式账户。

---

## 1. 完整投放流程

```
BM 广告账户
  └── Campaign（广告系列） — 设定目标、总预算
        └── AdSet（广告组） — 设定受众、版位、日预算、竞价
              └── Ad（广告） — 绑定素材 (Creative)
```

---

## 2. 第一步：创建广告系列 (Campaign)

```python
import requests
import json

TOKEN = "你的Token（需要 ads_management 权限）"
AD_ACCOUNT_ID = "act_123456789"
BASE_URL = "https://graph.facebook.com/v22.0"

def create_campaign(name, objective, status="PAUSED", daily_budget=None, lifetime_budget=None):
    """
    创建广告系列
    objective 常用值：
      OUTCOME_SALES       — 销售/转化
      OUTCOME_LEADS       — 潜在客户
      OUTCOME_TRAFFIC     — 流量
      OUTCOME_AWARENESS   — 品牌知名度
      OUTCOME_ENGAGEMENT  — 互动
      OUTCOME_APP_PROMOTION — 应用推广
    """
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/campaigns"
    data = {
        "access_token": TOKEN,
        "name": name,
        "objective": objective,
        "status": status,           # ACTIVE / PAUSED
        "special_ad_categories": json.dumps([])  # 特殊广告类别（无则空数组）
    }
    
    # 预算只能选一种：日预算 或 总预算（单位：分）
    if daily_budget:
        data["daily_budget"] = int(daily_budget * 100)   # 元 → 分
    if lifetime_budget:
        data["lifetime_budget"] = int(lifetime_budget * 100)
    
    response = requests.post(url, data=data).json()
    if "error" in response:
        raise Exception(f"创建系列失败: {response['error']}")
    
    campaign_id = response["id"]
    print(f"✓ 广告系列创建成功: {campaign_id}")
    return campaign_id


# 示例：创建一个"转化"目标的广告系列，日预算 100 元，初始暂停
campaign_id = create_campaign(
    name="2024-Q1-转化-测试",
    objective="OUTCOME_SALES",
    status="PAUSED",
    daily_budget=100.0
)
```

---

## 3. 第二步：创建广告组 (AdSet)

```python
def create_adset(campaign_id, name, daily_budget, targeting, optimization_goal="OFFSITE_CONVERSIONS",
                 bid_strategy="LOWEST_COST_WITHOUT_CAP", pixel_id=None, status="PAUSED"):
    """
    创建广告组
    
    optimization_goal 常用值：
      OFFSITE_CONVERSIONS  — 网站转化（需要像素）
      LINK_CLICKS          — 链接点击
      REACH                — 触达
      LEADS                — 潜在客户
      APP_INSTALLS         — 应用安装
      LANDING_PAGE_VIEWS   — 落地页浏览
      VIDEO_VIEWS          — 视频观看
      THRUPLAY             — ThruPlay
    
    bid_strategy 常用值：
      LOWEST_COST_WITHOUT_CAP  — 最低成本（自动竞价，推荐）
      COST_CAP                 — 目标成本上限（需设 bid_amount）
      BID_CAP                  — 竞价上限（需设 bid_amount）
    """
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/adsets"
    data = {
        "access_token": TOKEN,
        "name": name,
        "campaign_id": campaign_id,
        "daily_budget": int(daily_budget * 100),  # 元 → 分
        "optimization_goal": optimization_goal,
        "billing_event": "IMPRESSIONS",           # 按展示计费（最常用）
        "bid_strategy": bid_strategy,
        "targeting": json.dumps(targeting),
        "status": status,
        "start_time": "2024-03-01T00:00:00+0800"  # 可选，不填则立即开始
    }
    
    # 转化目标需要绑定像素
    if pixel_id and optimization_goal in ["OFFSITE_CONVERSIONS", "LANDING_PAGE_VIEWS"]:
        data["promoted_object"] = json.dumps({
            "pixel_id": pixel_id,
            "custom_event_type": "PURCHASE"  # 或 LEAD / ADD_TO_CART 等
        })
    
    response = requests.post(url, data=data).json()
    if "error" in response:
        raise Exception(f"创建广告组失败: {response['error']}")
    
    adset_id = response["id"]
    print(f"✓ 广告组创建成功: {adset_id}")
    return adset_id


# ====== 定向设置示例 ======

# 示例1：按国家+年龄+兴趣定向
targeting_basic = {
    "geo_locations": {
        "countries": ["US", "CA"]       # 国家代码
    },
    "age_min": 25,
    "age_max": 45,
    "genders": [1],                     # 1=男, 2=女, 不填=不限
    "interests": [
        {"id": "6003139266461", "name": "Shopping"}
    ],
    "device_platforms": ["mobile"],     # mobile / desktop
    "publisher_platforms": ["facebook", "instagram"],
    "facebook_positions": ["feed", "story"],
    "instagram_positions": ["stream", "story"]
}

# 示例2：使用自定义受众定向（再营销）
targeting_retarget = {
    "geo_locations": {"countries": ["US"]},
    "age_min": 18,
    "age_max": 65,
    "custom_audiences": [
        {"id": "自定义受众ID", "name": "网站访客30天"}
    ],
    "excluded_custom_audiences": [
        {"id": "已购买受众ID", "name": "已购买用户"}
    ]
}

# 创建广告组
adset_id = create_adset(
    campaign_id=campaign_id,
    name="美国-25-45岁-转化-移动端",
    daily_budget=50.0,
    targeting=targeting_basic,
    optimization_goal="OFFSITE_CONVERSIONS",
    pixel_id="你的像素ID",
    status="PAUSED"
)
```

---

## 4. 第三步：创建广告素材 (Creative)

```python
def create_image_creative(name, image_url, title, body, link_url, call_to_action="SHOP_NOW", page_id=None):
    """
    创建图片广告素材
    call_to_action 常用值：
      SHOP_NOW / LEARN_MORE / SIGN_UP / CONTACT_US / BOOK_NOW
      DOWNLOAD / GET_OFFER / SUBSCRIBE / WATCH_MORE / APPLY_NOW
    """
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/adcreatives"
    
    object_story_spec = {
        "link_data": {
            "image_url": image_url,    # 或使用 image_hash（上传后获得）
            "link": link_url,
            "message": body,           # 广告文案（帖子正文）
            "name": title,             # 标题
            "call_to_action": {
                "type": call_to_action,
                "value": {"link": link_url}
            }
        }
    }
    
    if page_id:
        object_story_spec["page_id"] = page_id
    
    data = {
        "access_token": TOKEN,
        "name": name,
        "object_story_spec": json.dumps(object_story_spec)
    }
    
    response = requests.post(url, data=data).json()
    if "error" in response:
        raise Exception(f"创建素材失败: {response['error']}")
    
    creative_id = response["id"]
    print(f"✓ 广告素材创建成功: {creative_id}")
    return creative_id


# 创建图片广告素材
creative_id = create_image_creative(
    name="测试图片素材",
    image_url="https://example.com/ad_image.jpg",
    title="限时优惠 - 立省50%",
    body="🔥 全场商品限时五折，数量有限！点击立即购买。",
    link_url="https://example.com/sale",
    call_to_action="SHOP_NOW",
    page_id="你的主页ID"
)
```

---

## 5. 第四步：创建广告 (Ad)

```python
def create_ad(adset_id, name, creative_id, tracking_url=None, status="PAUSED"):
    """创建广告，绑定广告组和素材"""
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/ads"
    data = {
        "access_token": TOKEN,
        "name": name,
        "adset_id": adset_id,
        "creative": json.dumps({"creative_id": creative_id}),
        "status": status
    }
    
    # 可选：添加 UTM 跟踪参数
    if tracking_url:
        data["tracking_specs"] = json.dumps([{
            "action.type": ["offsite_conversion"],
            "fb.pixel": ["你的像素ID"]
        }])
    
    response = requests.post(url, data=data).json()
    if "error" in response:
        raise Exception(f"创建广告失败: {response['error']}")
    
    ad_id = response["id"]
    print(f"✓ 广告创建成功: {ad_id}")
    return ad_id


# 创建广告
ad_id = create_ad(
    adset_id=adset_id,
    name="广告-图片-A版",
    creative_id=creative_id,
    status="PAUSED"
)

print(f"\n投放结构创建完成！")
print(f"  Campaign: {campaign_id}")
print(f"  AdSet:    {adset_id}")
print(f"  Ad:       {ad_id}")
```

---

## 6. 完整一站式创建流程（封装版）

```python
def create_full_campaign(config):
    """
    一键创建完整广告投放结构
    config 格式见下方示例
    """
    print("=== 开始创建广告结构 ===")
    
    # 1. 创建系列
    campaign_id = create_campaign(
        name=config["campaign_name"],
        objective=config["objective"],
        status="PAUSED",
        daily_budget=config.get("campaign_daily_budget")
    )
    
    results = {"campaign_id": campaign_id, "adsets": []}
    
    for adset_config in config["adsets"]:
        # 2. 创建广告组
        adset_id = create_adset(
            campaign_id=campaign_id,
            name=adset_config["name"],
            daily_budget=adset_config["daily_budget"],
            targeting=adset_config["targeting"],
            optimization_goal=config.get("optimization_goal", "OFFSITE_CONVERSIONS"),
            pixel_id=config.get("pixel_id"),
            status="PAUSED"
        )
        
        adset_ads = []
        for creative_config in adset_config["creatives"]:
            # 3. 创建素材
            creative_id = create_image_creative(
                name=creative_config["name"],
                image_url=creative_config["image_url"],
                title=creative_config["title"],
                body=creative_config["body"],
                link_url=config["landing_url"],
                call_to_action=config.get("cta", "SHOP_NOW"),
                page_id=config.get("page_id")
            )
            
            # 4. 创建广告
            ad_id = create_ad(
                adset_id=adset_id,
                name=creative_config["name"],
                creative_id=creative_id,
                status="PAUSED"
            )
            adset_ads.append({"ad_id": ad_id, "creative_id": creative_id})
        
        results["adsets"].append({"adset_id": adset_id, "ads": adset_ads})
    
    return results


# ====== 使用示例 ======
campaign_config = {
    "campaign_name": "2024-Q1-电商大促",
    "objective": "OUTCOME_SALES",
    "optimization_goal": "OFFSITE_CONVERSIONS",
    "pixel_id": "你的像素ID",
    "page_id": "你的主页ID",
    "landing_url": "https://example.com/sale",
    "cta": "SHOP_NOW",
    "adsets": [
        {
            "name": "美国-宽泛-25-45",
            "daily_budget": 100.0,
            "targeting": {
                "geo_locations": {"countries": ["US"]},
                "age_min": 25, "age_max": 45
            },
            "creatives": [
                {
                    "name": "素材A-红色Banner",
                    "image_url": "https://example.com/adA.jpg",
                    "title": "限时特卖 - 今日截止",
                    "body": "全场商品五折，仅限今天！"
                },
                {
                    "name": "素材B-生活场景",
                    "image_url": "https://example.com/adB.jpg",
                    "title": "千万人的选择",
                    "body": "品质生活，从这里开始。"
                }
            ]
        }
    ]
}

results = create_full_campaign(campaign_config)
print("\n创建结果:", json.dumps(results, indent=2))
```

---

## 7. 启动 / 暂停 / 删除广告

```python
def update_ad_status(object_id, new_status, object_type="ad"):
    """
    修改广告/广告组/广告系列状态
    new_status: ACTIVE / PAUSED / DELETED / ARCHIVED
    """
    url = f"{BASE_URL}/{object_id}"
    response = requests.post(url, data={
        "access_token": TOKEN,
        "status": new_status
    }).json()
    if response.get("success"):
        print(f"✓ {object_type} {object_id} 状态已更新为 {new_status}")
    else:
        print(f"✗ 更新失败: {response}")
    return response


# 启动广告
update_ad_status(ad_id, "ACTIVE", "广告")

# 暂停广告组
update_ad_status(adset_id, "PAUSED", "广告组")

# 批量启动多个广告
ad_ids = ["111", "222", "333"]
for ad_id in ad_ids:
    update_ad_status(ad_id, "ACTIVE")

# 修改广告组日预算
requests.post(f"{BASE_URL}/{adset_id}", data={
    "access_token": TOKEN,
    "daily_budget": int(200 * 100)  # 改为 200 元/天
})
```
