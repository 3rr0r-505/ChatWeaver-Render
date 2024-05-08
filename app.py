import os
import markdown
# import webbrowser
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_bcrypt import generate_password_hash
from flask_bcrypt import check_password_hash
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI')
client = MongoClient(MONGODB_URI)
db = client.get_default_database()

# Ensure users and chats collections exist
if "users" not in db.list_collection_names():
    db.create_collection("users")
if "chats" not in db.list_collection_names():
    db.create_collection("chats")

# MongoDB collections
users_collection = db.get_collection('users')
chats_collection = db.get_collection('chats')

#Gemini Model
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.0-pro-latest')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

@app.route("/")
def index():
    if "user_email" in session:
        # Load previous chats from MongoDB for the logged-in user
        user_email = session["user_email"]
        user = users_collection.find_one({"email": user_email})
        if user:
            previous_chats = user.get("chats", [])
        else:
            previous_chats = []
        
        # Convert bot responses to markdown format
        for chat in previous_chats:
            chat['bot_response'] = markdown.markdown(chat['bot_response'])
        
        return render_template('chat.html', previous_chats=previous_chats)
    else:
        return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        
        user = users_collection.find_one({"email": email})
        if user:
            # User exists, check password
            if check_password_hash(user["password"], password):
                # Password is correct, log in the user
                session["user_email"] = email
                flash("Login successful!", "success")
                return redirect(url_for("index"))
            else:
                flash("Invalid email or password", "error")
        else:
            # User does not exist, register them
            hashed_password = generate_password_hash(password).decode('utf-8')
            users_collection.insert_one({"email": email, "password": hashed_password, "chats": []})
            session["user_email"] = email
            flash("Registration successful! You are now logged in.", "success")
            return redirect(url_for("index"))
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_email", None)
    flash("You have been logged out", "info")
    return redirect(url_for("login"))

@app.route("/get", methods=["POST"])
def chat():
    if "user_email" in session:
        user_email = session["user_email"]
        user = users_collection.find_one({"email": user_email})
        if user:
            user_message = request.form["msg"]
            bot_response_markdown, raw_response = get_chat_response(user_message)  # Get the markdown-formatted response
            
            # Save the chat to MongoDB for the logged-in user
            chats_collection.insert_one({"user_email": user_email, "user_message": user_message, "bot_response": raw_response})
            # Also update the user's chats list
            users_collection.update_one({"email": user_email}, {"$push": {"chats": {"user_message": user_message, "bot_response": raw_response}}})
            
            return bot_response_markdown

    return "You are not logged in"

def get_chat_response(question):
    response = model.generate_content(question)

    markdown_response = markdown.markdown(response.text)
    return markdown_response, response.text

# if __name__ == '__main__':
#     webbrowser.open('http://127.0.0.1:8000')
#     app.run(host='127.0.0.1', port=8000)
