# Widget Authoring

## 当前架构

第一版 Widget 仍直接在 `public/kiosk-test/index.html`、CSS 和本地 JS 中实现。不要为了单个 Widget 引入前端框架迁移。

## 推荐流程

1. 定义 Widget 目的、显示尺寸、刷新频率和失败状态。
2. 定义 JSON 数据契约，并在 `docs/development/interface-spec.md` 或对应 Widget 文档中记录。
3. 在 `public/kiosk-test/` 添加 mock JSON，确保无 runtime 数据时可以预览。
4. 新增或修改 `scripts/collect-*-snapshot.py`，把真实数据写入 `public/runtime/<name>.json`。
5. 修改 `public/kiosk-test/index.html` 渲染 Widget，并保持布局稳定。
6. 更新 README、中文 README、CHANGELOG 和必要的开发文档。

## 数据契约

- runtime snapshot 必须是可序列化 JSON，不包含密钥、token、直接联系方式或不必要的私人内容。
- 采集器应输出 `generatedAt` 或等价时间字段，方便 UI 显示数据新鲜度。
- 刷新频率按数据变化速度设定：磁盘容量可低频，CPU/内存/网络可中频，实时动画不要依赖高频系统采集。
- Widget 必须处理 missing、loading、stale、error 或 unavailable 状态。

## 视觉要求

- 紧凑组件优先稳定网格和可扫描信息，不用说明性长文案。
- 颜色应来自主题 token；确需硬编码时要有明确理由。
- 不要让文本溢出按钮、卡片、图表轴或固定格子。
