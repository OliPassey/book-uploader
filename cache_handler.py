# cache_handler.py

import json
import os
from datetime import datetime, timedelta
import logging

CACHE_FILE = 'woocommerce_products_cache.json'
CACHE_EXPIRATION_DAYS = 31

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
            cache_date = datetime.fromisoformat(cache_data['cache_date'])
            if datetime.now() - cache_date < timedelta(days=CACHE_EXPIRATION_DAYS):
                logging.info(f"Using cached product data from {cache_date}")
                return cache_data['products']
        except (json.JSONDecodeError, KeyError) as e:
            logging.warning(f"Error reading cache file: {e}. Will fetch fresh data.")
    return None

def save_cache(products):
    cache_data = {
        'cache_date': datetime.now().isoformat(),
        'products': products
    }
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
        logging.info("Cache saved successfully.")
    except Exception as e:
        logging.error(f"Failed to save cache: {e}")
