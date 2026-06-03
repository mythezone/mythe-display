# OpenClaw / 像素 Agent 可视化参考调研

日期：2026-06-03

## 结论

推荐先实现自己的 `core.pixelAgents` 兼容层，再按需接入第三方项目或资产包。原因：

- 我们的主场景是 3840x1100 机箱副屏，不是桌面 IDE 面板或独立小硬件。
- 需要统一主题资源包、动态背景和 widget 接口。
- 第三方项目的许可证、资产来源、OpenClaw 接口稳定性不同，不能无审查地整仓复制。

第一版可吸收这些设计：

- Pixel Agents：像素办公室、角色状态机、可替换资产目录、agent-agnostic 架构。
- Agent World：OpenClaw Gateway 插件、实时状态、sub-agent 链路可视化。
- OpenClawfice：OpenClaw 专用虚拟办公室、任务/聊天/状态聚合。
- PixClaw：把 Agent 状态简化为桌面宠物的状态展示。

## Pixel Agents

链接：[pixel-agents-hq/pixel-agents](https://github.com/pixel-agents-hq/pixel-agents)

公开仓库显示它是 MIT 许可的 VS Code 扩展，目标是把多 Agent 系统显示为像素办公室。README 描述了角色会走动、坐到工位、根据写代码/读文件/等待输入等状态变化，并且支持外部资产目录和家具资源 manifest。

可借鉴点：

- Canvas 2D + React/Vite 技术路线，适合浏览器运行时。
- Agent 状态机：idle、walk、type/read、waiting 等。
- 资产包结构：家具、地板、墙面、角色分开管理，manifest 描述资源。
- 长期目标是 agent-agnostic、platform-agnostic、theme-agnostic，和本项目插件方向一致。

限制：

- 当前主要绑定 VS Code + Claude Code transcript。
- 适合 IDE 面板，不是专门为单一 kiosk 屏幕设计。
- 直接复用前需要检查资产来源和构建依赖。

## Agent World

链接：[Agent World](https://www.agentworld.space/)

其页面说明它把 OpenClaw session 转成实时像素控制室，并以 OpenClaw 插件方式安装：`@spicyclaws/openclaw-agentworld`。页面还提到实时追踪、连接状态、sub-agent 链路和布局编辑。

可借鉴点：

- OpenClaw 插件式接入，而不是让显示端侵入 Agent 执行。
- 重点展示 active session、connection state、sub-agent chain。
- 布局和 seat assignment 可以持久化。

限制：

- 明确是 OpenClaw Gateway 集成，泛用性取决于它的插件 API。
- 我们不应直接依赖其 UI，而应先定义 `openclaw.compat -> PixelAgentSnapshot`。

## OpenClawfice

链接：[OpenClawfice](https://openclawfice.com/)；[GitHub](https://github.com/openclawfice/openclawfice)

它把 OpenClaw Agents 展示为像素 NPC/虚拟办公室，页面描述了自动发现 OpenClaw agents、实时状态、任务日志、水冷聊天和本地优先。页面声明项目开源，站点显示 AGPL-3.0。

可借鉴点：

- 对 OpenClaw 专用场景的产品表达比较完整。
- 状态不仅有 idle/working，也包含待决策、聊天和任务日志。
- 可以作为后续“像素办公室”高级组件的行为参考。

限制：

- AGPL-3.0 对直接复用代码有传染性要求；除非接受 AGPL，第一阶段只参考交互概念。
- “自动发现”依赖 OpenClaw 运行时细节，必须由适配器隔离。

## PixClaw

链接：[PixClaw](https://www.pixclaw.io/)

PixClaw 是实体桌面小屏/桌宠方向。它把 OpenClaw 或 Claude Desktop Buddy 的状态映射成像素宠物动画，强调 idle、working、error、offline 这类极简状态。

可借鉴点：

- 状态模型足够简单，适合本项目第一版。
- “只读地镜像状态，不干扰 Agent 执行”的边界适合副屏。
- 它也说明 OpenClaw 连接可以是 LAN 本地方式。

限制：

- 主要是硬件设备和固件，不适合作为本项目 Web kiosk 的直接基础。
- 可作为状态语义和小尺寸视觉反馈参考。

## OpenClaw 基础运行时

链接：[OpenClaw 文档](https://docs.openclaw.ai/)

官方文档把 Gateway 描述为 session、routing 和 channel connection 的中心，并提供浏览器 Control UI。默认本地 dashboard 地址在文档中记录为 `127.0.0.1:18789`。

对本项目的影响：

- OpenClaw 适配器应优先读 Gateway 或插件暴露的 session 状态。
- 副屏不应保存 OpenClaw 凭据。
- 如果要访问远程 OpenClaw，应优先走 Tailscale 或本地反向代理，而不是公开控制接口。

## 推荐路线

1. 保留当前 `core.pixelAgents` 数据模型。
2. 先实现本地 JSON/HTTP 数据源，让任意脚本都能输出 Agent 状态。
3. 后续新建 `vendor.openclaw-agent-bridge` 插件，专门读取 OpenClaw Gateway。
4. 需要像素办公室高级玩法时，再研究 Pixel Agents 的资产 manifest 和 Canvas 2D 状态机。
5. 任何第三方代码并入前，先做许可证和资产来源审查。
