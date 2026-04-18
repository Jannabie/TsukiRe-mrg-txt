# mrg tool - Tsukihime Remake (Switch) Script Extractor & Repacker

Tool untuk ekstrak dan repack file `script_text.mrg` game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mendukung format arsip MZP (`mrgd00`) dan encoding UTF-8 untuk kebutuhan lokalisasi.

## Update: Rute Terorganisir
Script teks kini telah **berhasil disortir**. Kamu bisa menemukan file teks yang sudah dipisahkan berdasarkan alur cerita untuk mempermudah proses penerjemahan:
* **Common Route**
* **Arcueid Route**
* **Ciel Route**

## Perbandingan Terjemahan

| Sebelum (Original Japanese) | Sesudah (Indonesian Patch) |
| :--- | :--- |
| ![Sebelum](https://i.imgur.com/Fl6iTqW.png) | ![Sesudah](https://i.imgur.com/eEtdYFB.jpeg) |

## Preview Format Teks (.txt)

Hasil ekstraksi mempertahankan ID Offset agar bisa di-repack dengan tepat:

<img src="https://i.imgur.com/yALew5y.png" width="500" alt="Preview TXT">

## Struktur Arsip MZP
Tool ini menangani 10 section utama dalam arsip `script_text.mrg`:
- **Section 0 & 1:** Main Offset Table & String Data (UTF-8).
- **Section 2 - 9:** Padding & Newline sections (`\r\n` dan full-width space).

## Cara Pakai

### 1. Mode GUI
Jalankan langsung untuk membuka jendela antarmuka (memerlukan `tkinter`):
```bash
python mrg_tool.py
