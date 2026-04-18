# mrg_tool - Tsukihime Remake (Switch) Script Extractor & Repacker

Tool untuk ekstrak dan repack file `script_text.mrg` pada game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mendukung format arsip MZP (`mrgd00`) dan encoding UTF-8 untuk kebutuhan lokalisasi.

## Update: Rute Terorganisir
Script teks kini telah **berhasil disortir**. File teks telah dipisahkan berdasarkan alur cerita untuk mempermudah proses penerjemahan:
- Common Route
- Arcueid Route
- Ciel Route

## Perbandingan Terjemahan

| Sebelum (Original Japanese) | Sesudah (Indonesian Patch) |
| :---: | :---: |
| ![Sebelum](https://i.imgur.com/Fl6iTqW.png) | ![Sesudah](https://i.imgur.com/eEtdYFB.jpeg) |

## Preview Format Teks (.txt)

<p align="center">
  <img src="https://i.imgur.com/yALew5y.png" width="450" alt="Preview TXT">
  <br>
  <i>Hasil ekstraksi mempertahankan ID Offset agar bisa di-repack dengan tepat.</i>
</p>

## Alternatif Tool
Jika Anda mencari cara yang lebih praktis tanpa harus mengubah file ke format `.txt` terlebih dahulu, Anda bisa menggunakan:
- **[TsukiRe-translation](https://github.com/Jannabie/TsukiRe-translation)**: Memiliki antarmuka GUI yang lebih intuitif dan mendukung pengeditan langsung.

## Penjelasan Teknis Kompresor (Repacker)
Alat ini menggunakan logika *repacking* khusus untuk membangun ulang arsip MZP tanpa merusak struktur internal game:
- **Kalkulasi Offset Otomatis:** Menghitung ulang seluruh tabel *pointer* (offset) secara otomatis saat panjang teks berubah.
- **Manajemen 10 Section:** Menangani rekonstruksi 10 bagian utama dalam arsip `script_text.mrg`, termasuk penyelarasan byte (*alignment*).
- **Presisi Sektor:** Mengikuti standar sektor `0x800` untuk kompatibilitas penuh pada emulator maupun konsol Switch.

## Cara Pakai

### 1. Mode GUI
Jalankan langsung untuk membuka jendela antarmuka (memerlukan `tkinter`):
```bash
python mrg_tool.py
