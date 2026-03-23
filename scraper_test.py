import os
#!/usr/bin/env python3
"""Teste rápido: busca Instagram de 3 escolas via Apify Google Search"""
import pandas as pd
from apify_client import ApifyClient
import re, json

APIFY_KEY = os.environ.get("APIFY_KEY", "")
EXCEL_PATH = "/Users/raphaelbruno/Documents/Prospeção - Agente AI/Surf School Peniche .xlsx"

client = ApifyClient(APIFY_KEY)

df = pd.read_excel(EXCEL_PATH)
names = df['Business Name'].tolist()[:3]  # só 3 para testar

print(f"Escolas a testar: {names}\n")

# Step 1: Busca Google para encontrar handles Instagram
queries = [f'site:instagram.com "{name}"' for name in names]
print("Queries:\n" + "\n".join(queries))
print("\nA correr Google Search Scraper...")

run = client.actor("apify/google-search-scraper").call(run_input={
    "queries": "\n".join(queries),
    "resultsPerPage": 3,
    "maxPagesPerQuery": 1,
    "languageCode": "pt-PT",
    "countryCode": "pt"
})

results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
print(f"\nResultados recebidos: {len(results)}")
print("\n=== RAW OUTPUT (primeiros 2) ===")
print(json.dumps(results[:2], indent=2, default=str))

# Extrai handles
def extract_handle(results, school_name):
    for item in results:
        q = item.get('searchQuery', {}).get('query', '') or item.get('query', '')
        if school_name.lower()[:12] not in q.lower():
            continue
        for r in item.get('organicResults', []):
            url = r.get('url', '')
            if 'instagram.com/' in url:
                m = re.search(r'instagram\.com/([^/?#\s]+)', url)
                if m:
                    h = m.group(1).strip('/')
                    if h not in ['p', 'explore', 'reel', 'stories', 'accounts', 'tv']:
                        return h
    return None

handles = {name: extract_handle(results, name) for name in names}
print("\n=== HANDLES ENCONTRADOS ===")
for k, v in handles.items():
    print(f"  {k} → {v}")
