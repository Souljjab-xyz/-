import sys
import mysql.connector
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5 import uic
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import time

# UI 파일 로드
form_class = uic.loadUiType("stock_analyzer.ui")[0]

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
                return hist[['close']]  # 종가만 반환
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
                all_data = all_data.rename(columns={'종가': 'close'})
                
                # 필요한 기간만 필터링
                all_data = all_data[all_data.index >= start_date]
                
                return all_data[['close']]
            
            return None
            
        except Exception as e:
            print(f"네이버 금융 오류: {e}")
            return None

class DataFetchThread(QThread):
    """데이터 수집을 위한 별도 스레드"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, symbol, years):
        super().__init__()
        self.symbol = symbol
        self.years = years
        self.fetcher = StockDataFetcher()
    
    def run(self):
        try:
            self.progress.emit("Yahoo Finance에서 데이터 수집 중...")
            data = self.fetcher.fetch_from_yahoo(self.symbol, f"{self.years}y")
            
            if data is None or data.empty:
                self.progress.emit("네이버 금융에서 데이터 수집 중...")
                data = self.fetcher.fetch_from_naver(self.symbol, self.years)
            
            if data is not None and not data.empty:
                self.finished.emit(data)
            else:
                self.error.emit("데이터를 가져올 수 없습니다.")
                
        except Exception as e:
            self.error.emit(str(e))

class StockAnalyzer(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle("주식 분석 프로그램")
        
        # MySQL 연결 설정
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': 'your_password',
            'database': 'stock_db'
        }
        
        # UI 요소 초기화
        self.init_ui()
        
        # 시그널 연결
        self.btnAnalyze.clicked.connect(self.analyze_stock)
        self.btnSaveData.clicked.connect(self.save_to_db)
        
        # 상태바 설정
        self.statusBar().showMessage("준비됨")
        
    def init_ui(self):
        # 년도 선택 콤보박스 초기화
        self.cmbYears.addItems(['1년', '2년', '3년', '5년', '10년'])
        
        # matplotlib Figure 설정
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.chartLayout.addWidget(self.canvas)
        
        # 테이블 위젯 설정
        self.tableWidget.setColumnCount(5)
        self.tableWidget.setHorizontalHeaderLabels(['날짜', '종가', '9일 평균', '22일 평균', '변동률(%)'])
        
        # 프로그레스 바 추가
        self.progress_bar = QProgressBar()
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.progress_bar.setVisible(False)
        
    def connect_db(self):
        """MySQL 데이터베이스 연결"""
        try:
            self.conn = mysql.connector.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            
            # 테이블 존재 확인 및 생성
            self.create_tables_if_not_exists()
            
            return True
        except mysql.connector.Error as err:
            QMessageBox.critical(self, "DB 연결 오류", f"데이터베이스 연결 실패: {err}")
            return False
    
    def create_tables_if_not_exists(self):
        """필요한 테이블이 없으면 생성"""
        try:
            # stocks 테이블 생성
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    symbol VARCHAR(20) PRIMARY KEY,
                    name VARCHAR(100),
                    market VARCHAR(20),
                    sector VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # stock_prices 테이블 생성
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_prices (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    date DATE NOT NULL,
                    close_price DECIMAL(10, 2) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_symbol_date (symbol, date),
                    INDEX idx_symbol_date (symbol, date)
                )
            """)
            
            self.conn.commit()
        except Exception as e:
            print(f"테이블 생성 오류: {e}")
    
    def get_stock_data_from_db(self, symbol, years):
        """데이터베이스에서 주식 데이터 조회"""
        if not self.connect_db():
            return None
        
        try:
            # 시작 날짜 계산
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * years)
            
            query = """
            SELECT date, close_price 
            FROM stock_prices 
            WHERE symbol = %s AND date >= %s 
            ORDER BY date
            """
            
            self.cursor.execute(query, (symbol, start_date))
            data = self.cursor.fetchall()
            
            if data:
                # DataFrame으로 변환
                df = pd.DataFrame(data, columns=['date', 'close'])
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                return df
            
            return None
            
        except Exception as e:
            print(f"DB 조회 오류: {e}")
            return None
        finally:
            self.conn.close()
    
    def analyze_stock(self):
        """주식 분석 실행"""
        symbol = self.lineEditSymbol.text().strip()
        if not symbol:
            QMessageBox.warning(self, "입력 오류", "종목 코드를 입력해주세요.")
            return
        
        # 선택된 년도 가져오기
        years_text = self.cmbYears.currentText()
        years = int(years_text.replace('년', ''))
        
        # UI 비활성화
        self.btnAnalyze.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 무한 진행
        
        # 먼저 DB에서 확인
        self.statusBar().showMessage("데이터베이스 확인 중...")
        db_data = self.get_stock_data_from_db(symbol, years)
        
        if db_data is not None and len(db_data) > 100:  # 충분한 데이터가 있으면
            self.statusBar().showMessage("데이터베이스에서 데이터 로드 완료")
            self.process_data(db_data, symbol)
        else:
            # 실시간 데이터 수집
            self.statusBar().showMessage("실시간 데이터 수집 중...")
            self.data_thread = DataFetchThread(symbol, years)
            self.data_thread.finished.connect(lambda data: self.on_data_fetched(data, symbol))
            self.data_thread.progress.connect(self.statusBar().showMessage)
            self.data_thread.error.connect(self.on_fetch_error)
            self.data_thread.start()
    
    def on_data_fetched(self, data, symbol):
        """데이터 수집 완료 처리"""
        self.progress_bar.setVisible(False)
        self.btnAnalyze.setEnabled(True)
        
        if data is not None:
            self.statusBar().showMessage("데이터 수집 완료")
            self.process_data(data, symbol)
            
            # DB에 저장할지 묻기
            reply = QMessageBox.question(self, '데이터 저장', 
                                       '수집한 데이터를 데이터베이스에 저장하시겠습니까?',
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.save_fetched_data(data, symbol)
    
    def on_fetch_error(self, error_msg):
        """데이터 수집 오류 처리"""
        self.progress_bar.setVisible(False)
        self.btnAnalyze.setEnabled(True)
        self.statusBar().showMessage("데이터 수집 실패")
        QMessageBox.critical(self, "오류", f"데이터 수집 실패: {error_msg}")
    
    def process_data(self, data, symbol):
        """데이터 처리 및 표시"""
        # DataFrame 준비
        self.df = data.copy()
        
        # 이동평균 계산
        self.df['ma9'] = self.df['close'].rolling(window=9).mean()
        self.df['ma22'] = self.df['close'].rolling(window=22).mean()
        
        # 변동률 계산
        self.df['change_pct'] = self.df['close'].pct_change() * 100
        
        # 차트 그리기
        self.plot_chart(symbol)
        
        # 테이블 업데이트
        self.update_table()
        
        # 통계 정보 표시
        self.show_statistics()
    
    def plot_chart(self, symbol):
        """주가 차트 그리기"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # 주가 및 이동평균선 그리기
        ax.plot(self.df.index, self.df['close'], label='종가', linewidth=1.5, color='black')
        ax.plot(self.df.index, self.df['ma9'], label='9일 평균', alpha=0.7, color='red')
        ax.plot(self.df.index, self.df['ma22'], label='22일 평균', alpha=0.7, color='blue')
        
        # 차트 설정
        ax.set_title(f'{symbol} 주가 차트', fontsize=14, fontweight='bold')
        ax.set_xlabel('날짜')
        ax.set_ylabel('가격 (원)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # x축 날짜 포맷 설정
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        # 차트 배경색
        ax.set_facecolor('#f0f0f0')
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def update_table(self):
        """테이블 위젯 업데이트"""
        # 최근 30일 데이터만 표시
        recent_data = self.df.tail(30)
        
        self.tableWidget.setRowCount(len(recent_data))
        
        for i, (date, row) in enumerate(recent_data.iterrows()):
            # 날짜
            date_item = QTableWidgetItem(date.strftime('%Y-%m-%d'))
            date_item.setTextAlignment(Qt.AlignCenter)
            self.tableWidget.setItem(i, 0, date_item)
            
            # 종가
            close_item = QTableWidgetItem(f"{row['close']:,.0f}")
            close_item.setTextAlignment(Qt.AlignRight)
            self.tableWidget.setItem(i, 1, close_item)
            
            # 9일 평균
            if not pd.isna(row['ma9']):
                ma9_item = QTableWidgetItem(f"{row['ma9']:,.0f}")
                ma9_item.setTextAlignment(Qt.AlignRight)
                self.tableWidget.setItem(i, 2, ma9_item)
            else:
                self.tableWidget.setItem(i, 2, QTableWidgetItem("-"))
            
            # 22일 평균
            if not pd.isna(row['ma22']):
                ma22_item = QTableWidgetItem(f"{row['ma22']:,.0f}")
                ma22_item.setTextAlignment(Qt.AlignRight)
                self.tableWidget.setItem(i, 3, ma22_item)
            else:
                self.tableWidget.setItem(i, 3, QTableWidgetItem("-"))
            
            # 변동률
            if not pd.isna(row['change_pct']):
                change_item = QTableWidgetItem(f"{row['change_pct']:.2f}%")
                change_item.setTextAlignment(Qt.AlignRight)
                if row['change_pct'] > 0:
                    change_item.setForeground(QColor('red'))
                elif row['change_pct'] < 0:
                    change_item.setForeground(QColor('blue'))
                self.tableWidget.setItem(i, 4, change_item)
            else:
                self.tableWidget.setItem(i, 4, QTableWidgetItem("-"))
        
        self.tableWidget.resizeColumnsToContents()
    
    def show_statistics(self):
        """통계 정보 표시"""
        current_price = self.df['close'].iloc[-1]
        start_price = self.df['close'].iloc[0]
        total_change = ((current_price - start_price) / start_price) * 100
        
        max_price = self.df['close'].max()
        min_price = self.df['close'].min()
        avg_price = self.df['close'].mean()
        
        # 52주 최고/최저
        if len(self.df) >= 252:  # 1년 이상 데이터
            weeks_52 = self.df.tail(252)
            high_52w = weeks_52['close'].max()
            low_52w = weeks_52['close'].min()
            stats_52w = f"\n52주 최고: {high_52w:,.0f}원\n52주 최저: {low_52w:,.0f}원"
        else:
            stats_52w = ""
        
        stats_text = f"""현재가: {current_price:,.0f}원
시작가: {start_price:,.0f}원
총 변동률: {total_change:.2f}%

최고가: {max_price:,.0f}원
최저가: {min_price:,.0f}원
평균가: {avg_price:,.0f}원{stats_52w}

데이터 기간: {self.df.index[0].strftime('%Y-%m-%d')} ~ {self.df.index[-1].strftime('%Y-%m-%d')}
거래일 수: {len(self.df)}일"""
        
        self.textEditStats.setPlainText(stats_text)
    
    def save_fetched_data(self, data, symbol):
        """수집한 데이터를 DB에 저장"""
        if not self.connect_db():
            return
        
        try:
            # 종목 정보 저장 (없으면)
            self.cursor.execute("""
                INSERT IGNORE INTO stocks (symbol, name) VALUES (%s, %s)
            """, (symbol, symbol))
            
            # 기존 데이터 삭제
            self.cursor.execute("DELETE FROM stock_prices WHERE symbol = %s", (symbol,))
            
            # 새 데이터 삽입
            insert_query = """
                INSERT INTO stock_prices (symbol, date, close_price) 
                VALUES (%s, %s, %s)
            """
            
            data_to_insert = [(symbol, date.date(), float(row['close'])) 
                            for date, row in data.iterrows()]
            
            self.cursor.executemany(insert_query, data_to_insert)
            self.conn.commit()
            
            self.statusBar().showMessage(f"{len(data_to_insert)}개 데이터 저장 완료")
            
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "저장 오류", f"데이터 저장 실패: {e}")
        finally:
            self.conn.close()
    
    def save_to_db(self):
        """현재 분석 데이터를 데이터베이스에 저장"""
        if not hasattr(self, 'df') or self.df is None:
            QMessageBox.warning(self, "저장 오류", "분석할 데이터가 없습니다.")
            return
        
        symbol = self.lineEditSymbol.text().strip()
        self.save_fetched_data(self.df[['close']], symbol)
        QMessageBox.information(self, "저장 완료", "데이터가 저장되었습니다.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 스타일 설정
    app.setStyle('Fusion')
    
    window = StockAnalyzer()
    window.show()
    sys.exit(app.exec_())