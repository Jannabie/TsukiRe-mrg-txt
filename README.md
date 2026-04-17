# ◈ mrg_tool — Tsukihime Remake (Switch) Script Text Extractor & Repacker

**mrg_tool** adalah skrip Python yang dirancang khusus untuk mengekstrak dan melakukan *repack* pada file `script_text.mrg` dari game **Tsukihime -A piece of blue glass moon-** (versi Nintendo Switch). 

Tool ini mendukung format arsip MZP (`mrgd00`) dan memfasilitasi lokalisasi/terjemahan *visual novel* dengan cara mengekstrak teks game ke dalam format `.txt` yang mudah diedit, lalu mengemasnya kembali dengan mengkalkulasi ulang *offset table* secara otomatis. Mendukung penuh *encoding* UTF-8.

---

> **⚠️ CATATAN PENTING (STATUS SCRIPT SAAT INI)** > Saat ini, teks yang diekstrak dari `script_text.mrg` **belum disortir atau dibagi berdasarkan rute** (misal: rute Arcueid, rute Ciel, dll). Seluruh baris teks game masih tergabung dan acak dalam satu file. Pemisahan direktori atau pengelompokan teks berdasarkan rute akan diperbarui di masa mendatang jika proses penyortiran sudah selesai.

---

## 📸 Preview Hasil Terjemahan

Berikut adalah contoh implementasi tool ini untuk menerjemahkan teks game dari Bahasa Jepang ke Bahasa Indonesia:

**Sebelum Diterjemahkan (Original Japanese):** ![Sebelum Terjemahan](https://i.imgur.com/Fl6iTqW.png)

**Sesudah Diterjemahkan (Indonesian Patch):** ![Sesudah Terjemahan](https://i.imgur.com/eEtdYFB.jpeg)

---

## ✨ Fitur

- **Mode GUI & CLI:** Tersedia antarmuka visual (GUI) yang ramah pengguna, serta mode Command Line untuk otomatisasi.
- **Dukungan UTF-8 Penuh:** Bebas menggunakan karakter apa pun, sangat cocok untuk lokalisasi dari Bahasa Jepang ke Bahasa Indonesia, Inggris, dll.
- **Kalkulasi Offset Otomatis:** Perubahan panjang string terjemahan ditangani secara otomatis saat *repack*.
- **Aman & Akurat:** Membangun ulang arsip MZP secara presisi (dengan 10 *section* arsip) sehingga dapat terbaca sempurna oleh mesin game di emulator (Yuzu/Ryujinx) maupun *console* Switch asli.

## ⚙️ Persyaratan

- **Python 3.6+**
- Tidak memerlukan *library* eksternal untuk berjalan (hanya menggunakan standar *library* bawaan Python dan `tkinter` untuk GUI).

## 🚀 Cara Penggunaan

### 1. Mode GUI (Sangat Direkomendasikan)
Cukup jalankan skrip tanpa argumen apa pun untuk membuka antarmuka GUI:
```bash
python mrg_tool.py
