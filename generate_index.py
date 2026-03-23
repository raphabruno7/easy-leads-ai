#!/usr/bin/env python3
"""Gera index.html — hub central de nichos de prospeção."""
import pandas as pd, math
from pathlib import Path

BASE = Path("/Users/raphaelbruno/Documents/Prospeção - Agente AI")
OUT  = BASE / "index.html"

NICHOS_ATIVOS = [
    {
        "nome": "Escolas de Surf",
        "icon": "🏄",
        "cor": "#0ea5e9",
        "excel": "Surf School Peniche Enriched.xlsx",
        "dashboard": "dashboard.html",
        "scraper_id": "surf",
        "score_col": "Score Atividade",
        "ig_col": "Instagram Handle",
        "phone_col": "Phone",
        "desc": "Escolas de surf na zona de Peniche e Baleal",
    },
    {
        "nome": "Restaurantes",
        "icon": "🍽️",
        "cor": "#f97316",
        "excel": "Restaurantes Peniche Enriched.xlsx",
        "dashboard": "restaurantes.html",
        "scraper_id": "restaurantes",
        "score_col": "Score AI Potencial",
        "ig_col": "Instagram Handle",
        "phone_col": "Phone",
        "desc": "Restaurantes, cafés e takeaway — raio 15km Peniche",
    },
]

NICHOS_SUGERIDOS = [
    {"icon": "🏠", "nome": "Imobiliárias",         "estrelas": 5, "cor": "#8b5cf6", "desc": "Qualificação de leads, agendamento de visitas, follow-up automático"},
    {"icon": "🦷", "nome": "Clínicas / Dentistas",  "estrelas": 5, "cor": "#ec4899", "desc": "Marcações, lembretes, follow-up pós-consulta, captação de novos pacientes"},
    {"icon": "🏨", "nome": "Alojamento Local",       "estrelas": 4, "cor": "#14b8a6", "desc": "Check-in automático, FAQ de turistas, gestão de reviews"},
    {"icon": "💆", "nome": "Fisioterapia / Wellness","estrelas": 4, "cor": "#a78bfa", "desc": "Lesões de surf = alta procura. Marcações, planos de treino, upsell"},
    {"icon": "🚗", "nome": "Rent-a-Car / Transfers", "estrelas": 4, "cor": "#34d399", "desc": "Reservas, confirmações, rotas, upsell de seguros"},
    {"icon": "💈", "nome": "Barbearias / Salões",    "estrelas": 3, "cor": "#fb923c", "desc": "Marcações, confirmações, lembretes, upsell de serviços"},
    {"icon": "🏄", "nome": "Lojas de Surf",          "estrelas": 3, "cor": "#38bdf8", "desc": "Stock, aluguer, reparações, notificações de chegada de produto"},
    {"icon": "📸", "nome": "Fotógrafos de Surf",     "estrelas": 3, "cor": "#f472b6", "desc": "Entrega de fotos, packs, agendamento de sessões"},
]

def get_stats(nicho):
    path = BASE / nicho["excel"]
    if not path.exists():
        return None
    df = pd.read_excel(path)
    df = df.where(pd.notna(df), None)
    total = len(df)
    with_ig = df[nicho["ig_col"]].notna().sum() if nicho["ig_col"] in df.columns else 0
    with_phone = df[nicho["phone_col"]].notna().sum() if nicho["phone_col"] in df.columns else 0
    sc = nicho["score_col"]
    avg_score = round(df[sc].mean(), 0) if sc in df.columns else 0
    cold = (df.get("Status Lead") == "Cold").sum() if "Status Lead" in df.columns else total
    return {"total": total, "ig": int(with_ig), "phone": int(with_phone),
            "avg_score": int(avg_score), "cold": int(cold)}

def stars_html(n):
    return "★" * n + "☆" * (5 - n)

# Build cards
active_cards = ""
for n in NICHOS_ATIVOS:
    s = get_stats(n)
    if not s:
        continue
    cor = n["cor"]
    score_pct = s["avg_score"]
    active_cards += f"""
    <a href="{n['dashboard']}" class="card active" style="--accent:{cor}">
      <div class="card-header">
        <span class="card-icon">{n['icon']}</span>
        <span class="card-badge active-badge">Ativo</span>
      </div>
      <h2 class="card-title">{n['nome']}</h2>
      <p class="card-desc">{n['desc']}</p>
      <div class="card-stats">
        <div class="stat-item"><span class="stat-val">{s['total']}</span><span class="stat-lbl">Leads</span></div>
        <div class="stat-item"><span class="stat-val">{s['ig']}</span><span class="stat-lbl">Instagram</span></div>
        <div class="stat-item"><span class="stat-val">{s['phone']}</span><span class="stat-lbl">Telefone</span></div>
        <div class="stat-item"><span class="stat-val">{s['cold']}</span><span class="stat-lbl">Cold</span></div>
      </div>
      <div class="score-bar-wrap">
        <div class="score-bar-label"><span>Score médio</span><span style="color:{cor}">{score_pct}/100</span></div>
        <div class="score-bar-bg"><div class="score-bar-fill" style="width:{score_pct}%;background:{cor}"></div></div>
      </div>
      <div class="card-btn" style="background:{cor}">Abrir Dashboard →</div>
      <div onclick="event.preventDefault();launchScraper('{n['scraper_id']}','{n['nome']}','{n['dashboard']}')" style="text-align:center;font-size:11px;color:#64748b;cursor:pointer;padding:4px 0">↺ Actualizar dados</div>
    </a>"""

suggested_cards = ""
for n in NICHOS_SUGERIDOS:
    cor = n["cor"]
    suggested_cards += f"""
    <div class="card suggested" style="--accent:{cor}">
      <div class="card-header">
        <span class="card-icon">{n['icon']}</span>
        <span class="card-badge soon-badge">Em breve</span>
      </div>
      <h2 class="card-title">{n['nome']}</h2>
      <p class="card-desc">{n['desc']}</p>
      <div class="stars" style="color:{cor}">{stars_html(n['estrelas'])}</div>
      <div class="card-btn-ghost" style="border-color:{cor};color:{cor}" onclick="alert('Em breve!')">+ Lançar Scraper</div>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prospeção Peniche — AI Agent Leads</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}}
.header{{background:#1e293b;border-bottom:1px solid #334155;padding:28px 32px}}
.header h1{{font-size:26px;font-weight:700;color:#f8fafc;margin-bottom:4px}}
.header p{{color:#64748b;font-size:14px}}
.section{{padding:32px}}
.section-title{{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:#64748b;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}}
.card{{background:#1e293b;border-radius:14px;padding:24px;border:1px solid #334155;text-decoration:none;color:inherit;display:flex;flex-direction:column;gap:14px;transition:border-color .2s,transform .15s}}
.card.active{{border-color:color-mix(in srgb,var(--accent) 30%,#334155)}}
.card.active:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.card.suggested{{opacity:.7}}
.card.suggested:hover{{opacity:.9}}
.card-header{{display:flex;align-items:center;justify-content:space-between}}
.card-icon{{font-size:28px}}
.card-badge{{font-size:10px;font-weight:700;padding:3px 8px;border-radius:20px;text-transform:uppercase;letter-spacing:.05em}}
.active-badge{{background:#166534;color:#86efac}}
.soon-badge{{background:#1e3a5f;color:#93c5fd}}
.card-title{{font-size:18px;font-weight:700;color:#f8fafc}}
.card-desc{{font-size:12px;color:#94a3b8;line-height:1.5}}
.card-stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
.stat-item{{text-align:center}}
.stat-val{{display:block;font-size:18px;font-weight:700;color:#f8fafc}}
.stat-lbl{{display:block;font-size:10px;color:#64748b;margin-top:2px}}
.score-bar-wrap{{display:flex;flex-direction:column;gap:6px}}
.score-bar-label{{display:flex;justify-content:space-between;font-size:11px;color:#64748b}}
.score-bar-bg{{background:#0f172a;border-radius:99px;height:6px;overflow:hidden}}
.score-bar-fill{{height:100%;border-radius:99px;transition:width .3s}}
.card-btn{{display:block;text-align:center;padding:10px;border-radius:8px;font-size:13px;font-weight:600;color:white;margin-top:4px}}
.card-btn-ghost{{display:block;text-align:center;padding:9px;border-radius:8px;font-size:13px;font-weight:600;border:1px solid;margin-top:4px;cursor:pointer}}
.stars{{font-size:18px;letter-spacing:2px}}
.divider{{height:1px;background:#1e293b;margin:0 32px}}
.scraper-btn{{display:block;text-align:center;padding:10px;border-radius:8px;font-size:13px;font-weight:600;color:white;margin-top:4px;cursor:pointer;border:none;width:100%}}
.scraper-btn:disabled{{opacity:.5;cursor:not-allowed}}
.progress-panel{{display:none;margin-top:10px;background:#0f172a;border-radius:8px;padding:10px;font-size:11px;color:#94a3b8;max-height:160px;overflow-y:auto;line-height:1.7;font-family:monospace}}
.progress-panel.open{{display:block}}
</style>
</head>
<body>
<div class="header">
  <h1>🌊 Prospeção Peniche — raio 15km</h1>
  <p>AI Agent Leads — Nichos locais com maior potencial de automação</p>
</div>

<div class="section">
  <div class="section-title">Nichos ativos</div>
  <div class="grid">{active_cards}</div>
</div>

<div class="divider"></div>

<div class="section">
  <div class="section-title">Próximos nichos sugeridos</div>
  <div class="grid">{suggested_cards}</div>
</div>

<div id="scraper-modal" style="display:none;position:fixed;inset:0;background:#00000099;z-index:300;align-items:center;justify-content:center">
  <div style="background:#1e293b;border-radius:14px;padding:28px;width:90%;max-width:500px;max-height:80vh;overflow-y:auto">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2 id="modal-title" style="font-size:18px;font-weight:700;color:#f8fafc"></h2>
      <button onclick="closeScraperModal()" style="background:none;border:none;color:#94a3b8;font-size:22px;cursor:pointer">×</button>
    </div>
    <div id="modal-log" style="background:#0f172a;border-radius:8px;padding:12px;font-size:11px;font-family:monospace;color:#94a3b8;min-height:80px;max-height:300px;overflow-y:auto;line-height:1.8"></div>
    <div id="modal-actions" style="margin-top:14px;display:flex;gap:8px">
      <button id="modal-open-btn" style="display:none;flex:1;padding:10px;background:#22c55e;color:white;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer" onclick="openDashboard()">Abrir Dashboard →</button>
    </div>
  </div>
</div>

<script>
var _nicho = null;
var _dashboard = null;
var _poll = null;

function launchScraper(nicho, label, dashboard) {{
  _nicho = nicho;
  _dashboard = dashboard;
  document.getElementById('modal-title').textContent = '🚀 ' + label;
  document.getElementById('modal-log').innerHTML = '<span style="color:#60a5fa">A iniciar scraper...</span>';
  document.getElementById('modal-open-btn').style.display = 'none';
  document.getElementById('scraper-modal').style.display = 'flex';

  fetch('/api/scrape/' + nicho)
    .then(r => r.json())
    .then(d => {{
      if (d.status === 'already_running') appendLog('⚠️ Já está a correr...');
      startPolling();
    }})
    .catch(e => appendLog('❌ Servidor não responde. Usa: python3 server.py'));
}}

function startPolling() {{
  if (_poll) clearInterval(_poll);
  _poll = setInterval(pollStatus, 1500);
}}

function pollStatus() {{
  if (!_nicho) return;
  fetch('/api/status/' + _nicho)
    .then(r => r.json())
    .then(d => {{
      var logEl = document.getElementById('modal-log');
      logEl.innerHTML = (d.log || []).map(function(l) {{
        var col = l.startsWith('✅')||l.startsWith('🎉') ? '#22c55e' : l.startsWith('❌') ? '#ef4444' : '#94a3b8';
        return '<span style="color:'+col+'">'+l+'</span>';
      }}).join('<br>');
      logEl.scrollTop = logEl.scrollHeight;
      if (d.status === 'done') {{
        clearInterval(_poll);
        document.getElementById('modal-open-btn').style.display = 'block';
        setTimeout(() => location.reload(), 2000);
      }} else if (d.status === 'error') {{
        clearInterval(_poll);
      }}
    }});
}}

function appendLog(msg) {{
  var el = document.getElementById('modal-log');
  el.innerHTML += '<br>' + msg;
}}

function openDashboard() {{
  if (_dashboard) window.location.href = _dashboard;
}}

function closeScraperModal() {{
  if (_poll) clearInterval(_poll);
  document.getElementById('scraper-modal').style.display = 'none';
}}
</script>
</body>
</html>"""

OUT.write_text(html, encoding="utf-8")
print(f"OK → {OUT}")
