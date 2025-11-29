from google import genai
# in here we clasified waht kind of post do we recieved is it a comment, dm, a reply story or dm reply, and a story mention. theres should be 5 label
# gimana cara dapet message yang, dia melihat dari reply story, dan reply apa nya gaada, terus gabisa liat reaction
import time
import requests
from datetime import datetime, timezone
from google import genai
import requests
import json

def time_diff(data, long_access_token, wait_second=10):
    sender_id = data["messaging"][0]["sender"]["id"]
    url = "https://graph.instagram.com/v24.0/me/conversations"
    payload = {
        "platform": "instagram",
        "fields": "messages{created_time,from,message,reactions,shares,attachment,reply,story,reply_to}",
        "access_token": long_access_token,
        "user_id": sender_id
    }
    time.sleep(wait_second)
    second = requests.get(url, params=payload).json()
    latest_msg = second["data"][0]["messages"]["data"][0]

    chat_time = latest_msg["created_time"]
    then = datetime.strptime(chat_time, "%Y-%m-%dT%H:%M:%S%z")
    now = datetime.now(timezone.utc)

    diff = (now - then).total_seconds()
    print(f"ini dari diff, waktu pesan terakhir: {diff}s")

    return diff

# in here we clasified waht kind of post do we recieved is it a comment, dm, a reply story or dm reply, and a story mention. theres should be 5 label
def clasified_post(data): # 1
    if "messaging" in data:
        with open("cwdchat_config.json", "r", encoding="utf-8") as file:
            config = json.load(file)
        long_access_token = config.get("long_access_token")
        #disini ambill conversation
        wait_next_reply = 60
        diff = time_diff(data,long_access_token,wait_next_reply)
        if int(diff) > wait_next_reply:
            if "message" in data["messaging"][0]: 
                dm = data["messaging"][0]["message"]
            elif "message" not in data["messaging"][0]:
                dm = data["messaging"][0]
        else: 
            return "waiting"
    else:
        pass
    if "changes" in data and data["changes"][0]["field"] == "comments":
        label = "comment"
    elif "reply_to" in dm :
        if "story" in dm["reply_to"]:
            label = "reply_story"
        else:
            label = "dm_reply"
    elif "attachments" in dm:
        if dm["attachments"][0]["type"] == "story_mention":
            label = "story_mention"
    elif "message_edit" in dm:
        label = "this_is_nothing"
    else:
        label = "dm"
    print(f"ini dari label : {label}")
    return label

#in here we should clasified if its should be a complain or not using machine learning, but for now lets use gemini:
def complain_or_not(data, label, key="AIzaSyA63Ye0096HIpdhZnSisQsmuWJGTiC0tgM"): # 2
    if label == "comment":
        text = data["changes"][0]["value"]["text"]
    elif label in ("reply_story","dm_reply", "dm"):
        dm = data["messaging"][0]["message"]
        text = dm["text"]
    elif label == "story_mention":
        text = "Terima kasih sudah mention kami di IG Story Anda 😊 Jika ada informasi tambahan atau kendala, silakan chat di sini ya!"
    elif label == "this_is_nothing":
        text = "this_is_nothing"
    elif label == "waiting":
        text = "netral"
        answer = "not_complaint"
        return text, answer
    # disini seharusnya pake ml buat nentuin di complaint atau bukan
    client = genai.Client(api_key=key)
    prompt = f"ada teks sebagai beriku {text} Kamu adalah asisten layanan pelanggan. Tentukan apakah kalimat tersebut termasuk keluhan (complaint) atau bukan keluhan. Jawab ('complaint') jika kalimat menunjukkan ketidakpuasan, masalah, kesalahan, atau pengalaman negatif terhadap produk atau layanan. Jawab 'not_complaint' jika kalimatnya netral, sekadar bertanya, menyapa, atau memuji."
    response = client.models.generate_content(
    model="gemini-2.5-flash", contents= prompt
    )
    answer = response.text
    print(f"ini dari comlpaint or not")
    return text, answer

def complaint(data, long_access_token): # 3.2.1
    # disini bisa bikin prompt untuk menghubunghi ig admin untuk memberi pemberitahuan 
    # jika ada yang melakukan complaint dan sekalian 
    # berikan informasi terkaitnya, seperti url nya
    senderid = data["messaging"][0]["sender"]["id"] # ini ngambil dari sender id dari webhooknya
    userid = data['id']
    if senderid != userid:
        jawaban = "kok complain, yauudah bisa hubungin CEO kami, yaitu Irfan Risqy Trianto"
        my_id = "1183164537081901"  # IG User ID pemilik token
        url = "https://graph.instagram.com/v24.0/me/messages"
        headers = {
            "Authorization": f"Bearer {long_access_token}",
            "Content-Type": "application/json"
        }
        json_body = {
            "recipient": {"id": senderid},
            "message": {"text": jawaban}
        }
        response = requests.post(url, headers=headers, json=json_body)
        print(f"ini dari complaint")
        # print(response.status_code, response.text)
    else:
        return

def comment(data,key,long_access_token): # 3.1.1
    # --- Ambil data dasar dari webhook ---
    comment = data["changes"][0]["value"]["text"]
    comment_id = data["changes"][0]["value"]["id"]
    media_id = data["changes"][0]["value"]["media"]["id"]
    username = data["changes"][0]["value"]["from"]["username"]

    # --- Ambil data postingan (caption & username pembuat postingan) ---
    url =  f"https://graph.instagram.com/{media_id}"
    fields = {'id,caption,media_type,media_url,permalink,timestamp,username'}
    payload = {
        "fields": fields,
        "access_token": long_access_token
    }

    response = requests.get(url, params=payload)
    post = response.json()

    caption = post.get("caption", "")
    user = post.get("username", "")

    # --- Hanya balas jika komentator bukan pemilik postingan ---
    if user != username:
        # Buat prompt untuk model AI
        prompt = f'''
        Terdapat caption postingan: ({caption}). 
        @{username} memberikan komentar: ({comment}). 

        Buat balasan singkat dan ramah seperti admin atau SPG toko yang sopan dan antusias. 
        Jika komentarnya berupa pertanyaan, mulai dengan memuji pertanyaannya lalu jawab singkat. 
        Jika komentarnya bukan pertanyaan, cukup ucapkan terima kasih dengan nada positif dan bersahabat. 
        Jika isi komentar menunjukkan keluhan, arahkan dengan sopan agar pengguna memeriksa DM. 

        Gunakan bahasa sehari-hari yang natural (tidak kaku, tidak alay, tanpa tanda *), cukup satu kalimat saja. 
        Awali balasan dengan menyapa dan bilang, kalo saya adalah Jokowi, dan jangan gunakan aku atau saya tapi sebut nama Jokowi
        Jangan ajak untuk cek postingan lain atau promosi tambahan.
        '''

        # Generate jawaban dengan Gemini
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents= prompt
        )
        jawaban = response.text

        # Kirim balasan komentar
        reply_url = f"https://graph.instagram.com/v24.0/{comment_id}/replies"
        payload = {
            "message" : jawaban, 
            "access_token" : long_access_token
        }
        response = requests.post(reply_url, params = payload)
        print("comment has been replied")
        print(f"ini dari comment")
    else:
        return

def reply_story():
    print("story reply has been replied")

def dm_reply():
    print("dm reply has been replied")

def dm(data, key, long_access_token):
    #gimana cara dapet message yang, dia melihat dari reply story, dan reply apa nya gaada, terus gabisa liat reaction
    senderid = data["messaging"][0]["sender"]["id"] # ini ngambil dari sender id dari webhooknya
    userid = data['id']
    # print(senderid)
    # print(userid)
    if senderid != userid:
        url = f"https://graph.instagram.com/v24.0/me/conversations"
        payload = {
            "platform" : "instagram",
            "fields" : "messages{created_time,from,message,reactions,shares,attachment,reply,story}",
            "access_token" : long_access_token
            ,"user_id" : senderid
        }
        conv = requests.get(url, params=payload).json()

        chat = conv["data"][0]['messages']["data"]

        a = len(chat) - 1  # mulai dari bawah, hanya bisamengambil 26 bubble chat terakhir
        text = ""
        while a >= 0:
            sender = chat[a]['from']['username']
            message = chat[a]['message']

            # gabungkan pesan dengan pesan berikutnya jika sender sama
            b = a - 1
            while b >= 0 and chat[b]['from']['username'] == sender:
                message += " / " + chat[b]['message'] 
                b -= 1
            text += f"{sender}: {message}" + "\n" + "<next bubble chat> "
            # lompat ke index terakhir yang belum diproses
            a = b
        # print(sender)
        # print(text)
        prompt = f'''
        terdapat percakapan seperti ini:
        {text}
        bales chat terakhir dari username {sender} berikan output jawabannya saja, 
        balas dengan ramah, awali menyapa biasa, lalu bilang hi saya Jokowi, jangan pake aku atau saya tapi pake nama yaitu Jokowi, kalau sebelumnya sudah ada sapaan, gausah lakukan lagi
        dan jangan terlalu panjang, bikin singkat aja, kaya dalam satu kalimat kalau bisa 
        kalo ga jelas tanyakan kenapa, kalo paham jawab, 
        di akhir kalimat berikan kata "HIDUP JOKOWI" atau "ANTEK ANTEK ASENG" atau "FUFUFAFA ANAK MULYONO" atau "IJAZAH PALSU KOK JADI PRESIDEN" atau "KANGEN PRABOWO"
        kalo dia nanya kenapa ada kata "HIDUP JOKOWI" atau "ANTEK ANTEK ASENG" atau "FUFUFAFA ANAK MULYONO" atau "IJAZAH PALSU KOK JADI PRESIDEN" atau "KANGEN PRABOWO", blaesnya ngeyel, seakan itu kebebasan sebagai SPG
        '''
        # Generate jawaban dengan Gemini
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents= prompt
        )
        jawaban = response.text
        # print(jawaban)
        url = "https://graph.instagram.com/v24.0/me/messages"
        headers = {
            "Authorization": f"Bearer {long_access_token}",
            "Content-Type": "application/json"
        }
        json_body = {
            "recipient": {"id": senderid },  # ID penerima (harus dari conversation sebelumnya)
            "message": {"text": f"{jawaban}"}
        }
        response = requests.post(url, headers=headers, json=json_body)
        # print(f"ini dari dm : {response}")
    else :
        pass

    print("dm has been replied")

def story_mention(data,long_access_token):
    messaging = data["messaging"][0]
    mid = messaging["message"]["mid"]
    recipient_id = messaging["sender"]["id"]
    
    # Balas DM
    text = "Terima kasih sudah mention kami di IG Story Anda 😊 Jika ada informasi tambahan atau kendala, silakan chat di sini ya!"

    message_url = "https://graph.instagram.com/v24.0/me/messages"
    headers = {
        "Authorization": f"Bearer {long_access_token}",
        "Content-Type": "application/json"
    }
    json_body = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": text  
        }
    }

    send_message  =requests.post(message_url, headers=headers, json=json_body)

    # React love
    react_url = f"https://graph.instagram.com/v24.0/me/messages?access_token={long_access_token}"
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": "react",
        "payload": {
            "message_id": mid,
            "reaction": "love"
        }
    }
    send_reaction = requests.post(react_url, json=payload)
    print("story mention has been replied")

def auto_response(data,label,answer,key="AIzaSyA63Ye0096HIpdhZnSisQsmuWJGTiC0tgM"): # 3
    # Baca file konfigurasi
    with open("cwdchat_config.json", "r", encoding="utf-8") as file:
        config = json.load(file)
    long_access_token = config.get("long_access_token")
    if answer == "not_complaint": # 3.1
        if label == "comment":
            comment(data,key,long_access_token) # 3.1.1
        elif label in ("reply_story","dm_reply", "dm"):
            if label == "reply_story":
                reply_story() 
                dm(data, key, long_access_token)
            elif label == "dm_reply":
                dm_reply()
                dm(data, key, long_access_token)
            elif label == "dm":
                dm(data, key,long_access_token)
        elif label == "story_mention":
            story_mention(data, long_access_token)
        elif label == "waiting":
            print("Waiting… diff < 15s, no response sent.")
            return
    else:
        complaint(data, long_access_token) # 3.2