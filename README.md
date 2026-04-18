# TsukiRe-Translator & mrg_tool

Kumpulan alat (tools) untuk proses lokalisasi game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mendukung ekstraksi, pengeditan teks secara langsung (GUI), hingga pengemasan ulang (*repacking*) ke format aslinya.

---

## 1. TsukiRe-Translator (GUI Editor)
Alat utama untuk menerjemahkan tanpa perlu berurusan dengan file teks mentah secara manual. Memungkinkan pengeditan langsung dengan tampilan dua kolom yang intuitif.

### Preview Interface
<p align="center">
  <kbd>
    <img src="https://i.imgur.com/wxw2gl5.png" width="750" alt="GUI Preview">
  </kbd>
</p>

**Fitur:**
- **Visual Divider:** Garis pemisah vertikal antara kolom Original dan Translation untuk keterbacaan maksimal.
- **Direct Editing:** Klik dua kali pada kolom terjemahan untuk mengedit teks secara instan.
- **Route Tree:** Navigasi berdasarkan rute (**Arcueid**, **Ciel**, **Common**) yang sudah disortir otomatis menggunakan `scene_map.json`.
- **Live Search:** Mencari baris dialog tertentu dengan cepat menggunakan kata kunci.
- **Project System:** Menyimpan progres kerja dalam format `.tsproj` sebelum di-patch ke game.

## Cara Penggunaan

### A. Menggunakan Translator GUI (Rekomendasi)
1. Jalankan `tsuki_trans.py`.
2. Buka file `script_text.mrg`.
3. Pilih rute/scene pada panel kiri, lalu mulai menerjemahkan di kolom kanan.
4. Gunakan menu **File > Patch MRG** untuk menerapkan terjemahan ke file game.

