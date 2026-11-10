// 给 dep_gate.py 用：近似按 npm 规则解析顶层包「今天安装会拉到」的完整依赖树。
// 只读 registry 元数据（abbreviated packument），不下载压缩包、不安装、不执行。
// 依赖：dependencies + optionalDependencies + 非可选 peerDependencies（npm 7+ 会自动装）；版本选取优先 latest，
// 否则取满足范围的最高版本。semver 用 npm 自带的那份（node 安装目录里的 npm/node_modules/semver）。
//
//   node scripts/npm_tree.mjs <semver 模块路径> < in.json > out.json
//   in:  [{"entry": "<条目名>", "pkg": "<name>@<version>"}, …]
//   out: {"entries": {"<条目名>": ["name@ver", …]}, "nodes": {"name@ver": {name, version, hasInstallScript, deprecated}}, "errors": […]}
import { createRequire } from "node:module";
import fs from "node:fs";

const semver = createRequire(import.meta.url)(process.argv[2]);
const top = JSON.parse(fs.readFileSync(0, "utf8"));
const REGISTRY = "https://registry.npmjs.org";

const cache = new Map();
let active = 0;
const queue = [];
const limit = (fn) => new Promise((resolve, reject) => {
  const run = async () => {
    active++;
    try { resolve(await fn()); } catch (e) { reject(e); } finally { active--; if (queue.length) queue.shift()(); }
  };
  if (active < 24) run(); else queue.push(run);
});

function packument(name) {
  if (!cache.has(name)) {
    cache.set(name, limit(async () => {
      for (let i = 0; i < 4; i++) {
        try {
          const r = await fetch(`${REGISTRY}/${name.replace("/", "%2f")}`, {
            headers: { Accept: "application/vnd.npm.install-v1+json" }, signal: AbortSignal.timeout(60000),
          });
          if (r.status === 404) return null;
          if (r.ok) return await r.json();
        } catch { /* 重试 */ }
        await new Promise((s) => setTimeout(s, 1500 * (i + 1)));
      }
      throw new Error(`拉取元数据失败：${name}`);
    }));
  }
  return cache.get(name);
}

function pick(doc, range) {
  const versions = Object.keys(doc.versions);
  const tags = doc["dist-tags"] || {};
  if (tags[range]) return tags[range];
  if (!range || range === "*" || range === "latest") return tags.latest && doc.versions[tags.latest] ? tags.latest : semver.maxSatisfying(versions, "*");
  if (tags.latest && semver.satisfies(tags.latest, range)) return tags.latest;
  return semver.maxSatisfying(versions, range) || semver.maxSatisfying(versions, range, { includePrerelease: true });
}

const nodes = {};
const errors = [];

async function resolve(name, range, seen) {
  if (/^(?:npm:|git|https?:|file:|link:|workspace:|github:)/.test(range || "")) {
    if (range.startsWith("npm:")) {  // 别名 "npm:real-name@range"
      const spec = range.slice(4);
      const at = spec.lastIndexOf("@");
      return resolve(at > 0 ? spec.slice(0, at) : spec, at > 0 ? spec.slice(at + 1) : "*", seen);
    }
    errors.push(`${name}@${range}：不是 registry 依赖，未解析`);
    return;
  }
  let doc;
  try { doc = await packument(name); } catch (e) { errors.push(String(e.message || e)); return; }
  if (!doc) { errors.push(`${name}：npm 上不存在（404）`); return; }
  const v = pick(doc, range);
  if (!v) { errors.push(`${name}@${range}：没有满足范围的版本`); return; }
  const key = `${name}@${v}`;
  if (seen.has(key)) return;
  seen.add(key);
  const m = doc.versions[v];
  nodes[key] ??= { name, version: v, hasInstallScript: !!m.hasInstallScript, deprecated: m.deprecated || "" };
  const peerMeta = m.peerDependenciesMeta || {};
  const deps = { ...(m.dependencies || {}), ...(m.optionalDependencies || {}) };
  for (const [p, r] of Object.entries(m.peerDependencies || {})) if (!peerMeta[p]?.optional && !(p in deps)) deps[p] = r;
  await Promise.all(Object.entries(deps).map(([d, r]) => resolve(d, r, seen)));
}

const entries = {};
await Promise.all(top.map(async (t) => {
  const at = t.pkg.lastIndexOf("@");
  const seen = new Set();
  await resolve(at > 0 ? t.pkg.slice(0, at) : t.pkg, at > 0 ? t.pkg.slice(at + 1) : "latest", seen);
  entries[t.entry] = [...(entries[t.entry] || []), ...seen];
}));
process.stdout.write(JSON.stringify({ entries, nodes, errors }));
