# 部署与使用指南

本文档提供详细的部署说明、配置指南和运维操作。

## 快速开始 (Docker Compose)

### 前置条件
- Docker >= 20.10
- Docker Compose >= 2.0
- 4GB+ RAM (推荐 8GB)
- 20GB+ 磁盘空间

### 步骤 1: 准备环境

```bash
# 克隆项目
git clone https://github.com/wagjixiang/personal-agent.git
cd personal-agent

# 复制环境变量模板
cp .env.example .env
```

### 步骤 2: 配置环境变量

编辑 `.env` 文件，设置必要参数：

```bash
# LLM 配置（必需）
OPENAI_API_KEY=sk-your-api-key-here
GPT_MODEL=qwen-plus
MODEL_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 数据库配置（必需）
DB_NAME=school
DB_USER=root
DB_PASS=your-secure-password

# 可选配置
REDIS_ENABLED=True
ENABLE_METRICS=True
ENABLE_TRACING=False
GRAFANA_PASSWORD=admin
```

### 步骤 3: 启动服务

```bash
# 构建镜像并启动所有服务
docker-compose up -d

# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f app
```

### 步骤 4: 验证部署

```bash
# 检查应用健康状态
curl http://localhost:5000/health

# 查看数据库连接
docker-compose exec mysql mysql -u root -p$DB_PASS -e "SELECT 1"

# 检查 Redis
docker-compose exec redis redis-cli ping

# 访问监控面板
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
# Jaeger: http://localhost:16686
```

---

## 本地开发环境

### 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Unix/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 启动开发服务

```bash
# 方式 1: 直接运行 Flask
python app.py

# 方式 2: 使用 Flask CLI
flask run

# 方式 3: 带调试的运行
FLASK_ENV=development FLASK_DEBUG=1 python app.py
```

### 本地数据库设置

如果不使用 Docker，需要手动设置 MySQL：

```bash
# 连接到 MySQL
mysql -u root -p

# 创建数据库
CREATE DATABASE school CHARACTER SET utf8mb4;
CREATE USER 'agent'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON school.* TO 'agent'@'localhost';
FLUSH PRIVILEGES;
```

然后执行索引创建脚本：

```bash
python sql/index_optimizer.py > create_indexes.sql
mysql -u agent -p school < create_indexes.sql
```

---

## 生产部署

### 场景 1: 单机部署（小规模）

```bash
# 使用 Gunicorn 作为 WSGI 服务器
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# 使用 Supervisor 管理进程
# /etc/supervisor/conf.d/personal-agent.conf
[program:personal-agent]
command=/path/to/venv/bin/gunicorn -w 4 app:app
directory=/path/to/app
user=www-data
autostart=true
autorestart=true
```

### 场景 2: 容器编排（中等规模）

```bash
# 使用 Kubernetes
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# 查看部署状态
kubectl get pods -l app=personal-agent
kubectl logs -f deployment/personal-agent
```

### 场景 3: 云平台部署

#### AWS ECS
```bash
# 登录 ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin xxx.dkr.ecr.us-east-1.amazonaws.com

# 构建镜像并推送
docker build -t personal-agent:latest .
docker tag personal-agent:latest xxx.dkr.ecr.us-east-1.amazonaws.com/personal-agent:latest
docker push xxx.dkr.ecr.us-east-1.amazonaws.com/personal-agent:latest

# 使用 ECS 创建任务定义和服务
```

#### 阿里云容器服务
```bash
# 登录容器镜像服务
docker login --username=your-username registry.cn-beijing.aliyuncs.com

# 构建并推送镜像
docker build -t personal-agent:latest .
docker tag personal-agent:latest registry.cn-beijing.aliyuncs.com/your-ns/personal-agent:latest
docker push registry.cn-beijing.aliyuncs.com/your-ns/personal-agent:latest
```

---

## 配置指南

### 数据库优化

```bash
# 创建索引
mysql> source sql/index_optimizer.py;

# 启用慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;
SHOW VARIABLES LIKE 'slow_query_log%';

# 分析表统计
ANALYZE TABLE student, teacher, course, enrollment;
```

### Redis 优化

```bash
# 检查内存使用
redis-cli INFO memory

# 设置内存上限
redis-cli CONFIG SET maxmemory 2gb

# 设置驱逐策略（LRU）
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### 缓存预热

```python
# 在应用启动时预热常用查询
from cache import create_cache_backend, CacheManager
from query_engine import HybridQueryEngine

cache = create_cache_backend("redis")
cache_mgr = CacheManager(cache)
engine = HybridQueryEngine(cache_mgr, validator)

# 预热热点查询
hot_queries = [
    "学院有多少个学生？",
    "排名前三的学院是哪些？",
]

for query in hot_queries:
    engine.query(query)
```

---

## 监控与告警

### Prometheus 告警规则

```yaml
# prometheus-rules.yml
groups:
  - name: personal-agent
    interval: 30s
    rules:
      # 查询错误率告警
      - alert: HighQueryErrorRate
        expr: rate(queries_total{status="error"}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "高错误率: {{ $value | humanizePercentage }}"
      
      # 缓存命中率低告警
      - alert: LowCacheHitRate
        expr: cache_hit_rate < 0.5
        for: 10m
        annotations:
          summary: "缓存命中率过低: {{ $value }}"
      
      # 数据库连接池满告警
      - alert: DBConnectionPoolExhausted
        expr: active_db_connections > 25
        for: 2m
        annotations:
          summary: "DB连接接近上限"
      
      # Redis 内存使用告警
      - alert: RedisHighMemory
        expr: redis_used_memory_bytes / redis_max_memory_bytes > 0.8
        for: 5m
        annotations:
          summary: "Redis 内存使用过高: {{ $value | humanizePercentage }}"
```

### Grafana 仪表板

**常用面板：**
1. 系统概览：QPS、错误率、平均延迟、缓存命中率
2. 数据库性能：连接数、查询耗时、慢查询
3. 缓存统计：命中/未命中、内存使用、驱逐数
4. 应用健康：CPU、内存、磁盘、网络

**导入面板：**
```bash
# 下载官方 Dashboard
# MySQL: https://grafana.com/grafana/dashboards/7362
# Redis: https://grafana.com/grafana/dashboards/11114
```

---

## 性能调优

### 数据库优化

```sql
-- 1. 定期运行 ANALYZE（重新计算统计）
ANALYZE TABLE student;
ANALYZE TABLE teacher;
ANALYZE TABLE course;

-- 2. 优化表结构
OPTIMIZE TABLE student;

-- 3. 检查表完整性
CHECK TABLE student;
REPAIR TABLE student;

-- 4. 查看索引统计
SELECT * FROM INFORMATION_SCHEMA.STATISTICS 
WHERE TABLE_NAME = 'student';
```

### 查询优化

```python
# 使用 EXPLAIN 分析查询
results = DBExecutor.execute(
    "SELECT * FROM student WHERE college_id = 1",
    explain=True
)

# 查看执行计划
# 关键字段说明：
# - type: ALL(全表扫描) < INDEX < RANGE < REF < EQ_REF < CONST
# - key: 使用的索引
# - rows: 扫描的行数（越少越好）
# - Extra: 额外信息
```

### 内存优化

```python
# 定期清理过期缓存
cache_backend.clear()

# 监控内存使用
import psutil
process = psutil.Process()
print(f"内存: {process.memory_info().rss / 1024 / 1024:.2f} MB")
```

---

## 故障恢复

### 数据库故障

```bash
# 1. 检查 MySQL 状态
docker-compose ps mysql

# 2. 查看错误日志
docker-compose logs mysql

# 3. 重启 MySQL
docker-compose restart mysql

# 4. 验证数据完整性
docker-compose exec mysql mysql -u root -p$DB_PASS -e "SHOW PROCESSLIST;"

# 5. 恢复备份（如有备份）
docker cp backup.sql personal-agent-mysql:/backup.sql
docker-compose exec mysql mysql -u root -p$DB_PASS < /backup.sql
```

### Redis 故障

```bash
# 1. 检查 Redis 状态
docker-compose exec redis redis-cli ping

# 2. 查看 Redis 日志
docker-compose logs redis

# 3. 重启 Redis
docker-compose restart redis

# 4. 检查数据
docker-compose exec redis redis-cli DBSIZE
docker-compose exec redis redis-cli FLUSHDB  # 清空（谨慎操作）
```

### 应用故障

```bash
# 1. 查看应用日志
docker-compose logs app

# 2. 检查应用健康状态
curl -v http://localhost:5000/health

# 3. 重启应用
docker-compose restart app

# 4. 完整重启（核选项）
docker-compose down
docker-compose up -d
```

---

## 备份与恢复

### 数据库备份

```bash
# 完整备份
docker-compose exec mysql mysqldump -u root -p$DB_PASS school > backup-$(date +%Y%m%d).sql

# 增量备份（使用二进制日志）
docker-compose exec mysql mysql -u root -p$DB_PASS -e "SHOW BINARY LOGS;"
```

### 恢复数据库

```bash
# 从备份恢复
docker-compose exec -T mysql mysql -u root -p$DB_PASS school < backup-20260527.sql

# 验证恢复
docker-compose exec mysql mysql -u root -p$DB_PASS -e "SELECT COUNT(*) FROM student;"
```

---

## 升级与维护

### 应用升级

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 更新依赖
pip install -r requirements.txt

# 3. 运行迁移（如有）
# flask db upgrade

# 4. 重启应用
docker-compose restart app
```

### 依赖更新

```bash
# 检查过时的包
pip list --outdated

# 更新所有包到最新版本
pip install --upgrade -r requirements.txt

# 生成新的 requirements.txt
pip freeze > requirements.txt
```

---

## 常见问题

### Q: 如何扩展应用容量？

**A:** 使用容器编排工具：
```bash
# 使用 Docker Compose 扩展服务（不推荐）
docker-compose up --scale app=3

# 推荐使用 Kubernetes
kubectl scale deployment/personal-agent --replicas=3
```

### Q: 如何实现 0 停机部署？

**A:** 使用滚动更新：
```yaml
# kubernetes
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

### Q: 如何处理数据库迁移？

**A:** 离线迁移流程：
```bash
# 1. 停止写入操作
docker-compose stop app

# 2. 备份旧数据库
mysqldump -u root -p school > backup.sql

# 3. 迁移数据到新数据库
mysql -u root -p new_school < backup.sql

# 4. 重新指向新数据库
# 修改 .env 中的 DB_NAME

# 5. 重启应用
docker-compose up -d app
```

---

**最后更新**: 2026-05-27  
**维护者**: @wagjixiang
