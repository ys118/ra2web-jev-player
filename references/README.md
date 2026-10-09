# references —— 参考资料（原 `refs/` + `_research/` 合并）

> 本目录是**外部资料的存档**：上游文档快照与数据挖掘素材。运行时（对局）不依赖它；
> 知识成品的正本在 `docs/knowledge/`（攻略三件套与作战手册）。

## 结构

| 路径 | 来源 | 内容 |
|---|---|---|
| `werhd/` | 原 `refs/` | 游戏官方玩家 API 文档快照与示例：`player-console-api.md`（werhd API 原文）、`jev-player-local.md`、`jev-player-goal-audit.md`、`examples/`（官方播放器源码，含 `jev/` 子目录示例） |
| `research/` | 原 `_research/` | 数值真值与可复现流水线：`rules.ini`（游戏客户端原文件）、`ra2.csf` + `csf_decoded.json`（代号→中文名）、`rules_extract*.md`（提取表）、`app.js`/`worker.js`（引擎语义查证）、`pages/`（社区攻略原文 43 篇）、抓取/解码脚本（`web.py`/`fetch_pages.py`/`decode_csf.py`/`gen_json.py`/`verify.py` 等） |

## 对应关系

- `research/` 是 `docs/knowledge/` 三件套的**上游**：原始数据与生成脚本在此，
  结论蒸馏进 `docs/knowledge/RA2-BIBLE.md` / `AI-OPERATING-CARD.md` / `RA2-UNITS.json`。
  复现/刷新流程照 `research/README.md` 抄（含游戏版本升级后的整体刷新步骤）。
- 引擎/站点语义的事实以 `werhd/` 的官方文档为准；本项目自有的 API 定义与页内客户端
  在 `src/ra2web_jev_player/werhd/`（`api.md` + `client.js` + 官方类型副本 `.d.ts`）。

## 运行说明

- `research/` 下的抓取脚本依赖 `requests`：`uv sync --group research` 后
  `uv run python references/research/<脚本>.py`。
- 本目录不参与静态检查与测试（`pyproject.toml` 的 ruff `extend-exclude`），
  也不进 wheel（仓库根运行）。
