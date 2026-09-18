import requests
for d in ['10.1609/aaai.v35i16.17690','10.1609/aaai.v35i16.17689','10.1609/aaai.v37i11.26560','10.1609/aaai.v39i23.34630','10.1016/j.ins.2024.121251']:
 x=requests.get('https://api.openalex.org/works/https://doi.org/'+d,timeout=30).json(); inv=x.get('abstract_inverted_index'); txt='';
 if inv:
  arr=[]
  for w,ps in inv.items():
   for p in ps: arr.append((p,w))
  txt=' '.join(w for _,w in sorted(arr))
 print('\n',x.get('title'),'\n',txt[:800])
