import requests
for d in ['10.1609/aaai.v35i16.17689','10.1609/aaai.v37i11.26560','10.1609/aaai.v39i23.34630','10.1016/j.ins.2024.121251','10.18653/v1/2022.acl-long.21','10.18653/v1/D17-1314']:
 x=requests.get('https://api.openalex.org/works/https://doi.org/'+d,timeout=30).json(); print(d,x.get('publication_year'),x.get('title')); print([a['author']['display_name'] for a in x.get('authorships',[])])
