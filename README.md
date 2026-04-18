# mrg_tool - Tsukihime Remake (Switch) Script Extractor & Repacker

Tool untuk ekstrak dan repack file `script_text.mrg` game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mendukung format arsip MZP (`mrgd00`) dan encoding UTF-8 untuk kebutuhan lokalisasi.

> **CATATAN:**
> Script yang diekstrak saat ini masih acak dan belum disortir per rute (Arcueid, Ciel, dll). Sortir manual atau update otomatis akan menyusul di masa mendatang.

## Perbandingan Terjemahan

| Sebelum (Original Japanese) | Sesudah (Indonesian Patch) |
| :--- | :--- |
| ![Sebelum](https://i.imgur.com/Fl6iTqW.png) | ![Sesudah](https://i.imgur.com/eEtdYFB.jpeg) |

## Preview Format Teks (.txt)

Hasil ekstraksi berupa file teks terstruktur yang mempertahankan ID Offset agar bisa di-repack dengan tepat:

![Preview TXT](https://i.imgur.com/yALew5y.png)

## Struktur Arsip MZP
Tool ini menangani 10 section utama dalam arsip `script_text.mrg`, termasuk:
- **Section 0 & 1:** Main Offset Table & String Data (UTF-8).
- **Section 2 - 9:** Padding & Newline sections (`\r\n` dan full-width space).

## Cara Pakai

### 1. Mode GUI
Jalankan langsung untuk membuka jendela antarmuka (memerlukan `tkinter`):
```bash
python mrg_tool.py
