"""Ağ: yalnız yerel ağ, UDP. Paketler eşleştirme kodundan türetilen anahtarlarla şifrelenir ve imzalanır.

Güvenlik (kullanıcı isteği 2026-10-17: "güvenli yap, riske atma"):
- Kod 10 karakter (31 harfli alfabe, ~50 bit). Ağdan hiç gönderilmez; yalnız anahtar türetmek için kullanılır.
  Anahtar: PBKDF2-SHA256(kod, 200 000 tur) -> ayrı şifreleme ve imza anahtarları.
- İmza: HMAC-SHA256 (16 bayt). Kodu bilmeyen paket uyduramaz ya da değiştiremez; imzası tutmayan paket atılır.
- Şifreleme: HMAC-SHA256 tabanlı anahtar akışı (sayaç kipi), şifrele-sonra-imzala. Ağı dinleyen hangi tuşa
  basıldığını göremez. (Yalnız standart kütüphane; AES yok. Her paketin (oturum, sıra) çifti tekildir.)
- Tekrar gönderme: alan her açılışta rastgele bir "alan nonce" üretir; paketler onu taşımak zorundadır.
  Eski bir çalışmadan kaydedilen paketler bu yüzden reddedilir. Aynı çalışmada sıra numarası yalnız büyür.
- Yalnız özel ağ adresleri (192.168.x, 10.x, 172.16-31.x, link-local) kabul edilir: modemde port açılsa bile
  internetten gelen paket uygulanmaz.
- Aynı anda tek gönderen: bir gönderen bağlıyken (son 5 sn içinde paket geldiyse) başka oturum kabul edilmez.
- Alan yalnız beyaz listedeki tuşları basar (girdi.TUSLAR); başka tuş gelirse uygulanmaz.

Paket: b"TY" | sürüm(1) | tür(1) | oturum(8) | alan_nonce(8) | sıra(8) | şifreli içerik | imza(16)

UDP'de paket kaybolabilir: gönderen 200 ms'de bir "nabız" ile basılı tuş/düğme listesini yollar, alan buna göre
düzeltir. Alan 1 sn paket almazsa basılı her şeyi bırakır (takılı kalan W olmasın).
"""
import hashlib
import hmac
import ipaddress
import logging
import os
import secrets
import socket
import struct
import threading
import time

log = logging.getLogger("ag")

PORT = 47810
SURUM = 2
ALFABE = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"            # karışan harfler yok (0/O, 1/I/L)
KOD_UZUNLUK = 10
KESIF, KESIF_CEVAP, TUS, HAREKET, DUGME, TEKER, NABIZ, NABIZ_CEVAP, BIRAK = range(1, 10)
_BAS = struct.Struct("<2sBB8s8sQ")
IMZA = 16
ZAMAN_ASIMI = 1.0                                     # alan: bu kadar paket gelmezse hepsini bırak
TEK_GONDEREN_SN = 5.0                                 # bu süre içinde başka gönderen kabul edilmez
NABIZ_SN = 0.2
BOS_NONCE = bytes(8)


def yeni_kod() -> str:
    return "".join(secrets.choice(ALFABE) for _ in range(KOD_UZUNLUK))


def kod_duzelt(kod: str) -> str:
    return "".join(c for c in kod.upper() if c.isalnum())


def kod_gecerli(kod: str) -> bool:
    k = kod_duzelt(kod)
    return len(k) == KOD_UZUNLUK and all(c in ALFABE for c in k)


def kod_goster(kod: str) -> str:
    k = kod_duzelt(kod)
    return f"{k[:5]}-{k[5:]}"


def ozel_adres_mi(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (a.is_private or a.is_link_local) and not a.is_unspecified and not a.is_multicast


def yerel_adresler() -> list[str]:
    """Bu bilgisayarın yerel ağ adresleri; asıl (varsayılan yoldaki) adres başta. Diğerleri çoğunlukla sanal
    bağdaştırıcılardır (Hyper-V, WSL, VPN)."""
    asil = None
    for deneme in ("192.168.255.255", "10.255.255.255"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((deneme, 1))                 # paket gitmez; yalnız çıkış arayüzünü öğrenir
                asil = s.getsockname()[0]
                break
        except OSError:
            continue
    digerleri = set()
    try:
        for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            digerleri.add(a[4][0])
    except OSError:
        pass
    temiz = [a for a in sorted(digerleri - {asil}) if ozel_adres_mi(a) and not a.startswith("127.")]
    return ([asil] if asil and ozel_adres_mi(asil) and not asil.startswith("127.") else []) + temiz


class Paketci:
    def __init__(self, kod: str):
        ana = hashlib.pbkdf2_hmac("sha256", kod_duzelt(kod).encode(), b"TusYansit/2", 200_000)
        self._sifre = hmac.new(ana, b"sifreleme", hashlib.sha256).digest()
        self._imza = hmac.new(ana, b"imza", hashlib.sha256).digest()

    def _akis(self, tur: int, oturum: bytes, nonce: bytes, sira: int, uzunluk: int) -> bytes:
        cikti, sayac = b"", 0
        while len(cikti) < uzunluk:
            cikti += hmac.new(self._sifre, struct.pack("<B8s8sQI", tur, oturum, nonce, sira, sayac),
                              hashlib.sha256).digest()
            sayac += 1
        return cikti[:uzunluk]

    def paketle(self, tur: int, oturum: bytes, nonce: bytes, sira: int, icerik: bytes = b"") -> bytes:
        sifreli = bytes(a ^ b for a, b in zip(icerik, self._akis(tur, oturum, nonce, sira, len(icerik))))
        govde = _BAS.pack(b"TY", SURUM, tur, oturum, nonce, sira) + sifreli
        return govde + hmac.new(self._imza, govde, hashlib.sha256).digest()[:IMZA]

    def coz(self, veri: bytes):
        """(tür, oturum, nonce, sıra, içerik) ya da None (bozuk / imzası tutmayan / başka sürüm)."""
        if len(veri) < _BAS.size + IMZA or len(veri) > 512:
            return None
        govde, imza = veri[:-IMZA], veri[-IMZA:]
        if not hmac.compare_digest(imza, hmac.new(self._imza, govde, hashlib.sha256).digest()[:IMZA]):
            return None
        sihir, surum, tur, oturum, nonce, sira = _BAS.unpack_from(govde)
        if sihir != b"TY" or surum != SURUM:
            return None
        sifreli = govde[_BAS.size:]
        icerik = bytes(a ^ b for a, b in zip(sifreli, self._akis(tur, oturum, nonce, sira, len(sifreli))))
        return tur, oturum, nonce, sira, icerik


def nabiz_icerigi(acik: bool, tuslar: set, dugmeler: set) -> bytes:
    """acik: gönderende yansıtma açık mı (alan göstergesi buna bakar) + basılı tuşlar + düğme maskesi."""
    t = sorted(tuslar)[:16]
    return (bytes([int(acik), len(t)]) + b"".join(bytes([k, int(e)]) for k, e in t)
            + bytes([sum(1 << d for d in dugmeler) & 0x1F]))


def nabiz_coz(icerik: bytes) -> tuple[bool, set, set]:
    n = min(icerik[1], 16)
    if len(icerik) < 3 + 2 * n:
        raise ValueError("kısa nabız")
    tuslar = {(icerik[2 + 2 * i], bool(icerik[3 + 2 * i])) for i in range(n)}
    maske = icerik[2 + 2 * n]
    return bool(icerik[0]), tuslar, {d for d in range(5) if maske >> d & 1}


# ── alan ─────────────────────────────────────────────────────────────────────
class Alici:
    """Gelen paketleri basici'ye uygular. durum(olay, *bilgi) arayüze haber verir (kendi iş parçacığında)."""

    def __init__(self, kod: str, basici, ad: str, durum=lambda *a: None, port: int = PORT):
        self.paketci, self.basici, self.ad, self.durum = Paketci(kod), basici, ad, durum
        self.nonce = os.urandom(8)                     # her açılışta yeni: eski kayıtlı paketler geçersiz
        self.etkin = True                              # arayüzdeki "gelen tuşları uygula" anahtarı
        self.uzak_acik = False                         # gönderende yansıtma açık mı (gösterge için)
        self.son_paket = 0.0
        self.gonderen = None                           # (ip, port)
        self._oturum = None
        self._son_sira = -1
        self.sayac = {"kabul": 0, "red": 0}
        self._calisiyor = True
        self.soket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.soket.bind(("0.0.0.0", port))
        self.soket.settimeout(0.2)
        threading.Thread(target=self._dinle, daemon=True, name="alici").start()

    def kapat(self):
        self._calisiyor = False
        self.basici.hepsini_birak()
        try:
            self.soket.close()
        except OSError:
            pass

    def _dinle(self):
        while self._calisiyor:
            try:
                veri, adres = self.soket.recvfrom(2048)
            except socket.timeout:
                self._bekci()
                continue
            except OSError:
                if not self._calisiyor:
                    return
                continue
            try:
                self._isle(veri, adres)
            except Exception:  # noqa: BLE001
                log.exception("paket işleme")
            self._bekci()

    def _bekci(self):
        if (self.basici.basili_tuslar or self.basici.basili_dugmeler) and time.time() - self.son_paket > ZAMAN_ASIMI:
            log.info("gönderenden %s sn paket gelmedi: basılı her şey bırakıldı", ZAMAN_ASIMI)
            self.basici.hepsini_birak()
            self.durum("koptu")

    def _reddet(self):
        self.sayac["red"] += 1

    def _isle(self, veri: bytes, adres):
        if not ozel_adres_mi(adres[0]):                # internetten gelen: asla
            return self._reddet()
        p = self.paketci.coz(veri)
        if p is None:
            return self._reddet()
        tur, oturum, nonce, sira, icerik = p
        simdi = time.time()
        baska = self._oturum is not None and oturum != self._oturum and simdi - self.son_paket < TEK_GONDEREN_SN
        if tur == KESIF:                               # bul isteği: yalnız aynı kodu bilen cevap alır
            if not baska:
                self.soket.sendto(self.paketci.paketle(KESIF_CEVAP, oturum, self.nonce, sira,
                                                       icerik[:8] + self.ad.encode()[:60]), adres)
            return
        if nonce != self.nonce:                        # nonce'u bilmiyor (yeni bağlanıyor ya da eski kayıt)
            if tur == NABIZ and not baska:             # nabıza nonce'la cevap ver; hiçbir girdi uygulanmaz
                self.soket.sendto(self.paketci.paketle(NABIZ_CEVAP, oturum, self.nonce, sira, b"0"), adres)
            return self._reddet()
        if baska:                                      # başka bir gönderen bağlı
            return self._reddet()
        if oturum != self._oturum:
            self._oturum, self._son_sira = oturum, -1
        if sira <= self._son_sira:                     # eski / tekrar gönderilmiş paket
            return self._reddet()
        self._son_sira = sira
        self.sayac["kabul"] += 1
        self.son_paket = simdi
        if self.gonderen != adres:
            self.gonderen = adres
            self.durum("baglandi", adres[0])
        if tur == NABIZ:
            self.soket.sendto(self.paketci.paketle(NABIZ_CEVAP, oturum, self.nonce, sira,
                                                   b"1" if self.etkin else b"2"), adres)
        if not self.etkin:
            self.uzak_acik = False
            self.basici.hepsini_birak()
            return
        if tur == TUS and len(icerik) >= 3:
            self.basici.tus(icerik[0], bool(icerik[1]), bool(icerik[2]))
        elif tur == HAREKET and len(icerik) >= 4:
            dx, dy = struct.unpack("<hh", icerik[:4])
            self.basici.fare_hareket(dx, dy)
        elif tur == DUGME and len(icerik) >= 2:
            self.basici.fare_dugme(icerik[0], bool(icerik[1]))
        elif tur == TEKER and len(icerik) >= 3:
            miktar, yatay = struct.unpack("<hB", icerik[:3])
            self.basici.teker(miktar, bool(yatay))
        elif tur == NABIZ and len(icerik) >= 3:
            acik, tuslar, dugmeler = nabiz_coz(icerik)
            self.uzak_acik = acik
            if acik:
                self.basici.esitle(tuslar, dugmeler)
            else:
                self.basici.hepsini_birak()
        elif tur == BIRAK:
            self.uzak_acik = False
            self.basici.hepsini_birak()


# ── gönderen ─────────────────────────────────────────────────────────────────
class Gonderici:
    def __init__(self, kod: str):
        self.paketci = Paketci(kod)
        self.oturum = os.urandom(8)
        self.sira = 0
        self.hedef = None                              # (ip, port)
        self.nonce = BOS_NONCE                         # alanın bu açılıştaki değeri (nabız cevabından öğrenilir)
        self.son_cevap = 0.0
        self.alan_durumu = ""                          # "1": uyguluyor, "2": alanda uygulama kapalı
        self._kilit = threading.Lock()
        self.soket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.soket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.soket.bind(("0.0.0.0", 0))
        self.soket.settimeout(0.2)
        self._bulunan: dict[str, str] = {}
        self._kesif_nonce = b""
        self._calisiyor = True
        threading.Thread(target=self._cevaplari_dinle, daemon=True, name="gonderici").start()

    def kapat(self):
        self._calisiyor = False
        try:
            self.soket.close()
        except OSError:
            pass

    def hedefle(self, ip: str):
        if not ozel_adres_mi(ip):
            raise ValueError("yalnız yerel ağ adresi")
        if not self.hedef or self.hedef[0] != ip:
            self.hedef, self.nonce = (ip, PORT), BOS_NONCE

    def _yolla(self, tur: int, icerik: bytes = b"", adres=None):
        adres = adres or self.hedef
        if not adres:
            return
        with self._kilit:
            self.sira += 1
            paket = self.paketci.paketle(tur, self.oturum, self.nonce, self.sira, icerik)
        try:
            self.soket.sendto(paket, adres)
        except OSError as h:
            log.debug("gönderilemedi: %s", h)

    def bul(self, sure: float = 1.5) -> dict[str, str]:
        """Aynı kodu kullanan alanları yerel ağda arar: {ip: ad}."""
        self._bulunan = {}
        self._kesif_nonce = os.urandom(8)
        for hedef in {"255.255.255.255"} | {a.rsplit(".", 1)[0] + ".255" for a in yerel_adresler()}:
            self._yolla(KESIF, self._kesif_nonce, (hedef, PORT))
        time.sleep(sure)
        return dict(self._bulunan)

    def _cevaplari_dinle(self):
        while self._calisiyor:
            try:
                veri, adres = self.soket.recvfrom(2048)
            except (socket.timeout, OSError):
                continue
            if not ozel_adres_mi(adres[0]):
                continue
            p = self.paketci.coz(veri)
            if p is None:
                continue
            tur, oturum, nonce, sira, icerik = p
            if oturum != self.oturum:
                continue
            if tur == KESIF_CEVAP and self._kesif_nonce and icerik[:8] == self._kesif_nonce:
                self._bulunan[adres[0]] = icerik[8:].decode(errors="replace")
            elif tur == NABIZ_CEVAP and self.hedef and adres[0] == self.hedef[0]:
                self.nonce = nonce
                self.son_cevap = time.time()
                self.alan_durumu = icerik[:1].decode(errors="replace")

    def bagli_mi(self) -> bool:
        return time.time() - self.son_cevap < 1.0 and self.alan_durumu in ("1", "2")

    # olaylar (alanın nonce'u öğrenilmeden gönderilenler alanda reddedilir; nabız hemen öğretir)
    def tus(self, tarama: int, e0: bool, basili: bool):
        self._yolla(TUS, bytes([tarama, int(e0), int(basili)]))

    def hareket(self, dx: int, dy: int):
        while dx or dy:                                # çok büyük sıçrama: parçalara böl
            px, py = max(-32767, min(32767, dx)), max(-32767, min(32767, dy))
            self._yolla(HAREKET, struct.pack("<hh", px, py))
            dx, dy = dx - px, dy - py

    def dugme(self, no: int, basili: bool):
        self._yolla(DUGME, bytes([no, int(basili)]))

    def teker(self, miktar: int, yatay: bool):
        self._yolla(TEKER, struct.pack("<hB", max(-32768, min(32767, miktar)), int(yatay)))

    def nabiz(self, acik: bool, tuslar: set, dugmeler: set):
        self._yolla(NABIZ, nabiz_icerigi(acik, tuslar, dugmeler))

    def birak(self):
        self._yolla(BIRAK)
