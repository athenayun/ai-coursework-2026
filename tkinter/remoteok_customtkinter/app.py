"""Remote OK job explorer built with CustomTkinter.

Run: python app.py
Remote OK attribution: https://remoteok.com/
"""

import csv
import queue
import re
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
import requests
from bs4 import BeautifulSoup

API_URL = "https://remoteok.com/api"
DEFAULT_KEYWORDS = "machine learning, mlops, data engineer, ai engineer, data scientist"
COLUMNS = ("title", "company", "location", "salary", "date")


def safe_int(value):
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def plain_text(value):
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def normalize_job(raw):
    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    return {
        "title": str(raw.get("position") or ""),
        "company": str(raw.get("company") or ""),
        "location": str(raw.get("location") or "Remote / Not specified"),
        "tags": [str(tag) for tag in tags],
        "salary_min": safe_int(raw.get("salary_min")),
        "salary_max": safe_int(raw.get("salary_max")),
        "date": str(raw.get("date") or ""),
        "description": plain_text(raw.get("description")),
        "url": str(raw.get("url") or ""),
        "apply_url": str(raw.get("apply_url") or ""),
    }


def fetch_jobs():
    response = requests.get(
        API_URL,
        headers={
            "User-Agent": "RemoteJobExplorer/1.0 (educational desktop app)",
            "Accept": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Unexpected API response: expected a list")
    return [normalize_job(item) for item in payload if isinstance(item, dict) and item.get("position")]


def salary_text(job):
    low, high = job["salary_min"], job["salary_max"]
    if low and high:
        return f"${low:,}–${high:,}"
    if low:
        return f"From ${low:,}"
    if high:
        return f"Up to ${high:,}"
    return "Not listed"


class JobExplorer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Remote OK — Job Explorer")
        self.geometry("1220x780")
        self.minsize(920, 640)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.jobs = []
        self.filtered_jobs = []
        self.events = queue.Queue()
        self.loading = False

        self._build_ui()
        self.after(150, self._process_events)
        self.refresh_jobs()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Remote Job Explorer", font=ctk.CTkFont(size=27, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Data provided by Remote OK • https://remoteok.com", text_color="gray").grid(row=1, column=0, sticky="w")
        self.refresh_button = ctk.CTkButton(header, text="Refresh Jobs", command=self.refresh_jobs, width=125)
        self.refresh_button.grid(row=0, column=1, rowspan=2, padx=(12, 0))

        filters = ctk.CTkFrame(self)
        filters.grid(row=1, column=0, sticky="ew", padx=20, pady=(6, 12))
        for col in range(4):
            filters.grid_columnconfigure(col, weight=1)

        ctk.CTkLabel(filters, text="Job title keywords (comma-separated)").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 0))
        self.keyword_entry = ctk.CTkEntry(filters, placeholder_text="machine learning, mlops, data engineer")
        self.keyword_entry.insert(0, DEFAULT_KEYWORDS)
        self.keyword_entry.grid(row=1, column=0, sticky="ew", padx=12, pady=(3, 9))

        ctk.CTkLabel(filters, text="Location contains").grid(row=0, column=1, sticky="w", padx=12, pady=(12, 0))
        self.location_entry = ctk.CTkEntry(filters, placeholder_text="Europe, Worldwide, Germany...")
        self.location_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=(3, 9))

        ctk.CTkLabel(filters, text="Skills / tags (comma-separated)").grid(row=0, column=2, sticky="w", padx=12, pady=(12, 0))
        self.tags_entry = ctk.CTkEntry(filters, placeholder_text="python, tensorflow, gcp")
        self.tags_entry.grid(row=1, column=2, sticky="ew", padx=12, pady=(3, 9))

        ctk.CTkLabel(filters, text="Minimum listed salary (USD)").grid(row=0, column=3, sticky="w", padx=12, pady=(12, 0))
        self.salary_entry = ctk.CTkEntry(filters, placeholder_text="e.g. 80000")
        self.salary_entry.grid(row=1, column=3, sticky="ew", padx=12, pady=(3, 9))

        self.include_unknown = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(filters, text="Include jobs without salary", variable=self.include_unknown).grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 12))
        ctk.CTkButton(filters, text="Apply Filters", command=self.apply_filters).grid(row=2, column=2, sticky="ew", padx=12, pady=(0, 12))
        ctk.CTkButton(filters, text="Clear Filters", fg_color="gray40", hover_color="gray30", command=self.clear_filters).grid(row=2, column=3, sticky="ew", padx=12, pady=(0, 12))

        content = ctk.CTkFrame(self)
        content.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 8))
        content.grid_rowconfigure(0, weight=3)
        content.grid_rowconfigure(1, weight=2)
        content.grid_columnconfigure(0, weight=1)

        table_frame = ctk.CTkFrame(content, fg_color="transparent")
        table_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 4))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, columns=COLUMNS, show="headings", selectmode="browse")
        for key, heading, width in [
            ("title", "Job Title", 300), ("company", "Company", 190),
            ("location", "Location", 190), ("salary", "Salary (USD)", 150),
            ("date", "Posted", 170),
        ]:
            self.table.heading(key, text=heading)
            self.table.column(key, width=width, minwidth=100, stretch=True)
        self.table.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.bind("<<TreeviewSelect>>", self.show_details)
        self.table.bind("<Double-1>", lambda _: self.open_job())

        details = ctk.CTkFrame(content)
        details.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 10))
        details.grid_columnconfigure(0, weight=1)
        details.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(details, text="Selected Job Details", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
        self.details_text = ctk.CTkTextbox(details, wrap="word")
        self.details_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self._set_details("Select a job to see its details. Double-click a row to open the listing.")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 14))
        footer.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(footer, text="Loading...", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(footer, text="Open Selected Job", command=self.open_job).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(footer, text="Export Filtered CSV", command=self.export_csv).grid(row=0, column=2, padx=(8, 0))

    def _set_details(self, content):
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", content)
        self.details_text.configure(state="disabled")

    def refresh_jobs(self):
        if self.loading:
            return
        self.loading = True
        self.refresh_button.configure(state="disabled", text="Loading...")
        self.status_label.configure(text="Fetching Remote OK listings...")
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            self.events.put(("success", fetch_jobs()))
        except (requests.RequestException, ValueError) as exc:
            self.events.put(("error", str(exc)))

    def _process_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self.loading = False
                self.refresh_button.configure(state="normal", text="Refresh Jobs")
                if kind == "success":
                    self.jobs = payload
                    self.apply_filters()
                else:
                    self.status_label.configure(text="Failed to fetch jobs; existing results retained.")
                    messagebox.showerror("Remote OK request failed", payload)
        except queue.Empty:
            pass
        self.after(150, self._process_events)

    def clear_filters(self):
        for entry in (self.keyword_entry, self.location_entry, self.tags_entry, self.salary_entry):
            entry.delete(0, "end")
        self.include_unknown.set(True)
        self.apply_filters()

    def apply_filters(self):
        keywords = [s.strip().casefold() for s in self.keyword_entry.get().split(",") if s.strip()]
        location = self.location_entry.get().strip().casefold()
        tags = [s.strip().casefold() for s in self.tags_entry.get().split(",") if s.strip()]
        minimum_text = self.salary_entry.get().strip().replace(",", "")
        if minimum_text:
            minimum = safe_int(minimum_text)
            if minimum is None or minimum < 0:
                messagebox.showwarning("Invalid salary", "Enter a nonnegative numeric minimum salary (USD).")
                return
        else:
            minimum = None

        matches = []
        for job in self.jobs:
            if keywords and not any(word in job["title"].casefold() for word in keywords):
                continue
            if location and location not in job["location"].casefold():
                continue
            search_tags = " ".join(job["tags"]).casefold()
            if tags and not any(tag in search_tags for tag in tags):
                continue
            if minimum is not None:
                upper = job["salary_max"] or job["salary_min"]
                if upper is None:
                    if not self.include_unknown.get():
                        continue
                elif upper < minimum:
                    continue
            matches.append(job)

        self.filtered_jobs = matches
        self.table.delete(*self.table.get_children())
        for idx, job in enumerate(matches):
            self.table.insert("", "end", iid=str(idx), values=(
                job["title"], job["company"], job["location"], salary_text(job), job["date"]
            ))
        self._set_details("Select a job to see its details. Double-click a row to open the listing.")
        self.status_label.configure(text=f"Showing {len(matches)} of {len(self.jobs)} jobs • Remote OK")

    def selected_job(self):
        selected = self.table.selection()
        if not selected:
            return None
        idx = int(selected[0])
        return self.filtered_jobs[idx] if idx < len(self.filtered_jobs) else None

    def show_details(self, _event=None):
        job = self.selected_job()
        if not job:
            return
        text = (
            f"{job['title']} — {job['company']}\n"
            f"Location: {job['location']}\n"
            f"Salary (USD): {salary_text(job)}\n"
            f"Posted: {job['date']}\n"
            f"Tags: {', '.join(job['tags']) or 'Not specified'}\n"
            f"Listing: {job['url']}\n\n"
            f"Description:\n{job['description'] or 'No description provided.'}"
        )
        self._set_details(text)

    def open_job(self):
        job = self.selected_job()
        if not job:
            messagebox.showinfo("Select a job", "Select a job from the table first.")
            return
        url = job["url"] or job["apply_url"]
        if not url.startswith("https://"):
            messagebox.showwarning("No link", "This job does not have a valid HTTPS listing URL.")
            return
        webbrowser.open(url)

    def export_csv(self):
        if not self.filtered_jobs:
            messagebox.showinfo("Nothing to export", "There are no matching jobs to export.")
            return
        destination = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"remoteok_jobs_{datetime.now():%Y%m%d}.csv",
        )
        if not destination:
            return
        fieldnames = ["Job Title", "Company", "Location", "Tags", "Salary Min", "Salary Max", "Posted Date", "Description", "Job URL", "Apply URL", "Source"]
        try:
            with Path(destination).open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for job in self.filtered_jobs:
                    writer.writerow({
                        "Job Title": job["title"], "Company": job["company"],
                        "Location": job["location"], "Tags": ", ".join(job["tags"]),
                        "Salary Min": job["salary_min"], "Salary Max": job["salary_max"],
                        "Posted Date": job["date"], "Description": job["description"],
                        "Job URL": job["url"], "Apply URL": job["apply_url"],
                        "Source": "Remote OK (https://remoteok.com)",
                    })
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Export complete", f"Saved {len(self.filtered_jobs)} jobs to:\n{destination}")


if __name__ == "__main__":
    app = JobExplorer()
    app.mainloop()
