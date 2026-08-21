# RH-NBV Fonksiyon Savunmaları

Her fonksiyon için üç soru: **Ne yapıyor? Neden var? Neden böyle yapıldı?**
(Kod referansları `rh_planner.py` içindir.)

---

## 1. `rh_view()` — ana receding-horizon adımı (satır 476)

**Ne yapıyor:** K aday dizi örnekler, her birini puanlar, en iyi dizinin
yalnızca ilk viewpoint'ini döndürür.

**Neden var:** Tek adım ileriye bakan (miyop) NBV, kısa vadede iyi ama uzun
vadede kötü görüşlere kilitlenebilir; tüm diziyi körlemesine uygulamak ise
her ölçümden sonra elimize geçen yeni bilgiyi çöpe atmak olur. "H adım
planla, 1 adım uygula, yeniden planla" bu ikisinin arasındaki optimum nokta.

**Neden böyle:** Bircher (ICRA 2016) bu stratejinin keşif problemlerinde hem
frontier'dan hızlı hem de gürültüye dayanıklı olduğunu gösterdi; MPC
literatüründe de aynı ilke kontrol hatalarına karşı kanıtlanmış şekilde
gürbüz. Alternatif olan "planı sonuna kadar uygula" open-loop'tur ve
belief güncellenince ilk plan genellikle geçersizleşir.

---

## 2. Stagnation check + escape (satır 496–542)

**Ne yapıyor:** ROI coverage `stagnation_threshold` (%1.5)'ten az artarsa
sayaç artar; `stagnation_patience` (4) iterasyona ulaşınca çalışma
uzayından örneklenen 20 noktanın mevcut pozisyona en uzak olanına zıplar.

**Neden var:** Lokal örnekleme (küçük teğetsel adımlar) doğası gereği
lokaldir; kamera bir "görülecek şey kalmamış" cebe girerse K aday da aynı
cepten örneklenir ve planner kilitlenir. Verlinden'in PSO makalesi gradient
tabanlı yöntemin tam bu yüzden %40 coverage'da takıldığını gösteriyor —
bizim çözümümüz aynı probleme örnekleme tarafından verilmiş cevap.

**Neden böyle:**
- *Neden coverage sinyali?* Coverage görevin asıl metriği; utility değeri
  ise ölçekten etkilenir. Gerçek ilerleme durduysa takılmışızdır — en
  dolaysız sinyal bu.
- *Neden tam antipodal nokta değil de "20 örnekten en uzağı"?* Antipodal
  nokta robot erişiminin dışına düşebilir (kod yorumunda da yazıyor).
  Erişilebilir örnekler arasından en uzağını seçmek aynı "mümkün olduğunca
  farklı bakış açısı" etkisini kısıt ihlali riski olmadan verir.
- *Neden `2·step_size` alt sınırı?* Zıplama normal bir adımdan bariz büyük
  değilse zıplama sayılmaz; küçük kaymalar zaten normal örneklemeyle
  deneniyor.
- *Patience=4, threshold=%1.5:* tek kötü iterasyonda panik yapmayacak kadar
  sabırlı, ama bütçenin (20 view) çeyreğini takılı harcamayacak kadar tez.

---

## 3. `generate_candidate_sequence()` (satır 211)

**Ne yapıyor:** H adımlık bir viewpoint dizisi üretir: her adım %70 (bias
ratio b) olasılıkla hedefe teğetsel küçük bir orbit kayması, %30 olasılıkla
çalışma kutusunda uniform rastgele bir sıçramadır.

**Neden var:** Aday üretim stratejisi arama uzayının neresine bakacağımızı
belirler. Salt rastgele örnekleme (SamplingNBV) verimsiz — Burusa bunun 10
kat fazla ray-tracing gerektirdiğini gösterdi. Salt lokal adım ise lokal
optimuma mahkûm.

**Neden böyle:**
- *Neden teğetsel adım?* Kamera her zaman hedefe bakıyor; hedefe doğru/
  hedeften uzağa (radyal) hareket görüş açısını değiştirmez, sadece ölçeği
  değiştirir. Yeni bilgi esas olarak *açı* değişiminden gelir; teğetsel
  bileşen tam olarak açıyı değiştiren bileşendir. Rastgele yönden radyal
  bileşeni çıkarıp teğeti almak (Gram-Schmidt tek adımı, satır 234-241)
  bunun en ucuz gerçeklenmesi.
- *Neden %70/%30 karışımı?* Exploitation/exploration dengesi: çoğunlukla
  mevcut iyi bölgeyi pürüzsüzce tarar (Burusa'nın "smooth trajectory"
  avantajı gradyansız elde edilir), ara sıra uzak sıçrama K aday havuzuna
  çeşitlilik enjekte eder. Saf orbit (b=1) takılır, saf rastgele (b=0)
  savurur.
- *Neden adım boyu `s·uniform(0.3, 1.0)`?* Sabit adım örüntü oluşturur
  (aliasing); tam 0'a inen uniform ise yerinde saymayı örnekler. Alt sınır
  0.3s "anlamlı ama değişken" adım garantiler. s=0.065 Burusa'nın kendi
  step_size'ı — adil karşılaştırma için aynen alındı.
- *Neden uniform sıçrama kutu içinde?* Varsayılan modda Burusa ile aynı
  box-constrained kamera uzayını aramak zorundayız (adil karşılaştırma);
  küresel kabuk versiyonu ablasyon olarak ayrıca var.

---

## 4. `evaluate_sequence()` (satır 430)

**Ne yapıyor:** Bir diziyi `J = Σ γ^k (f_inc − λ·C)` ile puanlar; her
hipotetik görüşten sonra belief kopyasını `predict_update` ile ilerletir;
önceki adımlara `s/2`'den yakın adımların kazancını ×0.3 ile kırpar.

**Neden var:** Diziyi *bütün olarak* puanlamak RH'nin varlık sebebi; ama
naif toplama (Bircher tarzı, mevcut haritada her düğümün gain'ini toplamak)
aynı belirsiz voxelleri iki kez sayar ve "aynı yerde dur, aynı entropiyi
tekrar topla" dizilerini ödüllendirir.

**Neden böyle:**
- *Neden discount γ=0.85?* Horizon'un ilerideki adımları giderek daha
  belirsiz bir harita tahminine dayanıyor — 2. adımın gain'i 1. adımın
  *tahmin edilmiş* sonucuna bağlı. Belirsiz bilgiye daha az güvenmek
  rasyoneldir; γ bunu kodlar. Ayrıca yalnızca ilk adım uygulanacağı için
  ilk adımın kalitesi pratikte daha önemli. γ=1 (Zhang'daki gibi indirimsiz
  toplam) ileri adımların tahminlerine gerçek ölçüm muamelesi yapar.
- *Neden λ·C lineer çıkarma, Bircher'in `e^{-λc}` üsteli değil?* Üstel
  çarpan gain'i asla negatife düşüremez — çok uzun ama az kazançlı hamle
  yine pozitif puan alır. Lineer ceza net kazancı eksiye düşürebilir, yani
  "bu hamle zahmetine değmez" diyebilir; MPC hedef fonksiyonlarının
  standart biçimi de budur (stage reward − stage cost).
- *Neden ×0.3 cezası, tam 0 değil?* Yakın tekrar görüş tamamen değersiz
  değildir: derinlik sensörü gürültülüdür, aynı bölgenin ikinci ölçümü
  occupancy'yi rafine eder. 0 yapmak bunu inkar eder; 1 bırakmak yerinde
  saymayı ödüllendirir. 0.3 "caydır ama yasaklama" seviyesi.
- *Neden eşik `s/2`?* Ölçek doğal olarak adım boyuna bağlı: bir adımın
  yarısından yakın iki viewpoint pratikte aynı görüştür. Mutlak bir sabit
  (örn. 3 cm) s değişince anlamını yitirirdi; s/2 ablasyonlarda kendini
  ölçekler.

---

## 5. `compute_gain_on_grid()` — utility (satır 283)

**Ne yapıyor:** Verilen kamera pozisyonundan hedefe bakan sanal görüntünün
tüm pikselleri boyunca ışın atar; her ışın noktasında
`transmittance × semantik entropi` toplar; `log(mean(·))` döndürür.
Opsiyonel occlusion bonus'u ekler. Her çağrı `ray_trace_count`'u artırır.

**Neden var:** "Bu görüş ne kadar değerli?" sorusunun cevabı planner'ın
kalbidir. Hedef-odaklı görev için düz occupancy entropisi (Zhang) yanlış
şeyi ölçer: sahnenin her yerindeki belirsizliği eşit sayar.

**Neden böyle:**
- *Neden semantik entropi?* Görev "domates node'unu / hedef nesneyi iyi
  algıla", "her şeyi haritala" değil. Semantik olasılığın entropisi tam
  olarak "hedef sınıfına dair kararsızlığı" ölçer (Burusa Eq. 7). ROI
  dışı voxeller zaten background'a init edildiği için katkıları düşük —
  utility otomatik olarak hedefe odaklanır.
- *Neden transmittance ağırlığı?* Önü kapalı voxel'in entropisi o görüşten
  azaltılamaz; onu saymak occluded görüşleri şişirir. `Π(1−opacity)`
  çarpanı (Delmerico'nun occlusion-aware VI'sı, Burusa Eq. 6) yalnızca
  gerçekten görülebilecek belirsizliği sayar — occlusion problemi çözen
  bir planner için vazgeçilmez.
- *Neden `sigmoid(1e7·(occ−0.51))` opaklık?* Occupancy 0.51'in üstündeyse
  ışını pratikte kesen, altındaysa geçiren sert bir eşik gerekiyor; dik
  sigmoid bunun sayısal olarak stabil (NaN üretmeyen) hali. 0.51 ofseti
  tam 0.5'te (bilinmeyen) duran voxellerin ışını kesmemesi için.
- *Neden `log(mean)`?* Monotonik dönüşüm — adayların sıralamasını
  değiştirmez, ama gain'in dinamik aralığını sıkıştırıp λ·C ile aynı
  ölçeğe getirir; λ'nın tek değeriyle tüm iterasyonlarda anlamlı kalmasını
  sağlar.
- *Neden `torch.no_grad()`?* Skaler döndürüyoruz, geri yayılım yok;
  autograd grafiği saf bellek/zaman israfıydı. Sayısal sonuç birebir aynı
  (docstring'de belgeli). Gradyan istemiyoruz çünkü stratejimiz zaten
  örnekleme tabanlı — gradyan kullansaydık Burusa'nın lokal minimum
  problemini geri ithal ederdik.
- *Neden occlusion_bonus varsayılan 0?* Terim RH'ye özgü bir avantaj;
  GradientNBV'nin utility'sinde karşılığı yok. Baseline karşılaştırmasında
  açık olsaydı "kazanç RH'den mi bonus'tan mı?" sorusu cevapsız kalırdı.
  Kapalı tutup ablasyonda ayrıca ölçmek deneysel hijyen.

---

## 6. `predict_update()` — belief ileri simülasyonu (satır 349)

**Ne yapıyor:** Hipotetik görüşün ışınlarının kestiği voxellerde, belirsiz
semantik değerleri (0.3–0.7) ve belirsiz occupancy'leri (0.45–0.55) emin
değerlere doğru %40 oranında çeker (`0.6·eski + 0.4·hedef`). Kazanç değil
harita döndürür; `ray_trace_count`'a **sayılmaz**.

**Neden var:** Bu fonksiyon olmadan dizinin 2. ve 3. adımları 1. adımın
göreceği voxelleri "hâlâ belirsizmiş" gibi puanlar — çifte sayım. Bircher
ve Zhang'da bu mekanizma yok; bizim incremental IG iddiamızın teknik
temeli bu fonksiyon.

**Neden böyle:**
- *Neden gerçek sensör modeli değil de bu basit çekme?* Gerçek ölçümü
  bilemeyiz (nesnenin bilinmeyen kısmı ne çıkacak?). Bilebileceğimiz tek
  şey: "oraya bakarsam oradaki belirsizlik azalır." Belirsizliği azaltıp
  yönünü (occupancy'de mevcut eğilimin tarafına, satır 410-414) korumak,
  içerik uydurmadan yapılabilecek en dürüst tahmin.
- *Neden kısmi (%40) güncelleme, tam değil?* Tek hipotetik ölçüm
  belirsizliği sıfırlamaz — gerçek sensör füzyonu da tek ölçümde
  kesinleşmez. Kısmi çekme, tekrar ziyaretin azalan getirisini de doğal
  modeller (ikinci bakış daha az kazandırır).
- *Neden sadece 0.3–0.7 / 0.45–0.55 bantları?* Zaten emin olunan voxelleri
  (0.9 occupancy gibi) hipotetik ölçümle oynatmak mevcut bilgiyi bozmak
  olur; yalnızca kararsız bölge güncellenir.
- *Neden ray-trace sayacına dahil değil?* Hesaplama maliyeti metriğimiz
  Burusa'nın "number of ray-tracing calls" metriği — o yalnızca gain
  değerlendirmelerini sayar. Tahmin güncellemesini de saysaydık kendi
  yöntemimizi baseline'a göre yapay olarak pahalı gösterirdik; ama bunu
  açıkça belgeliyoruz (docstring + tez metni), gizlemiyoruz.

---

## 7. `motion_cost()` (satır 424)

**Ne yapıyor:** İki viewpoint arasındaki Öklid mesafesini döndürür.

**Neden var:** Maliyetsiz utility, kazancı %1 fazla diye çalışma uzayının
öbür ucuna savrulan bir kamera üretir: yavaş, enerji israfı, kol için
riskli, trajectory-distance metriğinde felaket.

**Neden böyle:** Gerçek maliyet eklem-uzayı yol uzunluğudur ama onu bilmek
her aday için IK + motion planning çağrısı gerektirir (K·H kere!). Öklid
mesafesi, küçük lokal çalışma kutusunda eklem maliyetiyle güçlü korelasyon
gösteren sıfır maliyetli bir vekildir. Bircher ve Delmerico da aynı
sadeleştirmeyi kullanır — literatür standardı.

---

## 8. `_push_to_min_standoff()` (satır 194) ve reach clamp (satır 171)

**Ne yapıyor:** Hedefe `MIN_STANDOFF`'tan yakın örnekleri radyal olarak
dışarı iter; robot erişim kutusunun dışındakileri kutuya kırpar.

**Neden var:** Kamera çalışma kutusu (CAM_WRAP_Y) yan görüşler aranabilsin
diye nesnenin etrafını sarar — yani kutunun içinde nesnenin kendisi de var.
Bu koruma olmadan örnekler nesnenin *içine* veya D455'in minimum derinlik
mesafesinin altına düşebilir: fiziksel çarpışma + tamamen bozuk ölçüm.

**Neden böyle:** Geçersiz örneği atıp yeniden örneklemek yerine *itmek*
tercih edildi çünkü: (a) örnek israfı yok, K sabit kalıyor; (b) itilen
nokta "o yönden bakılabilecek en yakın geçerli nokta"dır — yani örnekleme
niyeti (yön) korunur, sadece kısıt ihlali düzeltilir. Yön korunarak mesafe
düzeltmek, reddet-yeniden-örnekle döngüsünün belirsiz süresinden de kaçınır.

---

## 9. `_project_to_shell()` (satır 182, varsayılan KAPALI)

**Ne yapıyor:** Açıksa kamerayı hedef merkezli `[r_min, r_max]` küresel
kabuğuna projeler (yön korunur, mesafe kırpılır).

**Neden var (ve neden kapalı):** Kabuk, kamerayı her zaman "iyi gözlem
mesafesi bandında" tutan RH'ye özgü bir kısıt. Ama GradientNBV'de karşılığı
yok; açık olsaydı iki planner farklı arama uzaylarında yarışırdı ve sonuç
karşılaştırılamaz olurdu. Bu yüzden varsayılan kapalı — yalnızca ablasyon
olarak açılıyor (satır 57-61'deki yorum). Bu, "adil karşılaştırma"
iddiamızın somut kanıtlarından biri.

---

## 10. `update_voxel_grid()` + D455 ofseti (satır 637–656)

**Ne yapıyor:** Gerçek ölçümü (derinlik + semantik) grid'e füzyonlar;
bunu yapmadan önce komuta edilen pozisyona kameranın renk-derinlik
sensörleri arasındaki 59 mm'lik fiziksel ofseti ekler.

**Neden var:** MoveIt kolu `camera_color_frame`'e göre konumlandırır ama
Gazebo derinlik ölçümü `camera_link`'ten gelir. 59 mm, 3 mm'lik voxel
grid'de ~20 voxel'lik sistematik kayma demektir — düzeltilmezse tüm
rekonstrüksiyon kayar ve F1 çöker. (Nitekim F1 diagnostiği bu tür eksen
kaymalarını yakalamak için yazıldı, `calculate_F1(diagnose=True)`.)

**Neden böyle:** Ofset rotasyona bağlı olduğu için sabit vektör olarak
eklenemez; kameranın anlık yönelim matrisiyle döndürülerek eklenir
(`R_cws @ [0, 0.059, 0]`). Bu, kalibrasyon dosyasından okunabilecek bir
değer ama simülasyonda URDF'ten kesin olarak biliniyor.

---

## 11. Değerlendirme fonksiyonları: `calculate_F1`, `set_occluded_mesh_points`, `compute_occluded_recall`, `compute_sigma`

**Ne yapıyorlar:** Burusa'nın metrik setinin birebir uygulanması: hedef
sınıf voxellerinin ROI içinde ground-truth mesh'e karşı F1/precision/recall;
ilk görüşte görünmeyen mesh noktalarının sonradan kurtarılma oranı
(occluded recall); rekonstrüksiyonun uzamsal yayılımı (σ).

**Neden varlar:** Karşılaştırmanın anlamlı olması için baseline'ın kendi
metrikleriyle ölçülmek zorundayız — kendi icat ettiğimiz metrikle kendi
yöntemimizi övmek savunulamaz.

**Neden böyle (kritik savunma noktaları):**
- *F1 eşiği neden Burusa'nın 2 mm'si değil?* Burusa 2 mm voxel grid
  kullanır; bizim grid 3 mm ve ölçülen voxel merkezleri sürekli mesh
  yüzeyinden ~9–13 mm önde bir kabuk oluşturuyor (bu her İKİ planner için
  de ölçüldü ve doğrulandı — satır 758-766'daki yorum). 2-3 mm eşikte TP
  matematiksel olarak imkânsız. Eşik `voxel_size × 4` olarak dürüstçe
  raporlanıyor ve `F1_THRESH` ile duyarlılık analizine açık. İki planner
  aynı eşiği kullandığı için karşılaştırma adil kalıyor.
- *ROI kırpması neden ±75 mm?* Coverage hesabındaki ROI ile (voxel_grid'in
  set_target_roi'si) aynı olmak zorunda; eski ±30 mm değeri F1 ile
  coverage'ın farklı bölgeleri ölçmesine yol açıyordu (satır 736-741'deki
  yorum bu hatanın tespitini ve düzeltmesini belgeliyor).
- *Neden TP/FP/FN açıkça saklanıyor?* (`last_tp/fp/fn`) F1 tek sayı olarak
  yanıltıcı olabilir; ham sayımlar raporlanınca sonuç yeniden hesaplanabilir
  ve denetlenebilir.

---

## 12. Sabitlenen tohum ve `fair_comparison_config.py`

**Ne yapıyor:** `rng_seed=42` tüm rastgeleliği sabitler; ortak config
dosyası ROI, kamera kutusu, voxel boyutu, hedef pozisyonu gibi her ortak
parametreyi tek kaynaktan dağıtır.

**Neden var:** Örnekleme tabanlı bir planner'ın sonuçları koşudan koşuya
değişir; sabit tohum + env-var ile parametrelenen ablasyonlar tam
tekrarlanabilirlik sağlar. Ortak config ise iki planner'ın parametrelerinin
"sessizce ayrışmasını" (dosyanın kendi docstring'indeki ifade) yapısal
olarak imkânsız kılar — adil karşılaştırma iddiasının altyapısı.
