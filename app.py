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
model = genai.GenerativeModel('gemini-3-pro-preview')

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
                
                # Limpiar la respuesta por si Gemini pone ```json ... ```
                text_response = response.text.strip()
                if text_response.startswith("```json"):
                    text_response = text_response.replace("```json", "").replace("```", "")
                
                # Parsear JSON
                data = json.loads(text_response)
                narracion = data["historia"]
                visual_prompt = data["imagen_prompt"]
                
                # Mostrar Texto
                st.markdown(narracion)
                
                # Mostrar Imagen
                image_url = get_image_url(visual_prompt)
                st.image(image_url, caption="Visualización de la escena")
                
                # Guardar en el historial (guardamos el JSON raw para poder reconstruirlo luego)
                st.session_state.messages.append({"role": "model", "parts": [text_response]})
                
            except Exception as e:
                st.error(f"Error narrativo: {e}")
                # Fallback por si el JSON falla
                st.markdown("El narrador se ha confundido, intenta otra acción.")




