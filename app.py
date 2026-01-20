import streamlit as st
import google.generativeai as genai
import json
import os
import re
import requests
import time

# --- 1. CONFIGURACIÓN DE PÁGINA (ESTILO PULP/RPG) ---
st.set_page_config(
    page_title="Pulp Cthulhu Storyteller", 
    page_icon="🐙", 
    layout="wide" 
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Special+Elite&display=swap');
    
    .stChatMessage {
        max-width: 80% !important;
        margin: auto !important;
    }
    .stMarkdown {
        font-size: 1.25rem !important;
        line-height: 1.8 !important;
        font-family: 'Georgia', serif;
    }
    h1 {
        font-family: 'Special Elite', cursive;
        text-align: center;
        color: #2e4d36;
    }
    .stImage img {
        border: 5px solid #2e4d36;
        border-radius: 10px;
        box-shadow: 5px 5px 15px rgba(0,0,0,0.7);
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🐙 Pulp Cthulhu: Crónicas de 1934")

# --- 2. CONFIGURACIÓN DE APIS ---
GOOGLE_KEY = st.secrets.get("GOOGLE_API_KEY")
HF_TOKEN = st.secrets.get("HF_TOKEN")

if not GOOGLE_KEY or not HF_TOKEN:
    st.error("Faltan las claves API (GOOGLE_API_KEY o HF_TOKEN) en los Secrets.")
    st.stop()

genai.configure(api_key=GOOGLE_KEY)

# Configuración del modelo Gemini 3
generation_config = {
    "temperature": 1.0,
    "top_p": 0.95,
    "response_mime_type": "application/json",
}

# Desactivar censura de Google para el texto narrativo
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

# --- 3. FUNCIONES DE APOYO ---

def generate_flux_image(visual_prompt):
    """Genera imagen usando FLUX.1-schnell en Hugging Face (Alta calidad/Sin censura)"""
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    # Enriquecemos el prompt para mantener el estilo artístico
    pulp_prompt = f"Cinematic 1930s pulp adventure style, gritty atmosphere, {visual_prompt}, highly detailed, oil painting texture, dramatic lighting"
    
    payload = {"inputs": pulp_prompt, "parameters": {"width": 1024, "height": 768}}
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=40)
        if response.status_code == 200:
            return response.content # Devuelve los bytes de la imagen
        else:
            return None
    except:
        return None

def clean_json_response(text):
    """Extrae el JSON del texto por si el modelo añade explicaciones"""
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return None
    except:
        return None

# --- 4. GESTIÓN DE LA SESIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Saludo inicial
    st.session_state.messages.append({
        "role": "model", 
        "parts": ["¡Bienvenido, aventurero! El motor de tu hidroavión tose humo negro sobre la selva. El destino te espera. ¿Quién eres y qué haces primero?"]
    })

# --- 5. RENDERIZAR CHAT ---
for msg in st.session_state.messages:
    if not msg.get("parts"): continue
    
    with st.chat_message(msg["role"]):
        raw_content = msg["parts"][0]
        data = clean_json_response(raw_content)
        
        if data:
            st.markdown(data.get("historia", ""))
            # Si el mensaje guardado incluía una imagen (bytes o url), aquí podrías mostrarla.
            # Para simplificar, en el renderizado histórico solo mostramos el texto.
            if "visual_data" in msg:
                st.image(msg["visual_data"])
        else:
            st.markdown(raw_content)

# --- 6. BUCLE DE INTERACCIÓN ---
if prompt := st.chat_input("Escribe tu acción aquí..."):
    # Mostrar mensaje usuario
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "parts": [prompt]})

    with st.chat_message("assistant"):
        with st.spinner("El Guardián está tejiendo la realidad..."):
            
            # Instrucción de sistema
            system_instruction = """
            Eres un narrador de rol experto en Pulp Cthulhu. 
            Responde SIEMPRE en JSON con esta estructura exacta:
            {
                "historia": "Escribe aquí la narración literaria usando Markdown.",
                "imagen_prompt": "Descripción visual detallada en INGLÉS para la imagen."
            }
            """
            
            # Construir historial limpio (solo texto)
            history_payload = []
            for m in st.session_state.messages:
                role = "user" if m["role"] == "user" else "model"
                txt = m["parts"][0]
                extracted = clean_json_response(txt)
                if extracted: txt = extracted.get("historia", txt)
                history_payload.append({"role": role, "parts": [txt]})

            try:
                # 1. Obtener texto de Gemini
                chat = model.start_chat(history=history_payload[:-1])
                response = chat.send_message(f"{system_instruction}\n\nAcción del jugador: {prompt}")
                
                # Extraer texto de la respuesta (manejo robusto de Gemini 3)
                if response.candidates and response.candidates[0].content.parts:
                    raw_text = response.candidates[0].content.parts[0].text
                else:
                    st.error("El modelo no pudo responder. Intenta otra acción.")
                    st.stop()

                data = clean_json_response(raw_text)
                
                if data:
                    # 2. Mostrar Narración
                    st.markdown(data["historia"])
                    
                    # 3. Generar Imagen con FLUX.1
                    img_data = generate_flux_image(data["imagen_prompt"])
                    
                    if img_data:
                        st.image(img_data, caption="Escena visualizada por FLUX.1")
                        # Guardamos los bytes de la imagen en el mensaje para que persista en la sesión
                        st.session_state.messages.append({
                            "role": "model", 
                            "parts": [raw_text],
                            "visual_data": img_data
                        })
                    else:
                        st.info("⌛ El generador de imágenes está ocupado, pero la historia continúa...")
                        st.session_state.messages.append({"role": "model", "parts": [raw_text]})
                else:
                    # Fallback si no hay JSON
                    st.markdown(raw_text)
                    st.session_state.messages.append({"role": "model", "parts": [raw_text]})

            except Exception as e:
                st.error(f"Error en el velo de la realidad: {e}")
