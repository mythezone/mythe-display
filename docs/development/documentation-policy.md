# 文档维护规范

日期：2026-06-03

## 必需文档

- `README.md`：用户可见的搭建方式、当前项目状态和主要入口。
- `CHANGELOG.md`：按日期记录重要变化。
- `docs/research/`：调研记录和带来源的对比。
- `docs/decisions/`：架构决策记录。
- `docs/development/`：技术设计、实现说明和未来开发指南。

## 更新规则

- 当搭建方式、运行命令或用户可见行为变化时，更新 `README.md`。
- 每次有实质性的文档、架构或代码变化时，更新 `CHANGELOG.md`。
- 当技术方向变成长期决策时，在 `docs/decisions/` 中新增 ADR。
- 不要把密钥、本地凭据路径或私有 token 写入任何文档。
- 外部调研需要保留来源链接，方便后续贡献者复核。

## 命名规则

- 调研文档：`docs/research/<topic>.md`。
- ADR：`docs/decisions/NNNN-short-title.md`。
- 开发指南：`docs/development/<topic>.md`。

## 截图和资源

- 评估现有开源项目时，优先在调研文档中引用上游图片 URL。
- 只有项目自有或明确可复用的图片，才保存到 `docs/assets/`。
- 本地调试截图保存到 `screenshots/local/`；该路径已被 Git 忽略。
