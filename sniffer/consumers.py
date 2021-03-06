from channels.generic.websocket import WebsocketConsumer
from scapy.all import *
import json
import hashlib
import os
from packetstudio import settings as st

"""
Gönderilen Mesaj Tipleri:
- packet: Paketlerin gönderildiğini bildirir
- notify: Kaç paket sonra yenileneme yapılacağını bildirir
- filtre: Filtreleme ile ilgili bilgiler gönderir(onay ve temizleme)
- info  : İstenilen paket hakkında bilgi içerir

Gelen Mesaj Tipleri:
- set : Bir ayar içeren mesajdır
- info: Bir bilgi almak isteyen mesajdır(paket hakkında)

"""

class SniffConsumer(WebsocketConsumer):
    def connect(self):
        self.filter_list = []
        self.paketler = []
        self.pause = False

        self.allow = {
            "tcp":TCP,
            "arp":ARP,
            "udp":UDP,
            "icmp":ICMP,
            "dns":DNS,
        }
        self.sniffer = AsyncSniffer(prn=self.send_packet)
        self.sniffer.start()        
        self.buffer = []
        self.max_packet = 50
        self.accept()
        

    def send_packet(self,packet):
        if(self.pause):
            return

        
        if len(self.buffer) >= self.max_packet:
            # paketler gönderiliyor
            self.send(text_data=json.dumps({
                "type":"packet",
                "message":self.buffer
            }))

            self.buffer.clear()
            return

        elif len(self.filter_list):
            for i in self.filter_list:
                if i in packet:
                    self.buffer.append(packet.summary())
                    self.paketler.append(packet)
        else:
            self.buffer.append(packet.summary())
            self.paketler.append(packet)

        # Kalan paket bildirimi gönderiliyor
        self.send(text_data = json.dumps(
            {"type":"notify","info":"{} paket sonra yenilenecek".format(self.max_packet-len(self.buffer))}
        ))
    def disconnect(self, close_code):
        self.sniffer.stop()
        pass

    # mesaj alınırsa
    def receive(self, text_data):
        try:
            message = json.loads(text_data)
            _type = message['type']
            if(_type == "set"):
                # ayarlama işlemleri

                if(message["work"] == "clear"):
                    # Listenin temizlendiği bildirimi gönderiliyor
                    self.filter_list.clear()
                    self.send(text_data = json.dumps({"type":"filtre","info":"Filtre temizlendi"}))
                    return
                elif(message["work"] == "play"):
                    # Paket yakalayıcıyı duraklat/devam ettir
                    self.pause = not self.pause
                    self.send(text_data=json.dumps({
                        "type":"notify",
                        "info":"Paket yakalama {}".format("durduruldu" if self.pause else "devam ediyor")
                    }))
                elif("speed" in message["work"]):
                    try:
                        veri = int(message["work"].split(":")[1])
                        if(veri<=0):
                            raise Exception("ULAN")
                        self.max_packet = veri
                        self.send_packet(self.paketler[0])
                        self.send(text_data=json.dumps({
                            "type":"filtre",
                            "info":"Yenileme hızı: {}".format(self.max_packet)
                        }))
                    except Exception as e:
                        self.send(text_data=json.dumps({
                            "type":"filtre",
                            "info":"Hatalı bildirim"
                        }))      
                elif(message["work"] == "save"):
                    # kaydetme işlemi
                    result = self.sniffer.stop()
                    name = hashlib.md5(result[0].show(dump=True).encode("utf-8")).hexdigest()+".cap"
                    if(not os.path.exists(os.path.join(st.BASE_DIR,"sniffer","download"))):
                        os.mkdir(os.path.join(st.BASE_DIR,"sniffer","download"))
                    path = os.path.join(st.BASE_DIR,"sniffer","download",name)
                    wrpcap(path,result)
                    self.send(text_data=json.dumps(
                        {"type":"save",
                        "info":name}
                    ))
                else:
                    # Filtrenin uygulandığı mesajı gönderiliyor
                    f = message["work"].split(",")
                    for i in f:
                        if i.lower() not in self.allow:
                            return
                    
                    self.filter_list.clear()
                    m = ""
                    for i in f:
                        m += " "+i
                        self.filter_list.append(self.allow.get(i.lower()))

                    self.buffer.clear()
                    self.send(text_data = json.dumps(
                        {"type":"filtre",
                        "info":"Filtre eklendi: "+m}
                    ))

            elif(_type == "info"):
                # paket bilgi alma işlemleri
                self.send(text_data = json.dumps(
                    {"type":"info",
                    "message":self.paketler[message["index"]].show(dump=True)}
                ))
        except Exception as e:
            print(e)

    def sendWrap(self,data):
        self.send(text_data=json.dumps(
            data
        ))