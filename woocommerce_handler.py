# woocommerce_handler.py

from woocommerce import API
import json
import logging
import time

class WooCommerceHandler:
    def __init__(self, config):
        try:
            self.wc_api = API(
                url=config['site_url'],
                consumer_key=config['client_key'],
                consumer_secret=config['client_secret'],
                version='wc/v3',
                timeout=30
            )
        except KeyError as e:
            logging.error(f"Missing required configuration in config-bl.json: {e}")
            raise

    def get_products(self, per_page=100, page=1):
        try:
            response = self.wc_api.get("products", params={"per_page": per_page, "page": page})
            response.raise_for_status()
            return response.json(), response.headers
        except Exception as e:
            logging.error(f"Error fetching products from WooCommerce: {e}")
            raise

    def create_products_batch(self, products_batch):
        try:
            response = self.wc_api.post("products/batch", {'create': products_batch})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error creating products batch: {e}")
            raise

    def update_products_batch(self, products_batch):
        try:
            response = self.wc_api.put("products/batch", {'update': products_batch})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error updating products batch: {e}")
            raise

    def get_categories(self, search_term):
        try:
            response = self.wc_api.get("products/categories", params={"search": search_term})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error fetching categories: {e}")
            raise

    def create_category(self, category_name):
        try:
            response = self.wc_api.post("products/categories", {"name": category_name})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error creating category '{category_name}': {e}")
            raise
