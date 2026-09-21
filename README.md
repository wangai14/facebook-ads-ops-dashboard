这个项目的本质是一个 Facebook / Meta 广告运营工作台，把“拉数据、看数据、诊断问题、执行操作”放在同一个本地面板里。它不只是看报表，还包含一套 facebook_bm_ads Skill。
主要作用
- 自动拉广告数据：支持今天、昨天、近 7 天、近 30 天和自定义日期范围。
- 多层级查看：可以从广告账户、系列、广告组、广告、素材几个层级查看表现。
- 核心指标汇总：花费、展示、点击、CTR、CPC、购买、收入、ROAS、CPA、加购、结账和转化漏斗。
- 广告诊断：识别有点击无加购、花费无单、ROAS 偏低、素材疲劳、衰退系列等问题。
- 每日运营决策：给出放量、降预算、检查承接、暂停广告或继续观察等建议。
- 订单对账：可以录入店铺后台订单数，与 Facebook 归因订单对比，查看差异。
- 一键关闭系列：设置“无单花费超过多少美元”后，筛选并批量暂停对应系列。
- 一键复制优质系列：筛选满足 ROAS、购买、花费等条件的系列，复制成默认暂停的新系列。
- 交互查看广告：点击广告行或卡片后，可以查看该条广告的详细指标、诊断原因和建议动作。
- 自动刷新：支持定时同步当前日期范围的数据，并按设定周期自动更新面板。
- 附带 FB BM Skill：包含账号、Insights、Campaign、受众、素材、自动投放、报警、扩量和关停判断等文档与拉数脚本。
它适合解决什么问题
- 每天快速判断哪些广告该关、哪些该加预算。
- 对比 Facebook 后台订单和店铺后台订单。
- 把广告数据从多个账户汇总到一个面板。
- 让运营不用逐个进入 Ads Manager 查系列和广告。
- 把重复的拉数、诊断和暂停动作自动化。
它不是什么
- 不是 Facebook 官方产品，而是一个通过 Meta Marketing API 拉数的本地工具。
- 不是完全实时数据，Meta API 本身存在归因延迟、缓存和统计口径差异。
- 必须有 Meta Access Token 才能拉真实数据。
- 关闭和复制系列是真实写操作，需要 ads_management 权限。
- Facebook 归因订单和店铺后台订单本来就可能不一致，不能简单认为面板数据一定“错了”。
# Facebook Ads Operations Dashboard

开源的 Facebook / Meta 广告数据拉取、诊断和日常投放决策面板。项目包含可视化面板与 `facebook_bm_ads` 分析 Skill，支持多广告账户、系列/广告组/广告层级分析、订单对账、止损提示和优质系列复制。

## 功能

- 从 Meta Marketing API 拉取今天、昨天、近 7 天和近 30 天数据
- 汇总花费、购买、收入、ROAS、CPA、CTR 和漏斗数据
- 按账户、Campaign、Adset、广告和素材家族查看表现
- 给出放量、降预算、查承接和风险提示
- 一键筛选无单花费系列并执行关闭
- 筛选优质系列并复制为默认暂停的新系列
- 输入店铺后台订单数，对比 Facebook 归因订单
- 自带 Facebook BM Ads Skill 文档和拉数脚本

## 环境要求

- Python 3.10+
- Meta Access Token
- Token 至少具备 `ads_read`；关闭或复制系列还需要 `ads_management`

## Windows 快速启动

```powershell
git clone https://github.com/sosoveooo-bit/facebook-ads-ops-dashboard.git
cd facebook-ads-ops-dashboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r facebook_ads_monitor\requirements.txt
New-Item -ItemType Directory -Force data | Out-Null
Set-Content -Path data\facebook_token.txt -Value "YOUR_META_ACCESS_TOKEN"
python -m facebook_ads_monitor.server --host 127.0.0.1 --port 8788
```

然后打开 [http://127.0.0.1:8788/](http://127.0.0.1:8788/)。

## macOS / Linux 快速启动

```bash
git clone https://github.com/sosoveooo-bit/facebook-ads-ops-dashboard.git
cd facebook-ads-ops-dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r facebook_ads_monitor/requirements.txt
mkdir -p data
printf '%s' 'YOUR_META_ACCESS_TOKEN' > data/facebook_token.txt
python -m facebook_ads_monitor.server --host 127.0.0.1 --port 8788
```

## 配置

默认路径都相对于仓库根目录：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `FB_ADS_TOKEN_PATH` | `data/facebook_token.txt` | Meta Token 文件 |
| `FB_ADS_REPORT_ROOT` | `data/reports/fb_pull_report` | 拉取报表目录 |
| `FB_ADS_SKILL_ROOT` | `facebook_bm_ads` | Skill 目录 |
| `FB_ADS_PULL_TIMEOUT_SECONDS` | `1800` | 单次拉取超时秒数 |

PowerShell 临时覆盖示例：

```powershell
$env:FB_ADS_TOKEN_PATH = "D:\secrets\facebook_token.txt"
$env:FB_ADS_REPORT_ROOT = "D:\facebook-reports"
python -m facebook_ads_monitor.server --port 8788
```

## 仅运行 Skill 拉数

```powershell
python facebook_bm_ads\scripts\fb_pull_report.py `
  --token-path data\facebook_token.txt `
  --date-preset yesterday `
  --no-auto-backfill
```

本地自测不需要 Token：

```powershell
python facebook_bm_ads\scripts\fb_pull_report.py --mock
```

## 安全说明

- Token 和拉取后的广告数据均被 `.gitignore` 排除。
- 公开仓库中只包含代码、示例配置与文档。
- 关闭和复制系列属于真实 Meta API 写操作，面板执行前会要求确认。

## License

[MIT](LICENSE)

