import requests,re
t=requests.get('https://www.ijcai.org/proceedings/2025/921').text
for pat in ['citation_title','citation_author','citation_publication_date']:
 print(pat,re.findall(pat+r'" content="(.*?)"',t))
