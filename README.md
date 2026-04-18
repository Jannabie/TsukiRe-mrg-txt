# mrg_tool — Tsukihime Remake Script Extractor & Repacker

Tool spesialis untuk menangani file `script_text.mrg` pada game **Tsukihime -A piece of blue glass moon-** (Nintendo Switch). Mendukung penuh format arsip MZP (`mrgd00`) dan encoding UTF-8 untuk kebutuhan lokalisasi.

---

## Update: Rute Terorganisir
Kabar baik! Script teks hasil ekstraksi kini telah **berhasil disortir**. Kamu bisa menemukan file teks yang sudah dipisahkan berdasarkan alur cerita untuk mempermudah alur kerja penerjemahan:
- **Common Route**
- **Arcueid Route**
- **Ciel Route**

---

## Perbandingan Visual

<div align="center">
  <table style="margin-left: auto; margin-right: auto;">
    <tr>
      <td align="center"><b>Sebelum (Original Japanese)</b></td>
      <td align="center"><b>Sesudah (Indonesian Patch)</b></td>
    </tr>
    <tr>
      <td><img src="https://i.imgur.com/Fl6iTqW.png" width="350"></td>
      <td><img src="https://i.imgur.com/eEtdYFB.jpeg" width="350"></td>
    </tr>
  </table>
</div>

### Preview Format Teks (.txt)
Hasil ekstraksi mempertahankan ID Offset agar proses *repacking* tetap presisi dan tidak merusak pointer asli game.

<div align="center">
  <table style="margin-left: auto; margin-right: auto;">
    <tr>
      <td align="center"><b>Struktur File Teks Mentah</b></td>
    </tr>
    <tr>
      <td><img src="https://i.imgur.com/yALew5y.png" width="500" alt="Preview TXT"></td>
    </tr>
  </table>
  <br>
  <i>Setiap baris teks dikaitkan dengan offset unik untuk menjamin integritas data.</i>
</div>

---

## Fitur Teknis Repacker
Alat ini menggunakan logika rekonstruksi khusus untuk membangun ulang arsip MZP tanpa merusak struktur internal engine:
- **Auto-Offset Calculation:** Secara otomatis menghitung ulang seluruh tabel pointer saat panjang teks berubah (mencegah game *crash*).
- **10-Section Management:** Menangani rekonstruksi 10 bagian utama dalam arsip secara mendalam, termasuk penyelarasan byte (*byte alignment*).
- **Sector Precision:** Mengikuti standar sektor `0x800` untuk memastikan kompatibilitas penuh pada emulator maupun hardware Switch asli.

---

## Cara Penggunaan

### 1. Mode GUI
Jalankan skrip langsung untuk membuka jendela antarmuka (memerlukan `tkinter`):
```bash
python mrg_tool.py
