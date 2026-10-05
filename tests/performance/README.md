# 性能测试说明

本目录用于量化漫画/视频本地库和预览库的加载、搜索、筛选、排序、封面等性能。默认测试门禁不会自动运行这里的压测，避免日常开发变慢。

## 1. 生成大数据集

```powershell
python tests/tools/generate_perf_dataset.py --output tests/.runtime/perf/data/meta_data --items 20000 --tags 500 --lists 200
```

生成后可以把 `server_config.json` 的 `storage.data_dir` 指向 `tests/.runtime/perf/data`，再启动后端。

## 2. 重建/查看 SQLite 索引

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:5035/api/v1/performance/catalog-index/rebuild
Invoke-RestMethod http://127.0.0.1:5035/api/v1/performance/catalog-index/status
```

## 3. 测量关键接口延迟

```powershell
python tests/tools/measure_catalog_api.py --base-url http://127.0.0.1:5035 --rounds 30
```

输出包含每个接口的 `min/p50/p95/max/avg`，同时读取 `X-Ultimate-Elapsed-Ms` 来区分客户端整体耗时和服务端应用耗时。

## 4. 运行索引 smoke benchmark

```powershell
pytest -q tests/performance/benchmark/test_catalog_index_benchmark.py
```

## 5. k6 接口压测

```powershell
k6 run -e BASE_URL=http://127.0.0.1:5035 tests/performance/http/catalog_api_perf.js
```

当前阈值用于第一阶段看护：漫画/视频分页列表 p95 应低于 350ms。真实阈值应在本机 2 万、5 万条数据基线完成后再收紧。
