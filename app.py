import json, math, re
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

st.set_page_config(page_title='Radar Seguros SP V3',page_icon='🛡️',layout='wide')
st.markdown('''<style>.stApp{background:#f4f7fb}.block-container{max-width:1500px;padding-top:1.2rem}.hero{padding:23px;border-radius:14px;background:linear-gradient(110deg,#063968,#061d38);color:#fff}.hero h1{margin:0}.box{background:#fff;border:1px solid #dbe6ef;border-radius:12px;padding:15px}.src{font-size:11px;color:#708090}.big{font-size:25px;font-weight:800;color:#07519a}.ok{color:#198754;font-weight:800}.warn{color:#996400;font-weight:800}</style>''',unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🛡️ Radar Inteligente de Seguros | São Paulo</h1><p>V3: fontes públicas oficiais e metodologia transparente</p></div>',unsafe_allow_html=True)

c1,c2,c3=st.columns([2.1,1.2,.7])
with c1: address=st.text_input('Endereço','Rua Itapicuru, 203, Perdizes')
with c2: city=st.text_input('Cidade','São Paulo, SP, Brasil',disabled=True)
with c3: radius=st.selectbox('Raio',[3,5,10],index=1,format_func=lambda x:f'{x} km')

HEAD={'User-Agent':'radar-seguros-sp-v3/1.0 demonstracao'}
@st.cache_data(ttl=86400,show_spinner=False)
def geocode(q):
 r=requests.get('https://nominatim.openstreetmap.org/search',params={'q':q,'format':'json','limit':1,'countrycodes':'br','addressdetails':1},headers=HEAD,timeout=20);r.raise_for_status();x=r.json();return x[0] if x else None
@st.cache_data(ttl=3600,show_spinner=False)
def overpass(lat,lon,rad):
 q=f'''[out:json][timeout:35];(nwr(around:{rad},{lat},{lon})[office=insurance];nwr(around:{rad},{lat},{lon})[shop=insurance];);out center tags;'''
 errs=[]
 for u in ['https://overpass.kumi.systems/api/interpreter','https://overpass-api.de/api/interpreter']:
  try:
   r=requests.post(u,data={'data':q},headers=HEAD,timeout=45);r.raise_for_status();return r.json().get('elements',[])
  except Exception as e: errs.append(str(e))
 return []
@st.cache_data(ttl=86400,show_spinner=False)
def observa():
 urls=['https://dados-abertos-observasampa.prefeitura.sp.gov.br/_temp/DadosAbertos/ObservaSampaDadosAbertosIndicadoresJSON.json','https://dados-abertos-observasampa.prefeitura.sp.gov.br/_temp/DadosAbertos/ObservaSampaDadosAbertosVariaveisJSON.json']
 out=[]
 for u in urls:
  try:
   r=requests.get(u,headers=HEAD,timeout=45);r.raise_for_status();data=r.json()
   if isinstance(data,list): out.extend(data)
   elif isinstance(data,dict):
    for v in data.values():
     if isinstance(v,list): out.extend(v)
  except Exception: pass
 return pd.json_normalize(out,sep=' | ') if out else pd.DataFrame()

def textrow(row): return ' '.join(str(v) for v in row.values if pd.notna(v)).lower()
def district_profile(df,district):
 if df.empty or not district:return pd.DataFrame()
 d=district.lower(); mask=df.apply(lambda r:d in textrow(r),axis=1); sub=df[mask].copy()
 if sub.empty:return sub
 keys='popula|renda|domic|sal[aá]rio|habitante|densidade|emprego|empresa'
 return sub[sub.apply(lambda r:bool(re.search(keys,textrow(r))),axis=1)].tail(20)
def ll(e):return (e.get('lat') or e.get('center',{}).get('lat'),e.get('lon') or e.get('center',{}).get('lon'))

def find_numeric_mentions(df,terms):
 if df.empty:return None,None
 for _,r in df.iloc[::-1].iterrows():
  t=textrow(r)
  if any(x in t for x in terms):
   nums=[]
   for c,v in r.items():
    if pd.notna(v) and re.fullmatch(r'-?[\d.,]+',str(v).strip()): nums.append((c,str(v)))
   if nums:return nums[-1][1],t[:180]
 return None,None

if st.button('🔎 Analisar região',type='primary',use_container_width=True):
 with st.spinner('Consultando endereço, concorrência cartográfica e perfil distrital...'):
  loc=geocode(address+', São Paulo, SP, Brasil')
 if not loc: st.error('Endereço não localizado em São Paulo.');st.stop()
 lat,lon=float(loc['lat']),float(loc['lon']); ad=loc.get('address',{})
 district=ad.get('suburb') or ad.get('city_district') or ad.get('quarter') or ad.get('neighbourhood') or 'Distrito não identificado'
 insurers=overpass(lat,lon,radius*1000)
 odf=observa(); prof=district_profile(odf,district)
 pop,popdesc=find_numeric_mentions(prof,['popula','habitante'])
 income,incdesc=find_numeric_mentions(prof,['renda','salário','salario'])
 homes,homedesc=find_numeric_mentions(prof,['domic'])

 st.success(f'Área localizada: {district} | {loc.get("display_name",address)}')
 labels=[('Distrito/bairro',district,'Nominatim/OSM'),('População distrital',pop or 'Não localizada','ObservaSampa'),('Indicador de renda',income or 'Não localizado','ObservaSampa'),('Domicílios',homes or 'Não localizado','ObservaSampa'),('Seguros no mapa',len(insurers),'OSM/Overpass')]
 cols=st.columns(5)
 for c,(a,b,s) in zip(cols,labels):c.markdown(f'<div class="box"><div>{a}</div><div class="big">{b}</div><div class="src">Fonte: {s}</div></div>',unsafe_allow_html=True)

 pts=[{'lat':lat,'lon':lon,'nome':'Endereço','cor':[225,40,40,230]}];names=[]
 for e in insurers:
  la,lo=ll(e);name=e.get('tags',{}).get('name','Operação de seguros sem nome informado')
  if la and lo:pts.append({'lat':float(la),'lon':float(lo),'nome':name,'cor':[0,119,204,210]})
  if name not in names:names.append(name)
 left,right=st.columns([1.3,1])
 with left:
  st.subheader('🗺️ Território e concorrência')
  pdf=pd.DataFrame(pts)
  layers=[pdk.Layer('ScatterplotLayer',pdf,get_position='[lon,lat]',get_fill_color='cor',get_radius=100,pickable=True),pdk.Layer('ScatterplotLayer',pd.DataFrame([{'lat':lat,'lon':lon}]),get_position='[lon,lat]',get_radius=radius*1000,get_fill_color='[0,120,210,25]',get_line_color='[0,120,210,180]',stroked=True,line_width_min_pixels=2)]
  st.pydeck_chart(pdk.Deck(layers=layers,initial_view_state=pdk.ViewState(latitude=lat,longitude=lon,zoom=12 if radius==5 else 11 if radius==10 else 13),tooltip={'html':'<b>{nome}</b>'}),height=500)
 with right:
  st.subheader('🏢 Corretoras/operações mapeadas')
  if names:
   for n in names[:20]:st.write('• '+n)
  else:st.warning('Nenhum ponto classificado como seguros foi devolvido pelo OpenStreetMap. Isso não significa ausência de corretoras.')
  st.caption('A validação oficial de registro depende da pesquisa ou base autenticada da SUSEP.')

 st.divider();st.subheader('📊 Evidências socioeconômicas oficiais encontradas')
 if prof.empty: st.warning(f'O ObservaSampa não devolveu registros automaticamente associados a “{district}”. O aplicativo não substituirá esse vazio por números fictícios.')
 else:
  show=prof.astype(str).iloc[-12:,:min(8,len(prof.columns))]
  st.dataframe(show,use_container_width=True,hide_index=True)

 # score conservador, exibido apenas quando há base
 base=sum(x is not None for x in [pop,income,homes]); comp=min(len(names),20)
 st.subheader('✨ Leitura comercial')
 if base==0:
  st.info('Ainda não há evidência socioeconômica suficiente para pontuar os produtos. A V3 mantém a análise bloqueada, em vez de inventar renda ou população.')
 else:
  res=min(95,55+base*8); emp=min(90,48+comp); life=min(88,50+base*7); prev=min(86,45+base*8); auto=min(84,45+comp)
  scores={'Residencial':res,'Vida':life,'Previdência':prev,'Auto':auto,'Empresarial':emp}
  cc=st.columns(5)
  for c,(n,v) in zip(cc,sorted(scores.items(),key=lambda x:x[1],reverse=True)):c.metric(n,f'{v}/100')
  st.write('O ranking é uma triagem territorial, não uma previsão atuarial ou recomendação individual. A explicação usa apenas sinais agregados do distrito e concorrência cartográfica observável.')
 with st.expander('Metodologia e limitações'):
  st.write('População, renda e domicílios são procurados nos dados abertos do ObservaSampa no nível territorial disponível. O raio desenhado é exato, mas os indicadores socioeconômicos podem representar o distrito, não o círculo de 5 km. O recorte exato exigirá incorporar a malha dos setores censitários 2022 e seus agregados ao repositório. As corretoras do mapa são registros do OpenStreetMap e não substituem a consulta oficial da SUSEP.')
else:st.info('A V3 está limitada ao município de São Paulo. Clique em **Analisar região** para iniciar.')
st.divider();st.caption('Fontes: Prefeitura de São Paulo/ObservaSampa; GeoSampa e IBGE para a próxima camada setorial; OpenStreetMap/Nominatim/Overpass; SUSEP para validação oficial de corretores.')
