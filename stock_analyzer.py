# -*- coding: utf-8 -*-
import sys
import os
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
import matplotlib.font_manager as fm
import platform
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import time
import json
from collections import defaultdict

# 한글 폰트 설정 함수
def setup_korean_font():
    """운영체제별 한글 폰트 자동 설정"""
    system = platform.system()
    
    if system == 'Windows':
        font_names = ['Malgun Gothic', 'NanumGothic', '맑은 고딕', '나눔고딕']
    elif system == 'Darwin':
        font_names = ['AppleGothic', 'Apple SD Gothic Neo', 'NanumGothic', 'Arial Unicode MS']
    else:
        font_names = ['NanumGothic', 'UnDotum', 'DejaVu Sans', 'Liberation Sans']
    
    for font_name in font_names:
        try:
            plt.rcParams['font.family'] = font_name
            plt.rcParams['axes.unicode_minus'] = False
            return True
        except:
            continue
    
    # 폰트를 찾지 못한 경우 기본 폰트 사용
    plt.rcParams['axes.unicode_minus'] = False
    return False

# 프로그램 시작 시 한글 폰트 설정
setup_korean_font()

# UI 파일 로드
form_class = uic.loadUiType("stock_analyzer.ui")[0]

class ExchangeRateManager:
    """환율 관리 클래스"""
    
    def __init__(self):
        self.usd_to_krw = None
        self.last_update = None
        self.update_exchange_rate()
    
    def update_exchange_rate(self):
        """실시간 환율 업데이트"""
        try:
            # Yahoo Finance에서 USD/KRW 환율 가져오기
            ticker = yf.Ticker("USDKRW=X")
            data = ticker.history(period="1d")
            if not data.empty:
                self.usd_to_krw = data['Close'].iloc[-1]
                self.last_update = datetime.now()
                return self.usd_to_krw
        except:
            pass
        
        # 백업: 고정 환율 사용
        if self.usd_to_krw is None:
            self.usd_to_krw = 1350.0  # 기본값
        
        return self.usd_to_krw
    
    def convert_to_krw(self, usd_amount):
        """달러를 원화로 변환"""
        if self.usd_to_krw is None:
            self.update_exchange_rate()
        return usd_amount * self.usd_to_krw
    
    def get_rate_info(self):
        """환율 정보 문자열 반환"""
        if self.last_update:
            time_str = self.last_update.strftime("%H:%M")
            return f"1 USD = {self.usd_to_krw:,.0f} KRW ({time_str} 기준)"
        return f"1 USD = {self.usd_to_krw:,.0f} KRW"

class TechnicalIndicators:
    """기술적 지표 계산 클래스"""
    
    @staticmethod
    def calculate_rsi(data, period=14):
        """RSI (상대강도지수) 계산"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(data, fast=12, slow=26, signal=9):
        """MACD 계산"""
        ema_fast = data.ewm(span=fast).mean()
        ema_slow = data.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_bollinger_bands(data, period=20, std_dev=2):
        """볼린저 밴드 계산"""
        middle_band = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        return upper_band, middle_band, lower_band
    
    @staticmethod
    def calculate_stochastic(high, low, close, period=14, smooth_k=3, smooth_d=3):
        """스토캐스틱 계산"""
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        k_percent = k_percent.rolling(window=smooth_k).mean()
        d_percent = k_percent.rolling(window=smooth_d).mean()
        return k_percent, d_percent

class AlertManager(QObject):
    """알림 관리 클래스"""
    alert_triggered = pyqtSignal(str, str)  # symbol, message
    
    def __init__(self):
        super().__init__()
        self.alerts = []
        self.load_alerts()
    
    def add_alert(self, symbol, alert_type, condition, value):
        """알림 추가"""
        alert = {
            'symbol': symbol,
            'type': alert_type,
            'condition': condition,
            'value': value,
            'active': True,
            'created': datetime.now().isoformat()
        }
        self.alerts.append(alert)
        self.save_alerts()
        return alert
    
    def remove_alert(self, index):
        """알림 제거"""
        if 0 <= index < len(self.alerts):
            del self.alerts[index]
            self.save_alerts()
    
    def check_alerts(self, symbol, current_price, indicators):
        """알림 조건 확인"""
        for alert in self.alerts:
            if alert['symbol'] == symbol and alert['active']:
                triggered = False
                message = ""
                
                if alert['type'] == 'price':
                    if alert['condition'] == '이상' and current_price >= alert['value']:
                        triggered = True
                        message = f"{symbol} 현재가({current_price:,.0f})가 목표가({alert['value']:,.0f}) 도달"
                    elif alert['condition'] == '이하' and current_price <= alert['value']:
                        triggered = True
                        message = f"{symbol} 현재가({current_price:,.0f})가 목표가({alert['value']:,.0f}) 도달"
                
                elif alert['type'] == 'golden_cross' and 'ma9' in indicators and 'ma22' in indicators:
                    if len(indicators['ma9']) >= 2:
                        prev_diff = indicators['ma9'].iloc[-2] - indicators['ma22'].iloc[-2]
                        curr_diff = indicators['ma9'].iloc[-1] - indicators['ma22'].iloc[-1]
                        if prev_diff < 0 and curr_diff > 0:
                            triggered = True
                            message = f"{symbol} 골든크로스 발생 (9일선이 22일선 상향 돌파)"
                
                elif alert['type'] == 'dead_cross' and 'ma9' in indicators and 'ma22' in indicators:
                    if len(indicators['ma9']) >= 2:
                        prev_diff = indicators['ma9'].iloc[-2] - indicators['ma22'].iloc[-2]
                        curr_diff = indicators['ma9'].iloc[-1] - indicators['ma22'].iloc[-1]
                        if prev_diff > 0 and curr_diff < 0:
                            triggered = True
                            message = f"{symbol} 데드크로스 발생 (9일선이 22일선 하향 돌파)"
                
                if triggered:
                    alert['active'] = False  # 한 번만 알림
                    self.alert_triggered.emit(symbol, message)
                    self.save_alerts()
    
    def save_alerts(self):
        """알림 설정 저장"""
        try:
            with open('alerts.json', 'w', encoding='utf-8') as f:
                json.dump(self.alerts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"알림 저장 오류: {e}")
    
    def load_alerts(self):
        """알림 설정 로드"""
        try:
            with open('alerts.json', 'r', encoding='utf-8') as f:
                self.alerts = json.load(f)
        except:
            self.alerts = []

class Portfolio:
    """포트폴리오 관리 클래스"""
    
    def __init__(self):
        self.holdings = {}
        self.transactions = []
        self.load_portfolio()
    
    def add_stock(self, symbol, quantity, price, date=None):
        """주식 매수"""
        if date is None:
            date = datetime.now()
        
        if symbol not in self.holdings:
            self.holdings[symbol] = {
                'quantity': 0,
                'avg_price': 0,
                'total_cost': 0
            }
        
        holding = self.holdings[symbol]
        total_cost = holding['total_cost'] + (quantity * price)
        total_quantity = holding['quantity'] + quantity
        
        holding['quantity'] = total_quantity
        holding['avg_price'] = total_cost / total_quantity
        holding['total_cost'] = total_cost
        
        transaction = {
            'date': date.isoformat(),
            'symbol': symbol,
            'type': 'buy',
            'quantity': quantity,
            'price': price
        }
        self.transactions.append(transaction)
        
        self.save_portfolio()
    
    def sell_stock(self, symbol, quantity, price, date=None):
        """주식 매도"""
        if date is None:
            date = datetime.now()
        
        if symbol in self.holdings and self.holdings[symbol]['quantity'] >= quantity:
            holding = self.holdings[symbol]
            holding['quantity'] -= quantity
            holding['total_cost'] = holding['quantity'] * holding['avg_price']
            
            if holding['quantity'] == 0:
                del self.holdings[symbol]
            
            transaction = {
                'date': date.isoformat(),
                'symbol': symbol,
                'type': 'sell',
                'quantity': quantity,
                'price': price
            }
            self.transactions.append(transaction)
            
            self.save_portfolio()
            return True
        return False
    
    def calculate_returns(self, current_prices, exchange_manager):
        """수익률 계산 (환율 적용)"""
        results = {}
        total_cost_krw = 0
        total_value_krw = 0
        
        for symbol, holding in self.holdings.items():
            if symbol in current_prices:
                current_price = current_prices[symbol]
                current_value = holding['quantity'] * current_price
                profit = current_value - holding['total_cost']
                profit_rate = (profit / holding['total_cost']) * 100 if holding['total_cost'] > 0 else 0
                
                # 환율 적용
                is_us_stock = not symbol.isdigit()
                if is_us_stock:
                    current_value_krw = exchange_manager.convert_to_krw(current_value)
                    total_cost_krw += exchange_manager.convert_to_krw(holding['total_cost'])
                    total_value_krw += current_value_krw
                else:
                    current_value_krw = current_value
                    total_cost_krw += holding['total_cost']
                    total_value_krw += current_value
                
                results[symbol] = {
                    'quantity': holding['quantity'],
                    'avg_price': holding['avg_price'],
                    'current_price': current_price,
                    'total_cost': holding['total_cost'],
                    'current_value': current_value,
                    'current_value_krw': current_value_krw,
                    'profit': profit,
                    'profit_rate': profit_rate,
                    'is_us_stock': is_us_stock
                }
        
        total_profit_krw = total_value_krw - total_cost_krw
        total_profit_rate = (total_profit_krw / total_cost_krw) * 100 if total_cost_krw > 0 else 0
        
        return results, {
            'total_cost_krw': total_cost_krw,
            'total_value_krw': total_value_krw,
            'total_profit_krw': total_profit_krw,
            'total_profit_rate': total_profit_rate
        }
    
    def save_portfolio(self):
        """포트폴리오 저장"""
        data = {
            'holdings': self.holdings,
            'transactions': self.transactions
        }
        try:
            with open('portfolio.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"포트폴리오 저장 오류: {e}")
    
    def load_portfolio(self):
        """포트폴리오 로드"""
        try:
            with open('portfolio.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.holdings = data.get('holdings', {})
                self.transactions = data.get('transactions', [])
        except:
            self.holdings = {}
            self.transactions = []

class StockDataFetcher:
    """실시간 주가 데이터를 가져오는 클래스"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_from_yahoo(self, symbol, period='1y'):
        """Yahoo Finance에서 데이터 가져오기"""
        try:
            if symbol.isdigit():  # 한국 종목코드인 경우
                ticker_symbol = f"{symbol}.KS"
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(period=period)
                if hist.empty:
                    ticker_symbol = f"{symbol}.KQ"
                    ticker = yf.Ticker(ticker_symbol)
                    hist = ticker.history(period=period)
            else:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)
            
            if not hist.empty:
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
        self.setWindowTitle("주식 분석 프로그램 Pro - 글로벌 에디션")
        
        # 창 크기를 화면의 80%로 설정
        screen = QApplication.desktop().screenGeometry()
        self.setGeometry(
            int(screen.width() * 0.1),
            int(screen.height() * 0.1),
            int(screen.width() * 0.8),
            int(screen.height() * 0.8)
        )
        
        # 다크 테마 스타일 적용
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0a0e27;
            }
            QGroupBox {
                background-color: #151a3a;
                border: 2px solid #2d3561;
                border-radius: 10px;
                margin-top: 10px;
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 15px 0 15px;
                background-color: #151a3a;
                color: #00d4ff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #1e2444;
                border: 2px solid #2d3561;
                border-radius: 6px;
                padding: 8px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #00d4ff;
                background-color: #252b4f;
            }
            QPushButton {
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
                min-width: 100px;
                border: none;
            }
            QPushButton:hover {
                transform: translateY(-2px);
            }
            QTableWidget {
                background-color: #151a3a;
                alternate-background-color: #1e2444;
                border: 2px solid #2d3561;
                gridline-color: #2d3561;
                color: #ffffff;
                selection-background-color: #00d4ff;
                border-radius: 8px;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #1e2444;
                color: #00d4ff;
                padding: 10px;
                border: none;
                font-weight: bold;
                font-size: 13px;
            }
            QTextEdit {
                background-color: #151a3a;
                border: 2px solid #2d3561;
                border-radius: 8px;
                color: #ffffff;
                padding: 10px;
                font-size: 13px;
            }
            QTabWidget::pane {
                background-color: #151a3a;
                border: 2px solid #2d3561;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #1e2444;
                color: #a0a0a0;
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #00d4ff;
                color: #0a0e27;
            }
            QTabBar::tab:hover {
                background-color: #2d3561;
                color: #ffffff;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 10px;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 2px solid #2d3561;
                background-color: #1e2444;
            }
            QCheckBox::indicator:checked {
                background-color: #00d4ff;
                border: 2px solid #00d4ff;
                image: url(check.png);
            }
            QProgressBar {
                border: 2px solid #2d3561;
                border-radius: 6px;
                background-color: #1e2444;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #00d4ff;
                border-radius: 4px;
            }
            QStatusBar {
                background-color: #151a3a;
                color: #e0e0e0;
                border-top: 2px solid #2d3561;
                font-size: 12px;
            }
            QScrollBar:vertical {
                background-color: #1e2444;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #00d4ff;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #00a8cc;
            }
            QMessageBox {
                background-color: #151a3a;
                color: #ffffff;
            }
        """)
        
        # MySQL 연결 설정 (인증 플러그인 오류 해결)
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': 'your_password',
            'database': 'stock_db',
            'auth_plugin': 'mysql_native_password'  # 인증 플러그인 명시
        }
        
        # 관리자 객체 초기화
        self.alert_manager = AlertManager()
        self.portfolio = Portfolio()
        self.exchange_manager = ExchangeRateManager()
        self.current_prices = {}
        self.currency_symbols = {}  # 통화 기호 저장
        
        # UI 요소 초기화
        self.init_ui()
        
        # 시그널 연결
        self.connect_signals()
        
        # 상태바 설정
        self.statusBar().showMessage("준비됨")
        
        # 환율 정보 표시
        self.update_exchange_rate_display()
        
        # 포트폴리오 초기 로드
        self.update_portfolio_view()
        
    def init_ui(self):
        # 년도 선택 콤보박스 초기화
        self.cmbYears.addItems(['1년', '2년', '3년', '5년', '10년'])
        
        # 메인 차트 Figure 설정
        self.figure = Figure(figsize=(14, 10), facecolor='#0a0e27')
        self.canvas = FigureCanvas(self.figure)
        self.chartLayout.addWidget(self.canvas)
        
        # 포트폴리오 차트 설정
        self.portfolio_figure = Figure(figsize=(8, 6), facecolor='#0a0e27')
        self.portfolio_canvas = FigureCanvas(self.portfolio_figure)
        self.portfolioChartLayout.addWidget(self.portfolio_canvas)
        
        # 테이블 위젯 설정
        self.tableWidget.setColumnCount(5)
        self.tableWidget.setHorizontalHeaderLabels(['날짜', '종가', '9일 평균', '22일 평균', '변동률(%)'])
        
        # 기술적 지표 테이블
        self.indicatorTable.setColumnCount(2)
        self.indicatorTable.setHorizontalHeaderLabels(['지표', '값'])
        
        # 알림 테이블
        self.alertTable.setColumnCount(5)
        self.alertTable.setHorizontalHeaderLabels(['종목', '유형', '조건', '값', '상태'])
        
        # 포트폴리오 테이블
        self.portfolioTable.setColumnCount(8)
        self.portfolioTable.setHorizontalHeaderLabels(['종목', '수량', '평균단가', '현재가', '평가금액', '평가금액(원)', '손익', '수익률(%)'])
        
        # 프로그레스 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(15)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.progress_bar.setVisible(False)
        
        # 환율 정보 라벨
        self.exchange_label = QLabel("")
        self.exchange_label.setStyleSheet("color: #00d4ff; font-weight: bold; padding: 0 20px;")
        self.statusBar().addPermanentWidget(self.exchange_label)
        
        # 알림 타입 콤보박스
        self.cmbAlertType.addItems(['가격 알림', '골든크로스', '데드크로스'])
        
        # 기술적 지표 체크박스
        self.chkRSI.setChecked(True)
        self.chkMACD.setChecked(True)
        self.chkBollinger.setChecked(True)
        self.chkStochastic.setChecked(True)
        
        # 버튼 색상 설정
        self.btnAnalyze.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00ff88, stop:1 #00cc66);
                color: #ffffff;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00ffaa, stop:1 #00dd77);
            }
        """)
        
        self.btnSaveData.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0099ff, stop:1 #0066cc);
                color: #ffffff;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00aaff, stop:1 #0077dd);
            }
        """)
        
    def connect_signals(self):
        """시그널 연결"""
        self.btnAnalyze.clicked.connect(self.analyze_stock)
        self.btnSaveData.clicked.connect(self.save_to_db)
        self.btnAddAlert.clicked.connect(self.add_alert)
        self.btnRemoveAlert.clicked.connect(self.remove_alert)
        self.btnAddPortfolio.clicked.connect(self.add_to_portfolio)
        self.btnSellPortfolio.clicked.connect(self.sell_from_portfolio)
        self.btnRefreshPortfolio.clicked.connect(self.refresh_portfolio)
        
        # 체크박스 시그널 연결 (실시간 차트 업데이트)
        self.chkRSI.stateChanged.connect(self.update_chart)
        self.chkMACD.stateChanged.connect(self.update_chart)
        self.chkBollinger.stateChanged.connect(self.update_chart)
        self.chkStochastic.stateChanged.connect(self.update_chart)
        
        # 알림 시그널
        self.alert_manager.alert_triggered.connect(self.show_alert_notification)
        
        # 환율 업데이트 타이머 (30분마다)
        self.exchange_timer = QTimer()
        self.exchange_timer.timeout.connect(self.update_exchange_rate_display)
        self.exchange_timer.start(1800000)  # 30분
        
    def update_exchange_rate_display(self):
        """환율 정보 업데이트"""
        self.exchange_manager.update_exchange_rate()
        self.exchange_label.setText(self.exchange_manager.get_rate_info())
    
    def is_us_stock(self, symbol):
        """미국 주식 여부 확인"""
        return not symbol.isdigit()
    
    def get_currency_symbol(self, symbol):
        """통화 기호 반환"""
        if self.is_us_stock(symbol):
            return '$', 'USD'
        else:
            return '₩', 'KRW'
    
    def format_price(self, price, symbol, convert_to_krw=False):
        """가격 포맷팅"""
        currency, currency_code = self.get_currency_symbol(symbol)
        
        if currency == '$':
            if convert_to_krw:
                krw_price = self.exchange_manager.convert_to_krw(price)
                return f"₩{krw_price:,.0f}"
            else:
                return f"{currency}{price:,.2f}"
        else:
            return f"{currency}{price:,.0f}"
    
    def connect_db(self):
        """MySQL 데이터베이스 연결"""
        try:
            self.conn = mysql.connector.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            self.create_tables_if_not_exists()
            return True
        except mysql.connector.Error as err:
            # 인증 플러그인 오류 대응
            if "Authentication plugin" in str(err):
                QMessageBox.warning(self, "DB 연결 오류", 
                    "MySQL 인증 플러그인 오류입니다.\n"
                    "MySQL에서 다음 명령을 실행하세요:\n"
                    "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'your_password';")
            else:
                QMessageBox.critical(self, "DB 연결 오류", f"데이터베이스 연결 실패: {err}")
            return False
    
    def create_tables_if_not_exists(self):
        """필요한 테이블이 없으면 생성"""
        try:
            # stocks 테이블
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    symbol VARCHAR(20) PRIMARY KEY,
                    name VARCHAR(100),
                    market VARCHAR(20),
                    sector VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
            
            # stock_prices 테이블
            self.cursor.execute("""
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
                    INDEX idx_symbol_date (symbol, date)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
            
            self.conn.commit()
        except Exception as e:
            print(f"테이블 생성 오류: {e}")
    
    def analyze_stock(self):
        """주식 분석 실행"""
        symbol = self.lineEditSymbol.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "입력 오류", "종목 코드를 입력해주세요.")
            return
        
        years_text = self.cmbYears.currentText()
        years = int(years_text.replace('년', ''))
        
        # UI 비활성화
        self.btnAnalyze.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        # 데이터 수집 스레드 시작
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
            
            # 현재가 업데이트
            self.current_prices[symbol] = data['close'].iloc[-1]
            
            # 알림 확인
            indicators = {
                'ma9': self.df['ma9'],
                'ma22': self.df['ma22']
            }
            self.alert_manager.check_alerts(symbol, self.current_prices[symbol], indicators)
    
    def on_fetch_error(self, error_msg):
        """데이터 수집 오류 처리"""
        self.progress_bar.setVisible(False)
        self.btnAnalyze.setEnabled(True)
        self.statusBar().showMessage("데이터 수집 실패")
        QMessageBox.critical(self, "오류", f"데이터 수집 실패: {error_msg}")
    
    def process_data(self, data, symbol):
        """데이터 처리 및 표시"""
        self.df = data.copy()
        self.current_symbol = symbol
        
        # 이동평균 계산
        self.df['ma9'] = self.df['close'].rolling(window=9).mean()
        self.df['ma22'] = self.df['close'].rolling(window=22).mean()
        
        # 변동률 계산
        self.df['change_pct'] = self.df['close'].pct_change() * 100
        
        # 기술적 지표 계산
        self.calculate_technical_indicators()
        
        # 차트 그리기
        self.plot_charts(symbol)
        
        # 테이블 업데이트
        self.update_table()
        
        # 통계 정보 표시
        self.show_statistics()
        
        # 기술적 지표 표시
        self.show_technical_indicators()
    
    def calculate_technical_indicators(self):
        """기술적 지표 계산"""
        # RSI
        self.df['rsi'] = TechnicalIndicators.calculate_rsi(self.df['close'])
        
        # MACD
        macd, signal, histogram = TechnicalIndicators.calculate_macd(self.df['close'])
        self.df['macd'] = macd
        self.df['macd_signal'] = signal
        self.df['macd_histogram'] = histogram
        
        # 볼린저 밴드
        upper, middle, lower = TechnicalIndicators.calculate_bollinger_bands(self.df['close'])
        self.df['bb_upper'] = upper
        self.df['bb_middle'] = middle
        self.df['bb_lower'] = lower
        
        # 스토캐스틱 (high, low 데이터가 있는 경우)
        if 'high' in self.df.columns and 'low' in self.df.columns:
            k, d = TechnicalIndicators.calculate_stochastic(
                self.df['high'], self.df['low'], self.df['close']
            )
            self.df['stoch_k'] = k
            self.df['stoch_d'] = d
    
    def update_chart(self):
        """체크박스 변경 시 차트 업데이트"""
        if hasattr(self, 'current_symbol') and hasattr(self, 'df'):
            self.plot_charts(self.current_symbol)
    
    def plot_charts(self, symbol):
        """차트 그리기"""
        self.figure.clear()
        
        # 다크 테마 설정
        plt.style.use('dark_background')
        self.figure.patch.set_facecolor('#0a0e27')
        
        # 서브플롯 설정
        num_indicators = sum([self.chkRSI.isChecked(), self.chkMACD.isChecked(), 
                            self.chkStochastic.isChecked() and 'stoch_k' in self.df.columns])
        
        if num_indicators > 0:
            height_ratios = [3] + [1] * num_indicators
            gs = self.figure.add_gridspec(num_indicators + 1, 1, height_ratios=height_ratios, hspace=0.3)
            ax1 = self.figure.add_subplot(gs[0])
            indicator_idx = 1
        else:
            ax1 = self.figure.add_subplot(111)
        
        # 축 배경색 설정
        ax1.set_facecolor('#0a0e27')
        
        # 통화 기호 가져오기
        currency, currency_code = self.get_currency_symbol(symbol)
        
        # 메인 차트 (주가, 이동평균선, 볼린저 밴드)
        ax1.plot(self.df.index, self.df['close'], label='종가', linewidth=2.5, color='#ffffff')
        ax1.plot(self.df.index, self.df['ma9'], label='9일 평균', alpha=0.9, color='#ff6b6b', linewidth=2)
        ax1.plot(self.df.index, self.df['ma22'], label='22일 평균', alpha=0.9, color='#4ecdc4', linewidth=2)
        
        if self.chkBollinger.isChecked():
            ax1.plot(self.df.index, self.df['bb_upper'], '--', alpha=0.6, color='#95e1d3', label='볼린저 상단', linewidth=1.5)
            ax1.plot(self.df.index, self.df['bb_lower'], '--', alpha=0.6, color='#f38181', label='볼린저 하단', linewidth=1.5)
            ax1.fill_between(self.df.index, self.df['bb_upper'], self.df['bb_lower'], alpha=0.05, color='#dfe6e9')
        
        # 제목과 라벨
        title_text = f'{symbol} 주가 차트 ({currency_code})'
        if self.is_us_stock(symbol):
            krw_price = self.exchange_manager.convert_to_krw(self.df['close'].iloc[-1])
            title_text += f' - 현재가: {self.format_price(self.df["close"].iloc[-1], symbol)} (₩{krw_price:,.0f})'
        
        ax1.set_title(title_text, fontsize=18, fontweight='bold', color='#ffffff', pad=20)
        ax1.set_ylabel(f'가격 ({currency})', color='#ffffff', fontsize=14)
        ax1.legend(loc='upper left', framealpha=0.9, facecolor='#151a3a', edgecolor='#2d3561')
        ax1.grid(True, alpha=0.2, color='#2d3561', linestyle='-', linewidth=0.5)
        ax1.tick_params(colors='#e0e0e0', labelsize=12)
        
        # 축 테두리 색상
        for spine in ax1.spines.values():
            spine.set_edgecolor('#2d3561')
            spine.set_linewidth(2)
        
        # RSI 차트
        if self.chkRSI.isChecked():
            ax_rsi = self.figure.add_subplot(gs[indicator_idx])
            ax_rsi.set_facecolor('#0a0e27')
            ax_rsi.plot(self.df.index, self.df['rsi'], color='#a29bfe', linewidth=2)
            ax_rsi.axhline(y=70, color='#ff6b6b', linestyle='--', alpha=0.6, linewidth=1.5)
            ax_rsi.axhline(y=30, color='#6bcf7f', linestyle='--', alpha=0.6, linewidth=1.5)
            ax_rsi.fill_between(self.df.index, 30, 70, alpha=0.05, color='#636e72')
            ax_rsi.set_ylabel('RSI', color='#ffffff', fontsize=12)
            ax_rsi.set_ylim(0, 100)
            ax_rsi.grid(True, alpha=0.2, color='#2d3561', linestyle='-', linewidth=0.5)
            ax_rsi.tick_params(colors='#e0e0e0', labelsize=11)
            for spine in ax_rsi.spines.values():
                spine.set_edgecolor('#2d3561')
                spine.set_linewidth(2)
            indicator_idx += 1
        
        # MACD 차트
        if self.chkMACD.isChecked():
            ax_macd = self.figure.add_subplot(gs[indicator_idx])
            ax_macd.set_facecolor('#0a0e27')
            ax_macd.plot(self.df.index, self.df['macd'], label='MACD', color='#74b9ff', linewidth=2)
            ax_macd.plot(self.df.index, self.df['macd_signal'], label='Signal', color='#fd79a8', linewidth=2)
            ax_macd.bar(self.df.index, self.df['macd_histogram'], label='Histogram', alpha=0.4, color='#81ecec')
            ax_macd.set_ylabel('MACD', color='#ffffff', fontsize=12)
            ax_macd.legend(loc='upper left', framealpha=0.9, facecolor='#151a3a', edgecolor='#2d3561')
            ax_macd.grid(True, alpha=0.2, color='#2d3561', linestyle='-', linewidth=0.5)
            ax_macd.tick_params(colors='#e0e0e0', labelsize=11)
            for spine in ax_macd.spines.values():
                spine.set_edgecolor('#2d3561')
                spine.set_linewidth(2)
            indicator_idx += 1
        
        # 스토캐스틱 차트
        if self.chkStochastic.isChecked() and 'stoch_k' in self.df.columns:
            ax_stoch = self.figure.add_subplot(gs[indicator_idx])
            ax_stoch.set_facecolor('#0a0e27')
            ax_stoch.plot(self.df.index, self.df['stoch_k'], label='%K', color='#55efc4', linewidth=2)
            ax_stoch.plot(self.df.index, self.df['stoch_d'], label='%D', color='#ff7675', linewidth=2)
            ax_stoch.axhline(y=80, color='#ff6b6b', linestyle='--', alpha=0.6, linewidth=1.5)
            ax_stoch.axhline(y=20, color='#6bcf7f', linestyle='--', alpha=0.6, linewidth=1.5)
            ax_stoch.set_ylabel('Stochastic', color='#ffffff', fontsize=12)
            ax_stoch.set_ylim(0, 100)
            ax_stoch.legend(loc='upper left', framealpha=0.9, facecolor='#151a3a', edgecolor='#2d3561')
            ax_stoch.grid(True, alpha=0.2, color='#2d3561', linestyle='-', linewidth=0.5)
            ax_stoch.tick_params(colors='#e0e0e0', labelsize=11)
            for spine in ax_stoch.spines.values():
                spine.set_edgecolor('#2d3561')
                spine.set_linewidth(2)
        
        # x축 날짜 포맷
        for ax in self.figure.get_axes():
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, color='#e0e0e0')
        
        # 마지막 차트만 x축 레이블 표시
        for ax in self.figure.get_axes()[:-1]:
            ax.set_xticklabels([])
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def show_technical_indicators(self):
        """기술적 지표 값 표시"""
        self.indicatorTable.setRowCount(7)
        
        latest = self.df.iloc[-1]
        currency = self.get_currency_symbol(self.current_symbol)[0]
        
        indicators = [
            ('RSI', f"{latest['rsi']:.2f}" if not pd.isna(latest['rsi']) else '-'),
            ('MACD', f"{latest['macd']:.2f}" if not pd.isna(latest['macd']) else '-'),
            ('MACD Signal', f"{latest['macd_signal']:.2f}" if not pd.isna(latest['macd_signal']) else '-'),
            ('볼린저 상단', self.format_price(latest['bb_upper'], self.current_symbol) if not pd.isna(latest['bb_upper']) else '-'),
            ('볼린저 하단', self.format_price(latest['bb_lower'], self.current_symbol) if not pd.isna(latest['bb_lower']) else '-'),
        ]
        
        if 'stoch_k' in latest:
            indicators.extend([
                ('Stochastic %K', f"{latest['stoch_k']:.2f}" if not pd.isna(latest['stoch_k']) else '-'),
                ('Stochastic %D', f"{latest['stoch_d']:.2f}" if not pd.isna(latest['stoch_d']) else '-'),
            ])
        
        for i, (name, value) in enumerate(indicators):
            self.indicatorTable.setItem(i, 0, QTableWidgetItem(name))
            self.indicatorTable.setItem(i, 1, QTableWidgetItem(value))
    
    def update_table(self):
        """테이블 위젯 업데이트"""
        recent_data = self.df.tail(30)
        self.tableWidget.setRowCount(len(recent_data))
        
        for i, (date, row) in enumerate(recent_data.iterrows()):
            # 날짜
            self.tableWidget.setItem(i, 0, QTableWidgetItem(date.strftime('%Y-%m-%d')))
            
            # 종가 (환율 정보 포함)
            price_text = self.format_price(row['close'], self.current_symbol)
            if self.is_us_stock(self.current_symbol):
                krw_price = self.exchange_manager.convert_to_krw(row['close'])
                price_text += f"\n(₩{krw_price:,.0f})"
            self.tableWidget.setItem(i, 1, QTableWidgetItem(price_text))
            
            # 이동평균
            if not pd.isna(row['ma9']):
                self.tableWidget.setItem(i, 2, QTableWidgetItem(self.format_price(row['ma9'], self.current_symbol)))
            else:
                self.tableWidget.setItem(i, 2, QTableWidgetItem("-"))
                
            if not pd.isna(row['ma22']):
                self.tableWidget.setItem(i, 3, QTableWidgetItem(self.format_price(row['ma22'], self.current_symbol)))
            else:
                self.tableWidget.setItem(i, 3, QTableWidgetItem("-"))
            
            # 변동률
            if not pd.isna(row['change_pct']):
                change_item = QTableWidgetItem(f"{row['change_pct']:.2f}%")
                if row['change_pct'] > 0:
                    change_item.setForeground(QColor('#ff6b6b'))
                elif row['change_pct'] < 0:
                    change_item.setForeground(QColor('#4ecdc4'))
                self.tableWidget.setItem(i, 4, change_item)
        
        self.tableWidget.resizeColumnsToContents()
    
    def show_statistics(self):
        """통계 정보 표시"""
        current_price = self.df['close'].iloc[-1]
        start_price = self.df['close'].iloc[0]
        total_change = ((current_price - start_price) / start_price) * 100
        
        max_price = self.df['close'].max()
        min_price = self.df['close'].min()
        avg_price = self.df['close'].mean()
        
        # 환율 정보 추가
        stats_text = f"현재가: {self.format_price(current_price, self.current_symbol)}"
        if self.is_us_stock(self.current_symbol):
            krw_price = self.exchange_manager.convert_to_krw(current_price)
            stats_text += f" (₩{krw_price:,.0f})"
        
        stats_text += f"\n시작가: {self.format_price(start_price, self.current_symbol)}"
        stats_text += f"\n총 변동률: {total_change:.2f}%"
        
        stats_text += f"\n\n최고가: {self.format_price(max_price, self.current_symbol)}"
        stats_text += f"\n최저가: {self.format_price(min_price, self.current_symbol)}"
        stats_text += f"\n평균가: {self.format_price(avg_price, self.current_symbol)}"
        
        # 52주 최고/최저
        if len(self.df) >= 252:
            weeks_52 = self.df.tail(252)
            high_52w = weeks_52['close'].max()
            low_52w = weeks_52['close'].min()
            stats_text += f"\n\n52주 최고: {self.format_price(high_52w, self.current_symbol)}"
            stats_text += f"\n52주 최저: {self.format_price(low_52w, self.current_symbol)}"
        
        stats_text += f"\n\n데이터 기간: {self.df.index[0].strftime('%Y-%m-%d')} ~ {self.df.index[-1].strftime('%Y-%m-%d')}"
        stats_text += f"\n거래일 수: {len(self.df)}일"
        
        # 환율 정보
        if self.is_us_stock(self.current_symbol):
            stats_text += f"\n\n{self.exchange_manager.get_rate_info()}"
        
        self.textEditStats.setPlainText(stats_text)
    
    def add_alert(self):
        """알림 추가"""
        symbol = self.lineEditSymbol.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "입력 오류", "종목 코드를 입력해주세요.")
            return
        
        alert_type = self.cmbAlertType.currentText()
        
        if alert_type == '가격 알림':
            value, ok = QInputDialog.getDouble(self, "목표가 설정", "목표 가격을 입력하세요:", 
                                              min=0, decimals=2)
            if not ok:
                return
            
            items = ['이상', '이하']
            condition, ok = QInputDialog.getItem(self, "조건 선택", "조건을 선택하세요:", 
                                               items, 0, False)
            if not ok:
                return
            
            self.alert_manager.add_alert(symbol, 'price', condition, value)
            
        elif alert_type == '골든크로스':
            self.alert_manager.add_alert(symbol, 'golden_cross', '', 0)
            
        elif alert_type == '데드크로스':
            self.alert_manager.add_alert(symbol, 'dead_cross', '', 0)
        
        self.update_alert_table()
        QMessageBox.information(self, "알림 추가", "알림이 추가되었습니다.")
    
    def remove_alert(self):
        """알림 제거"""
        current_row = self.alertTable.currentRow()
        if current_row >= 0:
            self.alert_manager.remove_alert(current_row)
            self.update_alert_table()
    
    def update_alert_table(self):
        """알림 테이블 업데이트"""
        self.alertTable.setRowCount(len(self.alert_manager.alerts))
        
        for i, alert in enumerate(self.alert_manager.alerts):
            self.alertTable.setItem(i, 0, QTableWidgetItem(alert['symbol']))
            
            type_text = {
                'price': '가격',
                'golden_cross': '골든크로스',
                'dead_cross': '데드크로스'
            }.get(alert['type'], alert['type'])
            self.alertTable.setItem(i, 1, QTableWidgetItem(type_text))
            
            self.alertTable.setItem(i, 2, QTableWidgetItem(alert.get('condition', '-')))
            
            if alert['value'] > 0:
                currency = self.get_currency_symbol(alert['symbol'])[0]
                value_text = self.format_price(alert['value'], alert['symbol'])
            else:
                value_text = '-'
            self.alertTable.setItem(i, 3, QTableWidgetItem(value_text))
            
            status = '활성' if alert['active'] else '완료'
            status_item = QTableWidgetItem(status)
            if not alert['active']:
                status_item.setForeground(QColor('#95a5a6'))
            else:
                status_item.setForeground(QColor('#00d4ff'))
            self.alertTable.setItem(i, 4, status_item)
    
    def show_alert_notification(self, symbol, message):
        """알림 표시"""
        QMessageBox.information(self, f"알림 - {symbol}", message)
        self.update_alert_table()
    
    def add_to_portfolio(self):
        """포트폴리오에 추가"""
        symbol = self.lineEditPortfolioSymbol.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "입력 오류", "종목 코드를 입력해주세요.")
            return
        
        quantity = self.spinQuantity.value()
        price = self.spinPrice.value()
        
        if quantity <= 0 or price <= 0:
            QMessageBox.warning(self, "입력 오류", "수량과 가격을 올바르게 입력해주세요.")
            return
        
        self.portfolio.add_stock(symbol, quantity, price)
        
        # 현재가 업데이트
        if symbol not in self.current_prices:
            thread = DataFetchThread(symbol, 1)
            thread.finished.connect(lambda data: self.update_current_price(symbol, data))
            thread.start()
        
        self.update_portfolio_view()
        QMessageBox.information(self, "매수 완료", f"{symbol} {quantity}주를 {self.format_price(price, symbol)}에 매수했습니다.")
    
    def sell_from_portfolio(self):
        """포트폴리오에서 매도"""
        current_row = self.portfolioTable.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "선택 오류", "매도할 종목을 선택해주세요.")
            return
        
        symbol = self.portfolioTable.item(current_row, 0).text()
        max_quantity = self.portfolio.holdings[symbol]['quantity']
        
        quantity, ok = QInputDialog.getInt(self, "매도 수량", f"매도할 수량을 입력하세요 (최대: {max_quantity}):", 
                                         min=1, max=max_quantity)
        if not ok:
            return
        
        current_price = self.current_prices.get(symbol, 0)
        if current_price == 0:
            price, ok = QInputDialog.getDouble(self, "매도 가격", "매도 가격을 입력하세요:", 
                                             min=0, decimals=2)
            if not ok:
                return
        else:
            price = current_price
        
        if self.portfolio.sell_stock(symbol, quantity, price):
            self.update_portfolio_view()
            QMessageBox.information(self, "매도 완료", f"{symbol} {quantity}주를 {self.format_price(price, symbol)}에 매도했습니다.")
    
    def update_current_price(self, symbol, data):
        """현재가 업데이트"""
        if data is not None and not data.empty:
            self.current_prices[symbol] = data['close'].iloc[-1]
            self.update_portfolio_view()
    
    def refresh_portfolio(self):
        """포트폴리오 새로고침"""
        self.statusBar().showMessage("포트폴리오 업데이트 중...")
        
        # 모든 보유 종목의 현재가 업데이트
        for symbol in self.portfolio.holdings.keys():
            thread = DataFetchThread(symbol, 1)
            thread.finished.connect(lambda data, s=symbol: self.update_current_price(s, data))
            thread.start()
    
    def update_portfolio_view(self):
        """포트폴리오 뷰 업데이트"""
        if not self.portfolio.holdings:
            self.portfolioTable.setRowCount(0)
            self.labelTotalValue.setText("총 평가금액: ₩0")
            self.labelTotalProfit.setText("총 손익: ₩0 (0.00%)")
            return
        
        # 수익률 계산
        results, total = self.portfolio.calculate_returns(self.current_prices, self.exchange_manager)
        
        # 테이블 업데이트
        self.portfolioTable.setRowCount(len(results))
        
        for i, (symbol, data) in enumerate(results.items()):
            self.portfolioTable.setItem(i, 0, QTableWidgetItem(symbol))
            self.portfolioTable.setItem(i, 1, QTableWidgetItem(f"{data['quantity']:,}"))
            self.portfolioTable.setItem(i, 2, QTableWidgetItem(self.format_price(data['avg_price'], symbol)))
            self.portfolioTable.setItem(i, 3, QTableWidgetItem(self.format_price(data['current_price'], symbol)))
            self.portfolioTable.setItem(i, 4, QTableWidgetItem(self.format_price(data['current_value'], symbol)))
            self.portfolioTable.setItem(i, 5, QTableWidgetItem(f"₩{data['current_value_krw']:,.0f}"))
            
            profit_text = self.format_price(abs(data['profit']), symbol)
            if data['profit'] < 0:
                profit_text = f"-{profit_text}"
            profit_item = QTableWidgetItem(profit_text)
            if data['profit'] > 0:
                profit_item.setForeground(QColor('#ff6b6b'))
            elif data['profit'] < 0:
                profit_item.setForeground(QColor('#4ecdc4'))
            self.portfolioTable.setItem(i, 6, profit_item)
            
            rate_item = QTableWidgetItem(f"{data['profit_rate']:.2f}%")
            if data['profit_rate'] > 0:
                rate_item.setForeground(QColor('#ff6b6b'))
            elif data['profit_rate'] < 0:
                rate_item.setForeground(QColor('#4ecdc4'))
            self.portfolioTable.setItem(i, 7, rate_item)
        
        # 총계 표시
        self.labelTotalValue.setText(f"총 평가금액: ₩{total['total_value_krw']:,.0f}")
        
        profit_color = '#ff6b6b' if total['total_profit_krw'] > 0 else '#4ecdc4'
        self.labelTotalProfit.setText(
            f"총 손익: ₩{total['total_profit_krw']:,.0f} ({total['total_profit_rate']:.2f}%)"
        )
        self.labelTotalProfit.setStyleSheet(f"color: {profit_color}; font-weight: bold; font-size: 14px;")
        
        # 자산 배분 차트 업데이트
        self.update_portfolio_chart(results)
    
    def update_portfolio_chart(self, results):
        """포트폴리오 차트 업데이트"""
        self.portfolio_figure.clear()
        ax = self.portfolio_figure.add_subplot(111)
        ax.set_facecolor('#0a0e27')
        
        if results:
            labels = []
            sizes = []
            colors = ['#ff6b6b', '#4ecdc4', '#a29bfe', '#fd79a8', '#fdcb6e', '#6c5ce7', '#00b894', '#e17055', '#74b9ff', '#00d4ff']
            
            for i, (symbol, data) in enumerate(results.items()):
                labels.append(f"{symbol}\n{data['profit_rate']:.1f}%")
                sizes.append(data['current_value_krw'])  # 원화 기준
            
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors[:len(results)], 
                                             autopct='%1.1f%%', startangle=90, 
                                             textprops={'color': '#ffffff'})
            
            # 글자 스타일
            for text in texts:
                text.set_fontsize(12)
                text.set_color('#ffffff')
                text.set_weight('bold')
            for autotext in autotexts:
                autotext.set_fontsize(11)
                autotext.set_color('#000000')
                autotext.set_weight('bold')
            
            ax.set_title('포트폴리오 자산 배분 (원화 기준)', fontsize=16, fontweight='bold', color='#ffffff', pad=20)
        else:
            ax.text(0.5, 0.5, '포트폴리오가 비어있습니다', 
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes, fontsize=14, color='#ffffff')
        
        self.portfolio_figure.tight_layout()
        self.portfolio_canvas.draw()
    
    def save_to_db(self):
        """데이터베이스에 저장"""
        if not hasattr(self, 'df') or self.df is None:
            QMessageBox.warning(self, "저장 오류", "분석할 데이터가 없습니다.")
            return
        
        if not self.connect_db():
            return
        
        try:
            symbol = self.current_symbol
            
            # 종목 정보 저장
            self.cursor.execute("""
                INSERT IGNORE INTO stocks (symbol, name) VALUES (%s, %s)
            """, (symbol, symbol))
            
            # 기존 데이터 삭제
            self.cursor.execute("DELETE FROM stock_prices WHERE symbol = %s", (symbol,))
            
            # 새 데이터 삽입
            insert_query = """
                INSERT INTO stock_prices 
                (symbol, date, open_price, high_price, low_price, close_price, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            data_to_insert = []
            for date, row in self.df.iterrows():
                data_to_insert.append((
                    symbol,
                    date.date(),
                    float(row.get('open', row['close'])),
                    float(row.get('high', row['close'])),
                    float(row.get('low', row['close'])),
                    float(row['close']),
                    int(row.get('volume', 0))
                ))
            
            self.cursor.executemany(insert_query, data_to_insert)
            self.conn.commit()
            
            QMessageBox.information(self, "저장 완료", f"{len(data_to_insert)}개 데이터가 저장되었습니다.")
            
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "저장 오류", f"데이터 저장 실패: {e}")
        finally:
            self.conn.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    window = StockAnalyzer()
    window.show()
    sys.exit(app.exec_())
