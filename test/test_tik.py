"""Gerçek fare tıklaması testi (2026-10-21 "sol / sağ tık çalışmıyor" hatası için).
Zararsız: imlecin tam altına kendi küçük penceresini açar ve tıklamayı yalnız imleç o pencerenin üstündeyse yapar;
değilse hiç tıklamadan "ATLANDI" der. Testin sonunda basılı düğme kalmaz.
python -X utf8 test/test_tik.py"""
import ctypes
import sys
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import girdi  # noqa: E402

_u32 = ctypes.windll.user32
_u32.WindowFromPoint.argtypes = (wintypes.POINT,)
_u32.WindowFromPoint.restype = wintypes.HWND
_u32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
_u32.GetAncestor.restype = wintypes.HWND
hatalar = []


def kontrol(ad, kosul):
    print(("OK   " if kosul else "HATA ") + ad)
    if not kosul:
        hatalar.append(ad)


imlec = wintypes.POINT()
_u32.GetCursorPos(ctypes.byref(imlec))
kok = tk.Tk()
kok.overrideredirect(True)
kok.attributes("-topmost", True)
kok.configure(bg="#203040")
kok.geometry(f"240x160+{imlec.x - 120}+{imlec.y - 80}")
tk.Label(kok, text="Tuş Yansıt tık testi", bg="#203040", fg="white").pack(expand=True)
tk_olaylar = []
for olay in ("<ButtonPress-1>", "<ButtonRelease-1>", "<ButtonPress-3>", "<ButtonRelease-3>"):
    kok.bind_all(olay, lambda e, o=olay: tk_olaylar.append(o))
kok.update()
kok.focus_force()
time.sleep(0.3)
kok.update()

yakalanan = []
yak = girdi.Yakalayici(lambda *a: None, lambda *a: None, lambda no, b: yakalanan.append((no, b)),
                       lambda *a: None, lambda *a: None, enjekteleri_al=True)
basici = girdi.Basici()


def bizim_mi() -> bool:
    nokta = wintypes.POINT()
    _u32.GetCursorPos(ctypes.byref(nokta))
    altindaki = _u32.GetAncestor(_u32.WindowFromPoint(nokta), 2)          # GA_ROOT
    return bool(altindaki) and altindaki == _u32.GetAncestor(kok.winfo_id(), 2)


atlandi = False
for no in (0, 1):                                     # 0 sol, 1 sağ
    if not bizim_mi():                                # imleç başka bir yere kaydıysa asla tıklama
        atlandi = True
        break
    basici.fare_dugme(no, True)
    time.sleep(0.05)
    basici.fare_dugme(no, False)
    for _ in range(10):
        kok.update()
        time.sleep(0.03)
basici.hepsini_birak()
yak.kapat()
for _ in range(10):
    kok.update()
    time.sleep(0.03)
kok.destroy()

if atlandi:
    print("ATLANDI: imleç test penceresinin üstünde değildi, hiç tıklanmadı. Fareyi oynatmadan tekrar çalıştır.")
    sys.exit(2)
kontrol("gönderen sol tık basışını ve bırakışını yakalar", (0, True) in yakalanan and (0, False) in yakalanan)
kontrol("gönderen sağ tık basışını ve bırakışını yakalar", (1, True) in yakalanan and (1, False) in yakalanan)
kontrol("alan sol tıkı pencereye uygular", "<ButtonPress-1>" in tk_olaylar and "<ButtonRelease-1>" in tk_olaylar)
kontrol("alan sağ tıkı pencereye uygular", "<ButtonPress-3>" in tk_olaylar and "<ButtonRelease-3>" in tk_olaylar)
kontrol("basılı düğme kalmadı", not basici.basili_dugmeler)
print("HEPSİ GEÇTİ" if not hatalar else f"{len(hatalar)} HATA")
sys.exit(1 if hatalar else 0)
