import json
from flask import Flask, request
from google import genai
import main
import time
import requests
from datetime import datetime, timezone

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route("/privacy_policy")
def privacy_policy():
    with open("./privacy_policy.html", "rb") as file:
        privacy_policy_html = file.read()
    return privacy_policy_html

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        try: #disinilah proses notifikasi masuk dan bagaimana kita ingin memunculkannya
            print(json.dumps(request.get_json(), indent=4))
            data = request.get_json()
            entry = data["entry"][0]
            label = main.clasified_post(entry)
            print(f"label adalah: {label}")
            kalimat, jenis = main.complain_or_not(entry, label)
            print(f"kalimat adalah: {kalimat}")
            print(f"jenis adalah: {jenis}")
            text = main.auto_response(entry,label,jenis)

            #codenya masukin sini nanti
        except Exception as e:
            print(f"Error parsing JSON: {e}")
        return "<p>This is a POST request, Hello World!</p>"

    if request.method == "GET":
        hub_mode = request.args.get("hub.mode")
        hub_challenge = request.args.get("hub.challenge")  # ✅ fixed typo
        hub_verify_token = request.args.get("hub.verify_token")

        if hub_challenge:
            return hub_challenge
        else:
            return "<p>This is a GET request, Hello World!</p>"

if __name__ == "__main__":  # ✅ added this line to actually start the Flask server
    app.run(debug=True)
