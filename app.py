import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title='Radar Inteligente de Seguros', page_icon='🛡️', layout='wide')
st.markdown('''<style>.stApp{background:#f5f8fb}.block-container{padding-top:1.8rem}.metric-card{background:white;border:1px solid #dde7ef;border-radius:12px;padding:16px}.tag{color:#146c43;font-weight:700}</style>''', unsafe_allow_html=True)
st.title('🛡️ Radar Inteligente de Oportunidades em Seguros')
st.caption('Dados, território e IA para decisões comerciais mais inteligentes')

c1,c2,c3=st.columns([2.2,1.4,.7])
with c1: rua=st.text_input('Endereço','Rua Itapicuru, 203, Perdizes')
with c2: cidade=st.text_input('Cidade','São Paulo, SP, Brasil')
with c3: raio=st.selectbox('Raio',[3,5,10],index=1,format_func=lambda x:f'{x} km')

@st.cache_data(ttl=3600,show_spinner=False)
def geocode(q):
    r=requests.get('https://nominatim.openstreetmap.org/search',params={'q':q,'format':'json','limit':1,'countrycodes':'br'},headers={'User-Agent':'radar-seguros-demo/1.0'},timeout=15)
    r.raise_for_status(); data=r.json()
    return data[0] if data else None

@st.cache_data(ttl=1800,show_spinner=False)
def insurance_places(lat,lon,radius_m):
    query=f'''[out:json][timeout:20];(node(around:{radius_m},{lat},{lon})[office=insurance];way(around:{radius_m},{lat},{lon})[office=insurance];node(around:{radius_m},{lat},{lon})[shop=insurance];way(around:{radius_m},{lat},{lon})[shop=insurance];);out center tags;'''
    r=requests.get('https://overpass-api.de/api/interpreter',params={'data':query},headers={'User-Agent':'radar-seguros-demo/1.0'},timeout=30)
    r.raise_for_status(); return r.json().get('elements',[])

if st.button('🔎 Analisar região',type='primary',use_container_width=True):
    with st.spinner('Localizando o endereço e analisando a região...'):
        try: loc=geocode(f'{rua}, {cidade}')
        except Exception as e: loc=None; st.error(f'Falha temporária na geocodificação: {e}')
    if not loc:
        st.warning('Não encontrei esse endereço. Tente incluir número, bairro, cidade e estado.')
    else:
        lat,lon=float(loc['lat']),float(loc['lon'])
        st.session_state['last']=(lat,lon,loc.get('display_name',''))
        try: places=insurance_places(lat,lon,raio*1000)
        except Exception: places=[]; st.info('O endereço foi localizado, mas a consulta pública de estabelecimentos de seguros não respondeu agora.')
        pts=[{'lat':lat,'lon':lon,'tipo':'Endereço'}]
        names=[]
        for e in places:
            la=e.get('lat') or e.get('center',{}).get('lat'); lo=e.get('lon') or e.get('center',{}).get('lon')
            if la and lo: pts.append({'lat':la,'lon':lo,'tipo':'Seguros'})
            name=e.get('tags',{}).get('name','Estabelecimento de seguros')
            if name not in names:names.append(name)
        left,right=st.columns([1.3,1])
        with left:
            st.subheader('🗺️ Região analisada')
            st.map(pd.DataFrame(pts),latitude='lat',longitude='lon',zoom=12 if raio>=5 else 13,height=470)
            st.caption(f'Ponto localizado: {loc.get("display_name", rua)}')
        with right:
            st.subheader('📊 Dados disponíveis agora')
            a,b=st.columns(2); a.metric('Latitude',f'{lat:.5f}'); b.metric('Longitude',f'{lon:.5f}')
            a,b=st.columns(2); a.metric('Raio',f'{raio} km'); b.metric('Locais de seguros no OSM',len(names))
            st.markdown('**Camadas oficiais a incorporar na próxima versão**')
            st.write('• População e domicílios: IBGE, Censo 2022 por setor censitário')
            st.write('• Renda: agregados estatísticos compatíveis com o território')
            st.write('• Registro de corretores: SUSEP')
            if names:
                st.markdown('**Exemplos mapeados**')
                for n in names[:8]: st.write('• '+n)
        st.divider()
        st.subheader('✨ Motor de oportunidade')
        st.info('A versão atual só pontua um produto quando houver dados suficientes. Assim, a demonstração não apresenta números socioeconômicos inventados.')
        cols=st.columns(5)
        for col,(icon,name) in zip(cols,[('🏠','Residencial'),('❤','Vida'),('📈','Previdência'),('🚗','Auto'),('🏢','Empresarial')]):
            with col:
                st.markdown(f'<div class="metric-card"><b>{icon} {name}</b><br><span class="tag">Perfil IBGE pendente</span></div>',unsafe_allow_html=True)
else:
    st.info('Use o endereço de Perdizes já preenchido e clique em **Analisar região**. Desta vez o processamento ocorre no servidor do Streamlit.')

st.divider()
st.caption('MVP demonstrativo. Geocodificação: OpenStreetMap/Nominatim. Concorrência cartográfica: OpenStreetMap/Overpass. Dados socioeconômicos serão incorporados a partir das bases oficiais do IBGE.')
