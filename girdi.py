"""Girdi: gönderende yakalama (Raw Input), alanda basma (SendInput). Yalnız Python standart kütüphanesi.

Yakalama neden Raw Input (düşük seviye kanca değil): kanca (WH_KEYBOARD_LL / WH_MOUSE_LL) Windows'un girdi
akışını Python kodu dönene kadar bekletir; 1000 Hz oyun faresinde gecikme yapabilir. Raw Input yalnız bildirimdir,
hiçbir tuşu ya da fare hareketini bekletmez ve engellemez (CanYouSpeak fare.py dersi). Programla basılan
(enjekte) girdiler hDevice = 0 ile gelir ve atlanır: iki program aynı bilgisayarda çalışsa da döngü olmaz.

Hangi tuşların yansıtılacağını ALAN seçer (kendi klavyesinden ekler / çıkarır; varsayılan: W A S D, Shift, Ctrl).
Farede de ALAN seçer: sol / sağ / orta / yan tıklar, tekerlek (kaydırma) ve hareket ayrı ayrı açılıp kapanır (FARE_*).
Alan listesini nabız cevabıyla gönderene bildirir. Gönderen yalnız o listedeki tuşları gönderir; alan da listesinde
olmayan tuşu basmaz (iki taraflı beyaz liste). YASAK listesindeki tuşlar (Windows, menü, F1-F12 / Scroll Lock)
hiçbir zaman seçilemez ve yansıtılmaz.
"""
import ctypes
import logging
import threading
from ctypes import wintypes

log = logging.getLogger("girdi")

# Varsayılan liste (alan değiştirebilir): (tarama kodu, E0 genişletilmiş mi) -> ad
TUSLAR = {
    (0x11, False): "W", (0x1E, False): "A", (0x1F, False): "S", (0x20, False): "D",
    (0x2A, False): "Sol Shift", (0x36, False): "Sağ Shift",
    (0x1D, False): "Sol Ctrl", (0x1D, True): "Sağ Ctrl",
}
EN_COK_TUS = 60                                       # alanın listesi en çok bu kadar tuş (paket boyu sınırı)
# Fare düğmeleri: 0 sol, 1 sağ, 2 orta, 3 yan1 (geri), 4 yan2 (ileri)
DUGME_ADLARI = ["Sol tık", "Sağ tık", "Orta tık", "Yan tuş 1", "Yan tuş 2"]
# Alanın fare izni (bit maskesi): bit 0-4 düğmeler (yukarıdaki sırayla), 5 tekerlek, 6 hareket
FARE_TEKER, FARE_HAREKET = 5, 6
FARE_HEPSI = 0x7F                                     # varsayılan: hepsi açık (önceki sürümlerle aynı davranış)
FARE_SIRASI = (0, 1, 2, 3, 4, FARE_TEKER, FARE_HAREKET)

# Tarama kodu -> ad (açma/kapama tuşu seçimi için; yansıtılmaz)
F_TUSLARI = {0x3B: "F1", 0x3C: "F2", 0x3D: "F3", 0x3E: "F4", 0x3F: "F5", 0x40: "F6", 0x41: "F7", 0x42: "F8",
             0x43: "F9", 0x44: "F10", 0x57: "F11", 0x58: "F12", 0x46: "Scroll Lock"}

# Asla seçilemeyen / yansıtılmayan tuşlar: Windows tuşları ve menü tuşu (sistem kısayolları),
# Windows'un ok tuşlarıyla ürettiği sahte Shift'ler (E0 2A / E0 36), Num Lock ile karışan E0 45.
YASAK = {(0x5B, True), (0x5C, True), (0x5D, True), (0x2A, True), (0x36, True), (0x45, True)}
# Yan tuş adları (Windows'un kendi adları dile göre tutarsız): (tarama, e0) -> (tr, en)
YAN_ADLAR = {(0x2A, False): ("Sol Shift", "Left Shift"), (0x36, False): ("Sağ Shift", "Right Shift"),
             (0x1D, False): ("Sol Ctrl", "Left Ctrl"), (0x1D, True): ("Sağ Ctrl", "Right Ctrl"),
             (0x38, False): ("Sol Alt", "Left Alt"), (0x38, True): ("Sağ Alt", "Right Alt"),
             (0x39, False): ("Boşluk", "Space")}


def izin_verilir_mi(tarama: int, e0: bool) -> bool:
    """Bu tuş alanın listesine eklenebilir / yansıtılabilir mi?"""
    return 0 < tarama < 0x80 and (tarama, bool(e0)) not in YASAK and not (tarama in F_TUSLARI and not e0)


_u32 = ctypes.WinDLL("user32", use_last_error=True)
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_INPUT, WM_CLOSE, WM_DESTROY = 0x00FF, 0x0010, 0x0002
RIDEV_INPUTSINK = 0x00000100
RID_INPUT, RIM_TYPEMOUSE, RIM_TYPEKEYBOARD = 0x10000003, 0, 1
RI_KEY_BREAK, RI_KEY_E0, RI_KEY_E1 = 0x01, 0x02, 0x04
MOUSE_MOVE_ABSOLUTE = 0x01
HWND_MESSAGE = wintypes.HWND(-3)
# RAWMOUSE.usButtonFlags -> (düğme, basılı)
_DUGME_BAYRAK = {0x0001: (0, True), 0x0002: (0, False), 0x0004: (1, True), 0x0008: (1, False),
                 0x0010: (2, True), 0x0020: (2, False), 0x0040: (3, True), 0x0080: (3, False),
                 0x0100: (4, True), 0x0200: (4, False)}
RI_MOUSE_WHEEL, RI_MOUSE_HWHEEL = 0x0400, 0x0800

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_u32.DefWindowProcW.restype = LRESULT
_u32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_u32.CreateWindowExW.restype = wintypes.HWND
_u32.CreateWindowExW.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                                 wintypes.HINSTANCE, wintypes.LPVOID)
_k32.GetModuleHandleW.restype = wintypes.HMODULE
_k32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
_u32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_u32.DestroyWindow.argtypes = (wintypes.HWND,)
_u32.GetRawInputData.argtypes = (wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT),
                                 wintypes.UINT)
_u32.GetKeyNameTextW.argtypes = (wintypes.LONG, wintypes.LPWSTR, ctypes.c_int)
_u32.UnregisterClassW.argtypes = (wintypes.LPCWSTR, wintypes.HINSTANCE)


def tus_adi(tarama: int, e0: bool, dil: str = "tr") -> str:
    """Tuşun okunur adı (klavye düzenine göre, ör. Türkçe Q klavyede "Ğ")."""
    yan = YAN_ADLAR.get((tarama, bool(e0)))
    if yan:
        return yan[0] if dil == "tr" else yan[1]
    tampon = ctypes.create_unicode_buffer(64)
    if _u32.GetKeyNameTextW((tarama << 16) | (1 << 24 if e0 else 0), tampon, 64) > 0:
        return tampon.value
    return f"#{tarama:02X}{' E0' if e0 else ''}"


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                ("dwFlags", wintypes.DWORD), ("hwndTarget", wintypes.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wintypes.DWORD), ("dwSize", wintypes.DWORD),
                ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]


class RAWMOUSE(ctypes.Structure):
    # Windows'ta usFlags'tan sonra 4 baytlık hizalanmış bir birleşim (ulButtons / usButtonFlags+usButtonData) gelir:
    # arada 2 bayt boşluk var. Boşluk yazılmazsa düğme bayrakları hep 0 okunur ve tıklar / tekerlek hiç gelmez
    # (2026-10-21 hatası: "sol tık, sağ tık çalışmıyor"). Doğru konumlar: usButtonFlags 4, usButtonData 6.
    _fields_ = [("usFlags", wintypes.USHORT), ("_bosluk", wintypes.USHORT), ("usButtonFlags", wintypes.USHORT),
                ("usButtonData", wintypes.USHORT), ("ulRawButtons", wintypes.ULONG),
                ("lLastX", wintypes.LONG), ("lLastY", wintypes.LONG), ("ulExtraInformation", wintypes.ULONG)]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [("MakeCode", wintypes.USHORT), ("Flags", wintypes.USHORT), ("Reserved", wintypes.USHORT),
                ("VKey", wintypes.USHORT), ("Message", wintypes.UINT), ("ExtraInformation", wintypes.ULONG)]


class _RAWDATA(ctypes.Union):
    _fields_ = [("mouse", RAWMOUSE), ("keyboard", RAWKEYBOARD)]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("data", _RAWDATA)]


class Yakalayici:
    """Gönderen tarafı. Geri çağrılar kendi iş parçacığında çalışır, kısa tutulmalı:
    tus(tarama, e0, basili) (izin_verilir_mi olan her tuş; hangisinin gideceğine çağıran karar verir),
    fare_hareket(dx, dy), fare_dugme(no, basili), teker(miktar, yatay),
    f_tusu(tarama) (F1-F12 / Scroll Lock basıldığında: açma/kapama ve tuş atama için; yansıtılmaz)."""

    _sayac = 0

    def __init__(self, tus, fare_hareket, fare_dugme, teker, f_tusu, enjekteleri_al: bool = False):
        self._tus, self._hareket, self._dugme, self._teker, self._f_tusu = tus, fare_hareket, fare_dugme, teker, f_tusu
        self.enjekteleri_al = enjekteleri_al         # yalnız testte: programla basılan girdileri de say
        self._hwnd = None
        self._hazir = threading.Event()
        self._basili_f: set[int] = set()
        threading.Thread(target=self._calis, daemon=True, name="yakalayici").start()
        self._hazir.wait(3)
        if not self._hwnd:
            raise RuntimeError("girdi dinleyici açılamadı")

    def kapat(self):
        if self._hwnd:
            _u32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)

    def _calis(self):
        try:
            self._wndproc = WNDPROC(self._islev)            # referans tutulmazsa çöp toplanır ve çöker
            hinst = _k32.GetModuleHandleW(None)
            # Her dinleyiciye ayrı sınıf adı: aynı ad ikinci kez kaydedilemez ve yeni pencere eski (silinmiş)
            # dinleyicinin işlevini çağırırdı (rol değiştirme, alanda "tuş ekle").
            Yakalayici._sayac += 1
            self._sinif_adi = f"TusYansitGirdi{Yakalayici._sayac}"
            sinif = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=self._wndproc,
                                hInstance=hinst, lpszClassName=self._sinif_adi)
            _u32.RegisterClassExW(ctypes.byref(sinif))
            hwnd = _u32.CreateWindowExW(0, self._sinif_adi, None, 0, 0, 0, 0, 0, HWND_MESSAGE, None, hinst, None)
            aygitlar = (RAWINPUTDEVICE * 2)(RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd),   # klavye
                                            RAWINPUTDEVICE(0x01, 0x02, RIDEV_INPUTSINK, hwnd))   # fare
            if not _u32.RegisterRawInputDevices(aygitlar, 2, ctypes.sizeof(RAWINPUTDEVICE)):
                log.error("raw input kaydı başarısız: %s", ctypes.get_last_error())
            else:
                self._hwnd = hwnd
        except Exception:  # noqa: BLE001
            log.exception("girdi penceresi")
        finally:
            self._hazir.set()
        if not self._hwnd:
            return
        mesaj = wintypes.MSG()
        while _u32.GetMessageW(ctypes.byref(mesaj), None, 0, 0) > 0:
            _u32.DispatchMessageW(ctypes.byref(mesaj))
        _u32.UnregisterClassW(self._sinif_adi, _k32.GetModuleHandleW(None))

    def _islev(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_INPUT:
                veri = RAWINPUT()
                boyut = wintypes.UINT(ctypes.sizeof(veri))
                if _u32.GetRawInputData(lparam, RID_INPUT, ctypes.byref(veri), ctypes.byref(boyut),
                                        ctypes.sizeof(RAWINPUTHEADER)) != 0xFFFFFFFF:
                    if veri.header.hDevice or self.enjekteleri_al:
                        if veri.header.dwType == RIM_TYPEKEYBOARD:
                            self._klavye(veri.data.keyboard)
                        elif veri.header.dwType == RIM_TYPEMOUSE:
                            self._fare(veri.data.mouse)
            elif msg == WM_CLOSE:
                _u32.DestroyWindow(hwnd)
                return 0
            elif msg == WM_DESTROY:
                _u32.PostQuitMessage(0)
                return 0
        except Exception:  # noqa: BLE001
            log.exception("girdi mesajı")
        return _u32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _klavye(self, k: RAWKEYBOARD):
        if k.Flags & RI_KEY_E1:                        # Pause: tuhaf dizi, yansıtılmaz
            return
        basili = not (k.Flags & RI_KEY_BREAK)
        e0 = bool(k.Flags & RI_KEY_E0)
        if k.MakeCode in F_TUSLARI and not e0:
            if basili and k.MakeCode not in self._basili_f:   # basılı tutunca tekrar etmesin
                self._f_tusu(k.MakeCode)
            (self._basili_f.add if basili else self._basili_f.discard)(k.MakeCode)
            return
        # E0 2A / E0 36: Windows'un ok tuşlarıyla ürettiği sahte Shift'ler; gerçek Shift değil (YASAK'ta)
        if izin_verilir_mi(k.MakeCode, e0):
            self._tus(k.MakeCode, e0, basili)

    def _fare(self, m: RAWMOUSE):
        if not (m.usFlags & MOUSE_MOVE_ABSOLUTE) and (m.lLastX or m.lLastY):
            self._hareket(m.lLastX, m.lLastY)
        b = m.usButtonFlags
        if not b:
            return
        for bit, (no, basili) in _DUGME_BAYRAK.items():
            if b & bit:
                self._dugme(no, basili)
        if b & RI_MOUSE_WHEEL:
            self._teker(ctypes.c_short(m.usButtonData).value, False)
        if b & RI_MOUSE_HWHEEL:
            self._teker(ctypes.c_short(m.usButtonData).value, True)


# ── alan tarafı: SendInput ──────────────────────────────────────────────────
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x0001, 0x0002, 0x0008
MOUSEEVENTF_MOVE = 0x0001
_DUGME_GIRDI = {0: (0x0002, 0x0004, 0), 1: (0x0008, 0x0010, 0), 2: (0x0020, 0x0040, 0),
                3: (0x0080, 0x0100, 1), 4: (0x0080, 0x0100, 2)}          # (basış, bırakış, XBUTTON no)
MOUSEEVENTF_WHEEL, MOUSEEVENTF_HWHEEL = 0x0800, 0x1000
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _GIRDI_BIRLESIM(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _GIRDI_BIRLESIM)]


_u32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)


def _gonder(*girdiler: INPUT) -> bool:
    dizi = (INPUT * len(girdiler))(*girdiler)
    return _u32.SendInput(len(girdiler), dizi, ctypes.sizeof(INPUT)) == len(girdiler)


class Basici:
    """Alan tarafı. Basılı tuş ve düğmeleri izler: bağlantı koparsa hepsi bırakılabilsin."""

    def __init__(self, izinli=None, fare_izni: int = FARE_HEPSI):
        self.basili_tuslar: set[tuple[int, bool]] = set()
        self.basili_dugmeler: set[int] = set()
        self._kilit = threading.Lock()
        self.izinli: frozenset = frozenset(TUSLAR)
        self.fare_izni = FARE_HEPSI
        self.izinli_ayarla(TUSLAR if izinli is None else izinli)
        self.fare_izni_ayarla(fare_izni)

    def fare_izni_ayarla(self, maske: int) -> int:
        """Alanın fare seçimi (bit maskesi). Kapatılan ama basılı olan düğme bırakılır."""
        self.fare_izni = int(maske) & FARE_HEPSI
        for no in list(self.basili_dugmeler):
            if not self.fare_izni >> no & 1:
                self.fare_dugme(no, False)
        return self.fare_izni

    def izinli_ayarla(self, tuslar) -> frozenset:
        """Alanın seçtiği liste (YASAK olanlar ve fazlası atılır). Listeden çıkan ama basılı olan tuş bırakılır."""
        temiz = [(int(t), bool(e)) for t, e in tuslar if izin_verilir_mi(int(t), bool(e))]
        self.izinli = frozenset(temiz[:EN_COK_TUS])
        for t in list(self.basili_tuslar - self.izinli):
            self.tus(*t, False)
        return self.izinli

    def tus(self, tarama: int, e0: bool, basili: bool) -> bool:
        if (tarama, e0) not in self.izinli and not ((tarama, e0) in self.basili_tuslar and not basili):
            # beyaz liste dışı: asla basma (listeden yeni çıkarılmış basılı bir tuşu bırakmak serbest)
            log.warning("izin verilmeyen tuş geldi, basılmadı: %#x", tarama)
            return False
        with self._kilit:
            if basili == ((tarama, e0) in self.basili_tuslar) and not basili:
                return True                            # zaten bırakılmış
            bayrak = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if e0 else 0) | (0 if basili else KEYEVENTF_KEYUP)
            g = INPUT(type=INPUT_KEYBOARD)
            g.u.ki = KEYBDINPUT(0, tarama, bayrak, 0, 0)
            (self.basili_tuslar.add if basili else self.basili_tuslar.discard)((tarama, e0))
            return _gonder(g)

    def fare_hareket(self, dx: int, dy: int) -> bool:
        if not self.fare_izni >> FARE_HAREKET & 1:     # alan fare hareketini kapattı
            return False
        g = INPUT(type=INPUT_MOUSE)
        g.u.mi = MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, 0)
        return _gonder(g)

    def fare_dugme(self, no: int, basili: bool) -> bool:
        if no not in _DUGME_GIRDI:
            return False
        if basili and not self.fare_izni >> no & 1:    # alan bu düğmeyi kapattı (bırakmak hep serbest)
            log.warning("izin verilmeyen fare düğmesi geldi, basılmadı: %s", no)
            return False
        with self._kilit:
            if not basili and no not in self.basili_dugmeler:
                return True
            bas, birak, xno = _DUGME_GIRDI[no]
            g = INPUT(type=INPUT_MOUSE)
            g.u.mi = MOUSEINPUT(0, 0, xno, bas if basili else birak, 0, 0)
            (self.basili_dugmeler.add if basili else self.basili_dugmeler.discard)(no)
            return _gonder(g)

    def teker(self, miktar: int, yatay: bool) -> bool:
        if not self.fare_izni >> FARE_TEKER & 1:       # alan tekerleği (kaydırmayı) kapattı
            return False
        g = INPUT(type=INPUT_MOUSE)
        g.u.mi = MOUSEINPUT(0, 0, ctypes.c_uint32(miktar).value, MOUSEEVENTF_HWHEEL if yatay else MOUSEEVENTF_WHEEL,
                            0, 0)
        return _gonder(g)

    def hepsini_birak(self):
        """Bağlantı koptu / yansıtma kapandı: takılı kalan W ya da sol tık olmasın."""
        for tarama, e0 in list(self.basili_tuslar):
            self.tus(tarama, e0, False)
        for no in list(self.basili_dugmeler):
            self.fare_dugme(no, False)

    def esitle(self, tuslar: set[tuple[int, bool]], dugmeler: set[int]):
        """Göndericinin nabızla bildirdiği basılı listesine göre düzelt (UDP'de kaybolan paket olursa)."""
        for t in list(self.basili_tuslar - tuslar):
            self.tus(*t, False)
        for t in tuslar - self.basili_tuslar:
            self.tus(*t, True)
        for d in list(self.basili_dugmeler - dugmeler):
            self.fare_dugme(d, False)
        for d in dugmeler - self.basili_dugmeler:
            self.fare_dugme(d, True)
