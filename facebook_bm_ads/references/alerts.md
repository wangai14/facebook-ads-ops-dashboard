# 广告报警通知指南

不需要每天盯后台。配置报警规则后，系统自动监控广告数据，
触发条件时通过 **飞书 / Telegram / 邮件** 推送报警。

---

## 报警规则说明

| 规则 | 默认配置 | 说明 |
|---|---|---|
| ROAS 连续低于阈值 | ROAS < 1.5，连续 2 天 | 连续多日亏损才触发，避免单日波动误报 |
| CPA 超标 | CPA > 目标 × 130% | 超出目标 30% 立即报警 |
| 花费无转化 | 花费 > $20 且转化 = 0 | 烧钱没效果，立即提醒 |

---

## 1. 配置区域

```python
"""
fb_alerts.py — Facebook 广告报警通知系统
"""

import os
import json
import time
import smtplib
import requests
import sqlite3
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===== 全局配置（按需修改）=====
ALERT_CONFIG = {
    # Facebook API
    "fb_token": os.environ.get("FB_TOKEN", "你的Token"),
    "bm_id": os.environ.get("FB_BM_ID", "你的BM_ID"),
    "ad_account_ids": [],           # 留空则自动从BM拉取

    # ── 报警规则 ──
    "rules": {
        "roas_low": {
            "enabled": True,
            "threshold": 1.5,           # ROAS 低于此值
            "consecutive_days": 2,      # 连续几天触发报警
        },
        "cpa_high": {
            "enabled": True,
            "target_cpa": 50.0,         # 你的目标 CPA（美元）
            "multiplier": 1.3,          # 超出目标多少倍 → 报警（1.3 = 超出30%）
            "min_spend": 20.0,          # 最低花费（避免小样本误报）
        },
        "spend_no_conversion": {
            "enabled": True,
            "min_spend": 20.0,          # 花费超过此值但 0 转化 → 报警
        },
    },

    # ── 通知渠道（至少配置一个）──

    # 飞书 Webhook（推荐）
    "feishu": {
        "enabled": True,
        "webhook_url": os.environ.get("FEISHU_WEBHOOK", ""),
        # 创建飞书机器人 Webhook：飞书群 → 设置 → 机器人 → 添加 → 自定义机器人
    },

    # Telegram Bot
    "telegram": {
        "enabled": False,
        "bot_token": os.environ.get("TG_BOT_TOKEN", ""),
        "chat_id": os.environ.get("TG_CHAT_ID", ""),
        # 创建Bot：@BotFather → /newbot → 获取token
        # 获取chat_id：发消息给Bot后访问 https://api.telegram.org/bot{TOKEN}/getUpdates
    },

    # 邮件（SMTP）
    "email": {
        "enabled": False,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "username": os.environ.get("EMAIL_USER", ""),
        "password": os.environ.get("EMAIL_PASS", ""),  # Gmail 使用应用专用密码
        "from_addr": "",
        "to_addrs": [],              # 收件人列表，支持多个
    },

    # 历史数据存储（用于"连续N天"检测）
    "db_path": "fb_alerts_history.db",
}
```

---

## 2. 数据抓取（复用 analytics.md 的 api_get / paginate 函数）

```python
BASE_URL = f"https://graph.facebook.com/v22.0"
TOKEN = ALERT_CONFIG["fb_token"]


def api_get(url, params, max_retries=5):
    if "access_token" not in params:
        params["access_token"] = TOKEN
    for attempt in range(max_retries):
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        if "error" in data:
            code = data["error"].get("code")
            if code in [4, 17, 32, 613]:
                time.sleep(min(300, (2 ** attempt) * 5))
                continue
            raise Exception(f"API {code}: {data['error'].get('message')}")
        return data
    raise Exception("超过最大重试次数")


def paginate(endpoint, params):
    results, url = [], f"{BASE_URL}/{endpoint}"
    current = {**params, "access_token": TOKEN}
    while url:
        data = api_get(url, current)
        results.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        current = {}
    return results


def get_ad_accounts():
    if ALERT_CONFIG["ad_account_ids"]:
        return ALERT_CONFIG["ad_account_ids"]
    accs = paginate(f"{ALERT_CONFIG['bm_id']}/owned_ad_accounts",
                    {"fields": "id,account_status", "limit": 200})
    return [a["id"] for a in accs if a.get("account_status") == 1]


def fetch_adset_daily(account_id, date_since, date_until):
    """按天抓取广告组数据"""
    return paginate(f"{account_id}/insights", {
        "fields": "adset_id,adset_name,spend,conversions,cost_per_result,purchase_roas",
        "time_range": json.dumps({"since": date_since, "until": date_until}),
        "level": "adset",
        "time_increment": 1,
        "limit": 500
    })
```

---

## 3. 历史数据库（连续N天检测）

```python
def init_db():
    """初始化 SQLite 存储历史指标（用于检测连续天数）"""
    conn = sqlite3.connect(ALERT_CONFIG["db_path"])
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            date TEXT,
            adset_id TEXT,
            adset_name TEXT,
            account_id TEXT,
            spend REAL,
            conversions REAL,
            cpa REAL,
            roas REAL,
            PRIMARY KEY (date, adset_id)
        )
    """)
    conn.commit()
    return conn


def save_daily_metrics(conn, account_id, rows):
    today = datetime.now().strftime("%Y-%m-%d")
    for row in rows:
        roas_list = row.get("purchase_roas", [])
        roas = float(roas_list[0]["value"]) if roas_list else 0.0
        conn.execute("""
            INSERT OR REPLACE INTO daily_metrics
            (date, adset_id, adset_name, account_id, spend, conversions, cpa, roas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today,
            row.get("adset_id", ""),
            row.get("adset_name", ""),
            account_id,
            float(row.get("spend", 0)),
            float(row.get("conversions", 0)),
            float(row.get("cost_per_result", 0)),
            roas
        ))
    conn.commit()


def get_consecutive_low_roas(conn, adset_id, threshold, days):
    """查询某广告组最近N天是否连续 ROAS 低于阈值"""
    rows = conn.execute("""
        SELECT date, roas FROM daily_metrics
        WHERE adset_id = ? AND spend > 5
        ORDER BY date DESC LIMIT ?
    """, (adset_id, days)).fetchall()

    if len(rows) < days:
        return False, []
    low_days = [(d, r) for d, r in rows if r < threshold]
    return len(low_days) >= days, low_days
```

---

## 4. 报警规则引擎

```python
def check_alerts(conn, account_id, today_rows):
    """检查所有规则，返回触发的报警列表"""
    alerts = []
    cfg = ALERT_CONFIG["rules"]

    for row in today_rows:
        adset_id = row.get("adset_id", "")
        adset_name = row.get("adset_name", adset_id)
        spend = float(row.get("spend", 0))
        conversions = float(row.get("conversions", 0))
        cpa = float(row.get("cost_per_result", 0))
        roas_list = row.get("purchase_roas", [])
        roas = float(roas_list[0]["value"]) if roas_list else 0.0

        # ── 规则1：ROAS 连续低于阈值 N 天 ──
        if cfg["roas_low"]["enabled"] and spend > 10:
            threshold = cfg["roas_low"]["threshold"]
            cons_days = cfg["roas_low"]["consecutive_days"]
            triggered, low_history = get_consecutive_low_roas(
                conn, adset_id, threshold, cons_days
            )
            if triggered:
                alerts.append({
                    "level": "🔴 严重",
                    "rule": "ROAS持续低于阈值",
                    "adset_name": adset_name,
                    "adset_id": adset_id,
                    "account_id": account_id,
                    "detail": (
                        f"ROAS 已连续 {cons_days} 天低于 {threshold}x\n"
                        f"今日 ROAS: {roas:.2f}x | 花费: ${spend:.2f}"
                    ),
                    "suggestion": "立即检查素材和受众，考虑暂停后更换创意重启",
                    "metrics": {"roas": roas, "spend": spend, "days": cons_days}
                })

        # ── 规则2：CPA 超出目标 N% ──
        if cfg["cpa_high"]["enabled"] and spend >= cfg["cpa_high"]["min_spend"]:
            target_cpa = cfg["cpa_high"]["target_cpa"]
            limit_cpa = target_cpa * cfg["cpa_high"]["multiplier"]
            if cpa > limit_cpa:
                overage_pct = (cpa - target_cpa) / target_cpa * 100
                alerts.append({
                    "level": "🟡 警告",
                    "rule": "CPA超出目标",
                    "adset_name": adset_name,
                    "adset_id": adset_id,
                    "account_id": account_id,
                    "detail": (
                        f"CPA ${cpa:.2f} 超出目标 ${target_cpa:.2f} 的 {overage_pct:.0f}%\n"
                        f"花费: ${spend:.2f} | 转化: {int(conversions)} 次"
                    ),
                    "suggestion": "检查落地页转化率，或暂时降低日预算避免持续浪费",
                    "metrics": {"cpa": cpa, "target_cpa": target_cpa, "overage": f"{overage_pct:.0f}%"}
                })

        # ── 规则3：花费 > 阈值 但 0 转化 ──
        if cfg["spend_no_conversion"]["enabled"]:
            min_spend = cfg["spend_no_conversion"]["min_spend"]
            if spend >= min_spend and conversions == 0:
                alerts.append({
                    "level": "🔴 严重",
                    "rule": "花费无转化",
                    "adset_name": adset_name,
                    "adset_id": adset_id,
                    "account_id": account_id,
                    "detail": (
                        f"今日花费 ${spend:.2f}，但转化次数为 0\n"
                        f"可能是像素失效、落地页崩溃或受众严重不匹配"
                    ),
                    "suggestion": "立即检查像素是否正常触发，落地页是否可访问，考虑暂停",
                    "metrics": {"spend": spend, "conversions": 0}
                })

    return alerts
```

---

## 5. 通知渠道

### 飞书（Feishu Webhook）

```python
def send_feishu(alerts):
    """发送飞书报警消息（富文本卡片格式）"""
    cfg = ALERT_CONFIG["feishu"]
    if not cfg["enabled"] or not cfg["webhook_url"]:
        return

    if not alerts:
        return

    # 构建消息正文
    lines = [f"**📢 Facebook 广告报警 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]**\n"]
    lines.append(f"共触发 {len(alerts)} 条报警\n")
    lines.append("---")

    for a in alerts:
        lines.append(f"\n{a['level']} **[{a['rule']}]** {a['adset_name']}")
        lines.append(f"• {a['detail'].replace(chr(10), chr(10)+'• ')}")
        lines.append(f"💡 建议：{a['suggestion']}")

    message = "\n".join(lines)

    # 飞书卡片消息格式
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🚨 FB广告报警 - {len(alerts)}条异常"
                },
                "template": "red" if any(a["level"].startswith("🔴") for a in alerts) else "yellow"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": message
                },
                {
                    "tag": "action",
                    "actions": [{
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看广告后台"},
                        "url": "https://www.facebook.com/adsmanager",
                        "type": "default"
                    }]
                }
            ]
        }
    }

    resp = requests.post(cfg["webhook_url"], json=payload, timeout=10)
    if resp.status_code == 200:
        print("✅ 飞书通知已发送")
    else:
        print(f"❌ 飞书发送失败: {resp.text}")
```

### Telegram Bot

```python
def send_telegram(alerts):
    """发送 Telegram 报警消息"""
    cfg = ALERT_CONFIG["telegram"]
    if not cfg["enabled"] or not cfg["bot_token"] or not cfg["chat_id"]:
        return
    if not alerts:
        return

    lines = [f"🚨 *Facebook 广告报警*\n`{datetime.now().strftime('%Y-%m-%d %H:%M')}`\n"]
    lines.append(f"共 *{len(alerts)}* 条报警\n")

    for a in alerts:
        lines.append(f"\n{a['level']} *{a['rule']}*")
        lines.append(f"📍 {a['adset_name']}")
        for line in a['detail'].split('\n'):
            lines.append(f"  {line}")
        lines.append(f"💡 {a['suggestion']}")
        lines.append("─────────────")

    text = "\n".join(lines)

    url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": cfg["chat_id"],
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }, timeout=10)

    if resp.json().get("ok"):
        print("✅ Telegram 通知已发送")
    else:
        print(f"❌ Telegram 发送失败: {resp.json()}")
```

### 邮件（SMTP）

```python
def send_email(alerts):
    """发送邮件报警"""
    cfg = ALERT_CONFIG["email"]
    if not cfg["enabled"] or not cfg["username"] or not cfg["to_addrs"]:
        return
    if not alerts:
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"[FB广告报警] {len(alerts)} 条异常 — {date_str}"

    # HTML 邮件正文
    rows_html = ""
    for a in alerts:
        color = "#ff4444" if "严重" in a["level"] else "#ff9900"
        detail_html = a['detail'].replace('\n', '<br>')
        rows_html += f"""
        <tr>
          <td style="color:{color};font-weight:bold;padding:8px">{a['level']}</td>
          <td style="padding:8px;font-weight:bold">{a['rule']}</td>
          <td style="padding:8px">{a['adset_name']}</td>
          <td style="padding:8px">{detail_html}</td>
          <td style="padding:8px;color:#0066cc">{a['suggestion']}</td>
        </tr>"""

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif">
    <h2 style="color:#cc0000">🚨 Facebook 广告报警 — {date_str}</h2>
    <p>共触发 <strong>{len(alerts)}</strong> 条报警，请及时处理：</p>
    <table border="1" cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%">
      <thead style="background:#f0f0f0">
        <tr>
          <th style="padding:8px">级别</th>
          <th style="padding:8px">规则</th>
          <th style="padding:8px">广告组</th>
          <th style="padding:8px">详情</th>
          <th style="padding:8px">建议</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p style="margin-top:20px">
      <a href="https://www.facebook.com/adsmanager" style="color:#0066cc">→ 打开广告管理器</a>
    </p>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"] or cfg["username"]
    msg["To"] = ", ".join(cfg["to_addrs"])
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
            server.starttls()
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["username"], cfg["to_addrs"], msg.as_string())
        print(f"✅ 邮件已发送至 {cfg['to_addrs']}")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")


def send_all_notifications(alerts):
    """统一触发所有已启用的通知渠道"""
    if not alerts:
        print("✅ 无报警触发，一切正常")
        return
    send_feishu(alerts)
    send_telegram(alerts)
    send_email(alerts)
```

---

## 6. 主程序入口

```python
def run_with_mock_alerts():
    """Mock 测试模式 —— 不需要真实 Token"""
    print("🧪 报警测试模式\n")
    mock_alerts = [
        {
            "level": "🔴 严重", "rule": "ROAS持续低于阈值",
            "adset_name": "美国-25-45岁-转化", "adset_id": "AS001", "account_id": "act_test",
            "detail": "ROAS 已连续 2 天低于 1.5x\n今日 ROAS: 0.82x | 花费: $143.50",
            "suggestion": "立即检查素材和受众，考虑暂停后更换创意重启",
            "metrics": {"roas": 0.82, "spend": 143.5, "days": 2}
        },
        {
            "level": "🟡 警告", "rule": "CPA超出目标",
            "adset_name": "英国-再营销", "adset_id": "AS002", "account_id": "act_test",
            "detail": "CPA $78.00 超出目标 $50.00 的 56%\n花费: $234.00 | 转化: 3 次",
            "suggestion": "检查落地页转化率，或暂时降低日预算避免持续浪费",
            "metrics": {"cpa": 78, "target_cpa": 50, "overage": "56%"}
        },
        {
            "level": "🔴 严重", "rule": "花费无转化",
            "adset_name": "德国-新客冷启", "adset_id": "AS003", "account_id": "act_test",
            "detail": "今日花费 $35.20，但转化次数为 0\n可能是像素失效、落地页崩溃或受众严重不匹配",
            "suggestion": "立即检查像素是否正常触发，落地页是否可访问，考虑暂停",
            "metrics": {"spend": 35.2, "conversions": 0}
        }
    ]
    # 打印报警摘要
    for a in mock_alerts:
        print(f"{a['level']} [{a['rule']}] {a['adset_name']}")
        print(f"  {a['detail'].split(chr(10))[0]}")
        print(f"  → {a['suggestion']}\n")

    print("\n发送通知...")
    send_all_notifications(mock_alerts)


def main():
    import sys
    if "--test" in sys.argv:
        run_with_mock_alerts()
        return

    print(f"🔔 FB 广告报警检查 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    conn = init_db()
    accounts = get_ad_accounts()
    all_alerts = []

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    lookback = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    for acc_id in accounts:
        print(f"  检查账户: {acc_id}")
        try:
            rows = fetch_adset_daily(acc_id, lookback, yesterday)
            # 只保存今天（昨天）的数据
            today_rows = [r for r in rows if r.get("date_start") == yesterday]
            save_daily_metrics(conn, acc_id, today_rows)
            alerts = check_alerts(conn, acc_id, today_rows)
            all_alerts.extend(alerts)
        except Exception as e:
            print(f"  ❌ 失败: {e}")

    conn.close()
    print(f"\n共触发 {len(all_alerts)} 条报警")
    send_all_notifications(all_alerts)


if __name__ == "__main__":
    main()
```

---

## 7. 快速配置指南

### 飞书 Webhook 配置步骤

1. 打开飞书群 → **设置** → **群机器人** → **添加机器人**
2. 选择 **自定义机器人** → 填写名称（如"FB广告报警"）
3. 复制生成的 **Webhook URL**
4. 填入 `ALERT_CONFIG["feishu"]["webhook_url"]`

### Telegram Bot 配置步骤

1. 在 Telegram 搜索 **@BotFather** → 发送 `/newbot`
2. 按提示命名，获得 **Bot Token**（格式：`123456:ABCdef...`）
3. 向 Bot 发送任意消息，然后访问：
   ```
   https://api.telegram.org/bot{TOKEN}/getUpdates
   ```
4. 从响应中找到 `"chat":{"id":...}` 即为 **Chat ID**

### Gmail 配置步骤

1. Google 账户 → **安全性** → **两步验证** → **应用专用密码**
2. 生成密码，填入 `ALERT_CONFIG["email"]["password"]`
3. `smtp_host` 填 `smtp.gmail.com`，`smtp_port` 填 `587`

---

## 8. 定时运行

### Windows 任务计划（每天 8:00 运行）

```powershell
schtasks /create /tn "FB广告报警" /tr "python d:\scripts\fb_alerts.py" /sc daily /st 08:00
```

### Linux / Mac cron（每天 8:00）

```bash
0 8 * * * /usr/bin/python3 /path/to/fb_alerts.py >> /var/log/fb_alerts.log 2>&1
```

### 测试发送（无需真实数据）

```bash
python fb_alerts.py --test
```
