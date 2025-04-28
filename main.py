import firebase_admin
from firebase_admin import credentials, firestore
from transformers import AutoTokenizer, AutoModelForCausalLM
import requests
import unicodedata
from flask import Flask, request

# Firebase 
if not firebase_admin._apps:
    cred = credentials.Certificate("./ninatec-ecc00-firebase-adminsdk-fbsvc-5d1171c4a7 (1).json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Cargar el modelo desde Hugging Face
model_name = "NadiaLiz/Llama-3.2"  
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

# WhatsApp Business API credentials
WHATSAPP_API_URL = "https://graph.facebook.com/v13.0/1003671118634835/messages"
ACCESS_TOKEN = "EAAJqQiKe1jgBO4ZAPuNwAwCnJElu5wJD8KslYnk8958mSyx9TDgw5wjd1Jz1N9dkl24o7ynoL7a82Ht1L8FUVA2NiS9iSCPHMovMEiYTR92SN9uubZAxQu9goMEFdZBQxmwQJWXoJSrSO58bcIXGxBHZAv84WWsYkePJB0k3P0XZC6soQot5ZCcEG6ZBe55qjZBxXnZBmOnXDO8gb6bU9MZBCpXcUbLukZD"

# Funciones de contexto y normalización
def obtener_contexto():
    return (
        "Eres un asistente virtual de Ninatec, una empresa especializada en tecnología y automatización. "
        "Estás capacitado para responder preguntas sobre nuestros productos, servicios y soporte técnico. "
        "Responde siempre de manera amable, clara y profesional."
    )

def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    return texto

def extraer_producto(mensaje):
    mensaje_norm = normalizar(mensaje)
    productos_ref = db.collection("Productos").stream()

    for doc in productos_ref:
        nombre_producto = doc.to_dict().get("producto")
        nombre_norm = normalizar(nombre_producto)

        if nombre_norm in mensaje_norm:
            return doc.id
    return None

def buscar_precio(producto):
    ref = db.collection("Productos").document(producto)
    doc = ref.get()

    if doc.exists:
        data = doc.to_dict()
        producto = data.get("producto")
        precio = data.get("precio")
        return f"Claro, el {producto} cuesta S/{precio}."
    else:
        return None

# Función para enviar mensaje a WhatsApp Business API
def send_whatsapp_message(to, message):
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message}
    }
    response = requests.post(WHATSAPP_API_URL, headers=headers, json=data)
    return response.json()

# Endpoint Flask para recibir mensajes de WhatsApp
app = Flask(__name__)

# Ruta para verificación de webhook
@app.route('/whatsapp', methods=['GET', 'POST'])
def whatsapp_mymessage():
    if request.method == 'GET':
        # Aquí debes colocar el token de verificación que configuraste en la consola de WhatsApp
        VERIFY_TOKEN = "mi_token_unico_12345"

        # Recuperamos los parámetros de la solicitud GET
        mode = request.args.get('hub.mode')
        challenge = request.args.get('hub.challenge')
        verify_token = request.args.get('hub.verify_token')

        # Verificar si el token de verificación coincide
        if mode == 'subscribe' and verify_token == VERIFY_TOKEN:
            print("Webhook verificado correctamente")
            return str(challenge)  # Devuelves el challenge que WhatsApp te envió
        else:
            return 'Error, token no coincide', 403

    elif request.method == 'POST':
        incoming_msg = request.values.get('Body', '').lower()
        print("Mensaje recibido:", incoming_msg)
        from_number = request.values.get('From', '')

        respuesta = ""
        contexto = obtener_contexto()

        if "precio" in incoming_msg or "cuánto cuesta" in incoming_msg:
            producto = extraer_producto(incoming_msg)
            if producto:
                respuesta = buscar_precio(producto)
                if not respuesta:
                    respuesta = f"Lo siento, no encontré detalles para el producto '{producto}'."
            else:
                respuesta = "¿De qué producto deseas saber el precio?"
        else:
            prompt = (
                f"{contexto}\n\n"
                f"Usuario: {incoming_msg}\n"
                f"Asistente:"
            )

            inputs = tokenizer(prompt, return_tensors="pt")
            outputs = model.generate(**inputs, max_new_tokens=100, do_sample=True, temperature=0.7)
            respuesta_generada = tokenizer.decode(outputs[0], skip_special_tokens=True)
            respuesta = respuesta_generada.replace(prompt, "").strip()

        print("Respuesta generada:", respuesta)

        # Enviar la respuesta por WhatsApp Business API
        send_whatsapp_message(from_number, respuesta)

        return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
