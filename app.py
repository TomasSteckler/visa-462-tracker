import streamlit as st
import pdfplumber
import re
import math
from datetime import datetime
import time

st.set_page_config(page_title="Visa 462 Tracker", page_icon="🇦🇺", initial_sidebar_state="expanded")

if 'profiles' not in st.session_state:
    st.session_state.profiles = {}
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

st.title("🇦🇺 Visa 462 Days Tracker")
st.markdown("Calcula tus días de **Specified Work**")

# --- GESTIÓN DE PERFILES ---
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
                
                candidatos = []
                horas_detectadas = []
                
                # --- DETECTOR MULTI-FORMATO ---
                
                # FORMATO 1 y 2: Hays (CIVEO)
                # Patrón: "Normal Time W/E [fecha] [HORAS] $ [rate]"
                patron_hays = r'Normal Time W/E.*?(\d{1,3}(?:\.\d{1,2})?)\s*\$'
                matches_hays = re.findall(patron_hays, texto)
                
                if matches_hays:
                    for hora in matches_hays:
                        h = float(hora)
                        horas_detectadas.append(h)
                        candidatos.append(h)
                    
                    total_hays = sum([float(h) for h in matches_hays])
                    st.success(f"✅ **Hays detectado:** {len(matches_hays)} línea(s) de trabajo")
                    
                    for i, h in enumerate(matches_hays, 1):
                        st.info(f"   Línea {i}: {h} horas")
                    
                    if len(matches_hays) > 1:
                        st.write(f"**Total combinado:** {total_hays} horas")
                
                # FORMATO 3: Statum Services
                # Patrón: "Base Hourly" seguido de HOURS en columna
                patron_statum = r'Base Hourly.*?(\d{1,3}(?:\.\d{1,2})?)\s*\$'
                match_statum = re.search(patron_statum, texto)
                
                if match_statum:
                    horas_statum = float(match_statum.group(1))
                    horas_detectadas.append(horas_statum)
                    candidatos.append(horas_statum)
                    st.success(f"✅ **Statum Services detectado:** {horas_statum} horas")
                
                # FORMATO GENÉRICO: Buscar "HOURS" en columnas
                patron_hours_column = r'(?:HOURS|Hours)\s+(?:CALC|RATE).*?\n.*?(\d{1,3}(?:\.\d{1,2})?)\s+\$'
                match_hours_col = re.search(patron_hours_column, texto, re.IGNORECASE)
                
                if match_hours_col and not match_statum:
                    horas_col = float(match_hours_col.group(1))
                    horas_detectadas.append(horas_col)
                    candidatos.append(horas_col)
                    st.success(f"✅ **Formato tabla detectado:** {horas_col} horas")
                
                # Si se detectó algo automáticamente
                if candidatos:
                    st.write("---")
                    
                    # Eliminar duplicados
                    candidatos = sorted(list(set(candidatos)), reverse=True)
                    
                    seleccion = st.multiselect(
                        "Confirma las horas detectadas:",
                        candidatos,
                        default=candidatos,  # Auto-seleccionadas
                        format_func=lambda x: f"{x} horas"
                    )
                    
                else:
                    # FALLBACK: Modo manual
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
            with st.expander("Ver detalles del error"):
                st.code(str(e))
            st.stop()
        
        # --- CONFIRMACIÓN Y CÁLCULO ---
        if seleccion:
            total = sum(seleccion)
            
            st.write("---")
            st.write(f"### 📊 Total seleccionado: **{total} horas**")
            
            # Validaciones
            if total > 100:
                st.warning("⚠️ Más de 100 horas parece incorrecto")
            elif total < 1:
                st.error("❌ El valor parece demasiado bajo")
            
            # Cálculo de días
            if total >= 35:
                dias_sumar = 7
                st.success(f"✅ **Semana completa:** Como trabajaste ≥35h, sumas **7 días**")
            else:
                dias_sumar = math.ceil(total / 7.6)
                st.info(f"🔢 **Cálculo:** {total}h ÷ 7.6 = **{dias_sumar} días**")
            
            # Vista previa
            nuevo_total = dias + dias_sumar
            progreso_nuevo = min(nuevo_total / 179, 1.0) * 100
            
            col_a, col_b = st.columns(2)
            col_a.metric("Días actuales", dias)
            col_b.metric("Nuevo total", f"{nuevo_total} / 179", delta=f"+{dias_sumar}")
            
            st.progress(progreso_nuevo / 100)
            
            # Botón de confirmación CON FEEDBACK MEJORADO
            if st.button("✅ Confirmar y Guardar", type="primary", key="confirm", use_container_width=True):
                # Spinner mientras guarda
                with st.spinner('⏳ Guardando tu registro...'):
                    time.sleep(0.5)
                    
                    profile["days"] += dias_sumar
                    
                    nombre_archivo = uploaded.name if uploaded else "Manual"
                    
                    profile["history"].append(
                        f"{datetime.now().strftime('%d/%m/%Y %H:%M')} - +{dias_sumar} días ({total}h) [{nombre_archivo}]"
                    )
                
                # Toast notifications
                st.toast('✅ ¡Registro guardado!', icon='✅')
                time.sleep(0.2)
                st.toast(f'📊 Nuevo total: {nuevo_total}/179 días', icon='📊')
                
                # Calcular progreso
                nuevo_progreso = min(100, round((nuevo_total / 179) * 100))
                
                # Mensaje grande
                st.success(f"""
### 🎉 ¡Registro guardado exitosamente!

✅ **{dias_sumar} días** agregados a tu contador

📊 **Progreso:** {nuevo_total} / 179 días ({nuevo_progreso}%)

🎯 Te faltan **{179 - nuevo_total}** días para completar
                """)
                
                st.balloons()
                time.sleep(2.5)
                st.rerun()
    
    st.divider()
    
    # --- ENTRADA MANUAL ---
    st.subheader("✍️ O agregar manualmente")
    
    horas = st.number_input("Horas trabajadas:", 0.0, 200.0, 0.0, 0.5, key="manual")
    
    if st.button("➕ Agregar Días", key="manual_btn") and horas > 0:
        with st.spinner('Guardando...'):
            dias_manual = 7 if horas >= 35 else math.ceil(horas/7.6)
            profile["days"] += dias_manual
            profile["history"].append(f"{datetime.now().strftime('%d/%m/%Y %H:%M')} - +{dias_manual} días ({horas}h) [Manual]")
            time.sleep(0.5)
        
        st.toast(f'✅ {dias_manual} días agregados!', icon='✅')
        st.success(f"✅ Agregados {dias_manual} días. Nuevo total: {profile['days']}/179")
        time.sleep(1.5)
        st.rerun()
    
    st.divider()
    
    # --- HISTORIAL ---
    st.subheader("📋 Historial")
    
    if profile["history"]:
        for i, h in enumerate(reversed(profile["history"])):
            with st.expander(f"📄 Registro #{len(profile['history']) - i}"):
                st.text(h)
                
                # Botón para eliminar
                if st.button("🗑️ Eliminar este registro", key=f"del_{i}"):
                    # Extraer días del registro para restarlos
                    match = re.search(r'\+(\d+) días', h)
                    if match:
                        dias_a_restar = int(match.group(1))
                        profile["days"] -= dias_a_restar
                    
                    profile["history"].remove(h)
                    st.toast('🗑️ Registro eliminado', icon='🗑️')
                    time.sleep(0.5)
                    st.rerun()
    else:
        st.info("Sin registros aún. ¡Sube tu primer payslip!")
    
    st.divider()
    
    # --- OPCIONES AVANZADAS ---
    with st.expander("⚙️ Opciones avanzadas"):
        
        col_opt1, col_opt2 = st.columns(2)
        
        with col_opt1:
            if st.button("📥 Descargar resumen", use_container_width=True):
                resumen = f"""VISA 462 - RESUMEN DE DÍAS TRABAJADOS
{'=' * 50}

Perfil: {user}
Fecha de reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')}

PROGRESO:
---------
Días trabajados: {dias} / 179
Días restantes: {faltantes}
Porcentaje completado: {min(100, round((dias / 179) * 100))}%

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
            if st.button("🗑️ Resetear contador", use_container_width=True):
                if st.checkbox("⚠️ ¿Estás seguro?", key="confirm_reset"):
                    profile["days"] = 0
                    profile["history"].append(f"{datetime.now().strftime('%d/%m/%Y %H:%M')} - RESET COMPLETO")
                    st.toast('🔄 Contador reseteado', icon='🔄')
                    time.sleep(1)
                    st.rerun()

else:
    st.warning("👆 Crea tu primer perfil arriba para comenzar")

st.divider()
st.caption("ℹ️ Calculadora orientativa. Verifica con tu agente de migración.")
st.caption("Hecho con ❤️ para Working Holiday Makers")
