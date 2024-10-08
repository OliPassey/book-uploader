# gui.py

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import logging
import json
import os
import time
from main import (
    setup_logging,
    load_config,
    load_xml,
    WooCommerceHandler,
    analyze_products,
    new_stock_import,
    update_stock_and_price,
    load_cache,
    save_cache
)

class WooCommerceImporterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("WooCommerce Product Importer")
        self.root.geometry("800x600")
        
        setup_logging()
        self.config, self.presets = load_config()
        self.wc_handler = WooCommerceHandler(self.config)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize attributes before creating widgets
        self.selected_file = None
        self.mode = tk.StringVar(value="dry-run")  # Initialized before create_widgets

        self.create_widgets()

    def create_widgets(self):
        # Create a Notebook widget for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Create frames for each tab
        self.main_frame = ttk.Frame(notebook)
        self.settings_frame = ttk.Frame(notebook)

        # Add tabs to the notebook
        notebook.add(self.main_frame, text="Main")
        notebook.add(self.settings_frame, text="Settings")

        # ----------------- Main Tab Widgets ----------------- #
        # File Selection Frame
        file_frame = ttk.LabelFrame(self.main_frame, text="1. Select XML File")
        file_frame.pack(fill="x", padx=10, pady=10)

        self.file_entry = ttk.Entry(file_frame, width=80)
        self.file_entry.pack(side="left", padx=5, pady=5, expand=True, fill="x")

        browse_button = ttk.Button(file_frame, text="Browse", command=self.browse_file)
        browse_button.pack(side="left", padx=5, pady=5)

        # Mode Selection Frame
        mode_frame = ttk.LabelFrame(self.main_frame, text="2. Select Mode")
        mode_frame.pack(fill="x", padx=10, pady=10)

        modes = [("Dry Run", "dry-run"), ("Add New Products", "new-stock"), ("Update Existing Products", "update")]
        for text, mode in modes:
            ttk.Radiobutton(mode_frame, text=text, variable=self.mode, value=mode).pack(side="left", padx=10, pady=5)

        # Action Buttons Frame
        action_frame = ttk.Frame(self.main_frame)
        action_frame.pack(fill="x", padx=10, pady=10)

        self.run_button = ttk.Button(action_frame, text="Run", command=self.run_process)
        self.run_button.pack(side="left", padx=5, pady=5)

        self.cancel_button = ttk.Button(action_frame, text="Cancel", command=self.root.quit)
        self.cancel_button.pack(side="left", padx=5, pady=5)

        # Progress Bar
        self.progress = ttk.Progressbar(self.main_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=10)

        # Log Display
        log_frame = ttk.LabelFrame(self.main_frame, text="Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_text = tk.Text(log_frame, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)

        # Redirect logging to the log_text widget
        self.setup_log_redirect()

        # ----------------- Settings Tab Widgets ----------------- #
        settings_label = ttk.Label(self.settings_frame, text="Configure WooCommerce API Settings", font=("Arial", 14))
        settings_label.pack(pady=10)

        # Settings Form Frame
        form_frame = ttk.Frame(self.settings_frame)
        form_frame.pack(padx=20, pady=10, fill="x")

        # Site URL
        site_url_label = ttk.Label(form_frame, text="Site URL:")
        site_url_label.grid(row=0, column=0, sticky="e", pady=5)
        self.site_url_entry = ttk.Entry(form_frame, width=50)
        self.site_url_entry.grid(row=0, column=1, pady=5, padx=5)
        self.site_url_entry.insert(0, self.config.get('site_url', ''))

        # Consumer Key
        client_key_label = ttk.Label(form_frame, text="Consumer Key:")
        client_key_label.grid(row=1, column=0, sticky="e", pady=5)
        self.client_key_entry = ttk.Entry(form_frame, width=50)
        self.client_key_entry.grid(row=1, column=1, pady=5, padx=5)
        self.client_key_entry.insert(0, self.config.get('client_key', ''))

        # Consumer Secret
        client_secret_label = ttk.Label(form_frame, text="Consumer Secret:")
        client_secret_label.grid(row=2, column=0, sticky="e", pady=5)
        self.client_secret_entry = ttk.Entry(form_frame, width=50, show="*")
        self.client_secret_entry.grid(row=2, column=1, pady=5, padx=5)
        self.client_secret_entry.insert(0, self.config.get('client_secret', ''))

        # Save Button
        save_button = ttk.Button(self.settings_frame, text="Save Settings", command=self.save_settings)
        save_button.pack(pady=10)

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select XML File",
            filetypes=(("XML Files", "*.xml"), ("All Files", "*.*"))
        )
        if file_path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_path)
            self.selected_file = file_path

    def setup_log_redirect(self):
        # Create a custom handler to redirect logs to the Text widget
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                msg = self.format(record)
                def append():
                    self.text_widget.configure(state='normal')
                    self.text_widget.insert(tk.END, msg + '\n')
                    self.text_widget.see(tk.END)
                    self.text_widget.configure(state='disabled')
                self.text_widget.after(0, append)

        text_handler = TextHandler(self.log_text)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        text_handler.setFormatter(formatter)
        logging.getLogger().addHandler(text_handler)

    def run_process(self):
        if not self.selected_file:
            messagebox.showwarning("No File Selected", "Please select an XML file to proceed.")
            return

        mode = self.mode.get()
        if mode not in ['dry-run', 'new-stock', 'update']:
            messagebox.showwarning("Invalid Mode", "Please select a valid mode of operation.")
            return

        # Disable the Run button to prevent multiple clicks
        self.run_button.config(state="disabled")

        # Reset Progress Bar
        self.progress['value'] = 0
        self.progress['maximum'] = 100  # Will be updated based on total operations

        # Start the process in a separate thread to keep the GUI responsive
        thread = threading.Thread(target=self.process, args=(mode,))
        thread.start()

    def process(self, mode):
        try:
            root = load_xml(self.selected_file)
            existing_products = load_cache()
            if existing_products is None:
                # Fetch from API if cache is not available
                existing_products = {}
                page = 1
                total_products = 0
                logging.info("Fetching existing products from WooCommerce...")
                while True:
                    products, headers = self.wc_handler.get_products(per_page=100, page=page)
                    if not products:
                        break
                    for product in products:
                        existing_products[product['sku']] = product
                    total_products += len(products)
                    logging.info(f"Fetched {total_products} products (Page {page})")
                    if 'X-WP-TotalPages' in headers:
                        total_pages = int(headers['X-WP-TotalPages'])
                        if page >= total_pages:
                            break
                    page += 1
                    time.sleep(0.5)
                logging.info(f"Completed fetching existing products. Total: {len(existing_products)}")
                save_cache(existing_products)

            new_product_skus, update_skus = analyze_products(root, existing_products)
            logging.info(f"New products to be added: {len(new_product_skus)}")
            logging.info(f"Existing products to be updated: {len(update_skus)}")

            if mode == 'dry-run':
                logging.info("Dry run completed. No changes were made.")
                messagebox.showinfo("Dry Run", f"Dry run completed.\n\nNew products to add: {len(new_product_skus)}\nExisting products to update: {len(update_skus)}")
            elif mode == 'new-stock':
                if not new_product_skus:
                    logging.info("No new products to add.")
                    messagebox.showinfo("No New Products", "There are no new products to add.")
                else:
                    proceed = messagebox.askyesno("Confirm Import", f"Do you want to proceed with adding {len(new_product_skus)} new products?")
                    if proceed:
                        total_new = len(new_product_skus)
                        self.progress['maximum'] = total_new
                        new_stock_import(
                            root, 
                            self.wc_handler, 
                            existing_products, 
                            new_product_skus, 
                            self.presets,
                            batch_size=50,
                            progress_callback=self.update_progress
                        )
                        messagebox.showinfo("Import Completed", f"Successfully added {len(new_product_skus)} new products.")
                    else:
                        logging.info("Operation cancelled by user.")
            elif mode == 'update':
                if not update_skus:
                    logging.info("No existing products to update.")
                    messagebox.showinfo("No Updates", "There are no existing products to update.")
                else:
                    proceed = messagebox.askyesno("Confirm Update", f"Do you want to proceed with updating {len(update_skus)} existing products?")
                    if proceed:
                        total_updates = len(update_skus)
                        self.progress['maximum'] = total_updates
                        update_stock_and_price(
                            root, 
                            self.wc_handler, 
                            existing_products, 
                            update_skus,
                            batch_size=50,
                            progress_callback=self.update_progress
                        )
                        messagebox.showinfo("Update Completed", f"Successfully updated {len(update_skus)} products.")
                    else:
                        logging.info("Operation cancelled by user.")

        except Exception as e:
            logging.error(f"An unexpected error occurred: {str(e)}")
            messagebox.showerror("Error", f"An unexpected error occurred:\n{str(e)}")
        finally:
            # Re-enable the Run button
            self.run_button.config(state="normal")

    def update_progress(self, increment):
        # Update the progress bar incrementally
        self.progress['value'] += increment
        self.progress.update_idletasks()

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.root.destroy()

    def save_settings(self):
        site_url = self.site_url_entry.get().strip()
        client_key = self.client_key_entry.get().strip()
        client_secret = self.client_secret_entry.get().strip()

        # Basic validation
        if not site_url or not client_key or not client_secret:
            messagebox.showwarning("Incomplete Data", "All fields are required.")
            return

        # Confirm with the user
        proceed = messagebox.askyesno("Confirm Save", "Are you sure you want to save the new settings?")
        if not proceed:
            return

        # Update config dictionary
        self.config['site_url'] = site_url
        self.config['client_key'] = client_key
        self.config['client_secret'] = client_secret

        try:
            with open("config-bl.json", "w") as f:
                json.dump(self.config, f, indent=4)
            messagebox.showinfo("Success", "Settings have been saved successfully.")
            logging.info("Settings updated successfully.")

            # Optionally, prompt the user to restart the application
            restart = messagebox.askyesno("Restart Required", "Changes will take effect after restarting the application. Do you want to restart now?")
            if restart:
                self.root.destroy()
                os.system(f'python "{os.path.abspath("gui.py")}"')

        except Exception as e:
            logging.error(f"Failed to save settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings:\n{str(e)}")

def main():
    root = tk.Tk()
    app = WooCommerceImporterGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
