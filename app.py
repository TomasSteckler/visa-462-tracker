import streamlit as st
import pdfplumber
import re
import math
from datetime import datetime
import time
from supabase import create_client, Client

st.set_page_config(page_title="Visa 462 Tracker", page_icon="🇦🇺", initial_sidebar_state="expanded")

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# --- FUNCIONES DE BASE DE DATOS ---
def cargar_perfil(username):
    """Cargar perfil desde Supabase"""
    try:
        response = supabase.table("profiles").select("*").eq("username", username).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        st.error(f"Error al cargar perfil: {e}")
        return None

def guardar_perfil(username, days, objetivo, tipo, history):
    """Guardar o actualizar perfil en Supabase"""
    try:
        # Verificar si existe
        existing = supabase.table("profiles").select("id").eq("username", username).execute()
        
        data = {
            "username": username,
            "days": days,
            "objetivo": objetivo,
            "tipo": tipo,
            "history": history
        }
        
        if existing.data:
            # Actualizar
            response = supabase.table("profiles").update(data).eq("username", username).execute()
        else:
            # Crear nuevo
            response = supabase.table("profiles").insert(data).execute()
        
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

def listar_perfiles():
    """Obtener lista de todos los perfiles"""
    try:
        response = supabase.table("profiles").select("username").execute()
        return [p["username"] for p in response.data] if response.data else []
    except Exception as e:
        st.error(f"Error al listar perfiles: {e}")
        return []

def eliminar_perfil(username):
    """Eliminar perfil de Supabase"""
    try:
        supabase.table("profiles").delete().eq("username", username).execute()
        return True
    except Exception as e:
        st.error(f"Error al eliminar: {e}")
        return False

# --- INICIALIZAR SESIÓN ---
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'profile_data' not in st.session_state:
    st.session_state.profile_data = None

st.title("🇦🇺 Visa 462 Days Tracker")
st.markdown("Calcula tus días de **Specified Work** - *Ahora con guardado permanente* ☁️")

# --- GESTIÓN DE PERFILES ---
st.header("👤 Tu Perfil")

# Listar perfiles existentes
perfiles_existentes = listar_perfiles()

if not perfiles_existentes:
    st.info("👇 Crea tu primer perfil")

# Formulario de creación
with st.form("crear_perfil", clear_on_submit=True):
    nuevo = st.text_input("Nombre del perfil:", placeholder="Ej: Juan")
    
    objetivo = st.radio(
        "¿Para qué visa estás trabajando?",
        options=["Primera visa (88 días)", "Segunda visa (179 días)"],
        help="La primera WHV requiere 88 días para renovar. La segunda requiere 179 días para una tercera visa."
    )
    
    submit = st.form_submit_button("➕ Crear Perfil", type="primary", use_container_width=True)
    
    if submit and nuevo:
        if nuevo not in perfiles_existentes:
            dias_objetivo = 88 if "88" in objetivo else 179
            tipo = "Primera WHV" if dias_objetivo == 88 else "Segunda WHV"
            
            if guardar_perfil(nuevo, 0, dias_objetivo, tipo, []):
                st.session_state.current_user = nuevo
                st.toast(f'✅ Perfil creado: {dias_objetivo} días', icon='✅')
                time.sleep(0.5)
                st.rerun()
        else:
            st.warning("⚠️ Ese perfil ya existe")

if perfiles_existentes:
    user = st.selectbox("Selecciona tu perfil:", perfiles_existentes, key="select_user")
    
    # Cargar datos del perfil seleccionado
    if user != st.session_state.current_user:
        st.session_state.current_user = user
        st.session_state.profile_data = cargar_perfil(user)
    
    if not st.session_state.profile_data:
        st.session_state.profile_data = cargar_perfil(user)
    
    profile = st.session_state.profile_data
    
    if profile:
        st.divider()
        
        # --- MÉTRICAS ---
        st.subheader(f"Hola, {user}! 👋")
        st.caption(f"🎯 Objetivo: {profile['tipo']} ({profile['objetivo']} días)")
        
        dias = profile["days"]
        objetivo = profile["objetivo"]
        faltantes = max(0, objetivo - dias)
        
        col1, col2 = st.columns(2)
        col1.metric("📅 Días trabajados", f"{dias} / {objetivo}")
        col2.metric("⏳ Faltan", faltantes)
        
        st.progress(min(dias/objetivo, 1.0))
        
        if dias >= objetivo:
            st.balloons()
            st.success(f"🎉 ¡Cumpliste los {objetivo} días!")
        
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
                    
                    candidatos = []
                    
                    # DETECTOR MULTI-FORMATO
                    patron_hays = r'Normal Time W/E.*?(\d{1,3}(?:\.\d{1,2})?)\s*\$'
                    matches_hays = re.findall(patron_hays, texto)
                    
                    if matches_hays:
                        for hora in matches_hays:
                            candidatos.append(float(hora))
                        
                        total_hays = sum([float(h) for h in matches_hays])
                        st.success(f"✅ **Hays detectado:** {len(matches_hays)} línea(s) de trabajo")
                        
                        for i, h in enumerate(matches_hays, 1):
                            st.info(f"   Línea {i}: {h} horas")
                        
                        if len(matches_hays) > 1:
                            st.write(f"**Total combinado:** {total_hays} horas")
                    
                    patron_statum = r'Base Hourly.*?(\d{1,3}(?:\.\d{1,2})?)\s*\$'
                    match_statum = re.search(patron_statum, texto)
                    
                    if match_statum:
                        horas_statum = float(match_statum.group(1))
                        candidatos.append(horas_statum)
                        st.success(f"✅ **Statum Services detectado:** {horas_statum} horas")
                    
                    if candidatos:
                        st.write("---")
                        candidatos = sorted(list(set(candidatos)), reverse=True)
                        
                        seleccion = st.multiselect(
                            "Confirma las horas detectadas:",
                            candidatos,
                            default=candidatos,
                            format_func=lambda x: f"{x} horas"
                        )
                        
                    else:
                        st.warning("⚠️ No reconocí el formato automáticamente")
                        
                        with st.expander("🔍 Ver texto extraído (para debug)"):
                            st.text(texto[:1500])
                        
                        st.info("👇 Selecciona las horas manualmente:")
                        
                        nums = re.findall(r"(?<!\$)\b(\d{1,3}(?:[\.,]\d{1,2})?)\b", texto)
                        todos_candidatos = sorted(
                            list(set([float(n.replace(',','.')) for n in nums if 0.5 <= float(n.replace(',','.')) <= 200])), 
                            reverse=True
                        )
                        
                        if todos_candidatos:
                            seleccion = st.multiselect(
                                "Valores encontrados:",
                                todos_candidatos[:15],
                                format_func=lambda x: f"{x} horas"
                            )
                        else:
                            st.error("❌ No encontré números válidos")
                            seleccion = []
            
            except Exception as e:
                st.error(f"❌ Error al leer PDF: {e}")
                st.stop()
            
            # CONFIRMACIÓN Y CÁLCULO
            if seleccion:
                total = sum(seleccion)
                
                st.write("---")
                st.write(f"### 📊 Total seleccionado: **{total} horas**")
                
                if total > 100:
                    st.warning("⚠️ Más de 100 horas parece incorrecto")
                elif total < 1:
                    st.error("❌ El valor parece demasiado bajo")
                
                if total >= 35:
                    dias_sumar = 7
                    st.success(f"✅ **Semana completa:** Como trabajaste ≥35h, sumas **7 días**")
                else:
                    dias_sumar = math.ceil(total / 7.6)
                    st.info(f"🔢 **Cálculo:** {total}h ÷ 7.6 = **{dias_sumar} días**")
                
                nuevo_total = dias + dias_sumar
                progreso_nuevo = min(nuevo_total / objetivo, 1.0) * 100
                
                col_a, col_b = st.columns(2)
                col_a.metric("Días actuales", dias)
                col_b.metric("Nuevo total", f"{nuevo_total} / {objetivo}", delta=f"+{dias_sumar}")
                
                st.progress(progreso_nuevo / 100)
                
                if st.button("✅ Confirmar y Guardar", type="primary", key="confirm", use_container_width=True):
                    with st.spinner('⏳ Guardando en la nube...'):
                        profile["days"] += dias_sumar
                        
                        nombre_archivo = uploaded.name
                        nuevo_registro = f"{datetime.now().strftime('%d/%m/%Y %H:%M')} - +{dias_sumar} días ({total}h) [{nombre_archivo}]"
                        profile["history"].append(nuevo_registro)
                        
                        if guardar_perfil(user, profile["days"], profile["objetivo"], profile["tipo"], profile["history"]):
                            st.session_state.profile_data = profile
                            time.sleep(0.5)
                            
                            st.toast('✅ ¡Guardado en la nube!', icon='✅')
                            time.sleep(0.2)
                            st.toast(f'📊 Nuevo total: {nuevo_total}/{objetivo} días', icon='📊')
                            
                            nuevo_progreso = min(100, round((nuevo_total / objetivo) * 100))
                            
                            st.success(f"""
### 🎉 ¡Registro guardado exitosamente!

✅ **{dias_sumar} días** agregados a tu contador

📊 **Progreso:** {nuevo_total} / {objetivo} días ({nuevo_progreso}%)

🎯 Te faltan **{objetivo - nuevo_total}** días para completar

☁️ **Guardado permanentemente en la nube**
                            """)
                            
                            st.balloons()
                            time.sleep(2.5)
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar. Intenta de nuevo.")
        
        st.divider()
        
        # --- ENTRADA MANUAL ---
        st.subheader("✍️ O agregar manualmente")
        
        horas = st.number_input("Horas trabajadas:", 0.0, 200.0, 0.0, 0.5, key="manual")
        
        if st.button("➕ Agregar Días", key="manual_btn") and horas > 0:
            with st.spinner('Guardando en la nube...'):
                dias_manual = 7 if horas >= 35 else math.ceil(horas/7.6)
                profile["days"] += dias_manual
                
                nuevo_registro = f"{datetime.now().strftime('%d/%m/%Y %H:%M')} - +{dias_manual} días ({horas}h) [Manual]"
                profile["history"].append(nuevo_registro)
                
                if guardar_perfil(user, profile["days"], profile["objetivo"], profile["tipo"], profile["history"]):
                    st.session_state.profile_data = profile
                    time.sleep(0.5)
                    
                    st.toast(f'✅ {dias_manual} días agregados!', icon='✅')
                    st.success(f"✅ Agregados {dias_manual} días. Nuevo total: {profile['days']}/{objetivo}")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("❌ Error al guardar")
        
        st.divider()
        
        # --- HISTORIAL ---
        st.subheader("📋 Historial")
        
        if profile["history"]:
            for i, h in enumerate(reversed(profile["history"])):
                with st.expander(f"📄 Registro #{len(profile['history']) - i}"):
                    st.text(h)
                    
                    if st.button("🗑️ Eliminar este registro", key=f"del_{i}"):
                        match = re.search(r'\+(\d+) días', h)
                        if match:
                            dias_a_restar = int(match.group(1))
                            profile["days"] -= dias_a_restar
                        
                        profile["history"].remove(h)
                        
                        if guardar_perfil(user, profile["days"], profile["objetivo"], profile["tipo"], profile["history"]):
                            st.session_state.profile_data = profile
                            st.toast('🗑️ Registro eliminado', icon='🗑️')
                            time.sleep(0.5)
                            st.rerun()
        else:
            st.info("Sin registros aún. ¡Sube tu primer payslip!")
        
        st.divider()
        
        # --- OPCIONES AVANZADAS ---
        with st.expander("⚙️ Opciones avanzadas"):
            st.write("**Cambiar objetivo de días:**")
            nuevo_objetivo = st.radio(
                "Selecciona nuevo objetivo:",
                options=[88, 179],
                index=0 if profile["objetivo"] == 88 else 1,
                format_func=lambda x: f"{x} días ({'Primera WHV' if x == 88 else 'Segunda WHV'})",
                key="cambiar_objetivo"
            )
            
            if st.button("🔄 Actualizar objetivo", key="update_objetivo"):
                profile["objetivo"] = nuevo_objetivo
                profile["tipo"] = "Primera WHV" if nuevo_objetivo == 88 else "Segunda WHV"
                
                if guardar_perfil(user, profile["days"], profile["objetivo"], profile["tipo"], profile["history"]):
                    st.session_state.profile_data = profile
                    st.toast(f'✅ Objetivo actualizado a {nuevo_objetivo} días', icon='✅')
                    time.sleep(1)
                    st.rerun()
            
            st.divider()
            
            col_opt1, col_opt2 = st.columns(2)
            
            with col_opt1:
                if st.button("📥 Descargar resumen", use_container_width=True):
                    resumen = f"""VISA 462 - RESUMEN DE DÍAS TRABAJADOS
{'=' * 50}

Perfil: {user}
Objetivo: {profile['tipo']} ({objetivo} días)
Fecha de reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')}

PROGRESO:
---------
Días trabajados: {dias} / {objetivo}
Días restantes: {faltantes}
Porcentaje completado: {min(100, round((dias / objetivo) * 100))}%

HISTORIAL DE REGISTROS:
-----------------------
"""
                    for h in profile["history"]:
                        resumen += f"\n{h}"
                    
                    st.download_button(
                        "💾 Descargar TXT",
                        resumen,
                        f"visa462_{user}_{datetime.now().strftime('%Y%m%d')}.txt",
                        use_container_width=True
                    )
            
            with col_opt2:
                if st.button("🗑️ Borrar perfil", use_container_width=True):
                    if st.checkbox("⚠️ ¿Seguro? Se borrará todo", key="confirm_delete"):
                        if eliminar_perfil(user):
                            st.session_state.current_user = None
                            st.session_state.profile_data = None
                            st.toast('🗑️ Perfil eliminado', icon='🗑️')
                            time.sleep(1)
                            st.rerun()

else:
    st.warning("👆 Crea tu primer perfil arriba para comenzar")

st.divider()
st.caption("ℹ️ Calculadora orientativa. Verifica con tu agente de migración.")
st.caption("☁️ Tus datos se guardan permanentemente en la nube - Hecho con ❤️")
