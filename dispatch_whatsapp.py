#!/usr/bin/env python3
"""
dispatch_whatsapp.py — envia 1ª abordagem via OpenClaw para contacts do Arcus.

Seleção: contacts com tag 'easy-leads-ai' + stage 'LEAD' + last_interaction NULL + phone válido.
Respeita: 20/dia total, 09–20h Europe/Lisbon, sem domingos, cooldown 4–17min entre envios.
Invoca: openclaw agent --agent prospector --channel whatsapp --to <phone> --message <json> --deliver --json

Uso:
    python3 dispatch_whatsapp.py --dry-run --limit 5
    python3 dispatch_whatsapp.py --limit 3
    python3 dispatch_whatsapp.py --status
"""
import argparse, json, os, random, re, subprocess, sys, time
from datetime import datetime, timezone, timedelta, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

BASE = Path(__file__).parent
NICHES_PATH = BASE / "niches.json"
LOG_PATH = BASE / "data" / "dispatch-log.jsonl"
STATE_PATH = BASE / "data" / "dispatch-state.json"
ENV_PATH = Path.home() / ".easy-leads" / "arcus.env"

ORG_ID = "c4669ad5-e6b2-41ed-9c51-c09dfbec17f9"
TZ = ZoneInfo("Europe/Lisbon")
QUIET_START = dtime(9, 0)
QUIET_END = dtime(20, 0)
DAILY_CAP = 20
COOLDOWN_MIN_SEC = 4 * 60
COOLDOWN_MAX_SEC = 17 * 60
OPENCLAW_BIN = os.environ.get("OPENCLAW_BIN", "/opt/homebrew/bin/openclaw")
OPENCLAW_TIMEOUT_SEC = 180


def load_env():
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    if not env.get("ARCUS_SUPABASE_URL") or not env.get("ARCUS_SUPABASE_KEY"):
        sys.exit(f"ERRO: {ENV_PATH} sem ARCUS_SUPABASE_URL/KEY.")
    for k in ("CALCOM_BOOKING_URL", "RAPHAEL_PHONE", "TELEGRAM_HANDOFF_CHAT_ID"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def load_state():
    if not STATE_PATH.exists():
        return {"date": "", "sent_today": 0, "last_sent_ts": 0, "opt_outs": []}
    return json.loads(STATE_PATH.read_text())


def save_state(s):
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(s, indent=2))


def today_lisbon():
    return datetime.now(TZ).date().isoformat()


def now_lisbon():
    return datetime.now(TZ)


def within_send_window():
    n = now_lisbon()
    if n.weekday() == 6:  # sunday
        return False, "domingo"
    if n.time() < QUIET_START or n.time() >= QUIET_END:
        return False, f"fora da janela {QUIET_START}-{QUIET_END}"
    return True, None


def log(obj):
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(obj, default=str, ensure_ascii=False) + "\n")


def arcus_get(path, env, params=None):
    r = requests.get(f"{env['ARCUS_SUPABASE_URL']}/rest/v1/{path}",
                     headers={"apikey": env["ARCUS_SUPABASE_KEY"],
                              "Authorization": f"Bearer {env['ARCUS_SUPABASE_KEY']}"},
                     params=params, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Arcus GET {path} → {r.status_code}: {r.text[:200]}")
    return r.json()


def arcus_patch(path, env, params, json_body):
    r = requests.patch(f"{env['ARCUS_SUPABASE_URL']}/rest/v1/{path}",
                       headers={"apikey": env["ARCUS_SUPABASE_KEY"],
                                "Authorization": f"Bearer {env['ARCUS_SUPABASE_KEY']}",
                                "Content-Type": "application/json",
                                "Prefer": "return=representation"},
                       params=params, json=json_body, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Arcus PATCH {path} → {r.status_code}: {r.text[:200]}")
    return r.json()


def arcus_post(path, env, json_body):
    r = requests.post(f"{env['ARCUS_SUPABASE_URL']}/rest/v1/{path}",
                      headers={"apikey": env["ARCUS_SUPABASE_KEY"],
                               "Authorization": f"Bearer {env['ARCUS_SUPABASE_KEY']}",
                               "Content-Type": "application/json",
                               "Prefer": "return=representation"},
                      json=json_body, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Arcus POST {path} → {r.status_code}: {r.text[:200]}")
    return r.json()


def fetch_eligible_contacts(env):
    """Contacts tagged easy-leads-ai, stage=LEAD, never contacted, phone valid."""
    rows = arcus_get("contacts", env, params={
        "select": "id,name,phone,tags,notes,last_interaction,stage,status",
        "organization_id": f"eq.{ORG_ID}",
        "stage": "eq.LEAD",
        "status": "eq.ACTIVE",
        "tags": "cs.{easy-leads-ai}",
        "last_interaction": "is.null",
        "order": "created_at.desc",
        "limit": "100",
    })
    return [r for r in rows if r.get("phone")]


def pick_niche_and_lang(tags):
    niche = next((t for t in (tags or []) if t.startswith("peniche_")), None)
    return niche, "pt-PT"  # default PT; agent switches on reply


def derive_pitch_file(niche, lang):
    """Compute the pitch filename so the agent never has to derive it."""
    niche_slug = niche.removeprefix("peniche_") if niche else "restaurantes"
    lang_short = lang.split("-")[0].lower()  # pt-PT → pt, en-GB → en
    return f"{niche_slug}_{lang_short}.md"


PITCHES_DIR = Path.home() / ".openclaw" / "workspace-prospector" / "pitches"

VARIANT_HEADINGS = {
    "A": ["# Abordagem A", "# Approach A"],
    "B": ["# Abordagem B", "# Approach B"],
    "C": ["# Follow-up C", "# Follow-up C (toque 2"],
}

# Delay entre blocos da mesma mensagem (segundos)
BLOCK_DELAY_MIN = 15
BLOCK_DELAY_MAX = 25


def greeting_pt():
    h = now_lisbon().hour
    if h < 12:
        return "Bom dia."
    if h < 19:
        return "Boa tarde."
    return "Boa noite."


def extract_blocks(pitch_text, variant):
    """Extrai lista de blocos (## Bloco 1/2/3) dentro de uma variante."""
    section = extract_section(pitch_text, variant)
    if not section:
        return None
    blocks = []
    current = []
    for line in section.splitlines():
        if line.startswith("## Bloco "):
            if current:
                blocks.append("\n".join(current).strip())
            current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    # Remove blocos vazios
    blocks = [b for b in blocks if b]
    return blocks if blocks else None


def extract_section(pitch_text, variant):
    """Extract the body of the section matching the variant heading."""
    headings = VARIANT_HEADINGS.get(variant, VARIANT_HEADINGS["A"])
    lines = pitch_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if any(line.strip().startswith(h) for h in headings):
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("# "):
            end = j
            break
    body = "\n".join(lines[start:end]).strip()
    return body


def _apply_replacements(text, business, context):
    """Substitui todos os placeholders num texto."""
    name = business.get("name") or ""
    city = business.get("city") or "na tua zona"
    ig_handle = business.get("ig_handle") or ""
    ig_followers = business.get("ig_followers_str") or ""
    reviews = business.get("reviews") or ""
    rating = business.get("rating") or ""
    signal = business.get("signal") or ""
    signal_suffix = f" e vi que têm {signal}" if signal else ""

    replacements = {
        "{GREETING}": greeting_pt(),
        "{BUSINESS_NAME}": name,
        "{BUSINESS_CITY}": city,
        "{BUSINESS_SIGNAL_SUFFIX}": signal_suffix,
        "{IG_HANDLE}": ig_handle,
        "{IG_FOLLOWERS}": str(ig_followers),
        "{REVIEW_COUNT}": str(reviews),
        "{RATING}": str(rating),
        "{CALCOM_URL}": (context or {}).get("calcom_url", ""),
        "{RAPHAEL_WA_LINK}": (context or {}).get("raphael_wa_link", ""),
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def render_blocks(pitch_file, variant, business, context):
    """Retorna lista de blocos renderizados (3 mensagens separadas)."""
    path = PITCHES_DIR / pitch_file
    if not path.exists():
        return None
    blocks = extract_blocks(path.read_text(), variant or "A")
    if not blocks:
        return None
    return [_apply_replacements(b, business, context) for b in blocks]


def render_message(pitch_file, variant, business, context):
    """Fallback: retorna a secção inteira como 1 mensagem (sem blocos)."""
    path = PITCHES_DIR / pitch_file
    if not path.exists():
        return None
    body = extract_section(path.read_text(), variant or "A")
    if not body:
        return None
    return _apply_replacements(body, business, context)


def parse_msg1(notes):
    """Extrai Msg1 pré-gerada das notes (guardada com \\n como escape de newlines)."""
    m = re.search(r'\| Msg1: ([^\|]+?)(?= \||$)', notes or '', re.DOTALL)
    if not m:
        return None
    return m.group(1).strip().replace("\\n", "\n")


def parse_notes_to_business(notes, name):
    """Extrai reviews/rating/ig/followers/signal dos notes formatados pelo export."""
    biz = {"name": name}
    if not notes:
        return biz
    head = notes.split("\n", 1)[0]
    for part in [p.strip() for p in head.split("|")]:
        if part.endswith("reviews"):
            try: biz["reviews"] = int(part.split()[0])
            except: pass
        elif "⭐" in part:
            try: biz["rating"] = float(part.replace("⭐", "").strip())
            except: pass
        elif part.startswith("IG:"):
            ig = part.replace("IG:", "").strip()
            if "(" in ig:
                handle, foll = ig.split("(", 1)
                biz["ig_handle"] = handle.strip()
                biz["ig_followers_str"] = foll.replace(")", "").strip()
            else:
                biz["ig_handle"] = ig
        elif part.startswith("Signal:"):
            biz["signal"] = part.removeprefix("Signal:").strip()
    return biz


def dispatch_one(contact, env, dry_run=False, test_phone=None, variant="A"):
    niche, lang = pick_niche_and_lang(contact.get("tags"))
    if not niche:
        return {"ok": False, "skip": "no_niche_tag"}
    business = parse_notes_to_business(contact.get("notes") or "", contact["name"])
    context = {}
    if env.get("CALCOM_BOOKING_URL"):
        context["calcom_url"] = env["CALCOM_BOOKING_URL"]
    if env.get("RAPHAEL_PHONE"):
        context["raphael_wa_link"] = "https://wa.me/" + env["RAPHAEL_PHONE"].lstrip("+").replace(" ", "")

    pitch_file = derive_pitch_file(niche, lang)
    blocks = render_blocks(pitch_file, variant, business, context)
    if not blocks:
        # Fallback: sem blocos, envia como mensagem única
        rendered = render_message(pitch_file, variant, business, context)
        if not rendered:
            return {"ok": False, "error": f"pitch_file_missing:{pitch_file}"}
        blocks = [rendered]

    target_phone = test_phone or contact["phone"]
    label = f"[TEST → {target_phone}] " if test_phone else ""
    print(f"  {label}{contact['name']} · {niche} · {variant} · {len(blocks)} blocos")

    if dry_run:
        for i, bloco in enumerate(blocks, 1):
            print(f"  --- Bloco {i} ---")
            print("  " + bloco.replace("\n", "\n  "))
        print("  ---")
        return {"ok": True, "dry": True}

    # Envia cada bloco com delay entre eles
    started = time.time()
    for i, bloco in enumerate(blocks):
        cmd = [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
               "--target", target_phone, "--message", bloco, "--json"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=OPENCLAW_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout_bloco_{i+1}"}

        if proc.returncode != 0:
            err_tail = (proc.stderr or "")[-200:]
            return {"ok": False, "error": f"bloco_{i+1}_falhou", "stderr_tail": err_tail}

        print(f"  ✓ Bloco {i+1}/{len(blocks)} enviado")

        # Delay entre blocos (não aplica depois do último)
        if i < len(blocks) - 1:
            delay = random.randint(BLOCK_DELAY_MIN, BLOCK_DELAY_MAX)
            if test_phone:
                delay = 5  # delay reduzido em modo teste
            print(f"  ⏱ aguarda {delay}s antes do bloco {i+2}...")
            time.sleep(delay)

    took = time.time() - started
    full_msg = "\n\n---\n\n".join(blocks)

    # Skip Arcus writes em test mode
    if not test_phone:
        try:
            arcus_patch("contacts", env, params={"id": f"eq.{contact['id']}"},
                        json_body={"last_interaction": datetime.now(timezone.utc).isoformat()})
            arcus_post("activities", env, json_body={
                "title": f"1ª abordagem WhatsApp — {niche}",
                "description": f"Mensagem enviada ({len(blocks)} blocos):\n{full_msg}",
                "type": "whatsapp_out",
                "date": datetime.now(timezone.utc).isoformat(),
                "contact_id": contact["id"],
                "completed": True,
                "organization_id": ORG_ID,
            })
        except Exception as ex:
            print(f"    (activity log falhou: {ex})")

    return {"ok": True, "took_sec": round(took, 1), "blocks_sent": len(blocks)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=5, help="Máximo de envios nesta corrida")
    ap.add_argument("--status", action="store_true", help="Mostra estado e sai")
    ap.add_argument("--force-window", action="store_true", help="Ignora quiet hours (cuidado!)")
    ap.add_argument("--test-phone", default=None,
                    help="Redireciona todos os envios para este número. Bypassa janela, cooldown reduzido a 5s, sem write Arcus.")
    ap.add_argument("--variant", default="A", choices=["A", "B", "C"],
                    help="Variante do pitch a usar (A/B/C). Default A.")
    ap.add_argument("--niche", default=None,
                    help="Filtra candidatos por nicho, ex: peniche_clinicas")
    args = ap.parse_args()
    test_mode = bool(args.test_phone)

    state = load_state()
    if state.get("date") != today_lisbon():
        state = {"date": today_lisbon(), "sent_today": 0, "last_sent_ts": 0,
                 "opt_outs": state.get("opt_outs", [])}
        save_state(state)

    if args.status:
        window_ok, reason = within_send_window()
        print(json.dumps({
            "today": state["date"], "sent_today": state["sent_today"],
            "remaining_today": max(0, DAILY_CAP - state["sent_today"]),
            "within_window": window_ok, "window_reason": reason,
            "now_lisbon": now_lisbon().isoformat(),
        }, indent=2))
        return

    window_ok, reason = within_send_window()
    if not window_ok and not args.force_window and not test_mode:
        print(f"⏸  Fora da janela de envio: {reason}. Usa --force-window para ignorar.")
        return

    if state["sent_today"] >= DAILY_CAP:
        print(f"⏸  Limite diário {DAILY_CAP} já atingido hoje ({state['date']}).")
        return

    env = load_env()
    print(f"Arcus: {env['ARCUS_SUPABASE_URL']}")
    print(f"Enviados hoje: {state['sent_today']}/{DAILY_CAP}")

    contacts = fetch_eligible_contacts(env)
    if args.niche:
        contacts = [c for c in contacts if args.niche in (c.get("tags") or [])]
    print(f"Candidatos elegíveis no Arcus: {len(contacts)}\n")

    budget = min(args.limit, DAILY_CAP - state["sent_today"])
    sent = 0
    for c in contacts:
        if sent >= budget:
            break
        if c["phone"] in state.get("opt_outs", []):
            continue

        # cooldown (5s fixo em test mode, 4–17min em produção)
        cooldown_min = 5 if test_mode else COOLDOWN_MIN_SEC
        elapsed = time.time() - state.get("last_sent_ts", 0)
        if elapsed < cooldown_min and state["sent_today"] > 0:
            wait = cooldown_min - elapsed
            print(f"⏱  cooldown: a aguardar {int(wait)}s...")
            time.sleep(wait)

        print(f"→ {c['name']} · {c['phone']}")
        result = dispatch_one(c, env, dry_run=args.dry_run,
                              test_phone=args.test_phone, variant=args.variant)
        log({"ts": datetime.now(timezone.utc).isoformat(), "contact_id": c["id"],
             "phone": c["phone"], "name": c["name"],
             "test_mode": test_mode, **result})

        if result.get("ok") and not result.get("dry"):
            if not test_mode:
                state["sent_today"] += 1
            state["last_sent_ts"] = time.time()
            save_state(state)
            sent += 1
            delay = 5 if test_mode else random.randint(COOLDOWN_MIN_SEC, COOLDOWN_MAX_SEC)
            label = f"~{delay}s" if test_mode else f"~{delay//60}min"
            print(f"  ✓ OK ({result.get('took_sec')}s) — próximo em {label}")
            if sent < budget:
                time.sleep(delay)
        elif result.get("dry"):
            sent += 1
        else:
            print(f"  ✗ FALHOU: {result.get('error') or result.get('stderr_tail','')[:200]}")

    print(f"\n=== fim · enviados nesta corrida: {sent} · total hoje: {state['sent_today']}/{DAILY_CAP} ===")


if __name__ == "__main__":
    main()
