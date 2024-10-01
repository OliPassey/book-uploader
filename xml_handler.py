# xml_handler.py

import xml.etree.ElementTree as ET
import logging

def load_xml(file_path, encoding='iso-8859-1'):
    try:
        with open(file_path, 'r', encoding=encoding) as file:
            content = file.read()
        root = ET.fromstring(content)
        logging.info(f"Successfully loaded XML file: {file_path} using {encoding} encoding")
        return root
    except ET.ParseError as e:
        logging.error(f"XML parsing error: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error loading XML file: {e}")
        raise

def safe_decode(text):
    if text is None:
        return ''
    return text.encode('utf-8', 'ignore').decode('utf-8')
