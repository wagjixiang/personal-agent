# 快速参考卡 (Cheat Sheet)

## 🚀 30 秒启动

```bash
cp .env.example .env
# 编辑 .env - 设置 OPENAI_API_KEY
docker-compose up -d
curl http://localhost:5000/health
```

## 📂 文件地图

| 文件 | 用途 | 修改频率 |
|-----|-----|--------|
| cache.py | Redis 缓存 | 低 |
| query_engine.py | 混合查询 | 低 |
| settings.py | 配置管理 | 中 |
| conversation_manager.py | 会话管理 | 低 |
| sql/executor.py | 数据库连接 | 低 |
| sql/index_optimizer.py | 索引管理 | 低 |
| .env.example | 配置模板 | 中 |
| Dockerfile | 容器镜像 | 低 |
| docker-compose.yml | 服务编排 | 低 |

## 🎯 常见任务

### 添加新的缓存

```python
from cache import CacheManager, create_cache_backend

cache_backend = create_cache_backend("redis")
cache_mgr = CacheManager(cache_backend)

# 缓存查询结果
cache_mgr.cache_query_result(sql, result, params, ttl=3600)

# 获取缓存
cached = cache_mgr.get_cached_query_result(sql, params)
```

### 分析查询性能

```sql
-- 查看执行计划
EXPLAIN SELECT * FROM student WHERE college_id = 1;

-- 启用慢查询
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;

-- 查看慢查询
SHOW VARIABLES LIKE 'slow_query_log%';
```

### 创建索引

```python
from sql.index_optimizer import IndexAnalyzer

analyzer = IndexAnalyzer()
sql_script = analyzer.get_create_index_sql()
# 执行 SQL 脚本创建索引
```

### 监控缓存

```bash
# Redis 统计
redis-cli INFO stats

# 缓存命中率
curl http://localhost:5000/api/metrics | grep cache_hit_rate

# 慢查询
curl http://localhost:5000/api/slow-queries
```

## 📊 监控面板

| 名称 | URL | 用途 |
|-----|-----|------|
| Grafana | http://localhost:3000 | 可视化指标 |
| Prometheus | http://localhost:9090 | 告警管理 |
| Jaeger | http://localhost:16686 | 追踪链路 |

## 🔧 故障排查

### 查询慢？
1. `curl http://localhost:5000/api/slow-queries` - 查看慢查询
2. `EXPLAIN SELECT ...` - 分析执行计划
3. 检查缓存命中率 - `curl http://localhost:5000/api/cache-stats`

### 内存高？
```bash
# 检查 Redis
redis-cli INFO memory

# 检查进程
ps aux | grep python

# 检查连接数
mysql -e "SHOW PROCESSLIST;" | wc -l
```

### 应用崩溃？
```bash
docker-compose logs --tail=100 app
docker-compose restart app
```

## 📝 配置速查

### 必需配置
```env
OPENAI_API_KEY=sk-...      # LLM API Key
DB_NAME=school             # 数据库名
DB_PASS=password           # 数据库密码
```

### 性能配置
```env
DB_POOL_SIZE=10            # 连接池大小
CACHE_TTL_DEFAULT=3600     # 默认缓存时间
QUERY_CACHE_TTL=3600       # 查询缓存
PLAN_CACHE_TTL=86400       # 计划缓存
```

### 安全配置
```env
ENABLE_AUTH=False          # 开启认证
RATE_LIMIT_ENABLED=False   # 速率限制
CORS_ENABLED=True          # 跨域
```

## 🧪 测试命令

```bash
# 健康检查
curl http://localhost:5000/health

# 聊天接口
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"学院有多少个学生?", "session_id":"test"}'

# 缓存统计
curl http://localhost:5000/api/cache-stats

# 慢查询
curl http://localhost:5000/api/slow-queries

# 连接池状态
curl http://localhost:5000/api/pool-stats
```

## 📦 部署命令

```bash
# 本地开发
python app.py

# Docker 启动
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down

# 完整重启
docker-compose down && docker-compose up -d

# 只重启应用
docker-compose restart app
```

## 🔄 数据库操作

```bash
# 备份数据库
docker-compose exec mysql mysqldump -u root -p$DB_PASS school > backup.sql

# 恢复数据库
docker-compose exec -T mysql mysql -u root -p$DB_PASS school < backup.sql

# 创建索引
mysql -u root -p school < sql/index_optimizer.py

# 查看表结构
mysql -u root -p -e "DESCRIBE school.student;"

# 查看索引
mysql -u root -p -e "SHOW INDEXES FROM school.student;"
```

## 🎓 性能调优

### 快速诊断

```bash
# 1. 检查缓存命中率
redis-cli INFO stats | grep hit

# 2. 查看数据库连接
mysql -e "SHOW PROCESSLIST;"

# 3. 分析慢查询
tail -f /var/log/mysql/slow.log

# 4. 检查 Redis 内存
redis-cli INFO memory
```

### 常见优化

| 问题 | 解决方案 |
|-----|--------|
| 查询慢 | 创建索引、启用缓存 |
| 内存高 | 清理缓存、调整 TTL |
| 连接满 | 增加 pool_size |
| 缓存低 | 分析查询模式、调整 TTL |

## 🌐 API 参考

### POST /chat
```json
{
  "message": "你的问题",
  "session_id": "可选-会话ID"
}
```

### GET /health
返回: `{"status":"ok","version":"2.0"}`

### GET /api/cache-stats
返回: 缓存统计信息

### GET /api/slow-queries
返回: 最近的慢查询列表

### GET /api/pool-stats
返回: 连接池统计

## 📚 文档引索

- **快速开始**: README.md
- **架构分析**: ARCHITECTURE_ANALYSIS.md
- **详细实现**: ENTERPRISE_OPTIMIZATION.md
- **部署指南**: DEPLOYMENT_GUIDE.md
- **配置模板**: .env.example
- **本快速卡**: 此文件

## ⏱️ 常见时间

| 操作 | 耗时 |
|-----|------|
| 缓存命中查询 | <50ms |
| 数据库查询 | 50-200ms |
| 启动应用 | 5-10s |
| Docker 启动 | 15-30s |

## 💬 常见问题

**Q: 缓存在哪？**  
A: Redis, 默认 localhost:6379

**Q: 日志在哪？**  
A: Docker: `docker-compose logs`, 本地: `./logs/`

**Q: 如何增加连接数？**  
A: 修改 `.env` 中的 `DB_POOL_SIZE`

**Q: 如何禁用缓存？**  
A: 设置 `REDIS_ENABLED=False` 或使用内存缓存

**Q: 性能基准是多少？**  
A: 缓存命中 <50ms, 数据库查询 200-500ms, 吞吐量 1000 req/s

---

**版本**: 2.0  
**最后更新**: 2026-05-27
