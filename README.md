# -
MySQL과 Qt designer를 이용하였음. md 파일 필독
#
# 주식 분석 프로그램 설치 및 사용 가이드

## 1. 필요한 패키지 설치

### Python 패키지 설치
```bash
pip install PyQt5
pip install mysql-connector-python
pip install pandas
pip install numpy
pip install matplotlib
pip install pyqt5-tools  # Qt Designer 포함
pip install yfinance  # Yahoo Finance API
pip install beautifulsoup4  # 웹 스크래핑
pip install requests  # HTTP 요청
pip install lxml  # HTML 파싱
```

## 2. MySQL 설정

### MySQL 서버 설치
- Windows: [MySQL Installer](https://dev.mysql.com/downloads/installer/)에서 다운로드
- Mac: `brew install mysql`
- Linux: `sudo apt-get install mysql-server`

### 데이터베이스 생성
1. MySQL에 접속
```bash
mysql -u root -p
```

2. 제공된 SQL 스크립트 실행
```sql
source /path/to/stock_db_schema.sql
```

### 데이터베이스 연결 설정 수정
`stock_analyzer.py` 파일의 다음 부분을 수정:
```python
self.db_config = {
    'host': 'localhost',
    'user': 'root',           # MySQL 사용자명
    'password': 'your_password',  # MySQL 비밀번호
    'database': 'stock_db'
}
```

## 3. 프로그램 실행

### 파일 준비
1. `stock_analyzer.py` - 메인 프로그램
2. `stock_analyzer.ui` - UI 파일 (같은 폴더에 위치)

### 실행
```bash
python stock_analyzer.py
```

## 4. 사용 방법

### 주식 분석하기
1. **종목 코드 입력**: 분석할 종목의 코드 입력 (예: 005930)
2. **기간 선택**: 드롭다운에서 분석 기간 선택 (1년~10년)
3. **분석 시작**: 녹색 "분석 시작" 버튼 클릭

### 실시간 데이터 수집
프로그램은 다음 순서로 데이터를 가져옵니다:
1. **데이터베이스 확인**: 기존 저장된 데이터 확인
2. **Yahoo Finance**: 글로벌 및 한국 주식 데이터 (종목코드.KS 또는 .KQ)
3. **네이버 금융**: Yahoo에서 실패 시 네이버 금융에서 수집

### 결과 확인
- **차트**: 주가, 9일 이동평균, 22일 이동평균선 표시
- **테이블**: 최근 30일간의 상세 데이터
- **통계 정보**: 현재가, 변동률, 최고/최저가, 52주 최고/최저가 등
- **상태바**: 실시간 진행 상황 표시

### 데이터 저장
- **자동 저장 제안**: 실시간 데이터 수집 후 자동으로 저장 여부 확인
- **수동 저장**: "DB 저장" 버튼으로 언제든 저장 가능

## 5. Qt Designer 사용하기 (UI 수정)

### Qt Designer 실행
```bash
designer
# 또는
python -m PyQt5.uic.pyuic5
```

### UI 파일 수정
1. Qt Designer에서 `stock_analyzer.ui` 열기
2. 원하는 대로 UI 수정
3. 저장

## 6. 실제 주가 데이터 연동

웹사이트 스크랩하였음


## 7. 문제 해결

### PyQt5 ImportError
```bash
pip uninstall PyQt5
pip install PyQt5==5.15.7
```

### MySQL 연결 오류
- MySQL 서비스 실행 확인
- 방화벽 설정 확인
- 사용자 권한 확인

### 한글 깨짐 문제
- MySQL 문자셋을 utf8mb4로 설정
- 파이썬 파일 인코딩 확인 (UTF-8)

## 8. 주요 종목 코드 참고

### KOSPI 주요 종목
- 005930: 삼성전자
- 000660: SK하이닉스
- 005490: POSCO
- 005380: 현대차
- 000270: 기아
- 068270: 셀트리온
- 051910: LG화학
- 006400: 삼성SDI
- 035420: NAVER
- 105560: KB금융
- 055550: 신한지주
- 096770: SK이노베이션

### KOSDAQ 주요 종목
- 247540: 에코프로비엠
- 086520: 에코프로
- 373220: LG에너지솔루션
- 357780: 솔브레인
- 393890: 엔씨소프트

### 미국 주식 (Yahoo Finance)
- AAPL: Apple
- MSFT: Microsoft
- GOOGL: Alphabet (Google)
- AMZN: Amazon
- TSLA: Tesla
- NVDA: NVIDIA
