-- GeoAssist MySQL 数据库初始化脚本
-- 用途：创建用户表 + repair_shops 表
-- 使用方式：mysql -u root -p < init_mysql.sql

SET NAMES utf8mb4;

-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS its DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE its;

-- 2. 创建 users 表（用户认证）
DROP TABLE IF EXISTS users;
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希 (bcrypt)',
    display_name VARCHAR(100) COMMENT '显示名称',
    avatar_url VARCHAR(300) COMMENT '头像URL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户认证表';

-- 3. 插入默认体验账号（密码: 123456, 使用 bcrypt hash）
-- hash 生成: bcrypt.hashpw('123456'.encode('utf-8'), bcrypt.gensalt())
INSERT INTO users (username, password_hash, display_name) VALUES
('admin', '$2b$12$wTD4OjP3dlWgrmR3B42HNugfp3722gGHEnl4tWFc3KHNH0cS/Fya.', '管理员')
ON DUPLICATE KEY UPDATE username=username;

-- 4. 创建 repair_shops 表
DROP TABLE IF EXISTS repair_shops;
CREATE TABLE repair_shops (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service_station_name VARCHAR(200) NOT NULL COMMENT '服务站名称',
    province VARCHAR(50) COMMENT '省份',
    city VARCHAR(50) COMMENT '城市',
    district VARCHAR(50) COMMENT '区县',
    address VARCHAR(300) COMMENT '详细地址',
    phone VARCHAR(50) COMMENT '联系电话',
    manager VARCHAR(100) COMMENT '负责人',
    manager_phone VARCHAR(50) COMMENT '负责人电话',
    opening_hours VARCHAR(200) COMMENT '营业时间',
    repair_types VARCHAR(200) COMMENT '维修类型',
    repair_specialties TEXT COMMENT '维修专长',
    repair_services TEXT COMMENT '维修服务项目',
    supported_brands VARCHAR(200) COMMENT '支持品牌',
    rating DECIMAL(2,1) COMMENT '评分',
    established_year INT COMMENT '成立年份',
    employee_count INT COMMENT '员工人数',
    service_station_description TEXT COMMENT '服务站描述',
    latitude DECIMAL(10,6) COMMENT '纬度 (BD09LL)',
    longitude DECIMAL(10,6) COMMENT '经度 (BD09LL)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='野外服务站/维修点信息表';

-- 3. 插入测试数据（北京及周边示例）
INSERT INTO repair_shops (
    service_station_name, province, city, district, address,
    phone, manager, manager_phone, opening_hours,
    repair_types, repair_specialties, repair_services, supported_brands,
    rating, established_year, employee_count, service_station_description,
    latitude, longitude
) VALUES
('北京昌平野外装备维修站', '北京', '北京市', '昌平区', '温都水城附近',
 '010-88880001', '张师傅', '13800001001', '09:00-18:00',
 'GPS,对讲机,登山杖,帐篷', 'GPS校准,电池更换', '设备检测,零件更换,紧急维修', '佳明,北斗,摩托罗拉',
 4.5, 2018, 5, '昌平区主要野外装备维修点，支持GPS和对讲机维修',
 40.090000, 116.360000),

('北京海淀地质仪器服务站', '北京', '北京市', '海淀区', '中关村南大街',
 '010-88880002', '李工', '13800001002', '08:30-17:30',
 '地质罗盘,水准仪,全站仪', '仪器校准,精度检测', '定期保养,故障排查,配件供应', '南方测绘,徕卡,拓普康',
 4.8, 2015, 8, '海淀区专业地质仪器维修服务站',
 39.960000, 116.320000),

('北京朝阳户外装备维修中心', '北京', '北京市', '朝阳区', '建国路88号',
 '010-88880003', '王师傅', '13800001003', '10:00-19:00',
 '帐篷,睡袋,登山鞋,冲锋衣', '防水处理,拉链更换', '清洗保养,修补缝制', '探路者,凯乐石,北面',
 4.2, 2020, 3, '朝阳区户外装备综合维修点',
 39.910000, 116.470000),

('河北涿州野外补给站', '河北', '保定市', '涿州市', '桃园街道',
 '0312-8880001', '赵站长', '13900001001', '全天24小时',
 '燃料,食品,饮用水,药品', '应急物资供应', '物资补给,临时休息,急救', '通用',
 4.0, 2019, 2, '涿州地区野外作业补给中转站',
 39.490000, 115.970000),

('内蒙古呼和浩特地质维修站', '内蒙古', '呼和浩特市', '赛罕区', '大学东路',
 '0471-8880001', '巴特尔', '15000001001', '09:00-17:00',
 '钻机,取样器,岩石锤', '钻探设备维修', '设备大修,零件加工,技术培训', '山河智能,中联重科',
 4.6, 2016, 6, '内蒙古地区地质勘探设备专业维修点',
 40.820000, 111.720000),

('北京门头沟野外医疗救助站', '北京', '北京市', '门头沟区', '门头沟路',
 '010-88880004', '刘医生', '13800001004', '08:00-20:00',
 '急救,外伤处理,蛇虫咬伤', '野外急救,创伤缝合', '医疗救助,药品供应,紧急转运', '通用医疗',
 4.7, 2021, 4, '门头沟山区野外作业医疗救助点',
 39.940000, 116.100000);

-- 4. 验证数据
SELECT COUNT(*) AS total_shops FROM repair_shops;
SELECT id, service_station_name, city, latitude, longitude FROM repair_shops;
