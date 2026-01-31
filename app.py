import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pypdf import PdfReader  # Biblioteka za čitanje PDF-a

# 1. KONFIGURACIJA
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 2. MODELI BAZE (Struktura podataka)

# Istorija četa
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(10))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Usluge i Cene
class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.String(50), nullable=False)

# Kontakt Informacije o Firmi (Single Source of Truth)
class CompanyInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False) # npr. 'email', 'phone'
    value = db.Column(db.Text, nullable=False) # npr. 'vasoje@email.com'

# 3. FUNKCIJE ZA UPRAVLJANJE ZNANJEM

def init_db_data():
    """Popunjava bazu početnim podacima ako je prazna"""
    if not Service.query.first():
        # Usluge
        usluge = [
            Service(name="Web Development", description="Izrada sajtova, React, Python", price="od 200€"),
            Service(name="AI Chatbot", description="Pametni asistent za vaš sajt", price="od 150€"),
            Service(name="SEO Optimizacija", description="Pozicioniranje na Google-u", price="100€ mesečno")
        ]
        db.session.add_all(usluge)
        
        # Kontakt podaci
        info = [
            CompanyInfo(key="email", value="vasojevicivan@yahoo.com"),
            CompanyInfo(key="phone", value="+381 6x xxx xxxx"),
            CompanyInfo(key="address", value="Remote, Čačak"),
            CompanyInfo(key="hours", value="Pon-Sub: 09-17h")
        ]
        db.session.add_all(info)
        
        db.session.commit()
        print("✅ Baza inicijalizovana sa uslugama i kontaktima.")

def read_pdf_content():
    """Čita sve PDF fajlove iz foldera 'knowledge_base'"""
    text_content = ""
    kb_folder = "knowledge_base"
    
    if not os.path.exists(kb_folder):
        os.makedirs(kb_folder) # Napravi folder ako ne postoji
        return ""

    for filename in os.listdir(kb_folder):
        if filename.endswith(".pdf"):
            try:
                file_path = os.path.join(kb_folder, filename)
                reader = PdfReader(file_path)
                text_content += f"\n--- SADRŽAJ DOKUMENTA: {filename} ---\n"
                for page in reader.pages:
                    text_content += page.extract_text() + "\n"
            except Exception as e:
                print(f"Greška pri čitanju {filename}: {e}")
                
    return text_content

# 4. INICIJALIZACIJA PRI POKRETANJU
with app.app_context():
    db.create_all()
    init_db_data() # Ovo pozivamo da napunimo bazu

model = genai.GenerativeModel('gemini-2.5-flash')

# 5. RUTE

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history', methods=['GET'])
def get_history():
    messages = ChatMessage.query.order_by(ChatMessage.timestamp).all()
    return jsonify([{"sender": m.sender, "content": m.content} for m in messages])

@app.route('/chat', methods=['POST'])
def chat():
    user_text = request.json.get("message")
    
    # 1. PRIPREMA ISTORIJE (Pre nego što sačuvamo novu poruku)
    # Izvlačimo poslednjih 6 poruka da bi bot imao kontekst
    last_messages = ChatMessage.query.order_by(ChatMessage.id.desc()).limit(6).all()
    last_messages.reverse() # Vraćamo ih u hronološki red (od najstarije ka najnovijoj)
    
    history_text = "\n=== ISTORIJA RAZGOVORA ===\n"
    if not last_messages:
        history_text += "(Nema prethodnih poruka)\n"
    
    for msg in last_messages:
        role = "Korisnik" if msg.sender == 'user' else "Ti (Asistent)"
        history_text += f"{role}: {msg.content}\n"

    # 2. Sačuvaj trenutnu poruku korisnika u bazu
    # (Radimo ovo POSLE čitanja istorije da ne bi duplirali trenutnu poruku u kontekstu)
    db.session.add(ChatMessage(sender='user', content=user_text))
    db.session.commit() # Obavezan commit da bi poruka dobila ID i timestamp
    
    try:
        # 3. PRIKUPLJANJE ZNANJA (RAG DEO - OVO OSTAJE ISTO)
        services = Service.query.all()
        services_text = "\n".join([f"- {s.name} ({s.price}): {s.description}" for s in services])
        
        infos = CompanyInfo.query.all()
        contact_text = "\n".join([f"- {i.key.capitalize()}: {i.value}" for i in infos])
        
        pdf_knowledge = read_pdf_content()

        # 4. FORMIRANJE MOZGA (System Prompt + Istorija)
        system_instruction = f"""
        Ti si napredni AI asistent za kompaniju 'AI Solutions'.
        
        TVOJI IZVORI PODATAKA:
        === KONTAKT INFORMACIJE ===
        {contact_text}
        === NAŠE USLUGE I CENE ===
        {services_text}
        === DODATNO ZNANJE (DOKUMENTI) ===
        {pdf_knowledge}
        
        UPUTSTVO:
        - Koristi istoriju razgovora da bi razumeo kontekst (npr. ako korisnik kaže "to mi se sviđa", znaj na šta misli).
        - Odgovaraj kratko i profesionalno.
        """

        # SPAJAMO SVE: Instrukcije + Istorija + Trenutno pitanje
        full_prompt = f"{system_instruction}\n\n{history_text}\n\nKorisnik sada pita: {user_text}"
        
        response = model.generate_content(full_prompt)
        bot_text = response.text

        # 5. Sačuvaj odgovor bota
        db.session.add(ChatMessage(sender='bot', content=bot_text))
        db.session.commit()

        return jsonify({"response": bot_text})

    except Exception as e:
        print(f"Greška: {e}")
        return jsonify({"response": "Greška na serveru."}), 500

if __name__ == '__main__':
    app.run(debug=True)