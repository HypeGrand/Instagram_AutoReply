from google import genai
import time
import requests
from datetime import datetime, timezone
import json
from flask import Flask, request
# LOAD CONFIG SEKALI SAJA DI AWAL
with open("cwdchat_config.json", "r", encoding="utf-8") as file:
    config = json.load(file)

key = config.get("key")  # API key Gemini
long_access_token = config.get("long_access_token")  # IG long-lived token

client = genai.Client(api_key=key)

def comment(data, key, long_access_token):
    """Handle comment replies"""
    try:
        comment_text = data["changes"][0]["value"]["text"]
        comment_id = data["changes"][0]["value"]["id"]
        media_id = data["changes"][0]["value"]["media"]["id"]
        username = data["changes"][0]["value"]["from"]["username"]

        # Get post data
        url = f"https://graph.instagram.com/{media_id}"
        fields = "id,caption,media_type,media_url,permalink,timestamp,username"
        payload = {
            "fields": fields,
            "access_token": long_access_token
        }

        response = requests.get(url, params=payload)
        post = response.json()

        caption = post.get("caption", "")
        user = post.get("username", "")

        # Only reply if commenter is not post owner
        if user != username:
            prompt = f'''
            Terdapat caption postingan: ({caption}). 
            @{username} memberikan komentar: ({comment_text}). 

            Buat balasan singkat dan ramah seperti admin atau SPG toko yang sopan dan antusias. 
            Jika komentarnya berupa pertanyaan, mulai dengan memuji pertanyaannya lalu jawab singkat. 
            Jika komentarnya bukan pertanyaan, cukup ucapkan terima kasih dengan nada positif dan bersahabat. 
            Jika isi komentar menunjukkan keluhan, arahkan dengan sopan agar pengguna memeriksa DM. 

            Gunakan bahasa sehari-hari yang natural (tidak kaku, tidak alay, tanpa tanda *), cukup satu kalimat saja. 
            Awali balasan dengan menyapa dan bilang, kalo saya adalah Jokowi, dan jangan gunakan aku atau saya tapi sebut nama Jokowi
            Jangan ajak untuk cek postingan lain atau promosi tambahan.
            '''

            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model = "gemini-2.5-flash", contents=prompt
            )
            jawaban = response.text

            # Send comment reply
            reply_url = f"https://graph.instagram.com/v24.0/{comment_id}/replies"
            payload = {
                "message": jawaban, 
                "access_token": long_access_token
            }
            response = requests.post(reply_url, params=payload)
            print("Comment has been replied")
            print(f"Response: {response.status_code}")
            
    except Exception as e:
        print(f"Error in comment function: {e}")


def reply_story():
    """Handle story reply"""
    print("Story reply has been replied")


def dm_reply():
    """Handle DM reply"""
    print("DM reply has been replied")


def story_mention(data, long_access_token):
    """Handle story mentions"""
    try:
        messaging = data["messaging"][0]
        mid = messaging["message"]["mid"]
        recipient_id = messaging["sender"]["id"]
        
        # Reply to DM
        text = "Terima kasih sudah mention kami di IG Story Anda 😊 Jika ada informasi tambahan atau kendala, silakan chat di sini ya!"

        message_url = "https://graph.instagram.com/v24.0/me/messages"
        headers = {
            "Authorization": f"Bearer {long_access_token}",
            "Content-Type": "application/json"
        }
        json_body = {
            "recipient": {"id": recipient_id},
            "message": {"text": text}
        }

        requests.post(message_url, headers=headers, json=json_body)

        # React with love
        react_url = f"https://graph.instagram.com/v24.0/me/messages"
        headers["Authorization"] = f"Bearer {long_access_token}"
        payload = {
            "recipient": {"id": recipient_id},
            "sender_action": "react",
            "payload": {
                "message_id": mid,
                "reaction": "love"
            }
        }
        requests.post(react_url, headers=headers, json=payload)
        print("Story mention has been replied")
        
    except Exception as e:
        print(f"Error in story_mention: {e}")


def time_diff(data, long_access_token, wait_second=30):
    """Calculate time difference between now and last message"""
    print("[LOG] === Masuk time_diff ===")

    try:
        sender_id = data["messaging"][0]["sender"]["id"]
        
        url = "https://graph.instagram.com/v24.0/me/conversations"
        payload = {
            "platform": "instagram",
            "fields": "messages{created_time,from,message,reactions,shares,attachment,reply,story,reply_to}",
            "access_token": long_access_token,
            "user_id": sender_id
        }

        print(f"[LOG] Menunggu {wait_second} detik sebelum GET conversation...")
        time.sleep(wait_second)

        second = requests.get(url, params=payload)
        second = second.json()

        latest_msg = second["data"][0]["messages"]["data"][0]
        chat_time = latest_msg["created_time"]
        then = datetime.strptime(chat_time, "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.now(timezone.utc)

        diff = (now - then).total_seconds()
        print(f"[LOG] Waktu pesan terakhir: {diff}s yang lalu")

        return diff
        
    except Exception as e:
        print(f"[ERROR] Error in time_diff: {e}")
        return 9999


def clasified_post(data):
    """Classify the type of Instagram interaction"""
    # Skip message edits and reads
    if "messaging" in data:
        if "message_edit" in data["messaging"][0]:
            # print("[LOG] Message edit → SKIP")
            return "ok"
        if "read" in data["messaging"][0]:
            # print("[LOG] Read receipt → SKIP")
            return "ok"
        if data["messaging"][0]["sender"]["id"] == data["id"]:
            # print("[LOG] Message from self → SKIP")
            return "ok"
    # Handle comments
    elif "changes" in data and data["changes"][0]["field"] == "comments":
        print("[LOG] Detected COMMENT")
        if data["changes"][0]["value"]["from"]["id"] != data["id"]:
            return "comment"
        else:
            print("[LOG] Comment from self → SKIP")
            return "ok"

    print("\n=== [LOG] Masuk clasified_post ===")
    # Handle messaging events (DMs, story mentions, etc.)
    if "messaging" in data:
        print("[LOG] Detected messaging event")
        
        with open("cwdchat_config.json", "r", encoding="utf-8") as file:
            config = json.load(file)
        long_access_token = config.get("long_access_token")
        
        wait_next_reply = 5
        diff = time_diff(data, long_access_token, wait_next_reply)
        # print(f"[LOG] Time diff: {diff}s")

        if diff > wait_next_reply:
            print("[LOG] Diff > wait_next_reply, processing message...")
            dm = data["messaging"][0].get("message", data["messaging"][0])
        else:
            print("[LOG] Diff < wait_next_reply → WAITING\n")
            return "waiting"
        
        # Check for reply_to (story reply or DM reply)
        if "reply_to" in dm:
            print("[LOG] DM has reply_to")
            if "story" in dm["reply_to"]:
                print("[LOG] Detected reply_story")
                return "reply_story"
            else:
                print("[LOG] Detected dm_reply")
                return "dm_reply"
        
        # Check for attachments (story mention)
        elif "attachments" in dm:
            print("[LOG] DM has attachments")
            if dm["attachments"][0]["type"] == "story_mention":
                print("[LOG] Detected story_mention")
                return "story_mention"
        
        # Regular DM
        else:
            print("[LOG] Regular DM")
            return "dm"
    
    print("[LOG] Unknown type → SKIP\n")
    return "ok"


def complain_or_not(data, label, key, long_access_token):
    """Determine if message is a complaint or not"""
    # Skip certain events
    if "messaging" in data:
        if "message_edit" in data["messaging"][0]:
            return "ok", "ok"
        if data["messaging"][0]["sender"]["id"] == data["id"]:
            return "ok", "ok"
        if "read" in data["messaging"][0]:
            return "ok", "ok"
    
    if label == "ok" or label == "waiting":
        return "ok", "ok"
    print("\n=== [LOG] Masuk complain_or_not ===")
    print(f"[LOG] Label: {label}")
    
    # Get text based on label
    text = ""
    
    if label == "comment":
        text = data["changes"][0]["value"]["text"]
    
    elif label in ("reply_story", "dm_reply", "dm"):
        try:
            sender_id = data["messaging"][0]["sender"]["id"]
            user_id = data["id"]
            
            url = "https://graph.instagram.com/v24.0/me/conversations"
            payload = {
                "platform": "instagram",
                "fields": "messages{created_time,from,message}",
                "access_token": long_access_token,
                "user_id": sender_id
            }
            
            conv = requests.get(url, params=payload).json()
            chat = conv["data"][0]["messages"]["data"]
            
            # Check if last message is from us
            if chat[0]['from']['id'] == user_id:
                return "ok", "ok"
            
            text = data["messaging"][0]["message"].get("text", "")
            
        except Exception as e:
            print(f"[ERROR] Error getting conversation: {e}")
            return "ok", "ok"
    
    elif label == "story_mention":
        text = "Terima kasih sudah mention kami"
    
    if not text:
        return "ok", "ok"
    
    print(f"[LOG] Text untuk klasifikasi: {text}")
    
    # Classify with Gemini
    try:
        client = genai.Client(api_key=key)
        prompt = f"""Berikut adalah sebuah teks: {text}. 
        Kamu adalah asisten layanan pelanggan. Tentukan apakah teks tersebut merupakan keluhan atau bukan. 
        Kategorikan sebagai 'complaint' jika teks menunjukkan ketidakpuasan, masalah, kesalahan, komplain, atau pengalaman negatif terhadap produk/layanan. 
        Kategorikan sebagai 'not_complaint' jika teks bersifat netral, bertanya, menyapa, memberikan informasi, atau memuji. 
        Jawab hanya dengan 'complaint' atau 'not_complaint'."""

        response = client.models.generate_content(
            model = "gemini-2.5-flash", contents=prompt
        )

        answer = response.text.strip().lower()
        print(f"[LOG] Classification result: {answer}")

        return text, answer
        
    except Exception as e:
        print(f"[ERROR] Error in classification: {e}")
        return text, "not_complaint"


def dm(data, key, long_access_token):
    """Handle DM responses"""
    print("\n=== [LOG] Masuk dm ===")
    
    try:
        sender_id = data["messaging"][0]["sender"]["id"]
        user_id = data["id"]

        if sender_id == user_id:
            print("[LOG] Message from self → SKIP")
            return "ok"

        print("[LOG] Getting conversation for DM...")
        url = "https://graph.instagram.com/v24.0/me/conversations"
        payload = {
            "platform": "instagram",
            "fields": "messages{created_time,from,message}",
            "access_token": long_access_token,
            "user_id": sender_id
        }

        conv = requests.get(url, params=payload).json()
        chat = conv["data"][0]["messages"]["data"]
        
        # Check if last message is from us
        if chat[0]['from']['id'] == user_id:
            print("[LOG] Last message from us → SKIP")
            return "ok"

        # Build conversation context
        a = len(chat) - 1
        text = ""

        while a >= 0:
            sender = chat[a]['from']['username']
            message = chat[a].get('message', '')

            # Combine consecutive messages from same sender
            b = a - 1
            while b >= 0 and chat[b]['from']['username'] == sender:
                message += " / " + chat[b].get('message', '')
                b -= 1

            text += f"{sender}: {message}\n"
            a = b

        prompt = f'''Terdapat percakapan seperti ini:
        {text}

        Balas chat terakhir dari {sender} dengan ramah. 
        Awali dengan menyapa dan bilang "Hi, saya Jokowi" (gunakan nama Jokowi, bukan "aku" atau "saya").
        Jika sebelumnya sudah ada sapaan, tidak perlu sapa lagi.
        Buat balasan singkat, maksimal 1-2 kalimat.
        Jika tidak jelas, tanyakan klarifikasi. Jika paham, jawab dengan jelas.
        Di akhir kalimat tambahkan salah satu dari: "HIDUP JOKOWI" atau "ANTEK ANTEK ASENG" atau "FUFUFAFA ANAK MULYONO" atau "IJAZAH PALSU KOK JADI PRESIDEN" atau "KANGEN PRABOWO"
        Jika ditanya tentang kata-kata tersebut, jawab dengan ngeyel bahwa itu adalah kebebasan sebagai SPG.'''

        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model = "gemini-2.5-flash", contents=prompt
        )

        jawaban = response.text
        print(f"[LOG] Jawaban Gemini DM: {jawaban}")

        # Send DM
        url = "https://graph.instagram.com/v24.0/me/messages"
        headers = {
            "Authorization": f"Bearer {long_access_token}",
            "Content-Type": "application/json"
        }

        json_body = {
            "recipient": {"id": sender_id},
            "message": {"text": jawaban}
        }

        send = requests.post(url, headers=headers, json=json_body)
        # print(f"[LOG] DM sent: {send.status_code}\n")
        
    except Exception as e:
        print(f"[ERROR] Error in dm function: {e}")


def auto_response(data, label, answer, key, long_access_token):
    # """Route to appropriate response handler"""
    # print("\n=== [LOG] Masuk auto_response ===")
    # print(f"[LOG] Label: {label}, Answer: {answer}")

    if label == "ok" or label == "waiting":
        # print("[LOG] Skipping response")
        return

    if answer == "not_complaint":
        # print("[LOG] Not a complaint, routing to handler...")

        if label == "comment":
            print("[LOG] Calling comment()")
            comment(data, key, long_access_token)

        elif label in ("reply_story", "dm_reply", "dm"):
            print(f"[LOG] DM handler type: {label}")

            if label == "reply_story":
                reply_story()
            elif label == "dm_reply":
                dm_reply()

            dm(data, key, long_access_token)

        elif label == "story_mention":
            print("[LOG] Calling story_mention()")
            story_mention(data, long_access_token)

    else:  # complaint
        if label == "comment":
            # print("[LOG] Complaint in comment, still replying via comment()")
            comment(data, key, long_access_token)
        else:
            # print("[LOG] Complaint detected → calling complaint()")
            complaint(data, long_access_token)

    print("[LOG] auto_response completed\n")


def complaint(data, long_access_token):
    """Handle complaint messages"""
    print("\n=== [LOG] Masuk complaint ===")
    
    try:
        sender_id = data["messaging"][0]["sender"]["id"]
        user_id = data['id']
        
        if sender_id == user_id:
            print("[LOG] Complaint from self → SKIP")
            return "ok"

        jawaban = "Mohon maaf atas ketidaknyamanannya. Untuk penanganan lebih lanjut, silakan hubungi CEO kami, yaitu Irfan Risqy Trianto."
        
        url = "https://graph.instagram.com/v24.0/me/messages"
        headers = {
            "Authorization": f"Bearer {long_access_token}",
            "Content-Type": "application/json"
        }
        json_body = {
            "recipient": {"id": sender_id},
            "message": {"text": jawaban}
        }
        
        response = requests.post(url, headers=headers, json=json_body)
        print(f"[LOG] Complaint response sent: {response.status_code}")
        
    except Exception as e:
        print(f"[ERROR] Error in complaint: {e}")