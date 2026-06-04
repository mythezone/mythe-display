# Theme Authoring

## 目标

主题是可复制的资源包。用户只要拥有一个主题目录，就应该能还原出该主题的颜色、背景、Hero、看板娘和 Agent 精灵资源。

## 目录

默认主题位于 `public/themes/neon-dark/`。新主题推荐从它复制：

```bash
cp -R public/themes/neon-dark public/themes/my-theme
```

推荐结构：

```text
public/themes/<theme-id>/
  theme.json
  backgrounds/
  hero/
  mascot/
  sprites/
```

## 最小要求

- `theme.json` 必须存在，并声明主题 id、名称、语义颜色 token 和资源路径。
- 背景资源可选；没有动态背景时，页面应使用纯色或渐变 fallback。
- Hero 图、mascot、pixel Agent sprite 可选，但缺失时必须保留布局稳定和降级状态。
- 资源路径应使用主题目录内的相对路径，避免个人绝对路径。

## 修改原则

- 主题控制视觉，不改变 Widget 数据契约。
- 优先使用语义 token，例如 surface、accent、success、warning、danger，而不是在 Widget 内散落硬编码颜色。
- 对长条屏优先保证 `3840x1100` 布局，对浏览器预览保留窄屏降级。
- 新主题要更新 README 或文档中的使用方式，并在需要时添加示例截图。
