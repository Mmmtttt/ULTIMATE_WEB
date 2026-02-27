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
│   ├── utils/              # 工具函数
│   ├── data/               # 数据目录
│   └── requirements.txt    # 依赖文件
├── comic_frontend/         # 前端代码
│   ├── src/                # 源代码
│   ├── public/             # 静态资源
│   └── package.json        # 依赖文件
├── tests/                  # 测试目录
│   └── test_api.py         # API测试用例
├── start_project.ps1       # 启动脚本
├── stop_project.ps1        # 停止脚本
├── view_logs.ps1           # 查看日志脚本
├── run_tests.ps1           # 测试脚本
└── README.md               # 项目说明
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

使用一键启动脚本（推荐）：

```bash
# Windows PowerShell
.\start_project.ps1
```

启动脚本会：
- 自动检查依赖文件
- 启动后端服务（Flask）
- 启动前端服务（Vite 开发服务器）
- 显示服务访问地址

### 3. 访问服务

- **前端地址**: http://localhost:5173/
- **后端地址**: http://127.0.0.1:5000

### 4. 查看服务状态

```bash
# Windows PowerShell
.\view_logs.ps1
```

查看日志脚本会显示：
- 后端和前端进程信息
- 服务可用性测试结果
- HTTP 状态码

### 5. 停止项目

```bash
# Windows PowerShell
.\stop_project.ps1
```

停止脚本会：
- 停止所有 Python 进程（后端）
- 停止所有 Node.js 进程（前端）
- 清理临时文件

## 测试

使用测试脚本运行API测试：

```bash
# Windows PowerShell
.\run_tests.ps1
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
  "last_read_time": "2026-02-27T22:34:43",
  "create_time": "2026-02-27T22:34:43",
  "tag_ids": ["1", "2", "3"]
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

## 开发规范

- 小步迭代 + 进展记录
- 测试驱动开发（TDD）
- 代码风格统一
- 注释清晰

## 后续计划

1. **第二阶段**：
   - 实现标签管理功能
   - 实现搜索和筛选功能
   - 实现评分系统
   - 完善详情页展示

2. **性能优化**：
   - 优化图片加载性能
   - 实现图片懒加载
   - 优化前端渲染性能

3. **界面优化**：
   - 优化移动端适配
   - 改进阅读体验
   - 添加更多交互效果

## 脚本说明

### start_project.ps1
- 一键启动后端和前端服务
- 自动检查依赖文件
- 显示服务访问地址
- 修复了输出乱码问题

### stop_project.ps1
- 一键停止所有服务
- 停止 Python 和 Node.js 进程
- 清理临时文件
- 修复了输出乱码问题

### view_logs.ps1
- 查看服务运行状态
- 显示进程信息
- 测试服务可用性
- 修复了输出乱码问题

### run_tests.ps1
- 运行 API 测试用例
- 检查后端服务状态
- 显示测试结果

## 常见问题

### 1. 启动脚本输出乱码
**解决方案**：已修复，所有脚本都已添加 UTF-8 编码设置

### 2. 服务启动失败
**解决方案**：
- 检查是否已安装依赖
- 确认端口 5000 和 5173 未被占用
- 使用 `.\view_logs.ps1` 查看服务状态

### 3. 前端无法访问后端
**解决方案**：
- 确认后端服务已启动
- 检查 Vite 代理配置
- 查看浏览器控制台错误信息
