import streamlit as st
import google.generativeai as genai
import time
import json
import os

# --- 1. CONFIGURACIÓN DE PÁGINA (MODO ANCHO) ---
st.set_page_config(
    page_title="Storyteller RPG - Pulp Cthulhu", 
    page_icon="🐙", 
    layout="wide"  # Esto hace que la ventana use todo el ancho de la pantalla
)

# Estilo CSS personalizado para mejorar la lectura y el ancho del chat
st.markdown("""
    <style>
    .stChatMessage {
        max-width: 90% !important;
        margin: auto !important;
    }
    .stMarkdown {
        font-size: 1.1rem !important;
        line-height: 1.6 !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🐙 Pulp Cthulhu: Aventuras en los años 30")
st.caption("Gemini 3 Flash Preview | Visuales por Pollinations")

# --- 2. CONFIGURACIÓN DE API Y MODELO ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("Falta la API Key en los Secrets.")
    st.stop()

genai.configure(api_key=api_key)

generation_config = {
    "temperature": 1.0, # Más creatividad para el rol
    "top_p": 0.95,
    "response_mime_type": "application/json", # Intentamos forzar JSON
}

# Filtros desactivados para que no censure monstruos ni acción
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

# --- 3. ESTADO DE LA SESIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Mensaje inicial sin JSON para que el primer saludo sea natural
    st.session_state.messages.append({"role": "model", "parts": ["¡Bienvenido a la aventura! Estoy listo para narrar tu historia de Pulp Cthulhu."]})

def get_image_url(prompt):
    base_url = "https://image.pollinations.ai/prompt/"
    clean_prompt = prompt.replace(" ", "%20")
    seed = int(time.time())
    return f"{base_url}{clean_prompt}?width=1280&height=720&seed={seed}&nologo=true&enhance=true"

# --- 4. RENDERIZAR CHAT ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        content = msg["parts"][0]
        try:
            # Si es JSON, mostramos historia e imagen
            data = json.loads(content)
            st.markdown(data.get("historia", ""))
            if "imagen_prompt" in data:
                st.image(get_image_url(data["imagen_prompt"]))
        except:
            # Si no es JSON (como el saludo inicial), mostramos texto normal
            st.markdown(content)

# --- 5. LÓGICA DE INTERACCIÓN ---
if prompt := st.chat_input("Dime qué haces..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "parts": [prompt]})

    with st.chat_message("assistant"):
        with st.spinner("Narrando la siguiente escena..."):
            
            # Instrucción muy estricta para el JSON
            system_instruction = """
            Eres un narrador de rol para el sistema Pulp Cthulhu. 
            IMPORTANTE: Tu respuesta DEBE ser SIEMPRE un objeto JSON.
            No saludes, no te desvíes. 
            {
                "historia": "Escribe aquí la narración usando Markdown (negritas, títulos, etc.). Usa saltos de línea con \\n.",
                "imagen_prompt": "Descripción visual en inglés, detallada, estilo años 30, arte cinematográfico."
            }
            """
            
            # Construir historial limpio
            history_payload = []
            for m in st.session_state.messages:
                role = "user" if m["role"] == "user" else "model"
                raw_text = m["parts"][0]
                # Extraer solo el texto de la historia para no confundir al modelo con JSON viejos
                try:
                    raw_text = json.loads(raw_text).get("historia", raw_text)
                except:
                    pass
                history_payload.append({"role": role, "parts": [raw_text]})

            try:
                chat = model.start_chat(history=history_payload[:-1])
                response = chat.send_message(f"{system_instruction}\n\nAcción del usuario: {prompt}")
                
                # Extracción robusta del texto
                text_response = response.candidates[0].content.parts[0].text
                
                # Intentar parsear el JSON
                try:
                    data = json.loads(text_response)
                    # Si tiene éxito, mostramos bien
                    st.markdown(data.get("historia", ""))
                    if "imagen_prompt" in data:
                        st.image(get_image_url(data["imagen_prompt"]))
                    st.session_state.messages.append({"role": "model", "parts": [text_response]})
                
                except json.JSONDecodeError:
                    # FALLBACK: Si el modelo responde texto plano a pesar de todo
                    st.markdown(text_response)
                    # Creamos un JSON artificial para guardarlo en la sesión y que no falle el siguiente turno
                    fallback_json = json.dumps({"historia": text_response, "imagen_prompt": "Cthulhu mythos mystery"})
                    st.session_state.messages.append({"role": "model", "parts": [fallback_json]})
            
            except Exception as e:
                st.error(f"Error técnico: {e}")
