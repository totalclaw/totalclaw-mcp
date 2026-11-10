#!/bin/sh
# 装 pre-push 钩子：推送前跑与 Gitee Go 门禁同样的离线检查，不过就拒绝推送（说明见 SECURITY-GATE.md）。
# 用法：sh scripts/install-git-hooks.sh    重复运行会覆盖本脚本装过的旧版，不动别人的钩子。
set -e
root=$(git rev-parse --show-toplevel)
hooks=$(git -C "$root" rev-parse --git-path hooks)
case $hooks in /*) ;; *) hooks="$root/$hooks" ;; esac
hook="$hooks/pre-push"
marker='# installed-by: scripts/install-git-hooks.sh'
if [ -e "$hook" ] && ! grep -qF "$marker" "$hook"; then
  echo "已有别的 pre-push 钩子：$hook" >&2
  echo "请手工在里面加：python3 scripts/review_static.py --scan-registry && python3 scripts/gen_registry.py --check --strict && python3 scripts/dep_gate.py --check || exit 1" >&2
  exit 1
fi
mkdir -p "$hooks"
cat > "$hook" <<'HOOK'
#!/bin/sh
# installed-by: scripts/install-git-hooks.sh
# 推送前离线检查（清单查毒 + registry.json 一致性 + 恶意版本黑名单，几秒内）。git push --no-verify 能跳过这里，但跳不过 PR 门禁。
# shortcut: 查的是工作区而非精确的待推送提交（多数人推的就是当前分支）；精确把关靠流水线。
cd "$(git rev-parse --show-toplevel)" || exit 1
python3 scripts/review_static.py --scan-registry && python3 scripts/gen_registry.py --check --strict && exec python3 scripts/dep_gate.py --check
HOOK
chmod +x "$hook"
echo "已安装 $hook"
