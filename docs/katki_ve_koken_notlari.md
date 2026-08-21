# Katkı ve Köken Notları — RH-NBV

**Tarih:** 11 Ağustos 2026
**Amaç:** Tezin hangi parçası nereden geliyor? Neyi doğrudan aldım, neyden
esinlendim, ne benim? Savunmada "bu kısım sizin mi?" sorusuna hazır cevap.

**Yöntem:** Tezin ne yazdığına değil, kaynakların kendisine bakıldı. Upstream
repolar klonlanıp yerel kodla satır satır diff'lendi; makaleler
`~/Downloads/papers/` içinden okundu.

- `github.com/akshaykburusa/gradientnbv` (yerel kopya: `~/Downloads/gradientnbv-main`, GitHub `main` ile birebir aynı)
- `github.com/Daanverlinden02/PSO-for-perception-of-occluded-target-nodes`
- `github.com/ethz-asl/nbvplanner` (Bircher'in gerçek implementasyonu)

---

## 1. Doğrudan devralınanlar

| Parça | Kaynak | Kanıt |
|---|---|---|
| Voxel grid, ray sampler, koordinat dönüşümleri | Burusa `gradientnbv` | `conversions.py` **0 satır fark**; `raysampler.py` 43 satır (sadece near-clip/D455) |
| Semantik segmentasyon | aynı | `segmentator.py` **0 satır fark** |
| Viewpoint sampler | aynı | `viewpoint_sampler.py` 9 satır fark |
| **Utility çekirdeği** | aynı | aşağıda, §1.1 |
| GradientNBV algoritması | Burusa ICRA'24 | `loss()` + gradyan çıkışı aynen |
| PSO algoritması | Verlinden reposu | `c1=1.25, c2=0.5, w, bc`, bouncing bounds, pbest/gbest aynen |
| F1'in **implementasyonu** | Verlinden `pso_planner.calculate_F1()` | çift KDTree + `query_ball_point` + ilk eşleşmede `break` iskeleti birebir |
| **Bunny sahnesi** | Burusa reposu | `simulation_environment/worlds/bunny.world` + `meshes/bunny.dae` hazır geliyor |
| **Kutu okluder deneyi** | Burusa reposu + makale | `box.sdf`, `sdf_spawner.spawn_box()`, ve runner'da sol/sağ/üst/alt yorum satırları |
| Sabit başlangıç pozu | aynı | `predefine_start_pose(target, distance=0.35)` |
| Random baseline stratejisi | aynı | `random_view()` → komşu örnekle, rastgele seç |
| `grid_size = [0.3, 0.6, 0.3]` | aynı | upstream runner config'inde zaten böyle |

### 1.1 Utility'deki logaritma benim değil

Burusa'nın `voxel_grid.compute_gain()`'i:

```python
opacities     = torch.sigmoid(1e7 * (occ_sem_confs[0] - 0.51))
transmittance = self.shifted_cumprod(1.0 - opacities)
ray_gains     = transmittance * self.entropy(occ_sem_confs[1])
semantic_gain = torch.log(torch.mean(ray_gains) + self.eps)   # <-- log burada
```

Benim `compute_gain_on_grid()` bunun satır satır kopyası (+ `no_grad`,
+ dışarıdan grid alma, + occlusion bonus). Tezde logaritmayı uzun uzun
savunuyorum; savunma doğru ama "ben ekledim" izlenimi veriyor.
**Düzeltme:** "the log is retained from \citet{akshay_henten_kootstra_2023};
the reason it matters here is that..."

### 1.2 Yerel örnekleme de upstream'de var

`viewpoint_sampler.random_neighbour_sampler()` mevcut pozun etrafında
**d = 0.1 m yarıçaplı küreden** örnekliyor + look_at.
`semi_cylindrical_sampler()` hedefin etrafında sabit yarıçapta dönüyor.

**Benim gerçek farkım daha dar ama net:** adımın *teğetsel bileşene
projeksiyonu* (radyal bileşeni atmak), `s·U(0.3,1)` ile rastgele büyüklük, ve
tek bir dizi içinde teğetsel adım ile global sıçramanın `b=0.7` ile
karıştırılması.

---

## 2. GradientNBV makalesinden gelenler (tezde atıfsız)

`~/Downloads/papers/Gradient-based Local Next-best-view Planning...pdf`, §VI-C:

> "For each case, **four different initial values were randomly assigned to
> ξ = {pᶜ, pᵗ}**, with a total of 16 trials per planner."

> "The planning was **terminated at the end of 20 viewpoints**."

> "we partially occluded the target object... **using a box**... Four cases were
> considered, where the **left, right, top, or bottom** part of the target object
> was occluded."

> "The step size for GradientNBV was set to **0.065**, which roughly moved the
> camera the same distance as SamplingNBV for the initial steps."

Yani şunların hepsi bu makaleden: **±başlangıç perturbasyonu, N = 20 bütçesi,
s = 0.065 adım boyu, kutu-okluder tasarımı**, ve metrik setinin tamamı
(ROI coverage, F1, ray-tracing çağrısı, trajectory distance, occluded recall, σ).

### 2.1 Perturbasyon atfı yanlış makalede

Attention makalesi (`burusa_henten_gert_kootstra_2024`) tam tersini diyor:

> "To ensure that the performances of the planners were comparable, **all of them
> started from the same initial viewpoint ξ₀**. The choice of the initial
> viewpoint was arbitrary and did not influence the performance of the planners."

Onların varyansı **10 bitki modeli × 12 oryantasyon = 120 trial**'dan geliyor.
Yani ±3 cm atfı `burusa_2024` yerine `akshay_2023`'e gitmeli — bu, daha önce
düzeltilen Burusa atıf takasının aynısının bir kopyası daha.

Attention makalesinin gerçek analogu **benim yaw rotasyonlarım**
(`y000/y090/y180/y270`). "Following Burusa" cümlesi oraya ait.

### 2.2 İki esinlenme daha (belirtilmiyor, belirtilmeli)

- Burusa **τₐ = 0.8 eşiğine kaç viewpoint'te ulaşıldığını** hız metriği olarak
  kullanıyor → **H1b**'nin atası.
- Burusa orijinal bitkilerle **"simplified" (daha az okluzyonlu)** modelleri
  karşılaştırıyor → **H2a**'nın atası. Panel merdiveni bunun derecelendirilmiş
  hâli.

### 2.3 Tanımını değiştirdiğim metrikler — bunu yazmak zorundayım

| Metrik | Burusa | Ben |
|---|---|---|
| F1 eşiği | **0.002 m** = voxel çözünürlüğünün tam 1 katı | **4 × voxel = 0.012 m** |
| Occluded recall | *node tespiti*: pozisyon GT'ye 0.02 m içinde **ve** sınıf doğru | *yüzey noktası*: başta görülmemiş mesh noktalarının kaplanma oranı |
| ROI | 0.06 m kenarlı küp | ~0.19 m kenarlı küp (`ROI_HALF = 0.095`) |

Üçü de meşru (hedef bir domates düğümü değil), ama şu an "Burusa'nın metriği"
diye sunuluyor ve sayılar karşılaştırılabilirmiş gibi okunuyor.

### 2.4 Eksik baseline aslında eksik değil

Burusa'nın baseline'ları: GradientNBV / **SamplingNBV** / Random.
SamplingNBV = *K aday örnekle, aynı utility ile puanla, en iyisini seç, tek adım.*
Bu, benim **H = 1, K = 10 ablasyonumun tam olarak kendisi.** K=30/H=1 eşit-hesap
koşum da onların "SamplingNBV 10× daha fazla ray-tracing ister" iddiasının aynı
şekilli testi.

**Teze eklenecek cümle:**
> The H = 1 configuration is, by construction, the SamplingNBV baseline of
> \citet{akshay_henten_kootstra_2023}: K candidates scored by the same utility,
> one step committed. It is therefore not absent from this comparison but present
> as the horizon-ablated variant of the proposed planner.

**Uyarı:** onların ray-tracing sayacında GradientNBV viewpoint başına 1, benimki
K×H. Bu metrikte yapısal olarak kaybediyorum ve PSO sayacım zaten 0 yazıyor.
Ray-call tablosu ya düzeltilmeli ya tamamen çıkmalı.

---

## 3. Bircher'den ne aldım, ne almadım

`ethz-asl/nbvplanner`, `rrt.cpp:354`:

```cpp
newNode->gain_ = newParent->gain_
               + gain(newNode->state_) * exp(-degressiveCoeff_ * newNode->distance_);
```

Bircher: RRT ağacı, **çarpımsal üstel** mesafe cezası, ve gain her düğümde
**güncel haritadan** hesaplanıyor — **dal içinde inanç güncellemesi yok**
(yani aynı bölgeyi gören iki viewpoint iki kez ödüllendiriliyor).

Bende: RRT yok (K rastgele dizi = MPC random shooting), ceza **toplamsal**
(`−λ‖Δp‖`), iskonto `γ^{k−1}`, ve **dal içinde harita ilerliyor**.
Bircher'den alınan tek şey: **"sadece ilk adımı uygula"**.

---

## 4. Novelty'yi daraltmam gereken yer: Zhang & Zhang 2022

*"Volumetric Information Gain Guided Receding Horizon Planner for Active 3D
Reconstruction"*, ROBIO 2022. Özeti zaten şunları içeriyor: NBV'nin miyopluğu →
**dead zone**; **forward simulation** ile view path planner; **mobil
manipülatör**, yüksek boyut ve **erişilebilirlik kısıtı**; yeni durum
örneklenirken **reachability + continuity kısıtlarının açıkça gözetilmesi**;
MPC gibi çalışan receding horizon; farklı IG metriklerinin karşılaştırılması.

Yani "manipülatörde ileriye bakmak", "erişilebilir örnekleme" ve "dead zone"
tek başına yeni değil. **H4 (reachability) etrafındaki dil de "yeni" değil,
"bu ortamda ilk kez ölçüldü" olmalı.**

**Doğru boşluk ifadesi:**
> Sıralı planlama volumetrik keşif ve volumetrik nesne rekonstrüksiyonu için
> mevcut; **hedef odaklı, semantik, ROI-sınırlı** yerel algılama için mevcut
> değil — bu alanı tanımlayan planlayıcılar (GradientNBV, Attention-driven)
> tek adımlı.

---

## 5. F1 eşiği: savunulabilir mi? Evet — ve zaten savundum

`results.tex` §"Chamfer and Hausdorff distance: the $F_1$ ranking is not an
artefact of the matching threshold": 15 kombinasyondan **14'ünde** en yüksek
F1'e sahip planlayıcı en düşük Chamfer'a, **13'ünde** en düşük Hausdorff'a sahip.
Eşikli metriğe itiraz gelirse eşiksiz metrikle çapraz kontrol gösterilir.

**Eklenebilecek bedava sayı:** 33 koşunun tamamında
**Spearman(final F1, Chamfer) = −0.943**.

### 5.1 "9–13 mm" rakamını SİL

`fair_comparison_config.py` yorumunda ve tezin yorum satırında
"empirically observed to be 9–13 mm" yazıyor. Kendi loglarım bunu desteklemiyor:
rekonstrüksiyonun gerçekten tamamlandığı koşularda (final F1 > 0.95, n = 10)
Chamfer **2.0–5.5 mm, medyan 4.3 mm**. Jürinin kontrol edebileceği ve tutmayan
bir sayı.

### 5.2 Doğru gerekçe

1. τ dört planlayıcı için de aynı → bir avantaj **üretemez**.
2. Geniş τ farkları **bastırır**, yani H1a'nın **aleyhine** çalışır. Etkinin bu
   dezavantaja rağmen hayatta kalması muhafazakâr bir sonuçtur.
3. Sonuçlar eşiksiz metriklerle çapraz doğrulanmış (§5, yukarıda).

Yapısal not: Burusa'nın 0.002 m'si **voxel çözünürlüğünün tam 1 katı**. Kuralı
değil sayıyı taşısaydım 3 mm olurdu. 4× olduğunu ve nedenini açıkça yazmalıyım,
"Burusa'nın eşiği" diye sunmamalıyım.

### 5.3 Gerçekten canımı yakabilecek tek yer

**Null sonuçlar.** Bitki seviyesinde dört planlayıcının eşitlenmesi ve H2b,
geniş eşiğin doygunluğa ittiği bir yanılsama olabilir.
`f1_threshold_sweep.py` docstring'inde 4 Ağustos'ta tam bu soru sorulmuş,
dump'lar yok, soru cevapsız. İki seçenek: tek bir konfigürasyonun dump'ını
yeniden alıp sweep'i çalıştırmak, ya da limitation olarak açıkça yazmak.

### 5.4 Eşik ifadesinin tamamı yorum satırında

`experimental_setup.tex`'te F1 eşiğinden bahseden **her satır `%` ile kapalı**.
Okuyucu τ = 4 voxel'i ilk kez Sonuçlar'da görüyor. Yorumu aç.

---

## 6. Kesin olarak benim olanlar

Repo taramasından sonra da ayakta duranlar — hiçbiri iki upstream repoda da yok:

1. **Occlusion bonus** `B(M,p)` — `p_o > 0.6 ∧ 0.3 < p_s < 0.7` oranı, `w_occ` ağırlıklı
2. **PredictUpdate** — ufuk içi semantik inanç ilerletme + ray sayacına yazılmaması
3. **İskontolu dizi amaç fonksiyonu** `J(Ξ) = Σ γ^{k−1}[f(M_pred^{(k)}, p_k) − λ‖p_k − p_{k−1}‖]`
4. **Teğetsel adım / global sıçrama karışımı** (`b = 0.7`, `s·U(0.3,1)`)
5. **Stagnation escape** — coverage sinyali, 20 örnekten en uzağı, `2s` alt sınırı
6. **Coverage kanalı düzeltmesi** — upstream `p_sem` (ch2) sayıyor, ben `p_occ`
   (ch1)'e çevirdim; ch2 serbest-uzay semantik güncellemelerinde de yanlış
   "görüldü" sayıyor. Upstream **koduna** karşı bir düzeltme, makalenin tanımına
   sadakat. **Tezde hiç yazmıyor, yazılmalı.**
7. **Occluded recall implementasyonu** — iki repoda da yok
8. **Adil karşılaştırma altyapısı** — `fair_comparison_config.py`,
   `planner_eval_mixin.py`, ortak kutu/standoff, deney koşucusu (89 → 427 satır)
9. **Sahne ve okluzyon tasarımı** — kademeli panel merdiveni (stage1..8),
   L-şekli, ağaç/domates dünyaları, mug
10. **ROS 2 Jazzy + UR5e + D455 portu** — D455 renk↔derinlik ekstrinsik
    düzeltmesi (`[0, 0.059, 0]`), geçersiz ışınların tüm ışını sıfırlaması
11. **Analiz/çizim altyapısının tamamı**

---

## 7. Metodu nasıl kurdum (savunma anlatısı)

Devralmak bu alanda normaldir: Burusa transmittance'ı Delmerico'dan, voxel
grid'i Octomap'ten, segmentasyonu Mask R-CNN'den alıyor; Verlinden tamamen
Burusa'nın reposu üstüne kuruyor. Tez, sıfırdan yazılan satır sayısı değil,
**eklenen katman ve o katmanın işe yaradığını gösteren kanıttır.**

**Adım 1 — Problem.** Miyop planlayıcı ağır okluzyonda tıkanıyor. Benim iddiam
değil, literatürün kendi kaydı: Burusa GradientNBV/SamplingNBV'nin plato
yaptığını, Verlinden gradyanın %40'ta takıldığını gösteriyor.

**Adım 2 — Stratejiyi taşı.** Keşiften (Bircher) receding horizon'ı al. Ama
Bircher'in gain'i hacimsel ve dal içinde inanç güncellemesi yok — aynı bölgeyi
gören iki viewpoint iki kez ödüllendiriliyor. Hedef odaklı bir ROI'de bu hata
taşınamaz.

**Adım 3 — Eksikleri türet.** Buradan üç zorunluluk çıkıyor:
- **PredictUpdate** — çifte sayımı engellemek için.
- **Teğetsel adım + global sıçrama** — 3 yörünge adımı ≈ 20 cm götürür,
  okluderin arkası ≈ 50 cm uzaktadır. Sıçrama olmadan ileriye bakmanın anlamı
  kalmıyor. (Nicel türetme, methods'ta var.)
- **Occlusion bonus** — "dolu ama semantik olarak kararsız" voxel'ler, yani gizli
  hedefin kendisi, saf entropi ile kameraya çekim uygulamıyor.
- (+ stagnation escape: küçük teğetsel adımlar bir cebi tüketiyor.)

**Adım 4 — Ölçme aparatı.** Dört planlayıcı aynı kutuda, aynı standoff'ta, aynı
ROI'de, aynı okluder manifestiyle, eşleştirilmiş başlangıçlarla. Okluzyon ikili
bir koşuldan **derecelendirilmiş bağımsız değişkene** çevrildi.

**Adım 5 — Mekanizmayı izole et.** mug/panels3: RH-NBV **F1 0.892**,
GradientNBV **0.137**. Ufku 1'e indir → **0.573**. Aynı hesabı geniş tek-adım
aramaya harca → **0.198**. Fark ne utility'den ne hesap bütçesinden geliyor —
**ufuktan geliyor.** Bir tezin yapması gereken tam olarak bu: etkiyi göster,
sonra başka her açıklamayı tek tek kes.

### Tek cümlelik katkı ifadesi

> Receding horizon stratejisini hacimsel keşiften hedef odaklı semantik NBV'ye
> taşımak için gereken üç bileşeni (ufuk içi semantik belief güncellemesi,
> okluzyon-farkında fayda terimi, erişilebilirlik-kısıtlı dizi örneklemesi)
> tanımladım; ve kontrollü bir okluzyon merdiveni üzerinde, farkın utility'den
> veya hesap bütçesinden değil ufkun kendisinden geldiğini ablasyonla gösterdim
> — ayrıca nerede işe yaramadığını da (bütün-bitki ölçeğinde) raporladım.

Not: ray-call metriğinin kullanılamaz olduğunu, PSO sayacının eksik olduğunu,
Random'ın coverage'ı yüksekken Hausdorff'unun kötü olduğunu kendim yazdım.
Negatif sonucu saklamayan tez, jürinin güvendiği tezdir.

---

## 8. Yapılacaklar listesi (tez düzeltmeleri)

**11 Ağu 2026'da hepsi teze geçirildi.** Yedekler: `*.tex.bak-provenance-20260811`.

- [x] 1. Utility'deki `log`'un Burusa'dan devralındığı → `methods.tex` §Viewpoint Utility
- [x] 2. "re-implemented" → "ported, algorithms unchanged" → `introduction.tex` §Scope + `discussion.tex` §Simulation and scope
- [x] 3. F1 kodunun Verlinden'den geldiği → `methods.tex` §Implementation Framework
- [x] 4. ±3 cm atfı `burusa_2024` → `akshay_2023` → `experimental_setup.tex` §What is held identical (yorumdaki kopya da düzeltildi)
- [x] 5. N = 20 ve s = 0.065 atıfları → `experimental_setup.tex` §fair, `methods.tex` §sampling
- [x] 6. Kutu-okluder atası → `experimental_setup.tex` §Staged panel ladder
- [x] 7. F1 eşiği / occluded recall / ROI boyutu tanım farkları → `experimental_setup.tex` §Evaluation Metrics
- [x] 8. "H = 1 = SamplingNBV" → `experimental_setup.tex` §E3 + `results.tex` §H3
- [x] 9. Coverage kanalı düzeltmesi (`p_sem → p_occ`) → `experimental_setup.tex` §ROI Coverage
- [x] 10. F1 eşiği artık tezde geçiyor (yorum değil), "9–13 mm" iddiası silindi, yerine 3 maddelik gerekçe
- [x] 11. Eşik-doygunluğu limitation'ı → `results.tex` §secondary-geom + `discussion.tex` §What the metrics can and cannot show. **Sweep hâlâ koşulmadı**, limitation olarak yazıldı.
- [x] 12. H1b → τₐ atfı, H2a → "simplified plant" atfı → `results.tex`
- [x] 13. Zhang & Zhang kapsamı: zaten yapılmıştı (background.tex'te RH-VPP satırı manipülatör ✓ alıyor, reachability novelty iddiası yok). Sadece boşluk paragrafına occlusion bonus + sampler eklendi.

### Kalan tek iş
Eşik sweep'i: `test_tree_f1dump_node.py` ile tek bir konfigürasyonun dump'ını al,
`f1_threshold_sweep.py`'ı koştur. Simülasyon yeniden koşmayı gerektirmez ama
dump gerekir. Yapılmazsa mevcut limitation metni yeterli.
