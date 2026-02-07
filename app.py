import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pypdf import PdfReader

# 1. KONFIGURACIJA
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# OBAVEZNO: Tajni ključ za sesije (bez ovoga korpa ne radi!)
app.secret_key = 'neka_super_tajna_sifra_koju_niko_ne_zna' 

db = SQLAlchemy(app)

# --- GLOBALNA LISTA PROIZVODA ---
# Sada je ovde da bi je videle sve funkcije
PRODUCTS = [
    {'id': 1, 'name': 'AI Chatbot Basic', 'price': 299, 'image': '🤖', 'desc': 'Pametan asistent 24/7.'},
    {'id': 2, 'name': 'Web Optimizacija', 'price': 149, 'image': '⚡', 'desc': 'SEO i ubrzavanje sajta.'},
    {'id': 3, 'name': 'Python Automatizacija', 'price': 99, 'image': '🐍', 'desc': 'Skripte za dosadne poslove.'},
    {'id': 4, 'name': 'Konsultacije (1h)', 'price': 50, 'image': '👨‍💻', 'desc': 'Rešavanje tehničkih problema.'}
]

# 2. MODELI BAZE
# Izmena: Dodajemo session_id kolonu
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(50), nullable=False) # <--- NOVO
    sender = db.Column(db.String(10))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.String(50), nullable=False)

class CompanyInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)


# 3. HELPER FUNKCIJE
def init_db_data():
    if not Service.query.first():
        # --- USLUGE ---
        usluge = [
            Service(name="Web Development", description="Izrada modernih sajtova (HTML, CSS, JS, Python)", price="od 250€"),
            Service(name="AI Chatbot", description="Implementacija pametnih asistenata za vaš biznis", price="od 200€"),
            Service(name="Automatizacija", description="Skripte za ubrzavanje poslovnih procesa", price="Na upit")
        ]
        db.session.add_all(usluge)
        
        # --- KONTAKT ---
        info = [
            CompanyInfo(key="email", value="vasoje@tvoj-email.com"),
            CompanyInfo(key="phone", value="+381 6x xxx xxxx"),
            CompanyInfo(key="address", value="Online / Remote"),
            CompanyInfo(key="hours", value="Pon-Pet: 10-18h")
        ]
        db.session.add_all(info)
        db.session.commit()

def read_pdf_content():
    text_content = ""
    kb_folder = "knowledge_base"
    if not os.path.exists(kb_folder):
        return ""
    for filename in os.listdir(kb_folder):
        if filename.endswith(".pdf"):
            try:
                file_path = os.path.join(kb_folder, filename)
                reader = PdfReader(file_path)
                text_content += f"\n--- DOKUMENT: {filename} ---\n"
                for page in reader.pages:
                    text_content += page.extract_text() + "\n"
            except Exception:
                pass
    return text_content

# INICIJALIZACIJA BAZE (mora biti pre ruta)
with app.app_context():
    db.create_all()
    # init_db_data() # Otkomentariši ako ti treba ponovno punjenje

model = genai.GenerativeModel('gemini-2.5-flash') # 2.5 se koristi zbog brzine, ili 'gemini-2.5-pro' za bolje odgovore (ali sporije)

# 4. RUTE
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history', methods=['GET'])
def get_history():
    # Uzimamo session_id iz zahteva
    session_id = request.args.get('session_id')
    
    if not session_id:
        return jsonify([]) # Ako nema ID-a, vrati prazno

    # Filtriramo poruke SAMO za taj ID
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp).all()
    return jsonify([{"sender": m.sender, "content": m.content} for m in messages])

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get("message")
    session_id = data.get("session_id") # <--- NOVO
    
    if not session_id:
        return jsonify({"response": "Greška: Nedostaje Session ID"}), 400

    # 1. Čitanje istorije SAMO za ovog korisnika
    last_messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.id.desc()).limit(6).all()
    last_messages.reverse()
    
    history_text = "\n=== ISTORIJA RAZGOVORA ===\n"
    if not last_messages:
        history_text += "(Nema prethodnih poruka)\n"
    for msg in last_messages:
        role = "Korisnik" if msg.sender == 'user' else "Ti (Asistent)"
        history_text += f"{role}: {msg.content}\n"

    # 2. Čuvanje korisničke poruke sa ID-jem
    db.session.add(ChatMessage(sender='user', content=user_text, session_id=session_id))
    db.session.commit()
    
    try:
        # RAG Logika (Ostaje ista)
        services = Service.query.all()
        services_text = "\n".join([f"- {s.name} ({s.price}): {s.description}" for s in services])
        infos = CompanyInfo.query.all()
        contact_text = "\n".join([f"- {i.key.capitalize()}: {i.value}" for i in infos])
        pdf_knowledge = read_pdf_content()

        system_instruction = f"""
        Ti si AI asistent za 'AI Solutions'.
        PODACI:
        {contact_text}
        {services_text}
        {pdf_knowledge}
        UPUTSTVO: Koristi istoriju. Kratki odgovori.
        """

        full_prompt = f"{system_instruction}\n\n{history_text}\n\nKorisnik: {user_text}"
        
        response = model.generate_content(full_prompt)
        bot_text = response.text

        # 3. Čuvanje bot odgovora sa ID-jem
        db.session.add(ChatMessage(sender='bot', content=bot_text, session_id=session_id))
        db.session.commit()

        return jsonify({"response": bot_text})

    except Exception as e:
        print(e)
        return jsonify({"response": "Greška na serveru."}), 500

@app.route('/shop')
def shop():
    return render_template('shop.html', products=PRODUCTS)

@app.route('/cart')
def cart_page():
    # Uzmi korpu iz sesije, ili praznu listu ako nema ničega
    cart_items = session.get('cart', [])
    
    # Izračunaj ukupnu cenu (sumiramo cene svih proizvoda)
    total_price = sum(item['price'] for item in cart_items)
    
    return render_template('cart.html', cart=cart_items, total=total_price)

# --- NOVA RUTA: DAJ BROJ STVARI U KORPI ---
@app.route('/get_cart_count')
def get_cart_count():
    cart = session.get('cart', [])
    return jsonify({'count': len(cart)})

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    product_id = request.json.get('id')
    cart = session.get('cart', [])

    # Tražimo prvi proizvod sa tim ID-jem i brišemo ga
    for item in cart:
        if item['id'] == product_id:
            cart.remove(item) # Briše samo prvi na koji naiđe
            session.modified = True # Javljamo Flasku da sačuva promenu
            break # Prekidamo petlju da ne bi obrisali sve iste proizvode

    return jsonify({'status': 'success', 'count': len(cart)})

# --- NOVA RUTA: DODAJ U KORPU ---
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = request.json.get('id')
    
    # Nađi proizvod u listi
    product = next((p for p in PRODUCTS if p['id'] == product_id), None)
    
    if product:
        # Ako 'cart' ne postoji u sesiji, napravi praznu listu
        if 'cart' not in session:
            session['cart'] = []
        
        # Ubaci proizvod u sesiju
        session['cart'].append(product)
        session.modified = True # Kažemo Flasku da smo nešto promenili
        
        return jsonify({'status': 'success', 'count': len(session['cart'])})
    
    return jsonify({'status': 'error'}), 404

if __name__ == '__main__':
    app.run(debug=True)