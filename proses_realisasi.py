# Nama file: proses_realisasi.py

import os
import shutil
from datetime import datetime
import pandas as pd
from koneksi import get_koneksi

# Folder untuk menyimpan semua file yang di-upload
UPLOAD_FOLDER = 'arsip_realisasi'

def proses_file_realisasi(tahun, bulan, path_file_sumber):
    """
    Fungsi utama untuk memproses file realisasi, menjalankan kalkulasi,
    dan menyimpan hasilnya ke database.
    """
    # === BAGIAN 1: Mengarsipkan File Asli ===
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists(path_file_sumber):
        print(f"❌ ERROR: File sumber '{path_file_sumber}' tidak ditemukan.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nama_file_unik = f"{timestamp}_{os.path.basename(path_file_sumber)}"
    path_tujuan_arsip = os.path.join(UPLOAD_FOLDER, nama_file_unik)

    try:
        shutil.copy(path_file_sumber, path_tujuan_arsip)
        print(f"📄 File asli berhasil diarsipkan ke: {path_tujuan_arsip}")
    except Exception as e:
        print(f"❌ ERROR saat mengarsipkan file: {e}")
        return

    # === BAGIAN 2: Logika Pandas (Kode dari Anda) ===
    try:
        df = pd.read_excel(path_file_sumber)
        df.columns = df.columns.str.strip().str.lower()

        required_columns = ['kode sub skpd', 'kode program', 'nilai realisasi']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"File harus memiliki kolom: {required_columns}")

        bagian_map = {
            '3.29.01': 'Sekretariat', '3.29.02': 'Bidang air tanah', '3.29.03': 'Bidang pertambangan',
            '3.29.05': 'Bidang energi', '3.29.06': 'Bidang ke tenagalistrikan',
            '3.29.0.00.0.00.01.0001': 'WILAYAH I CIANJUR', '3.29.0.00.0.00.01.0002': 'WILAYAH II BOGOR',
            '3.29.0.00.0.00.01.0003': 'WILAYAH III PURWAKARTA', '3.29.0.00.0.00.01.0004': 'WILAYAH IV BANDUNG',
            '3.29.0.00.0.00.01.0005': 'WILAYAH V SUMEDANG', '3.29.0.00.0.00.01.0006': 'WILAYAH VI TASIKMALAYA',
            '3.29.0.00.0.00.01.0007': 'WILAYAH VII CIREBON', '3.29.0.00.0.00.01.0008': 'UPTD LABORATORIUM ESDM',
        }
        df['bagian'] = None
        for kode, nama in bagian_map.items():
            df.loc[df['kode sub skpd'].astype(str).str.startswith(kode), 'bagian'] = nama
        
        mask_khusus = df['kode sub skpd'] == '3.29.0.00.0.00.01.0000'
        df.loc[mask_khusus, 'bagian'] = df.loc[mask_khusus, 'kode program'].map(lambda x: bagian_map.get(str(x)))
        
        df_final = df[df['bagian'].notnull()]
        hasil_sum = df_final.groupby('bagian')['nilai realisasi'].sum().reset_index()
        print("📊 Kalkulasi pandas berhasil. Hasil:")
        print(hasil_sum)

    except Exception as e:
        print(f"❌ ERROR saat memproses data dengan pandas: {e}")
        return

    # === BAGIAN 3: Menyimpan Hasil ke Database ===
    koneksi = None
    try:
        koneksi = get_koneksi()
        if koneksi:
            kursor = koneksi.cursor()
            
            # Insert ke tabel induk (laporan_bulanan)
            query_induk = "INSERT INTO laporan_bulanan (tahun, bulan, nama_file_asli, path_file_disimpan) VALUES (%s, %s, %s, %s)"
            data_induk = (tahun, bulan, os.path.basename(path_file_sumber), path_tujuan_arsip)
            kursor.execute(query_induk, data_induk)
            laporan_baru_id = kursor.lastrowid

            # Siapkan data hasil kalkulasi untuk tabel anak
            data_realisasi = []
            for index, row in hasil_sum.iterrows():
                data_tuple = (laporan_baru_id, row['bagian'], row['nilai realisasi'])
                data_realisasi.append(data_tuple)

            # Insert ke tabel anak (realisasi_per_bagian)
            query_anak = "INSERT INTO realisasi_per_bagian (laporan_id, nama_bagian, total_realisasi) VALUES (%s, %s, %s)"
            kursor.executemany(query_anak, data_realisasi)

            koneksi.commit()
            print(f"\n✅ BERHASIL: Laporan dibuat dengan ID {laporan_baru_id} dan {kursor.rowcount} baris realisasi disimpan.")

    except Exception as e:
        print(f"❌ ERROR saat menyimpan ke database: {e}")
        if koneksi: koneksi.rollback()
    finally:
        if koneksi and koneksi.is_connected(): koneksi.close()

# --- Bagian untuk Menjalankan Skrip ---
if __name__ == "__main__":
    TAHUN_INPUT = 2025
    BULAN_INPUT = 6 # Juni
    FILE_REALISASI_INPUT = 'sumber_data_realisasi.xlsx'

    # Membuat file Excel dummy untuk pengujian
    try:
        dummy_data = {
            'kode sub skpd': ['3.29.01.2.02.01', '3.29.01.2.02.01', '3.29.03.2.01.03', '3.29.0.00.0.00.01.0000'],
            'kode program': ['PROGRAM A', 'PROGRAM B', 'PROGRAM C', '3.29.0.00.0.00.01.0007'],
            'Nilai Realisasi': [1000, 2000, 5000, 8000]
        }
        pd.DataFrame(dummy_data).to_excel(FILE_REALISASI_INPUT, index=False)
        print(f"File dummy '{FILE_REALISASI_INPUT}' telah dibuat untuk pengujian.")
    except Exception as e:
        print(f"Tidak bisa membuat file dummy: {e}")

    print("\n--- Memulai Proses ---")
    proses_file_realisasi(TAHUN_INPUT, BULAN_INPUT, FILE_REALISASI_INPUT)