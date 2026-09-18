import requests,re
t=requests.get('https://lrec.elra.info/lrec2024-main-0883').text
for pat in ['citation_title','citation_author','citation_publication_date']:
 print(pat,re.findall(pat+r'" content="(.*?)"',t)[:20])
