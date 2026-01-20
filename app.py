import streamlit as st
import google.generativeai as genai
import time
import json
import os
import re

# --- 1. CONFIGURACIÓN DE PÁGINA (ANCHO OPTIMIZADO) ---
st.set_page_config(
    page_title="Pulp Cthulhu Storyteller", 
    page_icon="🐙", 
    layout="wide" 
)

# Estilo para que el texto no sea "infinito" pero la ventana sea ancha
st.markdown("""
    <style>
    .stChatMessage {
        max-width: 85% !important;
        margin: auto !important;
        padding: 20px !important;
    }
    .stMarkdown {
        font-size: 1.2rem !important;
        line-height: 1.7 !important;
        font-family: 'Georgia', serif;
    }
    img {
        border-radius: 15px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.5);
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🐙 Pulp Cthulhu: Crónicas de 1934")

# --- 2. CONFIGURACIÓN DE API Y MODELO ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("Falta la API Key en los Secrets.")
    st.stop()

genai.configure(api_key=api_key)

generation_config = {
    "temperature": 1.0,
    "top_p": 0.95,
    "response_mime_type": "application/json",
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Usamos el modelo puntero que indicaste
MODEL_ID = 'gemini-3-flash-preview'
model = genai.GenerativeModel(model_name=MODEL_ID, generation_config=generation_config, safety_settings=safety_settings)

# --- 3. ESTADO DE LA SESIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "model", "parts": ["¡Bienvenido! Estoy listo para narrar tu historia de horror y aventura."]})

def get_image_url(prompt):
    # Añadimos un timestamp para evitar que el navegador cachee la imagen de error
    seed = int(time.time())
    clean_prompt = re.sub(r'[^\w\s]', '', prompt).replace(" ", "%20")
    return f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1280&height=720&seed={seed}&nologo=true&enhance=true&model=flux"

# --- 4. RENDERIZAR CHAT ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # Verificación de seguridad para evitar "list index out of range"
        if not msg.get("parts") or len(msg["parts"]) == 0:
            continue
            
        content = msg["parts"][0]
        try:
            data = json.loads(content)
            st.markdown(data.get("historia", ""))
            if "imagen_prompt" in data:
                st.image(get_image_url(data["imagen_prompt"]))
        except:
            st.markdown(content)

# --- 5. LÓGICA DE INTERACCIÓN ---
if prompt := st.chat_input("Dime qué haces..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "parts": [prompt]})

    with st.chat_message("assistant"):
        with st.spinner("El Guardián de los Arcanos está escribiendo..."):
            
            # Instrucción de sistema
            system_instruction = """
            Eres un narrador de rol para Pulp Cthulhu. 
            Responde SIEMPRE con un objeto JSON.
            {
                "historia": "Narración en Markdown. Usa **negritas** para énfasis y \\n\\n para párrafos.",
                "imagen_prompt": "Prompt visual detallado en inglés."
            }
            """
            
            # Construir historial SEGURO
            history_payload = []
            for m in st.session_state.messages:
                if m.get("parts") and len(m["parts"]) > 0:
                    role = "user" if m["role"] == "user" else "model"
                    txt = m["parts"][0]
                    try:
                        # Extraemos solo el texto para no marear a la IA con JSONs viejos
                        txt = json.loads(txt).get("historia", txt)
                    except: pass
                    history_payload.append({"role": role, "parts": [txt]})

            try:
                chat = model.start_chat(history=history_payload[:-1])
                response = chat.send_message(f"{system_instruction}\n\nAcción: {prompt}")
                
                # Extracción robusta (evita index out of range)
                if response.candidates and response.candidates[0].content.parts:
                    text_response = response.candidates[0].content.parts[0].text
                else:
                    st.error("El modelo no devolvió texto. Quizá por seguridad.")
                    st.stop()

                # Limpiador de JSON por si la IA pone texto extra
                json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
                if json_match:
                    text_clean = json_match.group(0)
                    data = json.loads(text_clean)
                    
                    # Mostrar texto
                    st.markdown(data.get("historia", ""))
                    
                    # Mostrar imagen con manejo de errores (Pollinations Rate Limit)
                    if "imagen_prompt" in data:
                        try:
                            st.image(get_image_url(data["imagen_prompt"]))
                        except:
                            st.info("🖼️ (La imagen no pudo cargarse esta vez, pero la historia continúa...)")
                    
                    # Guardar respuesta
                    st.session_state.messages.append({"role": "model", "parts": [text_clean]})
                else:
                    # Si no hay JSON, mostramos texto plano
                    st.markdown(text_response)
                    st.session_state.messages.append({"role": "model", "parts": [json.dumps({"historia": text_response})]})
            
            except Exception as e:
                st.error(f"Error técnico: {e}")

