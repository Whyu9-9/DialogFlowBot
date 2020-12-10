from fuzzywuzzy import process
import json
import requests
import time
import urllib
import string
import spell
import mysql.connector
import numpy as np
import functools
import operator

#konektor database
db = mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="Dragoncit1234",
            db="universitas",
            auth_plugin="mysql_native_password")

#token dari bot setelah daftar di @botfather
TOKEN = "1454394622:AAELC6UkG7DmqQslnGBl9AjYDO1vIuyBoX8"
#url dari bot
URL = "https://api.telegram.org/bot{}/".format(TOKEN)


#fungsi untuk mendapatkan url lalu ditaruh di variabel content
def get_url(url):
    response = requests.get(url)
    content = response.content.decode("utf8")
    return content

#fungsi untuk mendapatkan file json dari url lalu ditaruh di variabel js
def get_json_from_url(url):
    content = get_url(url)
    js = json.loads(content)
    return js


#fungsi untuk mendapatkan chat id dan text terbaru lalu ditaruh di variabel text dan chat_id
def get_last_chat_id_and_text(updates):
    num_updates = len(updates["result"])
    last_update = num_updates - 1
    text = updates["result"][last_update]["message"]["text"]
    chat_id = updates["result"][last_update]["message"]["chat"]["id"]
    return (text, chat_id)


#fungsi untuk mendapatkan update json
def get_updates(offset=None):
    url = URL + "getUpdates?timeout=100"
    if offset:
        url += "&offset={}".format(offset)
    js = get_json_from_url(url)
    return js

#fungsi untuk mendapatkan id update terbaru
def get_last_update_id(updates):
    update_ids = []
    for update in updates["result"]:
        update_ids.append(int(update["update_id"]))
    return max(update_ids)

#fungsi untuk mengirim pesan, data pesan akan di parse ke url
def send_message(text, chat_id):
    text = urllib.parse.quote_plus(text)
    url = URL + "sendMessage?text={}&chat_id={}".format(text, chat_id)
    get_url(url)

#fungsi untuk mengambil data dari database lalu dikirim ke fungsi send_message
#untuk selanjutnya nnti bakal dikirim ke user
def ngerjain_sendiri(updates):
    for update in updates["result"]:
        try:
            text = update["message"]["text"]
            #clean1 memproses text agar tidak berisi tanda baca
            clean1 = text.translate(str.maketrans("","",string.punctuation))

            #clean2 merupakan proses tokenizing text
            clean2 = clean1.split()
            strOptions = clean2

            #disini diselect semua keyword yang ada di database
            cari = "select keyword from tb_keyword"
            cursor = db.cursor()
            cursor.execute(cari)
            record = cursor.fetchall()

            #lalu disimpan di sebuah array
            arr = []
            arr.append(record)
            carinya = ''.join([str(i) for i in arr])

            #disini lah proses pembandingan rasio kesamaan input user dengan yang ada di database
            #menggunakan library fuzzywuzzy yang menerapkan levensthein distance
            #string dengan persentasi matching tertinggi dipilih dan dijadikan patokan proses selanjutnya
            highest = process.extractOne(carinya, strOptions)

            chat = update["message"]["chat"]["id"]
            a = spell.correction(highest[0])

            cursor = db.cursor()
            cursor.execute("insert into tb_inbox(input_user,flag) values (%s,%s) ", (text, '1'))
            db.commit()
            cursor.close()

            if(text=="/start"):
                op = "Halo! Selamat datang di Botnya Wahyu! Silahkan bertanya seputar hari libur nasional di Indonesia pada tahun 2020 (Contoh: Hari Raya Nyepi, Tahun Baru Masehi, dll)"
                send_message(op, chat)
            else:
                #kondisi if ketika rasio kecocokan lebih dari 40%
                #maka akan diselect di database mana respon yang tepat
                if (highest[1] >= 40):
                    cursor = db.cursor()
                    cursor.execute("select id from tb_keyword where keyword like %s limit 1", ("%" + a + "%",))
                    record2 = cursor.fetchall()
                    cursor.close()
                    for x in record2:
                        ids = ''.join(str(x))

                    array = []
                    array.append(ids)
                    id = ids.translate(str.maketrans("", "", string.punctuation))

                    cursor = db.cursor()
                    cursor.execute("select date_result from tb_result where id_keyword like %s limit 1", ("%" + id + "%",))
                    record3 = cursor.fetchone()
                    cursor.close()

                    cursor = db.cursor()
                    cursor.execute("select text_result from tb_result where id_keyword like %s limit 1", ("%" + id + "%",))
                    record4 = cursor.fetchone()
                    cursor.close()

                    #proses spelling correction
                    arr_mess = np.array(strOptions)
                    conv = []
                    for x in arr_mess:
                        arr_mess = spell.correction(x)
                        conv.append(arr_mess)
                        result = ' '.join([str(i) for i in conv])

                    #disini respon dari bot akan dikirim ke user
                    message = "%s %s" % (record4[0],record3[0])
                    send_message(message, chat)

                    cursor = db.cursor()
                    cursor.execute("select id from tb_inbox order by id desc limit 1")
                    foreign = cursor.fetchone()
                    cursor.close()

                    cursor = db.cursor()
                    cursor.execute("insert into tb_outbox(id_inbox,output_bot,flag) values (%s,%s,%s) ", (str(foreign[0]),message,'1'))
                    db.commit()
                    cursor.close()

                    #print keterangan
                    print("Input dari USER:", text)
                    print("Cleansing Input dari USER:", clean1)
                    print("Tokenizing Input dari USER:", strOptions)
                    print("Koreksi:",result)
                    print("Ekstraksi Keyword:",a)
                    print("Bot Message:",message)
                    print("ID Keyword:", id)
                    print("\n")
                else:
                    salah = "Maaf Bot Tidak Mengerti :/"

                    cursor = db.cursor()
                    cursor.execute("select id from tb_inbox order by id desc limit 1")
                    foreign2 = cursor.fetchone()
                    cursor.close()

                    cursor = db.cursor()
                    cursor.execute("insert into tb_outbox(id_inbox,output_bot,flag) values (%s,%s,%s) ", (str(foreign2[0]),"tidak dimengerti", '1'))
                    db.commit()
                    cursor.close()

                    send_message(salah, chat)
                    print(salah)
                    print("Input dari USER:", text)
                    print("\n")
        except Exception as e:
            print(e)

#fungsi main yang digunakan untuk looping tidak terbatas dengan while true
#fungsi main disini memanggil fungsi ngerjain_sendiri dan looping koneksi ke database
def main():
    last_update_id = None
    while True:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="Dragoncit1234",
            db="universitas",
            auth_plugin="mysql_native_password")
        updates = get_updates(last_update_id)
        if len(updates["result"]) > 0:
            last_update_id = get_last_update_id(updates) + 1
            ngerjain_sendiri(updates)
        db.close()
        time.sleep(0.5)

#fungsi yang memanggil fungsi main
if __name__ == '__main__':
    main()