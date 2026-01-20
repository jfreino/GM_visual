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
                # Iniciamos el chat con el historial (menos el último mensaje que enviamos ahora)
                chat = model.start_chat(history=history_payload[:-1])
                
                # Enviamos el mensaje con la instrucción de sistema
                full_query = f"{system_instruction}\n\nAcción del usuario: {prompt}"
                response = chat.send_message(full_query)
                
                # --- EXTRACCIÓN ROBUSTA DE TEXTO ---
                text_response = ""
                if response.candidates and response.candidates[0].content.parts:
                    # Unimos todas las partes de texto (evita errores en modelos de pensamiento)
                    parts = [p.text for p in response.candidates[0].content.parts if hasattr(p, 'text')]
                    text_response = "".join(parts).strip()
                else:
                    st.error("El modelo no devolvió contenido válido.")
                    st.stop()

                # Limpieza de posibles bloques de código Markdown
                if text_response.startswith("```"):
                    # Elimina ```json al principio y ``` al final
                    text_response = text_response.split("```")[1]
                    if text_response.startswith("json"):
                        text_response = text_response[4:]
                
                # 3. Parsear JSON y mostrar resultados
                data = json.loads(text_response.strip())
                
                # Mostrar texto narrativo
                st.markdown(data.get("historia", "El narrador guarda silencio..."))
                
                # Mostrar imagen
                if "imagen_prompt" in data:
                    img_url = get_image_url(data["imagen_prompt"])
                    st.image(img_url, caption="Escena actual")
                
                # Guardar la respuesta completa en el historial para el próximo turno
                st.session_state.messages.append({"role": "model", "parts": [text_response]})
                
            except json.JSONDecodeError as e:
                st.error("Error al interpretar el JSON del narrador.")
                st.info("Respuesta cruda del modelo:")
                st.code(text_response)
            except Exception as e:
                st.error(f"Error crítico: {e}")
