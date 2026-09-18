import requests,re
u='https://aclanthology.org/2024.sigdial-1.64/'
t=requests.get(u).text
print(re.findall(r'<title>(.*?) - ACL Anthology',t)[:1]);
print(re.findall(r'<meta content="(.*?)" name=citation_author>',t)[:10]); print(re.findall(r'name=citation_conference_title>(.*?)<',t)); print(re.findall(r'citation_publication_date>(.*?)<',t)); print(re.findall(r'citation_doi>(.*?)<',t))
