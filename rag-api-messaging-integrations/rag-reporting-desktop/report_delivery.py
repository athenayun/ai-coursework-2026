"""Format and deliver a reviewed RAG answer; never log credentials."""
import base64
import requests
from rag_engine import export_csv, export_docx


def format_report(record, title, note, question=True, sources=False):
    parts = [title or 'Document Q&A report', note,
             f"Query time: {record['timestamp']}\nDuration: {record['duration']:.3f} s\nModel: {record['model']}\nRetrieval: {record['strategy']}"]
    if question:
        parts.append('Question:\n' + record['question'])
    parts.append('Answer:\n' + record['answer'])
    if sources:
        parts.append('Retrieved evidence:\n' + '\n\n'.join(f"[{s['id']}] {s['location']}\n{s['text']}" for s in record['sources']))
    return '\n\n'.join(p for p in parts if p)


def post(url, token, payload, service):
    try:
        response = requests.post(url, headers={'Authorization': 'Bearer ' + token}, json=payload, timeout=40)
    except requests.RequestException:
        raise RuntimeError(f'{service} network error; delivery status unknown.') from None
    if not response.ok:
        raise RuntimeError(f'{service} rejected request (HTTP {response.status_code}). Check credentials, permissions and quota.')
    return response


def send_line(token, mode, recipient, text):
    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
    accepted = 0
    for i in range(0, len(chunks), 5):
        batch = chunks[i:i+5]
        payload = {'messages': [{'type':'text','text':s} for s in batch]}
        if mode == 'Push':
            payload['to'] = recipient
        try:
            post('https://api.line.me/v2/bot/message/' + mode.lower(), token, payload, 'LINE')
        except RuntimeError as exc:
            raise RuntimeError(f'{exc} {accepted} earlier message parts accepted.') from None
        accepted += len(batch)
    return f'LINE accepted {accepted} message part(s); delivery not guaranteed.'


def send_email(key, sender, recipient, subject, text, record, attachment):
    files = []
    # Include metadata in the attachment without changing the original engine.
    report = dict(record, answer=text)
    for fmt, exporter in [('csv', export_csv), ('docx', export_docx)]:
        if attachment in ('Both', fmt.upper()):
            files.append({'filename': 'rag_report.'+fmt, 'content': base64.b64encode(exporter([report])).decode('ascii')})
    payload = {'from':sender, 'to':[recipient], 'subject':subject, 'text':text, 'attachments':files}
    post('https://api.resend.com/emails', key, payload, 'Resend')
    return 'Resend accepted email request; delivery not guaranteed.'
