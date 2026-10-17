"""Arayüz metinleri: Türkçe / English."""
import ctypes

METIN = {
    "tr": {
        "baslik": "Tuş Yansıt: iki bilgisayar arası W A S D + Shift + Ctrl + fare",
        "dil": "Dil / Language:",
        "rol": "Bu bilgisayar:",
        "gonderen": "Gönderen (tuşlara burada basıyorum)",
        "alan": "Alan (tuşlar burada da basılsın)",
        "kod": "Eşleştirme kodu:",
        "yeni_kod": "Yeni kod",
        "kod_aciklama": "Bu kodu gönderen bilgisayara yazın. Kodu bilmeyen hiçbir cihaz tuş basamaz.",
        "adres": "Bu bilgisayarın adresi: {adres}",
        "uygula": "Gelen tuşları uygula",
        "bekleniyor": "Gönderen bekleniyor…",
        "baglandi": "Bağlı: {ip}",
        "koptu": "Gönderenden paket gelmiyor: basılı tuşların hepsi bırakıldı",
        "sayac": "Kabul edilen paket: {kabul} · reddedilen: {red}",
        "hedef_kod": "Alanın kodu:",
        "hedef_ip": "Alanın adresi:",
        "ip_bos": "boş bırakırsan ağda aranır",
        "bul": "Bul ve bağlan",
        "araniyor": "Aranıyor…",
        "bulunamadi": "Bulunamadı. Kod doğru mu, alan program açık mı? Alanın adresini elle de yazabilirsin.",
        "bulundu": "Bulundu: {ad} ({ip})",
        "ac_kapa": "Aç / kapa tuşu:",
        "tus_degistir": "{tus}  (değiştirmek için tıkla)",
        "tus_bekle": "F1–F12 ya da Scroll Lock'a bas…",
        "fare": "Fareyi de gönder (hareket, tıklar, tekerlek)",
        "yansitma_acik": "YANSITMA AÇIK",
        "yansitma_kapali": "YANSITMA KAPALI",
        "acik_aciklama": "{tus} ile kapat",
        "kapali_aciklama": "{tus} ile aç",
        "alan_yanit": "Alan cevap veriyor",
        "alan_yanit_yok": "Alandan cevap yok (kod, adres ya da güvenlik duvarı?)",
        "alan_kapali": "Alanda \"gelen tuşları uygula\" kapalı",
        "gosterge_gonderen": "● YANSITMA AÇIK ({tus})",
        "gosterge_alan": "● UZAKTAN GİRDİ",
        "yonetici": "Öndeki pencere yönetici olarak çalışıyor: tuşlar ona basılamaz. Programı da yönetici "
                    "olarak açın (BASLAT.bat → sağ tık → Yönetici olarak çalıştır).",
        "port_dolu": "Port {port} kullanımda: program iki kez mi açık?",
        "yansitilan": "Yansıtılan: W A S D · Shift · Ctrl{fare}. Diğer tuşlar bu bilgisayardan çıkmaz.",
        "fare_ek": " · fare",
    },
    "en": {
        "baslik": "Key Mirror: W A S D + Shift + Ctrl + mouse between two PCs",
        "dil": "Dil / Language:",
        "rol": "This PC is the:",
        "gonderen": "Sender (I press the keys here)",
        "alan": "Receiver (press them here too)",
        "kod": "Pairing code:",
        "yeni_kod": "New code",
        "kod_aciklama": "Type this code on the sending PC. No device without the code can press keys.",
        "adres": "This PC's address: {adres}",
        "uygula": "Apply incoming keys",
        "bekleniyor": "Waiting for the sender…",
        "baglandi": "Connected: {ip}",
        "koptu": "No packets from the sender: all held keys were released",
        "sayac": "Packets accepted: {kabul} · rejected: {red}",
        "hedef_kod": "Receiver's code:",
        "hedef_ip": "Receiver's address:",
        "ip_bos": "leave empty to search the network",
        "bul": "Find and connect",
        "araniyor": "Searching…",
        "bulunamadi": "Not found. Is the code right and the receiver running? You can also type its address.",
        "bulundu": "Found: {ad} ({ip})",
        "ac_kapa": "On / off key:",
        "tus_degistir": "{tus}  (click to change)",
        "tus_bekle": "Press F1–F12 or Scroll Lock…",
        "fare": "Also send the mouse (movement, clicks, wheel)",
        "yansitma_acik": "MIRRORING ON",
        "yansitma_kapali": "MIRRORING OFF",
        "acik_aciklama": "press {tus} to turn off",
        "kapali_aciklama": "press {tus} to turn on",
        "alan_yanit": "Receiver is answering",
        "alan_yanit_yok": "No answer from the receiver (code, address or firewall?)",
        "alan_kapali": "\"Apply incoming keys\" is off on the receiver",
        "gosterge_gonderen": "● MIRRORING ON ({tus})",
        "gosterge_alan": "● REMOTE INPUT",
        "yonetici": "The window in front runs as administrator: keys can't be pressed into it. Run this app as "
                    "administrator too (BASLAT.bat → right-click → Run as administrator).",
        "port_dolu": "Port {port} is in use: is the app open twice?",
        "yansitilan": "Mirrored: W A S D · Shift · Ctrl{fare}. Other keys never leave this PC.",
        "fare_ek": " · mouse",
    },
}
DIL_ADLARI = {"tr": "Türkçe", "en": "English"}


def varsayilan_dil() -> str:
    try:
        return "tr" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x1F else "en"
    except Exception:  # noqa: BLE001
        return "en"


def t(dil: str, anahtar: str, **kw) -> str:
    metin = METIN.get(dil, METIN["en"]).get(anahtar) or METIN["en"][anahtar]
    return metin.format(**kw) if kw else metin
