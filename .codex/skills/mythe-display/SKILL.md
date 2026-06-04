---
name: mythe-display
description: 适用于本仓库的所有工作：Mythe Display Ubuntu 副屏 kiosk 开发、主题和 Widget 定制、运行时采集器、文档发布整理、密钥保护，以及完成用户可见任务后的提交与推送。
---

# Mythe Display 项目定制助手

## 基本规则

- 默认用中文沟通；根 `README.md` 是正式英文入口，中文入口是 `README.zh-CN.md`。
- 当前发布版保留静态 Web kiosk + Python collector 架构；除非用户明确要求，不迁移 React/TypeScript。
- `.env`、API token、个人路径、私有主机名和运行时产物绝不提交或写入文档。
- 不提交 `public/runtime/`、`tmp/`、`screenshots/local/`、缓存目录或本地调试输出。
- 用户可见功能、命令、配置或复现步骤变化时，同步更新 README、相关 `docs/` 和 `CHANGELOG.md`。
- 完成实质性仓库变更后，只 stage 相关文件，commit 并 push。

## 产品方向

- 目标是 Ubuntu 服务器、NAS 或机箱上的普通 HDMI/DisplayPort 副屏。
- 默认运行方式是 `cage + Chromium` direct DRM fullscreen kiosk，不依赖完整 Ubuntu 桌面环境。
- Web 端预览和物理屏 kiosk 应显示同一套页面、主题和 Widget。
- USB-C 只有在硬件支持 DP Alt Mode、USB4 或雷电时才能作为普通视频输出；DisplayLink 属于可选适配器方向。

## 常用命令

- Web 预览：`python3 scripts/serve-web-test.py --host 0.0.0.0 --port 23456`
- 物理屏测试：`sudo MYTHE_DISPLAY_PORT=23456 scripts/run-kiosk-web-test.sh`
- 安装服务：`sudo scripts/install-kiosk-service.sh`
- 控制服务：`mdp start`、`mdp reload`、`mdp switch /kiosk-test/`、`mdp restart`、`mdp logs`
- 静态检查：`python3 -m py_compile scripts/*.py` 和 `bash -n scripts/*.sh scripts/mdp`

## 定制工作流

- 制作主题时，优先复制 `public/themes/neon-dark/`，再修改 `theme.json` 和资源文件；详见 `references/theme-authoring.md`。
- 开发 Widget 时，先定义 JSON 数据契约、mock 数据和低频 runtime collector，再改 `public/kiosk-test/index.html`；详见 `references/widget-authoring.md`。
- 发布整理、截图、验证和提交流程见 `references/release-workflow.md`。
- 长期调研写入 `docs/research/`，技术决策写入 `docs/decisions/`，开发规范写入 `docs/development/`。
