import math
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

st.set_page_config(page_title='Radar Inteligente de Seguros', page_icon='🛡️', layout='wide')
st.markdown('''<style>
.stApp{background:#f4f7fb}.block-container{padding-top:1.25rem;max-width:1500px}
.hero{background:linear-gradient(110deg,#063967,#071f3c);padding:24px;border-radius:14px;color:white;margin-bottom:14px}.hero h1{margin:0;font-size:30px}.hero p{margin:5px 0 0;color:#dbeafe}
.card{background:white;border:1px solid #dce6ee;border-radius:12px;padding:16px;min-height:124px}.card .label{font-size:13px;color:#60758a}.card .value{font-size:28px;font-weight:800;color:#07509a;margin:4px 0}.card .source{font-size:11px;color:#7a8997}
.product{background:white;border:1px solid #dce6ee;border-radius:12px;padding:15px;border-left:6px solid #27a45c;min-height:145px}.product h4{margin:0}.product .score{font-size:27px;font-weight:800;color:#07509a}.pill{display:inline-block;padding:3px 9px;border-radius:20px;background:#eaf7ef;color:#167341;font-weight:700;font-size:12px}
.small{font-size:12px;color:#687887}.stButton>button{font-weight:750;border-radius:8px}
</style>''', unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🛡️ Radar Inteligente de Oportunidades em Seguros</h1><p>Dados territoriais reais, leitura comercial e recomendações explicáveis</p></div>', unsafe_allow_html=True)

c1,c2,c3=st.columns([2.1,1.3,.65])
with c1: street=st.text_input('Endereço','Rua Itapicuru, 203, Perdizes')
with c2: city=st.text_input('Cidade','São Paulo, SP, Brasil')
with c3: radius_km=st.selectbox('Raio',[3,5,10],index=1,format_func=lambda x:f'{x} km')

@st.cache_data(ttl=86400,show_spinner=False)
def geocode(q):
    r=requests.get('https://nominatim.openstreetmap.org/search',params={'q':q,'format':'json','limit':1,'countrycodes':'br','addressdetails':1},headers={'User-Agent':'radar-seguros-demo/2.0 contato-demonstracao'},timeout=20)
    r.raise_for_status(); data=r.json(); return data[0] if data else None

@st.cache_data(ttl=3600,show_spinner=False)
def overpass(lat,lon,radius_m):
    q=f'''[out:json][timeout:45];(
      nwr(around:{radius_m},{lat},{lon})[office=insurance];nwr(around:{radius_m},{lat},{lon})[shop=insurance];
      nwr(around:{radius_m},{lat},{lon})[shop=car];nwr(around:{radius_m},{lat},{lon})[amenity=car_rental];
      nwr(around:{radius_m},{lat},{lon})[office=company];nwr(around:{radius_m},{lat},{lon})[office=accountant];
      nwr(around:{radius_m},{lat},{lon})[shop=mall];nwr(around:{radius_m},{lat},{lon})[amenity=hospital];
      nwr(around:{radius_m},{lat},{lon})[amenity=school];nwr(around:{radius_m},{lat},{lon})[amenity=university];
      nwr(around:{radius_m},{lat},{lon})[building=apartments];
    );out center tags;'''
    for endpoint in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
        try:
            r=requests.post(endpoint,data={'data':q},headers={'User-Agent':'radar-seguros-demo/2.0'},timeout=55)
            r.raise_for_status(); return r.json().get('elements',[])
        except Exception: pass
    raise RuntimeError('As duas instâncias públicas de dados cartográficos não responderam.')

def coords(e):
    return (e.get('lat') or e.get('center',{}).get('lat'),e.get('lon') or e.get('center',{}).get('lon'))

def classify(tags):
    if tags.get('office')=='insurance' or tags.get('shop')=='insurance': return 'Seguros'
    if tags.get('shop')=='car' or tags.get('amenity')=='car_rental': return 'Automóveis'
    if tags.get('office') in ('company','accountant'): return 'Empresas'
    if tags.get('shop')=='mall': return 'Centros comerciais'
    if tags.get('amenity')=='hospital': return 'Hospitais'
    if tags.get('amenity') in ('school','university'): return 'Educação'
    if tags.get('building')=='apartments': return 'Apartamentos mapeados'
    return 'Outros'

def make_score(counts):
    # Índices de atratividade relativos, baseados apenas em sinais observáveis no OSM.
    residential=min(95,42+min(counts.get('Apartamentos mapeados',0),80)*0.55+min(counts.get('Seguros',0),15)*0.5)
    business=min(95,38+min(counts.get('Empresas',0),60)*0.7+min(counts.get('Centros comerciais',0),10)*2)
    auto=min(92,36+min(counts.get('Automóveis',0),35)*1.25)
    life=min(90,40+min(counts.get('Hospitais',0),20)*1.3+min(counts.get('Educação',0),30)*0.6)
    pension=min(86,34+min(counts.get('Empresas',0),50)*0.45+min(counts.get('Educação',0),30)*0.65)
    return {'Residencial':round(residential),'Empresarial':round(business),'Auto':round(auto),'Vida':round(life),'Previdência':round(pension)}

def level(v): return 'Muito alto' if v>=80 else 'Alto' if v>=65 else 'Médio/alto' if v>=50 else 'Em validação'

if st.button('🔎 Analisar região',type='primary',use_container_width=True):
    with st.spinner('Localizando o endereço e cruzando as camadas cartográficas...'):
        try: loc=geocode(f'{street}, {city}')
        except Exception as e: loc=None; st.error(f'Geocodificação indisponível: {e}')
    if not loc:
        st.warning('Endereço não localizado. Inclua número, bairro, cidade e estado.')
        st.stop()
    lat,lon=float(loc['lat']),float(loc['lon'])
    try:
        with st.spinner('Mapeando seguros, empresas, automóveis, apartamentos e equipamentos urbanos...'):
            elements=overpass(lat,lon,radius_km*1000)
        map_status='Completa'
    except Exception as e:
        elements=[]; map_status='Parcial'; st.warning(str(e))
    rows=[]
    for e in elements:
        la,lo=coords(e); tags=e.get('tags',{}); typ=classify(tags)
        if la and lo: rows.append({'lat':float(la),'lon':float(lo),'tipo':typ,'nome':tags.get('name',typ)})
    df=pd.DataFrame(rows)
    counts=df['tipo'].value_counts().to_dict() if not df.empty else {}
    scores=make_score(counts)
    overall=round(sum(scores.values())/len(scores))

    st.success(f'Análise concluída para {loc.get("display_name",street)}')
    m1,m2,m3,m4,m5=st.columns(5)
    metrics=[('Raio',f'{radius_km} km','Geometria da análise'),('Seguros mapeados',counts.get('Seguros',0),'OpenStreetMap'),('Empresas mapeadas',counts.get('Empresas',0),'OpenStreetMap'),('Apartamentos mapeados',counts.get('Apartamentos mapeados',0),'OpenStreetMap'),('Índice observável',f'{overall}/100','Sinais cartográficos')]
    for col,(lab,val,src) in zip([m1,m2,m3,m4,m5],metrics):
        col.markdown(f'<div class="card"><div class="label">{lab}</div><div class="value">{val}</div><div class="source">Fonte: {src}</div></div>',unsafe_allow_html=True)

    left,right=st.columns([1.35,1])
    with left:
        st.subheader('🗺️ Mapa da região')
        center=pd.DataFrame([{'lat':lat,'lon':lon,'nome':'Endereço','tipo':'Endereço'}])
        plotdf=pd.concat([center,df],ignore_index=True) if not df.empty else center
        color_map={'Endereço':[230,50,50,220],'Seguros':[21,126,214,210],'Empresas':[31,168,88,180],'Automóveis':[245,158,11,190],'Apartamentos mapeados':[127,86,217,150],'Hospitais':[220,38,38,180],'Educação':[6,182,212,180],'Centros comerciais':[236,72,153,180]}
        plotdf['color']=plotdf['tipo'].apply(lambda x:color_map.get(x,[100,116,139,150]))
        layers=[pdk.Layer('ScatterplotLayer',data=plotdf,get_position='[lon, lat]',get_fill_color='color',get_radius=90 if radius_km<=5 else 140,pickable=True),pdk.Layer('ScatterplotLayer',data=pd.DataFrame([{'lat':lat,'lon':lon}]),get_position='[lon, lat]',get_fill_color='[15,118,210,30]',get_line_color='[15,118,210,180]',stroked=True,get_radius=radius_km*1000,line_width_min_pixels=2)]
        deck=pdk.Deck(layers=layers,initial_view_state=pdk.ViewState(latitude=lat,longitude=lon,zoom=12 if radius_km==5 else 13 if radius_km==3 else 11,pitch=0),tooltip={'html':'<b>{nome}</b><br>{tipo}'})
        st.pydeck_chart(deck,height=520)
        st.caption('O círculo representa o raio selecionado. A cobertura de pontos depende do cadastramento no OpenStreetMap.')
    with right:
        st.subheader('📍 Perfil territorial observável')
        table=pd.DataFrame([{'Camada':k,'Quantidade':v} for k,v in sorted(counts.items(),key=lambda x:x[1],reverse=True)])
        if table.empty: st.info('Sem pontos cartográficos disponíveis nesta consulta.')
        else: st.dataframe(table,use_container_width=True,hide_index=True,height=330)
        st.markdown('**Qualidade e origem**')
        st.write(f'• Geocodificação: **OpenStreetMap/Nominatim**')
        st.write(f'• Pontos territoriais: **OpenStreetMap/Overpass ({map_status})**')
        st.write('• SUSEP: **pendente de credencial empresarial**')
        st.write('• Renda/população: **pendente de recorte censitário IBGE**')

    st.divider(); st.subheader('🎯 Produtos com maior aderência territorial')
    ordered=sorted(scores.items(),key=lambda x:x[1],reverse=True)
    cols=st.columns(5)
    reasons={'Residencial':'apartamentos e densidade residencial observável','Empresarial':'empresas e centros comerciais mapeados','Auto':'lojas e serviços ligados a automóveis','Vida':'equipamentos de saúde e educação no território','Previdência':'atividade empresarial e educacional observável'}
    icons={'Residencial':'🏠','Empresarial':'🏢','Auto':'🚗','Vida':'❤','Previdência':'📈'}
    for col,(name,score) in zip(cols,ordered):
        col.markdown(f'<div class="product"><h4>{icons[name]} {name}</h4><div class="score">{score}/100</div><span class="pill">{level(score)}</span><p class="small">Base: {reasons[name]}.</p></div>',unsafe_allow_html=True)

    st.subheader('✨ Leitura comercial explicável')
    top=ordered[:3]
    competition=counts.get('Seguros',0)
    st.markdown(f'''O território apresenta **{len(df)} sinais cartográficos úteis** dentro de {radius_km} km. Os produtos que aparecem primeiro são **{top[0][0]}**, **{top[1][0]}** e **{top[2][0]}**, porque o modelo encontrou maior presença relativa dos indicadores associados a essas categorias. Foram mapeados **{competition} estabelecimentos de seguros**, um indicador de presença competitiva, mas não uma contagem oficial de corretores.

**Uso correto na apresentação:** este índice é uma triagem comercial baseada em dados territoriais observáveis. Ele não representa propensão individual, não usa dados pessoais e será enriquecido com população, domicílios e renda quando a camada censitária do IBGE estiver incorporada.''')

    with st.expander('Como o índice foi calculado'):
        st.write('O protótipo aplica regras transparentes sobre quantidades de apartamentos, empresas, centros comerciais, automóveis, hospitais e instituições de ensino registradas no OpenStreetMap. Cada indicador tem teto para evitar que áreas com muitos registros dominem o resultado. Os valores são comparáveis dentro da demonstração, mas ainda não são um modelo atuarial nem uma previsão de vendas.')
    with st.expander('Estabelecimentos de seguros encontrados'):
        ins=df[df['tipo']=='Seguros'][['nome','lat','lon']] if not df.empty else pd.DataFrame()
        if ins.empty: st.write('Nenhum ponto de seguros cadastrado foi encontrado.')
        else: st.dataframe(ins,use_container_width=True,hide_index=True)
else:
    st.info('Mantenha o endereço já preenchido e clique em **Analisar região**.')

st.divider(); st.caption('Fontes em uso: OpenStreetMap/Nominatim e OpenStreetMap/Overpass. Próximas integrações: agregados e malha do Censo 2022/IBGE; base autenticada de corretores/SUSEP. O protótipo não usa dados pessoais para recomendar produtos.')
