# gmail-watcher

Gmail 监听与下游 GitHub Actions 触发器，使用 Flask、Pub/Sub 与 Firestore。
本文件适用于独立 clone；父工作区存在时再按任务读取其规则，缺少父工作区不阻断本地工作。

## 入口与路由

- [README.md](README.md)：链路、配置、排障与带日期的部署取证。历史 revision、触发器与账户配置需现场复核。
- `main.py`：Pub/Sub 入口（同步处理）、historyId 去重、关键词匹配、Gmail 标签、workflow dispatch、watch 续期与健康检查。
- `mail_hub_notify.py`：独立 Cloud Run 邮件中枢通知入口，使用独立 Push 订阅。
- `generate_gmail_token.py`：人工 OAuth 凭据生成；`Dockerfile`：运行镜像。
- [RUN_LOCAL_DOCKER.md](RUN_LOCAL_DOCKER.md)：有账户副作用的本地启动说明，不能当作默认测试。
- [docs/design-haier-otp-delivery.md](docs/design-haier-otp-delivery.md)：早期候选方案。现行设计见 [邮件中枢交接](https://github.com/huozao/mail-hub/blob/main/docs/handoff.md)。

## 业务与授权边界

- 已记录的 Cloud Build 部署方式是 push/merge 到 main 后自动上线；本地修改授权不包括 commit、push、merge、创建 PR、改远程资源或部署。
- `POST /` 可修改 Gmail 标签、Firestore 状态并触发真实下游流水线；`GET /refresh_watch` 会续期 watch，可能发通知。HTTP 方法和本地运行不代表只读；真实调用、OAuth、账户变更与发信须在用户授权范围内。
- `GITHUB_REPO`、`GITHUB_WORKFLOW` 是源码常量，仓库转移时应同时核对目标、PAT 与 Cloud Build 绑定。公开仓 GET 200 不证明 workflow dispatch 权限；不要用无关私有仓作为本仓默认验证要求。
- Gmail watch 会过期；续期成功与下游业务完成分别验证。入口 HTTP 200、dispatch 接受或 Actions 绿灯均不能证明邮件链路完成。
- 不提交 `.env`、OAuth token、凭据、邮件正文、Firestore 导出、日志或账户数据；不打印秘密。工作区部署的凭据按其 SOPS 规则，独立 clone 不依赖私有仓。
- 保持 `.gitignore` 为 UTF-8；若改忽略规则，用 `git check-ignore -v` 验证敏感文件被忽略、源码未被误忽略。

## 关键架构经验与不变量

- **Cloud Run CPU 节流陷阱**：生产环境配置了 `cpu-throttling: true`（CPU 仅在处理活动请求期间分配）。`POST /` 处理消息时**必须同步处理并在全部完成后再返回 200 OK**；严禁开启后台线程立即返回 200，否则主请求结束后容器 CPU 会被极速冻结，导致 Gmail API 严重挂起（实测拖至 30s）甚至在缩容时直接丢弃任务。
- **Pub/Sub 确认超时**：为配合同步处理，推送订阅 `gmailtocloud-sub` 的 `ackDeadlineSeconds` 保持为 30s，防止正常处理期间误触发重投。
- **Firestore 读写防重**：每次接收消息需校验 `historyId > last_history_id`，且内部函数直接复用已读取的值，杜绝同轮处理中重复网络往返读取 Firestore。
- **免费额度与存储控制**：项目月请求量极低（约 300~500 次），Cloud Run、Pub/Sub、Scheduler、Firestore、Secret Manager 均在 Always Free 免费额度内。Artifact Registry 镜像库已配置 Cleanup Policy（删除 >7d 未标记旧镜像，保留最新 5 个版本），防止构建历史镜像超出 0.5 GB 产生存储费。

## 最小验证与维护

邮件中枢通知入口的离线测试运行 `python -B -m unittest discover -s tests -v`。原有应用的普通本地检查无需导入会初始化云客户端的应用：

```bash
python -m py_compile main.py generate_gmail_token.py
git diff --check
```

纯文档改动检查路径、链接与命令。编译只证明语法，不证明云服务、watch、去重或下游业务可用；
行为改动需针对受影响逻辑做隔离验证，无法验证时明确说明。

业务行为、路由、配置、部署触发或验证方式改变时，同批更新受影响的现有契约与导航。
新功能只补需要的文档，无影响不制造记录。历史取证标日期，待验证不写成线上事实。
