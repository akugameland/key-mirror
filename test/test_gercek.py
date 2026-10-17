"""Gerçek basma ve yakalama: yalnız zararsız girdiler (Shift, Ctrl, küçük ve geri alınan fare hareketi).
W ve tıklama denenmez: öndeki pencereye yazar ya da tıklar. python -X utf8 test/test_gercek.py"""
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import girdi  # noqa: E402

u32 = ctypes.windll.user32
hatalar = []


def kontrol(ad, kosul):
    print(("OK   " if kosul else "HATA ") + ad)
    if not kosul:
        hatalar.append(ad)


def basili_mi(vk):
    return bool(u32.GetAsyncKeyState(vk) & 0x8000)


def imlec():
    p = wintypes.POINT()
    u32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


b = girdi.Basici()
# Basma: Shift (VK_LSHIFT 0xA0), sağ Ctrl (VK_RCONTROL 0xA3, E0 genişletilmiş)
b.tus(0x2A, False, True)
time.sleep(0.05)
kontrol("sol Shift basıldı", basili_mi(0xA0))
b.tus(0x1D, True, True)
time.sleep(0.05)
kontrol("sağ Ctrl basıldı (E0)", basili_mi(0xA3) and not basili_mi(0xA2))
b.hepsini_birak()
time.sleep(0.05)
kontrol("hepsini bırak çalışır", not basili_mi(0xA0) and not basili_mi(0xA3))
kontrol("beyaz liste dışı (Enter) reddedilir", b.tus(0x1C, False, True) is False and not basili_mi(0x0D))
x0, y0 = imlec()
b.fare_hareket(30, 0)
time.sleep(0.05)
x1, _ = imlec()
b.fare_hareket(-30, 0)
time.sleep(0.05)
kontrol(f"fare hareketi uygulandı ({x0} -> {x1})", x1 != x0)

# Yakalama: programla basılan Shift'i yalnız test kipinde (enjekteleri_al) görmeli
gelen = []
yk = girdi.Yakalayici(lambda t, e, bs: gelen.append(("tus", t, e, bs)), lambda dx, dy: gelen.append(("fare", dx, dy)),
                      lambda n, bs: None, lambda m, y: None, lambda t: gelen.append(("f", t)), enjekteleri_al=True)
time.sleep(0.2)
b.tus(0x2A, False, True)
b.tus(0x2A, False, False)
b.fare_hareket(5, 0)
b.fare_hareket(-5, 0)
time.sleep(0.3)
yk.kapat()
kontrol("yakalayıcı Shift basış ve bırakışı gördü",
        ("tus", 0x2A, False, True) in gelen and ("tus", 0x2A, False, False) in gelen)
kontrol("yakalayıcı fare hareketini gördü", any(g[0] == "fare" for g in gelen))

# Döngü önleme: normal kipte programla basılanlar yok sayılır (iki program aynı PC'de olsa da yankı olmaz)
gelen.clear()
yk2 = girdi.Yakalayici(lambda t, e, bs: gelen.append(t),
                       lambda dx, dy: gelen.append("fare5" if abs(dx) == 5 and dy == 0 else "fare"),
                       lambda n, bs: None, lambda m, y: None, lambda t: None)
time.sleep(0.2)
b.tus(0x2A, False, True)
b.tus(0x2A, False, False)
b.fare_hareket(5, 0)
b.fare_hareket(-5, 0)
time.sleep(0.3)
yk2.kapat()
# (o sırada kullanıcı gerçek fareyi/klavyeyi kullanabilir: yalnız testin gönderdiklerine bak)
kontrol("normal kipte programla basılanlar yok sayılır (döngü yok)",
        0x2A not in gelen and gelen.count("fare5") == 0)
print("HEPSİ GEÇTİ" if not hatalar else f"{len(hatalar)} HATA")
sys.exit(1 if hatalar else 0)
