# 骨架动画与动态背景方案调研

日期：2026-06-03

状态：草案

## 调研目标

本次调研关注两类能力：

- 看板娘/pet 是否应该使用成熟骨架动画 JS 运行时，而不是只靠 CSS 摆动透明 PNG。
- MytheNAS 主标题背景是否可以使用成熟的“运动点 + 连线 + 三角面”视觉方案，同时仍然适合无桌面 Ubuntu kiosk 离线启动。

## 看板娘骨架动画候选

### Rive

链接：

- [Rive Web Runtime 文档](https://rive.app/docs/runtimes/web)
- [rive-app/rive-wasm](https://github.com/rive-app/rive-wasm)
- [Rive State Machine / States 文档](https://rive.app/community/doc/states/docEwEIEWU1U)

评估：

- 适合 Web kiosk。运行时直接挂载到 `<canvas>`，可以加载 `.riv` 文件。
- 支持 state machine，适合把 `idle`、`wave`、`scan`、`celebrate`、`patrol` 这类动作做成主题资源。
- 模型文件和动画可以作为主题资源包的一部分，不需要把动作逻辑写死在 widget 中。
- 默认主题不能随意内置网上找到的 `.riv` 模型，因为模型再分发许可证需要单独审查。

结论：推荐作为 `core.mascotAssistant` 的第一优先骨架动画接口。当前实现已经预留 `mascot.rive` 配置；默认关闭，提供 PNG/CSS fallback。

可用资源入口：

- [Unicorn Icons Rive](https://unicornicons.com/icons/rive)：提供 `.riv` 格式动画图标，适合测试 Rive 加载链路和 state machine 用法。
- [Rive Marketplace Animated Icons 示例](https://rive.app/marketplace/23356-43719-animated-icons/)：Rive marketplace 上有 CC BY 示例资源，适合学习结构和交互状态。
- Rive Community：适合找可学习的 state machine 示例。社区作品是否允许随项目再分发，需要逐个确认。

### Live2D Cubism Web

链接：

- [Live2D/CubismWebSamples](https://github.com/Live2D/CubismWebSamples)
- [Live2D/CubismWebFramework](https://github.com/Live2D/CubismWebFramework)

评估：

- 非常适合二次元看板娘，表现力强。
- Web 侧可用，但 Cubism Core、SDK、示例模型和第三方模型授权边界更复杂。
- 对“其他用户快速复现并替换自己的主题资源”而言，安装和授权说明会比 Rive 更重。

结论：适合作为后续 `vendor.live2dMascot` 插件，不作为默认标准组件依赖。

### Spine / DragonBones

评估：

- 都是成熟 2D 骨架动画方向，游戏资产生态更强。
- Spine 编辑器和 runtime 授权需要谨慎处理；DragonBones 生态维护活跃度需要进一步验证。
- 对当前 NAS 副屏项目，优先级低于 Rive 和 Live2D。

结论：保留为第三方插件方向，不进入第一版默认资源包。

## 动态背景候选

### Vanta.js

链接：[tengbao/vanta](https://github.com/tengbao/vanta)

评估：

- 提供现成网页背景效果，常见效果包括点线网络、云、波浪等。
- 依赖 Three.js，视觉效果直接可用。
- 作为默认 kiosk 依赖时会增加外部包和 WebGL 失败分支。

结论：适合参考视觉方向，也适合后续主题插件；默认测试页先采用本地 canvas 实现。

### tsParticles

链接：[tsparticles/tsparticles](https://github.com/tsparticles/tsparticles)

评估：

- 粒子系统能力强，可以实现运动点、连线、聚合、交互和多种背景效果。
- 配置能力丰富，适合插件化主题。
- 默认引入会增加前端体积，第一版静态测试页不需要完整粒子引擎。

结论：适合作为后续 `core.particleBackground` 或主题插件的候选。

### Trianglify

链接：[qrohlf/trianglify](https://github.com/qrohlf/trianglify)

评估：

- 适合生成三角形图案背景。
- 更偏静态图案生成，不直接覆盖“随机点缓慢运动并动态连成三角面”的需求。

结论：适合生成主题静态背景资源，不作为当前动态背景默认运行时。

## 当前推荐实现

默认实现采用本地 Canvas 三角网格：

- 不依赖 CDN 和 WebGL。
- 开机 kiosk 即可离线运行。
- 随机点缓慢运动，运行时把近邻点连成半透明三角面，并用主题主色、辅色和指标色渲染。
- 后续可以把同一视觉能力抽象成 `core.triangleMeshBackground` 或主题背景模块。

看板娘推荐流程：

1. 默认主题使用透明 PNG 和 CSS 动作，保证开箱即可运行。
2. 主题资源包可提供 `mascot.rive.src` 指向本地 `.riv` 文件。
3. 如果 `mascot.rive.enabled=true` 且资源存在，运行时加载 Rive canvas。
4. 如果 Rive 加载失败，自动回退到 PNG/CSS。

Agent 像素角色推荐流程：

1. 默认主题提供自有 SVG 像素状态精灵，避免第三方 sprite sheet 许可证问题。
2. 状态资源通过 `sprites.agent.<state>` 定义。
3. 授权的第三方像素行走图、动作图可以作为新主题或插件资源包接入。

可用像素资源入口：

- [OpenGameArt CC0 Walk Cycles](https://opengameart.org/content/cc0-walk-cycles)：收集了大量 CC0 行走动画资源，适合后续筛选统一风格的 sprite sheet。
- [OpenGameArt Character Walking](https://opengameart.org/content/character-walking)：页面标注 CC0，提供简单 4 帧行走图。
- [itch.io CC0 Pixel Art Sprites](https://itch.io/game-assets/free/tag-cc0/tag-pixel-art/tag-sprites)：可筛选 CC0 像素角色资源，下载前仍要逐个确认具体页面授权。
