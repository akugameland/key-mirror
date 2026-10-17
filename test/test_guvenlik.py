"""Protokol ve güvenlik testleri. Gerçek tuş basılmaz (sahte basıcı).
python -X utf8 test/test_guvenlik.py"""
import socket
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ag  # noqa: E402
import girdi  # noqa: E402

PORT = 47899


class SahteBasici(girdi.Basici):
    """Gerçek SendInput yerine yapılanları listeye yazar; beyaz liste ve izleme mantığı aynı."""

    def __init__(self):
        super().__init__()
        self.olaylar = []
        girdi_gonder = girdi._gonder
        girdi._gonder = lambda *g: self.olaylar.append(g) or True          # noqa: E731
        self._eski = girdi_gonder


hatalar = []


def kontrol(ad, kosul):
    print(("OK   " if kosul else "HATA ") + ad)
    if not kosul:
        hatalar.append(ad)


def bekle(kosul, sure=1.0):
    son = time.time() + sure
    while time.time() < son:
        if kosul():
            return True
        time.sleep(0.02)
    return kosul()


kod = ag.yeni_kod()
kontrol("kod 10 karakter ve geçerli", len(kod) == 10 and ag.kod_gecerli(kod) and ag.kod_gecerli(ag.kod_goster(kod)))
kontrol("karışan harf yok", not set(kod) & set("01OIL"))
p = ag.Paketci(kod)
paket = p.paketle(ag.TUS, b"o" * 8, b"n" * 8, 5, bytes([0x11, 0, 1]))
kontrol("paket çözülür", p.coz(paket) == (ag.TUS, b"o" * 8, b"n" * 8, 5, bytes([0x11, 0, 1])))
kontrol("içerik şifreli (düz metin pakette yok)", bytes([0x11, 0, 1]) not in paket[-3 - ag.IMZA - 2:])
kontrol("yanlış kod reddedilir", ag.Paketci(ag.yeni_kod()).coz(paket) is None)
bozuk = bytearray(paket); bozuk[-20] ^= 1
kontrol("değiştirilmiş paket reddedilir", p.coz(bytes(bozuk)) is None)
kontrol("çok uzun paket reddedilir", p.coz(paket + bytes(600)) is None)
kontrol("özel adres kontrolü", ag.ozel_adres_mi("192.168.1.5") and ag.ozel_adres_mi("10.0.0.2")
        and not ag.ozel_adres_mi("8.8.8.8") and not ag.ozel_adres_mi("1.1.1.1"))

basici = SahteBasici()
alici = ag.Alici(kod, basici, "test", port=PORT)
g = ag.Gonderici(kod)
g.hedef = ("127.0.0.1", PORT)

# 1) nonce'u bilmeden gönderilen tuş uygulanmaz; nabız nonce'u öğretir
g.tus(0x11, False, True)
time.sleep(0.2)
kontrol("nonce öğrenilmeden tuş basılmaz", not basici.basili_tuslar)
g.nabiz(False, set(), set())
kontrol("nabız cevabıyla nonce öğrenilir", bekle(lambda: g.nonce == alici.nonce))
# 2) normal akış
g.nabiz(True, set(), set())
g.tus(0x11, False, True)
kontrol("W basıldı", bekle(lambda: (0x11, False) in basici.basili_tuslar))
g.tus(0x11, False, False)
kontrol("W bırakıldı", bekle(lambda: not basici.basili_tuslar))
# 3) beyaz liste: Enter (0x1C) ve Windows tuşu gönderilse bile basılmaz
g.tus(0x1C, False, True)
g.tus(0x5B, True, True)
time.sleep(0.2)
kontrol("izin verilmeyen tuşlar basılmaz", not basici.basili_tuslar)
# 4) tekrar gönderme: aynı paket ikinci kez uygulanmaz
g.sira += 1
eski = g.paketci.paketle(ag.TUS, g.oturum, g.nonce, g.sira, bytes([0x1E, 0, 1]))
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(eski, ("127.0.0.1", PORT))
kontrol("A basıldı", bekle(lambda: (0x1E, False) in basici.basili_tuslar))
basici.hepsini_birak()
s.sendto(eski, ("127.0.0.1", PORT))
time.sleep(0.2)
kontrol("tekrar gönderilen eski paket uygulanmaz", not basici.basili_tuslar)
# 5) önceki çalışmadan kaydedilmiş paket (eski nonce) uygulanmaz
eski_calisma = g.paketci.paketle(ag.TUS, g.oturum, b"x" * 8, g.sira + 50, bytes([0x1F, 0, 1]))
s.sendto(eski_calisma, ("127.0.0.1", PORT))
time.sleep(0.2)
kontrol("eski çalışmanın paketi uygulanmaz", not basici.basili_tuslar)
# 6) internet adresinden gelen paket: doğrudan işleyiciyle dene
g.sira += 1
dis = g.paketci.paketle(ag.TUS, g.oturum, g.nonce, g.sira, bytes([0x20, 0, 1]))
alici._isle(dis, ("8.8.8.8", 5555))
kontrol("internetten gelen paket uygulanmaz", not basici.basili_tuslar)
# 7) ikinci gönderen: ilki bağlıyken reddedilir
g2 = ag.Gonderici(kod)
g2.hedef = ("127.0.0.1", PORT)
g2.nonce = alici.nonce
g2.tus(0x20, False, True)
time.sleep(0.2)
kontrol("ikinci gönderen araya giremez", not basici.basili_tuslar)
# 8) paket kaybı: nabız basılı listesiyle eşitler
g.nabiz(True, {(0x11, False), (0x2A, False)}, {0})
kontrol("nabızla eşitleme (W + Shift + sol tık)", bekle(
    lambda: basici.basili_tuslar == {(0x11, False), (0x2A, False)} and basici.basili_dugmeler == {0}))
g.nabiz(True, {(0x2A, False)}, set())
kontrol("nabızla bırakma (W ve tık bırakıldı)", bekle(
    lambda: basici.basili_tuslar == {(0x2A, False)} and not basici.basili_dugmeler))
# 9) bağlantı koparsa 1 sn içinde hepsi bırakılır
kontrol("koparsa hepsi bırakılır", bekle(lambda: not basici.basili_tuslar, 2.0))
# 10) yansıtma kapanınca (nabız acik=0) hepsi bırakılır
g.nabiz(True, {(0x11, False)}, set())
bekle(lambda: basici.basili_tuslar)
g.nabiz(False, set(), set())
kontrol("yansıtma kapanınca bırakılır", bekle(lambda: not basici.basili_tuslar))
# 11) alanda 'uygula' kapalıysa hiçbir şey basılmaz
alici.etkin = False
g.tus(0x11, False, True)
time.sleep(0.2)
kontrol("alanda uygulama kapalıyken basılmaz", not basici.basili_tuslar)
alici.etkin = True
# 12) fare: hareket, teker, düğme
n = len(basici.olaylar)
g.hareket(40, -15)
g.teker(-120, False)
g.dugme(3, True)
g.dugme(3, False)
kontrol("fare olayları uygulanır", bekle(lambda: len(basici.olaylar) >= n + 4))
mi = basici.olaylar[n][0].u.mi
kontrol("fare hareketi doğru (40, -15)", (mi.dx, mi.dy) == (40, -15))
# 13) bulma: yalnız aynı kodu bilen alan cevap verir
time.sleep(ag.TEK_GONDEREN_SN + 0.2)
yabanci = ag.Gonderici(ag.yeni_kod())
yabanci._kesif_nonce = b"k" * 8
yabanci._yolla(ag.KESIF, b"k" * 8, ("127.0.0.1", PORT))
time.sleep(0.3)
kontrol("yanlış kodla bulma cevapsız", not yabanci._bulunan)
dost = ag.Gonderici(kod)
dost._kesif_nonce = b"d" * 8
dost._yolla(ag.KESIF, b"d" * 8, ("127.0.0.1", PORT))
kontrol("doğru kodla bulma cevaplanır", bekle(lambda: "127.0.0.1" in dost._bulunan))
print(f"\nsayaç: {alici.sayac}")
alici.kapat()
print(f"{'HEPSİ GEÇTİ' if not hatalar else f'{len(hatalar)} HATA'}")
sys.exit(1 if hatalar else 0)
