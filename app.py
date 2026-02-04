import streamlit as st
import pdfplumber
import re
import math
from datetime import datetime

st.set_page_config(page_title="Visa 462 Tracker", page_icon="🇦🇺", initial_sidebar_state="expanded")

if 'profiles' not in st.session_state:
    st.session_state.profiles = {}
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

st.title("🇦🇺 Visa 462 Days Tracker")
st.markdown("Calcula tus días de **Specified Work**")

# --- GESTIÓN DE PERFILES (EN LA PÁGINA PRINCIPAL) ---
st.header("👤 Tu Perfil")

if not st.session_state.profiles:
    st.info("👇 Crea tu primer perfil")
    
nuevo = st.text_input("Nombre del perfil:", key="nuevo", placeholder="Ej: Juan")

if st.button("➕ Crear Perfil", type="primary") and nuevo:
    if nuevo not in st.session_state.profiles:
        st.session_state.profiles[nuevo] = {"days": 0, "history": []}
        st.session_state.current_user = nuevo
        st.success(f"✅ Perfil '{nuevo}' creado")
        st.rerun()
    else:
        st.warning("⚠️ Ese perfil ya existe")

if st.session_state.profiles:
    users = list(st.session_state.profiles.keys())
    
    user = st.selectbox("Selecciona tu perfil:", users, key="select_user")
    st.session_state.current_user = user
    
    profile = st.session_state.profiles[user]
    
    st.divider()
    
    # --- MÉTRICAS ---
    st.subheader(f"Hola, {user}! 👋")
    
    dias = profile["days"]
    faltantes = max(0, 179 - dias)
    
    col1, col2 = st.columns(2)
    col1.metric("📅 Días trabajados", f"{dias} / 179")
    col2.metric("⏳ Faltan", faltantes)
    
    st.progress(min(dias/179, 1.0))
    
    if dias >= 179:
        st.balloons()
        st.success("🎉 ¡Cumpliste los 179 días!")
    
    st.divider()
    
    # --- SUBIR PDF ---
    st.subheader("📄 Agregar Payslip")
    
    uploaded = st.file_uploader("Sube tu PDF:", type="pdf", key="upload")
    
    if uploaded:
        try:
            with pdfplumber.open(uploaded) as pdf:
                texto = ""
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        texto += t + "\n"
                
                if not texto.strip():
                    st.error("❌ PDF vacío o escaneado")
                    st.stop()
                
                nums = re.findall(r"(?<!\$)\b(\d{1,3}(?:[\.,]\d{1,2})?)\b", texto)
                candidatos = sorted(list(set([float(n.replace(',','.')) for n in nums if 0.5 <= float(n.replace(',','.')) <= 100])), reverse=True)
        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.stop()
        
        if candidatos:
            st.success(f"✅ Encontré {len(candidatos)} valores")
            seleccion = st.multiselect("Selecciona las horas:", candidatos[:10], format_func=lambda x: f"{x} horas")
            
            if seleccion:
                total = sum(seleccion)
                st.write(f"**Total: {total} horas**")
                
                dias_sumar = 7 if total >= 35 else math.ceil(total/7.6)
                st.info(f"✅ Se sumarán **{dias_sumar} días**")
                
                if st.button("✅ Confirmar y Guardar", type="primary", key="confirm"):
                    profile["days"] += dias_sumar
                    profile["history"].append(f"{datetime.now().strftime('%d/%m/%Y %H:%M')} - +{dias_sumar} días ({total}h)")
                    st.success(f"🎉 ¡Sumados {dias_sumar} días!")
                    st.rerun()
        else:
            st.error("❌ No encontré horas válidas en el PDF")
    
    st.divider()
    
    # --- ENTRADA MANUAL ---
    st.subheader("✍️ O agregar manualmente")
    
    horas = st.number_input("Horas trabajadas:", 0.0, 100.0, 0.0, 0.5, key="manual")
    
    if st.button("➕ Agregar Días", key="manual_btn") and horas > 0:
        dias_manual = 7 if horas >= 35 else math.ceil(horas/7.6)
        profile["days"] += dias_manual
        profile["history"].append(f"{datetime.now().strftime('%d/%m/%Y %H:%M')} - +{dias_manual} días ({horas}h) [Manual]")
        st.success(f"✅ Agregados {dias_manual} días")
        st.rerun()
    
    st.divider()
    
    # --- HISTORIAL ---
    st.subheader("📋 Historial")
    
    if profile["history"]:
        for h in reversed(profile["history"]):
            st.text(h)
    else:
        st.info("Sin registros aún")
    
    st.divider()
    
    # --- RESETEAR ---
    if st.button("🗑️ Resetear este perfil", key="reset"):
        if st.checkbox("⚠️ ¿Estás seguro?", key="confirm_reset"):
            profile["days"] = 0
            profile["history"] = []
            st.warning("Perfil reseteado")
            st.rerun()

else:
    st.warning("👆 Crea tu primer perfil arriba para comenzar")

st.divider()
st.caption("ℹ️ Calculadora orientativa. Verifica con tu agente de migración.")
