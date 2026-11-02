# 合入门禁

2026-11-02 技能库被 ClawHavoc 投毒（假「前置安装」、base64 混淆的下载即执行、带密码安装包、MCP 配置指向匿名隧道）。同类手法同样可能出现在注册表清单里，这份门禁让它们进不了 master。

## 门禁做什么

| 层 | 在哪 | 什么时候跑 | 拦不拦得住 |
|---|---|---|---|
| 流水线 | `.workflow/registry-gate.yml`（Gitee Go） | 发起 / 更新 PR；合入或推送 master 后 | 配合保护分支后，检查不过的 PR 合不进 master |
| 本地钩子 | `sh scripts/install-git-hooks.sh` 装 pre-push | 每次 `git push` 前 | 只防手滑，`--no-verify` 能跳过 |

只跑离线、只读的检查，不联网审包，不安装任何被审核的第三方包：

```
python3 scripts/review_static.py --selftest        # 扫描规则自检
python3 scripts/review_static.py --scan-registry   # 注册表文本查毒（命中退出码 1）
python3 scripts/gen_registry.py --check --strict   # registry.json 与清单逐文件 sha256 一致、包版本必须钉死
```

`--scan-registry` 把 `review_static.py` 的高危规则（下载即执行、解码进 shell、已知投毒特征、可疑外传端点与匿名隧道、提示注入话术、硬编码公网 IP、解码后执行、读 SSH 私钥 / 浏览器凭据 / 钱包等）加上隐藏 Unicode（零宽、双向控制、Tag 字符）检查，跑遍 `registry/servers/` 下全部文本文件（mcp.yaml、README.md、tools.json、svg）。只打印 `文件:行  [规则]`，不打印原文。两处有意跳过：

- 已下架条目（`scan_verdict: block`）整目录跳过：桌面端不列出它们、还会停掉本机已装的同名连接器，而它们的 `security.reason` 正是在引用下架原因的原话。
- mcp.yaml 文件头的注释块跳过：注释不进解析结果，审核意见会引用被拒原因。正文里 `#` 开头的行可能在块标量里、是真内容，照扫。

流水线里唯一会安装的是 `gen_registry.py` 自己要的 PyYAML：镜像里已有就不装，没有才装钉死的 `PyYAML==6.0.2`，且只收 wheel（`--only-binary=:all:`，不执行任何安装脚本）。

`.github/workflows/ci.yml` 是 GitHub Actions 配置，仓库在 Gitee 上时不会运行，门禁以 Gitee Go 为准。

## 需要仓库管理员在网页上做的（一次性）

没有这几步，流水线只会「报红」，拦不住合入。菜单文字以 Gitee 页面实际显示为准。

1. **开通 Gitee Go**：仓库页顶部「流水线」（部分页面在「服务」→「Gitee Go」）→ 开通（账号要绑手机号）。开通时如果提示「用模板创建流水线」，选**不创建 / 自定义**；万一生成了 `MasterPipeline.yml`、`BranchPipeline.yml`、`PRPipeline.yml`，把它们删掉。Gitee Go 读取仓库里已提交的 `.workflow/registry-gate.yml`，流水线列表里会出现「MCP 注册表门禁」。
2. **先让它跑一次**：开一个指向 master 的 PR，确认流水线跑起来并且是绿的。Gitee 只允许勾选「最近一周执行过的检查项」，所以这一步要在第 3 步之前。
3. **把 master 设成保护分支并要求门禁通过**：仓库「管理」→「保护分支设置」→ 新建规则（或编辑已有的 master 规则）：
   - 分支：`master`
   - 可推送代码成员：**不允许任何人**（想让没权限的推送自动变成 PR，可以把规则设成「评审模式」）
   - 可合并 Pull Request 成员：仓库管理员（或指定的审核人）
   - 勾选 **「要求门禁状态成功才能合并」**，检查项勾上「MCP 注册表门禁」（registry-gate）
   - 保存后回到「代码」→「分支」，确认 master 的分支状态是「保护分支」
4. **要求人工评审**：合并前至少 1 人审查通过。原因见「已知局限」第 1 条。
5. **清点谁能绕过**：仓库管理员可以跳过门禁强制合并；企业版的超级管理员、拥有者、管理员不受保护分支规则约束。不需要管理权限的账号在「管理」→「仓库成员管理」里降为「开发者」。

## 误报怎么办

1. 按输出的 `文件:行` 打开看。确属有问题的条目：按 `review_static.py` 的流程下架（`scan_verdict: block` + `security.reason`），再跑 `gen_registry.py`。
2. 确属误报：在 PR 里改 `scripts/review_static.py` 的 `HIGH_PATTERNS`（收紧正则），PR 描述写清是哪个条目、为什么无害，本地跑 `--selftest` 和 `--scan-registry` 确认。
3. 不许做的事：在 yml 里加 `|| true`、为了过门禁把正常条目标成 block、删掉检查步骤。这类改动审查时直接打回。

## 已知局限

1. Gitee Go 对 PR 用**源分支最新提交里的 yml 和脚本**跑，所以一个 PR 可以顺手把门禁本身改弱。动到 `.workflow/`、`scripts/review_static.py`、`scripts/gen_registry.py` 的 PR 必须人工逐行看（也可以用 Gitee 的 CODEOWNERS 给这些路径指定负责人）。
2. 有权限的人仍可强制合并。push master 触发的那次流水线只能事后发现，不能阻止。
3. 门禁只看注册表文本；包代码要靠 `review_static.py` 的联网静态审核（下载到内存扫描），那一步不在门禁里跑。

## 依据的 Gitee 文档

- 流水线触发（push / PR 语法、PR 预合并与「读源分支 yml」）：https://help.gitee.com/gitee-go/pipeline/trigger
- 流水线基本字段：https://help.gitee.com/gitee-go/pipeline/basic-config
- 云端编译插件（`build@python` 支持 2.7–3.9）：https://help.gitee.com/gitee-go/plugin/ci-build
- 开通 Gitee Go：https://help.gitee.com/gitee-go/get-started-in-3-steps
- PR 门禁检查（「要求门禁状态成功才能合并」、管理员可强制合并）：https://help.gitee.com/base/pullrequest/ci-check
- 保护分支与评审模式：https://help.gitee.com/repository/branch/protected-branches
- 保护分支规则细节：https://help.gitee.com/enterprise/repo/%E8%AE%BE%E7%BD%AE%E4%BF%9D%E6%8A%A4%E5%88%86%E6%94%AF
- CODEOWNERS：https://help.gitee.com/repository/extend/%E5%A6%82%E4%BD%95%E4%BD%BF%E7%94%A8CodeOwners%E5%8A%9F%E8%83%BD
