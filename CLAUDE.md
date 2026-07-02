# easy-leads-ai — CLAUDE.md

## O que é
Scripts operacionais do funil B2B de prospecção ativa: scraping → enriquecimento Instagram → Arcus CRM → dispatch WhatsApp (3 blocos + delay) → sync respostas.

É o **source of truth operacional** do projecto (os scripts correm daqui; `prospeccao-ativa/` tem o agente OpenClaw e os pitches).

**Produto vendido:** agentes de atendimento (WhatsApp) e voice agents (chamadas) — automatizam tarefas administrativas rotineiras: responder mensagens repetitivas, agendar, confirmar, fazer follow-up. Não é IA generativa, não é conteúdo.

## Stack
- Python (scripts standalone, sem framework)
- Servidor local em `server.py` (porta 8080, stdlib apenas)
- Dashboards HTML estáticos gerados por script
- Integração: Arcus CRM, OpenClaw WhatsApp, Apify

## Nichos activos (5)
`restaurantes`, `clinicas`, `advocacia`, `imobiliarias`, `guest_house`
Definidos em `niches.json`. Credenciais em `~/.easy-leads/arcus.env` (inclui `APIFY_KEY`).

## Comandos

```bash
python3 server.py                              # servidor local http://localhost:8080
python3 scraper_restaurantes.py                # scraping Google Maps/Instagram → Excel
python3 export_to_arcus.py                     # Excel → Arcus CRM (stage: LEAD)
python3 enrich_leads.py                        # Apify Instagram → signal nas notes do Arcus
python3 dispatch_whatsapp.py                   # dispara prospecção (3 blocos, delay 15-25s)
python3 sync_inbound.py                        # outcome-log.jsonl → Arcus activities
python3 generate_dashboard.py                  # regenera dashboards HTML
python3 scraper_recovery.py                    # retoma scraping interrompido
```

### Flags úteis
```bash
# enrich_leads.py
--dry-run --limit N --contact-id ID

# dispatch_whatsapp.py
--dry-run --limit N --force-window
--test-phone +351XXXXXXXXX --variant A   # delay reduzido a 5s em test mode
--niche peniche_clinicas                 # filtra candidatos por nicho
--status
```

## Scripts — resumo

| Script | Função |
|--------|--------|
| `scraper_restaurantes.py` | Google Maps + IG → Excel |
| `export_to_arcus.py` | Excel → Arcus (stage: LEAD) |
| `enrich_leads.py` | Apify IG profile + posts → signal nas notes; ~$0.001/lead |
| `dispatch_whatsapp.py` | Lê pitch de `prospeccao-ativa/agent/pitches/`, extrai 3 blocos, envia com delay 15-25s; escreve Arcus só após sucesso |
| `sync_inbound.py` | outcome-log.jsonl → Arcus activities |
| `generate_message.py` | **IGNORAR** — descartado (usava Claude API; Raphael usa templates) |

## Estrutura de dados
- `data/` — Excel por nicho, JSONL de outcomes
- Dashboards: `dashboard.html`, `restaurantes.html`, `imoveis.html`

## Contexto crítico
- `dispatch_whatsapp.py` lê os pitch files de `../prospeccao-ativa/agent/pitches/`
- Fallback: se não houver `## Bloco 1/2/3`, envia secção inteira como 1 mensagem
- Signals em inglês são válidos (Silver Coast tem muitos negócios EN)
- A ponte signal → dor administrativa **não elogia o produto** — conexão correcta: "bom conteúdo → muito movimento → dor de gerir mensagens"

## Geografia
- Raphael mora em **Peniche (PT)** e atende num **raio de 20 km**. Configurado em `niches.json → region.radius_km: 20`.
- **Nunca hardcode "em Peniche"** nas mensagens — usar `{BUSINESS_CITY}` ou frase neutra.
- **Pendente:** extrair `City` como coluna separada do `Address` no scraper.

## Pendências abertas
- Implementar 3 modelos (A/B/C) nos pitch files + actualizar `VARIANT_HEADINGS` em `dispatch_whatsapp.py`
- Adicionar `{SIGNAL_REFERENCE}` ao `_apply_replacements`
- Re-scrape advocacia com query mais específica
- Extrair `City` como coluna separada do `Address`
