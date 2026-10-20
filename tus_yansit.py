"""Tuş Yansıt (Key Mirror): bir bilgisayarda basılan tuşları ve fareyi yerel ağdaki ikinci bilgisayarda da aynı
anda basar. Türkçe / English. Yalnız Python standart kütüphanesi.

Gönderen: tuşlara basılan bilgisayar. Yansıtma kapalı başlar, açma/kapama tuşuyla (varsayılan F7) açılır;
açıkken ekranın sol üstünde kırmızı gösterge durur. Yalnız alanın seçtiği tuşlar gönderilir.
Alan: tuşların da basılacağı bilgisayar. Eşleştirme kodunu gösterir; yalnız o kodu bilen gönderenden gelen,
şifreli ve imzalı paketleri uygular. Hangi tuşların basılabileceğini kendi klavyesinden seçer
(ekle / çıkar; varsayılan W A S D, Shift, Ctrl). Güvenlik ayrıntıları: ag.py.
"""
import ctypes
import json
import logging
import os
import socket
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

if sys.stdout is None:                                 # çift tıklamayla (pythonw) açılınca konsol yok
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

KLASOR = Path(__file__).resolve().parent
AYAR_DOSYASI = KLASOR / "ayarlar.json"                 # eşleştirme kodu burada: depoya girmez (.gitignore)
logging.basicConfig(filename=KLASOR / "hata.log", level=logging.INFO, encoding="utf-8",
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:  # noqa: BLE001
    pass

import ag  # noqa: E402
import girdi  # noqa: E402
import yetki  # noqa: E402
from metinler import DIL_ADLARI, t, varsayilan_dil  # noqa: E402

VARSAYILAN = {"dil": "", "rol": "gonderen", "kod": "", "hedef_kod": "", "hedef_ip": "", "ac_kapa": 0x41,
              "fare": True, "izinli_tuslar": [[t, e] for t, e in sorted(girdi.TUSLAR)]}
KIRMIZI, YESIL, SARI, GRI, MAVI = "#ff5a5a", "#4dff6a", "#ffd84a", "#bdbdbd", "#8fd0ff"
ARKA, ON, KUTU = "#1e1f24", "#e8e8e8", "#2b2d34"
ANAHTAR_RENK = "#010203"

_u32 = ctypes.windll.user32
GWL_EXSTYLE = -20
TIKLAMA_GECIR = 0x80000 | 0x20 | 0x80 | 0x08000000     # layered | transparent | toolwindow | noactivate


def ayar_yukle() -> dict:
    a = dict(VARSAYILAN)
    try:
        a.update({k: v for k, v in json.loads(AYAR_DOSYASI.read_text(encoding="utf-8")).items() if k in VARSAYILAN})
    except (OSError, ValueError):
        pass
    if a["dil"] not in DIL_ADLARI:
        a["dil"] = varsayilan_dil()
    if not ag.kod_gecerli(a["kod"]):
        a["kod"] = ag.yeni_kod()
    if a["ac_kapa"] not in girdi.F_TUSLARI:
        a["ac_kapa"] = 0x41
    try:                                               # alanın tuş listesi: bozuksa varsayılana dön
        a["izinli_tuslar"] = [[int(t), bool(e)] for t, e in a["izinli_tuslar"]
                              if girdi.izin_verilir_mi(int(t), bool(e))][:girdi.EN_COK_TUS]
    except (TypeError, ValueError):
        a["izinli_tuslar"] = list(VARSAYILAN["izinli_tuslar"])
    return a


class Gosterge:
    """Ekranın sol üstünde, tıklamaları geçiren küçük yazı (yansıtma açıkken / uzaktan girdi gelirken)."""

    def __init__(self, kok):
        self.p = tk.Toplevel(kok)
        self.p.overrideredirect(True)
        self.p.configure(bg=ANAHTAR_RENK)
        self.p.attributes("-topmost", True)
        self.p.attributes("-transparentcolor", ANAHTAR_RENK)
        self.yazi = tk.Label(self.p, bg=ANAHTAR_RENK, fg=KIRMIZI, font=("Segoe UI", 13, "bold"))
        self.yazi.pack()
        self.p.geometry("+12+8")
        self.p.withdraw()
        self.metin = None

    def goster(self, metin: str | None, renk: str = KIRMIZI):
        if metin == self.metin:
            if metin:                                  # oyunlar kendini öne alabilir: düzenli olarak en öne
                _u32.SetWindowPos(_u32.GetParent(self.p.winfo_id()), -1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)
            return
        self.metin = metin
        if not metin:
            self.p.withdraw()
            return
        self.yazi.config(text=metin, fg=renk)
        self.p.deiconify()
        self.p.update_idletasks()
        hwnd = _u32.GetParent(self.p.winfo_id())
        _u32.SetWindowLongW(hwnd, GWL_EXSTYLE, _u32.GetWindowLongW(hwnd, GWL_EXSTYLE) | TIKLAMA_GECIR)


class Uygulama:
    def __init__(self):
        self.ayar = ayar_yukle()
        self._kaydet()
        self.kok = tk.Tk()
        self.kok.geometry("620x720")
        self.kok.configure(bg=ARKA)
        self.kok.protocol("WM_DELETE_WINDOW", self.kapat)
        self.kok.report_callback_exception = lambda *a: logging.error("arayüz hatası", exc_info=a)
        stil = ttk.Style()
        stil.theme_use("clam")
        stil.configure("TCombobox", fieldbackground=KUTU, background=KUTU, foreground=ON)
        stil.map("TCombobox", fieldbackground=[("readonly", KUTU)], foreground=[("readonly", ON)],
                 selectbackground=[("readonly", KUTU)], selectforeground=[("readonly", ON)])
        self.gosterge = Gosterge(self.kok)
        self.govde = None
        # gönderen durumu
        self.acik = False
        self.basili_tuslar: set = set()
        self.basili_dugmeler: set = set()
        self.yakalayici = self.gonderici = None
        self._atama = False
        self._bildir("", GRI)
        # alan durumu
        self.alici = None
        self.basici = girdi.Basici(self.ayar["izinli_tuslar"])
        self._ekleyici = None                          # alanda "tuş ekle" beklerken geçici klavye dinleyici
        self._engel = False
        self._calisiyor = True
        self._rolu_kur()
        threading.Thread(target=self._nabiz_dongusu, daemon=True, name="nabiz").start()
        self.kok.after(200, self._tik)

    def _bildir(self, metin: str, renk: str):
        """Kısa bildirim: 5 sn görünür, sonra bağlantı durumu yazılır."""
        self._bildirim = (metin, renk, time.time() if metin else 0.0)

    def m(self, anahtar, **kw):
        return t(self.ayar["dil"], anahtar, **kw)

    def _kaydet(self):
        try:
            AYAR_DOSYASI.write_text(json.dumps(self.ayar, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            logging.exception("ayar kaydı")

    # ── rol ──────────────────────────────────────────────────────────────────
    def _rolu_birak(self):
        self.acik = False
        if self.gonderici:
            self.gonderici.birak()
            self.gonderici.kapat()
        if self.yakalayici:
            self.yakalayici.kapat()
        if self.alici:
            self.alici.kapat()
        self._ekleme_bitir()
        self.yakalayici = self.gonderici = self.alici = None
        self.basici.hepsini_birak()

    def _rolu_kur(self):
        self._rolu_birak()
        self._bildir("", GRI)
        if self.ayar["rol"] == "alan":
            try:
                self.alici = ag.Alici(self.ayar["kod"], self.basici, socket.gethostname(), self._alan_olayi)
            except OSError:
                logging.exception("alıcı açılamadı")
                self._bildir(self.m("port_dolu", port=ag.PORT), KIRMIZI)
        else:
            self.yakalayici = girdi.Yakalayici(self._tus, self._hareket, self._dugme, self._teker, self._f_tusu)
            if ag.kod_gecerli(self.ayar["hedef_kod"]):
                self.gonderici = ag.Gonderici(self.ayar["hedef_kod"])
                if self.ayar["hedef_ip"]:
                    try:
                        self.gonderici.hedefle(self.ayar["hedef_ip"])
                    except ValueError:
                        self.ayar["hedef_ip"] = ""
        self._arayuz()

    # ── arayüz ───────────────────────────────────────────────────────────────
    def _arayuz(self):
        if self.govde is not None:
            self.govde.destroy()
        self.kok.title(self.m("baslik").split(":")[0])
        k = self.govde = tk.Frame(self.kok, bg=ARKA)
        k.pack(fill="both", expand=True, padx=16, pady=10)
        tk.Label(k, text=self.m("baslik"), bg=ARKA, fg=SARI, font=("Segoe UI", 13, "bold"),
                 wraplength=560, justify="left").pack(anchor="w", pady=(0, 8))
        c = tk.Frame(k, bg=ARKA)
        c.pack(fill="x")
        c.columnconfigure(1, weight=1)

        def etiket(yazi, satir):
            tk.Label(c, text=yazi, bg=ARKA, fg=ON, font=("Segoe UI", 10)).grid(row=satir, column=0, sticky="w",
                                                                              pady=4, padx=(0, 8))

        etiket(self.m("dil"), 0)
        dil = ttk.Combobox(c, values=list(DIL_ADLARI.values()), state="readonly")
        dil.set(DIL_ADLARI[self.ayar["dil"]])
        dil.grid(row=0, column=1, sticky="ew")
        dil.bind("<<ComboboxSelected>>", lambda e: self._ayarla(
            "dil", next(a for a, v in DIL_ADLARI.items() if v == dil.get()), yeniden=False))

        etiket(self.m("rol"), 1)
        rol = ttk.Combobox(c, values=[self.m("gonderen"), self.m("alan")], state="readonly")
        rol.set(self.m("alan") if self.ayar["rol"] == "alan" else self.m("gonderen"))
        rol.grid(row=1, column=1, sticky="ew")
        rol.bind("<<ComboboxSelected>>", lambda e: self._ayarla(
            "rol", "alan" if rol.get() == self.m("alan") else "gonderen"))

        if self.ayar["rol"] == "alan":
            self._alan_arayuzu(k, c, etiket)
        else:
            self._gonderen_arayuzu(k, c, etiket)
        self.durum = tk.Label(k, bg=ARKA, fg=GRI, font=("Segoe UI", 10), wraplength=560, justify="left")
        self.durum.pack(anchor="w", pady=(10, 0))

    def _alan_arayuzu(self, k, c, etiket):
        etiket(self.m("kod"), 2)
        satir = tk.Frame(c, bg=ARKA)
        satir.grid(row=2, column=1, sticky="ew")
        tk.Label(satir, text=ag.kod_goster(self.ayar["kod"]), bg=KUTU, fg=YESIL, font=("Consolas", 18, "bold"),
                 padx=10).pack(side="left")
        tk.Button(satir, text=self.m("yeni_kod"), command=self._yeni_kod, bg=KUTU, fg=ON,
                  relief="flat").pack(side="left", padx=8)
        tk.Label(c, text=self.m("kod_aciklama"), bg=ARKA, fg=GRI, font=("Segoe UI", 8), wraplength=420,
                 justify="left").grid(row=3, column=1, sticky="w")
        adresler = ag.yerel_adresler()
        tk.Label(c, text=self.m("adres", adres=adresler[0] if adresler else "?") + (
            f"   ({', '.join(adresler[1:])})" if len(adresler) > 1 else ""), bg=ARKA, fg=ON,
            font=("Segoe UI", 10)).grid(row=4, column=1, sticky="w", pady=4)
        self.uygula = tk.BooleanVar(value=self.alici.etkin if self.alici else True)
        tk.Checkbutton(c, text=self.m("uygula"), variable=self.uygula, command=self._uygula_degisti, bg=ARKA, fg=ON,
                       selectcolor=KUTU, activebackground=ARKA, activeforeground=ON).grid(row=5, column=1, sticky="w")
        # Basılabilecek tuşlar: alan kendi klavyesinden ekler / çıkarır
        etiket(self.m("izinli"), 6)
        liste = tk.Frame(c, bg=ARKA)
        liste.grid(row=6, column=1, sticky="ew", pady=(6, 0))
        self.tus_listesi = tk.Listbox(liste, height=9, bg=KUTU, fg=ON, selectbackground="#3d5a80", relief="flat",
                                      font=("Segoe UI", 10), activestyle="none", exportselection=False)
        kaydirma = tk.Scrollbar(liste, command=self.tus_listesi.yview)
        self.tus_listesi.config(yscrollcommand=kaydirma.set)
        self.tus_listesi.pack(side="left", fill="both", expand=True)
        kaydirma.pack(side="left", fill="y")
        dugmeler = tk.Frame(liste, bg=ARKA)
        dugmeler.pack(side="left", fill="y", padx=(8, 0))
        self.ekle_dugme = tk.Button(dugmeler, text=self.m("tus_ekle"), command=self._ekleme_baslat, bg=KUTU, fg=ON,
                                    relief="flat", width=18)
        self.ekle_dugme.pack(fill="x")
        tk.Button(dugmeler, text=self.m("tus_cikar"), command=self._tus_cikar, bg=KUTU, fg=ON,
                  relief="flat").pack(fill="x", pady=4)
        tk.Button(dugmeler, text=self.m("tus_varsayilan"), command=self._tus_varsayilan, bg=KUTU, fg=ON,
                  relief="flat").pack(fill="x")
        tk.Label(c, text=self.m("izinli_aciklama"), bg=ARKA, fg=GRI, font=("Segoe UI", 8), wraplength=420,
                 justify="left").grid(row=7, column=1, sticky="w")
        self._listeyi_yaz()
        self.sayac = tk.Label(k, bg=ARKA, fg=GRI, font=("Segoe UI", 9))
        self.sayac.pack(anchor="w", pady=(8, 0))

    def _gonderen_arayuzu(self, k, c, etiket):
        etiket(self.m("hedef_kod"), 2)
        self.kod_giris = tk.Entry(c, bg=KUTU, fg=ON, insertbackground=ON, relief="flat", font=("Consolas", 14))
        self.kod_giris.insert(0, ag.kod_goster(self.ayar["hedef_kod"]) if self.ayar["hedef_kod"] else "")
        self.kod_giris.grid(row=2, column=1, sticky="ew")
        etiket(self.m("hedef_ip"), 3)
        ip = tk.Frame(c, bg=ARKA)
        ip.grid(row=3, column=1, sticky="ew")
        self.ip_giris = tk.Entry(ip, bg=KUTU, fg=ON, insertbackground=ON, relief="flat", font=("Segoe UI", 11),
                                 width=18)
        self.ip_giris.insert(0, self.ayar["hedef_ip"])
        self.ip_giris.pack(side="left")
        tk.Label(ip, text=self.m("ip_bos"), bg=ARKA, fg=GRI, font=("Segoe UI", 8)).pack(side="left", padx=6)
        self.bul_dugme = tk.Button(c, text=self.m("bul"), command=self._bul, bg=KUTU, fg=ON, relief="flat")
        self.bul_dugme.grid(row=4, column=1, sticky="w", pady=4)
        etiket(self.m("ac_kapa"), 5)
        self.tus_dugme = tk.Button(c, command=self._tus_ata, bg=KUTU, fg=ON, relief="flat",
                                   text=self.m("tus_degistir", tus=girdi.F_TUSLARI[self.ayar["ac_kapa"]]))
        self.tus_dugme.grid(row=5, column=1, sticky="ew")
        self.fare = tk.BooleanVar(value=self.ayar["fare"])
        tk.Checkbutton(c, text=self.m("fare"), variable=self.fare, bg=ARKA, fg=ON, selectcolor=KUTU,
                       activebackground=ARKA, activeforeground=ON,
                       command=lambda: self._ayarla("fare", bool(self.fare.get()), yeniden=False)).grid(
            row=6, column=1, sticky="w")
        self.buyuk = tk.Label(k, bg=ARKA, font=("Segoe UI", 20, "bold"))
        self.buyuk.pack(anchor="w", pady=(12, 0))
        self.aciklama = tk.Label(k, bg=ARKA, fg=GRI, font=("Segoe UI", 10))
        self.aciklama.pack(anchor="w")
        self.yansitilan = tk.Label(k, bg=ARKA, fg=GRI, font=("Segoe UI", 9), wraplength=560, justify="left")
        self.yansitilan.pack(anchor="w", pady=(6, 0))

    def _ayarla(self, anahtar, deger, yeniden=True):
        if self.ayar.get(anahtar) == deger:
            return
        self.ayar[anahtar] = deger
        self._kaydet()
        if yeniden:
            self._rolu_kur()
        else:
            self._arayuz()

    # ── alan ─────────────────────────────────────────────────────────────────
    def _yeni_kod(self):
        self.ayar["kod"] = ag.yeni_kod()
        self._kaydet()
        self._rolu_kur()

    # ── alan: tuş listesi ────────────────────────────────────────────────────
    def _listeyi_yaz(self):
        dil = self.ayar["dil"]
        self._liste_sirasi = sorted(((t, bool(e)) for t, e in self.ayar["izinli_tuslar"]),
                                    key=lambda te: (len(girdi.tus_adi(*te, dil)) > 1, girdi.tus_adi(*te, dil).lower()))
        self.tus_listesi.delete(0, "end")
        for t, e in self._liste_sirasi:
            self.tus_listesi.insert("end", girdi.tus_adi(t, e, self.ayar["dil"]))

    def _liste_kaydet(self, tuslar):
        self.ayar["izinli_tuslar"] = [[t, e] for t, e in sorted(self.basici.izinli_ayarla(tuslar))]
        self._kaydet()
        logging.info("alanın tuş listesi: %s", self.ayar["izinli_tuslar"])
        self._listeyi_yaz()

    def _ekleme_baslat(self):
        if self._ekleyici:
            return self._ekleme_bitir()
        try:
            # Yalnız bu bilgisayarın gerçek klavyesi: uzaktan basılan (enjekte) tuşlar zaten atlanır
            self._ekleyici = girdi.Yakalayici(self._eklenen_tus, lambda *a: None, lambda *a: None, lambda *a: None,
                                              self._eklenen_f)
        except RuntimeError:
            logging.exception("tuş ekleme dinleyicisi")
            return
        self.ekle_dugme.config(text=self.m("tus_bekle_ekle"))

    def _ekleme_bitir(self):
        if self._ekleyici:
            self._ekleyici.kapat()
            self._ekleyici = None
        if self.ayar["rol"] == "alan" and getattr(self, "ekle_dugme", None) and self.ekle_dugme.winfo_exists():
            self.ekle_dugme.config(text=self.m("tus_ekle"))

    def _eklenen_tus(self, tarama, e0, basili):
        """Dinleyici iş parçacığından: arayüze aktar."""
        if basili:
            self.kok.after(0, lambda: self._tus_eklendi(tarama, e0))

    def _eklenen_f(self, tarama):
        self.kok.after(0, lambda: (self._ekleme_bitir(), self._bildir(self.m("tus_ayrilmis"), SARI)))

    def _tus_eklendi(self, tarama, e0):
        if not self._ekleyici:
            return
        self._ekleme_bitir()
        if tarama == 0x01 and not e0:                  # Esc: vazgeç
            return
        mevcut = {(t, bool(e)) for t, e in self.ayar["izinli_tuslar"]}
        if (tarama, e0) in mevcut:
            return self._bildir(self.m("tus_zaten", tus=girdi.tus_adi(tarama, e0, self.ayar["dil"])), SARI)
        if len(mevcut) >= girdi.EN_COK_TUS:
            return self._bildir(self.m("tus_dolu", n=girdi.EN_COK_TUS), SARI)
        self._liste_kaydet(mevcut | {(tarama, e0)})
        self._bildir(self.m("tus_eklendi", tus=girdi.tus_adi(tarama, e0, self.ayar["dil"])), YESIL)

    def _tus_cikar(self):
        secili = self.tus_listesi.curselection()
        if not secili:
            return self._bildir(self.m("tus_sec"), SARI)
        cikan = self._liste_sirasi[secili[0]]
        self._liste_kaydet({(t, bool(e)) for t, e in self.ayar["izinli_tuslar"]} - {cikan})
        self._bildir(self.m("tus_cikarildi", tus=girdi.tus_adi(*cikan, self.ayar["dil"])), GRI)

    def _tus_varsayilan(self):
        self._ekleme_bitir()
        self._liste_kaydet(set(girdi.TUSLAR))

    def _uygula_degisti(self):
        if self.alici:
            self.alici.etkin = bool(self.uygula.get())
            if not self.alici.etkin:
                self.basici.hepsini_birak()

    def _alan_olayi(self, olay, *bilgi):
        """Alıcı iş parçacığından: arayüze kuyruksuz, yalnız metin bırakılır (tik okur)."""
        if olay == "baglandi":
            self._bildir(self.m("baglandi", ip=bilgi[0]), YESIL)
            logging.info("gönderen bağlandı: %s", bilgi[0])
        elif olay == "koptu":
            self._bildir(self.m("koptu"), SARI)

    # ── gönderen ─────────────────────────────────────────────────────────────
    def _bul(self):
        kod = ag.kod_duzelt(self.kod_giris.get())
        if not ag.kod_gecerli(kod):
            self._bildir(self.m("bulunamadi"), KIRMIZI)
            return
        ip = self.ip_giris.get().strip()
        if ip and not ag.ozel_adres_mi(ip):
            self._bildir(self.m("bulunamadi"), KIRMIZI)
            return
        if kod != self.ayar["hedef_kod"] or not self.gonderici:
            self.ayar["hedef_kod"] = kod
            if self.gonderici:
                self.gonderici.birak()
                self.gonderici.kapat()
            self.gonderici = ag.Gonderici(kod)
        self.bul_dugme.config(text=self.m("araniyor"), state="disabled")

        def calis():
            if ip:
                bulunan = {ip: ip}
            else:
                bulunan = self.gonderici.bul()
            self.kok.after(0, lambda: self._bulundu(bulunan))
        threading.Thread(target=calis, daemon=True).start()

    def _bulundu(self, bulunan: dict):
        self.bul_dugme.config(text=self.m("bul"), state="normal")
        if not bulunan:
            self._bildir(self.m("bulunamadi"), KIRMIZI)
            return
        ip, ad = next(iter(bulunan.items()))
        self.gonderici.hedefle(ip)
        self.ayar["hedef_ip"] = ip
        self._kaydet()
        self.ip_giris.delete(0, "end")
        self.ip_giris.insert(0, ip)
        self._bildir(self.m("bulundu", ad=ad, ip=ip), YESIL)

    def _tus_ata(self):
        self._atama = True
        self.tus_dugme.config(text=self.m("tus_bekle"))

    def _f_tusu(self, tarama):
        """Yakalayıcı iş parçacığından."""
        if self._atama:
            self._atama = False
            self.ayar["ac_kapa"] = tarama
            self._kaydet()
            self.kok.after(0, self._arayuz)
        elif tarama == self.ayar["ac_kapa"]:
            self.ac_kapa()

    def ac_kapa(self):
        self.acik = not self.acik
        logging.info("yansıtma %s", "açıldı" if self.acik else "kapandı")
        if self.gonderici:
            if not self.acik:
                self.gonderici.birak()
            self.gonderici.nabiz(self.acik, self.basili_tuslar, self.basili_dugmeler)

    def _tus(self, tarama, e0, basili):
        (self.basili_tuslar.add if basili else self.basili_tuslar.discard)((tarama, e0))
        if self.acik and self.gonderici:
            self.gonderici.tus(tarama, e0, basili)

    def _hareket(self, dx, dy):
        if self.acik and self.gonderici and self.ayar["fare"]:
            self.gonderici.hareket(dx, dy)

    def _dugme(self, no, basili):
        (self.basili_dugmeler.add if basili else self.basili_dugmeler.discard)(no)
        if self.acik and self.gonderici and self.ayar["fare"]:
            self.gonderici.dugme(no, basili)

    def _teker(self, miktar, yatay):
        if self.acik and self.gonderici and self.ayar["fare"]:
            self.gonderici.teker(miktar, yatay)

    def _nabiz_dongusu(self):
        while self._calisiyor:
            g = self.gonderici
            if g and g.hedef:
                try:
                    g.nabiz(self.acik, self.basili_tuslar if self.acik else set(),
                            self.basili_dugmeler if self.acik and self.ayar["fare"] else set())
                except Exception:  # noqa: BLE001
                    logging.exception("nabız")
            time.sleep(ag.NABIZ_SN)

    # ── ana döngü ────────────────────────────────────────────────────────────
    def _tik(self):
        try:
            self._guncelle()
        except Exception:  # noqa: BLE001
            logging.exception("güncelleme")
        if self._calisiyor:
            self.kok.after(150, self._tik)

    def _guncelle(self):
        bildirim, b_renk, b_zaman = self._bildirim
        taze = bool(bildirim) and time.time() - b_zaman < 5
        if self.ayar["rol"] == "alan":
            a = self.alici
            metin, renk = (bildirim, b_renk) if bildirim and (not a or taze) else (self.m("bekleniyor"), GRI)
            if a:
                self.sayac.config(text=self.m("sayac", **a.sayac))
                bagli = time.time() - a.son_paket < 1.5
                self._engel = yetki.tuslar_engelli_mi() if bagli and a.uzak_acik else False
                if self._engel:
                    metin, renk = self.m("yonetici"), KIRMIZI
                elif taze:
                    metin, renk = bildirim, b_renk
                elif bagli and a.gonderen:
                    metin, renk = self.m("baglandi", ip=a.gonderen[0]), YESIL
                self.gosterge.goster(self.m("gosterge_alan") if bagli and a.uzak_acik and a.etkin else None, MAVI)
        else:
            tus = girdi.F_TUSLARI[self.ayar["ac_kapa"]]
            self.buyuk.config(text=self.m("yansitma_acik" if self.acik else "yansitma_kapali"),
                              fg=KIRMIZI if self.acik else GRI)
            self.aciklama.config(text=self.m("acik_aciklama" if self.acik else "kapali_aciklama", tus=tus))
            g = self.gonderici
            fare = self.m("fare_ek") if self.ayar["fare"] else ""
            if g and g.bagli_mi() and g.alan_tuslari:
                anahtar = (g.alan_tuslari, self.ayar["dil"])
                if getattr(self, "_ad_onbellek", (None, ""))[0] != anahtar:
                    adlar = sorted((girdi.tus_adi(t, e, self.ayar["dil"]) for t, e in g.alan_tuslari),
                                   key=lambda a: (len(a) > 1, a.lower()))
                    self._ad_onbellek = (anahtar, ", ".join(adlar))
                self.yansitilan.config(text=self.m("yansitilan", tuslar=self._ad_onbellek[1], fare=fare))
            else:
                self.yansitilan.config(text=self.m("yansitilan_bekle"))
            metin, renk = "", GRI
            if taze:
                metin, renk = bildirim, b_renk
            elif g and g.hedef:
                if g.bagli_mi():
                    metin, renk = ((self.m("alan_yanit"), YESIL) if g.alan_durumu == "1"
                                   else (self.m("alan_kapali"), SARI))
                else:
                    metin, renk = self.m("alan_yanit_yok"), SARI
            self.gosterge.goster(self.m("gosterge_gonderen", tus=tus) if self.acik else None, KIRMIZI)
        self.durum.config(text=metin, fg=renk)

    def kapat(self):
        self._calisiyor = False
        try:
            self._rolu_birak()
        finally:
            self.kok.destroy()

    def calis(self):
        self.kok.mainloop()


if __name__ == "__main__":
    try:
        Uygulama().calis()
    except Exception:  # noqa: BLE001
        logging.exception("çöküş")
        raise
