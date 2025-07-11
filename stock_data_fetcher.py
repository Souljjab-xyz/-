import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time

class StockDataFetcher:
    """실시간 주가 데이터를 가져오는 클래스"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_from_yahoo(self, symbol, period='1y'):
        """Yahoo Finance에서 데이터 가져오기"""
        try:
            # 한국 주식은 .KS, .KQ 접미사 사용
            if symbol.isdigit():  # 한국 종목코드인 경우
                ticker_symbol = f"{symbol}.KS"
                ticker = yf.Ticker(ticker_symbol)
                
                # KOSDAQ 종목인 경우 .KQ로 재시도
                hist = ticker.history(period=period)
                if hist.empty:
                    ticker_symbol = f"{symbol}.KQ"
                    ticker = yf.Ticker(ticker_symbol)
                    hist = ticker.history(period=period)
            else:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)
            
            if not hist.empty:
                # 컬럼명 변경
                hist = hist.rename(columns={
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                })
                return hist[['open', 'high', 'low', 'close', 'volume']]
            else:
                return None
                
        except Exception as e:
            print(f"Yahoo Finance 오류: {e}")
            return None
    
    def fetch_from_naver(self, symbol, years=1):
        """네이버 금융에서 데이터 가져오기"""
        try:
            # 전체 페이지 수 확인
            url = f"https://finance.naver.com/item/sise_day.nhn?code={symbol}"
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 페이지 수 계산
            pg_last = soup.find('td', class_='pgRR')
            if pg_last:
                last_page = int(pg_last.find('a')['href'].split('=')[-1])
            else:
                last_page = 1
            
            # 데이터 수집
            df_list = []
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * years)
            
            for page in range(1, min(last_page + 1, 100)):  # 최대 100페이지
                url = f"https://finance.naver.com/item/sise_day.nhn?code={symbol}&page={page}"
                response = requests.get(url, headers=self.headers)
                
                # pandas로 테이블 파싱
                tables = pd.read_html(response.text, encoding='cp949')
                if tables:
                    df = tables[0].dropna()
                    df_list.append(df)
                
                time.sleep(0.1)  # 요청 간격 조절
                
                # 날짜 확인
                if not df.empty:
                    last_date = pd.to_datetime(df.iloc[-1]['날짜'])
                    if last_date < start_date:
                        break
            
            if df_list:
                # 전체 데이터 결합
                all_data = pd.concat(df_list, ignore_index=True)
                all_data['날짜'] = pd.to_datetime(all_data['날짜'])
                all_data = all_data.set_index('날짜')
                all_data = all_data.sort_index()
                
                # 컬럼명 변경
                all_data = all_data.rename(columns={
                    '종가': 'close',
                    '시가': 'open',
                    '고가': 'high',
                    '저가': 'low',
                    '거래량': 'volume'
                })
                
                # 필요한 기간만 필터링
                all_data = all_data[all_data.index >= start_date]
                
                return all_data[['open', 'high', 'low', 'close', 'volume']]
            
            return None
            
        except Exception as e:
            print(f"네이버 금융 오류: {e}")
            return None
    
    def fetch_from_krx(self, symbol, start_date, end_date):
        """한국거래소(KRX)에서 데이터 가져오기"""
        try:
            # KRX API 엔드포인트
            url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
            
            # 요청 파라미터
            params = {
                'bld': 'dbms/MDC/STAT/standard/MDCSTAT01701',
                'locale': 'ko_KR',
                'isuCd': symbol,
                'isuCd2': symbol,
                'strtDd': start_date.strftime('%Y%m%d'),
                'endDd': end_date.strftime('%Y%m%d'),
                'adjStkPrc_check': 'Y',
                'adjStkPrc': '2',
                'share': '1',
                'money': '1',
                'csvxls_isNo': 'false'
            }
            
            response = requests.post(url, data=params, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                if 'output' in data:
                    df = pd.DataFrame(data['output'])
                    df['TRD_DD'] = pd.to_datetime(df['TRD_DD'])
                    df = df.set_index('TRD_DD')
                    
                    # 컬럼명 변경
                    df = df.rename(columns={
                        'TDD_OPNPRC': 'open',
                        'TDD_HGPRC': 'high',
                        'TDD_LWPRC': 'low',
                        'TDD_CLSPRC': 'close',
                        'ACC_TRDVOL': 'volume'
                    })
                    
                    # 숫자 형식으로 변환
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = pd.to_numeric(df[col].str.replace(',', ''))
                    
                    return df[['open', 'high', 'low', 'close', 'volume']]
            
            return None
            
        except Exception as e:
            print(f"KRX API 오류: {e}")
            return None
    
    def get_stock_data(self, symbol, years=1):
        """
        여러 소스에서 주가 데이터 가져오기
        우선순위: Yahoo Finance -> 네이버 금융 -> KRX
        """
        print(f"{symbol} 데이터 수집 중...")
        
        # 1. Yahoo Finance 시도
        data = self.fetch_from_yahoo(symbol, f"{years}y")
        if data is not None and not data.empty:
            print("Yahoo Finance에서 데이터 수집 완료")
            return data
        
        # 2. 네이버 금융 시도
        data = self.fetch_from_naver(symbol, years)
        if data is not None and not data.empty:
            print("네이버 금융에서 데이터 수집 완료")
            return data
        
        # 3. KRX 시도
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * years)
        data = self.fetch_from_krx(symbol, start_date, end_date)
        if data is not None and not data.empty:
            print("KRX에서 데이터 수집 완료")
            return data
        
        print("데이터 수집 실패")
        return None
    
    def save_to_mysql(self, data, symbol, connection):
        """MySQL 데이터베이스에 저장"""
        cursor = connection.cursor()
        
        try:
            # 기존 데이터 삭제
            cursor.execute("DELETE FROM stock_prices WHERE symbol = %s", (symbol,))
            
            # 새 데이터 삽입
            insert_query = """
            INSERT INTO stock_prices 
            (symbol, date, open_price, high_price, low_price, close_price, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            for date, row in data.iterrows():
                cursor.execute(insert_query, (
                    symbol,
                    date.date(),
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume'])
                ))
            
            connection.commit()
            print(f"{len(data)}개 레코드 저장 완료")
            
        except Exception as e:
            connection.rollback()
            print(f"저장 오류: {e}")
            raise


# 사용 예시
if __name__ == "__main__":
    # 필요한 패키지 설치
    # pip install yfinance beautifulsoup4 requests pandas
    
    fetcher = StockDataFetcher()
    
    # 삼성전자 1년치 데이터 가져오기
    data = fetcher.get_stock_data('005930', years=1)
    
    if data is not None:
        print("\n최근 5일 데이터:")
        print(data.tail())
        
        # 이동평균 계산
        data['MA9'] = data['close'].rolling(window=9).mean()
        data['MA22'] = data['close'].rolling(window=22).mean()
        
        print("\n이동평균 포함:")
        print(data[['close', 'MA9', 'MA22']].tail())