import requests
DOIS=['10.18653/v1/2023.acl-long.538','10.18653/v1/2024.sigdial-1.64','10.1109/lsp.2024.3416882','10.24963/ijcai.2025/921','10.63317/54n6s5mgr4np']
for d in DOIS:
 x=requests.get('https://api.openalex.org/works/https://doi.org/'+d,timeout=30).json(); print('\n',d,x.get('publication_year'),x.get('title'),x.get('type')); print(((x.get('primary_location') or {}).get('source') or {}).get('display_name')); print([a['author']['display_name'] for a in x.get('authorships',[])])
