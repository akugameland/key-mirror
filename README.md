# Key Mirror (Tuş Yansıt)

**English** · [Türkçe](#türkçe)

Press keys and use the **mouse** on one Windows PC, and the same input is pressed on a second PC on your home
network at the same time. **The receiver chooses which keys** (default: W A S D, Shift, Ctrl). Nothing else is sent.

- Two roles in one app: **Sender** (the PC you use) and **Receiver** (the PC that repeats the input).
- **Choose the keys on the receiver:** press **Add key**, then press the key on the receiver's own keyboard.
  Select a key and press **Remove selected** to take it off, or **Reset to default**. The Windows key, the menu key
  and F1–F12 / Scroll Lock can never be added.
- **Choose the mouse on the receiver:** tick or untick left click, right click, middle click, side buttons 1 and 2,
  wheel (scroll) and movement one by one. The sender never sends what the receiver has turned off.
- Mirroring starts **off**; toggle it with **F7** (changeable to F1–F12 / Scroll Lock). While it is on, a red
  `● MIRRORING ON` label stays in the top-left corner of the sender, and `● REMOTE INPUT` on the receiver.
- Mouse: movement, left/right/middle/side buttons and wheel; each one can be turned off on the receiver, and the
  whole mouse can be turned off on the sender.
- Turkish and English interface. Python standard library only: no third-party packages.

## Security

Built to be safe on a home network:

- **Whitelist on both sides, chosen by the receiver.** The receiver sends its key list to the sender inside the
  encrypted, signed heartbeat. The sender only ever sends keys on that list (plus the mouse); every other key never
  leaves the PC. The receiver also refuses to press any key outside its list, even if one arrives.
- **Typing while mirroring is on:** if the receiver adds letter keys, anything you type with those letters on the
  sender (for example in chat) is also typed on the receiver. Turn mirroring off with F7 before typing passwords or
  chat.
- **Pairing code.** The receiver shows a random 10-character code (~50 bits). The code itself is never sent over the
  network; it is only used to derive the keys (PBKDF2-SHA256, 200,000 rounds).
- **Encrypted and signed packets.** Each packet is encrypted (HMAC-SHA256 keystream) and signed (HMAC-SHA256).
  Without the code, nobody can read, forge or alter packets.
- **No replay.** Sequence numbers only grow, and the receiver uses a new random value on every start, so recorded
  packets are useless.
- **Local network only.** Packets from public (internet) addresses are dropped, even if a port is forwarded by mistake.
- **One sender at a time.** While a sender is connected, other devices are refused.
- **No stuck keys.** If packets stop for 1 second, the receiver releases every held key and button. A heartbeat every
  200 ms resynchronises held keys if a UDP packet is lost.
- **Nothing is logged.** `hata.log` only records connects and on/off events, never keys. No admin rights needed.
  Settings (`ayarlar.json`, contains the code) stay local and are not part of this repository.

**Firewall:** on the first start of the receiver, Windows asks whether Python may use the network. Allow it for
**Private networks** only.

## Games: read this

Many online games treat software-generated input as automation, and controlling two game clients at once
("multiboxing") is against the rules of many games and can get accounts banned. Anti-cheat software may also ignore
injected input. Check the rules of your game before using this. Use at your own risk.

If the program on the receiver runs as administrator, Windows does not allow a normal app to press keys into it;
the receiver shows a red warning and you can start it as administrator (right-click `BASLAT.bat`).

## Install and use

1. Download the repo (Code → Download ZIP) on **both** PCs and extract it.
2. Double-click `BASLAT.bat`. On first start it runs `KURULUM.bat`, which installs Python 3.12 if missing (via winget,
   no admin rights needed). Re-running it is safe.
3. On the receiving PC choose **Receiver**. Note the pairing code.
4. On the sending PC choose **Sender**, type the code and press **Find and connect** (or type the receiver's address
   shown on its screen). "Receiver is answering" means you are connected.
5. Press **F7** to start mirroring, **F7** again to stop.

## Updating

Version 4 of the network protocol (receiver-chosen keys and mouse) does not talk to older copies: update **both** PCs.
This update also fixes left / right / middle / side clicks and the wheel, which were not picked up on the sender.

## License

MIT. See [LICENSE](LICENSE).

---

## Türkçe

Bir Windows bilgisayarda tuşlara basıp **fareyi** kullandığında, aynı girdi ev ağındaki ikinci bilgisayarda da aynı
anda basılır. **Hangi tuşların gideceğini alan seçer** (varsayılan: W A S D, Shift, Ctrl). Başka hiçbir şey gönderilmez.

- Tek programda iki rol: **Gönderen** (kullandığın bilgisayar) ve **Alan** (girdiyi tekrarlayan bilgisayar).
- **Tuşları alanda seç:** **Tuş ekle**'ye bas, sonra alanın kendi klavyesinde o tuşa bas. Çıkarmak için listeden seçip
  **Seçileni çıkar**, baştaki listeye dönmek için **Varsayılana dön**. Windows tuşu, menü tuşu ve F1–F12 / Scroll Lock
  hiçbir zaman eklenemez.
- **Fareyi alanda seç:** sol tık, sağ tık, orta tık, yan tuş 1 ve 2, tekerlek (kaydırma) ve hareket kutularını tek tek
  işaretle ya da kaldır. Alanın kapattığını gönderen hiç yollamaz.
- Yansıtma **kapalı** başlar; **F7** ile açılıp kapanır (F1–F12 ya da Scroll Lock yapılabilir). Açıkken gönderende
  sol üstte kırmızı `● YANSITMA AÇIK`, alanda `● UZAKTAN GİRDİ` yazısı durur.
- Fare: hareket, sol/sağ/orta/yan tuşlar ve tekerlek; her biri alanda ayrı kapatılabilir, gönderende de farenin
  tamamı kapatılabilir.
- Türkçe ve İngilizce arayüz. Yalnız Python standart kütüphanesi, ek paket yok.

**Güvenlik:**
- İki taraflı beyaz liste, alan seçer: alan listesini şifreli ve imzalı nabız cevabıyla gönderene bildirir. Gönderen
  yalnız o listedeki tuşları yollar; listede olmayan hiçbir tuş bilgisayardan çıkmaz. Alan da listede olmayanı asla basmaz.
- Yansıtma açıkken yazı yazma: alan harf tuşları eklediyse, gönderende o harflerle yazdığın her şey (ör. sohbet) alanda
  da yazılır. Şifre ya da sohbet yazmadan önce F7 ile yansıtmayı kapat.
- 10 karakterlik eşleştirme kodu ağdan hiç gönderilmez; yalnız anahtar türetmede kullanılır.
- Paketler şifreli ve imzalıdır. Kodu bilmeyen paketleri okuyamaz, uyduramaz, değiştiremez.
- Kaydedilmiş eski paketler tekrar gönderilse de işe yaramaz.
- Yalnız ev ağından gelen paket kabul edilir, internetten gelen atılır.
- Aynı anda tek gönderen bağlanabilir.
- Paket 1 saniye gelmezse alan basılı her şeyi bırakır; takılı tuş kalmaz.
- Tuşlar hiçbir yere kaydedilmez. Yönetici izni gerekmez. Kodun durduğu `ayarlar.json` depoya girmez.
- Güvenlik duvarı: alan ilk açıldığında Windows izin sorar. Yalnız **Özel ağlar** için izin ver.

**Oyunlar için uyarı:** Birçok çevrimiçi oyun, programla basılan girdiyi otomasyon sayar. İki oyun istemcisini aynı
anda yönetmek (multiboxing) birçok oyunun kurallarına aykırıdır ve hesabın kapatılmasına yol açabilir. Hile korumaları
programla basılan tuşları yok sayabilir. Kullanmadan önce oyununun kurallarına bak; sorumluluk kullanıcıdadır.

**Güncelleme:** Bu sürümün ağ protokolü (sürüm 4) eski kopyalarla konuşmaz; **iki bilgisayarı da** güncelle. Bu sürüm
gönderende hiç algılanmayan sol / sağ / orta / yan tıkları ve tekerleği de düzeltir.

**Kurulum:** Depoyu **iki bilgisayara da** indir (Code → Download ZIP), klasöre çıkar, `BASLAT.bat`'a çift tıkla.
Python 3.12 yoksa kendisi kurar. Alan bilgisayarda **Alan** seç ve kodu not al. Gönderende **Gönderen** seç, kodu yaz,
**Bul ve bağlan**'a bas. **F7** ile aç ve kapat. Ayrıntı: [OKU_BENI.txt](OKU_BENI.txt)
