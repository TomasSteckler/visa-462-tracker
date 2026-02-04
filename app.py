import streamlit as st
import pdfplumber
import re
import json
import math
from datetime import datetime

st.set_page_config(page_title="Visa 462 Tracker", page_icon="🇦🇺")

if 'profiles' not in st.session_state:
    st.session_state.profiles = {}
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

st.title("🇦🇺 Visa 462 Days Tracker")

with st.sidebar:
    st.header("👤 Perfil")
    
    with st.expander("➕ Crear nuevo"):
        nuevo = st.text_input("Nombre:")
        if st.button("Crear") and nuevo:
            if nuevo not in st.session_state.profiles:
                st.session_state.profiles[nuevo] = {"days": 0, "history": []}
                st.session_state.current_user = nuevo
                st.rerun()
    
    if st.session_state.profiles:
        users = list(st.session_state.profiles.keys())
        user = st.selectbox("Selecciona:", users)
        st.session_state.current_user = user
    else:
        st.info("Crea un perfil arriba")
        st.stop()

user = st.session_state.current_user
profile = st.session_state.profiles[user]

st.subheader(f"Hola, {user}!")

dias = profile["days"]
faltantes = max(0, 179 - dias)

col1, col2 = st.columns(2)
col1.metric("Días trabajados", f"{dias}/179")
col2.metric("Faltan", faltantes)

st.progress(min(dias/179, 1.0))

if dias >= 179:
    st.balloons()
    st.success("🎉 ¡Cumpliste los 179 días!")

st.divider()

uploaded = st.file_uploader("📄 Sube tu payslip PDF", type="pdf")

if uploaded:
    try:
        with pdfplumber.open(uploaded) as pdf:
            texto = ""
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texto += t + "\n"
            
            if not texto.strip():
                st.error("PDF vacío o escaneado")
                st.stop()
            
            nums = re.findall(r"(?<!\$)\b(\d{1,3}(?:[\.,]\d{1,2})?)\b", texto)
            candidatos = sorted(list(set([float(n.replace(',','.')) for n in nums if 0.5 <= float(n.replace(',','.')) <= 100])), reverse=True)
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()
    
    if candidatos:
        st.success(f"Encontré {len(candidatos)} valores")
        seleccion = st.multiselect("Selecciona horas:", candidatos[:10], format_func=lambda x: f"{x}h")
        
        if seleccion:
            total = sum(seleccion)
            st.write(f"**Total: {total} horas**")
            
            dias_sumar = 7 if total >= 35 else math.ceil(total/7.6)
            st.info(f"Se sumarán **{dias_sumar} días**")
            
            if st.button("✅ Confirmar", type="primary"):
                profile["days"] += dias_sumar
                profile["history"].append(f"{datetime.now().strftime('%d/%m/%Y')} - +{dias_sumar} días ({total}h)")
                st.success(f"¡Sumados {dias_sumar} días!")
                st.rerun()
    else:
        st.error("No encontré números válidos")

st.divider()

with st.expander("✍️ Agregar manualmente"):
    horas = st.number_input("Horas:", 0.0, 100.0, 0.0, 0.5)
    if st.button("➕ Agregar") and horas > 0:
        dias_manual = 7 if horas >= 35 else math.ceil(horas/7.6)
        profile["days"] += dias_manual
        profile["history"].append(f"{datetime.now().strftime('%d/%m/%Y')} - +{dias_manual} días ({horas}h)")
        st.success(f"Agregados {dias_manual} días")
        st.rerun()

with st.expander("📋 Historial"):
    if profile["history"]:
        for h in reversed(profile["history"]):
            st.text(h)
    else:
        st.info("Sin registros")
