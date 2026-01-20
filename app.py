import streamlit as st
import google.generativeai as genai
import time
import json

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Storyteller Visual", page_icon="🐉")

# --- CONFIGURACIÓN DEL MODELO CON FILTROS RELAJADOS ---
generation_config = {
    "temperature": 0.9,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,
    "response_mime_type": "application/json", # Forzamos a que la salida sea JSON
}

# Relajamos los filtros para que no se bloquee por temas de RPG (combate, etc.)
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel(
    model_name='gemini-3-flash-preview',
    generation_config=generation_config,
    safety_settings=safety_settings
)

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

# --- PROCESAR INPUT USUARIO ---
if prompt := st.chat_input("Tu acción..."):
    # 1. Mostrar mensaje del usuario en la pantalla
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Guardar en el historial de la sesión
    st.session_state.messages.append({"role": "user", "parts": [prompt]})

    # 2. Generar respuesta de la IA
    with st.chat_message("assistant"):
        with st.spinner("Gemini 3 está narrando y dibujando..."):
            
            # Instrucción de sistema para asegurar el formato
            system_instruction = """
            Eres un narrador de rol experto. 
            Responde ÚNICAMENTE con un objeto JSON. 
            NO incluyas razonamientos internos ni etiquetas de Markdown fuera del JSON.
            Formato:
            {
                "historia": "La narración aquí...",
                "imagen_prompt": "Descripción visual en inglés para la imagen..."
            }
            """
            
            # --- AQUÍ DEFINIMOS history_payload (Lo que faltaba) ---
            history_payload = []
            for m in st.session_state.messages:
                role_api = "user" if m["role"] == "user" else "model"
                content = m["parts"][0]
                # Si el contenido es un JSON de un turno anterior, extraemos solo la historia 
                # para no ensuciar la memoria del modelo con estructuras JSON viejas
                if role_api == "model" and "{" in content:
                    try:
                        d = json.loads(content)
                        content = d.get("historia", content)
                    except:
                        pass
                history_payload.append({"role": role_api, "parts": [content]})
            
            try:
                chat = model.start_chat(history=history_payload[:-1])
                
                # Al haber configurado response_mime_type: application/json arriba, 
                # Gemini 3 ya sabe que solo debe escupir JSON.
                response = chat.send_message(f"Acción del usuario: {prompt}")
                
                # --- DIAGNÓSTICO DE RESPUESTA ---
                if not response.candidates or not response.candidates[0].content.parts:
                    # Si no hay partes, miramos la razón técnica
                    reason = response.candidates[0].finish_reason if response.candidates else "Desconocida"
                    st.error(f"El modelo no devolvió texto. Razón técnica: {reason}")
                    
                    # Si fue por seguridad, avisamos
                    if "SAFETY" in str(reason):
                        st.warning("⚠️ La respuesta fue bloqueada por los filtros de seguridad de Google. Intenta una acción menos violenta o explícita.")
                    st.stop()

                # Extraer texto de forma segura
                text_response = response.candidates[0].content.parts[0].text
                
                # 3. Parsear JSON (Gemini 3 con mime_type suele devolver JSON puro, sin ```json)
                text_clean = text_response.strip()
                if text_clean.startswith("```"):
                    text_clean = text_clean.split("```")[1]
                    if text_clean.startswith("json"): text_clean = text_clean[4:]
                
                data = json.loads(text_clean)
                
                # Mostrar resultados
                st.markdown(data.get("historia", "..."))
                if "imagen_prompt" in data:
                    st.image(get_image_url(data["imagen_prompt"]))
                
                st.session_state.messages.append({"role": "model", "parts": [text_response]})
                
            except Exception as e:
                st.error(f"Error en el turno: {e}")
                st.info("Respuesta cruda para depurar:")
                st.code(response.text if 'response' in locals() else "Sin respuesta")
