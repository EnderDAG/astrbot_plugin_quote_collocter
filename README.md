# 语录收集器 · quote_collocter

> **V3.0.0**：3.0 里程碑版本 · 仓库：[EnderDAG/astrbot_plugin_quote_collocter](https://github.com/EnderDAG/astrbot_plugin_quote_collocter)

> AstrBot 群聊语录插件：投稿截图、随机鞭尸、WebUI 管理、一键语义化、AI 语义召回、人物档案（pid 管理）。
>
> 当前版本：**v3.0.0**　·　AstrBot：`>=4.17,<5`　·　作者：enderdag（基于上游 `litsum` 二次开发）

群友又爆典了？截图发一句「语录投稿」存下来，以后被戳一戳、被 AI 点名、或者聊天聊到某个话题时，再把它翻出来「鞭尸」。

---

## 协作维护（v2.19+，可选）

**AstrBot 管理员**可以在群里用「/维护」添加维护成员，也可以在管理页「07 协作维护」里直接管理成员、生成邀请（7 / 30 / 90 天或长期）、吊销令牌、查看并撤销操作（v3.0.7 起群内 `/维护` 仅限 AstrBot 管理员，QQ 群主/群管理员与维护成员不再能执行群内维护命令）。成员打开独立协作页后，可以处理**语录归属、限制级标记、标签、语义队列**，所有操作都写入审计日志（支持一键撤销）。协作页通过邀请制令牌登录，与 AstrBot 管理后台完全隔离；一个维护者可授权多个群，登录后可切换。（v3.0.3 起协作页不再出现在仪表盘的插件页面列表中，只通过邀请链接访问。）

```
/维护 名单               查看维护成员（仅 AstrBot 管理员）
/维护 添加 <QQ>          添加维护员
/维护 移除 <QQ>          移除维护员
/维护 邀请 <QQ>          生成邀请链接（会自动私聊发送）
/维护 日志 [条数]        查看审计
/维护 关闭               吊销本群全部邀请
/限制级 开 | /限制级 关   本群是否允许发送限制级语录（默认关）
```

**协作页外网地址**：协作服务只监听 `127.0.0.1:6190`，需要由反向代理或内网穿透暴露到公网。部署后在管理页「07 协作维护 → 协作页外网地址」填入公开地址（例如 `https://your-domain.com/quote-collab/`），邀请链接才会带上完整 URL。nginx 示例：

```nginx
location /quote-collab/ {
    proxy_pass http://127.0.0.1:6190/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```
> 注意：这个 `location` 必须写在已有的 `listen 80; server_name <你的域名/IP>;` 的 `server` 块里。如果新开一个 `server_name` 相同的 `server` 块，nginx 只会用先加载的那个，`/quote-collab/` 会 404。


---

## 功能一览

- **投稿与随机发送**：`语录投稿+图片` / 引用图片 + `语录投稿` 入库；`/语录` 随机抽一张；被戳一戳时按概率随机发图。
- **WebUI 管理页**（v2.0+）：群列表、缩略图网格、搜索 / 排序 / 分页、批量删除、跨群移动、群设置。
- **一键语义化**（v2.1+）：视觉模型生成图片描述（`caption` / `tags` / `tone` / `speaker` / `visible_text`），向量模型建索引，支持自然语言检索。
- **发送记忆**（v2.2+）：机器人发过的语录会注入它自己的对话上下文，能接梗、引用、自嘲。
- **AI 语义召回**（v2.4+，v2.12.3 起工具合并为 `quote`）：AI 可调用 `quote(action="recall")` 检索本群语录，并用 `&&image_xxx.jpg&&` 标记随回复发图；标记只认图片 id，无效标记会记录原文；可开启「没写标记时自动补发 top1」。
- **人物档案**（v2.5+）：按 QQ 号记录昵称历史与头像历史（dHash 指纹），换昵称 / 换头像后仍能认出同一个人；支持以图找人、合并 / 拆分身份。
- **按「被拍的人」归档**（v2.6+）：视觉识别截图里的说话人，自动匹配群成员档案；可手动指定归属、批量回填、查看某人的全部语录。
- **昵称别名表**（v2.7+）：截图里读错 / 形近的昵称直接映射到 QQ 号，不再污染群名片历史；「待确认归属」可一键归并形近变体。
- **群昵称称呼**（v2.8+）：AI 提到语录人物时使用群昵称（群名片优先），不输出 QQ 号或数字 ID。
- **语录统计**（v2.9+）：管理页「语录统计」与群命令 `/语录排行`，按人物合并统计语录数量、投稿数量、30 天趋势；v2.12.2 起支持按月（`/语录排行 本月` / `上月`）。
- **稳定 pid**（v2.10+）：人物档案统一用 `pid_0001` 形式的编号管理，改名 / 换号 / 合并后记录仍归在同一个 pid 下。
- **更新推送**（v2.9.4+，v3.0.1 起默认关闭）：需在管理页显式配置目标群与 DSH 桥接 token；版本更新后经桥接推送更新日志，并在该群 AI 上下文注入近况提示（v2.9.5+）。
- **身份自动同步**（v2.9.3+）：默认每 24 小时同步一次群成员昵称、群名片与头像，周期可调（1–168 小时）或暂停。
- **全文检索与组合筛选**（v2.13+）：管理页搜索走 SQLite FTS5 索引（中文二元组），可按人物、标签、时间范围叠加筛选。
- **回收站**（v2.13+）：删除语录先进入回收站，可恢复或彻底删除；保留天数在群设置里调整，过期自动清理。
- **自动打标签队列**（v2.13+）：后台用视觉模型为新语录补 `tags`，队列可暂停/恢复，群设置里可关闭自动打标签。
- **俗名学习**（v2.15+）：从群聊里低频学习群友俗名/外号，生成「待确认俗名」候选；在「语录人物」页确认后写入别名表，之后归属识别与 AI 点名都能用这个称呼找到人。v3.0.5 起只记录最近消息里实际出现过的称呼（忽略 @ 提及与引用内容），候选列表会显示出现次数。已确认的俗名会成为 AI 称呼该群友的首选：AI 提到人物时优先用俗名，而不是原始群昵称（v3.0.6+）。
- **自动语义化**（v2.16+）：后台默认每 24 小时为尚未语义化的新语录补齐描述与向量，周期可在群设置调整（1–168 小时）或关闭。
- **称呼优先级与重填归属**（v2.16+）：展示与归属按「确认俗名 → 群名片 / QQ 当前昵称」取名；设置面板的「重填全部语录归属」可一次性刷新全部归属与语义 speaker。

---

## 快速开始

1. 把插件目录放到 AstrBot 的 `data/plugins/quote_collocter/`（或在插件市场安装）。
2. 依赖：AstrBot 自带的 `aiohttp`、`PyYAML`、`Pillow`（缺少 Pillow 时缩略图 / 头像处理不可用，其它功能不受影响）。
3. 重载插件（或在仪表盘插件页点「重载」）。
4. 群里让管理员发送「投稿权限+2」开启全员投稿。
5. 打开仪表盘 →「插件」→「语录收集器」→「语录管理」进入 WebUI。

---

## 群内命令

| 命令 | 说明 | 权限 |
| --- | --- | --- |
| `语录投稿` + 图片 | 保存当前图片 | 取决于 `mode` |
| 引用图片后发 `语录投稿` | 保存被引用消息里的图片 | 取决于 `mode` |
| `/语录` 或 `语录` | 随机发一张本群语录 | 所有人 |
| `/语录排行 [N]` / `语录排行` / `/语录统计` / `语录统计` | 查看本群语录数量排名，`N` 取 3–30，默认 10 | 所有人 |
| `/语录排行 本月` / `/语录排行 上月` | 按月查看语录数量与投稿排名（可再带条数） | 所有人 |
| `/语录 [@某人\|关键词] [N]` | 随机发一张；点名或关键词时从该人物/相关语录中取，`N` 最多 9 | 所有人 |
| `/语录详情 <序号\|图片名>` | 查看单条语录详情（人物、时间、投稿人、语义描述） | 所有人 |
| `/合集 [名称] [N]` | 随机发合集里的一张图；带 `N` 连发 N 张（最多 9 张） | 所有人 |
| `/周报` | 本周语录周报（表格图片，带头像；`/周报 上周` 看上一周） | 所有人 |
| `/年度报告 [@某人\|昵称] [年份]` | 生成某人当年 Wrapped 风格年度语录报告图片（默认本人、当年） | 所有人 |
| `投稿权限` + 数字 | 0=关闭投稿；1=仅 bot 管理员；2=所有人 | bot 管理员 |
| `戳戳冷却` + 秒数 | 设置戳一戳发图的冷却时间 | bot 管理员 |

被戳一戳时会先按 `poke_prob`（默认 0.85）判定是否发图，再受冷却限制。

---

## v2.12 新功能

- **专题合集**：管理页右上角「专题合集」可新建/重命名/删除合集，把勾选的语录批量加入或移除；群内 `/合集 名称` 随机发图。
- **每周语录周报**：「语录统计」弹窗底部可设置星期、整点、推送群并启用自动推送，也可「立即推送一次」；周报以表格图片形式发送，包含本周新增、参与人数、人物排行榜（带头像）、投稿人、热词；群内 `/周报` 也能随时看本周，`/周报 上周` 看上一周。
- **数据可视化**：管理页「数据可视化」可看时段热力图（星期 × 小时）、最近 26 周发帖日历、人物时间线（逐月条形 + 标签画像），并可预览/下载年度报告图片。
- **AI 侧**：`quote` 工具支持 `action=recall|stats|weekly`；recall 支持人物点名，候选精简到 3 条并带最近发送记忆，另有 5 分钟召回缓存。

- **限制级规则（v2.18+）**：低俗、不适合直接发群的语录可标为「限制级」，页面默认只展示/随机发送非限制级语录，AI 召回也会跳过限制级；`/限制级` 可显式查看。

### v2.20.3 协作维护

角色已合并为「维护员」；协作页查看面板可直接改标签（逗号分隔），也可恢复语义标签，改动可审计撤销。

## 管理页面

仪表盘插件页里的「语录管理」（v2.17.0 起改版，v2.17.6 细化）采用「左侧模块导航 + 独立圆角卡片模块」结构，配色、字体、渐变与圆角参数直接取自模板 PPT 的主题参数（lime `#D0E516`、纸感 `#FBF5ED`、墨黑 `#111111`，主字体思源黑体 CN Heavy）：

| 模块 | 内容 |
| --- | --- |
| 01 语录库 | 群列表、语义化状态带、检索/筛选/排序工具条、语录网格、批量操作 |
| 02 语录人物 | 人物列表与详情、俗名候选、身份同步、以图找人、合并/拆分、待确认归属、整理旧别名 |
| 03 语录统计 | 总量卡片、人物语录数量排行、投稿人排行、30 天趋势、各群概览、每周周报设置 |
| 04 专题合集 | 新建/编辑合集、把已选语录加入合集、合集成图片预览 |
| 05 数据可视化 | 时段热力图（含星期/时段分布）、发帖日历、人物时间线、年度报告预览 |
| 06 回收站 | 已删语录列表、恢复 / 彻底删除 / 清空回收站 |
| 07 协作维护 | 维护成员、邀请令牌（可长期）、审计日志与撤销 |

各模块从左侧 rail 或快捷键打开，打开时自动收起其他模块；按 `Esc` 关闭。旧版包含：

- **左侧群列表**：各群语录数量、投稿权限、最近投稿时间，点击切换群。
- **顶部工具条**：搜索（文件名 / 投稿人 / 标签，也可切「语义搜索」）、排序、每页条数、全选 / 清空、批量移动 / 删除。
- **语录网格**：缩略图懒加载，卡片显示投稿人、归属人物、时间；点击查看原图与元数据；可单条指定 / 清除归属。
- **群设置面板**：投稿权限、戳戳冷却、戳戳发图概率、`remember`、`recall`、`auto_recall`、清空本群语录。
- **语义化工具条**：显示向量模型与维度、各状态数量、实时进度，可取消任务、清空本群索引。
- **语录统计**（v2.9+）：总量、归属率、语义化覆盖率、占用空间、最近 30 天新增、各群概览、人物语录数量排名与投稿人排名。
- **语录人物**（v2.5+）：人物列表（显示 `pid` 与 QQ 数量）、详情（昵称历史、所在群、头像墙）、以图找人、合并 / 拆分、待确认归属、整理旧别名、自动同步设置。
- **更新推送设置**：配置目标群与 DSH 桥接 token（默认关闭、没有内置群号）、查看最近推送结果、保存配置或发送测试推送。
- **发送记忆**：查看 / 清空机器人发过的语录记忆。

页面在 sandbox iframe 中运行，所有破坏性操作使用页面内自绘确认框（不受 `window.confirm` 拦截影响）。

---

## AI 能力

### 工具

| 工具 | 作用 |
| --- | --- |
| `quote(action="recall", query)` | 语义检索本群语录，返回最多 3 个候选（仅 `id` / `who` / `caption` / `tags`，必要时 `via` / `sent_ago`）与最近已发过的图；query 里带 QQ 号或人物昵称时优先取该人物名下语录（`via=person`）。 |
| `quote(action="stats", limit?)` | 读取语录统计，按人物（pid）合并多个昵称，返回总量、人物排名、投稿人排行与趋势。 |
| `quote(action="weekly", offset?)` | 读取每周语录周报（`offset=-1` 为上周）。 |

### 回复标记

模型在回复中写 `&&image_1761753966459.jpg&&`，插件在 `on_decorating_result` 阶段替换为真实图片：

- 只识别 `image_*` 图片 id；文件必须存在于当前群目录。
- 无效标记会被移除并记录原文，不会让整条消息丢失。
- 群设置 `auto_recall=true` 时，模型忘写标记会兜底补发 top1。
- 发出的语录同时写入「发送记忆」。

### 上下文注入

`on_llm_request` 阶段会按需注入：

- 本会话最近发过的语录（发送记忆，最多 5 条 / 6 小时 / 每次注入 4 条）。
- 当前群最近一次更新推送的近况（版本、时间、要点，2 小时内有效），让 AI 能接住「刚才那个更新是什么」这类追问。
- 召回提示（`RECALL_REMIND_HEAD` 等），约束标记格式与发送行为。

---

## 人物识别与 pid

识别优先级（v2.9.2+）：

1. **QQ 号**：query 中出现 5–12 位数字且命中档案，直接取该人物。
2. **昵称历史**：该 QQ 用过的群名片 / 昵称（最近 12 个）做子串匹配。
3. **别名表**：`confirmed` 且未屏蔽的别名（截图里的各种写法）。
4. **形近匹配**：同群优先，长度差 ≤1–2 的形近字做兜底（高于阈值才启用）。

识别后会展开到同一 `pid` 下的所有 QQ 号，再取这些 QQ 名下已归属的语录。

- 群头衔 / LV 等级 / 管理员徽章会被忽略并进入屏蔽词（v2.9.1）。
- 别名有 `confirmed` 标记：手工 / 合并来源可信，`migrated` 来源需形近比对 ≥0.75。
- 每个 person 分配稳定 `pid_0001` 编号（v2.10），合并保留存活者 pid，拆分分配新 pid。

---

## 数据与目录结构

### 代码模块（v2.10.1 起拆分）

| 文件 | 行数 | 职责 |
| --- | --- | --- |
| `quote_core.py` | ~520 | 常量、路径与安全校验、群设置、元数据 / 缩略图基础工具 |
| `quote_identity.py` | ~1770 | 人物档案 `IdentityStore`：昵称 / 头像历史、别名、屏蔽词、pid、群成员同步、合并 / 拆分、清理 |
| `quote_announce.py` | ~320 | 更新推送：CHANGELOG 解析、推送文案、白名单、桥接配置、上下文摘要 |
| `quote_semantic.py` | ~860 | 一键语义化：视觉描述 + 向量索引、进度、检索 |
| `quote_sent.py` | ~360 | 发送记忆：记录 / 注入机器人发过的语录 |
| `quote_views.py` | ~230 | 图片读取、缩略图、列表载荷 |
| `quote_stats.py` | ~350 | 统计聚合：总量、人物排名、投稿人排名、趋势 |
| `quote_recall.py` | ~320 | AI 召回：候选构建、`&&标记&&` 解析与替换 |
| `main.py` | ~3070 | 插件类 `Quote_Plugin`：事件、Web API、AI 工具、群命令、定时任务 |

依赖方向：所有模块 `from quote_core import *`，`quote_core` 不反向依赖其它模块；`main.py` 只保留插件主体。

### 运行数据

```
data/plugin_data/quote_collocter/
├── quote.db                  # 元数据库（SQLite，WAL；见下节）
├── quotes_data/              # v3.0.1 起：语录图片与缩略图统一放在这里
│   └── <群号>/
│       ├── image_<毫秒>.jpg      # 语录原图
│       ├── quotes_meta.json      # v2.11 前旧格式，已入库，仅作备份
│       ├── quotes_semantic.json  # v2.11 前旧格式，已入库，仅作备份
│       ├── admin_settings.yml    # v2.11 前旧格式，已入库，仅作备份
│       └── .thumbs_v6/           # 缩略图缓存（可删除，会自动重建）
├── identities.json / quotes_sent.json / identity_sync.json / update_announce.json
│                             # v2.11 前旧格式，已入库，仅作备份
└── avatars/                  # 头像存档（sha1 命名，dHash 用于以图找人）
```

- 群号与文件名严格校验，无法目录穿越。
- 删除 `.thumbs_v6/` 不影响原图；删除 `avatars/` 后下次同步会重拉。
- 从 v1.x / v2.x 升级无需手动迁移：v2.10 会在首次加载时补发 pid，v2.11 把元数据导入 `quote.db`；v3.0.1 起旧 `data/quotes_data/` 下的图片与缩略图会自动迁移到 `data/plugin_data/quote_collocter/quotes_data/`，迁移完成后清理空的旧目录。

---

## 数据存储（SQLite，v2.11 起）

自 v2.11.0 起，插件的全部元数据存放于 **`data/plugin_data/quote_collocter/quote.db`**（SQLite，WAL 模式）：

| 表 | 内容 |
| --- | --- |
| `group_settings` | 各群的冷却、触发模式、AI 召回等设置 |
| `quote_meta` | 每条语录的投稿人、时间、归属人物等元数据 |
| `semantic_index` / `semantic_item` | 语义索引签名与每条语录的视觉描述、标签、向量 |
| `identity_user` / `identity_person` / `identity_alias` / `identity_blocked` | 人物档案：QQ、pid、别名、屏蔽词 |
| `sent_session` | 机器人发送记忆 |
| `doc` | 自动同步设置、更新推送设置 |

- **自动迁移**：首次启动时如果存在旧版 `quotes_meta.json`、`admin_settings.yml`、`quotes_semantic.json`、`identities.json`、`quotes_sent.json`、`identity_sync.json`、`update_announce.json`，会自动导入数据库；旧文件保留但不再读写。v3.0.1 起旧 `data/quotes_data/` 下的图片与缩略图也会自动迁移到 `plugin_data/quote_collocter/quotes_data/`。
- **备份**：停插件后打包 `quote.db`（连同 `-wal`/`-shm`）+ `quotes_data/` 图片目录即可；也可用 `GET database` 查看状态。
- 图片与头像仍然是磁盘文件，数据库只存路径/哈希等元数据。

## Web API（63 条）

全部注册在 `/quote_collocter/*`，走 AstrBot 插件鉴权。

| 分组 | 路由 |
| --- | --- |
| 总览 / 统计 | `overview`、`statistics` |
| 语录 | `quotes`、`image`、`quotes/delete`、`quotes/move`、`group/delete`、`settings` |
| 归属 | `quotes/subject`、`quotes/auto_subject`、`quotes/review`、`quotes/bind_name` |
| 语义化 | `semantic/status`、`semantic/run`、`semantic/progress`、`semantic/reset`、`semantic/backfill_speaker` |
| 发送记忆 | `sent` |
| 人物档案 | `identity/overview`、`identity/list`、`identity/detail`、`identity/avatars`、`identity/match`、`identity/sync`、`identity/merge`、`identity/split`、`identity/reset`、`identity/schedule`、`identity/match_names`、`identity/clusters`、`identity/cluster_merge`、`identity/cleanup`、`identity/aliases`、`identity/alias_delete` |
| 更新推送 | `announce` |
| 检索 / 回收站 / 自动标签 | `quotes/search`、`trash`、`trash/restore`、`trash/purge`、`tag/queue` |
| 排行 / 命令 | `quotes/ranking`、`quotes/subject`、`quotes/auto_subject`、`quotes/review` |
| 限制级 | `quotes/restricted`、`quotes/rating`、`quotes/auto_rating` |
| 可视化 / 报告 | `insights/heatmap`、`insights/timeline`、`insights/annual`、`insights/annual_image`、`weekly`、`weekly/settings`、`weekly/test` |
| 合集 | `collections`、`collection/save`、`collection/delete` |
| 协作维护 | `collab/members`、`collab/tokens`、`collab/audit`、`collab/base` |

常用参数：`group_id`（群号）、`page` / `page_size`、`top` / `days`、`user_id` / `person_id` / `pid`、`dry_run`（清理接口）。

---

## 群设置

`admin_settings.yml`（每个群独立，默认值如下）：

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `mode` | `0` | 0=关闭投稿；1=仅 bot 管理员；2=所有人 |
| `coldown` | `10` | 戳一戳发图冷却（秒） |
| `poke_prob` | `0.85` | 戳一戳发图概率（0–1） |
| `last_poke` | `0` | 上次戳一戳时间戳（内部使用） |
| `remember` | `true` | 让 AI 记住发过的语录 |
| `recall` | `true` | 允许 AI 语义召回并发送语录 |
| `auto_recall` | `false` | AI 没写标记时自动补发 top1 |

---

## 更新推送（DSH 桥接）

插件版本变化后，启动时会读取 `CHANGELOG.md` 中对应版本的条目，经 DSH 桥接插件推送到白名单群：

1. 等 `UPDATE_ANNOUNCE_DELAY`（默认 6 秒）后尝试推送；QQ 适配器未就绪时按 20/30/45 秒退避重试，最多 4 次。
2. 每个群向桥接的 `POST /push` 发送 `{session, text}`，鉴权头 `X-DSH-Token`；token 取 `update_announce.json.bridge_token`（v3.0.1 起不再自动读取其他插件配置里的 token）。
3. 同一版本只推一次（`last_version`），推送成功后写入 `last_result` 与 `last_context`；`last_context` 供 AI 上下文注入使用。
4. 更新推送默认关闭且没有内置群号：需在 `update_announce.json` 的 `groups` 中显式配置目标群并填写 `bridge_token`；`announce` API 支持预览（GET）与测试推送（POST `{"test": true}`）。

配置示例：

```json
{
  "enabled": true,
  "bridge_url": "http://127.0.0.1:4150/push",
  "bridge_token": "",
  "groups": [
    { "group_id": "123456789", "umo": "default:GroupMessage:123456789", "name": "主群" },
    { "group_id": "987654321", "umo": "default:GroupMessage:987654321", "name": "分会场" }
  ]
}
```

---

## 身份自动同步

- 默认每 24 小时同步一次：`identity/sync`（群成员昵称 + 群名片 + 头衔屏蔽）→ 头像补齐（单次最多 600 张）。
- 周期可在「语录人物」页调整（1–168 小时）或暂停；`identity/schedule` 返回 `last_sync_at` / `next_sync_at`。
- 同步只覆盖有语录数据的群（即 `data/plugin_data/quote_collocter/quotes_data/<群号>` 存在的群）。
- 状态存于 `identity_sync.json`。

---

## 开发与维护

- 编译检查：

  ```bash
  python -m py_compile main.py quote_*.py
  node --check pages/manage/script.js
  ```

- 部署：把 `main.py`、`quote_*.py`、`metadata.yaml`、`CHANGELOG.md` 与 `pages/manage/*` 覆盖到服务器插件目录，然后重载插件：

  ```bash
  curl -X POST "http://127.0.0.1:6185/api/v1/plugins/quote_collocter/reload" \
       -H "Authorization: Bearer <dashboard-token>"
  ```

  也可直接 `systemctl restart astrbot`（更彻底，会重建所有模块）。
- 新增模块时保持单向依赖：`quote_core` ← 其它模块 ← `main.py`；公共常量放 `quote_core`，避免多处版本 / 路径漂移。
- 修改破坏性逻辑（删除、合并、清理）务必遵守「预览 → dry_run → apply」流程，并保留原始昵称到 `subject_raw_name` 便于回溯。
- 备份：`main.py.bak-v2100` 是拆分前的 v2.10.0 单文件版本，可作对照；正式发布前建议同时备份 `data/plugin_data/quote_collocter/identities.json`。

---

## 已知限制

- 语义化依赖 AstrBot 中已配置的视觉模型与向量模型；未配置时相关按钮不可用，其余功能正常。
- AI 每轮最多召回一次、最多发送一张；模型偶尔仍可能纯文字回复（可开 `auto_recall` 兜底）。
- 头像取自公开的 qlogo 接口，仅用于识别与展示；群友更换头像后需等待下次同步。
- 「语录排行」按本群统计；跨群合并排名请用管理页「语录统计」。
- 官方查重 / AI 检测与插件无关。

---

## 版本历史

| 版本 | 主要内容 |
| --- | --- |
| v2.10.x | 人物档案改用稳定 `pid` 编号；工程重构：`main.py` 拆分为 9 个模块（v2.10.1） |
| v2.9.x | 语录统计与排行、群头衔过滤、按 QQ/别名点名召回、身份自动同步、更新推送与上下文注入、`quote_stats` 工具 |
| v2.8.x | AI 用群昵称称呼人物；修复「只发文字不发图」；放宽召回提示词 |
| v2.7 | 昵称别名表、变体聚类归并、旧别名整理 |
| v2.6.x | 按「被拍的人」归档语录、待确认归属、回填语义 speaker |
| v2.5 | 人物档案（昵称 / 头像历史、以图找人、合并拆分） |
| v2.4 | AI 语义召回 `quote` + `&&标记&&` 发图 |
| v2.3 | 修复 sandbox iframe 下确认框失效 |
| v2.2 | 发送记忆（AI 记住自己发过的语录） |
| v2.1 | 一键语义化与语义检索 |
| v2.0 | WebUI 管理页面 |

完整逐条记录见 [CHANGELOG.md](./CHANGELOG.md)。

---

## License

AGPL-3.0（基于上游 `litsum/astrbot_plugin_quote_collocter` 二次开发，沿用其许可证并保留原作者署名）。

> v2.17.6 起管理页为毛玻璃视觉：纸感渐变背景 + 柔光 + 等高线/涟漪装饰，面板与浮层为半透明玻璃；左侧导航采用模板墨黑 + lime 激活块。

- **v2.20.5**：协作维护页「重新语义化」可填写参考意见（如图中人物是谁），视觉模型据此校正识别，识别成功后自动清除。
