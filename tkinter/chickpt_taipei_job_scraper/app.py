"""Chickpt Taipei job scraper with a CustomTkinter desktop interface."""

import csv
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.chickpt.com.tw/"
COLUMNS = ["職位名稱", "每小時薪", "工作地區", "公司名稱", "更新時間", "Page"]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EducationalJobScraper/1.0)"}


def extract_text(card, selector):
    element = card.select_one(selector)
    return element.get_text(" ", strip=True) if element else ""


def find_job_cards(soup):
    """Find the common parent of each title and its listing fields.

    The title and field selectors come from the assignment screenshot. The
    enclosing card selector was not verified and can change with the website.
    """
    cards = []
    seen = set()
    for title in soup.select("h2.job-info-title"):
        card = title
        for parent in title.parents:
            if parent.name in ("body", "html"):
                break
            if (parent.select_one("span.salary") and
                    parent.select_one("span.place") and
                    parent.select_one("p.ellipsis-job-company")):
                card = parent
                break
        if card is title:
            continue
        # Prefer the nearest matching container, avoiding duplicate parent cards.
        identity = id(card)
        if identity not in seen:
            seen.add(identity)
            cards.append(card)
    return cards


def scrape_jobs(start_page, end_page, report=None):
    """Scrape a page range and return a DataFrame; report is a progress callback."""
    if start_page < 1 or end_page < start_page or end_page - start_page >= 50:
        raise ValueError("Choose pages >= 1, in ascending order, at most 50 pages.")

    records = []
    with requests.Session() as session:
        session.headers.update(HEADERS)
        for page in range(start_page, end_page + 1):
            response = session.get(
                BASE_URL, params={"area": "Taipei", "page": page}, timeout=20
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            cards = find_job_cards(soup)
            count = 0
            for card in cards:
                record = {
                    "職位名稱": extract_text(card, "h2.job-info-title"),
                    "每小時薪": extract_text(card, "span.salary"),
                    "工作地區": extract_text(card, "span.place"),
                    "公司名稱": extract_text(card, "p.ellipsis-job-company"),
                    "更新時間": extract_text(card, "span.date-time"),
                    "Page": page,
                }
                if record["職位名稱"]:
                    records.append(record)
                    count += 1
            if report:
                report(f"Page {page}: {count} jobs found")
            if page < end_page:
                time.sleep(1)
    return pd.DataFrame(records, columns=COLUMNS)


class JobScraperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Chickpt Taipei Job Scraper")
        self.geometry("1120x700")
        self.minsize(850, 500)
        self.results = pd.DataFrame(columns=COLUMNS)
        self.events = queue.Queue()
        self.is_running = False

        ctk.set_widget_scaling(1.0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(self, text="Chickpt Taipei Job Scraper", font=ctk.CTkFont(size=25, weight="bold"))
        title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        controls = ctk.CTkFrame(self)
        controls.grid(row=1, column=0, padx=20, pady=8, sticky="ew")
        ctk.CTkLabel(controls, text="Start page").pack(side="left", padx=(14, 6), pady=12)
        self.start_entry = ctk.CTkEntry(controls, width=75)
        self.start_entry.insert(0, "1")
        self.start_entry.pack(side="left", padx=(0, 18))
        ctk.CTkLabel(controls, text="End page").pack(side="left", padx=(0, 6))
        self.end_entry = ctk.CTkEntry(controls, width=75)
        self.end_entry.insert(0, "3")
        self.end_entry.pack(side="left", padx=(0, 18))
        self.scrape_button = ctk.CTkButton(controls, text="Start Scraping", command=self.start_scraping)
        self.scrape_button.pack(side="left", padx=(0, 10))
        self.export_button = ctk.CTkButton(controls, text="Export CSV", command=self.export_csv, state="disabled")
        self.export_button.pack(side="left", padx=(0, 12))

        table_frame = ctk.CTkFrame(self)
        table_frame.grid(row=2, column=0, padx=20, pady=8, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        self.table = ttk.Treeview(table_frame, columns=COLUMNS, show="headings")
        for column in COLUMNS:
            self.table.heading(column, text=column)
            self.table.column(column, width=175 if column != "Page" else 60, anchor="w")
        self.table.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        vertical.grid(row=0, column=1, sticky="ns", pady=(10, 0))
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky="ew", padx=(10, 0), pady=(0, 10))
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)

        self.status = ctk.CTkTextbox(self, height=105)
        self.status.grid(row=3, column=0, padx=20, pady=(8, 20), sticky="ew")
        self.status.insert("end", "Ready. Choose pages and click Start Scraping.\n")
        self.status.configure(state="disabled")
        self.after(100, self.process_events)

    def log(self, message):
        self.status.configure(state="normal")
        self.status.insert("end", message + "\n")
        self.status.see("end")
        self.status.configure(state="disabled")

    def start_scraping(self):
        if self.is_running:
            return
        try:
            start = int(self.start_entry.get().strip())
            end = int(self.end_entry.get().strip())
            if start < 1 or end < start or end - start >= 50:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid page range", "Enter whole numbers >= 1, start <= end, and no more than 50 pages.")
            return
        self.is_running = True
        self.scrape_button.configure(state="disabled", text="Scraping...")
        self.export_button.configure(state="disabled")
        self.results = pd.DataFrame(columns=COLUMNS)
        for item in self.table.get_children():
            self.table.delete(item)
        self.log(f"Starting Taipei pages {start}–{end}...")
        threading.Thread(target=self.scrape_worker, args=(start, end), daemon=True).start()

    def scrape_worker(self, start, end):
        try:
            data = scrape_jobs(start, end, report=lambda msg: self.events.put(("log", msg)))
            self.events.put(("done", data))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def process_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self.log(payload)
                elif kind == "done":
                    self.results = payload
                    for values in self.results.itertuples(index=False, name=None):
                        self.table.insert("", "end", values=values)
                    self.log(f"Finished: {len(self.results)} jobs collected.")
                    if self.results.empty:
                        self.log("No listings found. The website may have changed its HTML, blocked requests, or rendered jobs with JavaScript. Inspect its current structure.")
                    self.export_button.configure(state="normal" if not self.results.empty else "disabled")
                    self.finish()
                elif kind == "error":
                    self.log("Error: " + payload)
                    messagebox.showerror("Scraping failed", payload)
                    self.finish()
        except queue.Empty:
            pass
        self.after(100, self.process_events)

    def finish(self):
        self.is_running = False
        self.scrape_button.configure(state="normal", text="Start Scraping")

    def export_csv(self):
        if self.results.empty:
            messagebox.showinfo("No data", "Scrape some jobs first.")
            return
        filename = filedialog.asksaveasfilename(
            title="Save job listings", defaultextension=".csv",
            initialfile="chickpt_taipei_jobs.csv", filetypes=[("CSV files", "*.csv")]
        )
        if filename:
            self.results.to_csv(filename, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
            self.log(f"Saved CSV: {filename}")


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = JobScraperApp()
    app.mainloop()
