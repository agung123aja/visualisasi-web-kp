# Nama file: koneksi_db.py

import mysql.connector

def get_koneksi():
    """
    Fungsi ini membuat dan mengembalikan objek koneksi database MySQL.
    Mengembalikan None jika koneksi gagal.
    """
    try:
        koneksi = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="esdm_data"
        )
        return koneksi
    except mysql.connector.Error as err:
        print(f"Error saat koneksi ke database: {err}")
        return None

# --- BAGIAN UNTUK PENGUJIAN ---
# Kode di bawah ini hanya akan berjalan jika file koneksi_db.py dieksekusi langsung
if __name__ == "__main__":
    print("Menjalankan tes koneksi langsung dari file koneksi_db.py...")
    
    # Coba panggil fungsi get_koneksi
    koneksi_tes = get_koneksi()

    # Periksa hasilnya
    if koneksi_tes:
        print("✅ Tes koneksi BERHASIL!")
        # Penting: tutup kembali koneksi setelah tes selesai
        koneksi_tes.close()
        print("Koneksi untuk pengujian telah ditutup.")
    else:
        print("❌ Tes koneksi GAGAL. Periksa kembali detail koneksi di atas.")