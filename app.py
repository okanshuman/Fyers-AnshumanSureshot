# app.py
from flask import Flask, render_template, jsonify
from flask_apscheduler import APScheduler
from apscheduler.triggers.cron import CronTrigger  # Import CronTrigger
import Login as fyers
from utils import round_to_two_decimal, is_valid_symbol, clean_symbol, calculate_percentage_change
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import logging
import threading
import time
from datetime import datetime
import math  # Import math module for floor division

app = Flask(__name__)
scheduler = APScheduler()

holdings_data = []  # Global variables to store data
processed_symbols = set()
stock_data = []
purchased_symbols = set()  # Set to track purchased stock symbols
data_lock = threading.Lock()

def fetch_holdings_for_selling():
    global holdings_data
    try:
        holdings_response = fyers.fyers_active.holdings()
        holdings_data = holdings_response['holdings']

        total_pl = 0.0
        combined_holdings = {}

        for holding in holdings_data:
            if is_valid_symbol(holding['symbol']):
                holding['symbol'] = clean_symbol(holding['symbol'])
                holding['costPrice'] = round_to_two_decimal(holding['costPrice'])
                holding['ltp'] = round_to_two_decimal(holding['ltp'])
                holding['pl'] = round_to_two_decimal(holding['pl'])
                holding['marketVal'] = round_to_two_decimal(holding.get('marketVal', 0))
                holding['percentChange'] = calculate_percentage_change(holding['costPrice'], holding['ltp'])
                total_pl += holding['pl']

                if holding['symbol'] in combined_holdings: # Combine holdings with the same symbol
                    combined_holdings[holding['symbol']]['quantity'] += holding['quantity']
                    combined_holdings[holding['symbol']]['pl'] += holding['pl']
                    combined_holdings[holding['symbol']]['marketVal'] += holding.get('marketVal', 0)
                else:
                    combined_holdings[holding['symbol']] = {
                        'quantity': holding['quantity'],
                        'costPrice': holding['costPrice'],
                        'ltp': holding['ltp'],
                        'pl': holding['pl'],
                        'marketVal': holding.get('marketVal', 0),
                        'percentChange': holding['percentChange']
                    }

        filtered_holdings = []  # Convert combined holdings back to a list for further processing
        for symbol, data in combined_holdings.items():
            data.update({'symbol': symbol})
            filtered_holdings.append(data)

        filtered_holdings.sort(key=lambda x: x['percentChange'])

        for holding in filtered_holdings:  # Sell stocks using the new sell function
            if holding['percentChange'] > 2 and holding['symbol'] not in processed_symbols:
                place_sell_order(holding)
                print("Selling :" + holding['symbol'])

        holdings_data = filtered_holdings

        return round_to_two_decimal(total_pl)

    except Exception as e:
        print(f"Error fetching holdings: {str(e)}")
        return 0.0

def place_sell_order(holding):
    try:
        order_data = {
            "symbol": f"NSE:{holding['symbol']}-EQ",
            "qty": holding['quantity'],
            "type": 2,
            "side": -1,  # Side -1 indicates a sell order
            "productType": "CNC",
            "limitPrice": 0,
            "stopPrice": 0,
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False,
            "orderTag": "tag1"
        }
        response = fyers.fyers_active.place_order(data=order_data)
        print(f"Sell order placed for {holding['symbol']}: {response}")
        processed_symbols.add(holding['symbol'])  # Add the symbol to processed symbols after a successful sell order

    except Exception as e:
        print(f"Error placing sell order for {holding['symbol']}: {str(e)}")

def place_buy_order():
    global stock_data  # Access global stock data to place buy orders

    try:
        for stock in stock_data:
            if stock['symbol'] in purchased_symbols:
                print(f"Stock {stock['symbol']} has already been purchased. Skipping buy order.")
                continue
            
            current_price = stock['current_price']  # Calculate dynamic buy quantity based on current price
            buy_quantity = math.floor(5000 / current_price)  # Calculate quantity without decimals
            
            order_data = {
                "symbol": f"NSE:{stock['symbol']}-EQ",
                "qty": buy_quantity,  # Use dynamic quantity here
                "type": 2,
                "side": 1,  # Side 1 indicates a buy order
                "productType": "CNC",
                "limitPrice": 0,
                "stopPrice": 0,
                "validity": "DAY",
                "disclosedQty": 0,
                "offlineOrder": False,
                "orderTag": "tag1"
            }
            response = fyers.fyers_active.place_order(data=order_data)
            print(f"Buy order placed for {stock['symbol']} with quantity {buy_quantity}: {response}")

            purchased_symbols.add(stock['symbol']) # Add the symbol to the set of purchased symbols after a successful buy order
        
    except Exception as e:
        print(f"Error placing buy orders: {str(e)}")

def fetch_stocks():
    global stock_data  
    urls = [
        "https://chartink.com/screener/anshuman-sureshot1",
        "https://chartink.com/screener/anshuman-sureshot2",
        "https://chartink.com/screener/anshuman-sureshot3"
    ]

    chrome_options = Options()
    chrome_options.add_argument("--headless")  
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=ChromeService(executable_path='/usr/bin/chromedriver'), options=chrome_options)
    new_stocks = []

    try:
        for url in urls:
            logging.info(f"Fetching stocks from {url}")
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'table-striped')))
            stock_list = driver.find_element(By.CLASS_NAME, 'table-striped')
            rows = stock_list.find_elements(By.TAG_NAME, 'tr')[1:]  

            logging.info(f"Found {len(rows)} rows of stock data from {url}.")

            for row in rows:
                columns = row.find_elements(By.TAG_NAME, 'td')
                if len(columns) > 5:  # Ensure there are enough columns to avoid index errors
                    stock_name = columns[1].text.strip()
                    stock_symbol = clean_symbol(columns[2].text.strip().replace('$', ''))  
                    current_price = round_to_two_decimal(float(columns[5].text.strip()))  # Fetch current price
                    identified_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if is_valid_symbol(stock_symbol) and not any(stock['symbol'] == stock_symbol for stock in stock_data):
                        new_stocks.append({"name": stock_name, 
                                           "symbol": stock_symbol, 
                                           "current_price": current_price, 
                                           "date": identified_date})

        if new_stocks:
            with data_lock:
                stock_data.extend(new_stocks)
                logging.info(f"New stocks identified: {new_stocks}")
        
        else:
            logging.info("No new stocks identified.")

    except Exception as e:
        logging.error(f"An error occurred while fetching stocks: {e}")

    finally:
        driver.quit()

@app.route("/", methods=["GET"])
def index():
    total_pl = fetch_holdings_for_selling()  
    return render_template("index.html", holdings=holdings_data, total_pl=total_pl)

@app.route("/api/stocks", methods=["GET"])
def get_stocks():
    with data_lock:
        return jsonify(stock_data)  

@scheduler.task(trigger=CronTrigger(hour=15, minute=22), id='update_buy_orders_task')  
def scheduled_buy_orders():
    fetch_stocks()
    place_buy_order()

@scheduler.task('interval', id='update_holdings_task', seconds=60)  # Update holdings every minute
def scheduled_update_holdings():
    fetch_holdings_for_selling()

if __name__ == "__main__": 
    scheduler.init_app(app)
    scheduler.start()
    app.run(debug=False, host='0.0.0.0', port=5001)