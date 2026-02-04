import streamlit as st
import pdfplumber
import re
import json
import math
from datetime import datetime

st.set_page_config(page_title="Visa 462 Tracker", page_icon="🇦🇺", layout="centered")

# --- FUNCIONES DE PERSISTENCIA ---
def init_session():
    if 'profiles' not in st.session_state:
        st.session_state.profiles = {}
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None

init_session()

# --- INTERFAZ PRINCIPAL ---
st.title("🇦🇺 Visa 462 Days Tracker")
st.markdown("Calcula tus días de **Specified Work** para tu segunda Working Holiday Visa")

# --- GESTIÓN DE PERFILES ---
with st.sidebar:
    st.header("👤 Tu Perfil")
    
    # Crear nuevo perfil
    with st.expander("➕ Crear perfil nuevo"):
        nuevo_nombre = st.text_input("Nombre del perfil:", key="nuevo")
        if st.button("Crear", type="primary") and nuevo_nombre:
            if nuevo_nombre not in st.session_state.profiles:
                st.session_state.profiles[nuevo_nombre] = {
                    "days": 0,
                    "history": [],
                    "created": datetime.now().strftime("%d/%m/%Y")
                }
                st.session_state.current_user = nuevo_nombre
                st.success(f"✅ Perfil '{nuevo_nombre}' creado")
                st.rerun()
            else:
                st.warning("⚠️ Ese nombre ya existe")
    
    # Seleccionar perfil existente
    if st.session_state.profiles:
        perfiles_list = list(st.session_state.profiles.keys())
        perfil_actual = st.selectbox(
            "Selecciona tu perfil:",
            perfiles_list,
            index=perfiles_list.index(st.session_state.current_user) if st.session_state.current_user in perfiles_list else 0
        )
        st.session_state.current_user = perfil_actual
    else:
        st.info("👆 Crea tu primer perfil arriba")
        st.stop()
    
    st.divider()
    
    # Opciones del perfil
    if st.button("🗑️ Borrar este perfil"):
        del st.session_state.profiles[st.session_state.current_user]
        st.session_state.current_user = None
        st.rerun()

# --- DASHBOARD DEL USUARIO ---
user = st.session_state.current_user
profile = st.session_state.profiles[user]

st.subheader(f"Hola, {user}! 👋")

# Métricas principales
col1, col2, col3 = st.columns(3)

dias_actuales = profile["days"]
faltantes = max(0, 179 - dias_actuales)
porcentaje = min(100, round((dias_actuales / 179) * 100))

with col1:
    st.metric("📅 Días trabajados", dias_actuales)
with col2:
    st.metric("⏳ Días restantes", faltantes)
with col3:
    st.metric("📊 Progreso", f"{porcentaje}%")

# Barra de progreso
st.progress(min(dias_actuales / 179, 1.0))

if dias_actuales >= 179:
    st.balloons()
    st.success("🎉 **¡FELICITACIONES!** Ya cumpliste los 179 días. Puedes aplicar a tu segunda visa.")
elif dias_actuales >= 150:
    st.info(f"💪 ¡Casi ahí! Solo te faltan {faltantes} días")

st.divider()

# --- SUBIR PAYSLIP ---
st.subheader("📄 Agregar nuevo payslip")

uploaded_file = st.file_uploader(
    "Sube tu payslip en PDF",
    type="pdf",
    help="El PDF debe ser digital, no una foto escaneada"
)

if uploaded_file:
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            texto_completo = ""
            
            for page in pdf.pages:
                texto = page.extract_text()
                if texto:
                    texto_completo += texto + "\n"
            
            if not texto_completo.strip():
                st.error("❌ El PDF parece estar vacío o es una imagen escaneada")
                st.info("💡 Asegúrate de que sea un PDF digital donde puedas seleccionar el texto")
                st.stop()
            
            # Extraer números candidatos (horas)
            numeros_encontrados = re.findall(r"(?<!\$)\b(\d{1,3}(?:[\.,]\d{1,2})?)\b", texto_completo)
            
            # Filtrar y convertir
            candidatos = []
            for num in numeros_encontrados:
                try:
                    valor = float(num.replace(',', '.'))
                    if 0.5 <= valor <= 100:  # Rango razonable de horas
                        candidatos.append(valor)
                except:
                    continue
            
            # Eliminar duplicados y ordenar
            candidatos = sorted(list(set(candidatos)), reverse=True)
    
    except Exception as e:
        st.error(f"❌ Error al leer el PDF: {str(e)}")
        st.info("Intenta con otro PDF o contacta soporte")
        st.stop()
    
    if candidatos:
        st.success(f"✅ Encontré {len(candidatos)} valores posibles")
        
        # Mostrar solo top 10 para no saturar
        opciones_mostrar = candidatos[:10]
        
        st.info("👇 Selecciona las horas trabajadas (Normal + Overtime + otros si aplica)")
        
        horas_seleccionadas = st.multiselect(
            "Valores encontrados en el PDF:",
            opciones_mostrar,
            format_func=lambda x: f"{x} horas",
            help="Puedes seleccionar múltiples valores si tienes horas normales y overtime"
        )
        
        if horas_seleccionadas:
            total_horas = sum(horas_seleccionadas)
            
            st.write(f"### Total seleccionado: **{total_horas} horas**")
            
            # Validación
            if total_horas > 100:
                st.warning("⚠️ Más de 100 horas parece incorrecto. Verifica los valores seleccionados.")
            
            # Calcular días según reglas oficiales
            if total_horas >= 35:
                dias_a_sumar = 7
                st.info("🟢 **Semana completa:** Como trabajaste ≥35 horas, sumas **7 días**")
            else:
                dias_a_sumar = math.ceil(total_horas / 7.6)
                st.info(f"🟡 **Tiempo parcial:** {total_horas}h ÷ 7.6 = **{dias_a_sumar} días**")
            
            # Vista previa
            nuevo_total = dias_actuales + dias_a_sumar
            st.write(f"Días actuales: **{dias_actuales}** → Nuevo total: **{nuevo_total}** / 179")
            
            # Botón de confirmación
            if st.button("✅ Confirmar y guardar", type="primary", use_container_width=True):
                # Actualizar perfil
                profile["days"] += dias_a_sumar
                
                # Agregar al historial
                timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
                profile["history"].append({
                    "fecha": timestamp,
                    "dias": dias_a_sumar,
                    "horas": total_horas,
                    "archivo": uploaded_file.name
                })
                
                st.success(f"🎉 ¡Perfecto! Se agregaron **{dias_a_sumar} días** a tu contador")
                st.balloons()
                st.rerun()
    
    else:
        st.error("❌ No encontré valores de horas en el PDF")
        st.info("""
        **Posibles razones:**
        - Es un PDF escaneado (foto)
        - Las horas están en un formato no estándar
        - El PDF está protegido
        
        **Solución:** Intenta agregar las horas manualmente abajo
        """)

# --- ENTRADA MANUAL (FALLBACK) ---
st.divider()

with st.expander("✍️ O agregar horas manualmente"):
    st.write("Si no pudiste subir el PDF, ingresa las horas aquí:")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        horas_manual = st.number_input(
            "Horas trabajadas:",
            min_value=0.0,
            max_value=100.0,
            step=0.5,
            value=0.0
        )
    
    with col_b:
        nota_manual = st.text_input("Nota (opcional):", placeholder="Ej: Semana del 1-7 Feb")
    
    if st.button("➕ Agregar días", disabled=(horas_manual == 0)) and horas_manual > 0:
        if horas_manual >= 35:
            dias_manual = 7
        else:
            dias_manual = math.ceil(horas_manual / 7.6)
        
        profile["days"] += dias_manual
        
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        profile["history"].append({
            "fecha": timestamp,
            "dias": dias_manual,
            "horas": horas_manual,
            "archivo": f"Manual - {nota_manual}" if nota_manual else "Manual"
        })
        
        st.success(f"✅ Agregados {dias_manual} días")
        st.rerun()

# --- HISTORIAL ---
st.divider()
st.subheader("📋 Historial de registros")

if profile["history"]:
    # Mostrar en tabla invertida (más reciente primero)
    for i, registro in enumerate(reversed(profile["history"])):
        with st.expander(f"📄 {registro['fecha']} - {registro['dias']} días ({registro['horas']}h)"):
            st.write(f"**Archivo:** {registro.get('archivo', 'N/A')}")
            st.write(f"**Horas:** {registro['horas']}")
            st.write(f"**Días sumados:** {registro['dias']}")
            
            # Botón para eliminar registro
            if st.button("🗑️ Eliminar este registro", key=f"del_{i}"):
                # Restar días
                profile["days"] -= registro["dias"]
                # Remover del historial
                profile["history"].remove(registro)
                st.rerun()
else:
    st.info("Aún no hay registros. ¡Sube tu primer payslip arriba!")

# --- EXPORTAR DATOS ---
st.divider()

col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    if st.button("📥 Descargar resumen", use_container_width=True):
        resumen = f"""
VISA 462 - RESUMEN DE DÍAS TRABAJADOS
=====================================

Perfil: {user}
Fecha de creación: {profile['created']}
Fecha de reporte: {datetime.now().strftime("%d/%m/%Y %H:%M")}

PROGRESO:
---------
Días trabajados: {dias_actuales} / 179
Días restantes: {faltantes}
Porcentaje completado: {porcentaje}%

HISTORIAL:
----------
"""
        for reg in profile["history"]:
            resumen += f"\n[{reg['fecha']}] +{reg['dias']} días ({reg['horas']}h) - {reg.get('archivo', 'N/A')}"
        
        st.download_button(
            "💾 Descargar TXT",
            resumen,
            f"visa462_{user}_{datetime.now().strftime('%Y%m%d')}.txt",
            use_container_width=True
        )

with col_exp2:
    if st.button("🔄 Resetear contador", use_container_width=True):
        if st.checkbox("⚠️ ¿Estás seguro?", key="confirm_reset"):
            profile["days"] = 0
            profile["history"].append({
                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "dias": 0,
                "horas": 0,
                "archivo": "RESET COMPLETO"
            })
            st.warning("Contador reseteado a 0")
            st.rerun()

# --- FOOTER ---
st.divider()
st.caption("""
ℹ️ **Información importante:**
- Este tracker es orientativo. Verifica siempre con tu agente de migración.
- Las reglas oficiales: ≥35h/semana = 7 días | <35h = dividir por 7.6h
- Más info: [immi.homeaffairs.gov.au](https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/work-holiday-462)
""")

st.caption("Hecho con ❤️ para Working Holiday Makers")
