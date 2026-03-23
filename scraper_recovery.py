import os
#!/usr/bin/env python3
"""Recupera handles das escolas que não foram encontradas na primeira passagem."""
import pandas as pd
from apify_client import ApifyClient
import re, math

APIFY_KEY = os.environ.get("APIFY_KEY", "")
ENRICHED_PATH = "/Users/raphaelbruno/Documents/Prospeção - Agente AI/Surf School Peniche Enriched.xlsx"
SKIP_CHANNELS = {'p', 'explore', 'reel', 'reels', 'stories', 'accounts', 'tv', 'popular', ''}

client = ApifyClient(APIFY_KEY)

df = pd.read_excel(ENRICHED_PATH)
missing = df[df['Instagram Handle'].isna() | (df['Instagram Handle'] == '')]['Business Name'].tolist()
print(f"Escolas sem handle: {len(missing)}")
for m in missing:
    print(f"  - {m}")

def simplify_name(name):
    """Remove sufixos comuns para simplificar a busca."""
    name = re.sub(r'\s*-\s*(Peniche|Baleal)[^|]*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\|.*', '', name)
    name = re.sub(r'\s*(No\.|#)\s*\d+.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*-\s*All levels.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*/.*', '', name)
    return name.strip()

# Gera múltiplas queries por escola
queries_map = {}  # query → school_name
for name in missing:
    simple = simplify_name(name)
    # Query 1: nome simplificado com aspas + peniche
    q1 = f'site:instagram.com "{simple}"'
    # Query 2: sem aspas, mais amplo
    q2 = f'site:instagram.com {simple} peniche surf instagram'
    queries_map[q1] = name
    if simple != name:
        queries_map[q2] = name

print(f"\nQueries a executar: {len(queries_map)}")
for q, n in queries_map.items():
    print(f"  [{n}] → {q}")

print("\nA correr Google Search Scraper...")
run = client.actor("apify/google-search-scraper").call(run_input={
    "queries": "\n".join(queries_map.keys()),
    "resultsPerPage": 5,
    "maxPagesPerQuery": 1,
    "languageCode": "pt-PT",
    "countryCode": "pt"
})

results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
print(f"Resultados: {len(results)}")

def extract_handle(item):
    for r in item.get('organicResults', []):
        channel = r.get('channelName', '').strip('/')
        url = r.get('url', '')
        if 'instagram.com/' in url and channel not in SKIP_CHANNELS:
            return channel
    return None

# Mapeia resultados → handles
new_handles = {}
for item in results:
    term = item.get('searchQuery', {}).get('term', '')
    school = queries_map.get(term)
    if not school or school in new_handles:
        continue
    handle = extract_handle(item)
    if handle:
        new_handles[school] = handle

print(f"\nHandles recuperados: {len(new_handles)}/{len(missing)}")
for school, handle in new_handles.items():
    print(f"  ✓ {school} → @{handle}")

still_missing = [n for n in missing if n not in new_handles]
if still_missing:
    print(f"\nAinda sem handle ({len(still_missing)}):")
    for n in still_missing:
        print(f"  ✗ {n}")

# Scrapa os novos perfis
new_profiles = {}
if new_handles:
    print(f"\nScraping {len(new_handles)} novos perfis...")
    run2 = client.actor("apify/instagram-profile-scraper").call(run_input={
        "usernames": list(new_handles.values())
    })
    raw = list(client.dataset(run2["defaultDatasetId"]).iterate_items())
    new_profiles = {p.get('username', '').lower(): p for p in raw}
    print(f"Perfis obtidos: {len(new_profiles)}")

def activity_score(p):
    if not p:
        return 0
    followers = p.get('followersCount') or 0
    posts = p.get('postsCount') or 0
    f_score = min(40, int(math.log10(followers + 1) / math.log10(10001) * 40)) if followers > 0 else 0
    p_score = min(30, int(posts / 100 * 30))
    v_score = 10 if p.get('verified') else 0
    b_score = 10 if p.get('biography') else 0
    priv_score = -10 if p.get('isPrivate') else 0
    return max(0, f_score + p_score + v_score + b_score + priv_score)

# Atualiza o Excel
print("\nAtualizando Excel...")
for idx, row in df.iterrows():
    name = row['Business Name']
    if name not in new_handles:
        continue
    handle = new_handles[name]
    profile = new_profiles.get(handle.lower(), {})
    df.at[idx, 'Instagram Handle'] = f"@{handle}"
    df.at[idx, 'Instagram URL'] = f"https://instagram.com/{handle}"
    df.at[idx, 'Seguidores'] = profile.get('followersCount')
    df.at[idx, 'Seguindo'] = profile.get('followsCount')
    df.at[idx, 'Posts'] = profile.get('postsCount')
    df.at[idx, 'Bio'] = profile.get('biography', '')
    df.at[idx, 'Verificado'] = profile.get('verified', False)
    df.at[idx, 'Privado'] = profile.get('isPrivate', False)
    df.at[idx, 'Score Atividade'] = activity_score(profile)

df = df.sort_values('Score Atividade', ascending=False).reset_index(drop=True)
df.to_excel(ENRICHED_PATH, index=False)

total_found = df[df['Instagram Handle'].notna() & (df['Instagram Handle'] != '')].shape[0]
print(f"\n✅ Excel atualizado: {ENRICHED_PATH}")
print(f"Total com Instagram: {total_found}/{len(df)}")
print(f"\nTop 10:")
print(df[['Business Name', 'Instagram Handle', 'Seguidores', 'Posts', 'Score Atividade']].head(10).to_string(index=False))
