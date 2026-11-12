import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from urllib.parse import urljoin

import customtkinter as ctk
import pandas as pd
import requests
from bs4 import BeautifulSoup

URL = 'https://mopsov.twse.com.tw/mops/web/t05sr01_1'
COLUMNS = ['公司代號', '公司簡稱', '發言日期', '發言時間', '主旨', '公告連結']


def fetch_announcements():
    """Same GET and table-extraction logic as the working Colab notebook."""
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8'}
    session = requests.Session()
    response = session.get(URL, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, 'html.parser')
    required_headers = ['公司代號', '公司簡稱', '發言日期', '發言時間', '主旨']
    target_table = next((table for table in soup.find_all('table')
                         if all(h in table.get_text(' ', strip=True) for h in required_headers)), None)
    if target_table is None:
        raise ValueError('Announcement table not found in the response HTML.')
    records = []
    for tr in target_table.find_all('tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) < 5:
            continue
        values = [td.get_text(' ', strip=True) for td in cells[:5]]
        if not values[0].isdigit():
            continue
        link = cells[4].find('a', href=True)
        records.append(dict(zip(COLUMNS, values + [urljoin(URL, link['href']) if link else ''])))
    return pd.DataFrame(records, columns=COLUMNS)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('MOPS 即時重大訊息 Explorer')
        self.geometry('1250x760')
        self.minsize(850, 530)
        self.all_df = pd.DataFrame(columns=COLUMNS)
        self.view_df = self.all_df.copy()
        self.busy = False
        self.results_queue = queue.Queue()
        self.after(150, self._poll_results)

        ctk.CTkLabel(self, text='MOPS 即時重大訊息', font=ctk.CTkFont(size=25, weight='bold')).pack(anchor='w', padx=18, pady=(16, 4))
        ctk.CTkLabel(self, text=URL, text_color='gray').pack(anchor='w', padx=18)
        controls = ctk.CTkFrame(self)
        controls.pack(fill='x', padx=18, pady=12)
        self.fetch_btn = ctk.CTkButton(controls, text='Fetch / Refresh', command=self.start_fetch, width=135)
        self.fetch_btn.grid(row=0, column=0, padx=10, pady=12)
        self.filter_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(controls, text='Enable keyword filter', variable=self.filter_var, command=self.apply_filter).grid(row=0, column=1, padx=8)
        self.search_entry = ctk.CTkEntry(controls, placeholder_text='Company code, company name, or subject keywords (comma-separated)', width=430)
        self.search_entry.grid(row=0, column=2, padx=8, sticky='ew')
        self.search_entry.bind('<Return>', lambda _e: self.apply_filter())
        self.mode = ctk.CTkOptionMenu(controls, values=['Any keyword', 'All keywords'], command=lambda _v: self.apply_filter(), width=125)
        self.mode.grid(row=0, column=3, padx=8)
        ctk.CTkButton(controls, text='Apply', command=self.apply_filter, width=80).grid(row=0, column=4, padx=8)
        ctk.CTkButton(controls, text='Export CSV', command=self.export_csv, width=105).grid(row=0, column=5, padx=(8, 10))
        controls.grid_columnconfigure(2, weight=1)

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill='both', expand=True, padx=18, pady=(0, 10))
        self.tree = ttk.Treeview(table_frame, columns=COLUMNS, show='headings', selectmode='browse')
        widths = {'公司代號': 95, '公司簡稱': 135, '發言日期': 110, '發言時間': 90, '主旨': 530, '公告連結': 230}
        for col in COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], minwidth=65, stretch=col in ('主旨', '公告連結'))
        yscroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        self.tree.bind('<Double-1>', self.open_selected)

        self.status = ctk.CTkLabel(self, text='Ready. Click Fetch / Refresh to retrieve announcements.', anchor='w')
        self.status.pack(fill='x', padx=18, pady=(0, 12))

    def start_fetch(self):
        if self.busy:
            return
        self.busy = True
        self.fetch_btn.configure(state='disabled')
        self.status.configure(text='Fetching MOPS announcements (30-second request timeout)...')
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        # Worker never calls Tkinter; all UI operations stay on the main thread.
        started = time.perf_counter()
        try:
            result = fetch_announcements()
            self.results_queue.put(('success', result, time.perf_counter() - started))
        except Exception as exc:
            self.results_queue.put(('error', f'{type(exc).__name__}: {exc}', time.perf_counter() - started))

    def _poll_results(self):
        try:
            while True:
                kind, payload, elapsed = self.results_queue.get_nowait()
                if kind == 'success':
                    self._fetch_success(payload)
                    self.status.configure(text=f'Loaded {len(payload)} announcements in {elapsed:.1f}s. Showing {len(self.view_df)}.')
                else:
                    self._fetch_error(f'{payload} (elapsed {elapsed:.1f}s)')
        except queue.Empty:
            pass
        self.after(150, self._poll_results)

    def _fetch_success(self, df):
        self.busy = False
        self.fetch_btn.configure(state='normal')
        self.all_df = df
        self.apply_filter()
        self.status.configure(text=f'Loaded {len(df)} announcements. Showing {len(self.view_df)} records.')

    def _fetch_error(self, message):
        self.busy = False
        self.fetch_btn.configure(state='normal')
        self.status.configure(text='Fetch failed: ' + message)
        messagebox.showerror('MOPS fetch failed', message)

    def apply_filter(self):
        df = self.all_df
        if self.filter_var.get():
            terms = [s.strip().casefold() for s in self.search_entry.get().split(',') if s.strip()]
            if terms and not df.empty:
                searchable = df[['公司代號', '公司簡稱', '主旨']].fillna('').astype(str).agg(' '.join, axis=1).str.casefold()
                masks = [searchable.str.contains(term, regex=False) for term in terms]
                mask = masks[0]
                for next_mask in masks[1:]:
                    mask = (mask & next_mask) if self.mode.get() == 'All keywords' else (mask | next_mask)
                df = df.loc[mask]
        self.view_df = df.copy()
        for row in self.tree.get_children():
            self.tree.delete(row)
        for _, row in self.view_df.iterrows():
            self.tree.insert('', 'end', values=[str(row[col]) if pd.notna(row[col]) else '' for col in COLUMNS])
        self.status.configure(text=f'Total: {len(self.all_df)} | Showing: {len(self.view_df)}')

    def export_csv(self):
        if self.view_df.empty:
            messagebox.showinfo('Nothing to export', 'Fetch data or adjust your filter first.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', initialfile='MOPS_Announcements.csv', filetypes=[('CSV files', '*.csv')])
        if path:
            self.view_df.to_csv(path, index=False, encoding='utf-8-sig')
            self.status.configure(text=f'Exported {len(self.view_df)} records to {path}')

    def open_selected(self, _event):
        import webbrowser
        selected = self.tree.selection()
        if not selected:
            return
        url = self.tree.item(selected[0], 'values')[-1]
        if url.startswith(('http://', 'https://')):
            webbrowser.open(url)


if __name__ == '__main__':
    ctk.set_appearance_mode('System')
    ctk.set_default_color_theme('blue')
    App().mainloop()
