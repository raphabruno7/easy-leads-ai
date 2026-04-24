#!/usr/bin/env python3
"""
export_to_arcus.py — lê Excel do easy-leads-ai e cria contacts/companies no Arcus CRM.

Uso:
    python3 export_to_arcus.py --niche peniche_restaurantes
    python3 export_to_arcus.py --all --dry-run
    python3 export_to_arcus.py --niche peniche_surf --limit 5

Requer ~/.easy-leads/arcus.env com ARCUS_SUPABASE_URL e ARCUS_SUPABASE_KEY.
Log de cada operação em data/arcus-export.jsonl.
"""
import argparse, json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

BASE = Path(__file__).parent
NICHES_PATH = BASE / "niches.json"
LOG_PATH = BASE / "data" / "arcus-export.jsonl"
ENV_PATH = Path.home() / ".easy-leads" / "arcus.env"

ORG_ID = "c4669ad5-e6b2-41ed-9c51-c09dfbec17f9"  # Raphael Bruno
LEAD_STAGE = "LEAD"


def load_env():
    if not ENV_PATH.exists():
        sys.exit(f"ERRO: {ENV_PATH} não existe. Cria com ARCUS_SUPABASE_URL e ARCUS_SUPABASE_KEY.")
    env = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    if not env.get("ARCUS_SUPABASE_URL") or not env.get("ARCUS_SUPABASE_KEY"):
        sys.exit("ERRO: ARCUS_SUPABASE_URL ou ARCUS_SUPABASE_KEY faltando.")
    return env


def normalize_phone_pt(raw):
    """Normaliza número pt para E.164: '+351XXXXXXXXX' (sem espaços)."""
    if not raw or pd.isna(raw):
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 9 and digits[0] in "2369":  # móveis PT começam com 9, fixos com 2
        return "+351" + digits
    if len(digits) == 12 and digits.startswith("351"):
        return "+" + digits
    if len(digits) == 13 and digits.startswith("00351"):
        return "+" + digits[2:]
    return None  # rejeita números ambíguos


def score_bucket(score):
    if score >= 80: return "score-80+"
    if score >= 60: return "score-60-79"
    if score >= 40: return "score-40-59"
    return "score-low"


def format_ig_followers(n):
    if not n or pd.isna(n): return None
    n = int(n)
    if n >= 1000: return f"{n/1000:.1f}k"
    return str(n)


def build_notes(row, niche_cfg, lang="pt"):
    parts = [f"[{niche_cfg['label']}]"]
    score = int(row.get("Score AI Potencial") or 0)
    parts.append(f"Score: {score}/100")
    reviews = row.get("# Reviews")
    rating = row.get("Rating")
    if reviews and not pd.isna(reviews):
        parts.append(f"{int(reviews)} reviews")
    if rating and not pd.isna(rating):
        parts.append(f"{rating}⭐")
    ig = row.get("Instagram Handle")
    followers = format_ig_followers(row.get("Seguidores"))
    if ig:
        s = f"IG: {ig}"
        if followers: s += f" ({followers})"
        parts.append(s)
    website = row.get("Website")
    if website:
        parts.append(f"Web: {website}")
    head = " | ".join(parts)
    pain = niche_cfg.get(f"pain_one_liner_{lang}") or niche_cfg.get("pain_one_liner_pt", "")
    return f"{head}\n\nDor provável: {pain}"


def arcus_request(method, path, env, params=None, json_body=None):
    url = f"{env['ARCUS_SUPABASE_URL']}/rest/v1/{path}"
    headers = {
        "apikey": env["ARCUS_SUPABASE_KEY"],
        "Authorization": f"Bearer {env['ARCUS_SUPABASE_KEY']}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    r = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Arcus {method} {path} → {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else None


def find_contact_by_phone(phone, env):
    rows = arcus_request("GET", "contacts", env, params={
        "select": "id,name,stage", "phone": f"eq.{phone}",
        "organization_id": f"eq.{ORG_ID}", "limit": "1",
    })
    return rows[0] if rows else None


def upsert_company(name, website, env):
    existing = arcus_request("GET", "crm_companies", env, params={
        "select": "id,name,website", "name": f"eq.{name}",
        "organization_id": f"eq.{ORG_ID}", "limit": "1",
    })
    if existing:
        return existing[0]["id"]
    created = arcus_request("POST", "crm_companies", env, json_body={
        "name": name,
        "website": website or None,
        "organization_id": ORG_ID,
    })
    return created[0]["id"] if isinstance(created, list) else created["id"]


def create_contact(row, niche_key, niche_cfg, env):
    phone = normalize_phone_pt(row.get("Phone"))
    name = (row.get("Business Name") or "").strip()
    website = (row.get("Website") or "").strip() or None
    score = int(row.get("Score AI Potencial") or 0)

    company_id = upsert_company(name, website, env)

    tags = [niche_key, "peniche", score_bucket(score), "easy-leads-ai"]
    payload = {
        "name": name,
        "phone": phone,
        "company_name": name,
        "client_company_id": company_id,
        "status": "ACTIVE",
        "stage": LEAD_STAGE,
        "source": "PROSPECT",
        "tags": tags,
        "notes": build_notes(row, niche_cfg, lang="pt"),
        "total_value": niche_cfg.get("ticket_estimated_eur"),
        "organization_id": ORG_ID,
    }
    created = arcus_request("POST", "contacts", env, json_body=payload)
    return created[0] if isinstance(created, list) else created


def qualifies(row, qualification):
    score = int(row.get("Score AI Potencial") or 0)
    if score < qualification["min_score"]:
        return False, f"score_below_{qualification['min_score']}"
    if qualification["require_phone"]:
        if not normalize_phone_pt(row.get("Phone")):
            return False, "phone_invalid"
    if qualification["require_web_or_instagram"]:
        has_web = bool((row.get("Website") or "").strip())
        has_ig = bool((row.get("Instagram Handle") or "").strip())
        if not (has_web or has_ig):
            return False, "no_web_no_ig"
    return True, None


def log_jsonl(obj):
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(obj, default=str, ensure_ascii=False) + "\n")


def process_niche(niche_key, niche_cfg, qualification, env, args):
    excel_path = BASE / "data" / f"{niche_key}.xlsx"
    if not excel_path.exists():
        print(f"[{niche_key}] ⚠️  {excel_path} não existe — correr scraper primeiro.")
        return {"niche": niche_key, "skipped": True, "reason": "no_excel"}

    df = pd.read_excel(excel_path)
    print(f"[{niche_key}] {len(df)} rows no Excel")

    stats = {"niche": niche_key, "total": len(df), "qualified": 0, "sent": 0, "dup": 0, "skipped": 0, "errors": 0}
    sent_count = 0

    for _, row in df.iterrows():
        ok, reason = qualifies(row, qualification)
        if not ok:
            stats["skipped"] += 1
            continue
        stats["qualified"] += 1

        if args.limit and sent_count >= args.limit:
            break

        phone = normalize_phone_pt(row.get("Phone"))
        name = (row.get("Business Name") or "").strip()

        if args.dry_run:
            print(f"  [DRY] {name} · {phone} · score {row.get('Score AI Potencial')}")
            stats["sent"] += 1
            sent_count += 1
            continue

        try:
            existing = find_contact_by_phone(phone, env)
            if existing:
                print(f"  [DUP] {name} já existe como {existing['id']}")
                stats["dup"] += 1
                log_jsonl({"ts": datetime.now(timezone.utc).isoformat(), "niche": niche_key,
                           "action": "dup", "name": name, "phone": phone, "contact_id": existing["id"]})
                continue

            contact = create_contact(row, niche_key, niche_cfg, env)
            print(f"  [OK]  {name} · contact_id={contact['id']}")
            stats["sent"] += 1
            sent_count += 1
            log_jsonl({"ts": datetime.now(timezone.utc).isoformat(), "niche": niche_key,
                       "action": "created", "name": name, "phone": phone, "contact_id": contact["id"],
                       "score": int(row.get("Score AI Potencial") or 0)})
            time.sleep(0.2)  # gentle rate-limit
        except Exception as ex:
            stats["errors"] += 1
            print(f"  [ERR] {name}: {ex}")
            log_jsonl({"ts": datetime.now(timezone.utc).isoformat(), "niche": niche_key,
                       "action": "error", "name": name, "phone": phone, "error": str(ex)})

    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", help="Chave do nicho em niches.json (ex: peniche_restaurantes)")
    parser.add_argument("--all", action="store_true", help="Processar todos os nichos")
    parser.add_argument("--dry-run", action="store_true", help="Não envia, só imprime")
    parser.add_argument("--limit", type=int, help="Máximo de contacts a criar por nicho")
    parser.add_argument("--min-score", type=int, help="Override min_score da niches.json")
    args = parser.parse_args()

    if not args.niche and not args.all:
        sys.exit("Usa --niche <key> ou --all.")

    niches = json.loads(NICHES_PATH.read_text())
    qualification = niches["qualification"]
    if args.min_score is not None:
        qualification["min_score"] = args.min_score

    env = load_env()
    print(f"Arcus: {env['ARCUS_SUPABASE_URL']}")
    print(f"Org:   {ORG_ID}")
    print(f"Dry-run: {args.dry_run}\n")

    keys = list(niches["niches"].keys()) if args.all else [args.niche]
    all_stats = []
    for k in keys:
        if k not in niches["niches"]:
            print(f"⚠️  Nicho '{k}' não está em niches.json, skip.")
            continue
        print(f"\n── {k} ──")
        stats = process_niche(k, niches["niches"][k], qualification, env, args)
        all_stats.append(stats)

    print("\n=== RESUMO ===")
    for s in all_stats:
        print(f"  {s}")


if __name__ == "__main__":
    main()
