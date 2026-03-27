#!/usr/bin/env python3
import argparse, pandas as pd, json, html, math
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--excel",  default="/Users/raphaelbruno/Documents/Prospeção - Agente AI/Restaurantes Peniche Enriched.xlsx")
parser.add_argument("--output", default="/Users/raphaelbruno/Documents/Prospeção - Agente AI/restaurantes.html")
args, _ = parser.parse_known_args()

EXCEL = args.excel
OUT   = args.output

df = pd.read_excel(EXCEL)
df = df.where(pd.notna(df), None)

def clean(v):
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    return v

records = []
for _, row in df.iterrows():
    records.append({k: clean(v) for k, v in row.items()})

data_json = json.dumps(records, ensure_ascii=True, default=str)

def e(v): return html.escape(str(v or ''))

# Stats
total = len(df)
with_ig = df['Instagram Handle'].notna().sum()
with_phone = df['Phone'].notna().sum()
takeaway = df['Takeaway Signal'].sum()
avg_score = round(df['Score AI Potencial'].mean(), 1)

# Table rows
rows_html = ""
for i, row in df.iterrows():
    name = row.get('Business Name') or ''
    handle = row.get('Instagram Handle') or ''
    ig_url = row.get('Instagram URL') or ''
    followers = row.get('Seguidores')
    reviews = row.get('# Reviews')
    rating = row.get('Rating')
    phone = row.get('Phone'); phone = str(phone) if phone and str(phone) != 'nan' else ''
    score = row.get('Score AI Potencial') or 0
    status = row.get('Status Lead') or 'Cold'
    takeaway_sig = row.get('Takeaway Signal')
    website = row.get('Website') or ''

    followers_str = f"{int(followers):,}".replace(',','.') if followers and str(followers)!='nan' else '—'
    reviews_str = f"{int(reviews):,}".replace(',','.') if reviews and str(reviews)!='nan' else '—'
    rating_str = f"{float(rating):.1f}" if rating and str(rating)!='nan' else '—'

    score_color = '#22c55e' if score>=80 else '#f59e0b' if score>=50 else '#ef4444'
    status_badge = {'Cold':'#6b7280','Contacted':'#3b82f6','Interested':'#f59e0b','Client':'#22c55e'}.get(status,'#6b7280')
    ta_icon = '🛵' if takeaway_sig else ''

    ig_cell = f'<a href="{e(ig_url)}" target="_blank" style="color:#e1306c;text-decoration:none">{e(handle)}</a>' if handle else '—'
    ph_cell = f'<a href="https://wa.me/{phone.replace("+","").replace(" ","")}" target="_blank" style="color:#25d366;text-decoration:none">{e(phone)}</a>' if phone else '—'
    web_cell = f'<a href="{e(website)}" target="_blank" style="color:#60a5fa;text-decoration:none">↗</a>' if website else ''

    rows_html += f'''<tr class="row" data-name="{e(name)}" data-handle="{e(handle)}" data-status="{e(status)}" data-ig="{'yes' if handle else 'no'}" data-ta="{'yes' if takeaway_sig else 'no'}" onclick="openModal({i})" style="cursor:pointer">
      <td style="padding:10px 8px;font-size:13px;font-weight:500">{ta_icon} {e(name)} {web_cell}</td>
      <td style="padding:10px 8px;font-size:12px">{ig_cell}</td>
      <td style="padding:10px 8px;font-size:12px;text-align:right">{followers_str}</td>
      <td style="padding:10px 8px;font-size:12px;text-align:right">{reviews_str}</td>
      <td style="padding:10px 8px;font-size:12px;text-align:center">{rating_str}</td>
      <td style="padding:10px 8px;font-size:12px">{ph_cell}</td>
      <td style="padding:10px 8px;text-align:center"><span style="background:{score_color};color:white;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:700">{int(score)}</span></td>
      <td style="padding:10px 8px;text-align:center"><span style="background:{status_badge};color:white;padding:2px 8px;border-radius:12px;font-size:11px">{e(status)}</span></td>
    </tr>'''

html_content = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Restaurantes Peniche — AI Agent Leads</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0 }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#0f172a; color:#e2e8f0; min-height:100vh }}
.header {{ background:#1e293b; padding:20px 24px; position:sticky; top:0; z-index:100; border-bottom:1px solid #334155 }}
.header h1 {{ font-size:20px; font-weight:700; color:#f8fafc; margin-bottom:12px }}
.stats {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:14px }}
.stat {{ background:#0f172a; border-radius:8px; padding:8px 14px; font-size:12px; color:#94a3b8 }}
.stat b {{ color:#f8fafc; font-size:16px; display:block }}
.filters {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center }}
.filters input, .filters select {{ background:#0f172a; border:1px solid #334155; color:#e2e8f0; padding:7px 12px; border-radius:6px; font-size:13px; outline:none }}
.filters input:focus, .filters select:focus {{ border-color:#6366f1 }}
table {{ width:100%; border-collapse:collapse }}
thead th {{ background:#1e293b; padding:10px 8px; font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:#64748b; text-align:left; position:sticky; top:0 }}
tbody tr:hover {{ background:#1e293b }}
tbody tr:nth-child(even) {{ background:#0f172a80 }}
.modal-bg {{ display:none; position:fixed; inset:0; background:#00000088; z-index:200; align-items:center; justify-content:center }}
.modal-bg.open {{ display:flex }}
.modal {{ background:#1e293b; border-radius:12px; padding:28px; max-width:520px; width:90%; max-height:85vh; overflow-y:auto; position:relative }}
.modal h2 {{ font-size:18px; margin-bottom:16px; color:#f8fafc }}
.modal-row {{ display:flex; justify-content:space-between; padding:7px 0; border-bottom:1px solid #334155; font-size:13px }}
.modal-row .label {{ color:#64748b }}
.modal-row .val {{ color:#e2e8f0; text-align:right; max-width:60% }}
.modal-close {{ position:absolute; top:14px; right:18px; background:none; border:none; color:#94a3b8; font-size:22px; cursor:pointer }}
.modal-status {{ margin-top:14px }}
.modal-status select {{ width:100%; background:#0f172a; border:1px solid #334155; color:#e2e8f0; padding:8px; border-radius:6px; font-size:13px }}
.modal-bio {{ margin-top:10px; background:#0f172a; border-radius:6px; padding:10px; font-size:12px; color:#94a3b8; line-height:1.5 }}
a {{ color:#60a5fa }}
</style>
</head>
<body>
<div class="header">
  <h1>🍽️ Restaurantes Peniche — AI Agent Leads</h1>
  <div class="stats">
    <div class="stat"><b>{total}</b>Total</div>
    <div class="stat"><b>{with_ig}</b>Instagram</div>
    <div class="stat"><b>{int(takeaway)}</b>Takeaway</div>
    <div class="stat"><b>{with_phone}</b>Telefone</div>
    <div class="stat"><b>{avg_score}</b>Score médio</div>
  </div>
  <div class="filters">
    <input type="text" id="search" placeholder="🔍 Pesquisar..." oninput="filter()" style="width:200px">
    <select id="filterStatus" onchange="filter()">
      <option value="">Todos os status</option>
      <option value="Cold">Cold</option>
      <option value="Contacted">Contacted</option>
      <option value="Interested">Interested</option>
      <option value="Client">Client</option>
    </select>
    <select id="filterIG" onchange="filter()">
      <option value="">Com/Sem Instagram</option>
      <option value="yes">Com Instagram</option>
      <option value="no">Sem Instagram</option>
    </select>
    <select id="filterTA" onchange="filter()">
      <option value="">Todos</option>
      <option value="yes">🛵 Takeaway/Delivery</option>
      <option value="no">Sem delivery</option>
    </select>
    <select id="sortBy" onchange="filter()">
      <option value="score">Score AI</option>
      <option value="reviews">Reviews</option>
      <option value="followers">Seguidores</option>
      <option value="rating">Rating</option>
    </select>
  </div>
</div>
<div style="overflow-x:auto">
<table>
  <thead><tr>
    <th>Restaurante</th><th>Instagram</th><th style="text-align:right">Seguidores</th>
    <th style="text-align:right">Reviews</th><th style="text-align:center">Rating</th>
    <th>Telefone</th><th style="text-align:center">Score AI</th><th style="text-align:center">Status</th>
  </tr></thead>
  <tbody id="tbody">{rows_html}</tbody>
</table>
</div>

<div class="modal-bg" id="modal" onclick="closeModal(event)">
  <div class="modal" id="modal-box">
    <button class="modal-close" onclick="document.getElementById('modal').classList.remove('open')">×</button>
    <h2 id="m-name"></h2>
    <div id="m-rows"></div>
    <div class="modal-bio" id="m-bio" style="display:none"></div>
    <div class="modal-status">
      <select id="m-status" onchange="updateStatus()">
        <option>Cold</option><option>Contacted</option><option>Interested</option><option>Client</option>
      </select>
    </div>
  </div>
</div>

<script>
var DATA = {data_json};
var currentIdx = null;
var statuses = DATA.map(function(r){{ return r['Status Lead'] || 'Cold'; }});

function filter() {{
  var q = document.getElementById('search').value.toLowerCase();
  var st = document.getElementById('filterStatus').value;
  var ig = document.getElementById('filterIG').value;
  var ta = document.getElementById('filterTA').value;
  var sort = document.getElementById('sortBy').value;
  var rows = Array.from(document.querySelectorAll('#tbody .row'));
  var visible = rows.filter(function(r) {{
    if (q && r.dataset.name.toLowerCase().indexOf(q) === -1) return false;
    if (st && r.dataset.status !== st) return false;
    if (ig && r.dataset.ig !== ig) return false;
    if (ta && r.dataset.ta !== ta) return false;
    return true;
  }});
  rows.forEach(function(r){{ r.style.display='none'; }});
  var sortFn = {{
    score: function(a,b){{ return (DATA[b.rowIndex-1]['Score AI Potencial']||0)-(DATA[a.rowIndex-1]['Score AI Potencial']||0); }},
    reviews: function(a,b){{ return (DATA[b.rowIndex-1]['# Reviews']||0)-(DATA[a.rowIndex-1]['# Reviews']||0); }},
    followers: function(a,b){{ return (DATA[b.rowIndex-1]['Seguidores']||0)-(DATA[a.rowIndex-1]['Seguidores']||0); }},
    rating: function(a,b){{ return (DATA[b.rowIndex-1]['Rating']||0)-(DATA[a.rowIndex-1]['Rating']||0); }},
  }}[sort];
  visible.sort(sortFn);
  var tbody = document.getElementById('tbody');
  visible.forEach(function(r){{ r.style.display=''; tbody.appendChild(r); }});
}}

function openModal(i) {{
  currentIdx = i;
  var r = DATA[i];
  document.getElementById('m-name').textContent = r['Business Name'] || '';
  var rows = [
    ['Category', r['Category']],
    ['Address', r['Address']],
    ['Rating', r['Rating'] ? r['Rating'] + ' ⭐' : '—'],
    ['Reviews', r['# Reviews'] ? r['# Reviews'].toLocaleString('pt') : '—'],
    ['Score AI', r['Score AI Potencial']],
    ['Takeaway', r['Takeaway Signal'] ? '🛵 Sim' : 'Não'],
    ['Telefone', r['Phone'] || '—'],
    ['Instagram', r['Instagram Handle'] || '—'],
    ['Seguidores', r['Seguidores'] ? r['Seguidores'].toLocaleString('pt') : '—'],
    ['Posts', r['Posts'] || '—'],
    ['Website', r['Website'] ? '<a href="'+r['Website']+'" target="_blank">'+r['Website']+'</a>' : '—'],
  ];
  document.getElementById('m-rows').innerHTML = rows.map(function(x){{
    return '<div class="modal-row"><span class="label">'+x[0]+'</span><span class="val">'+x[1]+'</span></div>';
  }}).join('');
  var bio = r['Bio'];
  var bioEl = document.getElementById('m-bio');
  if (bio) {{ bioEl.textContent = bio; bioEl.style.display='block'; }} else {{ bioEl.style.display='none'; }}
  var sel = document.getElementById('m-status');
  sel.value = statuses[i];
  document.getElementById('modal').classList.add('open');
}}

function closeModal(e) {{
  if (e.target === document.getElementById('modal')) document.getElementById('modal').classList.remove('open');
}}

function updateStatus() {{
  if (currentIdx === null) return;
  var st = document.getElementById('m-status').value;
  statuses[currentIdx] = st;
  var rows = document.querySelectorAll('#tbody .row');
  rows[currentIdx].dataset.status = st;
  var colors = {{Cold:'#6b7280',Contacted:'#3b82f6',Interested:'#f59e0b',Client:'#22c55e'}};
  var badges = rows[currentIdx].querySelectorAll('span');
  var lastBadge = badges[badges.length-1];
  lastBadge.style.background = colors[st] || '#6b7280';
  lastBadge.textContent = st;
}}

filter();
</script>
</body>
</html>"""

Path(OUT).write_text(html_content, encoding='utf-8')
print(f"OK - {len(df)} restaurantes → {OUT}")
