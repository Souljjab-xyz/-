-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS stock_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE stock_db;

-- 주식 종목 테이블
CREATE TABLE IF NOT EXISTS stocks (
    symbol VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    market VARCHAR(20),
    sector VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 주가 데이터 테이블
CREATE TABLE IF NOT EXISTS stock_prices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    open_price DECIMAL(10, 2),
    high_price DECIMAL(10, 2),
    low_price DECIMAL(10, 2),
    close_price DECIMAL(10, 2) NOT NULL,
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_symbol_date (symbol, date),
    INDEX idx_symbol_date (symbol, date),
    FOREIGN KEY (symbol) REFERENCES stocks(symbol) ON DELETE CASCADE
);

-- 이동평균 데이터 저장 테이블 (선택사항)
CREATE TABLE IF NOT EXISTS moving_averages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    ma9 DECIMAL(10, 2),
    ma22 DECIMAL(10, 2),
    ma60 DECIMAL(10, 2),
    ma120 DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_symbol_date (symbol, date),
    FOREIGN KEY (symbol) REFERENCES stocks(symbol) ON DELETE CASCADE
);

-- 샘플 데이터 삽입
INSERT INTO stocks (symbol, name, market, sector) VALUES
('005930', '삼성전자', 'KOSPI', '전기전자'),
('000660', 'SK하이닉스', 'KOSPI', '전기전자'),
('035420', 'NAVER', 'KOSPI', 'IT'),
('035720', '카카오', 'KOSPI', 'IT'),
('051910', 'LG화학', 'KOSPI', '화학'),
('006400', '삼성SDI', 'KOSPI', '전기전자'),
('005380', '현대차', 'KOSPI', '운수장비'),
('000270', '기아', 'KOSPI', '운수장비'),
('068270', '셀트리온', 'KOSPI', '의약품'),
('105560', 'KB금융', 'KOSPI', '금융');

-- 저장 프로시저: 이동평균 계산
DELIMITER //
CREATE PROCEDURE calculate_moving_averages(IN p_symbol VARCHAR(20))
BEGIN
    INSERT INTO moving_averages (symbol, date, ma9, ma22, ma60, ma120)
    SELECT 
        symbol,
        date,
        AVG(close_price) OVER (ORDER BY date ROWS BETWEEN 8 PRECEDING AND CURRENT ROW) as ma9,
        AVG(close_price) OVER (ORDER BY date ROWS BETWEEN 21 PRECEDING AND CURRENT ROW) as ma22,
        AVG(close_price) OVER (ORDER BY date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) as ma60,
        AVG(close_price) OVER (ORDER BY date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) as ma120
    FROM stock_prices
    WHERE symbol = p_symbol
    ON DUPLICATE KEY UPDATE
        ma9 = VALUES(ma9),
        ma22 = VALUES(ma22),
        ma60 = VALUES(ma60),
        ma120 = VALUES(ma120);
END//
DELIMITER ;

-- 뷰: 최근 주가 및 변동률
CREATE VIEW v_recent_prices AS
SELECT 
    sp.symbol,
    s.name,
    sp.date,
    sp.close_price,
    LAG(sp.close_price) OVER (PARTITION BY sp.symbol ORDER BY sp.date) as prev_close,
    ROUND(((sp.close_price - LAG(sp.close_price) OVER (PARTITION BY sp.symbol ORDER BY sp.date)) / 
           LAG(sp.close_price) OVER (PARTITION BY sp.symbol ORDER BY sp.date)) * 100, 2) as change_pct
FROM stock_prices sp
JOIN stocks s ON sp.symbol = s.symbol
WHERE sp.date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY);

-- 권한 설정 (필요시)
-- GRANT ALL PRIVILEGES ON stock_db.* TO 'stock_user'@'localhost' IDENTIFIED BY 'password';
-- FLUSH PRIVILEGES;