# 腾讯地图

地点搜索、路线规划、地址与坐标互转、行政区划查询、距离矩阵计算。

由 TotalClaw 自研实现（`totalclaw-mcp-servers` 包），共 7 个工具（只读 7 / 写入 0）。

## 工具

- `search_place`（只读）— 按关键词搜索地点（POI），可限定城市或在指定坐标附近搜索。
- `geocoder`（只读）— 地址转坐标（正解析）：把中文地址解析成经纬度。
- `reverse_geocoder`（只读）— 坐标转地址（逆解析）：把经纬度解析成地址与周边 POI。
- `direction`（只读）— 路线规划，支持驾车、步行、骑行、公交四种方式，返回距离、耗时与路线。
- `distance_matrix`（只读）— 批量计算多个起点到多个终点的距离与耗时。
- `suggestion`（只读）— 地点输入联想补全，用于把用户模糊输入变成候选地点。
- `district_list`（只读）— 获取中国行政区划列表（省市区三级）。

## 安装

```bash
totalclaw mcp install tencent_map
```

## 需要的凭据

- `TENCENT_MAP_KEY`（密钥）

凭据写入 `$TOTALCLAW_HOME/.env`，配置文件里只保留 `${…}` 引用。

上游 API 文档：https://lbs.qq.com/service/webService/webServiceGuide/webServiceOverview

---

> 由 `scripts/gen_manifests.py` 从 `servers/` 的实现自动生成，请勿手改。
