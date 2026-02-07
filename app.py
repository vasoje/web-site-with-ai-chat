import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pypdf import PdfReader

# 1. KONFIGURACIJA
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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

with app.app_context():
    db.create_all()
    init_db_data()

model = genai.GenerativeModel('gemini-2.5-flash')

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
    # Ovde ćemo kasnije dodati proizvode
    return render_template('shop.html')

if __name__ == '__main__':
    app.run(debug=True)