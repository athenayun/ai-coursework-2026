"""Desktop UI for the existing ONNX RAG engine. macOS / tkinter."""
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from rag_engine import RAGSession, STRATEGIES, export_csv, export_docx
from line_messaging import send_line_message, prepare_message

class App:
    def __init__(self, root):
        self.root = root
        root.title("Multi-Strategy RAG — macOS Desktop")
        root.geometry("1100x720")
        root.minsize(900, 650)
        self.rag = RAGSession()
        self.records = []
        self.events = queue.Queue()
        self.busy = False
        self.path = None

        main = ttk.Frame(root, padding=14)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(main, width=315)
        sidebar.grid(row=0, column=0, sticky="ns", padx=(0,12))
        sidebar.grid_propagate(False)
        canvas = tk.Canvas(sidebar, highlightthickness=0, width=295)
        scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        left = ttk.LabelFrame(canvas, text="Configuration", padding=12)
        window_id = canvas.create_window((0,0), window=left, anchor="nw")
        left.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        def wheel(event):
            if event.delta: canvas.yview_scroll(-int(event.delta), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(left, text="Groq API key").pack(anchor="w")
        self.key = ttk.Entry(left, width=37, show="•")
        self.key.pack(fill="x", pady=(4,8))
        if os.getenv("GROQ_API_KEY"):
            self.key.insert(0, os.environ["GROQ_API_KEY"])
        self.connect_btn = ttk.Button(left, text="Connect / Fetch Models", command=self.connect)
        self.connect_btn.pack(fill="x", pady=(0,12))

        ttk.Label(left, text="Groq chat model").pack(anchor="w")
        self.model = ttk.Combobox(left, state="readonly", width=35,
                                  values=["openai/gpt-oss-20b"])
        self.model.set("openai/gpt-oss-20b")
        self.model.pack(fill="x", pady=(4,12))

        ttk.Label(left, text="Document").pack(anchor="w")
        self.doc_label = ttk.Label(left, text="No file selected", wraplength=245)
        self.doc_label.pack(anchor="w", pady=5)
        ttk.Button(left, text="Choose PDF / DOCX", command=self.choose_file).pack(fill="x")
        self.index_btn = ttk.Button(left, text="Index Document", command=self.index)
        self.index_btn.pack(fill="x", pady=(6,14))

        ttk.Label(left, text="Retrieval strategy").pack(anchor="w")
        self.strategy = ttk.Combobox(left, state="readonly", values=STRATEGIES)
        self.strategy.set("semantic")
        self.strategy.pack(fill="x", pady=(4,12))
        ttk.Label(left, text="Top-K").pack(anchor="w")
        self.k = tk.IntVar(value=3)
        ttk.Spinbox(left, from_=1, to=6, textvariable=self.k, width=8).pack(anchor="w", pady=(4,12))
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="LINE Messaging API", font=("Helvetica", 12, "bold")).pack(anchor="w")
        ttk.Label(left, text="Channel access token").pack(anchor="w", pady=(8, 0))
        self.line_token = ttk.Entry(left, width=37, show="•")
        self.line_token.pack(fill="x", pady=(3, 7))
        if os.getenv("LINE_CHANNEL_ACCESS_TOKEN"):
            self.line_token.insert(0, os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
        self.send_line_btn = ttk.Button(left, text="Broadcast Last Answer to LINE", command=self.send_last_to_line)
        self.send_line_btn.pack(fill="x", pady=(4, 8))
        ttk.Label(left, text="Broadcasts up to 500 characters to ALL eligible followers.\nNo webhook or recipient ID needed.",
                  wraplength=245, foreground="#555").pack(anchor="w")
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Button(left, text="Export CSV", command=lambda: self.export("csv")).pack(fill="x", pady=3)
        ttk.Button(left, text="Export DOCX", command=lambda: self.export("docx")).pack(fill="x", pady=3)
        ttk.Button(left, text="Clear Chat", command=self.clear).pack(fill="x", pady=3)
        ttk.Label(left, text="Embeddings run locally (ONNX).\nRetrieved text is sent to Groq.\nNo Cohere key needed.",
                  wraplength=245, foreground="#555").pack(anchor="w", pady=(20,0))

        ttk.Label(right, text="Document Q&A", font=("Helvetica", 17, "bold")).grid(row=0,column=0,sticky="w",pady=(0,8))
        self.chat = scrolledtext.ScrolledText(right, wrap="word", state="disabled", font=("Helvetica", 12))
        self.chat.grid(row=1,column=0,sticky="nsew")
        self.chat.tag_configure("user", foreground="#155b9b", font=("Helvetica",12,"bold"))
        self.chat.tag_configure("assistant", foreground="#197447", font=("Helvetica",12,"bold"))

        qrow = ttk.Frame(right)
        qrow.grid(row=2,column=0,sticky="ew",pady=(10,8))
        qrow.columnconfigure(0,weight=1)
        self.question = ttk.Entry(qrow)
        self.question.grid(row=0,column=0,sticky="ew",padx=(0,8))
        self.question.bind("<Return>",lambda e:self.ask())
        self.ask_btn = ttk.Button(qrow,text="Ask",command=self.ask)
        self.ask_btn.grid(row=0,column=1)

        ttk.Label(right,text="Retrieved evidence").grid(row=3,column=0,sticky="w")
        self.evidence = scrolledtext.ScrolledText(right, height=8, wrap="word", font=("Helvetica",10))
        self.evidence.grid(row=4,column=0,sticky="ew")
        self.evidence.configure(state="disabled")
        ttk.Label(right, text="Activity log (indexing progress)").grid(row=5,column=0,sticky="w",pady=(8,0))
        self.log_widget = scrolledtext.ScrolledText(right, height=7, wrap="word", font=("Menlo",10))
        self.log_widget.grid(row=6,column=0,sticky="ew")
        self.log_widget.configure(state="disabled")
        self.started_at = None
        self.status = tk.StringVar(value="Ready. Connect to Groq and index a document.")
        ttk.Label(root,textvariable=self.status,anchor="w",padding=(14,6)).pack(fill="x")
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
        self.send_line_btn.configure(state="disabled")
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
                self.send_line_btn.configure(state="normal")
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
            self.status.set(msg)
        self.work("Indexing document (first model download may take time)...",
                  lambda:self.rag.load(path,Path(path).name,
                      progress=lambda message:self.events.put(("progress",message))),success)

    def ask(self):
        q=self.question.get().strip()
        if not q: return
        strategy=self.strategy.get()
        model=self.model.get()
        try: k=int(self.k.get())
        except (ValueError,tk.TclError): k=3
        self.rag.model=model
        history=list(self.records)
        def success(result):
            answer,sources=result
            self.records.append(dict(question=q,answer=answer,strategy=strategy,model=model,sources=sources))
            self._append("You",q,"user")
            self._append("Assistant",answer,"assistant")
            self._replace(self.evidence,"\n\n".join(
                f"[{s['id']}] {s['location']}\n{s['text']}" for s in sources))
            self.question.delete(0,"end")
            self.status.set("Answer generated.")
        self.work("Retrieving evidence and generating answer...",
                  lambda:self.rag.answer(q,strategy,k,history),success)

    def send_last_to_line(self):
        if self.busy:
            return
        if not self.records:
            messagebox.showinfo("No answer", "Ask a question before broadcasting to LINE.")
            return
        token = self.line_token.get().strip()
        if not token:
            messagebox.showwarning("LINE settings", "Enter your LINE channel access token.")
            return
        answer = self.records[-1]["answer"]
        try:
            preview = prepare_message(answer)
        except ValueError as exc:
            messagebox.showerror("Invalid message", str(exc))
            return
        confirmed = messagebox.askyesno(
            "Confirm LINE broadcast",
            "This will send the same answer to ALL eligible followers of your LINE Official Account.\n"
            "It is NOT a private reply. It may use your monthly message quota.\n\n"
            f"Message ({len(preview)} characters):\n\n{preview[:400]}"
            + ("…" if len(preview) > 400 else "")
            + "\n\nBroadcast now?",
            icon="warning",
        )
        if not confirmed:
            self.status.set("LINE broadcast cancelled.")
            return
        self.work("Broadcasting answer to LINE...",
                  lambda: send_line_message(answer, token),
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
        self.records=[]
        self._replace(self.chat,"")
        self._replace(self.evidence,"")
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
    root=tk.Tk()
    App(root)
    root.mainloop()
