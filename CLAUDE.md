# ST MCU Selector

<!-- /init 填充 [方括号] 内容。手动创建时逐段填写。 -->

---

<!-- ============================================================
     PART 1: 全局规则 — TEMPLATE INHERITED
     
     本段落从 vibe-coding-template 继承,是所有项目的最高层约束。
     
     维护规则:
     - 项目中发现新的通用 learning → 先加到本项目 CLAUDE.md
     - 确认是跨项目通用的 → 同步回 template repo 的 CLAUDE.md
     - 定期(每月/每季度)用 template 的最新版本覆盖各项目的 PART 1
     
     不要在项目中修改 PART 1 的已有规则,只追加。
     项目特定的规则写在 PART 2。
     ============================================================ -->

## 协作偏好

- 反馈极简("合并"、"继续"、"还是报错"),结合 PROGRESS.md 和上下文理解,不要要求重复背景
- 回复同样简洁:直接说结论和操作,不铺垫、不重复已知信息
- 关键判断点(是否建 PR、架构选型、破坏性操作)暂停等确认;执行类操作直接做
- 解释方案时给出 reasoning 和 tradeoff,不只给"做什么"
- commit message 必须包含 WHY,不只是 WHAT
- 默认中文,技术术语保留英文(deploy、PR、workflow 等不翻译)
- 对外交付物(邮件、英文文档)用英文,主动校对术语准确性

## 模型分配规则

| 任务类型 | 推荐模型 | 说明 |
|---------|---------|------|
| 核心业务逻辑、架构设计、代码审查 | Claude (B 模型) | 不可降级 |
| 样板代码、单元测试、CRUD、格式转换 | DeepSeek (C 模型) | 省 token |
| 需求探索、领域知识、竞品调研 | Claude/Gemini (A 模型) | 在 Cursor 中使用 |
| 拿不准用哪个 | Claude (B 模型) | 安全默认值 |

## 代码规范(全局)

### 硬性规则
- 单文件不超过 **300 行**,超过必须拆分
- 每个 route 文件不超过 **5 个端点**,超过按子资源拆分
- React 组件命名 PascalCase,不超过 3 个单词
- 新文件必须符合项目特定的目录结构规范(见 PART 2),不允许自由放置
- 不使用 `any` 类型(TypeScript 项目)
- 所有 API 端点必须有错误处理,不允许裸 try-catch 吞掉错误

### 目录结构模板

**React + Vite:**
```
src/components/{ComponentName}/index.jsx
src/pages/{PageName}/index.jsx
src/store/{slice-name}.js
src/api/{resource}.js
```

**Flask / Express:**
```
server/routes/{resource}.js
server/middleware/{name}.js
server/models/{entity}.js
```

**Python 数据管道:**
```
scripts/{data-source}/fetch-{source}.py
scripts/{data-source}/transform-{source}.py
```
必须有 `--dry-run` 参数。

## 环境约束(全局)

- GCP 项目 `st-china-ai-force`,region `asia-east1`
- Cloud Run 监听 port **8080**,流式请求 **5 分钟超时**
- 大陆网络: Firestore 客户端直连**不可用**,需服务端代理或改用 BigQuery
- DeepSeek: OpenAI-compatible SDK,model ID `deepseek-chat`
- AkShare: 参数名有版本漂移,调用前先验证当前版本签名

## 跨项目 Learnings(持续累积)

<!-- 
这是整个 template 最重要的段落。
每个项目中遇到的通用教训都追加到这里,然后同步回 template repo。
格式: [日期] [来源项目] 教训内容
-->

- [2024-12] [analog-pd-dashboard] A 股财报数据是 YTD 累计,必须差减上季度得到单季值
- [2024-12] [analog-pd-dashboard] AkShare 千元单位需 ×0.1 转万元,不是 ×10000
- [2025-01] [resume-ai-screener] Firebase Anonymous Auth 需在控制台手动启用,默认关闭
- [2025-01] [resume-ai-screener] Service Worker 缓存 stale hash 导致部署后白屏,需配置 skipWaiting
- [2025-03] [mcu-competitor-dashboard] 普冉股份 stock code 是 688766 不是 688694
- [2025-03] [mcu-competitor-dashboard] STAR Market(科创板)在 AkShare 中 column 值不同于主板
- [2025-04] [geo-strategic-hub] Tailwind v4 无 typography plugin,需手动处理富文本样式
- [2025-04] [geo-strategic-hub] `@google/genai` SDK 不支持 OpenAI-compatible 接口,不能混用
- [2025-05] [geo-strategic-hub] Cloud Run 流式请求 5 分钟超时,文件操作必须串行不能并行
- [2025-05] [geo-monitoring] Recharts ResponsiveContainer 在 flex 布局中需要显式 width/height
- [2025-06] [st-newsletter] Net Income % 应改为 Net Margin % — 注意英文术语准确性
- [2025-06] [skill-radar] git worktree 多 agent 并行时 merge 顺序重要,先合基础分支

<!-- 新 learning 追加在上方,保持时间顺序 -->

---

<!-- ============================================================
     PART 2: 项目特定 — /init 填充
     
     以下内容仅适用于本项目,不回流到 template。
     ============================================================ -->

## 项目信息

- **描述**: ST MCU Selector，给工程师在网页上完成 MCU 短名单
- **部署**: Cloud Run `st-mcu-selector` on `st-china-ai-force` / `asia-east1`
- **技术栈**: 静态 HTML/CSS/JS + nginx
- **线上 URL**: [部署后填写]
- **GitHub**: [repo URL]

## 架构概览

### 主要模块

```
web/: ST Key Visual 单页（推荐 / 竞品对照 / 查看订货号）
nginx.conf: Cloud Run port 8080 与 /healthz
```

### 关键文件

```
web/index.html  — 页面结构与 TDK
web/styles.css  — ST 色板、Arial、message bar
web/app.js      — 三种问法示例切换
Dockerfile      — nginx 静态发布
```

## 项目特定代码规范

- 静态页与表单在 `web/`，API 在 `server/routes/`
- 字体只用 Arial；颜色只用 ST Dark Blue / Yellow / Light Blue / gray ramp
- 黄底必须用深蓝字，禁止白字配黄底
- 不使用投影、发光、非 ST 渐变
- 终端用户页面只开放 recommend / compare / inspect，不开放数据库更新

## 项目特定约束

- 选型查询走本服务 API，不要求用户使用 ChatGPT
- 不承诺引脚兼容、价格、交期
- 竞品对照必须有规格来源说明

## 常用命令

```bash
# 开发
python run.py

# 测试
python -m unittest tests.test_api

# 部署
gcloud run deploy st-mcu-selector --source . --project st-china-ai-force --region asia-east1 --port 8080 --allow-unauthenticated --memory 2Gi --timeout 300 --max-instances 1
```
