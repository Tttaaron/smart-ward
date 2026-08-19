-- ============================================================
-- 智慧病房云边协同系统 - 数据库初始化
-- 对齐方案书 §4.2 必须替换的领域对象
-- ============================================================

SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS smart_ward DEFAULT CHARSET utf8mb4;
USE smart_ward;

-- ============================================================
-- 1. 病区表 wards
-- ============================================================
CREATE TABLE IF NOT EXISTS wards (
    id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    ward_type VARCHAR(20) DEFAULT 'general' COMMENT 'general/rehab/geriatric/maternity/pediatric',
    location VARCHAR(100),
    status VARCHAR(20) DEFAULT 'online',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 2. 床位表 beds（FK -> wards）
-- ============================================================
CREATE TABLE IF NOT EXISTS beds (
    id VARCHAR(10) PRIMARY KEY,
    ward_id VARCHAR(10) NOT NULL,
    name VARCHAR(50) NOT NULL,
    patient_alias VARCHAR(50) COMMENT '演示用匿名别名，不存真实姓名',
    status VARCHAR(20) DEFAULT 'idle' COMMENT 'idle/occupied/alert/maintenance',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_ward (ward_id),
    FOREIGN KEY (ward_id) REFERENCES wards(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 3. 边缘节点表 edge_nodes（FK -> wards）
-- ============================================================
CREATE TABLE IF NOT EXISTS edge_nodes (
    id VARCHAR(30) PRIMARY KEY,
    ward_id VARCHAR(10) NOT NULL,
    bed_id VARCHAR(10),
    status VARCHAR(20) DEFAULT 'offline' COMMENT 'online/degraded/offline',
    model_version VARCHAR(50),
    last_heartbeat DATETIME,
    buffered_events INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_ward (ward_id),
    INDEX idx_bed (bed_id),
    FOREIGN KEY (ward_id) REFERENCES wards(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 4. 观测数据表 observations（多源观测，含 source/quality）
-- ============================================================
CREATE TABLE IF NOT EXISTS observations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ward_id VARCHAR(10) NOT NULL,
    node_id VARCHAR(30) NOT NULL,
    bed_id VARCHAR(10) NOT NULL,
    source_type VARCHAR(20) NOT NULL COMMENT 'camera/bed_sensor/environment',
    data JSON NOT NULL,
    quality JSON,
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_node_time (node_id, timestamp),
    INDEX idx_bed_time (bed_id, timestamp),
    INDEX idx_ward_type_time (ward_id, source_type, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 5. 安全事件表 safety_events（核心：跌倒/离床/呼叫等）
-- ============================================================
CREATE TABLE IF NOT EXISTS safety_events (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_id VARCHAR(64) NOT NULL UNIQUE,
    ward_id VARCHAR(10) NOT NULL,
    node_id VARCHAR(30) NOT NULL,
    bed_id VARCHAR(10) NOT NULL,
    event_type VARCHAR(30) NOT NULL,
    priority VARCHAR(5) NOT NULL COMMENT 'P1/P2/P3',
    state VARCHAR(20) NOT NULL DEFAULT 'new' COMMENT 'new/notified/acknowledged/resolved/false_positive/escalated',
    confidence FLOAT NOT NULL,
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    inference_ms INT DEFAULT 0,
    evidence_refs JSON,
    rule_hits JSON,
    details JSON,
    occurred_at DATETIME NOT NULL,
    detected_at DATETIME,
    acknowledged_at DATETIME,
    resolved_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ward_state (ward_id, state),
    INDEX idx_bed_time (bed_id, occurred_at),
    INDEX idx_priority_state (priority, state),
    INDEX idx_event_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 6. 告警任务表 alert_tasks（通知任务，与事件分开建模）
-- ============================================================
CREATE TABLE IF NOT EXISTS alert_tasks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_id VARCHAR(64) NOT NULL,
    ward_id VARCHAR(10) NOT NULL,
    bed_id VARCHAR(10) NOT NULL,
    priority VARCHAR(5) NOT NULL,
    channel VARCHAR(20) DEFAULT 'ws' COMMENT 'ws/sms/email',
    notified_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_event (event_id),
    INDEX idx_ward_priority (ward_id, priority),
    FOREIGN KEY (event_id) REFERENCES safety_events(event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 7. 事件处置表 event_dispositions（确认人/结果/误报标签）
-- ============================================================
CREATE TABLE IF NOT EXISTS event_dispositions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_id VARCHAR(64) NOT NULL,
    action VARCHAR(20) NOT NULL COMMENT 'acknowledge/resolve/false_positive/escalate',
    operator_id VARCHAR(50) NOT NULL,
    operator_name VARCHAR(50),
    operator_role VARCHAR(20),
    result VARCHAR(200),
    note TEXT,
    occurred_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_event (event_id),
    FOREIGN KEY (event_id) REFERENCES safety_events(event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 8. 模型版本表 model_versions
-- ============================================================
CREATE TABLE IF NOT EXISTS model_versions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    artifact_url VARCHAR(500) NOT NULL,
    checksum VARCHAR(128),
    runtime VARCHAR(20) DEFAULT 'onnx' COMMENT 'onnx/openvino/tensorrt/pytorch/gguf',
    target_device VARCHAR(10) DEFAULT 'cpu' COMMENT 'cpu/gpu/npu/auto',
    config JSON,
    status VARCHAR(20) DEFAULT 'draft' COMMENT 'draft/validating/released/deprecated/rolled_back',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_name_version (model_name, model_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 9. 模型部署表 model_deployments（灰度发布记录）
-- ============================================================
CREATE TABLE IF NOT EXISTS model_deployments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    node_id VARCHAR(30) NOT NULL,
    ward_id VARCHAR(10),
    action VARCHAR(20) NOT NULL COMMENT 'deploy/rollback',
    status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/success/failed',
    deployed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_node (node_id),
    INDEX idx_model (model_name, model_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 10. 审计日志表 audit_logs（事件写入/确认/下发全部留痕）
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    action VARCHAR(30) NOT NULL COMMENT 'event_create/event_ack/event_resolve/model_deploy/...',
    target_type VARCHAR(20),
    target_id VARCHAR(64),
    operator_id VARCHAR(50),
    detail JSON,
    occurred_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_target (target_type, target_id),
    INDEX idx_action_time (action, occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 11. 交接班摘要表 shift_summaries
-- ============================================================
CREATE TABLE IF NOT EXISTS shift_summaries (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ward_id VARCHAR(10) NOT NULL,
    shift_date DATE NOT NULL,
    shift_period VARCHAR(10) NOT NULL COMMENT 'day/evening/night',
    operator_id VARCHAR(50),
    summary_text TEXT NOT NULL,
    event_count INT DEFAULT 0,
    p1_count INT DEFAULT 0,
    p2_count INT DEFAULT 0,
    resolved_count INT DEFAULT 0,
    false_positive_count INT DEFAULT 0,
    avg_response_seconds INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ward_date (ward_id, shift_date),
    UNIQUE KEY uk_ward_date_period (ward_id, shift_date, shift_period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 初始演示数据：1 个病区、3 张床位、3 个边缘节点
-- ============================================================
INSERT INTO wards (id, name, ward_type, location, status) VALUES
    ('W-01', '普通病房 W-01', 'general', '三楼东侧', 'online')
ON DUPLICATE KEY UPDATE name=VALUES(name);

INSERT INTO beds (id, ward_id, name, patient_alias, status) VALUES
    ('B01', 'W-01', '1床', '张阿姨', 'idle'),
    ('B02', 'W-01', '2床', '李伯伯', 'idle'),
    ('B03', 'W-01', '3床', '王奶奶', 'idle')
ON DUPLICATE KEY UPDATE name=VALUES(name), patient_alias=VALUES(patient_alias);

INSERT INTO edge_nodes (id, ward_id, bed_id, status) VALUES
    ('EDGE-W01-B01', 'W-01', 'B01', 'offline'),
    ('EDGE-W01-B02', 'W-01', 'B02', 'offline'),
    ('EDGE-W01-B03', 'W-01', 'B03', 'offline')
ON DUPLICATE KEY UPDATE ward_id=VALUES(ward_id);
