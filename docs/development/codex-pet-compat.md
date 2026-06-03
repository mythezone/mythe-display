# Codex Pet 兼容规范草案

日期：2026-06-03

状态：草案

## 目标

`core.mascotAssistant` 支持三种资源模式：

- `png`：默认透明 PNG/WebP，通过 CSS 变换模拟动作。
- `rive`：可选 `.riv` 骨架动画。
- `codex-pet`：兼容 Codex/Petdex 生态的 `pet.json` + spritesheet 包。

Codex pet 官方 CLI 会把资源安装到：

```text
~/.codex/pets/<name>/
  pet.json
  spritesheet.webp
```

提交规范要求目录包含 `pet.json` 和 `spritesheet.{webp,png}`。本项目在此基础上额外兼容 `spritesheet.gif` 和 `spritesheet.svg`，用于本地调试或主题私有资源。

参考：

- [codex-pet CLI 文档](https://codex-pet.com/docs)
- [codex-pet 提交说明](https://codex-pet.com/submit)
- [Petdex 项目](https://github.com/crafter-station/petdex)

## 导入流程

先从 codex-pet 下载：

```bash
npx codex-pet-cli add fox
```

再导入到 Mythe Display 默认主题：

```bash
mdp pet fox --force
mdp reload
```

也可以直接导入目录或 zip：

```bash
mdp pet ~/.codex/pets/fox --force
mdp pet ~/Downloads/fox.zip --force
```

底层脚本是：

```bash
scripts/import-codex-pet.py ~/.codex/pets/fox --force
```

导入后资源会复制到：

```text
public/themes/neon-dark/mascot/pets/<pet-id>/
  pet.json
  spritesheet.webp
```

脚本会更新 `theme.json`：

```json
{
  "mascot": {
    "codexPet": {
      "enabled": true,
      "manifest": "mascot/pets/fox/pet.json",
      "columns": 8,
      "rows": 9,
      "frameWidth": 192,
      "frameHeight": 208,
      "frames": 8,
      "fps": 9
    }
  }
}
```

## 动作映射

默认兼容 8 列 x 9 行 atlas。动作行约定：

```text
0 idle
1 runRight / runningRight
2 runLeft / runningLeft
3 wave / waving
4 jump / celebrate / boot
5 fail / alert / guard
6 wait / think / sleep
7 run / patrol
8 review / scan / focus / type
```

主题可以覆盖映射：

```json
{
  "mascot": {
    "codexPet": {
      "actionRows": {
        "idle": 0,
        "wave": 3,
        "alert": 5,
        "scan": 8
      }
    }
  }
}
```

如果 `pet.json` 提供 `states`、`animations` 或 `animationStates`，运行时也会尝试读取其中的 `name/id/action` 和 `row/index` 字段。

## 授权要求

默认主题不直接内置第三方 Codex pet 素材，因为画面可能来自用户创作、二创或 fan content。导入前应确认：

- pet 作者允许本地使用。
- 如果要提交到仓库或插件包，必须确认允许再分发。
- 若资源目录有 `LICENSE` 或 `README.md`，导入脚本会一起复制，方便后续审计。
