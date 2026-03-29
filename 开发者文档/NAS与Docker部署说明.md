# NAS 与 Docker 部署说明

本文档面向希望在 NAS（群晖、威联通、Unraid 等）上以 Docker 方式运行 Ultimate Web 的开发者/用户。

## 1. 目标与范围

本方案目标：

1. 服务端直接运行在 NAS 容器中，不再依赖个人电脑长期在线。
2. `data` 数据目录持久化到 NAS 卷，容器重启或升级不丢数据。
3. 服务端路径导入可直接读取 NAS 上的漫画/视频目录。
4. 尽量不影响当前代码主干、测试工作流和三端打包流程。

本次提供：

1. 根目录 `Dockerfile`
2. 根目录 `docker-compose.yml`
3. 根目录 `.dockerignore`

---

## 2. 目录与端口约定

默认容器对外端口：

1. `5000`（后端 API + 已构建前端页面）

默认关键路径（容器内）：

1. 配置文件：`/app/server_config.json`
2. 第三方配置：`/app/comic_backend/third_party_config.json`
3. 数据目录（默认）：`/app/comic_backend/data`

---

## 3. 快速启动

在项目根目录执行：

```bash
docker compose build
docker compose up -d
```

启动后访问：

1. `http://<NAS_IP>:5000`

查看日志：

```bash
docker compose logs -f app
```

停止：

```bash
docker compose down
```

---

## 4. Volume 挂载说明（重点）

`docker-compose.yml` 已包含这些默认挂载：

1. `./server_config.json:/app/server_config.json`
2. `./comic_backend/third_party_config.json:/app/comic_backend/third_party_config.json`
3. `./data:/app/comic_backend/data`

注意：`./` 相对路径基于 `docker-compose.yml` 所在目录。  
如果你在 NAS 的可视化容器面板里直接粘贴 Compose（而不是在仓库根目录执行），建议改成 NAS 绝对路径，避免挂载错位。

如果你要做“服务端路径导入 NAS 媒体目录”，请额外挂载媒体路径，例如：

```yaml
volumes:
  - /volume1/library/comics:/library/comics:rw
  - /volume1/library/videos:/library/videos:rw
```

此时前端“服务端路径导入”里应填写容器内路径，如：

1. `/library/comics`
2. `/library/videos`

不是 Windows 映射盘路径，也不是你电脑本地路径。

---

## 5. 服务端路径导入与容器路径关系

当前后端校验逻辑是“路径必须存在于服务端所在设备可访问的本机路径”。

在 Docker/NAS 模式下：

1. “服务端所在设备” = 容器运行环境（容器可见文件系统）
2. 因此路径必须是“容器内可见路径”
3. 浏览器 `fakepath` 虚拟路径仍会被拒绝（这是正确行为）

结论：只要 Volume 正确挂载，并输入容器内绝对路径，就能正常导入。

---

## 6. 与“超大文件移动导入”相关的注意事项

你已实现的“超大文件移动导入（move_huge）”会检查源目录与目标目录是否同一文件系统。

### 6.1 自动降级行为

当检测到不同文件系统时，会自动降级为复制导入（`copy_safe`），并给出警告。

### 6.2 为什么会降级

典型场景：

1. 源目录挂载为 `/library/comics`
2. 数据目录挂载为 `/app/comic_backend/data`
3. 两者来自不同 NAS 卷或不同挂载点

这时无法保证原子级移动，系统会降级复制，避免不安全移动。

### 6.3 如何尽量保持“移动导入”

将源目录和数据目录放在同一 NAS 文件系统下，例如：

1. 挂载整块共享盘到容器：`/volume1:/nas`
2. 在 `server_config.json` 中设置：

```json
{
  "storage": {
    "data_dir": "/nas/ultimate_data"
  }
}
```

3. 服务端路径导入使用 `/nas/comics` 之类路径

这样源和目标更容易满足同盘条件。

---

## 7. 数据迁移（从已有本地部署迁移）

如果你已经有旧数据目录：

1. 先停止旧服务，确保没有写入。
2. 将旧 `data` 完整复制到 NAS 目标目录。
3. 保持 `server_config.json` 的 `storage.data_dir` 与容器挂载一致。
4. 启动容器后验证：
   1. 本地库可见
   2. 阅读进度在
   3. 标签/清单在

建议首次迁移先备份一份原始 `data`。

---

## 8. 权限与系统依赖

### 8.0 第三方配置路径迁移（重要）

仓库中的 `third_party_config.json` 可能包含 Windows 绝对路径（例如 `D:\...`）。  
在 NAS Docker 环境中，这些路径通常无效，需要改成容器内路径。

建议检查并修正：

1. `download_dir`
2. `base_dir`
3. 任何自定义文件路径字段

示例（容器内路径）：

1. `/app/comic_backend/data/comic/JM`
2. `/app/comic_backend/data/comic/PK`
3. 或你挂载的媒体目录路径（如 `/library/comics`）

未修正时，第三方同步/下载可能失败，但本地库浏览功能通常仍可运行。

### 8.1 文件权限

容器用户必须对这些路径有读写权限：

1. 数据目录
2. 导入源目录（至少读取；使用移动导入时需写入/重命名权限）

NAS 上如出现权限问题，优先检查：

1. 共享文件夹 ACL
2. Docker 容器运行用户（可用 `user: "<uid>:<gid>"`）

### 8.2 压缩格式依赖

镜像已安装：

1. `p7zip-full`
2. `unrar-free`

但不同 NAS 发行版、不同 `rar` 压缩特性下，仍可能出现个别压缩包兼容问题。遇到问题可在日志中定位具体文件后重打包测试。

---

## 9. 安全建议

1. 默认仅建议在内网使用。
2. 不要直接将 `5000` 暴露到公网。
3. 如需公网访问，建议放在反向代理后并加鉴权（如 Nginx + Basic Auth / OAuth 网关）。
4. 第三方账号配置仅保存在你挂载的配置文件中，请做好权限隔离和备份。

---

## 10. 常见问题排查

### Q1：页面能打开，但“服务端路径导入”提示路径不存在

检查顺序：

1. 该目录是否已挂载进容器
2. 你填的是不是容器内路径（如 `/library/comics`）
3. 容器用户是否有读权限

### Q2：启用“超大文件移动导入”后仍提示降级复制

说明源目录和目标目录不在同一文件系统。请按第 6.3 节调整挂载与 `data_dir`。

### Q3：升级镜像后数据丢失

通常是未挂载持久化目录导致。确认 `data` 与配置文件都在 volume 中。

---

## 11. 验收清单（建议）

部署后至少执行一次以下检查：

1. 打开首页并完成基础浏览。
2. 执行一次“服务端路径导入（文件夹）”。
3. 若有超大目录，测试一次“超大文件移动导入”并观察是否降级。
4. 重启容器后确认：
   1. 本地库数据仍在
   2. 标签/清单仍在
   3. 可恢复导入会话可继续

---

## 12. 对 CI/CD 的影响说明

本次 Docker 支持为增量能力：

1. 不改变现有 `test-gate`（集成 + E2E）流程
2. 不改变现有三端打包发布流程

如需增强，可后续新增独立的 Docker 构建冒烟 Job（可选）。
