import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# 1. UČITAVANJE KLJUČEVA (Prvo ovo!)
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

app = Flask(__name__)

# 2. KONFIGURACIJA BAZE
# Fajl baze će biti u folderu 'instance' (Flask ga sam pravi)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

@app.route('/history', methods=['GET'])
def get_history():
    # Izvuci sve poruke iz baze, sortirane po vremenu
    messages = ChatMessage.query.order_by(ChatMessage.timestamp).all()
    
    # Pretvori Python objekte u JSON listu koju JS razume
    history = []
    for msg in messages:
        history.append({
            "sender": msg.sender,
            "content": msg.content
        })
    
    return jsonify(history)

# 3. DEFINISANJE TABELE (Model)
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(10), nullable=False) # 'user' ili 'bot'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# 4. KREIRANJE BAZE (Školski: unutar app_context-a)
with app.app_context():
    db.create_all()

# 5. POSTAVKA GEMINI MODELA
model = genai.GenerativeModel('gemini-2.5-flash')

# 6. RUTE
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get("message")

    if not user_text:
        return jsonify({"error": "Nema poruke"}), 400

    # Sačuvaj poruku korisnika u bazu
    user_msg = ChatMessage(sender='user', content=user_text)
    db.session.add(user_msg)
    
    try:
        # Pozovi Gemini sa instrukcijom (System Prompt)
        # Ovde ga "dresiraš" da bude tvoj prodavac
        system_instruction = "Ti si asistent na sajtu AI Agencije. Pomažeš klijentima da razumeju kako AI može unaprediti njihov biznis. Budi kratak i profesionalan."
        response = model.generate_content(f"{system_instruction}\n\nKorisnik kaže: {user_text}")
        bot_text = response.text

        # Sačuvaj odgovor bota u bazu
        bot_msg = ChatMessage(sender='bot', content=bot_text)
        db.session.add(bot_msg)
        db.session.commit()

        return jsonify({"response": bot_text})
    
    except Exception as e:
        print(f"Greška: {e}")
        return jsonify({"response": "Izvini, došlo je do greške u povezivanju sa mojim mozgom."}), 500

if __name__ == '__main__':
    app.run(debug=True)