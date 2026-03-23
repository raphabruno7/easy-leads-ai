#!/usr/bin/env python3
import pandas as pd, json, math

df = pd.read_excel('/Users/raphaelbruno/Documents/Prospeção - Agente AI/Surf School Peniche Enriched.xlsx')
df = df.where(pd.notna(df), None)

def clean(v):
    if isinstance(v, float) and math.isnan(v): return None
    return v

records = []
for row in df.to_dict(orient='records'):
    r = {k: clean(v) for k, v in row.items()}
    for k in ['Seguidores', 'Seguindo', 'Posts', 'Score Atividade']:
        if r.get(k) is not None:
            try: r[k] = int(r[k])
            except: r[k] = None
    records.append(r)

records.sort(key=lambda r: r.get('Score Atividade') or 0, reverse=True)

def fmt(n):
    if n is None: return '—'
    if n >= 1_000_000: return f'{n/1e6:.1f}M'
    if n >= 1_000: return f'{n/1000:.1f}k'
    return str(n)

def score_class(s):
    if not s: return 'sl'
    if s >= 70: return 'sh'
    if s >= 40: return 'sm'
    return 'sl'

def status_class(s):
    m = {'Cold':'sc','Contactado':'sco','Proposta':'sp','Fechado':'sf'}
    return m.get(s or 'Cold', 'sc')

def e(s):
    if s is None: return ''
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

rows_html = ''
for i, r in enumerate(records):
    score = r.get('Score Atividade') or 0
    handle = r.get('Instagram Handle') or ''
    bio = (r.get('Bio') or '').replace('\n', ' ')[:65]
    phone = r.get('Phone') or ''
    phone = phone if str(phone).startswith('+') else ''
    rating = r.get('Rating') or ''
    reviews = r.get('# Reviews') or ''
    status = r.get('Status Lead') or 'Cold'

    rows_html += f'''<tr class="row" data-name="{e(r.get('Business Name','').lower())}" data-handle="{e(handle.lower())}" data-status="{e(status)}" data-ig="{'yes' if handle else 'no'}" onclick="openModal({i})">
<td><div class="name">{e(r.get('Business Name',''))}</div>{f'<div class="bio">{e(bio)}{"…" if len(bio)>=65 else ""}</div>' if bio else ''}</td>
<td>{f'<a class="handle" href="{e(r.get("Instagram URL",""))}" target="_blank" onclick="event.stopPropagation()">{e(handle)}</a>{" <b style=color:#3b82f6>✓</b>" if r.get("Verificado") else ""}' if handle else '<span class="dim">—</span>'}</td>
<td class="num">{fmt(r.get('Seguidores'))}</td>
<td class="num-sm">{fmt(r.get('Posts'))}</td>
<td class="num-sm">{f"⭐ {e(rating)}" if rating else "—"}</td>
<td class="tc"><span class="badge {score_class(score)}">{score}</span></td>
<td class="tc"><span class="badge {status_class(status)}">{e(status)}</span></td>
<td class="dim" style="font-size:11px">{e(phone)}</td>
</tr>'''

data_json = json.dumps(records, ensure_ascii=True)

total = len(records)
with_insta = sum(1 for r in records if r.get('Instagram Handle'))
scored = [r['Score Atividade'] for r in records if r.get('Score Atividade')]
avg_score = round(sum(scored)/len(scored)) if scored else 0
cold = sum(1 for r in records if (r.get('Status Lead') or 'Cold') == 'Cold')

html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<title>Surf Schools Peniche</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;font-size:14px}}
a{{color:#60a5fa;text-decoration:none}}
a:hover{{text-decoration:underline}}
.bar{{position:sticky;top:0;background:#0f172a;border-bottom:1px solid #1e293b;padding:14px 24px;z-index:10;box-shadow:0 2px 20px rgba(0,0,0,.6)}}
.bar-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}}
h1{{font-size:18px;font-weight:700;color:#fff}}
.sub{{font-size:11px;color:#64748b;margin-top:2px}}
.stats{{display:flex;gap:24px}}
.sv{{font-size:20px;font-weight:700;color:#fff}}
.sl2{{font-size:11px;color:#64748b;margin-top:1px}}
.filters{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
input,select{{background:#1e293b;border:1px solid #334155;color:#e2e8f0;border-radius:8px;padding:7px 12px;font-size:13px;outline:none}}
input:focus,select:focus{{border-color:#3b82f6}}
input::placeholder{{color:#64748b}}
#search{{width:220px}}
#count{{font-size:12px;color:#64748b;margin-left:4px}}
.wrap{{padding:0 24px 60px}}
table{{width:100%;border-collapse:collapse}}
th{{font-size:11px;color:#475569;font-weight:600;text-transform:uppercase;letter-spacing:.05em;padding:10px 12px;text-align:left;border-bottom:1px solid #1e293b;white-space:nowrap;position:sticky;top:0;background:#0f172a}}
td{{padding:10px 12px;border-bottom:1px solid #0f172a;vertical-align:middle}}
tr.row{{cursor:pointer}}
tr.row:hover td{{background:#1e293b}}
tr.hidden{{display:none}}
.name{{font-weight:600;color:#f1f5f9;line-height:1.3}}
.bio{{font-size:11px;color:#64748b;margin-top:2px}}
.handle{{font-family:monospace;font-size:12px}}
.num{{font-weight:600;color:#f1f5f9;text-align:right}}
.num-sm{{color:#94a3b8;text-align:right}}
.tc{{text-align:center}}
.dim{{color:#475569}}
.badge{{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600}}
.sh{{background:#065f46;color:#6ee7b7}}
.sm{{background:#78350f;color:#fcd34d}}
.sl{{background:#1e293b;color:#94a3b8}}
.sc{{background:#1e3a5f;color:#93c5fd}}
.sco{{background:#3b1f6e;color:#c4b5fd}}
.sp{{background:#78350f;color:#fcd34d}}
.sf{{background:#14532d;color:#86efac}}
.modal-bg{{position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:50;display:none;align-items:center;justify-content:center}}
.modal-bg.open{{display:flex}}
.modal{{background:#1e293b;border-radius:14px;padding:28px;max-width:560px;width:90%;max-height:90vh;overflow-y:auto;border:1px solid #334155}}
.modal h2{{font-size:18px;font-weight:700;color:#fff;margin-bottom:4px}}
.mrow{{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #1e293b;font-size:13px}}
.mrow:last-child{{border-bottom:none}}
.ml{{color:#94a3b8}}
.mv{{color:#f1f5f9;text-align:right}}
.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:14px 0}}
.metric{{background:#0f172a;border:1px solid #334155;border-radius:10px;padding:12px;text-align:center}}
.mn{{font-size:20px;font-weight:700;color:#fff}}
.mlb{{font-size:11px;color:#64748b;margin-top:3px}}
.biobox{{background:#0f172a;border:1px solid #334155;border-radius:10px;padding:14px;font-size:13px;color:#cbd5e1;line-height:1.6;margin:12px 0}}
.btn-ig{{background:linear-gradient(135deg,#7c3aed,#db2777);color:#fff;border:none;padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer}}
.mfooter{{display:flex;align-items:center;gap:12px;margin-top:14px;flex-wrap:wrap}}
</style>
</head>
<body>

<div class="bar">
  <div class="bar-top">
    <div><h1>🏄 Surf Schools Peniche</h1><div class="sub">Pipeline de prospecção — Agentes AI</div></div>
    <div class="stats">
      <div><div class="sv" id="s-total">{total}</div><div class="sl2">leads</div></div>
      <div><div class="sv" id="s-insta">{with_insta}</div><div class="sl2">instagram</div></div>
      <div><div class="sv">{avg_score}</div><div class="sl2">score médio</div></div>
      <div><div class="sv" id="s-cold">{cold}</div><div class="sl2">cold</div></div>
    </div>
  </div>
  <div class="filters">
    <input id="search" type="text" placeholder="🔍 Pesquisar..." oninput="applyFilters()">
    <select id="filterStatus" onchange="applyFilters()">
      <option value="">Todos os status</option>
      <option value="Cold">Cold</option>
      <option value="Contactado">Contactado</option>
      <option value="Proposta">Proposta</option>
      <option value="Fechado">Fechado</option>
    </select>
    <select id="filterInsta" onchange="applyFilters()">
      <option value="">Com e sem Instagram</option>
      <option value="yes">Com Instagram</option>
      <option value="no">Sem Instagram</option>
    </select>
    <span id="count">{total} escolas</span>
  </div>
</div>

<div class="wrap">
<table>
<thead><tr>
  <th>Escola</th><th>Instagram</th>
  <th style="text-align:right">Seguidores</th>
  <th style="text-align:right">Posts</th>
  <th style="text-align:right">Rating</th>
  <th style="text-align:center">Score</th>
  <th style="text-align:center">Status</th>
  <th>Telefone</th>
</tr></thead>
<tbody id="tbody">
{rows_html}
</tbody>
</table>
</div>

<div id="modal" class="modal-bg" onclick="if(event.target===this)closeModal()">
  <div class="modal" id="mc"></div>
</div>

<script>
var DATA = {data_json};

function applyFilters() {{
  var q = document.getElementById('search').value.toLowerCase();
  var st = document.getElementById('filterStatus').value;
  var ig = document.getElementById('filterInsta').value;
  var rows = document.getElementById('tbody').getElementsByTagName('tr');
  var visible = 0;
  for (var i = 0; i < rows.length; i++) {{
    var r = rows[i];
    var name = r.getAttribute('data-name') || '';
    var handle = r.getAttribute('data-handle') || '';
    var status = r.getAttribute('data-status') || '';
    var hasIg = r.getAttribute('data-ig') === 'yes';
    var show = true;
    if (q && name.indexOf(q) === -1 && handle.indexOf(q) === -1) show = false;
    if (st && status !== st) show = false;
    if (ig === 'yes' && !hasIg) show = false;
    if (ig === 'no' && hasIg) show = false;
    r.className = show ? 'row' : 'row hidden';
    if (show) visible++;
  }}
  document.getElementById('count').textContent = visible + ' de {total} escolas';
}}

function openModal(idx) {{
  var r = DATA[idx];
  if (!r) return;
  var score = r['Score Atividade'] || 0;
  var phone = r['Phone'] && String(r['Phone']).charAt(0) === '+' ? r['Phone'] : null;
  var bio = (r['Bio'] || '').replace(/\\n/g, '<br>');
  var sc = score>=70?'sh':score>=40?'sm':'sl';

  var h = '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">';
  h += '<div><h2>' + (r['Business Name']||'') + '</h2>';
  if (r['Instagram Handle']) h += '<a href="' + (r['Instagram URL']||'') + '" target="_blank">' + r['Instagram Handle'] + ' ↗</a>';
  else h += '<span style="color:#64748b;font-size:13px">Sem Instagram</span>';
  h += '</div>';
  h += '<div style="text-align:right">';
  h += '<span class="badge ' + sc + '" style="font-size:16px;padding:4px 12px">' + score + '</span><br>';
  h += '<button onclick="closeModal()" style="background:none;border:none;color:#64748b;cursor:pointer;font-size:12px;margin-top:6px">✕ fechar</button>';
  h += '</div></div>';

  if (bio) h += '<div class="biobox">' + bio + '</div>';

  h += '<div class="metrics">';
  if (r['Seguidores'] != null) h += '<div class="metric"><div class="mn">' + fmt(r['Seguidores']) + '</div><div class="mlb">Seguidores</div></div>';
  if (r['Posts'] != null) h += '<div class="metric"><div class="mn">' + fmt(r['Posts']) + '</div><div class="mlb">Posts</div></div>';
  if (r['Seguindo'] != null) h += '<div class="metric"><div class="mn">' + fmt(r['Seguindo']) + '</div><div class="mlb">Seguindo</div></div>';
  h += '</div><div>';
  if (r['Rating']) h += '<div class="mrow"><span class="ml">Rating Google</span><span class="mv">⭐ ' + r['Rating'] + ' ' + (r['# Reviews']||'') + '</span></div>';
  if (r['Category']) h += '<div class="mrow"><span class="ml">Categoria</span><span class="mv">' + r['Category'] + '</span></div>';
  if (r['Address']) h += '<div class="mrow"><span class="ml">Morada</span><span class="mv">' + r['Address'] + '</span></div>';
  if (phone) h += '<div class="mrow"><span class="ml">Telefone</span><a href="tel:' + phone + '">' + phone + '</a></div>';
  if (r['Email']) h += '<div class="mrow"><span class="ml">Email</span><a href="mailto:' + r['Email'] + '">' + r['Email'] + '</a></div>';
  if (r['Verificado']) h += '<div class="mrow"><span class="ml">Instagram</span><span style="color:#60a5fa">✓ Verificado</span></div>';
  if (r['Privado']) h += '<div class="mrow"><span class="ml">Perfil</span><span style="color:#fbbf24">🔒 Privado</span></div>';
  h += '</div>';

  var stMap = {{'Cold':'sc','Contactado':'sco','Proposta':'sp','Fechado':'sf'}};
  h += '<div class="mfooter"><span class="ml">Status:</span>';
  h += '<select onchange="updateStatus(' + idx + ',this.value)" style="padding:6px 12px">';
  h += '<option' + (r['Status Lead']==='Cold'?' selected':'') + '>Cold</option>';
  h += '<option' + (r['Status Lead']==='Contactado'?' selected':'') + '>Contactado</option>';
  h += '<option' + (r['Status Lead']==='Proposta'?' selected':'') + '>Proposta</option>';
  h += '<option' + (r['Status Lead']==='Fechado'?' selected':'') + '>Fechado</option>';
  h += '</select>';
  if (r['Instagram URL']) h += '<button class="btn-ig" onclick="window.open(\\'' + r['Instagram URL'] + '\\',\\'_blank\\')">Abrir Instagram ↗</button>';
  h += '</div>';

  document.getElementById('mc').innerHTML = h;
  document.getElementById('modal').className = 'modal-bg open';
}}

function closeModal() {{ document.getElementById('modal').className = 'modal-bg'; }}

function updateStatus(idx, s) {{
  DATA[idx]['Status Lead'] = s;
  var rows = document.getElementById('tbody').getElementsByTagName('tr');
  if (rows[idx]) rows[idx].setAttribute('data-status', s);
  var badges = rows[idx] ? rows[idx].getElementsByClassName('badge') : [];
  var stMap = {{'Cold':'sc','Contactado':'sco','Proposta':'sp','Fechado':'sf'}};
  if (badges.length > 0) {{
    var lastBadge = badges[badges.length-1];
    lastBadge.className = 'badge ' + (stMap[s]||'sc');
    lastBadge.textContent = s;
  }}
}}

function fmt(n) {{
  if (!n && n !== 0) return '—';
  if (n >= 1000000) return (n/1e6).toFixed(1)+'M';
  if (n >= 1000) return (n/1000).toFixed(1)+'k';
  return n;
}}

document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') closeModal(); }});
</script>
</body>
</html>"""

with open('/Users/raphaelbruno/Documents/Prospeção - Agente AI/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("OK -", len(records), "registos")
