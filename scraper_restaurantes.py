#!/usr/bin/env python3
"""
Scraper de Leads — Google Maps + Instagram
1. Google Maps → lista de negócios com rating, reviews, phone, website
2. Google Search → Instagram handles
3. Instagram Profile Scraper → métricas sociais
4. Score composto: atividade social + volume reviews + sinais digitais

Uso padrão (Peniche, restaurantes):
  python3 scraper_restaurantes.py

Uso customizado:
  python3 scraper_restaurantes.py --city "São Paulo" --niche "clínicas odontológicas"
"""
import os, argparse
import pandas as pd, re, math, json
from apify_client import ApifyClient

parser = argparse.ArgumentParser()
parser.add_argument("--city",   default="Peniche",      help="Cidade alvo")
parser.add_argument("--niche",  default="restaurante",  help="Nicho / segmento")
parser.add_argument("--output", default=None,           help="Caminho do Excel de saída")
args, _ = parser.parse_known_args()

CITY  = args.city
NICHE = args.niche
OUTPUT_PATH = args.output or "/Users/raphaelbruno/Documents/Prospeção - Agente AI/Restaurantes Zona Oeste.xlsx"

APIFY_KEY = os.environ.get("APIFY_KEY", "")
SKIP_CHANNELS = {'p', 'explore', 'reel', 'reels', 'stories', 'accounts', 'tv', 'popular', ''}

# Coordenadas de Peniche (usadas apenas quando cidade = Peniche)
PENICHE_LAT = 39.3568749
PENICHE_LNG = -9.3786838

client = ApifyClient(APIFY_KEY)

# ── 1. Google Maps ────────────────────────────────────────────────────────────
print(f"[1/4] Scraping Google Maps — {NICHE} em {CITY}...")
maps_params = {
    "searchStringsArray": [NICHE],
    "maxCrawledPlacesPerSearch": 60,
    "language": "pt-PT",
    "maxReviews": 0,
    "exportPlaceUrls": False,
    "additionalInfo": True,
}
if CITY.lower() == "peniche":
    maps_params["lat"]  = PENICHE_LAT
    maps_params["lng"]  = PENICHE_LNG
    maps_params["zoom"] = 12
else:
    maps_params["locationQuery"] = CITY
    maps_params["zoom"] = 14

run = client.actor("compass/crawler-google-places").call(run_input=maps_params)

places_raw = list(client.dataset(run["defaultDatasetId"]).iterate_items())
print(f"  Lugares encontrados: {len(places_raw)}")

# Filtra duplicados por nome
seen = set()
places = []
for p in places_raw:
    name = (p.get("title") or "").strip()
    cat = (p.get("categoryName") or "").lower()
    # Filtra não-restaurantes
    if not name or name in seen:
        continue
    seen.add(name)
    places.append(p)

print(f"  Únicos: {len(places)}")

# ── 2. Extrair dados do Maps ──────────────────────────────────────────────────
def clean_phone(raw):
    if not raw:
        return None
    digits = re.sub(r'\D', '', str(raw))
    if len(digits) == 9 and digits[0] in '9267':
        return '+351 ' + digits
    if len(digits) == 12 and digits[:3] == '351':
        return '+351 ' + digits[3:]
    return raw

rows = []
for p in places:
    # Sinais de takeaway/delivery
    category = (p.get("categoryName") or "").lower()
    cats_all = " ".join([c.lower() for c in (p.get("categories") or [])])
    desc = (p.get("description") or "").lower()
    menu_url = p.get("menu") or ""
    order_online = bool(p.get("orderBy"))  # links para delivery

    # Delivery apps na web (Uber Eats, Glovo, etc.)
    web = (p.get("website") or "").lower()
    has_delivery_app = any(x in web for x in ["ubereats","glovo","bolt food","zomato","yelp"])

    # Palavra-chave takeaway em categoria ou descrição
    takeaway_signal = any(x in (category + cats_all + desc) for x in
                         ["take away","takeaway","delivery","entregas","take-away","para viagem"])

    rows.append({
        "Business Name": p.get("title",""),
        "Category": p.get("categoryName",""),
        "Address": p.get("address",""),
        "Rating": p.get("totalScore"),
        "# Reviews": p.get("reviewsCount"),
        "Phone": clean_phone(p.get("phone")),
        "Website": p.get("website",""),
        "Google Maps URL": p.get("url",""),
        "Takeaway Signal": takeaway_signal or has_delivery_app or bool(order_online),
        "Order Online": bool(order_online),
        "Menu URL": menu_url,
        "Instagram Handle": "",
        "Instagram URL": "",
        "Seguidores": None,
        "Posts": None,
        "Bio": "",
        "Score AI Potencial": 0,
    })

df = pd.DataFrame(rows)
names = df["Business Name"].tolist()
print(f"\n  DataFrame: {len(df)} negócios")

# ── 3. Instagram handles via Google ──────────────────────────────────────────
print("\n[2/4] Buscando Instagram handles...")
queries = [f'site:instagram.com "{name}" {CITY}' for name in names]
run2 = client.actor("apify/google-search-scraper").call(run_input={
    "queries": "\n".join(queries),
    "resultsPerPage": 3,
    "maxPagesPerQuery": 1,
    "languageCode": "pt-PT",
    "countryCode": "pt",
})
search_results = list(client.dataset(run2["defaultDatasetId"]).iterate_items())

handles = {}
for item in search_results:
    term = item.get("searchQuery", {}).get("term", "")
    # Match ao nome
    matched = None
    for name in names:
        if name.lower()[:15] in term.lower():
            matched = name
            break
    if not matched:
        continue
    for r in item.get("organicResults", []):
        ch = r.get("channelName", "").strip("/")
        url = r.get("url", "")
        if "instagram.com/" in url and ch not in SKIP_CHANNELS:
            handles[matched] = ch
            break

print(f"  Handles encontrados: {len(handles)}")

df["Instagram Handle"] = df["Business Name"].apply(lambda n: f"@{handles[n]}" if n in handles else "")
df["Instagram URL"] = df["Business Name"].apply(lambda n: f"https://instagram.com/{handles[n]}" if n in handles else "")

# ── 4. Instagram profiles ────────────────────────────────────────────────────
profiles = {}
if handles:
    print(f"\n[3/4] Scraping {len(handles)} perfis Instagram...")
    run3 = client.actor("apify/instagram-profile-scraper").call(run_input={
        "usernames": list(handles.values())
    })
    raw = list(client.dataset(run3["defaultDatasetId"]).iterate_items())
    profiles = {p.get("username","").lower(): p for p in raw}
    print(f"  Perfis: {len(profiles)}")

    for idx, row in df.iterrows():
        name = row["Business Name"]
        handle = handles.get(name, "")
        p = profiles.get(handle.lower(), {})
        if p:
            df.at[idx, "Seguidores"] = p.get("followersCount")
            df.at[idx, "Posts"] = p.get("postsCount")
            df.at[idx, "Bio"] = p.get("biography", "")

# ── 5. Score AI Potencial ────────────────────────────────────────────────────
print("\n[4/4] Calculando Score AI Potencial...")

def score_ai(row):
    s = 0
    # Reviews Google: quanto mais, mais estabelecido e mais overloaded (precisa automação)
    reviews = row.get("# Reviews") or 0
    s += min(25, int(math.log10(reviews + 1) / math.log10(501) * 25)) if reviews > 0 else 0

    # Rating: 4+ = bom negócio com fluxo real
    rating = row.get("Rating") or 0
    if rating >= 4.5: s += 10
    elif rating >= 4.0: s += 7
    elif rating >= 3.5: s += 3

    # Instagram seguidores (log scale, 5k = max)
    followers = row.get("Seguidores") or 0
    s += min(20, int(math.log10(followers + 1) / math.log10(5001) * 20)) if followers > 0 else 0

    # Posts Instagram
    posts = row.get("Posts") or 0
    s += min(10, int(posts / 200 * 10))

    # Sinais digitais de takeaway/delivery
    if row.get("Takeaway Signal"): s += 15
    if row.get("Order Online"):    s += 10
    if row.get("Website"):         s += 5
    if row.get("Instagram Handle"):s += 5

    return min(100, s)

df["Score AI Potencial"] = df.apply(score_ai, axis=1)
df["Status Lead"] = "Cold"
df = df.sort_values("Score AI Potencial", ascending=False).reset_index(drop=True)

df.to_excel(OUTPUT_PATH, index=False)
print(f"\n✅ Salvo: {OUTPUT_PATH}")
print(f"\nTop 15 por Score AI Potencial:")
print(df[["Business Name","# Reviews","Rating","Seguidores","Takeaway Signal","Score AI Potencial"]].head(15).to_string(index=False))
