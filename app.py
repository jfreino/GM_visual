import streamlit as st
import google.generativeai as genai
import time
import json

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Storyteller Visual", page_icon="🐉")

# Título y descripción
st.title("🐉 Aventuras RPG Infinitas")
st.caption("Narrado por Gemini Pro | Ilustrado por Pollinations.ai")

# Configurar API Key de Google (Se coge de los 'Secrets' de Streamlit)
# Si lo pruebas en local, puedes cambiar st.secrets["GOOGLE_API_KEY"] por tu clave directa "AIza..."
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except:
    st.warning("⚠️ No se ha detectado la API Key. Configúrala en los Secrets de Streamlit.")
    st.stop()

# Configurar el modelo
model = genai.GenerativeModel('gemini-3-flash-preview')

# --- ESTADO DE LA SESIÓN (MEMORIA) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Mensaje inicial del sistema para dar contexto
    st.session_state.messages.append({
        "role": "model", 
        "parts": ["¡Bienvenido aventurero! ¿Dónde comienza nuestra historia hoy? (Dime un género o escenario)"]
    })

# --- FUNCIÓN PARA GENERAR URL DE IMAGEN ---
def get_image_url(prompt):
    # Pollinations.ai es gratis y funciona por URL. 
    # Añadimos 'enhance=true' para que mejore el prompt visualmente.
    base_url = "https://image.pollinations.ai/prompt/"
    # Limpiamos el prompt para la url
    clean_prompt = prompt.replace(" ", "%20")
    # Añadimos una semilla aleatoria para que no cachee siempre la misma imagen
    seed = int(time.time())
    final_url = f"{base_url}{clean_prompt}?width=1024&height=768&seed={seed}&nologo=true"
    return final_url

# --- INTERFAZ DE CHAT ---
# Mostrar historia previa
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["parts"][0])
    elif msg["role"] == "model":
        with st.chat_message("assistant"):
            # Si el mensaje guardado es un diccionario complejo (nuestro JSON), lo parseamos
            try:
                content = msg["parts"][0]
                # A veces guardamos texto plano, a veces JSON. 
                if "{" in content and "imagen_prompt" in content:
                    data = json.loads(content)
                    st.markdown(data["historia"])
                    st.image(get_image_url(data["imagen_prompt"]), caption="Generado en tiempo real")
                else:
                    st.markdown(content)
            except:
                st.markdown(msg["parts"][0])

# --- INPUT DEL USUARIO ---
if prompt := st.chat_input("Tu acción..."):
    # 1. Mostrar mensaje usuario
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "parts": [prompt]})

    # 2. Generar respuesta
    with st.chat_message("assistant"):
        with st.spinner("El narrador está pensando y dibujando..."):
            
            # Prompt de sistema forzado en cada turno para asegurar el formato JSON
            system_instruction = """
            Actúa como un narrador de rol inmersivo.
            IMPORTANTE: Debes responder SIEMPRE en formato JSON estricto con esta estructura:
            {
                "historia": "Aquí escribes la narración de la aventura continuando lo anterior...",
                "imagen_prompt": "Aquí una descripción visual detallada de la escena actual en INGLÉS, estilo cinemático, fantasía, detallado."
            }
            No escribas nada fuera del JSON.
            """
            
            # Construir historial para enviar a Gemini
            history_payload = []
            for m in st.session_state.messages:
                # Convertir formato interno al formato de la API de Gemini
                role_api = "user" if m["role"] == "user" else "model"
                history_payload.append({"role": role_api, "parts": m["parts"]})
            
            # Añadir la instrucción actual
            full_prompt = f"{system_instruction}\n\nResponde a esto: {prompt}"
            
            try:
                chat = model.start_chat(history=history_payload[:-1]) # Historial menos el último mensaje que enviamos ahora
                response = chat.send_message(full_prompt)
                
               # ... (dentro del bloque donde generas la respuesta)

try:
    chat = model.start_chat(history=history_payload[:-1])
    response = chat.send_message(f"{system_instruction}\n\nAcción del usuario: {prompt}")
    
    # --- NUEVA FORMA DE EXTRAER EL TEXTO (A prueba de Gemini 3) ---
    text_response = ""
    
    # Verificamos si hay respuesta y si no ha sido bloqueada
    if response.candidates and response.candidates[0].content.parts:
        # Unimos todas las partes de texto (por si vienen separadas de los pensamientos)
        parts = [p.text for p in response.candidates[0].content.parts if hasattr(p, 'text')]
        text_response = "".join(parts).strip()
    else:
        # Si finish_reason es 1 (STOP) pero no hay partes, puede ser un error de la API
        st.warning(f"El modelo terminó (razón {response.candidates[0].finish_reason}), pero no envió texto.")
        st.stop()

    # Limpieza de JSON (igual que antes)
    if text_response.startswith("```json"):
        text_response = text_response.replace("```json", "").replace("```", "")
    
    # Intentar parsear el JSON
    data = json.loads(text_response)
    
    # 1. Mostrar texto narrativo
    st.markdown(data["historia"])
    
    # 2. Mostrar imagen
    if "imagen_prompt" in data and data["imagen_prompt"]:
        img_url = get_image_url(data["imagen_prompt"])
        st.image(img_url, caption="Visualización con Pollinations")
    
    # Guardar en el historial
    st.session_state.messages.append({"role": "model", "parts": [text_response]})

except json.JSONDecodeError:
    st.error("Gemini 3 generó un formato extraño. Reintentando...")
    st.write(text_response) # Para que veas qué ha devuelto exactamente
except Exception as e:
    st.error(f"Error crítico con Gemini 3: {e}")
