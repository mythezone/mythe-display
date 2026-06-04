# Release Workflow

## 发布整理检查

- 根 `README.md` 使用英文，并在顶部提供 `README.zh-CN.md` 入口。
- 中文 README 与英文 README 的关键命令保持一致。
- `.env.example` 只包含非敏感默认值和空占位，不包含真实 token、私有地址或个人路径。
- `examples/screenshots/` 存放可发布截图；`screenshots/local/` 只放本地临时截图。
- `public/brand/` 存放可公开品牌资产。
- `systemd` 安装脚本应按当前仓库路径渲染服务，不硬编码个人目录。

## 验证命令

```bash
python3 -m py_compile scripts/*.py
bash -n scripts/*.sh scripts/mdp
scripts/collect-runtime-snapshots.py --once --pretty
git status --ignored --short
```

如果本机 `public/runtime/` 是 root-owned 或已有正在运行的 kiosk，可使用临时目录验证单个 collector，并在最终说明中写清楚无法运行默认输出目录的原因。
也可以运行：

```bash
scripts/collect-runtime-snapshots.py --once --pretty --runtime-dir tmp/verify-runtime
```

## 截图

- 本地调试截图先放 `screenshots/local/`。
- 确认适合公开后复制到 `examples/screenshots/`。
- README 只引用 `examples/screenshots/` 和 `public/brand/` 中的可发布资源。

## Git

- 只 stage 与当前任务相关的文件。
- 提交前检查没有 `.env`、runtime、cache、local screenshots 或调试产物。
- 完成后 commit 并 push；如果 push 失败，说明具体原因，不暴露凭据。
