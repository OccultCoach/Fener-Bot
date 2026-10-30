# 🏆 FENER-BOT RESMİ KARAR DEFTERİ VE MİMARİ ZAMAN ÇİZELGESİ

Bu belge; Fener-Bot'un doğumundan bugüne kadar saha tecrübeleri, canlı maç testleri ve kriz anlarında alınan **tüm kritik mimari kararların kronolojik sicilidir.** 

Gelecekte sistemde ne değişirse değişsin, geriye dönük bir referans gerektiğinde bu defterdeki tarihsel sıra ve mantık esastır.

---

## ⏱ MİMARİ GELİŞİM ZAMAN ÇİZELGESİ (ÖZET)

| # | Madde Başlığı | İlk Karar | Son Revizyon | Kapsam / Amaç |
| :-: | :--- | :-: | :-: | :--- |
| **1** | Dış Zamanlayıcı (`cron-job.org`) Mimarisi | 10 Ekim 2026 | — | GitHub schedule kör boşluklarını yok etme |
| **2** | Maç Başlamak Üzere (T-16 Dk) Zamanlaması | 12 Ekim 2026 | **30 Ekim 2026** | Bildirimi maça yarım saat kala değil, düdüğe 16 dk kala atma |
| **3** | Ertesi Gün Sabah 10:00 Kalkanı | 12 Ekim 2026 | — | Gece maçlarında maç sonu bildirimini koruma |
| **4** | Gece Nöbeti ve -210 Dk Giyotini | 12 Ekim 2026 | — | Skor API çöküşlerinde sonsuz döngüyü engelleme |
| **5** | URL Tabanlı Branş Filtresi (`is_football_match`) | 10 Ekim 2026 | — | Altyapı/basketbol sayfalarını kapıda eleme |
| **6** | Erken Çıkış (Fren) Sistemi | 10 Ekim 2026 | — | 43 gereksiz HTTP isteğini 8'e düşürme |
| **7** | Yedek Kulübesi ve 4 Kademeli Kadro Şelalesi | 14 Ekim 2026 | **30 Ekim 2026** | ESPN + FotMob + Flashscore + API-Football zinciri |
| **8** | Maçkolik (1.) ve Akıllı ESPN (2.) Skor Zırhı | 28 Ekim 2026 | — | Düdükten 30 sn sonra anlık skor alma |
| **9** | Dinamik Saat ve Kanal Değişikliği Algılayıcısı | 18 Ekim 2026 | — | TFF son dakika güncellemelerini yakalama |
| **10** | Otomatik Sezon ve Maç Özeti (Highlights) Butonu | 18 Ekim 2026 | — | Bitiş düdüğünde YouTube resmi özet butonu üretme |
| **11** | Telegram `/sil` Acil Temizlik Komutu | 10 Ekim 2026 | — | Test/hata anında mesaj kirliliğini gruptan silme |
| **12** | Dış Tetikleyici (`cron-job.org`) Mühürlü Reçetesi | 28 Ekim 2026 | — | GitHub Actions'tan bağımsız tetikleme reçetesi |
| **13** | Editoryal Zeka, Skor Psikolojisi & Kilit Ekranı | **30 Ekim 2026** | — | Skora göre ruh hali, Levent Mercan düzeltmesi |

---

## 📌 DETAYLI KARAR MADDELERİ

### 1. Dış Zamanlayıcı (cron-job.org) ve Saf Workflow Dispatch Mimarisi
* 📅 **Karar Tarihi:** 10 Ekim 2026
* **Karar:** GitHub Actions içindeki tüm `schedule:` tanımları kaldırıldı, tetikleme yetkisi tamamen bağımsız dış servis olan `cron-job.org` üzerine devredildi (`workflow_dispatch`).
* **Sebep:** GitHub Actions'ın ücretsiz paylaşımlı havuzundaki `schedule` motoru 15 dakikalık cron'larda saatlerce süren kör boşluklar (6-9 saatlik kayıp aralıklar) bırakmakta ve görevleri sessizce silmektedir (drop). Dış zamanlayıcı (`cron-job.org`) REST API üzerinden `workflow_dispatch` çağrısı yaptığında ise GitHub işi manuel bir çalışma gibi en yüksek öncelikle, saniyesi saniyesine ve sıfır gecikmeyle çalıştırmaktadır. Çift tetiklenme ve kuyruk çakışmasını engellemek için GitHub iç saati tamamen temizlenmiştir.

---

### 2. "24 Dakika" Hassasiyeti ve Maç Başlamak Üzere Zamanlaması
* 📅 **İlk Karar:** 12 Ekim 2026 *(39 Dakika Kuralı)*
* 🔄 **Revizyon Tarihi:** 30 Ekim 2026 *(24 Dakika Kuralı)*
* **Karar:** "Maç Başlamak Üzere" bildirimi maça 39 dakika kala değil, 24 dakika kala (`0 <= time_diff <= 24`) tetiklenir.
* **Sebep:** 26 Ekim Galatasaray derbisinde görüldüğü gibi bildirimin maça yarım saat kala (20:59'da) gelmesi çok erkendir. 15 dakikalık cron döngümüzde bildirim tam T-16'da (maça 16 dakika kala, takımlar tünele girerken ve taraftar ekran başına otururken) gönderilecek şekilde kapı eşiği 24 dakikaya ayarlanmıştır.

---

### 3. Ertesi Gün Sabah 10:00 Kalkanı
* 📅 **Karar Tarihi:** 12 Ekim 2026
* **Karar:** Biten bir maç, ertesi gün sabah 10:00'a kadar sıradaki maç olarak hafızada tutulur.
* **Sebep:** Gece yarısına sarkan Avrupa maçlarında, botun maçı unutup "Sonraki Maç"a atlamasını engellemek ve "Maç Bitti" bildirimini garanti altına almaktır.

---

### 4. Gece Nöbeti (Uyku Bypass) ve -210 Dk Giyotini
* 📅 **Karar Tarihi:** 12 Ekim 2026
* **Karar:** Maça kalan süre -220 dakika ile 5 dakika arasındaysa, sistem uyanık kalır. -210. dakikada maç zorla bitirilir.
* **Sebep:** Skor API'leri çökerse botun sonsuz döngüde beklemesi engellenmiştir. Sistem -210'da giyotini vurur ve yerli kaynaklardan maç skorunu çekip işi sonlandırır.

---

### 5. URL Tabanlı "U14/Genç/Basketbol" Branş Filtresi
* 📅 **Karar Tarihi:** 10 Ekim 2026
* **Karar:** `is_football_match()` fonksiyonu, maçı daha URL aşamasındayken filtreden geçirir.
* **Sebep:** Sadece A Takım maçlarına odaklanarak, altyapı ve diğer branş sayfalarını indirmeden kapıda reddetmesi sayesinde HTTP isteklerinden büyük tasarruf sağlanır.

---

### 6. Erken Çıkış (Fren) Sistemi
* 📅 **Karar Tarihi:** 10 Ekim 2026
* **Karar:** Gelecek 2 geçerli (upcoming) maç bulunduğu an HTML tarama döngüsü kırılır (`break`).
* **Sebep:** Kalan aylardaki 40 küsur maçın sayfasını boş yere indirmemek. 43 HTTP isteği 8'e düşürülmüş, botun hızı artmış ve IP ban riski sıfırlanmıştır.

---

### 7. Yedek Kulübesi ve 4 Kademeli Kadro Şelalesi (Waterfall Lineup)
* 📅 **İlk Karar:** 14 Ekim 2026 *(fenerbahce.org + beIN Sports kazıma)*
* 🔄 **Revizyon Tarihi:** 30 Ekim 2026 *(Kadro Şelalesi + Yedek Kulübesi Entegrasyonu)*
* **Karar:** "Maç Başlamak Üzere" bildirimine İlk 11'in yanına tüm yedek kulübesi (`🪑 Yedekler:`) eklendi. Eski ve ölü kaynaklar kaldırılıp 4 kademeli şelale kuruldu:
  1. **Öncelik 1 — ESPN API:** İlk 11 (mevkili) ve tüm yedek kulübesini tek yanıtta çeker. Başarılıysa diğer kaynaklar asla çalıştırılmaz (sıfır ek kota/gecikme).
  2. **Öncelik 2 — FotMob (`get_fotmob_lineup`):** ESPN yanıt vermezse devreye girer. Tüm ligler/kupalar için hem İlk 11 hem de yedekleri temiz JSON formatında sağlar.
  3. **Öncelik 3 — Flashscore Mobi (`get_flashscore_lineup`):** FotMob da bulunamazsa devreye girer. Hafif mobil HTML üzerinden ilk 11 ve yedek tablolarını çeker.
  4. **Öncelik 4 — API-Football RapidAPI (`get_api_football_lineup`):** Opsiyonel API anahtarı (`API_FOOTBALL_KEY`) tanımlıysa ve tüm önceki kaynaklar yetersiz kalırsa çağrılır.
* **Sebep:** Eski kaynakların (fenerbahce.org Cloudflare 403 engeli ve beIN Sports'un arama servisini kapatması/404) devre dışı kalması nedeniyle hem Süper Lig hem Avrupa kupalarını %100 kapsayan modern ve eksiksiz bir kadro altyapısı kurulmuştur.

---

### 8. Maçkolik (1. Sıra) ve Akıllı ESPN (2. Sıra) Hibrit Skor Mimarisi
* 📅 **Karar Tarihi:** 28 Ekim 2026 *(Restore Point v2 Mührü)*
* **Karar:** Maç bitiş düdüğü ve skor tespiti için 1. tercih olarak Maçkolik Canlı Skor servisi (`https://vd.mackolik.com/livedata?group=0`), 2. tercih olarak ise organizasyon bazlı akıllı ESPN API'si (`tur.1`, `tur.cup`, `uefa.champions`, `uefa.europa`) bağlandı.
* **Sebep:** 17 Ekim Alanyaspor maçında ESPN'in Süper Lig'i genel `all` havuzundan çıkarması ve eski NTV Spor linkinin 404 vermesi nedeniyle maç sonu bildirimi 22:44'e (-210 dk giyotinine) kadar gecikmişti. Maçkolik düdükten 30 saniye sonra "MS" verdiği için 1. sıraya alındı, ESPN ise lig bazlı taranarak çifte zırh sağlandı. 20 Ekim Slavia Prag ve 26 Ekim Galatasaray derbileri sıfır hatayla geçti.

---

### 9. Dinamik Saat ve Kanal Değişikliği Algılayıcısı
* 📅 **Karar Tarihi:** 18 Ekim 2026
* **Karar:** Bot, hafızasındaki maçla sitedeki maçı karşılaştırır. Saat veya kanalda fark varsa, `notified_matches` kontrolünü ezip gruba güncelleme uyarısı atar.
* **Sebep:** Türkiye'de TFF veya yayıncı kuruluşların maç saatlerini ve kanallarını son dakika değiştirmesi çok sıktır. Kullanıcının eski saatle ekran başında beklemesini engellemek için sistemin kendini düzeltmesi sağlanmıştır.

---

### 10. Otomatik Sezon ve Maç Özeti (Highlights) Butonu
* 📅 **Karar Tarihi:** 18 Ekim 2026
* **Karar:** Maç bittiğinde tarih üzerinden yazılım yılı ve sezonu hesaplanır, YouTube üzerinde dinamik bir özet linki oluşturulup mesaja Telegram butonu olarak eklenir.
* **Sebep:** Maç bittiğinde kullanıcının ekstra efor sarf etmeden direkt resmi özet görüntülerine tek tıkla ulaşması sağlanmıştır.

---

### 11. Telegram `/sil` Acil Temizlik Komutu
* 📅 **Karar Tarihi:** 10 Ekim 2026
* **Karar:** Telegram'dan `/sil` komutu gönderildiğinde bot, kendi attığı son mesajları gruptan temizler.
* **Sebep:** Test aşamalarında veya olası bir hata durumunda gruptaki mesaj kirliliğini (spam) anında yok etmek için geliştirilmiştir.

---

### 12. Dış Tetikleyici (cron-job.org) Tam Konfigürasyon Reçetesi
* 📅 **Karar Tarihi:** 28 Ekim 2026
* **Karar:** Gelecekte hesap silinir, token yenilenir veya servis değişirse kurulumu saniyeler içinde tekrarlayabilmek için tetikleyici parametreleri mühürlenmiştir:
  * **Hedef URL:** `https://api.github.com/repos/OccultCoach/Fener-Bot/actions/workflows/bot.yml/dispatches`
  * **Metot:** `POST`
  * **Zamanlama (Europe/Istanbul):** `14,29,44,59 10-23,0-2 * * *` *(Sabah 10:14'ten gece 02:59'a kadar her 15 dakikada bir)*
  * **Headers:**
    * `Accept`: `application/vnd.github+json`
    * `User-Agent`: `FenerBot-Trigger`
    * `Authorization`: `Bearer <GITHUB_PERSONAL_ACCESS_TOKEN>`
  * **Body:** `{"ref": "main"}`
* **Sebep:** Sistemin GitHub içindeki `schedule` kuyruğuna bir daha ASLA muhtaç olmamasını garanti altına almak.

---

### 13. Editoryal Zeka, Skor Psikolojisi ve Kilit Ekranı Mimarisi
* 📅 **Karar Tarihi:** 30 Ekim 2026
* **Karar:** 
  1. **Skor Psikolojisi:** Maç sonu bildiriminde "skor körlüğü" kaldırıldı. Galibiyette zafer coşkusu ve konfeti (`ZAFER BİZİM! 🎉`), mağlubiyette ise sıfır konfeti ile vakur ve asil bir duruş (`Başını dik tut Fenerbahçeli!`) getirildi.
  2. **Kilit Ekranı Hiyerarşisi:** Bildirimin ilk 2 satırına doğrudan Karşılaşma ve Saat çekildi; gövdedeki çift başlık kirliliği temizlendi.
  3. **İsim & Dil Sterilizasyonu:** ESPN kaynaklı `Munir Mercan` otomatik olarak **`Levent Mercan`**'a dönüştürüldü. Eksik Türkçe karakterler (`Oguz Aydin` -> `Oğuz Aydın`) yerelleştirildi.
  4. **Kompakt Kadro Formatı:** İlk 11 dizilimi nokta (`•`) ayraçlı bülten düzenine geçirilerek dikey mesaj taşması önlendi.
* **Sebep:** Botun sadece veri basan soğuk bir robot değil, taraftarın psikolojisini anlayan ve telefonda ilk bakışta en doğru bilgiyi veren premium bir kulüp bülteni olmasını sağlamak.
