import streamlit as st
import pdfplumber
import re
import math
from datetime import datetime
import time
from supabase import create_client, Client
import hashlib
import uuid

st.set_page_config(page_title="Visa 462 Tracker", page_icon="🇦🇺", initial_sidebar_state="expanded")

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# --- GENERAR ID DE DISPOSITIVO ---
def get_device_id():
    """Generar o recuperar ID único de dispositivo"""
    if 'device_id' not in st.session_state:
        # Intentar recuperar de query params (simulando localStorage)
        params = st.query_params
        if 'device_id' in params:
            st.session_state.device_id = params['device_id']
        else:
            # Generar nuevo ID
            st.session_state.device_id = str(uuid.uuid4())
            # Guardar en URL para persistencia
            st.query_params['device_id'] = st.session_state.device_id
    return st.session_state.device_id

# --- FUNCIONES DE BASE DE DATOS ---
def hash_pin(pin):
    """Hash del PIN para seguridad"""
    return hashlib.sha256(pin.encode()).hexdigest()

def cargar_perfil(username, pin=None):
    """Cargar perfil desde Supabase con verificación de PIN"""
    try:
        query = supabase.table("profiles").select("*").eq("username", username)
        response = query.execute()
        
        if response.data:
            profile = response.data[0]
            # Si tiene PIN, verificar
            if profile.get('pin'):
                if pin and hash_pin(pin) == profile['pin']:
                    return profile
                elif not pin:
                    return None  # Requiere PIN
            else:
                return profile  # Perfil sin PIN (retrocompatibilidad)
        return None
    except Exception as e:
        st.error(f"Error al cargar perfil: {e}")
        return None

def guardar_perfil(username, days, objetivo, tipo, history, pin=None, device_id=None):
    """Guardar o actualizar perfil en Supabase"""
    try:
        existing = supabase.table("profiles").select("id").eq("username", username).execute()
        
        data = {
            "username": username,
            "days": days,
            "objetivo": objetivo,
            "tipo": tipo,
            "history": history
        }
        
        # Agregar PIN si se proporciona
        if pin:
            data["pin"] = hash_pin(pin)
        
        # Agregar device_id para recordar sesión
        if device_id:
            data["device_id"] = device_id
        
        if existing.data:
            response = supabase.table("profiles").update(data).eq("username", username).execute()
        else:
            response = supabase.table("profiles").insert(data).execute()
        
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

def listar_perfiles_dispositivo():
    """Obtener perfiles de este dispositivo"""
    try:
        device_id = get_device_id()
        response = supabase.table("profiles").select("username").eq("device_id", device_id).execute()
        return [p["username"] for p in response.data] if response.data else []
    except Exception as e:
        st.error(f"Error al listar perfiles: {e}")
        return []

def verificar_pin(username, pin):
    """Verificar si el PIN es correcto"""
    profile = cargar_perfil(username, pin)
    return profile is not None

# --- INICIALIZAR SESIÓN ---
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'profile_data' not in st.session_state:
    st.session_state.profile_data = None
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

device_id = get_device_id()

st.title("🇦🇺 Visa 462 Days Tracker")
st.markdown("Calcula tus días de **Specified Work** - *Guardado seguro en la nube* 🔐☁️")

# --- GESTIÓN DE PERFILES ---
st.header("👤 Tu Perfil")

# Perfiles de este dispositivo
mis_perfiles = listar_perfiles_dispositivo()

# --- ESTADO: SIN PERFIL O SIN AUTENTICAR ---
if not st.session_state.authenticated:
    
    if mis_perfiles:
        st.info("👋 Bienvenido de vuelta! Selecciona tu perfil:")
        
        perfil_seleccionado = st.selectbox("Tus perfiles:", mis_perfiles, key="login_select")
        pin_login = st.text_input("PIN:", type="password", max_chars=6, key="pin_login")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔓 Acceder", type="primary", use_container_width=True):
                if len(pin_login) >= 4:
                    profile = cargar_perfil(perfil_seleccionado, pin_login)
                    if profile:
                        st.session_state.current_user = perfil_seleccionado
                        st.session_state.profile_data = profile
                        st.session_state.authenticated = True
                        st.toast('✅ Acceso concedido!', icon='✅')
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ PIN incorrecto")
                else:
                    st.warning("⚠️ El PIN debe tener al menos 4 dígitos")
        
        with col2:
            if st.button("➕ Crear otro perfil", use_container_width=True):
                st.session_state.show_create_form = True
                st.rerun()
    
    # Formulario de creación
    if not mis_perfiles or st.session_state.get('show_create_form', False):
        st.divider()
        st.subheader("Crear nuevo perfil")
        
        with st.form("crear_perfil", clear_on_submit=True):
            nuevo = st.text_input("Nombre del perfil:", placeholder="Ej: Tomi")
            
            pin_nuevo = st.text_input("Crea un PIN (4-6 dígitos):", type="password", max_chars=6, 
                                     help="Este PIN protegerá tu perfil. ¡No lo olvides!")
            pin_confirmar = st.text_input("Confirma el PIN:", type="password", max_chars=6)
            
            objetivo = st.radio(
                "¿Para qué visa estás trabajando?",
                options=["Primera visa (88 días)", "Segunda visa (179 días)"],
                help="La primera WHV requiere 88 días. La segunda requiere 179 días."
            )
            
            submit = st.form_submit_button("➕ Crear Perfil", type="primary", use_container_width=True)
            
            if submit and nuevo:
                # Validaciones
                if len(pin_nuevo) < 4:
                    st.error("❌ El PIN debe tener al menos 4 dígitos")
                elif pin_nuevo != pin_confirmar:
                    st.error("❌ Los PINs no coinciden")
                elif nuevo in mis_perfiles:
                    st.error("⚠️ Ya tienes un perfil con ese nombre")
                else:
                    # Crear perfil
                    dias_objetivo = 88 if "88" in objetivo else 179
                    tipo = "Primera WHV" if dias_objetivo == 88 else "Segunda WHV"
                    
                    if guardar_perfil(nuevo, 0, dias_objetivo, tipo, [], pin_nuevo, device_id):
                        st.session_state.current_user = nuevo
                        st.session_state.profile_data = cargar_perfil(nuevo, pin_nuevo)
                        st.session_state.authenticated = True
                        st.session_state.show_create_form = False
                        st.toast(f'✅ Perfil creado: {dias_objetivo} días', icon='✅')
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Error al crear perfil")

# --- ESTADO: AUTENTICADO ---
else:
    user = st.session_state.current_user
    profile = st.session_state.profile_data
    
    if profile:
        # Botón de cerrar sesión
        col_header1, col_header2 = st.columns([3, 1])
        with col_header1:
            st.subheader(f"Hola, {user}! 👋")
        with col_header2:
            if st.button("🚪 Salir", key="logout"):
                st.session_state.authenticated = False
                st.session_state.current_user = None
                st.session_state.profile_data = None
                st.rerun()
        
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
                    
                    # DETECTORES
                    patron_hays = r'Normal Time W/E.*?(\d{1,3}(?:\.\d{1,2})?)\s*\$'
                    matches_hays = re.findall(patron_hays, texto)
                    
                    if matches_hays:
                        for hora in matches_hays:
                            candidatos.append(float(hora))
                        
                        total_hays = sum([float(h) for h in matches_hays])
                        st.success(f"✅ **Hays detectado:** {len(matches_hays)} línea(s)")
                        
                        for i, h in enumerate(matches_hays, 1):
                            st.info(f"   Línea {i}: {h} horas")
                        
                        if len(matches_hays) > 1:
                            st.write(f"**Total combinado:** {total_hays} horas")
                    
                    patron_statum = r'Base Hourly.*?(\d{1,3}(?:\.\d{1,2})?)\s*\$'
                    match_statum = re.search(patron_statum, texto)
                    
                    if match_statum:
                        horas_statum = float(match_statum.group(1))
                        candidatos.append(horas_statum)
                        st.success(f"✅ **Statum detectado:** {horas_statum} horas")
                    
                    if candidatos:
                        st.write("---")
                        candidatos = sorted(list(set(candidatos)), reverse=True)
                        
                        seleccion = st.multiselect(
                            "Confirma las horas:",
                            candidatos,
                            default=candidatos,
                            format_func=lambda x: f"{x} horas"
                        )
                        
                    else:
                        st.warning("⚠️ No reconocí el formato")
                        
                        with st.expander("🔍 Ver texto (debug)"):
                            st.text(texto[:1500])
                        
                        nums = re.findall(r"(?<!\$)\b(\d{1,3}(?:[\.,]\d{1,2})?)\b", texto)
                        todos = sorted(
                            list(set([float(n.replace(',','.')) for n in nums if 0.5 <= float(n.replace(',','.')) <= 200])), 
                            reverse=True
                        )
                        
                        if todos:
                            seleccion = st.multiselect("Valores:", todos[:15], format_func=lambda x: f"{x} horas")
                        else:
                            st.error("❌ No encontré números")
                            seleccion = []
            
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.stop()
            
            # CONFIRMACIÓN
            if seleccion:
                total = sum(seleccion)
                
                st.write("---")
                st.write(f"### 📊 Total: **{total} horas**")
                
                if total > 100:
                    st.warning("⚠️ Más de 100 horas")
                
                if total >= 35:
                    dias_sumar = 7
                    st.success(f"✅ Semana completa: **7 días**")
                else:
                    dias_sumar = math.ceil(total / 7.6)
                    st.info(f"🔢 {total}h ÷ 7.6 = **{dias_sumar} días**")
                
                nuevo_total = dias + dias_sumar
                
                col_a, col_b = st.columns(2)
                col_a.metric("Actual", dias)
                col_b.metric("Nuevo", f"{nuevo_total}/{objetivo}", delta=f"+{dias_sumar}")
                
                st.progress(min(nuevo_total/objetivo, 1.0))
                
                if st.button("✅ Confirmar y Guardar", type="primary", key="confirm", use_container_width=True):
                    with st.spinner('⏳ Guardando...'):
                        profile["days"] += dias_sumar
                        
                        registro = f"{datetime.now().strftime('%d/%m/%Y %H:%M')} - +{dias_sumar} días ({total}h) [{uploaded.name}]"
                        profile["history"].append(registro)
                        
                        if guardar_perfil(user, profile["days"], profile["objetivo"], profile["tipo"], profile["history"], device_id=device_id):
                            st.session_state.profile_data = profile
                            time.sleep(0.5)
                            
                            st.toast('✅ ¡Guardado!', icon='✅')
                            st.success(f"""
### 🎉 ¡Guardado exitosamente!

✅ **{dias_sumar} días** agregados

📊 **Progreso:** {nuevo_total}/{objetivo} días

☁️ **Guardado en la nube**
                            """)
                            
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar")
        
        st.divider()
        
        # --- ENTRADA MANUAL ---
        st.subheader("✍️ Agregar manualmente")
        
        horas = st.number_input("Horas:", 0.0, 200.0, 0.0, 0.5, key="manual")
        
        if st.button("➕ Agregar", key="manual_btn") and horas > 0:
            with st.spinner('Guardando...'):
                dias_manual = 7 if horas >= 35 else math.ceil(horas/7.6)
                profile["days"] += dias_manual
                
                registro = f"{datetime.now().strftime('%d/%m/%Y %H:%M')} - +{dias_manual} días ({horas}h) [Manual]"
                profile["history"].append(registro)
                
                if guardar_perfil(user, profile["days"], profile["objetivo"], profile["tipo"], profile["history"], device_id=device_id):
                    st.session_state.profile_data = profile
                    st.toast(f'✅ {dias_manual} días!', icon='✅')
                    st.success(f"✅ Nuevo total: {profile['days']}/{objetivo}")
                    time.sleep(1.5)
                    st.rerun()
        
        st.divider()
        
        # --- HISTORIAL ---
        st.subheader("📋 Historial")
        
        if profile["history"]:
            for i, h in enumerate(reversed(profile["history"])):
                with st.expander(f"📄 Registro #{len(profile['history']) - i}"):
                    st.text(h)
                    
                    if st.button("🗑️ Eliminar", key=f"del_{i}"):
                        match = re.search(r'\+(\d+) días', h)
                        if match:
                            profile["days"] -= int(match.group(1))
                        
                        profile["history"].remove(h)
                        
                        if guardar_perfil(user, profile["days"], profile["objetivo"], profile["tipo"], profile["history"], device_id=device_id):
                            st.session_state.profile_data = profile
                            st.toast('🗑️ Eliminado', icon='🗑️')
                            time.sleep(0.5)
                            st.rerun()
        else:
            st.info("Sin registros")
        
        st.divider()
        
        # --- OPCIONES ---
        with st.expander("⚙️ Opciones"):
            
            # Cambiar objetivo
            nuevo_obj = st.radio(
                "Cambiar objetivo:",
                [88, 179],
                index=0 if profile["objetivo"] == 88 else 1,
                format_func=lambda x: f"{x} días",
                key="obj"
            )
            
            if st.button("🔄 Actualizar", key="upd_obj"):
                profile["objetivo"] = nuevo_obj
                profile["tipo"] = "Primera WHV" if nuevo_obj == 88 else "Segunda WHV"
                
                if guardar_perfil(user, profile["days"], profile["objetivo"], profile["tipo"], profile["history"], device_id=device_id):
                    st.session_state.profile_data = profile
                    st.toast(f'✅ Objetivo: {nuevo_obj}', icon='✅')
                    time.sleep(1)
                    st.rerun()
            
            st.divider()
            
            # Descargar
            if st.button("📥 Descargar resumen"):
                resumen = f"""VISA 462 - RESUMEN
{'=' * 50}

Perfil: {user}
Objetivo: {profile['tipo']} ({objetivo} días)
Fecha: {datetime.now().strftime('%d/%m/%Y')}

PROGRESO:
---------
Días: {dias}/{objetivo}
Restantes: {faltantes}
Completado: {min(100, round((dias/objetivo)*100))}%

HISTORIAL:
----------
"""
                for h in profile["history"]:
                    resumen += f"\n{h}"
                
                st.download_button(
                    "💾 Descargar",
                    resumen,
                    f"visa462_{user}_{datetime.now().strftime('%Y%m%d')}.txt"
                )

st.divider()
st.caption("🔐 Tus datos están protegidos con PIN - ☁️ Guardado permanente")
st.caption("Hecho con ❤️ para Working Holiday Makers")
