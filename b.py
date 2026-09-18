import requests,re
for u in ['https://aclanthology.org/2024.emnlp-industry.34/','https://aclanthology.org/2025.findings-emnlp.208/','https://aclanthology.org/2025.acl-long.757/']:
 t=requests.get(u).text; print('\n',u); print(re.findall(r'<title>(.*?) - ACL Anthology',t)[:1]); print(re.findall(r'<meta content="(.*?)" name=citation_author>',t)[1:8]); print(re.findall(r'name=citation_conference_title><meta content="(.*?)"',t)); print(re.findall(r'name=citation_doi><meta content="(.*?)"',t))
