# Python Gradle构建监控系统

一个完整的基于Python的Gradle构建过程监控和管理系统，提供异步执行、实时日志流、性能优化、APK分析等功能。

## 🚀 功能特性

### 核心功能
- **异步构建执行**: 基于asyncio的非阻塞Gradle构建执行
- **实时日志流**: WebSocket实时传输构建日志和进度
- **并发构建管理**: 支持多项目并发构建，智能资源调度
- **APK文件分析**: 自动检测和分析构建输出的APK文件
- **性能监控**: 系统资源使用监控和自动优化
- **超时管理**: 智能超时检测和任务取消机制

### 高级功能
- **项目上传管理**: 支持ZIP格式Android项目上传和解压
- **构建质量分析**: APK质量评分和优化建议
- **资源限制**: 内存、CPU、磁盘空间监控和限制
- **缓存系统**: 智能构建缓存管理
- **REST API**: 完整的FastAPI REST接口
- **WebSocket通信**: 实时双向通信支持

## 📦 安装和设置

### 环境要求
- Python 3.8+
- Java 8+ (用于Gradle)
- Android SDK (可选，用于高级分析)

### 安装依赖
```bash
pip install -r requirements.txt
```

### 系统配置
1. 确保Java环境正确配置
2. 设置ANDROID_HOME环境变量（可选）
3. 确保有足够的磁盘空间用于构建缓存

## 🎯 快速开始

### 1. 基本使用

```python
from gradle_monitor import GradleBuildManager

async def main():
    # 创建构建管理器
    build_manager = GradleBuildManager(max_concurrent_builds=2)
    await build_manager.start()

    # 提交构建任务
    build_id = await build_manager.submit_build(
        "/path/to/android/project",
        ["assembleDebug"],
        timeout=600
    )

    # 监控构建状态
    while True:
        result = await build_manager.get_build_status(build_id)
        print(f"构建状态: {result.status.value}")

        if result.status.value in ['success', 'failed', 'cancelled']:
            break

        await asyncio.sleep(2)

    await build_manager.stop()
```

### 2. FastAPI集成

```python
from fastapi_gradle_integration import app
import uvicorn

# 启动API服务器
uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 3. 性能优化

```python
from performance_optimization_guide import ConfigurationOptimizer, PerformanceLevel

# 系统优化
config_optimizer = ConfigurationOptimizer()
config_optimizer.optimize_for_system()
config_optimizer.set_performance_level(PerformanceLevel.HIGH_PERFORMANCE)
```

### 4. APK分析

```python
from apk_builder_analyzer import BuildResultAnalyzer

analyzer = BuildResultAnalyzer()
analysis = await analyzer.analyze_build_result(
    build_id="build_001",
    apk_path="/path/to/app.apk",
    build_logs=[],
    build_duration=120.0
)

print(f"质量分数: {analysis.quality_score}")
print(f"警告: {analysis.warnings}")
print(f"建议: {analysis.recommendations}")
```

## 🔧 配置选项

### 系统配置 (config.yaml)
```yaml
max_concurrent_builds: 3
max_memory_per_build: 2048  # MB
max_build_time: 1800        # 秒
enable_build_cache: true
cache_size_limit: 1024      # MB
monitoring_interval: 5.0    # 秒
```

### Gradle优化
```properties
# gradle.properties
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.jvmargs=-Xmx2g -XX:+UseG1GC
org.gradle.caching=true
```

## 📊 API接口

### REST API端点

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/projects/upload` | 上传Android项目ZIP文件 |
| GET | `/api/projects` | 列出所有项目 |
| POST | `/api/builds` | 提交构建任务 |
| GET | `/api/builds/{build_id}` | 获取构建状态 |
| POST | `/api/builds/{build_id}/cancel` | 取消构建 |
| GET | `/api/builds/{build_id}/download` | 下载APK文件 |
| GET | `/api/stats` | 系统统计信息 |

### WebSocket端点

- `ws://localhost:8000/ws/{client_id}` - 实时通信

### WebSocket消息格式

```json
{
  "type": "subscribe",
  "build_id": "build_001"
}
```

```json
{
  "type": "log",
  "build_id": "build_001",
  "data": {
    "content": "Task :app:compileDebugKotlin",
    "timestamp": "2024-01-01T00:00:00"
  }
}
```

## 🔍 监控和分析

### 性能指标
- CPU使用率
- 内存使用率
- 磁盘I/O
- 网络I/O
- 构建队列状态
- 缓存命中率

### APK分析项目
- 包名和版本信息
- 权限列表
- 组件分析（Activity、Service等）
- 文件大小评估
- 安全性检查
- 性能建议

### 质量评分算法
- 构建成功率
- APK文件大小 (0-30分)
- 权限数量 (0-20分)
- SDK版本兼容性 (0-20分)
- 安全配置 (0-30分)

## 🛠️ 高级功能

### 1. 长时间任务管理

```python
from task_timeout_manager import LongRunningTaskManager

task_manager = LongRunningTaskManager(
    resource_limits=ResourceLimits(max_memory_mb=2048),
    timeout_config=TimeoutConfig(default_timeout=600)
)

await task_manager.start()

result = await task_manager.execute_task(
    "task_001",
    long_running_coroutine(),
    timeout=600,
    progress_callback=lambda p: print(f"进度: {p}%")
)
```

### 2. 智能缓存

```python
from performance_optimization_guide import CacheManager

cache = CacheManager()

# 设置缓存
cache.set("build_result", data, ttl=3600)

# 获取缓存
cached_data = cache.get("build_result")
```

### 3. 资源监控

```python
from task_timeout_manager import ResourceMonitor

monitor = ResourceMonitor(ResourceLimits())
await monitor.start_monitoring()

# 添加违规处理回调
def handle_violation(data):
    violations = data['violations']
    for violation in violations:
        print(f"资源违规: {violation}")

monitor.add_callback(handle_violation)
```

## 📈 性能优化建议

### 系统级优化
1. **CPU优化**: 设置合理的并发构建数量（CPU核心数的一半）
2. **内存优化**: 根据系统内存调整每个构建的内存限制
3. **磁盘优化**: 定期清理构建缓存，使用SSD存储
4. **网络优化**: 配置代理和镜像以加速依赖下载

### Gradle优化
1. **启用守护进程**: `org.gradle.daemon=true`
2. **并行构建**: `org.gradle.parallel=true`
3. **构建缓存**: `org.gradle.caching=true`
4. **JVM调优**: 使用G1GC，调整堆大小

### 应用级优化
1. **异步处理**: 使用asyncio避免阻塞
2. **连接池**: 复用HTTP连接和数据库连接
3. **缓存策略**: 智能缓存构建结果和中间文件
4. **资源限制**: 设置合理的内存和CPU限制

## 🚨 故障排除

### 常见问题

1. **构建失败**
   - 检查Java环境配置
   - 验证Android SDK路径
   - 查看详细错误日志

2. **内存不足**
   - 减少并发构建数量
   - 调整JVM堆大小
   - 启用更激进的垃圾回收

3. **构建超时**
   - 增加超时时间
   - 检查网络连接
   - 优化构建脚本

4. **APK分析失败**
   - 安装Android Build Tools
   - 检查AAPT工具路径
   - 验证APK文件完整性

### 日志级别
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 调试模式
```python
# 启用详细日志
config_optimizer.config.enable_monitoring = True
config_optimizer.config.monitoring_interval = 1.0
```

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_gradle_monitor.py

# 生成覆盖率报告
pytest --cov=gradle_monitor --cov-report=html
```

## 📚 开发指南

### 项目结构
```
gradle_monitoring_system/
├── gradle_monitor.py              # 核心构建监控
├── fastapi_gradle_integration.py  # FastAPI集成
├── task_timeout_manager.py        # 超时管理
├── apk_builder_analyzer.py        # APK分析
├── performance_optimization_guide.py # 性能优化
├── complete_example.py           # 完整示例
├── requirements.txt              # 依赖包
└── README.md                     # 文档
```

### 扩展开发
1. **自定义日志解析器**: 继承`GradleLogParser`类
2. **添加新的分析指标**: 扩展`APKAnalyzer`类
3. **自定义优化策略**: 实现`PerformanceOptimizer`的子类
4. **集成新的构建工具**: 创建新的执行器类

## 📄 许可证

本项目采用MIT许可证。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 📞 支持

如有问题，请通过以下方式联系：
- 创建GitHub Issue
- 发送邮件至开发团队
- 查看文档和示例代码

---

**注意**: 这是一个演示项目，实际使用时请根据具体需求进行调整和优化。