import requests,re
u='https://aclanthology.org/2023.findings-emnlp.289/'
t=requests.get(u).text
print(re.findall(r'<title>(.*?) - ACL Anthology',t)[:1]); print(re.findall(r'<meta content="(.*?)" name=citation_author>',t)[:10]); print(re.findall(r'name=citation_conference_title><meta content="(.*?)"',t)); print(re.findall(r'name=citation_publication_date><meta content="(.*?)"',t)); print(re.findall(r'name=citation_doi><meta content="(.*?)"',t))
