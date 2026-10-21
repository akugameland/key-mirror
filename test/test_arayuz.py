"""Arayüz uçtan uca (tek bilgisayar, 127.0.0.1). Gerçek basılan tek tuş Shift'tir (zararsız).
python -X utf8 test/test_arayuz.py [ekran_goruntusu_klasoru]"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tus_yansit  # noqa: E402
import ag  # noqa: E402
import girdi  # noqa: E402

ag.PORT = 47897                                         # gerçek program açıksa onun portuna (47810) dokunma
GECICI = Path(tempfile.mkdtemp())
tus_yansit.AYAR_DOSYASI = GECICI / "ayarlar.json"      # kullanıcının ayarlarına dokunma
cikti = Path(sys.argv[1]) if len(sys.argv) > 1 else None
hatalar = []


def kontrol(ad, kosul):
    print(("OK   " if kosul else "HATA ") + ad)
    if not kosul:
        hatalar.append(ad)


def goruntu(app, ad):
    if not cikti:
        return
    from PIL import ImageGrab  # isteğe bağlı (yalnız görsel kontrol için)
    k = app.kok
    k.update()
    x, y = k.winfo_rootx(), k.winfo_rooty()
    ImageGrab.grab((x, y, x + k.winfo_width(), y + k.winfo_height()), all_screens=True).save(cikti / ad)


# ── 1) alan rolü ─────────────────────────────────────────────────────────────
tus_yansit.AYAR_DOSYASI.write_text('{"rol": "alan", "dil": "tr"}', encoding="utf-8")
app = tus_yansit.Uygulama()
app.kok.attributes("-topmost", True)
kod = app.ayar["kod"]
g = ag.Gonderici(kod)
g.hedefle("127.0.0.1")


def alan_adim():
    g.nabiz(True, set(), set())
    app.kok.after(400, alan_adim2)


def alan_adim2():
    g.nabiz(True, set(), set())
    g.tus(0x2A, False, True)
    app.kok.after(300, alan_adim3)


def alan_adim3():
    app._guncelle()
    kontrol("alan: gönderen bağlandı yazıyor", app.durum.cget("text").startswith("Bağlı"))
    kontrol("alan: UZAKTAN GİRDİ göstergesi açık", app.gosterge.metin == "● UZAKTAN GİRDİ")
    kontrol("alan: Shift gerçekten basıldı", (0x2A, False) in app.basici.basili_tuslar)
    goruntu(app, "alan.png")
    g.tus(0x2A, False, False)
    g.nabiz(False, set(), set())
    app.kok.after(400, alan_adim4)


def alan_adim4():
    app._guncelle()
    kontrol("alan: yansıtma kapanınca gösterge söner", app.gosterge.metin is None)
    kontrol("alan: Shift bırakıldı", not app.basici.basili_tuslar)
    kontrol("alan: sayaçta kabul var", app.alici.sayac["kabul"] >= 3)
    kontrol("alan: tuş listesinde varsayılan 8 tuş", app.tus_listesi.size() == 8)

    class SahteDinleyici:
        def kapat(self):
            pass
    app._ekleyici = SahteDinleyici()                   # "Tuş ekle"ye basılmış gibi: sonra E'ye basıldı
    app._tus_eklendi(0x12, False)
    kontrol("alan: E eklendi (liste, ayar, basıcı)", app.tus_listesi.size() == 9
            and [0x12, False] in app.ayar["izinli_tuslar"] and (0x12, False) in app.basici.izinli)
    app._ekleyici = SahteDinleyici()
    app._eklenen_f(0x3B)                               # F1: ayrılmış
    app.kok.update()
    kontrol("alan: F1 eklenmez", app.tus_listesi.size() == 9 and app._ekleyici is None)
    app._ekleyici = SahteDinleyici()
    app._tus_eklendi(0x01, False)                      # Esc: vazgeç
    kontrol("alan: Esc vazgeçer", app.tus_listesi.size() == 9)
    app.tus_listesi.selection_set(app._liste_sirasi.index((0x11, False)))
    app._tus_cikar()
    kontrol("alan: W çıkarıldı", app.tus_listesi.size() == 8 and (0x11, False) not in app.basici.izinli)
    kontrol("alan: fare kutuları varsayılanda hepsi açık", all(v.get() for v in app.fare_kutulari.values())
            and app.basici.fare_izni == girdi.FARE_HEPSI)
    app.fare_kutulari[1].set(False)                    # sağ tık kapalı
    app.fare_kutulari[girdi.FARE_TEKER].set(False)     # tekerlek (kaydırma) kapalı
    app._fare_izni_degisti()
    beklenen = girdi.FARE_HEPSI & ~(1 << 1) & ~(1 << girdi.FARE_TEKER)
    kontrol("alan: sağ tık ve tekerlek kapatıldı (ayar + basıcı)", app.ayar["fare_izni"] == beklenen
            and app.basici.fare_izni == beklenen)
    g.nabiz(True, set(), set())
    app.kok.after(400, alan_adim5)


def alan_adim5():
    kontrol("alan: gönderen yeni listeyi aldı (E var, W yok)", (0x12, False) in g.alan_tuslari
            and (0x11, False) not in g.alan_tuslari)
    kontrol("alan: gönderen fare iznini aldı (sağ tık ve tekerlek yok)", g.fare_izinli(0)
            and not g.fare_izinli(1) and not g.fare_izinli(girdi.FARE_TEKER) and g.fare_izinli(girdi.FARE_HAREKET))
    goruntu(app, "alan_liste.png")
    app._tus_varsayilan()
    kontrol("alan: varsayılana dönüldü", app.tus_listesi.size() == 8 and (0x12, False) not in app.basici.izinli)
    g.kapat()
    app.kapat()


app.kok.after(300, alan_adim)
app.calis()

# ── 2) gönderen rolü ─────────────────────────────────────────────────────────
olaylar = []


class SahteBasici(girdi.Basici):
    def tus(self, tarama, e0, basili):
        olaylar.append(("tus", tarama, basili))
        return super().tus(tarama, e0, basili) if False else True

    def hepsini_birak(self):
        olaylar.append(("birak",))

    def esitle(self, tuslar, dugmeler):
        olaylar.append(("esitle", frozenset(tuslar)))


kod2 = ag.yeni_kod()
alici = ag.Alici(kod2, SahteBasici(), "test-alan", port=ag.PORT)
tus_yansit.AYAR_DOSYASI.write_text(
    '{"rol": "gonderen", "dil": "en", "hedef_kod": "%s", "hedef_ip": "127.0.0.1"}' % kod2, encoding="utf-8")
app = tus_yansit.Uygulama()
app.kok.attributes("-topmost", True)


def gon_adim():
    app._guncelle()
    kontrol("gönderen: kapalı başlar", not app.acik and app.buyuk.cget("text") == "MIRRORING OFF")
    kontrol("gönderen: İngilizce arayüz", app.kok.title() == "Key Mirror")
    kontrol("gönderen: alan cevap veriyor", app.durum.cget("text") == "Receiver is answering")
    kontrol("gönderen: alanın listesi yazıyor", "chosen by the receiver" in app.yansitilan.cget("text")
            and "Left Shift" in app.yansitilan.cget("text") and "Right click" in app.yansitilan.cget("text")
            and "Wheel (scroll)" in app.yansitilan.cget("text"))
    app._tus(0x11, False, True)                       # kapalıyken basılan W gönderilmemeli
    app.kok.after(300, gon_adim2)


def gon_adim2():
    kontrol("gönderen: kapalıyken tuş gitmez", not any(o[0] == "tus" for o in olaylar))
    app._tus(0x11, False, False)
    app._f_tusu(0x41)                                 # F7: aç
    app._tus(0x1E, False, True)                       # A
    app.kok.after(300, gon_adim3)


def gon_adim3():
    app._guncelle()
    kontrol("gönderen: F7 ile açıldı + gösterge", app.acik and app.gosterge.metin == "● MIRRORING ON (F7)")
    kontrol("gönderen: açıkken A alana ulaştı", ("tus", 0x1E, True) in olaylar)
    goruntu(app, "gonderen.png")
    app._tus(0x1E, False, False)
    app._f_tusu(0x41)                                 # F7: kapat
    app.kok.after(300, gon_adim4)


def gon_adim4():
    app._guncelle()
    kontrol("gönderen: F7 ile kapandı, alana bırak gitti", not app.acik and ("birak",) in olaylar)
    kontrol("gönderen: gösterge söndü", app.gosterge.metin is None)
    alici.kapat()
    app.kapat()


app.kok.after(1200, gon_adim)
app.calis()
print("HEPSİ GEÇTİ" if not hatalar else f"{len(hatalar)} HATA")
sys.exit(1 if hatalar else 0)
