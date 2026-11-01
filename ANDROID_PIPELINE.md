# Android Uygulaması Üretim ve Derleme Mimarisi (Production Pipeline)

Bu doküman; Minis AI Agent ortamında Android uygulaması üretirken, derlerken ve dağıtırken izlenecek **bütünsel üretim mimarisini, derleyici hiyerarşisini, bağımlılık grafiğini ve yetki protokolünü** tanımlar.

---

## 1. Görevleme ve İş Sırası (Job & Task Execution Order)

Bir Android projesinin sıfırdan üretilmesi ve derlenmesi 8 kesin aşamadan oluşur:

```
[1. Pre-flight Analiz]
       │  (SDK, Gradle, Manifest, Paket Doğrulama)
       ▼
[2. Bağımlılık Çözümleme & Önbellek]
       │  (Maven Central, Google Maven, Gradle Cache)
       ▼
[3. Kaynak Derleme & Birleştirme (AAPT2)]
       │  (XML Linting, Layout Parse, R.java Üretimi)
       ▼
[4. Yerel / C++ / Go Bağlama (JNI / Gobind)]
       │  (Gomobile, NDK, Shared Object .so üretimi)
       ▼
[5. Kod Derleme (Kotlinc & Javac)]
       │  (KSP/KAPT Annotation Processing, Bytecode .class)
       ▼
[6. Dexing, Minification & Birleştirme (D8 & R8)]
       │  (.class -> .dex dönüşümü, Proguard kuralları)
       ▼
[7. Paketleme & İmzalama (APK/AAB Builder & Apksigner)]
       │  (Manifest Merger, Resources.arsc, Zipalign, V2/V3 İmza)
       ▼
[8. Doğrulama, Artefakt İndirme & Geri Bildirim]
          (Minis Chat'e bildirim, log teşhisi, APK teslimi)
```

---

## 2. Derleyiciler, Parçalayıcılar ve Birleştiriciler

| Bileşen | Görevi | İşlev Tipi | Hata Durumunda Teşhis |
|---|---|---|---|
| **AAPT2** | Android Asset Packaging Tool 2 | Parçalayıcı & Kaynak İlişkilendirici | XML yazım hataları, eksik drawable veya color tanımları |
| **Manifest Merger** | Çoklu kütüphane manifestolarını tek `AndroidManifest.xml`'e bağlar | Birleştirici | Çakışan `android:allowBackup` veya SDK seviyesi uyumsuzlukları |
| **Kotlinc / Javac** | Kotlin ve Java kaynak kodlarını JVM bytecode'a derler | Ana Derleyici | `Unresolved reference`, tip uyuşmazlığı, eksik import |
| **KSP / KAPT** | Annotation processor (Room, Hilt, Compose) | Kod Üretici | Eksik bağımlılık, plugin sürüm çakışması |
| **Gobind / NDK** | Go ve C/C++ kodlarını Android JNI kütüphanelerine (.so / .aar) dönüştürür | Yerel Derleyici | `gobind was not found`, clang linking hatası |
| **D8 / R8** | Java bytecode'unu Android Dalvik çalıştırılabilirlerine (`.dex`) çevirir, küçültür ve optimize eder | Birleştirici & Optimize Edici | Sınıf çakışması (`Duplicate class`), ProGuard eksik `-keep` |
| **Zipalign & Apksigner** | APK arşivini 4-byte hizalar ve V2/V3 şifreleme imzası atar | Paketleyici | Keystore şifre veya alias hataları |

---

## 3. Paralel Bağlılık, Bağımlılık ve Kütüphane Yönetimi

* **Paralel Çalıştırma:**
  * Bağımsız görevler (örneğin UI bileşen analizi, string lokalizasyonu ve test senaryoları) Minis PRoot içinde paralel planlanır.
  * GitHub Actions üzerinde `./gradlew --parallel --build-cache` bayraklarıyla çoklu çekirdek desteği kullanılır.
* **Bağımlılık İhtiyaç Sırası:**
  1. `androidx.core:core-ktx` (Temel Android API'leri)
  2. `androidx.compose.*` veya `androidx.appcompat` (Arayüz katmanı)
  3. `org.jetbrains.kotlinx:kotlinx-coroutines-*` (Eşzamanlılık ve asenkron akışlar)
  4. Yerel kütüphaneler (`.aar`, JNI bindings).
* **Önbellekleme:**
  * GitHub Actions üzerinde `~/.gradle/caches` ve `~/.gradle/wrapper` katmanları önbelleğe alınarak derleme süreleri %70 kısaltılır.

---

## 4. Takip ve Canlı Geri Bildirim Döngüsü (Feedback Loop)

1. **Ön Uçuş Kontrolü (`preflight_check`):**
   * Buluta gönderilmeden önce yerelde `dependency_graph.py` çalıştırılır. SDK sürümleri, Manifest izinleri ve dosya yapısı doğrulanır.
2. **Canlı İzleme (`build_monitor.py`):**
   * GitHub Actions API üzerinden çalıştırma durumu her 15 saniyede bir sorgulanır (`in_progress`, `queued`, `completed`).
3. **Akıllı Hata Teşhisi:**
   * Bir hata durumunda ham loglar yerine doğrudan `build_monitor.py` devreye girer. AAPT2, Kotlinc, Gomobile veya SDK lisans hatasını ayrıştırarak Minis chat ekranına **kesin çözüm önerisiyle** raporlar.
4. **Artefakt Teslimatı:**
   * Başarılı derlemede üretilen `.apk` ve `.aab` dosyaları otomatik olarak `/var/minis/workspace/artifacts/` dizinine indirilir ve kullanıcıya sunulur.

---

## 5. Terminal, Erişim ve Tam Yetki Protokolü

* **Önceden Verilen Tam Yetki:**
  * Depo oluşturma, GitHub Actions iş akışlarını tetikleme, logları okuma, Codespaces başlatma ve durdurma yetkileri `GITHUB_TOKEN` üzerinden tam yetkilendirilmiştir.
  * Ara onay adımları beklenmeksizin derleme, doğrulama, hata ayıklama ve düzeltme döngüsü özerk olarak işletilir.
* **Seviye Hiyerarşisi:**
  * **1. Seviye (Yerel Minis PRoot):** Kodlama, paketleme, orkestrasyon, dosya yönetimi.
  * **3. Seviye (GitHub Actions):** Ağır derlemeler, APK/AAB inşası, test otomasyonu.
  * **4. Seviye (GitHub Codespaces):** İnteraktif hata ayıklama, bulut terminali.

---

## 6. Pipeline Script & Module Reference (`scripts/android_pipeline/`)

- **`guardians.py`**: Manifest security compliance and debug flags check.
- **`vault_crypto.py`**: AES-256 Fernet encryption and binary `.jks` keystore base64 encoding/decoding.
- **`memory_manager.py`**: Multi-tier memory states (compilation, packaging, transient).
- **`size_optimizer.py`**: APK size calculation, ABI splitting, and asset metrics.
- **`cache_engine.py`**: Stale Gradle cache and build directory cleanup.
- **`auto_fixer.py`**: Closed-loop self-healing engine (Manifest permissions, ProGuard `-keep` rules).
- **`gitops_manager.py`**: AI-driven branch creation, PR generation, and merging.
- **`ota_bridge.py`**: On-device OTA installation and preview bridge.
- **`apk_profiler.py`**: DEX method count and component composition inspector.
- **`autonomous_nexus.py`**: Cybernetic meta-controller for telemetry and end-to-end autonomous loops.
- **`autonomous_daemon.py`**: Asynchronous background watcher daemon for automated polling and healing.

---

## 7. Elite Pipeline Modules Reference (`scripts/android_pipeline/`)

- **`builidroid_fixer.py`**: Advanced semantic error analysis and patch generation (>90% compilation success rate).
- **`appium_bridge.py`**: Translates natural language UI test commands into Appium WebDriver automation.
- **`security_acl.py`**: Enforces command/path scoping and Human-In-The-Loop (HITL) approval gates.
- **`project_detector.py`**: Automatically detects project architecture (Native Android, Flutter, React Native, KMP).
- **`version_bumper.py`**: Dynamically calculates and bumps `versionCode` and `versionName` from Git history.
- **`dashboard_generator.py`**: Produces a real-time HTML telemetry and monitoring dashboard from `metrics.jsonl`.
- **`setup_wizard.py`**: Indie hacker interactive onboarding script for 1-click environment priming.
