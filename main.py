# main.py

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from woocommerce_handler import WooCommerceHandler
from xml_handler import load_xml, safe_decode
from cache_handler import load_cache, save_cache

def setup_logging():
    logging.basicConfig(filename='import_log.txt', level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        encoding='utf-8')
    # Add a stream handler to display logs in console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

def load_config():
    try:
        with open("config-bl.json", "r") as f:
            config = json.load(f)
        with open("presets.json", "r") as f:
            presets = json.load(f)
        return config, presets
    except FileNotFoundError as e:
        logging.error(f"{e.filename} file not found. Please ensure it exists in the same directory as the script.")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error("Error parsing JSON file. Please ensure it's a valid JSON file.")
        sys.exit(1)

def sanitize_category_name(category_name):
    # Replace '/' with ' and ' and remove any other problematic characters
    return category_name.replace('/', ' and ').replace('\\', '').strip()

def get_or_create_category(wc_handler, category_name):
    sanitized_name = sanitize_category_name(category_name)
    try:
        # First, try to get the category by exact name match
        categories = wc_handler.get_categories(sanitized_name)
        exact_match = next((cat for cat in categories if cat['name'].lower() == sanitized_name.lower()), None)
        if exact_match:
            logging.info(f"Using existing category '{sanitized_name}' with ID: {exact_match['id']}")
            return exact_match['id']
        else:
            # If no exact match, create a new category
            new_category = wc_handler.create_category(sanitized_name)
            if 'id' in new_category:
                logging.info(f"Created new category '{sanitized_name}' with ID: {new_category['id']}")
                return new_category['id']
            else:
                logging.error(f"Failed to create category '{sanitized_name}'. Response: {new_category}")
                return None
    except Exception as e:
        logging.error(f"Error handling category '{sanitized_name}': {str(e)}")
        return None

def validate_and_clean_product_data(product_data):
    # Remove any attributes with None values
    product_data['attributes'] = [attr for attr in product_data['attributes'] if attr['options'][0] is not None]
    
    # Ensure all attribute options are strings
    for attr in product_data['attributes']:
        attr['options'] = [str(option) for option in attr['options']]
    
    # Ensure price is a valid string
    if not product_data.get('regular_price'):
        product_data['regular_price'] = '0'
    
    # Ensure stock quantity is an integer
    try:
        product_data['stock_quantity'] = int(product_data['stock_quantity'])
    except (ValueError, TypeError):
        product_data['stock_quantity'] = 0
    
    # Remove images if the URL is None
    if product_data.get('images') and product_data['images'][0].get('src') is None:
        product_data['images'] = []
    
    # Ensure description is not None
    if product_data.get('description') is None:
        product_data['description'] = ''
    
    # Ensure dimensions are properly formatted
    if 'dimensions' in product_data:
        dims = product_data['dimensions'].split('x')
        if len(dims) == 3:
            product_data['dimensions'] = {
                'length': dims[0].strip(),
                'width': dims[1].strip(),
                'height': dims[2].strip()
            }
        else:
            product_data['dimensions'] = {}
    
    return product_data

def analyze_products(root, existing_products):
    new_products = []
    updates = []
    for book in root.findall('book'):
        sku = safe_decode(book.find('isbn').text)
        if sku not in existing_products:
            new_products.append(sku)
        else:
            updates.append(sku)
    return new_products, updates

def new_stock_import(root, wc_handler, existing_products, new_product_skus, presets, batch_size=50):
    new_products_added = 0
    start_time = time.time()
    total_to_add = len(new_product_skus)
    batches = []
    current_batch = []

    logging.info(f"Starting import of {total_to_add} new products")

    for book in root.findall('book'):
        sku = safe_decode(book.find('isbn').text)
        if sku in new_product_skus:
            categories = []
            multicat = book.find('multicat')
            if multicat is not None and multicat.text:
                for cat in multicat.text.split(','):
                    cat_id = get_or_create_category(wc_handler, safe_decode(cat.strip()))
                    if cat_id is not None:
                        categories.append({"id": cat_id})

            new_product = {
                'name': safe_decode(book.find('title').text),
                'type': 'simple',
                'sku': sku,
                'regular_price': safe_decode(book.find('price').text),
                'stock_quantity': int(safe_decode(book.find('stock').text)) if book.find('stock') is not None else 0,
                'description': safe_decode(book.find('longdesc').text) if book.find('longdesc') is not None else '',
                'short_description': safe_decode(book.find('content').text) if book.find('content') is not None else '',
                'categories': categories,
                'images': [{"src": safe_decode(book.find('thumbnailL').text)}] if book.find('thumbnailL') is not None and book.find('thumbnailL').text else [],
                'attributes': [
                    {"name": "Author", "options": [safe_decode(book.find('author').text)]},
                    {"name": "Publisher", "options": [safe_decode(book.find('publisher').text)]},
                    {"name": "ISBN", "options": [sku]},
                    {"name": "Format", "options": [safe_decode(book.find('cover').text)]},
                    {"name": "Pages", "options": [safe_decode(book.find('pages').text)]},
                    {"name": "Language", "options": [safe_decode(book.find('lang').text)]},
                    {"name": "Dimensions", "options": [safe_decode(book.find('dimensions').text)]},
                    {"name": "Weight", "options": [safe_decode(book.find('weight').text)]},
                    {"name": "Publication Date", "options": [safe_decode(book.find('pub_date').text)]}
                ],
                'tags': [{"name": safe_decode(tag.strip())} for tag in book.find('subject').text.split('|')] if book.find('subject') is not None and book.find('subject').text else [],
                'tax_status': presets['tax_status'],
                'tax_class': presets['tax_class'],
                'manage_stock': presets['manage_stock'],
                'stock_status': presets['stock_status'],
                'shipping_class': presets['shipping_class'],
                'backorders': presets['backorders']
            }

            new_product = validate_and_clean_product_data(new_product)
            current_batch.append(new_product)

            # If batch is full, add it to batches and reset current_batch
            if len(current_batch) >= batch_size:
                batches.append(current_batch)
                current_batch = []

    # Add any remaining products to batches
    if current_batch:
        batches.append(current_batch)

    # Process each batch
    for idx, batch in enumerate(batches, start=1):
        try:
            response = wc_handler.create_products_batch(batch)
            # WooCommerce doesn't return individual success/failure per item in batch
            added = len(batch)
            new_products_added += added
            logging.info(f"Batch {idx}: Successfully added {added} products.")
            print(f"Batch {idx}: Successfully added {added} products.")
        except Exception as e:
            logging.error(f"Batch {idx}: Failed to add products. Error: {e}")

        # Optional: Add a small delay between batches to avoid hitting rate limits
        time.sleep(2)

    total_time = time.time() - start_time
    logging.info(f"Import completed. Total new products added: {new_products_added}")
    logging.info(f"Total time taken: {total_time:.2f} seconds")

def update_stock_and_price(root, wc_handler, existing_products, update_skus, batch_size=50):
    updates = 0
    start_time = time.time()
    batches = []
    current_batch = []

    for book in root.findall('book'):
        sku = safe_decode(book.find('isbn').text)
        if sku in update_skus:
            product_id = existing_products[sku]['id']
            try:
                update_data = {
                    'id': product_id,
                    'stock_quantity': int(safe_decode(book.find('stock').text)),
                    'regular_price': safe_decode(book.find('price').text)
                }
                current_batch.append(update_data)
                updates += 1

                # If batch is full, add it to batches and reset current_batch
                if len(current_batch) >= batch_size:
                    batches.append(current_batch)
                    current_batch = []
            except (ValueError, TypeError) as e:
                logging.error(f"Invalid data for SKU {sku}: {e}")

    # Add any remaining updates to batches
    if current_batch:
        batches.append(current_batch)

    # Process each batch
    for idx, batch in enumerate(batches, start=1):
        try:
            response = wc_handler.update_products_batch(batch)
            # WooCommerce doesn't return individual success/failure per item in batch
            updated = len(batch)
            logging.info(f"Batch {idx}: Successfully updated {updated} products.")
            print(f"Batch {idx}: Successfully updated {updated} products.")
        except Exception as e:
            logging.error(f"Batch {idx}: Failed to update products. Error: {e}")

        # Optional: Add a small delay between batches to avoid hitting rate limits
        time.sleep(2)

    total_time = time.time() - start_time
    logging.info(f"Total products updated: {updates}")
    logging.info(f"Total time taken: {total_time:.2f} seconds")
