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
./scripts/start_project.sh
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
