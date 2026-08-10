# Credential Audit Log & Rotation Checklist

原则(evidence audit C5/K5):"本地存在"≠"已泄露"。只有发现某凭据曾进入
Git 对象、日志、镜像、压缩包或屏幕分享时才轮换对应凭据;不做恐慌式全量轮换。

## Audit — 2026-07-31(branch dual-track-sprint)

| 检查 | 命令要点 | 结果 |
|---|---|---|
| 1. 敏感文件是否被跟踪 | `git ls-files` 过滤 .env/key/credential/pem | ✅ 仅 `backend/.env.example`(纯占位符,逐行核验) |
| 2. 已知敏感路径历史 | `git log --all --follow -- backend/.env backend/firebase-admin-key.json` | ✅ 从未被提交 |
| 3. 跟踪内容 secret 模式 | `git grep` API-key/私钥/带凭据连接串模式 | ✅ 无命中 |
| 4. 全历史 blob 路径扫描 | `git rev-list --all --objects` 过滤敏感文件名 | ✅ 无命中 |
| ignore 规则 | `git check-ignore` 两个本地敏感文件 | ✅ 均被忽略 |

**结论:未发现暴露,无需轮换。**

## 发布前必须重跑的场景

- 推送到新 remote / 公开仓库前
- 构建 Docker 镜像后(检查镜像层:`docker history` + 挂载检查 image 内无 .env)
- 打包 submission archive 前(解包后重跑检查 3)
- 任何录屏发布前(确认画面无 .env 内容、无 token URL)

## 若发现暴露,轮换顺序

1. MongoDB Atlas connection string(Atlas → Database Access 重置密码)
2. Voyage API key(dashboard 重新生成)
3. Firebase admin key(GCP IAM → 服务账号新建 key、删旧 key)
4. GCP 服务账号其余 key 与 OAuth secret
5. 轮换后重跑上表四项检查并在此追加记录
