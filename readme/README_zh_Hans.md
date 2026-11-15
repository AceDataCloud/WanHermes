# Wan by Ace Data Cloud：Hermes 单服务 Git 安装

[English](../README.md)

本源码变体只注册 **Wan 的 2 个工具**，由 Ace Data Cloud 维护，不表示与服务品牌方有隶属关系。需要 Hermes **0.23.1+**。官方目录仍只有 `acedatacloud-media` 一条媒体产品线入口，源码合并不表示独立官方收录或默认预装。

## 安装与应用 Token

```sh
hermes plugins install https://github.com/AceDataCloud/WanHermes --enable
hermes config set ACEDATACLOUD_API_KEY '<应用API密钥>'
hermes tools enable acedatacloud-single-wan
hermes tools list
```

默认安装仓库当前默认分支；如需固定版本或回滚，增加 `--ref <40位源码SHA>`，使用本仓已合并源码 commit，启用后开始新会话。CI 验证普通 Git URL 加精确 SHA 安装。要使用官方入口，请打开[官方媒体页面](https://hermes-agent.nousresearch.com/docs/plugins/acedatacloud-media)，安装 `acedatacloud-media` 并选择本服务工具集。未发布 PyPI 新项目，也未承诺本变体另获官方 listing。

1. 打开 [Ace Data Cloud → Applications](https://platform.acedata.cloud/console/applications?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=wanhermes_readme_api_key)，登录或注册。
2. 如未初始化，先初始化“通用应用”；也可选择具有本服务权限的专用应用。在“密钥 / 管理密钥 → 创建”中新建可单独撤销的 Hermes 密钥。
3. 检查到期时间、使用量限制和允许 API。复制不含 `Bearer ` 的原始 Token 到当前 Hermes profile；`platform-...` 管理 Token 不能替代应用 API Key。不要写进提示词或 Git。
4. 调用前检查[当前价格与余额](https://platform.acedata.cloud/models?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=wanhermes_readme_pricing)。试用额度以账户实际显示为准，安装成功不表示免费使用。

![应用密钥获取指引（英文界面原图），来源于已有 Ace 文档](https://raw.githubusercontent.com/AceDataCloud/NanoBananaDify/2522b2f57210597af2db866445319334a1677a23/_assets/tutorial/get-api-key-en.png)

**主操作立即消耗 Credits，不会出现 Hermes 审批提示。** 模型可以选择服务支持的高价模型、分辨率或数量选项。提示词和参考 URL 发送至 `api.acedata.cloud`。启用即允许模型使用密钥调用，schema 限制不等于预算。收费请求**不自动重试**；超时或送达未知时先查请求历史。使用同一任务 ID 恢复 pending 任务，查询不会新建生成。

## 工具与共装

主工具：`acedatacloud_single_wan_generate`。已有任务查询工具为 `acedatacloud_single_wan_task`，传入 `task_id` 及可选 `wait_seconds`（0–60）；pending/预览媒体不视为终态成功。
旧候选 `acedata_` 名称已移除，无别名；原服务如果有任务查询工具，旧任务 ID 可继续查询。

本变体使用 `acedatacloud_single_` 名称及 `acedatacloud-single-wan` 工具集，与官方媒体包的名称分开，避免共装覆盖。两者同时安装时同一服务只启用一种，避免模型重复收费调用；插件不自动改 profile 的其他选择。此服务不注册原生图像后端。

## 单一源码与验收边界

由 [canonical 媒体源码](https://github.com/AceDataCloud/AceDataCloudMediaHermes) 的 `4ebf0fa803b92a1bc8b41fb4d4cd3ce3aacf06a7` 统一生成。`source-lock.json` 固定 transport/schema 的来源、哈希和名称映射，CI 用同一 commit 重新生成比较。runtime/schema 修复先交唯一源，再生成消费仓，不手写维护多套底座。原候选 spec 和历史实测证据保留在 `history/`。

CI 包括 unittest 正常发现、Hermes 0.23.1 官方校验、按精确 SHA 正常 Git 安装、两种隔离模式的单独/共装注册和无效输入 dispatch。mock/宿主兼容不等于新收费请求、唯一账单、当前 GUI、默认预装或官方收录。

![2026-10-18 真实官方媒体目录历史截图](https://github.com/AceDataCloud/AceDataCloudMediaHermes/raw/8eaebfb86152d754061375de881548bfa096dd2d/assets/tutorial/hermes-gpt-image-search.jpg)

截图为 **2026-10-18** 官方媒体 **2.0.1** 历史页面，只展示共同媒体目录项，不是本服务搜索、本源码变体、新收费结果或当前 GUI 验收。
