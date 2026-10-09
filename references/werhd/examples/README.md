# 玩家 API 示例

这些示例属于 [玩家 API 文档](../player-console-api.md)，由使用者主动加载，不会随游戏自动执行。

- [基础玩家循环](werhd-user-script.mjs)：展开基地车、造兵、攻击的最小示例，可替换决策函数。
- [Jev 接入示例](jev/README.md)：模型决策、规则目录、策略、特殊行动、摄像机和本地看板。

在游戏页进入对局后加载基础示例：

```js
const { attachWerhdPlayer } = await import('/docs/examples/werhd-user-script.mjs')
attachWerhdPlayer(window.werhd)
```

## 维护与发布

`ra2web-werhd/docs/examples/` 是唯一编辑源。Vite 开发服务直接提供这些文件；构建将选定的文档与示例原样输出至 `dist/docs/`，不打入游戏主包。`sync:github-pages` 按发布清单同步到站点的同一路径。

发布范围在 `tools/lib/published-docs.mjs` 中显式列出，新增示例时一并登记。`public/`、站点根目录以及 `docs/` 根目录不再维护重复脚本。该清单之外的站点文档仍受保护。
