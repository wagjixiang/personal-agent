"""
MySQL 索引优化模块

提供索引设计、创建、分析的完整工具集
"""

# ============================================================
# 索引设计文档（SQL脚本）
# ============================================================

MYSQL_INDEX_DESIGN = """
-- ============================================================
-- MySQL 表索引优化设计
-- ============================================================
-- 本文档定义了个人助手应用所有核心表的索引策略
-- 包括：主键、外键、复合索引、全文索引、唯一约束等
-- ============================================================

-- ============================================================
-- 1. 学院表 (college) 索引
-- ============================================================
ALTER TABLE college
    ADD PRIMARY KEY IF NOT EXISTS (college_id),
    ADD UNIQUE INDEX IF NOT EXISTS idx_college_name (name),
    ADD INDEX IF NOT EXISTS idx_college_rank (rank);

-- 示例数据结构
-- CREATE TABLE college (
--     college_id INT PRIMARY KEY AUTO_INCREMENT,
--     name VARCHAR(100) NOT NULL,
--     rank INT,
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- ============================================================
-- 2. 学生表 (student) 索引 - 高优先级
-- ============================================================
ALTER TABLE student
    ADD PRIMARY KEY IF NOT EXISTS (student_id),
    ADD FOREIGN KEY IF NOT EXISTS fk_student_college (college_id) REFERENCES college(college_id),
    ADD UNIQUE INDEX IF NOT EXISTS idx_student_number (number),
    ADD INDEX IF NOT EXISTS idx_student_college (college_id),
    ADD INDEX IF NOT EXISTS idx_student_college_id (college_id, student_id),
    ADD FULLTEXT INDEX IF NOT EXISTS ft_student_name (name);

-- 复合索引用途：
-- idx_student_college_id: 用于 SELECT * FROM student WHERE college_id = ? ORDER BY student_id

-- ============================================================
-- 3. 教师表 (teacher) 索引
-- ============================================================
ALTER TABLE teacher
    ADD PRIMARY KEY IF NOT EXISTS (teacher_id),
    ADD FOREIGN KEY IF NOT EXISTS fk_teacher_college (college_id) REFERENCES college(college_id),
    ADD UNIQUE INDEX IF NOT EXISTS idx_teacher_number (number),
    ADD INDEX IF NOT EXISTS idx_teacher_college (college_id),
    ADD INDEX IF NOT EXISTS idx_teacher_title (title),
    ADD FULLTEXT INDEX IF NOT EXISTS ft_teacher_name (name);

-- ============================================================
-- 4. 课程表 (course) 索引
-- ============================================================
ALTER TABLE course
    ADD PRIMARY KEY IF NOT EXISTS (course_id),
    ADD FOREIGN KEY IF NOT EXISTS fk_course_college (college_id) REFERENCES college(college_id),
    ADD INDEX IF NOT EXISTS idx_course_college (college_id),
    ADD INDEX IF NOT EXISTS idx_course_name (name),
    ADD INDEX IF NOT EXISTS idx_course_code (code);

-- ============================================================
-- 5. 选课关系表 (enrollment) 索引
-- ============================================================
ALTER TABLE enrollment
    ADD PRIMARY KEY IF NOT EXISTS (enrollment_id),
    ADD FOREIGN KEY IF NOT EXISTS fk_enrollment_student (student_id) REFERENCES student(student_id),
    ADD FOREIGN KEY IF NOT EXISTS fk_enrollment_course (course_id) REFERENCES course(course_id),
    ADD UNIQUE INDEX IF NOT EXISTS idx_enrollment_student_course (student_id, course_id),
    ADD INDEX IF NOT EXISTS idx_enrollment_course (course_id),
    ADD INDEX IF NOT EXISTS idx_enrollment_grade (grade);

-- 复合索引用途：
-- idx_enrollment_student_course: 防止重复选课 + 快速查询学生选课列表

-- ============================================================
-- 6. 教学关系表 (teaching) 索引
-- ============================================================
ALTER TABLE teaching
    ADD PRIMARY KEY IF NOT EXISTS (teaching_id),
    ADD FOREIGN KEY IF NOT EXISTS fk_teaching_teacher (teacher_id) REFERENCES teacher(teacher_id),
    ADD FOREIGN KEY IF NOT EXISTS fk_teaching_course (course_id) REFERENCES course(course_id),
    ADD UNIQUE INDEX IF NOT EXISTS idx_teaching_teacher_course (teacher_id, course_id),
    ADD INDEX IF NOT EXISTS idx_teaching_course (course_id);

-- ============================================================
-- 7. 会话表 (session) 索引 - 新增（会话存储）
-- ============================================================
CREATE TABLE IF NOT EXISTS session (
    session_id VARCHAR(36) PRIMARY KEY,
    user_id INT,
    conversation_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    KEY idx_session_user (user_id),
    KEY idx_session_expires (expires_at),
    KEY idx_session_updated (updated_at)
);

-- 注：使用 Redis 时可不需要此表，此处作为持久化后备

-- ============================================================
-- 8. 查询缓存表 (query_cache) 索引 - 新增
-- ============================================================
CREATE TABLE IF NOT EXISTS query_cache (
    cache_key VARCHAR(255) PRIMARY KEY,
    cache_value LONGTEXT,
    query_plan_hash VARCHAR(64),
    result_count INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    hit_count INT DEFAULT 0,
    KEY idx_query_cache_expires (expires_at),
    KEY idx_query_cache_hash (query_plan_hash)
);

-- 注：使用 Redis 时可不需要此表，此处作为持久化后备

-- ============================================================
-- 9. 审计日志表 (audit_log) 索引 - 新增
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(36),
    user_id INT,
    action VARCHAR(50),
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSON,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_audit_session (session_id),
    KEY idx_audit_user (user_id),
    KEY idx_audit_action (action),
    KEY idx_audit_created (created_at),
    KEY idx_audit_resource (resource_type, resource_id)
);

-- ============================================================
-- 10. 性能指标表 (performance_metrics) 索引 - 新增
-- ============================================================
CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    metric_name VARCHAR(100),
    metric_value DECIMAL(10, 2),
    labels JSON,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_metrics_name (metric_name),
    KEY idx_metrics_time (recorded_at),
    KEY idx_metrics_name_time (metric_name, recorded_at)
);

-- ============================================================
-- 索引使用指南
-- ============================================================

-- 查看表的所有索引
-- SHOW INDEXES FROM table_name;

-- 查看索引统计信息
-- SELECT * FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = 'school' AND TABLE_NAME = 'student';

-- 分析查询执行计划
-- EXPLAIN SELECT * FROM student WHERE college_id = 1;

-- 查看索引大小（MB）
-- SELECT TABLE_NAME, ROUND(STAT_VALUE * @@innodb_page_size / 1024 / 1024, 2) AS size_mb
-- FROM mysql.innodb_index_stats
-- WHERE DATABASE_NAME = 'school' AND STAT_NAME = 'size';

-- ============================================================
-- 性能建议
-- ============================================================

-- 1. 避免 SELECT *，明确指定需要的字段
--    BAD:  SELECT * FROM student WHERE college_id = 1;
--    GOOD: SELECT student_id, name, number FROM student WHERE college_id = 1;

-- 2. 使用覆盖索引减少回表
--    示例：index idx_student_college_id 包含了 college_id, student_id, name
--    可直接从索引获取这些列，无需访问主表

-- 3. 避免在 WHERE 条件中进行函数计算
--    BAD:  WHERE YEAR(created_at) = 2024;
--    GOOD: WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';

-- 4. 定期运行 ANALYZE TABLE 更新统计信息
--    ANALYZE TABLE college, student, teacher, course, enrollment, teaching;

-- 5. 监视 slow_query_log 发现未优化的查询
--    SET GLOBAL slow_query_log = 'ON';
--    SET GLOBAL long_query_time = 1;  -- 查询超过 1 秒记录

-- ============================================================
-- 批量索引创建脚本
-- ============================================================

-- 创建所有核心索引
-- ALTER TABLE college ADD PRIMARY KEY (college_id), ADD UNIQUE INDEX idx_college_name (name);
-- ALTER TABLE student ADD PRIMARY KEY (student_id), ADD UNIQUE INDEX idx_student_number (number), ADD INDEX idx_student_college (college_id);
-- ALTER TABLE teacher ADD PRIMARY KEY (teacher_id), ADD UNIQUE INDEX idx_teacher_number (number), ADD INDEX idx_teacher_college (college_id);
-- ALTER TABLE course ADD PRIMARY KEY (course_id), ADD INDEX idx_course_college (college_id), ADD INDEX idx_course_code (code);
-- ALTER TABLE enrollment ADD PRIMARY KEY (enrollment_id), ADD UNIQUE INDEX idx_enrollment_student_course (student_id, course_id);
-- ALTER TABLE teaching ADD PRIMARY KEY (teaching_id), ADD UNIQUE INDEX idx_teaching_teacher_course (teacher_id, course_id);
"""

# ============================================================
# Python 工具类
# ============================================================

class IndexAnalyzer:
    """数据库索引分析工具"""
    
    @staticmethod
    def get_create_index_sql():
        """返回索引创建 SQL 脚本"""
        return MYSQL_INDEX_DESIGN
    
    @staticmethod
    def get_index_statistics_query():
        """查询索引统计信息"""
        return """
        SELECT 
            TABLE_NAME,
            INDEX_NAME,
            COLUMN_NAME,
            SEQ_IN_INDEX,
            CARDINALITY,
            STAT_VALUE
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
        """
    
    @staticmethod
    def get_slow_query_detection():
        """启用慢查询日志"""
        return """
        SET GLOBAL slow_query_log = 'ON';
        SET GLOBAL long_query_time = 1;
        SHOW VARIABLES LIKE 'slow_query_log%';
        """
    
    @staticmethod
    def get_query_execution_plan(query: str):
        """生成查询执行计划分析"""
        return f"EXPLAIN {query};"
    
    @staticmethod
    def get_index_size_report():
        """获取索引大小报告"""
        return """
        SELECT 
            TABLE_NAME,
            INDEX_NAME,
            ROUND(STAT_VALUE * @@innodb_page_size / 1024 / 1024, 2) AS size_mb,
            STAT_VALUE
        FROM mysql.innodb_index_stats
        WHERE DATABASE_NAME = DATABASE() AND STAT_NAME = 'size'
        ORDER BY size_mb DESC;
        """
    
    @staticmethod
    def get_index_usage_report():
        """查询索引使用频率"""
        return """
        SELECT 
            OBJECT_SCHEMA,
            OBJECT_NAME,
            INDEX_NAME,
            COUNT_READ,
            COUNT_WRITE,
            COUNT_DELETE,
            COUNT_UPDATE
        FROM performance_schema.table_io_waits_summary_by_index_usage
        WHERE OBJECT_SCHEMA != 'mysql'
        ORDER BY COUNT_READ DESC, COUNT_WRITE DESC;
        """


if __name__ == "__main__":
    analyzer = IndexAnalyzer()
    print("=== MySQL 索引创建脚本 ===\n")
    print(analyzer.get_create_index_sql())
    print("\n=== 索引统计查询 ===\n")
    print(analyzer.get_index_statistics_query())
    print("\n=== 索引大小报告 ===\n")
    print(analyzer.get_index_size_report())
