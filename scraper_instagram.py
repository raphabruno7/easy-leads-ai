import os
#!/usr/bin/env python3
"""
Scraper Instagram - Escolas de Surf Peniche
1. Lê Excel com nomes das escolas
2. Busca handles Instagram via Google (Apify)
3. Scrapa métricas dos perfis (Apify Instagram Profile Scraper)
4. Escreve Excel enriquecido com score de atividade
"""
import pandas as pd
from apify_client import ApifyClient
import re

APIFY_KEY = os.environ.get("APIFY_KEY", "")
EXCEL_PATH = "/Users/raphaelbruno/Documents/Prospeção - Agente AI/Surf School Peniche .xlsx"
OUTPUT_PATH = "/Users/raphaelbruno/Documents/Prospeção - Agente AI/Surf School Peniche Enriched.xlsx"

SKIP_CHANNELS = {'p', 'explore', 'reel', 'reels', 'stories', 'accounts', 'tv', ''}

client = ApifyClient(APIFY_KEY)

# ── 1. Ler Excel ──────────────────────────────────────────────────────────────
df = pd.read_excel(EXCEL_PATH)
names = df['Business Name'].tolist()
print(f"Escolas carregadas: {len(names)}")

# ── 2. Buscar handles via Google Search ───────────────────────────────────────
print(f"\n[1/3] Buscando handles Instagram para {len(names)} escolas...")
queries = [f'site:instagram.com "{name}"' for name in names]

run = client.actor("apify/google-search-scraper").call(run_input={
    "queries": "\n".join(queries),
    "resultsPerPage": 5,
    "maxPagesPerQuery": 1,
    "languageCode": "pt-PT",
    "countryCode": "pt"
})

search_results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
print(f"Resultados de busca: {len(search_results)}")

def extract_handle(item):
    """Extrai handle do primeiro resultado que é um perfil (não post)."""
    for r in item.get('organicResults', []):
        channel = r.get('channelName', '').strip('/')
        url = r.get('url', '')
        if 'instagram.com/' in url and channel not in SKIP_CHANNELS:
            return channel
    return None

def match_school(term, names):
    """Encontra a escola correspondente ao termo de busca."""
    term_lower = term.lower()
    for name in names:
        if name.lower() in term_lower:
            return name
    return None

handles = {}
for item in search_results:
    term = item.get('searchQuery', {}).get('term', '')
    school = match_school(term, names)
    if not school:
        continue
    handle = extract_handle(item)
    if handle:
        handles[school] = handle

print(f"\nHandles encontrados: {len(handles)}/{len(names)}")
for school, handle in handles.items():
    print(f"  ✓ {school} → @{handle}")

not_found = [n for n in names if n not in handles]
if not_found:
    print(f"\nSem handle ({len(not_found)}):")
    for n in not_found[:10]:
        print(f"  ✗ {n}")

# ── 3. Scraper perfis Instagram ───────────────────────────────────────────────
profiles = {}
if handles:
    print(f"\n[2/3] Scraping {len(handles)} perfis Instagram...")
    run2 = client.actor("apify/instagram-profile-scraper").call(run_input={
        "usernames": list(handles.values())
    })
    raw_profiles = list(client.dataset(run2["defaultDatasetId"]).iterate_items())
    profiles = {p.get('username', '').lower(): p for p in raw_profiles}
    print(f"Perfis scrapeados: {len(profiles)}")

# ── 4. Calcular score de atividade ────────────────────────────────────────────
def activity_score(p):
    """Score 0-100 baseado em seguidores, posts e recência."""
    if not p:
        return 0
    followers = p.get('followersCount') or 0
    posts = p.get('postsCount') or 0

    # Seguidores: até 40 pts (log scale, 10k = 40pts)
    import math
    f_score = min(40, int(math.log10(followers + 1) / math.log10(10001) * 40)) if followers > 0 else 0

    # Posts: até 30 pts (100+ posts = 30pts)
    p_score = min(30, int(posts / 100 * 30))

    # Verificado: +10 pts
    v_score = 10 if p.get('verified') else 0

    # Bio preenchida: +10 pts
    b_score = 10 if p.get('biography') else 0

    # Privado: -10 pts
    priv_score = -10 if p.get('isPrivate') else 0

    return max(0, f_score + p_score + v_score + b_score + priv_score)

# ── 5. Enriquecer DataFrame ───────────────────────────────────────────────────
print("\n[3/3] Montando Excel enriquecido...")

def get_profile(school):
    handle = handles.get(school, '')
    return profiles.get(handle.lower(), {}) if handle else {}

df['Instagram Handle'] = df['Business Name'].apply(lambda n: f"@{handles[n]}" if n in handles else '')
df['Instagram URL'] = df['Business Name'].apply(lambda n: f"https://instagram.com/{handles[n]}" if n in handles else '')
df['Seguidores'] = df['Business Name'].apply(lambda n: get_profile(n).get('followersCount'))
df['Seguindo'] = df['Business Name'].apply(lambda n: get_profile(n).get('followsCount'))
df['Posts'] = df['Business Name'].apply(lambda n: get_profile(n).get('postsCount'))
df['Bio'] = df['Business Name'].apply(lambda n: get_profile(n).get('biography', ''))
df['Verificado'] = df['Business Name'].apply(lambda n: get_profile(n).get('verified', False))
df['Privado'] = df['Business Name'].apply(lambda n: get_profile(n).get('isPrivate', False))
df['Score Atividade'] = df['Business Name'].apply(lambda n: activity_score(get_profile(n)))
df['Status Lead'] = 'Cold'

# Ordenar por score descendente
df = df.sort_values('Score Atividade', ascending=False).reset_index(drop=True)

df.to_excel(OUTPUT_PATH, index=False)
print(f"\n✅ Salvo em: {OUTPUT_PATH}")
print(f"\nTop 10 por Score de Atividade:")
print(df[['Business Name', 'Instagram Handle', 'Seguidores', 'Posts', 'Score Atividade']].head(10).to_string(index=False))
