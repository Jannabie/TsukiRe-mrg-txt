# mrg_tool - Tsukihime Remake (Switch) Script Extractor & Repacker

Tool untuk ekstrak dan repack file `script_text.mrg` game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mendukung format arsip MZP (`mrgd00`) dan encoding UTF-8 untuk kebutuhan lokalisasi.

## Update: Rute Terorganisir
Script teks kini telah **berhasil disortir**. Kamu bisa menemukan file teks yang sudah dipisahkan berdasarkan alur cerita untuk mempermudah proses penerjemahan:
* Common Route
* Arcueid Route
* Ciel Route

## Perbandingan Terjemahan

| Sebelum (Original Japanese) | Sesudah (Indonesian Patch) |
| :--- | :--- |
| ![Sebelum](https://i.imgur.com/Fl6iTqW.png) | ![Sesudah](https://i.imgur.com/eEtdYFB.jpeg) |

## Preview Format Teks (.txt)

<p align="center">
  <img src="https://i.imgur.com/yALew5y.png" width="500" alt="Preview TXT">
  <br>
  <i>Hasil ekstraksi mempertahankan ID Offset agar bisa di-repack dengan tepat.</i>
</p>

## Penjelasan Teknis Kompresor (Repacker)
Alat ini menggunakan logika *repacking* khusus untuk membangun ulang arsip MZP tanpa merusak struktur internal game:
- **Kalkulasi Offset Otomatis:** Setiap kali kamu mengubah panjang teks (misal: dari Bahasa Jepang yang pendek ke Bahasa Indonesia yang panjang), tool ini akan menghitung ulang seluruh tabel *pointer* (offset) dari awal.
- **Manajemen 10 Section:** Menangani rekonstruksi 10 bagian utama dalam arsip `script_text.mrg`, termasuk penyelarasan byte (*alignment*) untuk data string dan section padding.
- **Presisi Sektor:** Mengikuti standar sektor `0x800` untuk memastikan file hasil repack bisa dibaca dengan lancar oleh emulator maupun mesin Switch asli.

## Cara Pakai

### 1. Mode GUI
J
