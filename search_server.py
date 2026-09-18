"""
Pi Search web app.

Usage:
    python search_server.py --file pi_300m.txt
    (then open http://localhost:5000 in your browser)

Uses mmap so the OS pages the file in on demand instead of Python doubling
memory by loading it as a separate string — works fine at 300M digits and
scales cleanly to 1B+ without code changes.
"""
import argparse
import mmap
import re
import time
import os
from flask import Flask, jsonify, request, Response

app = Flask(__name__)
DATA = {}
def load_pi_file(path):
    f = open(path, "rb")
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    DATA["mmap"] = mm
    DATA["total"] = len(mm) - 1
    print(f"Loaded {DATA['total']:,} digits from {path}")


PI_FILE = os.environ.get("PI_FILE", "pi_300m.txt")
load_pi_file(PI_FILE)

PAGE = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Pi Search</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 700px;
         margin: 60px auto; padding: 0 20px; color: #222; }
  h1 { font-size: 1.6rem; }
  input { font-size: 1.1rem; padding: 10px 14px; width: 100%; box-sizing: border-box;
          border: 1px solid #ccc; border-radius: 8px; }
  #result { margin-top: 24px; line-height: 1.6; }
  .pos { font-weight: 600; color: #0a6b3d; }
  .ctx { font-family: ui-monospace, Menlo, monospace; background: #f4f4f4;
         padding: 10px; border-radius: 8px; word-break: break-all; }
  .hi { background: #ffe38a; }
  .meta { color: #777; font-size: 0.9rem; margin-top: 6px; }
</style>
</head>
<body>
  <h1>🥧 Pi Search — {{TOTAL}} digits</h1>
  <p>Type any sequence of digits and find where it first occurs in pi.</p>
  <input id="q" placeholder="e.g. your birthday, 141592, phone number..."
         inputmode="numeric" pattern="[0-9]*" autocomplete="off" autofocus>
  <div id="result"></div>

<script>
const input = document.getElementById('q');
const resultDiv = document.getElementById('result');
let debounceTimer = null;
let requestSeq = 0;

input.addEventListener('input', () => {
  const digitsOnly = input.value.replace(/\D/g, '');
  if (digitsOnly !== input.value) input.value = digitsOnly;
  clearTimeout(debounceTimer);
  if (!digitsOnly) {
    resultDiv.innerHTML = '';
    return;
  }
  debounceTimer = setTimeout(doSearch, 150);
});

// Belt-and-suspenders: block non-digit keys outright (input listener above
// also strips paste/autofill/IME text that keydown never sees).
input.addEventListener('keydown', e => {
  if (e.key === 'Enter') { clearTimeout(debounceTimer); doSearch(); return; }
  const allowed = ['Backspace', 'Delete', 'Tab', 'ArrowLeft', 'ArrowRight',
                    'ArrowUp', 'ArrowDown', 'Home', 'End'];
  if (allowed.includes(e.key) || e.ctrlKey || e.metaKey) return;
  if (!/^\d$/.test(e.key)) e.preventDefault();
});

async function doSearch() {
  const q = input.value.trim();
  if (!q) { resultDiv.innerHTML = ''; return; }
  const mySeq = ++requestSeq;
  const t0 = performance.now();
  const res = await fetch('/api/search?q=' + encodeURIComponent(q));
  const data = await res.json();
  if (mySeq !== requestSeq) return; // a newer keystroke already superseded this
  const ms = (performance.now() - t0).toFixed(1);
  if (!data.found) {
    resultDiv.innerHTML = `<p>"${q}" was not found. (${data.error || ''})</p>`;
    return;
  }
  resultDiv.innerHTML = `
    <p>Found at digit position <span class="pos">${data.position.toLocaleString()}</span>.</p>
    <div class="ctx">${data.context_before}<span class="hi">${data.match}</span>${data.context_after}</div>
    <div class="meta">query answered in ${ms} ms (server-side search: ${data.server_ms} ms)</div>
  `;
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    html = PAGE.replace("{{TOTAL}}", f"{DATA['total']:,}")
    return Response(html, mimetype="text/html")


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not re.fullmatch(r"\d+", q or ""):
        return jsonify(found=False, error="query must be digits only")
    if len(q) > 1000:
        return jsonify(found=False, error="query too long")

    needle = q.encode()
    t0 = time.time()
    mm = DATA["mmap"]
    idx = mm.find(needle)
    server_ms = round((time.time() - t0) * 1000, 2)

    if idx == -1:
        return jsonify(found=False, error="not found in the generated range", server_ms=server_ms)

    ctx_before = mm[max(0, idx - 15):idx].decode()
    ctx_after = mm[idx + len(needle): idx + len(needle) + 15].decode()
    return jsonify(
        found=True,
        position=idx - 1,  # digits-after-decimal index; mm[0] is the leading "3"
        match=q,
        context_before=ctx_before,
        context_after=ctx_after,
        server_ms=server_ms,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=PI_FILE, help="path to the generated digits text file")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()

    if args.file != PI_FILE:
        load_pi_file(args.file)

    print(f"Open http://localhost:{args.port} in your browser")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
