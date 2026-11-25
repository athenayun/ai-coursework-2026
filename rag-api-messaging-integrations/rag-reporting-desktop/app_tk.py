"""Desktop UI for the existing ONNX RAG engine. macOS / tkinter."""
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import customtkinter as ctk
from telegram_messaging import send_telegram_message
from rag_engine import RAGSession, STRATEGIES, export_csv, export_docx
from report_delivery import format_report, send_line, send_email
from datetime import datetime

class App:
    def __init__(self, root):
        self.root = root
        root.title("Multi-Strategy RAG | Multi-channel reporting")
        root.geometry("1250x820")
        root.minsize(900, 650)
        self.rag = RAGSession()
        self.records = []
        self.events = queue.Queue()
        self.busy = False
        self.path = None

        main = ctk.CTkFrame(root, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=14, pady=14)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)
        left = ctk.CTkScrollableFrame(main, width=355, label_text="Configuration")
        left.grid(row=0, column=0, sticky="ns", padx=(0,12))
        right = ctk.CTkFrame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="Groq API key").pack(anchor="w")
        self.key = ctk.CTkEntry(left, width=270, show="•")
        self.key.pack(fill="x", pady=(4,8))
        if os.getenv("GROQ_API_KEY"):
            self.key.insert(0, os.environ["GROQ_API_KEY"])
        self.connect_btn = ctk.CTkButton(left, text="Connect / Fetch Models", command=self.connect)
        self.connect_btn.pack(fill="x", pady=(0,12))

        ctk.CTkLabel(left, text="Groq chat model").pack(anchor="w")
        self.model = ctk.CTkComboBox(left, state="readonly", width=270,
                                  values=["openai/gpt-oss-20b"])
        self.model.set("openai/gpt-oss-20b")
        self.model.pack(fill="x", pady=(4,12))

        ctk.CTkLabel(left, text="Document").pack(anchor="w")
        self.doc_label = ctk.CTkLabel(left, text="No file selected", wraplength=245)
        self.doc_label.pack(anchor="w", pady=5)
        ctk.CTkButton(left, text="Choose PDF / DOCX", command=self.choose_file).pack(fill="x")
        self.index_btn = ctk.CTkButton(left, text="Index Document", command=self.index)
        self.index_btn.pack(fill="x", pady=(6,14))

        ctk.CTkLabel(left, text="Retrieval strategy").pack(anchor="w")
        self.strategy = ctk.CTkComboBox(left, state="readonly", values=STRATEGIES)
        self.strategy.set("semantic")
        self.strategy.pack(fill="x", pady=(4,12))
        ctk.CTkLabel(left, text="Top-K").pack(anchor="w")
        self.k = tk.IntVar(value=3)
        ctk.CTkEntry(left, textvariable=self.k, width=80).pack(anchor="w", pady=(4,12))
        ctk.CTkFrame(left, height=2).pack(fill="x", pady=10)
        self.tabs = ctk.CTkTabview(left, command=self.refresh_preview)
        self.tabs.pack(fill="x", pady=8)
        self.fields = {}
        self.send_buttons = []
        for channel in ("LINE", "Telegram", "Email"):
            tab = self.tabs.add(channel)
            fields = self.fields[channel] = {}
            def field(name, default="", secret=False):
                ctk.CTkLabel(tab, text=name).pack(anchor="w")
                widget = ctk.CTkEntry(tab, show="•" if secret else "")
                widget.pack(fill="x", pady=(2,6))
                widget.insert(0, default)
                fields[name] = widget
            if channel == "LINE":
                field("Channel access token", os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""), True)
                fields["Mode"] = ctk.CTkComboBox(tab, values=["Push", "Broadcast"], state="readonly", command=self.line_mode_changed)
                fields["Mode"].set("Push")
                fields["Mode"].pack(fill="x", pady=4)
                field("Recipient ID")
            elif channel == "Telegram":
                field("Bot token", os.getenv("TELEGRAM_BOT_TOKEN", ""), True)
                field("Chat ID", os.getenv("TELEGRAM_CHAT_ID", ""))
            else:
                field("Resend API key", os.getenv("RESEND_API_KEY", ""), True)
                field("Sender email", "onboarding@resend.dev")
                field("Recipient email")
            field("Subject" if channel == "Email" else "Report title", "Document Q&A report")
            ctk.CTkLabel(tab, text="Message / introduction").pack(anchor="w")
            fields["Note"] = ctk.CTkTextbox(tab, height=75)
            fields["Note"].pack(fill="x", pady=4)
            for label, default in [("Include question", True), ("Include evidence", False)]:
                var = tk.BooleanVar(value=default)
                fields[label] = var
                ctk.CTkCheckBox(tab, text=label, variable=var, command=self.refresh_preview).pack(anchor="w", pady=3)
            if channel == "Email":
                ctk.CTkLabel(tab, text="Attachments").pack(anchor="w")
                fields["Attachments"] = ctk.CTkComboBox(tab, values=["Both", "CSV", "DOCX", "None"], state="readonly", command=lambda _: self.refresh_preview())
                fields["Attachments"].set("Both")
                fields["Attachments"].pack(fill="x")
            ctk.CTkButton(tab, text="Refresh preview", command=self.refresh_preview).pack(fill="x", pady=4)
            button = ctk.CTkButton(tab, text="Send to " + channel, command=lambda ch=channel: self.send_report(ch))
            button.pack(fill="x", pady=4)
            self.send_buttons.append(button)
        ctk.CTkButton(left, text="Export CSV", command=lambda: self.export("csv")).pack(fill="x", pady=3)
        ctk.CTkButton(left, text="Export DOCX", command=lambda: self.export("docx")).pack(fill="x", pady=3)
        ctk.CTkButton(left, text="Clear Chat", command=self.clear).pack(fill="x", pady=3)
        ctk.CTkLabel(left, text="Embeddings run locally (ONNX).\nRetrieved text is sent to Groq.\nNo Cohere key needed.",
                  wraplength=245, text_color=("#555555", "#bbbbbb")).pack(anchor="w", pady=(20,0))

        ctk.CTkLabel(right, text="Document Q&A", font=("Helvetica", 17, "bold")).grid(row=0,column=0,sticky="w",pady=(0,8))
        self.chat = scrolledtext.ScrolledText(right, wrap="word", state="disabled", font=("Helvetica", 12))
        self.chat.grid(row=1,column=0,sticky="nsew")
        self.chat.tag_configure("user", foreground="#155b9b", font=("Helvetica",12,"bold"))
        self.chat.tag_configure("assistant", foreground="#197447", font=("Helvetica",12,"bold"))

        qrow = ctk.CTkFrame(right)
        qrow.grid(row=2,column=0,sticky="ew",pady=(10,8))
        qrow.columnconfigure(0,weight=1)
        self.question = ctk.CTkEntry(qrow)
        self.question.grid(row=0,column=0,sticky="ew",padx=(0,8))
        self.question.bind("<Return>",lambda e:self.ask())
        self.ask_btn = ctk.CTkButton(qrow,text="Ask",command=self.ask)
        self.ask_btn.grid(row=0,column=1)

        ctk.CTkLabel(right,text="Retrieved evidence").grid(row=3,column=0,sticky="w")
        self.evidence = scrolledtext.ScrolledText(right, height=8, wrap="word", font=("Helvetica",10))
        self.evidence.grid(row=4,column=0,sticky="ew")
        self.evidence.configure(state="disabled")
        ctk.CTkLabel(right, text="Activity log (indexing progress)").grid(row=5,column=0,sticky="w",pady=(8,0))
        self.log_widget = scrolledtext.ScrolledText(right, height=7, wrap="word", font=("Menlo",10))
        self.log_widget.grid(row=6,column=0,sticky="ew")
        self.log_widget.configure(state="disabled")
        ctk.CTkLabel(right, text="Delivery preview (latest answer)").grid(row=7,column=0,sticky="w")
        self.preview = scrolledtext.ScrolledText(right, height=7, wrap="word", state="disabled")
        self.preview.grid(row=8,column=0,sticky="ew")
        self.started_at = None
        self.status = tk.StringVar(value="Ready. Connect to Groq and index a document.")
        ctk.CTkLabel(root,textvariable=self.status,anchor="w").pack(fill="x")
        root.after(100,self.poll)

    def work(self, label, task, success):
        if self.busy: return
        self.busy=True
        self.status.set(label)
        self.log(label)
        self.started_at = time.monotonic()
        self.connect_btn.configure(state="disabled")
        self.index_btn.configure(state="disabled")
        self.ask_btn.configure(state="disabled")
        for button in self.send_buttons: button.configure(state="disabled")
        def runner():
            try: self.events.put(("ok",success,task()))
            except Exception as exc: self.events.put(("error",str(exc)))
        threading.Thread(target=runner,daemon=True).start()

    def log(self, message):
        stamp=time.strftime("%H:%M:%S")
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end",f"[{stamp}] {message}\n")
        self.log_widget.configure(state="disabled")
        self.log_widget.see("end")
        print(f"[{stamp}] {message}",flush=True)

    def poll(self):
        try:
            while True:
                msg=self.events.get_nowait()
                if msg[0]=="progress":
                    self.log(msg[1])
                    self.status.set(msg[1])
                    continue
                self.busy=False
                elapsed=time.monotonic()-self.started_at if self.started_at else 0
                self.log(f"{'FAILED' if msg[0]=='error' else 'FINISHED'} after {elapsed:.1f}s: {msg[1] if msg[0]=='error' else 'OK'}")
                self.connect_btn.configure(state="normal")
                self.index_btn.configure(state="normal")
                self.ask_btn.configure(state="normal")
                for button in self.send_buttons: button.configure(state="normal")
                if msg[0]=="error":
                    self.status.set("Error: "+msg[1])
                    messagebox.showerror("RAG error",msg[1])
                else:
                    try: msg[1](msg[2])
                    except Exception as exc:
                        self.status.set("UI error: "+str(exc))
                        messagebox.showerror("UI error",str(exc))
        except queue.Empty: pass
        self.root.after(100,self.poll)

    def connect(self):
        key=self.key.get().strip()
        if not key:
            messagebox.showwarning("API key","Enter your Groq API key first.")
            return
        self.rag.groq_key=key
        def success(models):
            chosen="openai/gpt-oss-20b" if "openai/gpt-oss-20b" in models else models[0]
            self.model.configure(values=models)
            self.model.set(chosen)
            self.status.set("Connected to Groq. Selected "+chosen)
        self.work("Fetching available models...",self.rag.models,success)

    def choose_file(self):
        path=filedialog.askopenfilename(filetypes=[("Documents","*.pdf *.docx"),("PDF","*.pdf"),("Word","*.docx")])
        if path:
            self.path=path
            self.doc_label.configure(text=Path(path).name)

    def index(self):
        if not self.path:
            messagebox.showwarning("Document","Choose a PDF or DOCX first.")
            return
        path=self.path
        def success(msg):
            self.records=[]
            self._replace(self.chat,"")
            self._replace(self.evidence,"")
            self.refresh_preview()
            self.status.set(msg)
        self.work("Indexing document (first model download may take time)...",
                  lambda:self.rag.load(path,Path(path).name,
                      progress=lambda message:self.events.put(("progress",message))),success)

    def ask(self):
        if self.busy: return
        q=self.question.get().strip()
        if not q: return
        strategy=self.strategy.get()
        model=self.model.get()
        try: k=int(self.k.get())
        except (ValueError,tk.TclError): k=3
        self.rag.model=model
        history=list(self.records)
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        def task():
            start = time.perf_counter()
            answer, sources = self.rag.answer(q,strategy,k,history)
            return answer, sources, time.perf_counter()-start
        def success(result):
            answer,sources,duration=result
            self.records.append(dict(question=q,answer=answer,strategy=strategy,model=model,sources=sources,timestamp=timestamp,duration=duration))
            self._append("You",q,"user")
            self._append("Assistant",answer,"assistant")
            self._replace(self.evidence,"\n\n".join(
                f"[{s['id']}] {s['location']}\n{s['text']}" for s in sources))
            self.question.delete(0,"end")
            self.refresh_preview()
            self.status.set(f"Answer generated in {duration:.3f} s.")
        self.work("Retrieving evidence and generating answer...",
                  task,success)

    def line_mode_changed(self, mode):
        self.fields["LINE"]["Recipient ID"].configure(state="normal" if mode == "Push" else "disabled")
        self.refresh_preview()

    def report_text(self, channel):
        f = self.fields[channel]
        title = f["Subject" if channel == "Email" else "Report title"].get().strip()
        return format_report(self.records[-1], title, f["Note"].get("1.0", "end").strip(),
                             f["Include question"].get(), f["Include evidence"].get())

    def refresh_preview(self):
        if not hasattr(self, "preview"): return
        channel = self.tabs.get()
        text = self.report_text(channel) if self.records else "Generate an answer first."
        if self.records and channel == "Email":
            text += "\n\nAttachments: " + self.fields[channel]["Attachments"].get()
        self._replace(self.preview, text)

    def send_report(self, channel):
        if self.busy: return
        if not self.records:
            messagebox.showinfo("No answer", "Generate an answer first.")
            return
        f = self.fields[channel]
        text = self.report_text(channel)
        self.refresh_preview()
        if channel == "LINE":
            token, mode, recipient = (f[k].get().strip() for k in ("Channel access token", "Mode", "Recipient ID"))
            if not token or (mode == "Push" and not recipient):
                messagebox.showwarning(channel, "Enter token and recipient for Push."); return
            target = "ALL eligible followers (broadcast; may consume quota)" if mode == "Broadcast" else recipient
            task = lambda: send_line(token, mode, recipient, text)
        elif channel == "Telegram":
            token, target = (f[k].get().strip() for k in ("Bot token", "Chat ID"))
            if not token or not target:
                messagebox.showwarning(channel, "Enter bot token and chat ID."); return
            task = lambda: send_telegram_message(token, target, text)
        else:
            key, sender, target, subject, attachment = (f[k].get().strip() for k in ("Resend API key", "Sender email", "Recipient email", "Subject", "Attachments"))
            if not all((key, sender, target, subject)):
                messagebox.showwarning(channel, "Enter API key, sender, recipient and subject."); return
            record = dict(self.records[-1])
            # Do not include omitted question/evidence in attachments.
            if not f["Include question"].get(): record["question"] = ""
            if not f["Include evidence"].get(): record["sources"] = []
            task = lambda: send_email(key, sender, target, subject, text, record, attachment)
        if not messagebox.askyesno("Confirm delivery", f"Send latest report via {channel} to {target}?\n\nReview the delivery preview before confirming.", icon="warning"):
            return
        self.work("Sending report via " + channel + "...", task,
                  lambda result: (self.status.set(result), self.log(result)))

    def _append(self,who,content,tag):
        self.chat.configure(state="normal")
        self.chat.insert("end",who+":\n",tag)
        self.chat.insert("end",content+"\n\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _replace(self,widget,text):
        widget.configure(state="normal")
        widget.delete("1.0","end")
        widget.insert("1.0",text)
        widget.configure(state="disabled")

    def clear(self):
        if self.busy: return
        self.records=[]
        self._replace(self.chat,"")
        self._replace(self.evidence,"")
        self.refresh_preview()
        self.status.set("Chat cleared. Document index retained.")

    def export(self,fmt):
        if not self.records:
            messagebox.showinfo("No results","Ask at least one question first.")
            return
        path=filedialog.asksaveasfilename(defaultextension="."+fmt,
            filetypes=[("CSV","*.csv")] if fmt=="csv" else [("Word Document","*.docx")],
            initialfile="rag_chat."+fmt)
        if not path: return
        data=export_csv(self.records) if fmt=="csv" else export_docx(self.records)
        Path(path).write_bytes(data)
        self.status.set("Exported "+path)

if __name__=="__main__":
    ctk.set_appearance_mode("System")
    root=ctk.CTk()
    App(root)
    root.mainloop()
