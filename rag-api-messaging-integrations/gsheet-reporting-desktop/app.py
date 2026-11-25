"""Google Sheets explorer and Telegram sender. Run: python app.py"""
import io
import base64
from docx import Document
import time
import html
import unicodedata
from datetime import datetime
import queue
import re
import threading
from urllib.parse import urlparse, parse_qs
from tkinter import messagebox, ttk, filedialog

import customtkinter as ctk
import pandas as pd
import requests


def parse_sheet_url(url):
    """Extract spreadsheet ID and worksheet GID from a Google Sheets URL."""
    parsed = urlparse(url.strip())
    if parsed.scheme != 'https' or parsed.netloc.lower() != 'docs.google.com':
        raise ValueError('Paste a valid HTTPS Google Sheets URL.')
    match = re.fullmatch(r'/spreadsheets/(?:u/\d+/)?d/([A-Za-z0-9_-]+)(?:/.*)?', parsed.path)
    if not match or match.group(1) == 'e':
        raise ValueError('Use the original Google Sheets sharing URL, not a published link.')
    gid = parse_qs(parsed.fragment, keep_blank_values=True).get('gid',
          parse_qs(parsed.query, keep_blank_values=True).get('gid', ['0']))[0]
    if not re.fullmatch(r'[0-9]+', gid):
        raise ValueError('The worksheet GID must be numeric.')
    return match.group(1), gid


def read_gsheet(sheet_id, gid):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', sheet_id) or not gid.isdigit():
        raise ValueError('Enter a valid Sheet ID and numeric GID.')
    url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}'
    with requests.get(url, timeout=30, stream=True) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > 10_000_000:
                raise ValueError('CSV exceeds 10 MB.')
    if data.lstrip().lower().startswith((b'<!doctype html', b'<html')):
        raise ValueError('Google returned HTML instead of CSV. Check sharing permissions.')
    return pd.read_csv(io.BytesIO(data), encoding='utf-8-sig', dtype=str).fillna('')


def display_width(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in text)


def cell(value, limit=24):
    text = ' '.join(str(value).split()) or '—'
    if display_width(text) <= limit:
        return text
    out = ''
    for c in text:
        if display_width(out + c) > limit - 1:
            break
        out += c
    return out + '…'


def format_records(df, started, elapsed, load_elapsed):
    """Return report pages, each with a repeated header and complete rows."""
    header = (f'📊 Google Sheets Query Report\n🕒 Query time: {started:%Y-%m-%d %H:%M:%S %z}\n'
              f'⏱ Query duration: {elapsed:.3f} s\n📥 Sheet loading: {load_elapsed:.3f} s\n'
              f'📋 Records: {len(df)} | Columns: {len(df.columns)}\n'
              'ℹ️ Cells may be shortened; exports retain full values.')
    pages = []
    # Groups of three data columns keep tables reasonably narrow on phones.
    for offset in range(0, len(df.columns), 3):
        group = df.iloc[:, offset:offset+3]
        rows = [[str(i), *(cell(v) for v in row)] for i, row in enumerate(group.itertuples(index=False, name=None), 1)]
        names = ['No.', *(cell(c) for c in group.columns)]
        widths = [max(display_width(r[j]) for r in [names, *rows]) for j in range(len(names))]
        def line(row):
            return ' | '.join(v + ' ' * (w-display_width(v)) for v,w in zip(row,widths)).rstrip()
        heading = line(names) + '\n' + '-+-'.join('-'*w for w in widths)
        label = f'🔍 Columns {offset+1}–{offset+len(group.columns)}'
        batch = heading
        for row in rows:
            candidate = batch + '\n' + line(row)
            if len(candidate) > 1500:
                pages.append((header + '\n' + label, batch))
                batch = heading + '\n' + line(row)
            else:
                batch = candidate
        pages.append((header + '\n' + label, batch))
    return pages


def plain_report(pages):
    return '\n\n'.join(header + '\n' + table for header, table in pages)


def send_telegram(token, chat_id, pages):
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token):
        raise ValueError('Invalid bot token format.')
    if not re.fullmatch(r'-?\d+', chat_id):
        raise ValueError('Enter a numeric Telegram chat ID.')
    parts = [html.escape(header) + "\n<pre>" + html.escape(table) + "</pre>" for header, table in pages]
    sent = 0
    for part in parts:
        try:
            response = requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={'chat_id': chat_id, 'text': part, 'parse_mode': 'HTML'}, timeout=25)
            result = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError(f'Telegram request failed after {sent}/{len(parts)} messages. Check connection and bot settings.') from None
        if not response.ok or not result.get('ok'):
            raise RuntimeError(f'Telegram rejected message (HTTP {response.status_code}); {sent}/{len(parts)} accepted. Check token, chat ID and bot permissions.')
        sent += 1
    return f'Telegram accepted {sent} message(s).'


def safe_csv(df):
    """Protect spreadsheet readers from formula injection."""
    def safe(v):
        return "'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v
    out = df.apply(lambda col: col.map(safe))
    out.columns = [safe(c) for c in df.columns]
    return out.to_csv(index=False).encode('utf-8-sig')


def word_report(df, metadata):
    doc = Document()
    doc.add_heading('Google Sheets Query Report', 0)
    doc.add_paragraph(metadata)
    # Split wide tables for readable Word pages; retain full cell values.
    def clean(v):
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(v))
    for offset in range(0, len(df.columns), 5):
        group = df.iloc[:, offset:offset+5]
        table = doc.add_table(rows=1, cols=len(group.columns)+1)
        table.style = 'Table Grid'
        for c, value in zip(table.rows[0].cells, ['No.', *group.columns]):
            c.text = clean(value)
        for i, row in enumerate(group.itertuples(index=False, name=None), 1):
            for c, value in zip(table.add_row().cells, [i, *row]):
                c.text = clean(value)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def send_email(key, sender, recipient, df, metadata, fmt, subject, body):
    """Send a snapshot through Resend REST API without storing credentials."""
    attachments = []
    if fmt in ('CSV', 'Both'):
        attachments.append({'filename': 'query_results.csv', 'content': base64.b64encode(safe_csv(df)).decode('ascii')})
    if fmt in ('Word', 'Both'):
        attachments.append({'filename': 'query_results.docx', 'content': base64.b64encode(word_report(df, metadata)).decode('ascii')})
    payload = {'from': sender, 'to': [recipient], 'subject': subject,
               'html': '<h2>' + html.escape(subject) + '</h2><p>' + html.escape(body).replace('\n', '<br>') + '</p><p>' + html.escape(metadata).replace('\n', '<br>') + '</p><p>📎 Query results attached.</p>',
               'attachments': attachments}
    try:
        response = requests.post('https://api.resend.com/emails', headers={'Authorization': 'Bearer ' + key}, json=payload, timeout=45)
        result = response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError('Resend request failed. Check connection and dashboard before retrying.') from None
    if not response.ok or not isinstance(result, dict) or not result.get('id'):
        raise RuntimeError(f'Resend rejected the email (HTTP {response.status_code}). Check API key, sender domain, recipient and attachment size.')
    return 'Resend accepted email request. Check dashboard for delivery status.'


def line_parts(text, limit=4500):
    # Conservative UTF-16 length accounting; preserve every character.
    parts, current, size = [], [], 0
    for ch in text:
        n = len(ch.encode('utf-16-le')) // 2
        if size + n > limit:
            parts.append(''.join(current)); current, size = [], 0
        current.append(ch); size += n
    if current: parts.append(''.join(current))
    return parts


def send_line(token, recipient, mode, parts):
    endpoint = 'broadcast' if mode == 'Broadcast' else 'push'
    accepted = 0
    for part in parts:
        payload = {'messages': [{'type': 'text', 'text': part}]}
        if endpoint == 'push': payload['to'] = recipient
        try:
            response = requests.post('https://api.line.me/v2/bot/message/' + endpoint,
                headers={'Authorization': 'Bearer ' + token}, json=payload, timeout=25)
        except requests.RequestException:
            raise RuntimeError(f'LINE request failed after {accepted}/{len(parts)} accepted. Check delivery before retrying.') from None
        if not response.ok:
            raise RuntimeError(f'LINE rejected request (HTTP {response.status_code}); {accepted}/{len(parts)} accepted.')
        accepted += 1
    return f'LINE accepted {accepted} message(s). Delivery is not guaranteed.'


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('Google Sheets • Multi-Channel Reporting')
        self.geometry('1100x760')
        self.minsize(780, 560)
        self.df = None
        self.result_df = None
        self.report_pages = None
        self.load_elapsed = 0.0
        self.columns = {}
        self.events = queue.Queue()
        self.busy = False
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        left = ctk.CTkScrollableFrame(self, width=350, label_text='Configuration')
        left.grid(row=0, column=0, sticky='nsew', padx=12, pady=12)
        def field(label, default='', secret=False, parent=left):
            ctk.CTkLabel(parent, text=label).pack(anchor='w', pady=(8,0))
            entry = ctk.CTkEntry(parent, show='*' if secret else '')
            entry.pack(fill='x', pady=4)
            entry.insert(0, default)
            return entry
        self.sheet = field('Google Sheets URL')
        self.sheet.configure(placeholder_text='Paste full Google Sheets link')
        self.load_btn = ctk.CTkButton(left, text='Load Google Sheet', command=self.load)
        self.load_btn.pack(fill='x', pady=8)
        ctk.CTkLabel(left, text='Select columns', font=ctk.CTkFont(weight='bold')).pack(anchor='w')
        self.column_frame = ctk.CTkFrame(left)
        self.column_frame.pack(fill='x')
        ctk.CTkButton(left, text='Select all', command=lambda: self.select(True)).pack(fill='x', pady=3)
        ctk.CTkButton(left, text='Clear selection', command=lambda: self.select(False)).pack(fill='x', pady=3)
        self.keyword = field('Keyword (all columns, optional)')
        self.limit = field('First N matching records', '10')
        self.preview_btn = ctk.CTkButton(left, text='Run query', command=self.preview)
        self.preview_btn.pack(fill='x', pady=5)
        self.export_format = ctk.CTkOptionMenu(left, values=['CSV', 'Excel', 'TXT', 'Word'])
        self.export_format.pack(fill='x', pady=4)
        self.export_btn = ctk.CTkButton(left, text='Export query result', command=self.export)
        self.export_btn.pack(fill='x', pady=5)
        self.tabs = ctk.CTkTabview(left, command=self.refresh_message)
        self.tabs.pack(fill='x', pady=8)
        tg = self.tabs.add('Telegram'); ln = self.tabs.add('LINE'); em = self.tabs.add('Email')
        self.token = field('Bot token', secret=True, parent=tg)
        self.chat = field('Chat ID', parent=tg)
        self.tg_title = field('Report title', 'Google Sheets Query Report', parent=tg)
        self.tg_note = field('Optional message / note', parent=tg)
        self.send_btn = ctk.CTkButton(tg, text='Send to Telegram', command=self.send)
        self.send_btn.pack(fill='x', pady=5)
        self.line_token = field('Channel access token', secret=True, parent=ln)
        self.line_mode = ctk.CTkOptionMenu(ln, values=['Push', 'Broadcast'], command=self.line_mode_changed)
        self.line_mode.pack(fill='x', pady=4)
        self.line_recipient = field('Recipient user / group / room ID', parent=ln)
        self.line_title = field('Report title', 'Google Sheets Query Report', parent=ln)
        self.line_note = field('Optional message / note', parent=ln)
        ctk.CTkLabel(ln, text='Broadcast sends to ALL eligible followers.', wraplength=280).pack(fill='x')
        self.line_btn = ctk.CTkButton(ln, text='Send to LINE', command=self.line, fg_color='#168343')
        self.line_btn.pack(fill='x', pady=5)
        self.resend_key = field('Resend API key', secret=True, parent=em)
        self.sender = field('Sender email', 'onboarding@resend.dev', parent=em)
        self.recipient = field('Recipient email / Gmail', parent=em)
        self.subject = field('Email subject', 'Google Sheets Query Report', parent=em)
        ctk.CTkLabel(em, text='Email body / greeting').pack(anchor='w')
        self.body = ctk.CTkTextbox(em, height=90)
        self.body.pack(fill='x', pady=4)
        self.body.insert('1.0', 'Hello, please find the query report attached.')
        ctk.CTkLabel(em, text='Attachment format').pack(anchor='w')
        self.attachment = ctk.CTkOptionMenu(em, values=['CSV', 'Word', 'Both'], command=lambda _: self.refresh_message())
        self.attachment.pack(fill='x', pady=4)
        self.email_btn = ctk.CTkButton(em, text='Send email report', command=self.email)
        self.email_btn.pack(fill='x', pady=5)
        for parent in (tg, ln, em):
            ctk.CTkButton(parent, text='Refresh message preview', command=self.refresh_message).pack(fill='x', pady=4)

        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky='nsew', padx=(0,12), pady=12)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        right.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(right, text='Query results', font=ctk.CTkFont(size=20, weight='bold')).grid(row=0,column=0,sticky='w',padx=12,pady=8)
        table = ctk.CTkFrame(right)
        table.grid(row=1,column=0,sticky='nsew',padx=12)
        table.grid_columnconfigure(0,weight=1); table.grid_rowconfigure(0,weight=1)
        self.tree = ttk.Treeview(table, show='headings')
        self.tree.grid(row=0,column=0,sticky='nsew')
        for orient, row, col, command, key in [('vertical',0,1,self.tree.yview,'yscrollcommand'),('horizontal',1,0,self.tree.xview,'xscrollcommand')]:
            bar=ttk.Scrollbar(table,orient=orient,command=command)
            bar.grid(row=row,column=col,sticky='ns' if orient=='vertical' else 'ew')
            self.tree.configure(**{key:bar.set})
        self.preview_label = ctk.CTkLabel(right,text='Telegram message preview')
        self.preview_label.grid(row=2,column=0,sticky='w',padx=12,pady=8)
        self.message = ctk.CTkTextbox(right, wrap='none', font=('Menlo', 12))
        self.message.grid(row=3,column=0,sticky='nsew',padx=12,pady=(0,12))
        self.message.configure(state='disabled')
        self.status = ctk.CTkLabel(self,text='Ready — load a shared Google Sheet.')
        self.status.grid(row=1,column=0,columnspan=2,sticky='w',padx=12,pady=(0,8))
        self.after(100,self.poll)

    def select(self, value):
        for var in self.columns.values(): var.set(value)

    def work(self, label, fn, callback):
        if self.busy: return
        self.busy=True
        self.status.configure(text=label)
        for btn in (self.load_btn,self.preview_btn,self.send_btn,self.export_btn,self.email_btn,self.line_btn): btn.configure(state='disabled')
        def runner():
            try: self.events.put((callback,fn(),None))
            except Exception as exc: self.events.put((None,None,str(exc)))
        threading.Thread(target=runner,daemon=True).start()

    def poll(self):
        try:
            callback,result,error=self.events.get_nowait()
            self.busy=False
            for btn in (self.load_btn,self.preview_btn,self.send_btn,self.export_btn,self.email_btn,self.line_btn): btn.configure(state='normal')
            if error:
                self.status.configure(text='Operation failed.')
                messagebox.showerror('Error',error)
            else:
                try: callback(result)
                except Exception as exc: messagebox.showerror('Error',str(exc))
        except queue.Empty: pass
        finally: self.after(100,self.poll)

    def load(self):
        try:
            sheet, gid = parse_sheet_url(self.sheet.get())
        except ValueError as exc:
            messagebox.showwarning('Google Sheets URL', str(exc))
            return
        def fetch():
            start = time.perf_counter()
            df = read_gsheet(sheet, gid)
            return df, time.perf_counter() - start
        self.work('Loading Google Sheet…', fetch, self.loaded)

    def loaded(self,result):
        df, self.load_elapsed = result
        self.df=df
        self.result_df = None
        self.report_pages = None
        for widget in self.column_frame.winfo_children(): widget.destroy()
        self.columns={}
        for col in df.columns:
            var=ctk.BooleanVar(value=True)
            self.columns[col]=var
            ctk.CTkCheckBox(self.column_frame,text=str(col),variable=var).pack(anchor='w',padx=6,pady=4)
        self.preview()

    def selection(self):
        if self.df is None: raise ValueError('Load a sheet first.')
        cols=[col for col,var in self.columns.items() if var.get()]
        if not cols: raise ValueError('Select at least one column.')
        try: n=int(self.limit.get())
        except ValueError: raise ValueError('Enter a positive integer for records.') from None
        if not 1<=n<=100: raise ValueError('Choose 1–100 records.')
        source = self.df
        keyword = self.keyword.get().strip()
        if keyword:
            mask = source.apply(lambda col: col.str.contains(keyword, case=False, regex=False, na=False)).any(axis=1)
            source = source.loc[mask]
        df=source.loc[:,cols].head(n).copy()
        return df

    def preview(self):
        started = datetime.now().astimezone()
        start = time.perf_counter()
        try: df=self.selection()
        except ValueError as exc:
            messagebox.showwarning('Selection',str(exc)); return None
        elapsed = time.perf_counter() - start
        self.result_df = df
        self.tree.delete(*self.tree.get_children())
        ids=[f'c{i}' for i in range(len(df.columns))]
        self.tree.configure(columns=ids)
        for key,col in zip(ids,df.columns):
            self.tree.heading(key,text=str(col)); self.tree.column(key,width=150,stretch=False)
        for row in df.itertuples(index=False,name=None): self.tree.insert('', 'end',values=row)
        self.metadata = (f'Query time: {started:%Y-%m-%d %H:%M:%S %z}\n'
                         f'Query duration: {elapsed:.3f} s\nSheet loading: {self.load_elapsed:.3f} s\n'
                         f'Records: {len(df)} | Columns: {len(df.columns)}')
        self.report_pages = format_records(df, started, elapsed, self.load_elapsed)
        text = plain_report(self.report_pages)
        self.refresh_message()
        self.status.configure(text=f'Loaded {len(self.df)} rows | Selected {len(df)} rows × {len(df.columns)} columns | Query {elapsed:.3f}s | Load {self.load_elapsed:.3f}s')
        return text

    def export(self):
        if self.busy: return
        text = plain_report(self.report_pages) if self.report_pages else None
        if text is None or self.result_df.empty:
            messagebox.showinfo('Export', 'Run a query with matching records first.')
            return
        fmt = self.export_format.get()
        ext = {'CSV': '.csv', 'Excel': '.xlsx', 'TXT': '.txt', 'Word': '.docx'}[fmt]
        path = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[(fmt, '*' + ext)], initialfile='query_results' + ext)
        if not path: return
        df = self.result_df.copy()
        metadata = self.metadata
        def save():
            # Prevent spreadsheet formula execution from untrusted sheet values.
            def safe(value):
                return "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value
            if fmt in ('CSV', 'Excel'):
                df_safe = df.apply(lambda col: col.map(safe))
                df_safe.columns = [safe(c) for c in df.columns]
                if fmt == 'CSV': df_safe.to_csv(path, index=False, encoding='utf-8-sig')
                else: df_safe.to_excel(path, index=False, engine='openpyxl')
            elif fmt == 'Word':
                with open(path, 'wb') as file: file.write(word_report(df, metadata))
            else:
                with open(path, 'w', encoding='utf-8') as file: file.write(text)
            return f'Exported {len(df)} records to {path}'
        self.work('Exporting query results…', save, lambda result: self.status.configure(text=result))

    def line_mode_changed(self, mode):
        self.line_recipient.configure(state='disabled' if mode == 'Broadcast' else 'normal')
        self.refresh_message()

    def custom_pages(self, title, note):
        title = title.strip() or 'Google Sheets Query Report'
        if len(title) > 120 or len(note) > 300:
            raise ValueError('Limit title to 120 and note to 300 characters.')
        return [(header.replace('Google Sheets Query Report', title, 1) + ('\n' + note.strip() if note.strip() else ''), table)
                for header, table in self.report_pages]

    def line_report(self):
        title = self.line_title.get().strip() or 'Google Sheets Query Report'
        note = self.line_note.get().strip()
        if len(title)>120 or len(note)>300: raise ValueError('Limit title to 120 and note to 300 characters.')
        # LINE text is not guaranteed to use a monospace font.
        records = ['🔹 Record ' + str(i) + '\n' + '\n'.join(f'• {c}: {v or "—"}' for c,v in zip(self.result_df.columns,row))
                   for i,row in enumerate(self.result_df.itertuples(index=False,name=None),1)]
        return line_parts('📊 ' + title + '\n' + self.metadata + '\n' + note + '\n\n' + '\n\n'.join(records))

    def refresh_message(self):
        channel = self.tabs.get()
        self.preview_label.configure(text=channel + ' message preview')
        text = 'Run a query first.'
        if self.report_pages:
            try:
                if channel == 'Telegram': text = plain_report(self.custom_pages(self.tg_title.get(), self.tg_note.get()))
                elif channel == 'LINE': text = '\n\n--- Next message ---\n\n'.join(self.line_report())
                else: text = 'Subject: ' + self.subject.get() + '\nTo: ' + self.recipient.get() + '\n\n' + self.body.get('1.0','end-1c') + '\n\n' + self.metadata + '\n\nAttachments: ' + self.attachment.get()
            except ValueError as exc: text = str(exc)
        self.message.configure(state='normal'); self.message.delete('1.0','end'); self.message.insert('1.0',text); self.message.configure(state='disabled')

    def ready(self):
        if self.busy: return False
        if self.result_df is None or self.result_df.empty:
            messagebox.showinfo('Report', 'Run a query with matching records first.'); return False
        return True

    def send(self):
        if not self.ready(): return
        token,chat=self.token.get().strip(),self.chat.get().strip()
        if not token or not chat: messagebox.showwarning('Telegram','Enter bot token and chat ID.'); return
        try: pages = self.custom_pages(self.tg_title.get(), self.tg_note.get())
        except ValueError as exc: messagebox.showwarning('Telegram',str(exc)); return
        self.refresh_message()
        if not messagebox.askyesno('Confirm send',f'Send {len(pages)} message(s) to chat {chat}?'): return
        self.work('Sending to Telegram…',lambda:send_telegram(token,chat,pages),lambda result:self.status.configure(text=result))

    def line(self):
        if not self.ready(): return
        token, recipient, mode = self.line_token.get().strip(), self.line_recipient.get().strip(), self.line_mode.get()
        if not token or (mode == 'Push' and not recipient):
            messagebox.showwarning('LINE','Enter channel access token and recipient ID for push.'); return
        try: parts = self.line_report()
        except ValueError as exc: messagebox.showwarning('LINE',str(exc)); return
        self.refresh_message()
        target = 'ALL eligible followers (may consume message quota)' if mode == 'Broadcast' else recipient
        if not messagebox.askyesno('Confirm LINE send',f'Send {len(parts)} message(s) to {target}?', icon='warning'): return
        self.work('Sending to LINE…',lambda:send_line(token,recipient,mode,parts),lambda result:self.status.configure(text=result))

    def email(self):
        if not self.ready(): return
        key, sender, recipient = (w.get().strip() for w in (self.resend_key, self.sender, self.recipient))
        subject, body = self.subject.get().strip(), self.body.get('1.0','end-1c')
        if not key or not subject or not all(re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', v) for v in (sender, recipient)):
            messagebox.showwarning('Email', 'Enter API key, subject and valid sender and recipient addresses.'); return
        fmt = self.attachment.get()
        df, metadata = self.result_df.copy(), self.metadata
        self.refresh_message()
        if not messagebox.askyesno('Confirm email', f'Send {len(df)} records to {recipient}?\nSubject: {subject}\nAttachments: {fmt}'): return
        self.work('Sending email report…', lambda: send_email(key, sender, recipient, df, metadata, fmt, subject, body),
                  lambda result: self.status.configure(text=result))


if __name__=='__main__':
    ctk.set_appearance_mode('System')
    App().mainloop()
