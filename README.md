# 漫画阅读系统

一个前后端分离的漫画阅读系统，支持漫画管理、阅读进度保存、图片懒加载等功能。

## 技术栈

### 后端
- Flask 2.3.0
- Flask-CORS 4.0.0
- Pillow
- JSON文件存储

### 前端
- Vue 3
- Vite
- Vue Router 4
- Pinia
- Axios
- Vant UI 组件库

## 项目结构

```
ULTIMATE_WEB/
├── comic_backend/          # 后端代码
│   ├── app.py              # 应用入口
│   ├── routes/             # 路由
│   ├── services/           # 业务逻辑
│   ├── utils/              # 工具函数
│   ├── data/               # 数据目录
│   └── requirements.txt     # 依赖文件
├── comic_frontend/         # 前端代码
│   ├── src/                # 源代码
│   ├── public/             # 静态资源
│   └── package.json        # 依赖文件
├── scripts/                 # 脚本目录
│   ├── start_project.ps1   # Windows启动脚本
│   ├── start_project.sh    # Linux启动脚本
│   ├── start_backend.ps1   # Windows单独启动后端
│   ├── start_backend.sh    # Linux单独启动后端
│   ├── start_frontend.ps1  # Windows单独启动前端
│   ├── start_frontend.sh   # Linux单独启动前端
│   ├── stop_services.ps1   # Windows停止脚本
│   ├── stop_services.sh    # Linux停止脚本
│   ├── view_status.ps1     # Windows查看状态脚本
│   ├── view_status.sh      # Linux查看状态脚本
│   ├── run_tests.ps1       # Windows运行测试脚本
│   └── run_tests.sh        # Linux运行测试脚本
├── tests/                  # 测试目录
│   └── test_api.py         # API测试用例
├── start_project.ps1       # Windows一键启动（调用scripts目录）
├── README.md               # 项目说明
└── 开发进展/                # 开发文档
```

## 快速开始

### 1. 安装依赖

#### 后端依赖
```bash
cd comic_backend
pip install -r requirements.txt
```

#### 前端依赖
```bash
cd comic_frontend
npm install
```

### 2. 启动项目

#### Windows (PowerShell)
```powershell
.\start_project.ps1
```

#### Linux/Mac (Bash)
```bash
chmod +x scripts/*.sh
./start_project.sh
```

#### 单独启动后端/前端

如果只想启动单个服务：

##### Windows
```powershell
# 只启动后端
.\scripts\start_backend.ps1

# 只启动前端
.\scripts\start_frontend.ps1
```

##### Linux/Mac
```bash
# 只启动后端
./scripts/start_backend.sh

# 只启动前端
./scripts/start_frontend.sh
```

启动脚本会：
- 自动检查依赖文件
- 先停止已运行的服务（避免端口冲突）
- 启动后端服务（Flask）
- 启动前端服务（Vite 开发服务器）
- 显示服务访问地址

### 3. 访问服务

- **前端地址**: http://localhost:5173/
- **后端地址**: http://127.0.0.1:5000

### 4. 查看服务状态

#### Windows
```powershell
.\scripts\view_status.ps1
```

#### Linux/Mac
```bash
./scripts/view_status.sh
```

### 5. 停止项目

#### Windows
```powershell
.\scripts\stop_services.ps1
```

#### Linux/Mac
```bash
./scripts/stop_services.sh
```

## 测试

使用测试脚本运行API测试：

#### Windows
```powershell
.\scripts\run_tests.ps1
```

#### Linux/Mac
```bash
./scripts/run_tests.sh
```

## 功能特性

- ✅ 漫画列表展示
- ✅ 漫画详情查看
- ✅ 漫画阅读（支持左右/上下翻页）
- ✅ 阅读进度自动保存
- ✅ 图片懒加载
- ✅ 响应式布局
- ✅ 搜索功能
- ✅ 分类标签
- ✅ 内容预览
- ✅ 标签管理（增删改查）
- ✅ 批量标签操作

## 数据结构

### 漫画数据结构
```json
{
  "id": "1024707",
  "title": "漫画标题",
  "author": "作者",
  "cover_path": "/static/cover/1024707.jpg",
  "total_page": 199,
  "current_page": 1,
  "score": 9.5,
  "tag_ids": ["tag_001", "tag_002"],
  "last_read_time": "2026-02-27T22:34:43",
  "create_time": "2026-02-27T22:34:43"
}
```

### 标签数据结构
```json
{
  "id": "tag_001",
  "name": "标签名称",
  "create_time": "2026-02-27T22:34:43"
}
```

## API接口

### 后端API
- `GET /health` - 健康检查
- `GET /api/v1/comic/list` - 获取漫画列表
- `GET /api/v1/comic/detail` - 获取漫画详情
- `GET /api/v1/comic/images` - 获取图片列表
- `GET /api/v1/comic/image` - 获取单张图片
- `PUT /api/v1/comic/progress` - 保存阅读进度
- `PUT /api/v1/comic/score` - 更新评分
- `PUT /api/v1/comic/tag/bind` - 绑定标签
- `PUT /api/v1/comic/tag/batch-add` - 批量添加标签
- `PUT /api/v1/comic/tag/batch-remove` - 批量移除标签
- `GET /api/v1/comic/search` - 搜索漫画
- `GET /api/v1/comic/filter` - 筛选漫画
- `GET /api/v1/tag/list` - 获取标签列表
- `POST /api/v1/tag/add` - 添加标签
- `PUT /api/v1/tag/edit` - 编辑标签
- `DELETE /api/v1/tag/delete` - 删除标签
- `GET /api/v1/tag/comics` - 获取指定标签的漫画

## 开发规范

- 小步迭代 + 进展记录
- 测试驱动开发（TDD）
- 代码风格统一
- 注释清晰

## 跨平台支持

### Windows
- PowerShell 5.1+
- Python 3.8+
- Node.js 16+

### Linux
- Bash
- Python 3.8+
- Node.js 16+

### Mac
- Bash/Terminal
- Python 3.8+
- Node.js 16+

## 常见问题

### 1. 启动脚本输出乱码
**解决方案**：已修复，所有脚本都已添加 UTF-8 编码设置

### 2. 服务启动失败
**解决方案**：
- 检查是否已安装依赖
- 确认端口 5000 和 5173 未被占用
- 使用 `.\scripts\view_status.ps1`（Windows）或 `./scripts/view_status.sh`（Linux）查看服务状态

### 3. 前端无法访问后端
**解决方案**：
- 确认后端服务已启动
- 检查 Vite 代理配置
- 查看浏览器控制台错误信息

## data 目录结构说明

### 目录概览
```
data/
├── cache/                   # 缓存目录
├── meta_data/               # 元数据目录（核心数据库）
└── recommendation_cache/    # 推荐内容缓存目录
```

---

### 1. cache/ - 缓存目录

**用途**：存储各类临时缓存数据，提高系统性能

**文件说明**：
- `author_works_author_works_*.json`
  - **作用**：缓存作者作品列表数据
  - **更新时机**：首次查询某作者作品时创建，后续直接使用缓存
  - **新增内容**：添加新作者或查询新作者作品时会新增对应文件

---

### 2. meta_data/ - 元数据目录（核心数据库）

**用途**：存储系统的核心业务数据，采用 JSON 文件格式存储

#### 2.1 主数据库文件

| 文件名 | 作用 | 更新时机 | 新增内容 |
|--------|------|----------|----------|
| `comics_database.json` | 主页漫画数据库，存储所有收藏的漫画信息 | 添加/修改/删除漫画、更新阅读进度、更新评分、绑定标签时更新 | 导入新漫画时新增漫画记录 |
| `recommendations_database.json` | 推荐页漫画数据库，存储推荐漫画信息 | 添加/修改/删除推荐漫画时更新 | 导入新推荐漫画时新增记录 |
| `tags_database.json` | 标签数据库，存储所有标签信息 | 添加/修改/删除标签时更新 | 创建新标签时新增标签记录 |
| `lists_database.json` | 清单数据库，存储用户创建的漫画清单 | 添加/修改/删除清单时更新 | 创建新清单时新增清单记录 |
| `actors_database.json` | 演员数据库（视频功能） | 添加/修改/删除演员信息时更新 | 添加新演员时新增记录 |
| `authors_database.json` | 作者数据库 | 添加/修改/删除作者信息时更新 | 添加新作者时新增记录 |
| `videos_database.json` | 视频数据库 | 添加/修改/删除视频时更新 | 导入新视频时新增记录 |
| `video_recommendations_database.json` | 视频推荐数据库 | 添加/修改/删除视频推荐时更新 | 添加新视频推荐时新增记录 |
| `import_tasks.json` | 导入任务数据库，存储漫画/视频导入任务状态 | 创建任务、任务进度更新、任务完成/失败时更新 | 创建新导入任务时新增任务记录 |
| `recommendation_cache_index.json` | 推荐缓存索引，管理推荐内容缓存 | 添加/删除推荐缓存、更新缓存访问时间时更新 | 新增推荐内容到缓存时新增索引记录 |

#### 2.2 备份文件（*.bkp）
- **作用**：JSON 数据库文件的实时备份，防止数据损坏
- **更新时机**：每次写入主数据库前自动创建备份
- **注意**：这些是自动备份文件，无需手动维护

#### 2.3 backup/ - 三级备份目录
包含子目录：`lists_database/`、`recommendations_database/`、`tags_database/` 等

**备份策略**：
- **Tier 1**：每 10 分钟备份一次，保留最近 3 个版本（30 分钟历史）
- **Tier 2**：每 1 小时备份一次（从 Tier 1 复制），保留最近 3 个版本（3 小时历史）
- **Tier 3**：每 1 天备份一次（从 Tier 2 复制），保留最近 3 个版本（3 天历史）

**文件说明**：
- `*_tier*.time`：记录该层级上次备份时间的时间戳文件
- `*_tier*_YYYYMMDD_HHMMSS.bkp`：具体的备份文件，带时间戳

#### 2.4 临时文件（*.tmp）
- **作用**：JSON 写入时的临时文件，确保写入操作的原子性
- **更新时机**：每次写入数据库时临时创建，写入成功后自动删除
- **注意**：如果系统异常中断，可能会残留 tmp 文件，可以安全删除

---

### 3. recommendation_cache/ - 推荐内容缓存目录

**用途**：存储推荐页漫画/视频的图片缓存，使用 LRU（最近最少使用）算法管理

**目录结构**：
```
recommendation_cache/
├── JM/          # 禁漫天堂平台内容缓存
│   └── {漫画ID}/
│       └── {章节}/
│           └── 00001.jpg, 00002.jpg, ...
└── PK/          # 哔咔漫画平台内容缓存
    └── comics/
        └── {作者名}/
            └── {漫画名}/
                └── {章节名}/
                    └── 0001.jpg, 0002.jpg, ...
```

**管理机制**：
- **最大容量**：默认 5120 MB（可配置）
- **淘汰策略**：当缓存容量满时，自动淘汰最久未访问的内容
- **索引管理**：通过 `meta_data/recommendation_cache_index.json` 管理缓存索引

**更新时机**：
- 阅读推荐页内容时，如果图片未缓存则下载并缓存
- 访问已缓存内容时更新访问时间（移到 LRU 队列末尾）
- 缓存容量不足时自动淘汰旧缓存

**新增内容**：
- 首次阅读某推荐内容时，下载图片并添加到缓存
- 通过 API 主动将内容添加到缓存

---

## 数据文件维护建议

### 日常维护
1. **不要手动修改**：建议通过系统 API 或前端界面操作数据，避免直接编辑 JSON 文件
2. **备份重要**：`meta_data/backup/` 目录中的三级备份非常重要，不要删除
3. **临时文件**：如有残留的 `.tmp` 文件，可以安全删除
4. **缓存清理**：可以通过 API 清理推荐缓存，释放磁盘空间

### 数据恢复
如果主数据库损坏，可以：
1. 先尝试使用同目录下的 `.bkp` 备份恢复（去掉 `.bkp` 后缀）
2. 如果不行，使用 `meta_data/backup/` 目录中的三级备份
3. 通过备份管理 API 选择特定时间点的备份恢复

### 磁盘空间管理
- 监控 `recommendation_cache/` 目录大小，必要时清理
- 定期清理 `import_tasks.json` 中已完成的旧任务
- 三级备份会自动轮转，无需手动清理

---

## 第三方库敏感数据配置说明

### 排查结果

经过详细排查，确认以下三个第三方库的配置情况：

1. **JMComic (禁漫天堂)** ✅ 符合要求
   - 配置文件：`comic_backend/third_party/JMComic-Crawler-Python/config.json`
   - 适配器：`comic_backend/third_party/jmcomic_adapter.py`
   - 状态：敏感数据已从代码中移除，统一从 `third_party_config.json` 读取

2. **Picacomic (哔咔漫画)** ✅ 符合要求
   - 配置文件：`comic_backend/third_party/Picacomic-Crawler/config.json`
   - 适配器：`comic_backend/third_party/picacomic_adapter.py`
   - 状态：敏感数据已从代码中移除，统一从 `third_party_config.json` 读取

3. **JavDB** ✅ 符合要求
   - 配置文件：`comic_backend/third_party_config.json`（主配置）
   - 适配器：`comic_backend/third_party/javdb_api_scraper.py`
   - 状态：敏感数据已从代码中移除，统一从 `third_party_config.json` 读取
   - 已清理：`javdb-api-scraper/config.py` 和 `javdb-api-scraper/cookies.json` 中的敏感数据

### 配置方法

#### 1. 配置文件位置

核心配置文件位于：
```
comic_backend/third_party_config.json
```

**重要**：请将此文件添加到 `.gitignore` 中，避免敏感数据被提交到 Git 仓库！

#### 2. 配置文件格式

```json
{
  "default_adapter": "jmcomic",
  "adapters": {
    "jmcomic": {
      "enabled": true,
      "config_path": "JMComic-Crawler-Python/config.json",
      "username": "你的JMComic用户名",
      "password": "你的JMComic密码",
      "download_dir": "data/pictures",
      "output_json": "comics_database.json",
      "progress_file": "download_progress.json",
      "favorite_list_file": "favorite_comics.txt",
      "consecutive_hit_threshold": 10,
      "collection_name": "我的最爱"
    },
    "picacomic": {
      "enabled": true,
      "account": "你的哔咔邮箱账号",
      "password": "你的哔咔密码",
      "base_dir": "data/pictures/PK"
    },
    "javdb": {
      "enabled": true,
      "domain_index": 0,
      "timeout": 30,
      "retry_times": 3,
      "sleep_time": 0.5,
      "cookies": {}
    }
  }
}
```

#### 3. 各平台配置说明

**JMComic (禁漫天堂)**：
- `username`：JMComic 账号用户名
- `password`：JMComic 账号密码
- 如果不填写账号密码，仍可使用部分公共功能，但无法访问收藏夹和下载限制内容

**Picacomic (哔咔漫画)**：
- `account`：哔咔注册邮箱账号
- `password`：哔咔账号密码
- 哔咔平台需要登录才能使用搜索、下载等功能

**JavDB**：
- `domain_index`：域名索引（0-2，用于自动切换域名）
- `timeout`：请求超时时间（秒）
- `retry_times`：请求失败重试次数
- `sleep_time`：请求间隔时间（秒）
- `cookies`：登录后的 cookie 数据（JSON 对象格式，可选）
- 当前版本无需配置账号密码即可使用基础功能
- 如需使用登录功能，可将登录后的 cookies 填入配置

#### 4. 工作原理

1. 系统启动时，`AdapterConfig` 类会加载 `third_party_config.json`
2. 各适配器通过 `BaseAdapter.get_config()` 方法读取配置
3. JMComic 适配器会动态将配置写入其自身的 `config.json` 文件
4. Picacomic 适配器直接在内存中使用配置，不写入磁盘
5. 所有敏感数据仅存在于 `third_party_config.json` 中，代码库中无硬编码

#### 5. 安全建议

- ✅ 务必将 `comic_backend/third_party_config.json` 添加到 `.gitignore`
- ✅ 定期备份配置文件，但不要将备份提交到代码仓库
- ✅ 不同环境（开发/测试/生产）使用不同的配置文件
- ✅ 不要在代码注释、文档或日志中泄露敏感信息
- ✅ 如发现配置文件被意外提交，立即更改相关账号密码

#### 6. .gitignore 配置建议

在项目根目录的 `.gitignore` 文件中添加：
```
# 第三方库敏感配置
comic_backend/third_party_config.json
comic_backend/third_party/JMComic-Crawler-Python/config.json
comic_backend/third_party/Picacomic-Crawler/config.json
comic_backend/third_party/javdb-api-scraper/config.py
comic_backend/third_party/javdb-api-scraper/cookies.json
comic_backend/third_party/javdb-api-scraper/third_party_config.json
```
