import os
#!/usr/bin/env python3
"""Busca telefones via Google Search e extrai números PT dos resultados."""
import pandas as pd, re
from apify_client import ApifyClient

APIFY_KEY = os.environ.get("APIFY_KEY", "")
EXCEL_PATH = "/Users/raphaelbruno/Documents/Prospeção - Agente AI/Surf School Peniche Enriched.xlsx"

client = ApifyClient(APIFY_KEY)

df = pd.read_excel(EXCEL_PATH)
df = df.where(pd.notna(df), None)
names = df['Business Name'].tolist()

# PT phone pattern: +351 followed by 9 digits, or 9XX XXX XXX, or 2XX XXX XXX
PT_PHONE = re.compile(r'(\+351[\s\-]?)?(\(?[239]\d{1,2}\)?[\s\-]?\d{3}[\s\-]?\d{3,4})')

def extract_phone(text):
    """Extrai primeiro número PT válido de um texto."""
    for m in PT_PHONE.finditer(text or ''):
        raw = m.group(0).strip()
        digits = re.sub(r'\D', '', raw)
        # PT mobile: 9 digits starting with 9 (or 12 with 351)
        if len(digits) == 9 and digits[0] in '9267':
            return '+351 ' + digits
        if len(digits) == 12 and digits[:3] == '351':
            return '+' + digits[:3] + ' ' + digits[3:]
    return None

print(f"Buscando telefones de {len(names)} escolas...")

# Batch: 1 query por escola, máximo de eficiência
queries = [f'"{name}" peniche telefone contacto' for name in names]

run = client.actor("apify/google-search-scraper").call(run_input={
    "queries": "\n".join(queries),
    "resultsPerPage": 5,
    "maxPagesPerQuery": 1,
    "languageCode": "pt-PT",
    "countryCode": "pt",
})

results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
print(f"Resultados: {len(results)}")

# Extrai telefones
phones = {}
for item in results:
    term = item.get('searchQuery', {}).get('term', '')
    # Match ao nome da escola
    school = None
    for name in names:
        if name.lower() in term.lower():
            school = name
            break
    if not school:
        continue

    # Procura telefone em todos os resultados orgânicos
    for r in item.get('organicResults', []):
        text = (r.get('description','') or '') + ' ' + (r.get('title','') or '')
        phone = extract_phone(text)
        if phone and school not in phones:
            phones[school] = phone
            break

    # Tenta também no AI overview ou outros campos
    if school not in phones:
        full_text = str(item)
        phone = extract_phone(full_text)
        if phone:
            phones[school] = phone

print(f"\nTelefones encontrados: {len(phones)}/{len(names)}")
for name, phone in list(phones.items())[:15]:
    print(f"  ✓ {name[:45]} → {phone}")

# Atualiza Excel
df['Phone'] = df['Business Name'].apply(lambda n: phones.get(n))
found = df['Phone'].notna().sum()
print(f"\nTotal com telefone: {found}")

df.to_excel(EXCEL_PATH, index=False)
print(f"✅ Excel atualizado")
