"""CTEE topic scraper desktop application (local Chrome + Selenium)."""
from __future__ import annotations

import csv
import queue
import re
import threading
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urljoin, urlparse

import customtkinter as ctk
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

TOPICS = {
    "財經焦點 (Financial Highlights)": "https://www.ctee.com.tw/finance/f-highlights",
    "台股 (Taiwan Stock Market)": "https://www.ctee.com.tw/stock/twmarket",
}
COLUMNS = ("分類", "發布時間", "新聞標題", "內容摘要", "新聞連結")


def parse_ctee(html: str, category: str, base_url: str) -> list[dict[str, str]]:
    """Parse time-tag-centered news cards; avoids pairing unrelated articles."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if any(marker in title.lower() for marker in ("cloudflare", "access denied", "403", "連線錯誤")):
        raise RuntimeError(f"CTEE returned an access/error page: {title}")

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for time_tag in soup.select("time.news-time"):
        card = time_tag
        anchor = None
        summary = None
        for _ in range(7):
            card = card.parent
            if card is None:
                break
            # The matching link and summary should belong to the same card.
            anchors = [a for a in card.select('a[href*="/news/"]') if a.get_text(" ", strip=True)]
            summaries = card.select("p.news-summary")
            if anchors and summaries:
                anchor, summary = anchors[0], summaries[0]
                break
        if anchor is None:
            continue
        url = urljoin(base_url, anchor.get("href", ""))
        if urlparse(url).netloc not in ("ctee.com.tw", "www.ctee.com.tw"):
            continue
        if url in seen:
            continue
        seen.add(url)
        results.append({
            "分類": category,
            "發布時間": time_tag.get("datetime") or time_tag.get_text(" ", strip=True),
            "新聞標題": anchor.get_text(" ", strip=True),
            "內容摘要": summary.get_text(" ", strip=True) if summary else "",
            "新聞連結": url,
        })
    return results


class CTEEApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CTEE News Explorer")
        self.geometry("1230x770")
        self.minsize(940, 600)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.all_records: list[dict[str, str]] = []
        self.visible_records: list[dict[str, str]] = []
        self.running = False

        heading = ctk.CTkFrame(self)
        heading.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(heading, text="CTEE News Explorer", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(heading, text="Select CTEE topics • fetch with local Chrome • filter articles • export CSV").pack(anchor="w", padx=16, pady=(0, 12))

        controls = ctk.CTkFrame(self)
        controls.pack(fill="x", padx=16, pady=6)
        self.topic_vars = {}
        ctk.CTkLabel(controls, text="Topics", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        for index, label in enumerate(TOPICS):
            var = ctk.BooleanVar(value=True)
            self.topic_vars[label] = var
            ctk.CTkCheckBox(controls, text=label, variable=var).grid(row=index + 1, column=0, sticky="w", padx=12, pady=5)

        self.fetch_button = ctk.CTkButton(controls, text="Fetch selected topics", command=self.start_fetch, width=170)
        self.fetch_button.grid(row=1, column=1, padx=15, pady=8)
        ctk.CTkButton(controls, text="Export filtered CSV", command=self.export_csv, width=170).grid(row=2, column=1, padx=15, pady=8)
        controls.grid_columnconfigure(2, weight=1)

        filter_frame = ctk.CTkFrame(self)
        filter_frame.pack(fill="x", padx=16, pady=6)
        self.filter_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(filter_frame, text="Enable keyword filter", variable=self.filter_enabled, command=self.apply_filter).pack(side="left", padx=12, pady=12)
        self.keyword_entry = ctk.CTkEntry(filter_frame, placeholder_text="Keywords: AI, 台積電, 半導體 (comma separated)", width=370)
        self.keyword_entry.pack(side="left", padx=8, fill="x", expand=True)
        self.keyword_entry.bind("<Return>", lambda _: self.apply_filter())
        self.match_mode = ctk.CTkOptionMenu(filter_frame, values=["Any keyword", "All keywords"], command=lambda _: self.apply_filter(), width=125)
        self.match_mode.pack(side="left", padx=8)
        ctk.CTkButton(filter_frame, text="Apply", width=80, command=self.apply_filter).pack(side="left", padx=(0, 12))

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=16, pady=6)
        self.tree = ttk.Treeview(table_frame, columns=COLUMNS, show="headings", selectmode="browse")
        for col, width in zip(COLUMNS, (115, 105, 320, 480, 280)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, minwidth=75, stretch=(col in ("新聞標題", "內容摘要")))
        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 0))
        scrollbar_y.grid(row=0, column=1, sticky="ns", pady=(8, 0))
        scrollbar_x.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=(0, 8))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        self.tree.bind("<Double-1>", self.open_selected)

        self.status = ctk.CTkLabel(self, text="Ready. Select topics and click Fetch.", anchor="w")
        self.status.pack(fill="x", padx=20, pady=(4, 12))
        self.after(100, self.process_messages)

    def start_fetch(self) -> None:
        if self.running:
            return
        selected = [(name, TOPICS[name]) for name, var in self.topic_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("No topics selected", "Please select at least one topic.")
            return
        self.running = True
        self.fetch_button.configure(state="disabled")
        self.status.configure(text="Launching local Chrome...")
        threading.Thread(target=self.fetch_worker, args=(selected,), daemon=True).start()

    def fetch_worker(self, selected: list[tuple[str, str]]) -> None:
        driver = None
        combined = []
        errors = []
        try:
            opts = Options()
            # Visible Chrome is intentional: this is the configuration tested on Mac.
            opts.add_argument("--window-size=1440,900")
            driver = webdriver.Chrome(options=opts)
            driver.set_page_load_timeout(35)
            for name, url in selected:
                self.messages.put(("status", f"Loading {name} ..."))
                try:
                    driver.get(url)
                    WebDriverWait(driver, 20).until(
                        lambda d: bool(d.find_elements(By.CSS_SELECTOR, "time.news-time"))
                        or "cloudflare" in d.title.lower()
                        or "連線錯誤" in d.title
                    )
                    parsed = parse_ctee(driver.page_source, name, url)
                    if not parsed:
                        errors.append(f"{name}: no article cards found (check the page or HTML selectors).")
                    combined.extend(parsed)
                    self.messages.put(("status", f"{name}: {len(parsed)} articles"))
                except (TimeoutException, WebDriverException, RuntimeError) as exc:
                    errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:200]}")
        except Exception as exc:
            errors.append(f"Chrome startup failed: {type(exc).__name__}: {exc}")
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
            self.messages.put(("done", (combined, errors)))

    def process_messages(self) -> None:
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "status":
                    self.status.configure(text=str(payload))
                elif kind == "done":
                    records, errors = payload
                    deduped = {r["新聞連結"]: r for r in records}
                    self.all_records = list(deduped.values())
                    self.apply_filter()
                    self.running = False
                    self.fetch_button.configure(state="normal")
                    self.status.configure(text=f"Loaded {len(self.all_records)} articles; showing {len(self.visible_records)}.")
                    if errors:
                        messagebox.showwarning("Fetch completed with issues", "\n\n".join(errors))
        except queue.Empty:
            pass
        self.after(100, self.process_messages)

    def apply_filter(self) -> None:
        terms = [x.strip().casefold() for x in re.split(r"[,，\n]+", self.keyword_entry.get()) if x.strip()]
        if not self.filter_enabled.get() or not terms:
            filtered = self.all_records[:]
        else:
            def matches(record: dict[str, str]) -> bool:
                haystack = " ".join(str(record[key]) for key in ("分類", "新聞標題", "內容摘要")).casefold()
                return all(t in haystack for t in terms) if self.match_mode.get() == "All keywords" else any(t in haystack for t in terms)
            filtered = [record for record in self.all_records if matches(record)]
        self.visible_records = filtered
        self.tree.delete(*self.tree.get_children())
        for i, record in enumerate(filtered):
            self.tree.insert("", "end", iid=str(i), values=[record.get(col, "") for col in COLUMNS])
        self.status.configure(text=f"Showing {len(filtered)} of {len(self.all_records)} articles.")

    def open_selected(self, _event=None) -> None:
        selection = self.tree.selection()
        if selection:
            url = self.visible_records[int(selection[0])]["新聞連結"]
            if url.startswith("https://"):
                webbrowser.open(url)

    def export_csv(self) -> None:
        if not self.visible_records:
            messagebox.showinfo("Nothing to export", "Fetch articles first or adjust your filter.")
            return
        filename = filedialog.asksaveasfilename(
            title="Save filtered articles", defaultextension=".csv",
            initialfile="CTEE_News.csv", filetypes=[("CSV files", "*.csv")]
        )
        if not filename:
            return
        with open(Path(filename), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(self.visible_records)
        messagebox.showinfo("Exported", f"Saved {len(self.visible_records)} articles.")


if __name__ == "__main__":
    CTEEApp().mainloop()
