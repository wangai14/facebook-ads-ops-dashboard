# 广告素材 (Creative) 管理指南

## 素材类型概览

| 类型 | 说明 | 推荐尺寸 |
|---|---|---|
| 单图广告 | 单张图片 | 1080×1080 (1:1) 或 1200×628 (1.91:1) |
| 单视频广告 | 单个视频 | 1080×1080 或 1920×1080 |
| 轮播广告 | 多张图/视频轮播 | 每张 1080×1080 |
| 动态广告 (DPA) | 商品目录自动匹配 | 需要上传商品目录 |
| 故事广告 | 全屏竖向 | 1080×1920 (9:16) |
| 合集广告 | 封面+商品网格 | 封面 1200×628 |

---

## 1. 上传图片并获取 image_hash

```python
import requests

TOKEN = "你的Token"
AD_ACCOUNT_ID = "act_123456789"
BASE_URL = "https://graph.facebook.com/v22.0"


def upload_image_from_url(image_url, name="uploaded_image"):
    """从 URL 上传图片到广告账户图库"""
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/adimages"
    response = requests.post(url, data={
        "access_token": TOKEN,
        "url": image_url,
        "name": name
    }).json()
    
    if "error" in response:
        raise Exception(f"图片上传失败: {response['error']}")
    
    # 返回格式：{"images": {"filename": {"hash": "xxx", ...}}}
    images = response.get("images", {})
    for filename, info in images.items():
        print(f"✓ 图片上传成功: hash={info['hash']}")
        return info["hash"]


def upload_image_from_file(file_path):
    """从本地文件上传图片"""
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/adimages"
    with open(file_path, "rb") as f:
        response = requests.post(url, data={"access_token": TOKEN},
                                 files={"filename": f}).json()
    images = response.get("images", {})
    for filename, info in images.items():
        return info["hash"]


# 使用 image_hash 创建素材（比 image_url 更稳定）
image_hash = upload_image_from_url("https://example.com/banner.jpg")
```

---

## 2. 单图广告素材

```python
import json

def create_single_image_creative(name, image_hash, title, body, link_url,
                                  description="", cta="SHOP_NOW", page_id=None):
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/adcreatives"
    
    link_data = {
        "image_hash": image_hash,
        "link": link_url,
        "message": body,        # 正文（帖子文案）
        "name": title,          # 标题
        "description": description,
        "call_to_action": {
            "type": cta,
            "value": {"link": link_url}
        }
    }
    
    object_story_spec = {"link_data": link_data}
    if page_id:
        object_story_spec["page_id"] = page_id
    
    response = requests.post(url, data={
        "access_token": TOKEN,
        "name": name,
        "object_story_spec": json.dumps(object_story_spec)
    }).json()
    
    if "error" in response:
        raise Exception(f"素材创建失败: {response['error']}")
    return response["id"]
```

---

## 3. 轮播广告素材

```python
def create_carousel_creative(name, cards, link_url, body, cta="SHOP_NOW", page_id=None):
    """
    cards 格式：
    [
        {"image_hash": "xxx", "title": "商品A", "description": "价格 $10", "link": "https://..."},
        {"image_hash": "yyy", "title": "商品B", "description": "价格 $20", "link": "https://..."},
    ]
    """
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/adcreatives"
    
    child_attachments = []
    for card in cards:
        attachment = {
            "link": card.get("link", link_url),
            "name": card["title"],
            "description": card.get("description", ""),
            "call_to_action": {"type": cta, "value": {"link": card.get("link", link_url)}}
        }
        if "image_hash" in card:
            attachment["image_hash"] = card["image_hash"]
        elif "image_url" in card:
            attachment["picture"] = card["image_url"]
        child_attachments.append(attachment)
    
    object_story_spec = {
        "link_data": {
            "link": link_url,
            "message": body,
            "child_attachments": child_attachments,
            "multi_share_optimized": True,  # 允许 FB 自动优化卡片顺序
            "call_to_action": {"type": cta, "value": {"link": link_url}}
        }
    }
    if page_id:
        object_story_spec["page_id"] = page_id
    
    response = requests.post(url, data={
        "access_token": TOKEN,
        "name": name,
        "object_story_spec": json.dumps(object_story_spec)
    }).json()
    
    if "error" in response:
        raise Exception(f"轮播素材创建失败: {response['error']}")
    return response["id"]


# 示例
carousel_creative_id = create_carousel_creative(
    name="夏季商品轮播",
    body="🌞 夏季新品上架，点击查看！",
    link_url="https://example.com/summer",
    cta="SHOP_NOW",
    page_id="你的主页ID",
    cards=[
        {"image_hash": "hash1", "title": "连衣裙 $39", "description": "多色可选", "link": "https://example.com/dress"},
        {"image_hash": "hash2", "title": "凉鞋 $29", "description": "舒适透气", "link": "https://example.com/sandal"},
        {"image_hash": "hash3", "title": "泳衣 $49", "description": "专业防晒", "link": "https://example.com/swimsuit"},
    ]
)
```

---

## 4. 视频广告素材

### 上传视频

```python
def upload_video(video_path_or_url, title=""):
    """上传视频文件"""
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/advideos"
    
    if video_path_or_url.startswith("http"):
        # 从 URL 上传
        response = requests.post(url, data={
            "access_token": TOKEN,
            "file_url": video_path_or_url,
            "title": title
        }).json()
    else:
        # 从本地文件上传（大文件需要分块上传）
        with open(video_path_or_url, "rb") as f:
            response = requests.post(url, data={"access_token": TOKEN, "title": title},
                                     files={"source": f}).json()
    
    if "error" in response:
        raise Exception(f"视频上传失败: {response['error']}")
    
    video_id = response["id"]
    print(f"✓ 视频上传成功: {video_id}")
    
    # 等待视频处理完成
    wait_for_video_ready(video_id)
    return video_id


def wait_for_video_ready(video_id, timeout=300):
    """等待视频处理完成"""
    import time
    start = time.time()
    while time.time() - start < timeout:
        status = requests.get(f"{BASE_URL}/{video_id}",
                              params={"access_token": TOKEN, "fields": "status"}).json()
        video_status = status.get("status", {}).get("video_status")
        print(f"视频状态: {video_status}")
        if video_status == "ready":
            return True
        elif video_status in ["error", "expired"]:
            raise Exception(f"视频处理失败: {status}")
        time.sleep(10)
    raise Exception("视频处理超时")


def create_video_creative(name, video_id, thumbnail_url, title, body, link_url,
                           cta="LEARN_MORE", page_id=None):
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/adcreatives"
    
    object_story_spec = {
        "video_data": {
            "video_id": video_id,
            "image_url": thumbnail_url,   # 封面图
            "title": title,
            "message": body,
            "link_description": "点击了解更多",
            "call_to_action": {
                "type": cta,
                "value": {"link": link_url}
            }
        }
    }
    if page_id:
        object_story_spec["page_id"] = page_id
    
    response = requests.post(url, data={
        "access_token": TOKEN,
        "name": name,
        "object_story_spec": json.dumps(object_story_spec)
    }).json()
    
    if "error" in response:
        raise Exception(f"视频素材创建失败: {response['error']}")
    return response["id"]
```

---

## 5. 动态广告素材 (Asset Feed / ACO)

适合 A/B 测试——上传多个标题、文案、图片，Facebook 自动组合投放最佳版本：

```python
def create_dynamic_creative(name, image_hashes, titles, bodies, link_url,
                              descriptions=None, cta="SHOP_NOW", page_id=None):
    """
    动态广告素材 (Asset Feed)
    Facebook 会自动测试不同图片+标题+文案的组合，找出效果最好的
    """
    url = f"{BASE_URL}/{AD_ACCOUNT_ID}/adcreatives"
    
    asset_feed_spec = {
        "images": [{"hash": h} for h in image_hashes],
        "titles": [{"text": t} for t in titles],
        "bodies": [{"text": b} for b in bodies],
        "link_urls": [{"website_url": link_url}],
        "call_to_action_types": [cta]
    }
    if descriptions:
        asset_feed_spec["descriptions"] = [{"text": d} for d in descriptions]
    
    data = {
        "access_token": TOKEN,
        "name": name,
        "asset_feed_spec": json.dumps(asset_feed_spec)
    }
    if page_id:
        data["object_story_spec"] = json.dumps({"page_id": page_id})
    
    response = requests.post(url, data=data).json()
    if "error" in response:
        raise Exception(f"动态素材创建失败: {response['error']}")
    return response["id"]


# 示例：3张图 × 3个标题 × 2段文案 = 18种组合
dynamic_creative_id = create_dynamic_creative(
    name="动态测试素材-夏促",
    image_hashes=["hash_红色", "hash_蓝色", "hash_生活场景"],
    titles=["限时五折", "爆款热销中", "千万人的选择"],
    bodies=["今天下单立减50%", "数量有限，抢完即止", "品质保证，满意退款"],
    descriptions=["免费配送", "7天无理由退换"],
    link_url="https://example.com/sale",
    cta="SHOP_NOW",
    page_id="你的主页ID"
)
```

---

## 6. 预览广告素材

```python
def preview_creative(creative_id, ad_format="DESKTOP_FEED_STANDARD"):
    """
    获取广告预览链接
    ad_format 常用值：
      DESKTOP_FEED_STANDARD  — 桌面端动态
      MOBILE_FEED_STANDARD   — 移动端动态
      INSTAGRAM_STANDARD     — Instagram 动态
      INSTAGRAM_STORY        — Instagram 故事
      FACEBOOK_STORY_MOBILE  — Facebook 故事
    """
    url = f"{BASE_URL}/{creative_id}/previews"
    response = requests.get(url, params={
        "access_token": TOKEN,
        "ad_format": ad_format
    }).json()
    
    for preview in response.get("data", []):
        print(f"预览 ({ad_format}):")
        # body 中包含 iframe HTML，可嵌入网页中预览
        print(preview.get("body", "")[:200])
    return response


preview_creative(dynamic_creative_id, "MOBILE_FEED_STANDARD")
```

---

## 常见 CTA 类型速查

| CTA 类型 | 显示文字 | 适用场景 |
|---|---|---|
| `SHOP_NOW` | 立即购买 | 电商 |
| `LEARN_MORE` | 了解详情 | 品牌/内容 |
| `SIGN_UP` | 立即注册 | 获客 |
| `CONTACT_US` | 联系我们 | B2B/服务 |
| `BOOK_NOW` | 立即预订 | 旅游/餐饮 |
| `GET_OFFER` | 领取优惠 | 促销 |
| `SUBSCRIBE` | 立即订阅 | 会员/新闻 |
| `DOWNLOAD` | 立即下载 | App |
| `APPLY_NOW` | 立即申请 | 金融/教育 |
| `WATCH_MORE` | 观看更多 | 视频 |
| `GET_DIRECTIONS` | 获取路线 | 本地商家 |
| `SEND_MESSAGE` | 发送消息 | 私信/对话 |
