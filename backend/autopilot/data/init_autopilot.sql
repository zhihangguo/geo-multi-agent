-- ============================================================
-- 自动驾驶评估系统 MySQL 数据库初始化脚本
-- 数据库: autopilot_eval
-- 包含: 7张核心表 + 真实样本数据
-- ============================================================

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS autopilot_eval
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE autopilot_eval;

-- ============================================================
-- 1. 车辆信息表
-- ============================================================
DROP TABLE IF EXISTS ad_vehicles;
CREATE TABLE ad_vehicles (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id      VARCHAR(50)  NOT NULL UNIQUE COMMENT '车辆唯一编号',
    model_name      VARCHAR(100) NOT NULL COMMENT '车型名称',
    sensor_config   JSON         COMMENT '传感器配置 JSON',
    software_ver    VARCHAR(50)  COMMENT '软件版本',
    hardware_ver    VARCHAR(50)  COMMENT '硬件版本',
    status          ENUM('active','maintenance','retired') DEFAULT 'active',
    tenant_id       VARCHAR(50)  NOT NULL DEFAULT 'default' COMMENT '租户隔离键',
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tenant   (tenant_id),
    INDEX idx_vehicle  (vehicle_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动驾驶车辆信息';

-- ============================================================
-- 2. 测试运行记录表
-- ============================================================
DROP TABLE IF EXISTS ad_test_runs;
CREATE TABLE ad_test_runs (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    run_id              VARCHAR(50)  NOT NULL UNIQUE,
    vehicle_id          VARCHAR(50)  NOT NULL,
    scenario_type       ENUM('highway','urban','parking','intersection','ramp','tunnel') NOT NULL,
    start_time          DATETIME     NOT NULL,
    end_time            DATETIME,
    total_distance_km   FLOAT        COMMENT '总里程(km)',
    avg_speed_kmh       FLOAT        COMMENT '平均速度(km/h)',
    max_speed_kmh       FLOAT        COMMENT '最高速度(km/h)',
    weather             ENUM('sunny','cloudy','rainy','foggy','snowy','night') DEFAULT 'sunny',
    road_condition      ENUM('dry','wet','icy','construction') DEFAULT 'dry',
    location            VARCHAR(200) COMMENT '测试地点',
    test_engineer       VARCHAR(100) COMMENT '测试工程师',
    status              ENUM('completed','aborted','in_progress') DEFAULT 'completed',
    tenant_id           VARCHAR(50)  NOT NULL DEFAULT 'default',
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tenant    (tenant_id),
    INDEX idx_run       (run_id),
    INDEX idx_vehicle   (vehicle_id),
    INDEX idx_scenario  (scenario_type),
    INDEX idx_time      (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试运行记录';

-- ============================================================
-- 3. 感知评估结果表
-- ============================================================
DROP TABLE IF EXISTS ad_perception_results;
CREATE TABLE ad_perception_results (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    run_id              VARCHAR(50)  NOT NULL,
    frame_id            INT          NOT NULL,
    timestamp_ms        BIGINT       NOT NULL,
    object_type         ENUM('car','pedestrian','cyclist','truck','motorcycle','traffic_sign','traffic_light') NOT NULL,
    true_positive       INT          DEFAULT 0,
    false_positive      INT          DEFAULT 0,
    false_negative      INT          DEFAULT 0,
    precision_score     FLOAT        COMMENT '精确率 0-1',
    recall_score        FLOAT        COMMENT '召回率 0-1',
    f1_score            FLOAT        COMMENT 'F1分数 0-1',
    avg_iou             FLOAT        COMMENT '平均IoU 0-1',
    avg_confidence      FLOAT        COMMENT '平均置信度 0-1',
    detection_latency_ms FLOAT       COMMENT '检测延迟(ms)',
    tenant_id           VARCHAR(50)  NOT NULL DEFAULT 'default',
    INDEX idx_tenant    (tenant_id),
    INDEX idx_run       (run_id),
    INDEX idx_obj       (object_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='感知评估结果';

-- ============================================================
-- 4. 安全事件表
-- ============================================================
DROP TABLE IF EXISTS ad_safety_events;
CREATE TABLE ad_safety_events (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    run_id              VARCHAR(50)  NOT NULL,
    event_id            VARCHAR(50)  NOT NULL UNIQUE,
    event_time          DATETIME     NOT NULL,
    event_type          ENUM('hard_brake','near_miss','human_intervention','lane_departure',
                             'speed_violation','traffic_light_violation','obstacle_avoidance') NOT NULL,
    severity            ENUM('low','medium','high','critical') NOT NULL,
    description         TEXT,
    human_intervention  BOOLEAN      DEFAULT FALSE,
    ego_speed_kmh       FLOAT        COMMENT '事件发生时车速(km/h)',
    ttc_seconds         FLOAT        COMMENT '碰撞时间TTC(秒)',
    resolved            BOOLEAN      DEFAULT TRUE,
    tenant_id           VARCHAR(50)  NOT NULL DEFAULT 'default',
    INDEX idx_tenant    (tenant_id),
    INDEX idx_run       (run_id),
    INDEX idx_severity  (severity),
    INDEX idx_type      (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='安全事件记录';

-- ============================================================
-- 5. 规划指标表
-- ============================================================
DROP TABLE IF EXISTS ad_planning_metrics;
CREATE TABLE ad_planning_metrics (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    run_id                  VARCHAR(50)  NOT NULL,
    timestamp_ms            BIGINT       NOT NULL,
    comfort_score           FLOAT        COMMENT '舒适度评分 0-100',
    efficiency_score        FLOAT        COMMENT '效率评分 0-100',
    safety_score            FLOAT        COMMENT '安全评分 0-100',
    path_deviation_m        FLOAT        COMMENT '路径偏差(m)',
    speed_smoothness        FLOAT        COMMENT '速度平滑度 0-1',
    lateral_accel_g         FLOAT        COMMENT '横向加速度(g)',
    longitudinal_accel_g    FLOAT        COMMENT '纵向加速度(g)',
    jerk_ms3                FLOAT        COMMENT '加加速度(m/s3)',
    planning_latency_ms     FLOAT        COMMENT '规划延迟(ms)',
    tenant_id               VARCHAR(50)  NOT NULL DEFAULT 'default',
    INDEX idx_tenant (tenant_id),
    INDEX idx_run    (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='规划质量指标';

-- ============================================================
-- 6. 系统日志表
-- ============================================================
DROP TABLE IF EXISTS ad_system_logs;
CREATE TABLE ad_system_logs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    run_id          VARCHAR(50)  NOT NULL,
    log_time        DATETIME     NOT NULL,
    module          ENUM('perception','planning','control','localization','prediction','map','system') NOT NULL,
    log_level       ENUM('DEBUG','INFO','WARNING','ERROR','CRITICAL') NOT NULL,
    message         TEXT         NOT NULL,
    latency_ms      FLOAT,
    cpu_usage       FLOAT        COMMENT 'CPU使用率(%)',
    memory_mb       FLOAT        COMMENT '内存使用(MB)',
    tenant_id       VARCHAR(50)  NOT NULL DEFAULT 'default',
    INDEX idx_tenant  (tenant_id),
    INDEX idx_run     (run_id),
    INDEX idx_module  (module),
    INDEX idx_level   (log_level),
    INDEX idx_time    (log_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统运行日志';

-- ============================================================
-- 7. 评估报告表
-- ============================================================
DROP TABLE IF EXISTS ad_evaluation_reports;
CREATE TABLE ad_evaluation_reports (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    report_id               VARCHAR(50)  NOT NULL UNIQUE,
    run_id                  VARCHAR(50)  NOT NULL,
    generated_at            DATETIME     DEFAULT CURRENT_TIMESTAMP,
    overall_score           FLOAT        COMMENT '综合评分 0-100',
    perception_score        FLOAT,
    planning_score          FLOAT,
    safety_score            FLOAT,
    comfort_score           FLOAT,
    efficiency_score        FLOAT,
    total_distance_km       FLOAT,
    total_duration_min      FLOAT,
    intervention_count      INT          DEFAULT 0,
    critical_event_count    INT          DEFAULT 0,
    summary                 TEXT,
    recommendations         TEXT,
    status                  ENUM('draft','final','archived') DEFAULT 'final',
    tenant_id               VARCHAR(50)  NOT NULL DEFAULT 'default',
    INDEX idx_tenant    (tenant_id),
    INDEX idx_run       (run_id),
    INDEX idx_report    (report_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评估报告';

-- ============================================================
-- 样本数据
-- ============================================================

-- 车辆数据 (tenant_a: 研发团队A, tenant_b: 研发团队B)
INSERT INTO ad_vehicles (vehicle_id, model_name, sensor_config, software_ver, hardware_ver, status, tenant_id) VALUES
('AV-001', '特斯拉 Model 3', '{"lidar":"Velodyne VLP-32","camera":"8x 1080p","radar":"12x 77GHz","ultrasonic":"12x"}', 'v2.3.1', 'HW3.0', 'active', 'tenant_a'),
('AV-002', '比亚迪 汉EV',   '{"lidar":"Livox Horizon","camera":"6x 1080p","radar":"5x 77GHz","ultrasonic":"8x"}',  'v1.8.2', 'HW2.5', 'active', 'tenant_a'),
('AV-003', '蔚来 ET7',      '{"lidar":"Innoviz Pro","camera":"11x 8MP","radar":"5x 77GHz","ultrasonic":"12x"}',   'v3.1.0', 'HW4.0', 'active', 'tenant_b'),
('AV-004', '小鹏 P7',       '{"lidar":"RoboSense RS-32","camera":"14x 2MP","radar":"5x 77GHz","ultrasonic":"12x"}','v2.0.5','HW3.5', 'active', 'tenant_b'),
('AV-005', '理想 L9',       '{"lidar":"Luminar Iris","camera":"6x 8MP","radar":"4x 77GHz","ultrasonic":"12x"}',   'v1.5.3', 'HW3.0', 'maintenance', 'tenant_a');

-- 测试运行记录 (20条)
INSERT INTO ad_test_runs (run_id, vehicle_id, scenario_type, start_time, end_time, total_distance_km, avg_speed_kmh, max_speed_kmh, weather, road_condition, location, test_engineer, status, tenant_id) VALUES
('RUN-001','AV-001','highway',     '2024-01-10 09:00:00','2024-01-10 11:30:00', 120.5, 96.4, 120.0,'sunny',  'dry',         '北京-天津高速G2','张伟','completed','tenant_a'),
('RUN-002','AV-001','urban',       '2024-01-12 14:00:00','2024-01-12 16:00:00',  35.2, 17.6,  60.0,'cloudy', 'dry',         '北京市朝阳区城区','张伟','completed','tenant_a'),
('RUN-003','AV-002','intersection','2024-01-15 10:00:00','2024-01-15 11:00:00',  12.3, 12.3,  50.0,'rainy',  'wet',         '北京市海淀区路口','李娜','completed','tenant_a'),
('RUN-004','AV-002','parking',     '2024-01-18 15:00:00','2024-01-18 15:45:00',   2.1,  2.8,  15.0,'sunny',  'dry',         '北京国贸停车场','李娜','completed','tenant_a'),
('RUN-005','AV-003','highway',     '2024-01-20 08:00:00','2024-01-20 10:30:00', 200.0,100.0, 130.0,'sunny',  'dry',         '上海-南京高速G42','王芳','completed','tenant_b'),
('RUN-006','AV-003','urban',       '2024-01-22 13:00:00','2024-01-22 15:30:00',  42.0, 16.8,  70.0,'foggy',  'wet',         '上海市浦东新区','王芳','completed','tenant_b'),
('RUN-007','AV-004','ramp',        '2024-01-25 09:30:00','2024-01-25 10:30:00',  18.5, 18.5,  80.0,'cloudy', 'dry',         '广州南沙匝道','陈明','completed','tenant_b'),
('RUN-008','AV-004','tunnel',      '2024-01-28 11:00:00','2024-01-28 11:45:00',   8.2, 10.9,  60.0,'sunny',  'dry',         '广州珠江隧道','陈明','completed','tenant_b'),
('RUN-009','AV-001','highway',     '2024-02-01 07:00:00','2024-02-01 09:30:00', 180.0, 90.0, 120.0,'snowy',  'icy',         '北京-石家庄高速G4','张伟','completed','tenant_a'),
('RUN-010','AV-002','urban',       '2024-02-05 10:00:00','2024-02-05 12:00:00',  28.0, 14.0,  55.0,'rainy',  'wet',         '北京市西城区','李娜','completed','tenant_a'),
('RUN-011','AV-003','intersection','2024-02-08 14:00:00','2024-02-08 15:30:00',  15.0, 10.0,  50.0,'sunny',  'dry',         '上海市静安区路口','王芳','completed','tenant_b'),
('RUN-012','AV-004','highway',     '2024-02-10 08:30:00','2024-02-10 11:00:00', 220.0,110.0, 130.0,'sunny',  'dry',         '深圳-广州高速G4W','陈明','completed','tenant_b'),
('RUN-013','AV-001','urban',       '2024-02-15 09:00:00','2024-02-15 11:30:00',  50.0, 20.0,  65.0,'night',  'dry',         '北京市东城区夜间','张伟','completed','tenant_a'),
('RUN-014','AV-002','parking',     '2024-02-18 16:00:00','2024-02-18 16:30:00',   1.8,  3.6,  10.0,'cloudy', 'dry',         '北京西单停车场','李娜','completed','tenant_a'),
('RUN-015','AV-003','highway',     '2024-02-20 07:30:00','2024-02-20 10:00:00', 240.0, 96.0, 120.0,'cloudy', 'dry',         '杭州-宁波高速G92','王芳','completed','tenant_b'),
('RUN-016','AV-004','urban',       '2024-02-22 14:00:00','2024-02-22 16:00:00',  38.0, 19.0,  70.0,'sunny',  'dry',         '深圳市南山区','陈明','completed','tenant_b'),
('RUN-017','AV-001','ramp',        '2024-02-25 10:00:00','2024-02-25 11:00:00',  22.0, 22.0,  90.0,'sunny',  'dry',         '北京五环匝道','张伟','completed','tenant_a'),
('RUN-018','AV-002','tunnel',      '2024-02-28 13:00:00','2024-02-28 13:40:00',   6.5,  9.8,  60.0,'sunny',  'dry',         '北京长安街隧道','李娜','completed','tenant_a'),
('RUN-019','AV-003','urban',       '2024-03-02 09:00:00','2024-03-02 11:00:00',  45.0, 22.5,  75.0,'rainy',  'wet',         '上海市徐汇区','王芳','aborted',  'tenant_b'),
('RUN-020','AV-004','intersection','2024-03-05 14:00:00','2024-03-05 15:30:00',  20.0, 13.3,  55.0,'sunny',  'dry',         '广州市天河区路口','陈明','completed','tenant_b');

-- ============================================================
-- 感知评估结果 (每run 5条, 共50条, 覆盖前10个run)
-- ============================================================
INSERT INTO ad_perception_results (run_id, frame_id, timestamp_ms, object_type, true_positive, false_positive, false_negative, precision_score, recall_score, f1_score, avg_iou, avg_confidence, detection_latency_ms, tenant_id) VALUES
('RUN-001',100,100000,'car',145,8,5,0.948,0.967,0.957,0.872,0.921,28.5,'tenant_a'),
('RUN-001',200,200000,'pedestrian',32,3,4,0.914,0.889,0.901,0.812,0.876,31.2,'tenant_a'),
('RUN-001',300,300000,'cyclist',18,2,2,0.900,0.900,0.900,0.835,0.891,29.8,'tenant_a'),
('RUN-001',400,400000,'truck',22,1,2,0.957,0.917,0.936,0.891,0.934,27.3,'tenant_a'),
('RUN-001',500,500000,'traffic_sign',55,2,1,0.965,0.982,0.973,0.921,0.956,25.1,'tenant_a'),
('RUN-002',100,100000,'car',88,6,7,0.936,0.926,0.931,0.845,0.903,32.1,'tenant_a'),
('RUN-002',200,200000,'pedestrian',65,8,9,0.890,0.878,0.884,0.798,0.851,35.4,'tenant_a'),
('RUN-002',300,300000,'cyclist',28,4,5,0.875,0.848,0.861,0.782,0.834,33.7,'tenant_a'),
('RUN-002',400,400000,'traffic_light',42,3,2,0.933,0.955,0.944,0.876,0.912,29.5,'tenant_a'),
('RUN-002',500,500000,'truck',15,2,3,0.882,0.833,0.857,0.801,0.856,31.8,'tenant_a'),
('RUN-003',100,100000,'car',72,9,8,0.889,0.900,0.894,0.821,0.878,38.2,'tenant_a'),
('RUN-003',200,200000,'pedestrian',48,7,6,0.873,0.889,0.881,0.795,0.843,40.1,'tenant_a'),
('RUN-003',300,300000,'cyclist',22,5,4,0.815,0.846,0.830,0.751,0.812,39.5,'tenant_a'),
('RUN-003',400,400000,'traffic_light',38,4,3,0.905,0.927,0.916,0.856,0.893,36.5,'tenant_a'),
('RUN-003',500,500000,'motorcycle',12,3,4,0.800,0.750,0.774,0.712,0.778,42.3,'tenant_a'),
('RUN-004',100,100000,'car',25,2,1,0.926,0.962,0.943,0.887,0.921,22.5,'tenant_a'),
('RUN-004',200,200000,'pedestrian',18,2,2,0.900,0.900,0.900,0.845,0.889,24.1,'tenant_a'),
('RUN-004',300,300000,'cyclist',8,1,1,0.889,0.889,0.889,0.823,0.867,23.8,'tenant_a'),
('RUN-004',400,400000,'truck',5,0,1,1.000,0.833,0.909,0.912,0.945,21.2,'tenant_a'),
('RUN-004',500,500000,'traffic_sign',12,1,0,0.923,1.000,0.960,0.934,0.967,20.5,'tenant_a'),
('RUN-005',100,100000,'car',198,10,8,0.952,0.961,0.956,0.889,0.932,26.8,'tenant_b'),
('RUN-005',200,200000,'truck',45,3,2,0.938,0.957,0.947,0.901,0.938,25.3,'tenant_b'),
('RUN-005',300,300000,'pedestrian',15,2,3,0.882,0.833,0.857,0.801,0.856,29.7,'tenant_b'),
('RUN-005',400,400000,'traffic_sign',68,3,2,0.958,0.971,0.964,0.923,0.951,24.1,'tenant_b'),
('RUN-005',500,500000,'cyclist',12,1,2,0.923,0.857,0.889,0.845,0.891,28.4,'tenant_b'),
('RUN-006',100,100000,'car',105,12,10,0.897,0.913,0.905,0.832,0.878,35.6,'tenant_b'),
('RUN-006',200,200000,'pedestrian',78,11,9,0.876,0.897,0.886,0.801,0.845,38.9,'tenant_b'),
('RUN-006',300,300000,'cyclist',35,6,5,0.854,0.875,0.864,0.778,0.823,37.2,'tenant_b'),
('RUN-006',400,400000,'traffic_light',52,5,4,0.912,0.929,0.920,0.867,0.901,33.4,'tenant_b'),
('RUN-006',500,500000,'motorcycle',18,4,5,0.818,0.783,0.800,0.723,0.778,41.5,'tenant_b'),
('RUN-007',100,100000,'car',62,5,4,0.925,0.939,0.932,0.878,0.912,30.2,'tenant_b'),
('RUN-007',200,200000,'pedestrian',20,3,3,0.870,0.870,0.870,0.801,0.845,33.5,'tenant_b'),
('RUN-007',300,300000,'truck',15,1,2,0.938,0.882,0.909,0.867,0.901,28.7,'tenant_b'),
('RUN-007',400,400000,'traffic_sign',30,2,1,0.938,0.968,0.952,0.912,0.945,26.3,'tenant_b'),
('RUN-007',500,500000,'cyclist',8,1,1,0.889,0.889,0.889,0.834,0.878,31.8,'tenant_b'),
('RUN-008',100,100000,'car',45,4,3,0.918,0.938,0.928,0.867,0.901,29.5,'tenant_b'),
('RUN-008',200,200000,'pedestrian',12,2,2,0.857,0.857,0.857,0.789,0.834,32.1,'tenant_b'),
('RUN-008',300,300000,'truck',10,1,1,0.909,0.909,0.909,0.856,0.889,27.8,'tenant_b'),
('RUN-008',400,400000,'traffic_sign',22,1,1,0.957,0.957,0.957,0.923,0.951,25.4,'tenant_b'),
('RUN-008',500,500000,'cyclist',6,1,0,0.857,1.000,0.923,0.878,0.912,30.2,'tenant_b'),
('RUN-009',100,100000,'car',155,15,12,0.912,0.928,0.920,0.845,0.889,35.8,'tenant_a'),
('RUN-009',200,200000,'pedestrian',28,5,6,0.848,0.824,0.836,0.756,0.812,39.4,'tenant_a'),
('RUN-009',300,300000,'truck',35,4,3,0.897,0.921,0.909,0.856,0.891,33.2,'tenant_a'),
('RUN-009',400,400000,'traffic_sign',48,4,3,0.923,0.941,0.932,0.889,0.921,31.5,'tenant_a'),
('RUN-009',500,500000,'cyclist',10,3,4,0.769,0.714,0.741,0.678,0.734,42.7,'tenant_a'),
('RUN-010',100,100000,'car',92,11,9,0.893,0.911,0.902,0.823,0.867,37.2,'tenant_a'),
('RUN-010',200,200000,'pedestrian',55,8,7,0.873,0.887,0.880,0.801,0.845,40.5,'tenant_a'),
('RUN-010',300,300000,'cyclist',25,5,4,0.833,0.862,0.847,0.767,0.823,38.9,'tenant_a'),
('RUN-010',400,400000,'traffic_light',45,5,4,0.900,0.918,0.909,0.845,0.878,35.6,'tenant_a'),
('RUN-010',500,500000,'motorcycle',15,4,5,0.789,0.750,0.769,0.701,0.756,44.3,'tenant_a');

-- ============================================================
-- 安全事件 (50条)
-- ============================================================
INSERT INTO ad_safety_events (run_id, event_id, event_time, event_type, severity, description, human_intervention, ego_speed_kmh, ttc_seconds, resolved, tenant_id) VALUES
('RUN-001','EVT-001','2024-01-10 09:45:00','hard_brake','low','前方车辆急刹，自动紧急制动触发',FALSE,85.0,3.2,TRUE,'tenant_a'),
('RUN-001','EVT-002','2024-01-10 10:20:00','lane_departure','low','变道时短暂越线，系统自动修正',FALSE,95.0,NULL,TRUE,'tenant_a'),
('RUN-002','EVT-003','2024-01-12 14:30:00','near_miss','medium','行人突然横穿，TTC 2.1秒',FALSE,35.0,2.1,TRUE,'tenant_a'),
('RUN-002','EVT-004','2024-01-12 15:10:00','human_intervention','high','复杂路口判断失误，人工接管',TRUE,28.0,NULL,TRUE,'tenant_a'),
('RUN-003','EVT-005','2024-01-15 10:30:00','hard_brake','medium','雨天路滑，前车急停',FALSE,42.0,2.8,TRUE,'tenant_a'),
('RUN-003','EVT-006','2024-01-15 11:00:00','near_miss','high','骑行者突然切入，TTC 1.5秒',FALSE,38.0,1.5,TRUE,'tenant_a'),
('RUN-003','EVT-007','2024-01-15 11:30:00','human_intervention','critical','感知失效，人工紧急接管',TRUE,30.0,NULL,TRUE,'tenant_a'),
('RUN-005','EVT-008','2024-01-20 08:30:00','lane_departure','low','高速变道轻微越线',FALSE,110.0,NULL,TRUE,'tenant_b'),
('RUN-005','EVT-009','2024-01-20 09:15:00','hard_brake','low','前方施工区减速',FALSE,100.0,4.5,TRUE,'tenant_b'),
('RUN-006','EVT-010','2024-01-22 13:30:00','near_miss','medium','雾天能见度低，行人识别延迟',FALSE,32.0,2.5,TRUE,'tenant_b'),
('RUN-006','EVT-011','2024-01-22 14:00:00','traffic_light_violation','high','黄灯判断错误，闯红灯风险',FALSE,45.0,NULL,TRUE,'tenant_b'),
('RUN-006','EVT-012','2024-01-22 14:45:00','human_intervention','high','复杂交叉口人工接管',TRUE,25.0,NULL,TRUE,'tenant_b'),
('RUN-007','EVT-013','2024-01-25 10:15:00','obstacle_avoidance','medium','隧道内障碍物规避',FALSE,55.0,3.0,TRUE,'tenant_b'),
('RUN-008','EVT-014','2024-01-28 09:20:00','hard_brake','low','匝道合流紧急制动',FALSE,50.0,3.8,TRUE,'tenant_b'),
('RUN-009','EVT-015','2024-02-01 08:45:00','lane_departure','medium','冰雪路面侧滑',FALSE,80.0,NULL,TRUE,'tenant_a'),
('RUN-009','EVT-016','2024-02-01 09:30:00','hard_brake','high','雪地制动距离超预期',FALSE,75.0,2.0,TRUE,'tenant_a'),
('RUN-009','EVT-017','2024-02-01 10:00:00','human_intervention','critical','冰面失控，人工紧急接管',TRUE,60.0,NULL,TRUE,'tenant_a'),
('RUN-010','EVT-018','2024-02-05 14:20:00','near_miss','medium','雨天行人识别延迟',FALSE,28.0,2.3,TRUE,'tenant_a'),
('RUN-010','EVT-019','2024-02-05 15:00:00','hard_brake','low','积水路面减速',FALSE,35.0,4.0,TRUE,'tenant_a'),
('RUN-011','EVT-020','2024-02-08 10:30:00','traffic_light_violation','medium','感知延迟导致黄灯判断偏差',FALSE,40.0,NULL,TRUE,'tenant_b'),
('RUN-012','EVT-021','2024-02-10 09:30:00','lane_departure','low','高速超车轻微越线',FALSE,120.0,NULL,TRUE,'tenant_b'),
('RUN-012','EVT-022','2024-02-10 10:15:00','hard_brake','low','前方事故减速区',FALSE,105.0,5.0,TRUE,'tenant_b'),
('RUN-013','EVT-023','2024-02-15 13:30:00','near_miss','high','夜间行人识别失败，TTC 1.8秒',FALSE,42.0,1.8,TRUE,'tenant_a'),
('RUN-013','EVT-024','2024-02-15 14:00:00','human_intervention','high','夜间复杂场景人工接管',TRUE,38.0,NULL,TRUE,'tenant_a'),
('RUN-014','EVT-025','2024-02-18 10:20:00','obstacle_avoidance','low','停车场障碍物规避',FALSE,12.0,2.5,TRUE,'tenant_a'),
('RUN-015','EVT-026','2024-02-20 09:45:00','hard_brake','medium','匝道紧急制动',FALSE,65.0,2.5,TRUE,'tenant_b'),
('RUN-016','EVT-027','2024-02-22 14:20:00','obstacle_avoidance','medium','隧道内落石规避',FALSE,48.0,2.8,TRUE,'tenant_b'),
('RUN-017','EVT-028','2024-03-01 08:30:00','lane_departure','low','高速变道越线',FALSE,105.0,NULL,TRUE,'tenant_a'),
('RUN-017','EVT-029','2024-03-01 09:00:00','hard_brake','low','前方减速区',FALSE,95.0,4.2,TRUE,'tenant_a'),
('RUN-018','EVT-030','2024-03-05 14:30:00','human_intervention','critical','系统故障，紧急接管',TRUE,32.0,NULL,TRUE,'tenant_a'),
('RUN-019','EVT-031','2024-03-08 09:30:00','lane_departure','low','高速变道',FALSE,115.0,NULL,TRUE,'tenant_b'),
('RUN-019','EVT-032','2024-03-08 10:00:00','hard_brake','low','前方施工',FALSE,100.0,4.8,TRUE,'tenant_b'),
('RUN-020','EVT-033','2024-03-10 13:30:00','near_miss','medium','城区行人横穿',FALSE,35.0,2.2,TRUE,'tenant_b'),
('RUN-020','EVT-034','2024-03-10 14:00:00','traffic_light_violation','low','黄灯通过判断',FALSE,42.0,NULL,TRUE,'tenant_b'),
('RUN-001','EVT-035','2024-01-10 10:50:00','obstacle_avoidance','low','高速路肩障碍物',FALSE,90.0,3.5,TRUE,'tenant_a'),
('RUN-002','EVT-036','2024-01-12 15:40:00','speed_violation','low','限速区超速5km/h',FALSE,65.0,NULL,TRUE,'tenant_a'),
('RUN-005','EVT-037','2024-01-20 09:45:00','obstacle_avoidance','medium','高速落石规避',FALSE,105.0,2.8,TRUE,'tenant_b'),
('RUN-006','EVT-038','2024-01-22 15:00:00','speed_violation','low','城区超速',FALSE,68.0,NULL,TRUE,'tenant_b'),
('RUN-009','EVT-039','2024-02-01 10:30:00','lane_departure','high','冰面侧滑严重越线',FALSE,55.0,NULL,TRUE,'tenant_a'),
('RUN-010','EVT-040','2024-02-05 15:30:00','near_miss','low','雨天轻微险情',FALSE,25.0,3.5,TRUE,'tenant_a'),
('RUN-011','EVT-041','2024-02-08 11:00:00','hard_brake','medium','路口急停',FALSE,35.0,2.2,TRUE,'tenant_b'),
('RUN-012','EVT-042','2024-02-10 11:00:00','obstacle_avoidance','low','高速碎石规避',FALSE,110.0,3.8,TRUE,'tenant_b'),
('RUN-013','EVT-043','2024-02-15 14:30:00','speed_violation','low','夜间超速',FALSE,72.0,NULL,TRUE,'tenant_a'),
('RUN-015','EVT-044','2024-02-20 10:00:00','hard_brake','low','匝道减速',FALSE,55.0,4.5,TRUE,'tenant_b'),
('RUN-016','EVT-045','2024-02-22 14:40:00','lane_departure','low','隧道内轻微越线',FALSE,45.0,NULL,TRUE,'tenant_b'),
('RUN-017','EVT-046','2024-03-01 09:30:00','obstacle_avoidance','low','高速路障规避',FALSE,88.0,4.0,TRUE,'tenant_a'),
('RUN-019','EVT-047','2024-03-08 10:30:00','hard_brake','medium','高速紧急制动',FALSE,95.0,2.5,TRUE,'tenant_b'),
('RUN-019','EVT-048','2024-03-08 11:00:00','lane_departure','low','变道越线',FALSE,105.0,NULL,TRUE,'tenant_b'),
('RUN-020','EVT-049','2024-03-10 14:30:00','near_miss','medium','城区险情',FALSE,38.0,2.0,TRUE,'tenant_b'),
('RUN-020','EVT-050','2024-03-10 15:00:00','human_intervention','medium','复杂路口接管',TRUE,30.0,NULL,TRUE,'tenant_b');

-- ============================================================
-- 规划指标 (每个run 3条, 共60条)
-- ============================================================
INSERT INTO ad_planning_metrics (run_id, timestamp_ms, comfort_score, efficiency_score, safety_score, path_deviation_m, speed_smoothness, lateral_accel_g, longitudinal_accel_g, jerk_ms3, planning_latency_ms, tenant_id) VALUES
('RUN-001',100000,85.2,92.1,88.5,0.12,0.91,0.15,0.22,1.8,45.2,'tenant_a'),
('RUN-001',200000,83.8,90.5,86.2,0.18,0.88,0.22,0.35,2.1,48.7,'tenant_a'),
('RUN-001',300000,87.1,93.5,90.1,0.08,0.94,0.11,0.18,1.5,42.3,'tenant_a'),
('RUN-002',100000,78.5,72.3,82.1,0.35,0.76,0.32,0.48,3.2,58.5,'tenant_a'),
('RUN-002',200000,75.2,70.1,79.8,0.42,0.73,0.38,0.55,3.8,62.1,'tenant_a'),
('RUN-002',300000,80.1,74.5,84.5,0.28,0.79,0.28,0.42,2.8,55.8,'tenant_a'),
('RUN-003',100000,72.3,68.5,75.2,0.48,0.71,0.35,0.52,3.5,65.3,'tenant_a'),
('RUN-003',200000,70.1,65.2,72.8,0.55,0.68,0.42,0.58,4.1,70.2,'tenant_a'),
('RUN-003',300000,68.5,62.8,70.1,0.62,0.65,0.48,0.65,4.5,75.8,'tenant_a'),
('RUN-004',100000,92.1,65.5,95.2,0.05,0.96,0.08,0.12,1.2,35.5,'tenant_a'),
('RUN-004',200000,90.5,62.8,93.8,0.08,0.94,0.10,0.15,1.4,38.2,'tenant_a'),
('RUN-004',300000,93.5,68.2,96.1,0.04,0.97,0.06,0.10,1.1,33.8,'tenant_a'),
('RUN-005',100000,88.5,95.2,91.2,0.09,0.93,0.13,0.20,1.6,40.5,'tenant_b'),
('RUN-005',200000,86.2,93.8,89.5,0.12,0.90,0.18,0.28,1.9,43.2,'tenant_b'),
('RUN-005',300000,89.8,96.5,92.8,0.07,0.95,0.10,0.17,1.4,38.8,'tenant_b'),
('RUN-006',100000,75.8,70.5,80.2,0.38,0.74,0.35,0.50,3.3,60.5,'tenant_b'),
('RUN-006',200000,73.2,68.2,78.5,0.45,0.71,0.40,0.58,3.8,65.2,'tenant_b'),
('RUN-006',300000,70.5,65.8,76.2,0.52,0.68,0.45,0.62,4.2,72.1,'tenant_b'),
('RUN-007',100000,82.5,78.5,85.2,0.22,0.85,0.25,0.38,2.5,52.3,'tenant_b'),
('RUN-007',200000,80.1,75.2,83.5,0.28,0.82,0.30,0.45,2.8,55.8,'tenant_b'),
('RUN-007',300000,84.8,80.5,86.8,0.18,0.87,0.22,0.32,2.2,50.1,'tenant_b'),
('RUN-008',100000,88.2,72.5,90.5,0.10,0.92,0.14,0.22,1.7,42.5,'tenant_b'),
('RUN-008',200000,86.5,70.2,88.8,0.15,0.89,0.18,0.28,2.0,45.8,'tenant_b'),
('RUN-008',300000,89.8,74.8,92.1,0.08,0.94,0.12,0.18,1.5,40.2,'tenant_b'),
('RUN-009',100000,72.5,85.2,68.5,0.55,0.65,0.45,0.62,4.2,72.5,'tenant_a'),
('RUN-009',200000,68.2,82.5,65.2,0.68,0.60,0.55,0.72,5.1,80.2,'tenant_a'),
('RUN-009',300000,70.1,80.8,66.8,0.62,0.62,0.50,0.68,4.8,78.5,'tenant_a'),
('RUN-010',100000,74.5,68.2,78.5,0.42,0.72,0.38,0.52,3.5,65.2,'tenant_a'),
('RUN-010',200000,72.1,65.5,76.2,0.48,0.69,0.42,0.58,4.0,70.5,'tenant_a'),
('RUN-010',300000,70.8,62.8,74.5,0.55,0.66,0.48,0.65,4.5,75.8,'tenant_a'),
('RUN-011',100000,80.5,75.2,82.8,0.25,0.82,0.28,0.40,2.8,55.2,'tenant_b'),
('RUN-011',200000,78.2,72.5,80.5,0.30,0.79,0.32,0.48,3.2,60.5,'tenant_b'),
('RUN-011',300000,82.1,78.5,84.2,0.20,0.85,0.25,0.35,2.5,52.8,'tenant_b'),
('RUN-012',100000,87.5,94.2,89.8,0.10,0.92,0.14,0.22,1.7,42.5,'tenant_b'),
('RUN-012',200000,85.2,92.5,88.2,0.14,0.89,0.18,0.30,2.0,45.8,'tenant_b'),
('RUN-012',300000,89.1,95.8,91.5,0.08,0.94,0.12,0.18,1.5,40.2,'tenant_b'),
('RUN-013',100000,76.5,72.5,80.2,0.38,0.75,0.32,0.48,3.2,60.5,'tenant_a'),
('RUN-013',200000,74.2,70.2,78.5,0.42,0.72,0.38,0.55,3.8,65.8,'tenant_a'),
('RUN-013',300000,78.1,75.5,82.1,0.32,0.78,0.28,0.42,2.8,58.2,'tenant_a'),
('RUN-014',100000,91.5,62.5,94.2,0.06,0.95,0.08,0.12,1.2,35.8,'tenant_a'),
('RUN-014',200000,89.8,60.2,92.5,0.08,0.93,0.10,0.15,1.5,38.5,'tenant_a'),
('RUN-014',300000,93.2,65.5,95.8,0.05,0.97,0.06,0.10,1.0,33.2,'tenant_a'),
('RUN-015',100000,86.5,94.5,89.2,0.12,0.91,0.15,0.25,1.8,43.5,'tenant_b'),
('RUN-015',200000,84.2,92.2,87.5,0.15,0.88,0.20,0.32,2.2,48.2,'tenant_b'),
('RUN-015',300000,88.1,96.8,91.2,0.09,0.93,0.12,0.20,1.5,40.8,'tenant_b'),
('RUN-016',100000,78.5,72.5,82.1,0.35,0.76,0.32,0.48,3.2,60.5,'tenant_b'),
('RUN-016',200000,76.2,70.2,80.5,0.42,0.73,0.38,0.55,3.8,65.2,'tenant_b'),
('RUN-016',300000,80.1,75.5,84.2,0.28,0.79,0.28,0.42,2.8,55.8,'tenant_b'),
('RUN-017',100000,84.5,82.5,86.8,0.18,0.86,0.22,0.35,2.4,50.5,'tenant_a'),
('RUN-017',200000,82.2,80.2,85.2,0.22,0.83,0.28,0.42,2.8,55.2,'tenant_a'),
('RUN-017',300000,86.1,85.5,88.5,0.15,0.88,0.18,0.30,2.2,48.8,'tenant_a'),
('RUN-018',100000,88.5,72.5,90.2,0.10,0.92,0.14,0.22,1.7,42.5,'tenant_a'),
('RUN-018',200000,86.2,70.2,88.5,0.15,0.89,0.18,0.28,2.0,45.8,'tenant_a'),
('RUN-018',300000,90.1,74.8,92.1,0.08,0.94,0.12,0.18,1.5,40.2,'tenant_a'),
('RUN-019',100000,74.5,68.5,78.2,0.42,0.72,0.38,0.52,3.5,65.2,'tenant_b'),
('RUN-019',200000,72.2,65.2,76.5,0.48,0.69,0.42,0.58,4.0,70.5,'tenant_b'),
('RUN-019',300000,70.8,62.8,74.2,0.55,0.66,0.48,0.65,4.5,75.8,'tenant_b'),
('RUN-020',100000,80.5,75.5,82.8,0.25,0.82,0.28,0.40,2.8,55.2,'tenant_b'),
('RUN-020',200000,78.2,72.2,80.5,0.30,0.79,0.32,0.48,3.2,60.5,'tenant_b'),
('RUN-020',300000,82.1,78.8,84.2,0.20,0.85,0.25,0.35,2.5,52.8,'tenant_b');

-- ============================================================
-- 系统日志 (30条, 覆盖多个模块和级别)
-- ============================================================
INSERT INTO ad_system_logs (run_id, log_time, module, log_level, message, latency_ms, cpu_usage, memory_mb, tenant_id) VALUES
('RUN-001','2024-01-10 09:00:05','system','INFO','系统启动完成，所有模块初始化成功',NULL,15.2,2048,'tenant_a'),
('RUN-001','2024-01-10 09:05:00','perception','INFO','激光雷达点云处理正常，帧率 10Hz',28.5,45.8,3072,'tenant_a'),
('RUN-001','2024-01-10 09:15:00','perception','WARNING','行人检测模型置信度下降至 0.82',31.2,48.5,3200,'tenant_a'),
('RUN-001','2024-01-10 09:30:00','planning','INFO','路径规划正常，规划延迟 45ms',45.2,32.5,2560,'tenant_a'),
('RUN-001','2024-01-10 09:45:00','control','WARNING','紧急制动触发，减速度 0.5g',NULL,55.2,3584,'tenant_a'),
('RUN-001','2024-01-10 10:00:00','localization','INFO','RTK定位精度 0.02m，状态正常',5.2,12.5,1536,'tenant_a'),
('RUN-002','2024-01-12 14:00:05','system','INFO','系统启动，城区模式',NULL,18.5,2200,'tenant_a'),
('RUN-002','2024-01-12 14:30:00','perception','ERROR','行人检测模块超时，延迟 120ms',120.5,62.3,4096,'tenant_a'),
('RUN-002','2024-01-12 14:30:01','perception','WARNING','启用降级感知策略',NULL,55.8,3800,'tenant_a'),
('RUN-002','2024-01-12 15:10:00','planning','ERROR','复杂路口路径规划失败，降级至跟停模式',85.5,58.2,3500,'tenant_a'),
('RUN-003','2024-01-15 10:00:05','system','INFO','雨天模式启动',NULL,22.5,2400,'tenant_a'),
('RUN-003','2024-01-15 10:30:00','perception','ERROR','摄像头受雨水影响，目标识别率下降',45.8,52.5,3400,'tenant_a'),
('RUN-003','2024-01-15 11:00:00','prediction','WARNING','骑行者轨迹预测不确定性增加',15.2,28.5,2048,'tenant_a'),
('RUN-005','2024-01-20 08:00:05','system','INFO','高速模式启动，车速上限 130km/h',NULL,14.5,2048,'tenant_b'),
('RUN-005','2024-01-20 09:15:00','perception','INFO','高速场景感知正常，检测延迟 26ms',26.5,42.8,2800,'tenant_b'),
('RUN-005','2024-01-20 10:00:00','planning','INFO','车道变更规划执行成功',38.5,30.2,2400,'tenant_b'),
('RUN-006','2024-01-22 13:00:05','system','INFO','雾天模式启动',NULL,20.5,2300,'tenant_b'),
('RUN-006','2024-01-22 13:30:00','perception','WARNING','能见度低，激光雷达受雾气干扰',35.5,48.5,3200,'tenant_b'),
('RUN-006','2024-01-22 14:00:00','perception','CRITICAL','交通灯检测模块置信度低于阈值 0.6',42.8,55.2,3800,'tenant_b'),
('RUN-007','2024-01-25 09:30:05','system','INFO','匝道模式启动',NULL,16.5,2100,'tenant_b'),
('RUN-007','2024-01-25 10:15:00','planning','WARNING','匝道汇入规划延迟较高',65.2,38.5,2800,'tenant_b'),
('RUN-008','2024-01-28 11:00:05','system','INFO','隧道模式启动，切换至惯导定位',NULL,18.5,2200,'tenant_b'),
('RUN-008','2024-01-28 11:15:00','localization','WARNING','隧道内 GPS 信号丢失，切换至 IMU',NULL,22.5,2400,'tenant_b'),
('RUN-008','2024-01-28 11:30:00','localization','INFO','隧道出口 GPS 信号恢复',8.5,16.5,1800,'tenant_b'),
('RUN-009','2024-02-01 07:00:05','system','INFO','雪地模式启动，降低车速上限',NULL,25.5,2500,'tenant_a'),
('RUN-009','2024-02-01 08:45:00','control','CRITICAL','冰雪路面检测到车轮打滑',NULL,68.5,4096,'tenant_a'),
('RUN-009','2024-02-01 09:30:00','perception','ERROR','雪地反光导致误检，产生 5 个假阳性',38.5,52.5,3500,'tenant_a'),
('RUN-009','2024-02-01 10:00:00','planning','CRITICAL','规划模块无法生成安全路径，请求人工接管',95.2,62.5,4096,'tenant_a'),
('RUN-010','2024-02-05 10:00:05','system','INFO','雨天城区模式启动',NULL,20.5,2300,'tenant_a'),
('RUN-010','2024-02-05 10:30:00','perception','WARNING','雨天行人检测延迟上升至 40ms',40.5,50.2,3400,'tenant_a');

-- ============================================================
-- 评估报告 (10条, 覆盖不同场景)
-- ============================================================
INSERT INTO ad_evaluation_reports (report_id, run_id, overall_score, perception_score, planning_score, safety_score, comfort_score, efficiency_score, total_distance_km, total_duration_min, intervention_count, critical_event_count, summary, recommendations, status, tenant_id) VALUES
('RPT-001','RUN-001',88.5,92.1,85.2,86.5,85.2,92.1,120.5,150,0,0,'高速场景整体表现优秀。感知模块在车辆和交通标志检测上精度均超过 94%，规划模块保持稳定的路径跟踪，全程无人工接管。','建议优化行人检测在高速行驶中的召回率，当前为 88.9%，目标提升至 92% 以上。','final','tenant_a'),
('RPT-002','RUN-002',78.2,85.2,75.5,72.1,78.5,72.3,35.2,120,1,0,'城区场景面临较多挑战。感知模块在复杂路口出现行人检测延迟，规划模块在路口决策时偶发失败导致降级。','重点优化城区复杂路口的感知-规划协同，提升行人检测的鲁棒性，降低超时概率。','final','tenant_a'),
('RPT-003','RUN-003',68.5,76.2,70.1,65.2,72.3,68.5,12.3,60,1,1,'雨天交叉路口测试暴露了感知系统在恶劣天气下的脆弱性。摄像头受雨水影响导致识别率下降，骑行者轨迹预测不确定性增加。','增强雨天感知冗余策略，引入激光雷达辅助行人检测，优化骑行者预测模型。','final','tenant_a'),
('RPT-004','RUN-004',93.5,95.2,90.5,94.8,92.1,65.5,2.1,45,0,0,'停车场场景表现最佳。低速环境下感知精度极高，规划稳定性好，舒适度评分达到 92.1。行驶效率较低但符合场景预期。','停车场场景已达到上线标准，可考虑增加自动泊车功能验证。','final','tenant_a'),
('RPT-005','RUN-005',92.8,94.5,90.2,91.5,88.5,95.2,200.0,150,0,0,'长距离高速测试验证了系统在高负荷条件下的稳定性。200km 全程无安全事件，感知和规划指标均优于平均水平。','当前高速场景算法成熟度高，建议扩大测试里程至 500km 验证长期稳定性。','final','tenant_b'),
('RPT-006','RUN-006',72.1,78.5,75.2,76.2,75.8,70.5,42.0,150,1,1,'雾天城区测试揭示了感知模块在低能见度条件下的性能瓶颈。交通灯检测置信度低于安全阈值，需要传感器融合策略。','增加毫米波雷达与摄像头的融合算法，在雾天场景下优先使用雷达数据辅助决策。','final','tenant_b'),
('RPT-007','RUN-007',82.5,86.5,80.5,85.2,82.5,78.5,18.5,60,0,0,'匝道场景测试整体良好。规划模块在汇入主路时延迟偏高但仍在可接受范围内，无安全事件发生。','优化匝道汇入路径预测算法，降低规划延迟至 50ms 以内。','final','tenant_b'),
('RPT-008','RUN-008',88.2,90.5,88.5,90.2,88.2,72.5,8.2,45,0,0,'隧道场景测试验证了定位模块的冗余切换能力。GPS 丢失期间惯导保持精度，驶出后快速恢复定位。','验证惯导在更长隧道中的精度漂移情况，建议增加视觉定位作为第三冗余。','final','tenant_b'),
('RPT-009','RUN-009',65.2,70.1,68.5,62.8,72.5,85.2,180.0,150,1,2,'雪地高速测试暴露了系统在极端天气下的多方面问题。感知模块误检率上升，控制模块检测到车轮打滑，最终因无法生成安全路径触发人工接管。','重点投入冰雪场景算法优化，引入雪地专用感知模型，优化防滑控制策略，建议暂时限制雪地自动驾驶功能。','final','tenant_a'),
('RPT-010','RUN-010',74.5,80.5,78.2,78.5,74.5,68.2,28.0,120,0,0,'雨天城区测试表现中等偏上。感知模块延迟有所上升但未触发严重降级，规划模块在积水路段表现稳定。','继续优化雨天感知算法，重点关注行人和骑行者的检测延迟，目标降至 30ms 以内。','final','tenant_a');
