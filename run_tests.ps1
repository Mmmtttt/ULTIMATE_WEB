# 运行测试脚本
# 运行根目录下的测试用例

Write-Host "=== 开始运行测试 ===" -ForegroundColor Green

# 检查测试文件是否存在
if (-not (Test-Path "tests\test_api.py")) {
    Write-Host "错误: 找不到测试文件 tests\test_api.py" -ForegroundColor Red
    exit 1
}

# 检查后端服务是否运行
Write-Host "检查后端服务是否运行..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/health" -TimeoutSec 3
    if ($response.StatusCode -eq 200) {
        Write-Host "后端服务运行正常" -ForegroundColor Green
    } else {
        Write-Host "后端服务返回状态码: $($response.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "错误: 后端服务未运行，请先启动后端服务" -ForegroundColor Red
    exit 1
}

# 运行测试
Write-Host "运行测试用例..." -ForegroundColor Cyan
python -m pytest tests\test_api.py -v

Write-Host "=== 测试完成 ===" -ForegroundColor Green
