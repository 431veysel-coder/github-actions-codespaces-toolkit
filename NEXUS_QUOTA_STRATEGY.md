# GITHUB ACTIONS KOTA VE LİMİT KORUMA STRATEJİSİ (NEXUS OS)

**Tarih:** 2026-11-02  
**Amaç:** GitHub Actions aylık 2.000 dakika ücretsiz derleme kotasını korumak, sunucu timeout risklerini sıfırlamak ve cihaz (Minis PRoot) üzerindeki donanım kısıtlarını aşan hibrit bir derleme mimarisi kurmak.

---

## 🏛️ 1. GİTHUB KISITLARI VE ALINAN SİSTEMİK ÖNLEMLER

| GitHub Actions Kısıtı / Engeli | Olası Risk | Nexus OS Hibrit Çözümü & Optimizasyon |
| :--- | :--- | :--- |
| **Aylık Dakika Kotası (2.000 dk Limit)** | Sürekli yapılan küçük commit'lerde kotanın hızla tükenmesi. | **1. Path Filtering:** Sadece `apps/minis-nexus/**` değiştiğinde çalışır.<br>**2. Pre-flight Check (Seviye 1):** Cihazda syntax hatası veya eksik paket varsa buluta gönderilmeden lokal engellenir. |
| **Uzun Derleme Süreleri (15-20 dk)** | Sıfırdan Gradle/SDK indirme sebebiyle sürelerin uzaması. | **Aggressive Caching (`actions/cache@v3`):** Gradle wrapper ve dependency cache'leri hafızada tutulur. Derleme süresi 15 dakikadan **2-3 dakikaya** düşürülür ( Kota harcaması %80 azalır). |
| **Runner Out-Of-Memory (OOM)** | Gradle daemon'ın 7GB RAM sınırını aşarak çökmesi. | **JVM Tuning (`gradle.properties`):** `org.gradle.jvmargs=-Xmx3g -XX:+UseG1GC` ile bellek optimize edildi. |
| **İnteraktif Hata Ayıklama İhtiyacı** | Bulut loglarında hatayı çözemeyip sürekli deneme-yanılma yapmak. | **Seviye 4 (Codespaces Katmanı):** Yılda 180 saat ücretsiz verilen Codespaces cloud VM'i kullanılarak canlı Docker/Linux terminali üzerinden anında debug yapılır. |

---

## 🔄 2. HİBRİT DERLEME DÖNGÜSÜ (1 - 3 - 4 HİYERARŞİSİ)

```
[Seviye 1: Minis PRoot (Cihaz İçi)]
    │  - Kod yazımı, UI tasarımı, Manifest düzenleme
    │  - Pre-flight syntax kontrolü (Sıfır Hatalı Push)
    ▼
[Seviye 3: GitHub Actions (Bulut CI)]
    │  - Path filtering tetiklenir
    │  - Cache'ten Gradle bağımlılıkları çekilir (2-3 dk)
    │  - APK derlenir, imzalanır ve Artifact olarak paketlenir
    ▼
[Seviye 4: GitHub Codespaces (Canlı VM Debug - İhtiyaç Halinde)]
    │  - Derleme hatası tekrar ederse canlı bulut terminalinde inceleme
```

---

## 🛡️ 3. KENDİNİ ONARMA VE OTOMASYON (CIRCUIT BREAKER)
* Toolkit bünyesindeki `auto_fixer.py` ve `builidroid_fixer.py`, GitHub Actions build loglarını otomatik dinler.
* SDK lisans hatası, AAPT2 veya ProGuard hatası durumunda düzeltmeyi bulutta uygulayıp yeni commit atar.
* **Circuit Breaker:** Aynı hata parmak izi için maksimum 3 deneme hakkı tanınır; böylece sonsuz build döngüleri ve kota israfı kesin olarak engellenir.
