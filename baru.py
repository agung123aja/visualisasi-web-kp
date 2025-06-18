import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from functools import wraps
from koneksi import get_koneksi
import logging

# Import untuk PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from reportlab.lib import colors
import io
import json

# Import untuk pemformatan angka dengan locale
from babel.numbers import format_decimal
import locale

# Konfigurasi logging untuk debugging lebih baik
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Coba set locale Indonesia untuk pemformatan angka
try:
    locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'id_ID') # Fallback untuk beberapa sistem
    except locale.Error:
        app.logger.warning("Locale 'id_ID.UTF-8' or 'id_ID' not found. Number formatting might not be standard Indonesia.")


# --- 1. KONFIGURASI AWAL APLIKASI ---
app = Flask(__name__)
app.secret_key = 'kunci_super_rahasia_dan_aman_milik_anda_12345' # Ganti dengan kunci yang lebih kuat di produksi

# Daftar kategori
kategori_dppa_target = [
    'sekretariat', 'air_tanah', 'pertambangan', 'energi', 'ketenagalistrikan',
    'cianjur', 'bogor', 'purwakarta', 'bandung', 'sumedang',
    'tasikmalaya', 'cirebon', 'lab'
]

# Mapping nama_bagian dari database ke kategori_dppa_target (untuk konsistensi)
nama_bagian_to_kategori = {
    'Sekretariat': 'sekretariat',
    'Bidang air tanah': 'air_tanah',
    'Bidang pertambangan': 'pertambangan',
    'Bidang energi': 'energi',
    'Bidang ke tenagalistrikan': 'ketenagalistrikan',
    'WILAYAH I CIANJUR': 'cianjur',
    'WILAYAH II BOGOR': 'bogor',
    'WILAYAH III PURWAKARTA': 'purwakart',
    'WILAYAH IV BANDUNG': 'bandung',
    'WILAYAH V SUMEDANG': 'sumedang',
    'WILAYAH VI TASIKMALAYA': 'tasikmalaya',
    'WILAYAH VII CIREBON': 'cirebon',
    'UPTD LABORATORIUM ESDM': 'lab'
}


# --- 2. DECORATOR UNTUK MEWAJIBKAN LOGIN ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Anda harus login terlebih dahulu untuk mengakses halaman ini.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- 3. BAGIAN RUTE (URL) APLIKASI ---

# Rute "/" sekarang menjadi halaman utama, yaitu Login
@app.route("/", methods=['GET', 'POST'])
def login():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username_input = request.form.get('username')
        password_input = request.form.get('password')

        if username_input == 'esdm' and password_input == 'jabarprov':
            session['logged_in'] = True
            flash('Login berhasil! Selamat datang.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau Password salah!', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

# Rute untuk Logout
@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    flash('Anda telah berhasil logout.', 'success')
    return redirect(url_for('login'))

# Rute untuk Dashboard (sekarang dilindungi)
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template('dashboard.html')

# Rute untuk Upload (sekarang dilindungi)
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def handle_upload():
    if request.method == 'POST':
        tahun = request.form.get('tahun')
        bulan = request.form.get('bulan')
        file = request.files.get('myfile')

        if not all([tahun, bulan, file]) or file.filename == '':
            flash('Tahun, Bulan, dan File wajib diisi!', 'error')
            return redirect(url_for('handle_upload'))

        try:
            df = pd.read_excel(file)
            df.columns = df.columns.str.strip().str.lower()
            required_columns = ['kode sub skpd', 'kode program', 'nilai realisasi']
            if not all(col in df.columns for col in required_columns):
                raise ValueError(f"File Excel harus memiliki kolom: {required_columns}")
            df['nilai realisasi'] = df['nilai realisasi'].fillna(0)

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
            df_final = df.dropna(subset=['bagian'])
            hasil_sum_parsial = df_final.groupby('bagian')['nilai realisasi'].sum().reset_index()
            semua_nama_bagian = list(bagian_map.values())
            df_master_bagian = pd.DataFrame(semua_nama_bagian, columns=['bagian'])
            hasil_lengkap = pd.merge(df_master_bagian, hasil_sum_parsial, on='bagian', how='left')
            hasil_lengkap['nilai realisasi'] = hasil_lengkap['nilai realisasi'].fillna(0)
        except Exception as e:
            flash(f'Gagal membaca atau memproses file Excel: {e}', 'error')
            return redirect(url_for('handle_upload'))

        data_dppa_target_manual = []
        for kat in kategori_dppa_target:
            nama_kategori_lengkap = kat.replace('_', ' ').title()
            nilai_dppa = request.form.get(f'dppa_{kat}', 0, type=float)
            nilai_target = request.form.get(f'target_{kat}', 0, type=float)
            data_dppa_target_manual.append({'kategori': nama_kategori_lengkap, 'dppa': nilai_dppa, 'target': nilai_target})

        koneksi = None
        try:
            koneksi = get_koneksi()
            if koneksi:
                kursor = koneksi.cursor()
                query_induk = "INSERT INTO laporan_bulanan (tahun, bulan) VALUES (%s, %s)"
                kursor.execute(query_induk, (tahun, bulan))
                laporan_baru_id = kursor.lastrowid

                data_to_insert_realisasi = [(laporan_baru_id, row['bagian'], row['nilai realisasi']) for index, row in hasil_lengkap.iterrows()]
                if data_to_insert_realisasi:
                    query_realisasi = "INSERT INTO realisasi_per_bagian (laporan_id, nama_bagian, total_realisasi) VALUES (%s, %s, %s)"
                    kursor.executemany(query_realisasi, data_to_insert_realisasi)

                data_to_insert_dppa = [(laporan_baru_id, item['kategori'], item['dppa'], item['target']) for item in data_dppa_target_manual]
                if data_to_insert_dppa:
                    query_dppa = "INSERT INTO dppa_target_per_kategori (laporan_id, nama_kategori, nilai_dppa, nilai_target) VALUES (%s, %s, %s, %s)"
                    kursor.executemany(query_dppa, data_to_insert_dppa)

                koneksi.commit()
                flash(f'Sukses! Laporan lengkap untuk {bulan}-{tahun} berhasil diupload.', 'success')
        except Exception as e:
            if koneksi: koneksi.rollback()
            flash(f'Gagal menyimpan ke database: {e}', 'error')
        finally:
            if koneksi and koneksi.is_connected(): koneksi.close()
        return redirect(url_for('handle_upload'))

    return render_template('upload.html')

# --- Rute untuk Halaman Pilih ---
@app.route("/pilih")
@login_required
def halaman_pilih():
    koneksi = get_koneksi()
    daftar_laporan = []
    if koneksi:
        try:
            kursor = koneksi.cursor(dictionary=True)
            query_select = "SELECT id, tahun, bulan FROM laporan_bulanan ORDER BY tahun DESC, bulan DESC"
            kursor.execute(query_select)
            daftar_laporan = kursor.fetchall()
        except Exception as e:
            app.logger.error(f'Gagal mengambil data laporan untuk pemilihan: {e}', exc_info=True)
            flash(f'Gagal mengambil data laporan untuk pemilihan: {e}', 'error')
        finally:
            koneksi.close()

    nama_bulan = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    for laporan in daftar_laporan:
        laporan['nama_bulan'] = nama_bulan.get(laporan['bulan'], 'Tidak Valid')

    return render_template('pilih.html', daftar_laporan=daftar_laporan)


# --- ROUTE: process_reports untuk Pemrosesan Data dan Grafik ---
@app.route('/process_reports', methods=['POST'])
@login_required
def process_reports():
    koneksi = None
    try:
        koneksi = get_koneksi()
        if not koneksi:
            return jsonify({'success': False, 'message': 'Gagal terhubung ke database.'}), 500

        start_date_str = request.form.get('startDate')
        end_date_str = request.form.get('endDate')
        selected_report_ids = request.form.getlist('selected_report_ids')

        reports_to_process_ids = []
        last_report_id_for_dppa_target = None
        report_period_info = "" # Untuk informasi periode laporan di PDF

        nama_bulan_dict = {1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
                           7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"}

        if start_date_str and end_date_str:
            start_year, start_month = map(int, start_date_str.split('-'))
            end_year, end_month = map(int, end_date_str.split('-'))

            kursor = koneksi.cursor(dictionary=True)
            query_range = """
                SELECT id, tahun, bulan
                FROM laporan_bulanan
                WHERE (tahun > %s OR (tahun = %s AND bulan >= %s))
                AND (tahun < %s OR (tahun = %s AND bulan <= %s))
                ORDER BY tahun ASC, bulan ASC
            """
            kursor.execute(query_range, (start_year, start_year, start_month, end_year, end_year, end_month))
            reports_in_range = kursor.fetchall()
            reports_to_process_ids = [report['id'] for report in reports_in_range]

            if not reports_to_process_ids:
                return jsonify({'success': False, 'message': 'Tidak ada laporan ditemukan dalam rentang tanggal yang dipilih.'})

            last_report_in_range = reports_in_range[-1]
            last_report_id_for_dppa_target = last_report_in_range['id']

            # Set informasi periode
            if start_date_str == end_date_str:
                report_period_info = f"Periode Laporan: {nama_bulan_dict.get(start_month)} {start_year}"
            else:
                report_period_info = f"Periode Laporan: {nama_bulan_dict.get(start_month)} {start_year} - {nama_bulan_dict.get(end_month)} {end_year}"

        elif selected_report_ids:
            reports_to_process_ids = [int(id_str) for id_str in selected_report_ids]

            if not reports_to_process_ids:
                return jsonify({'success': False, 'message': 'Tidak ada laporan yang dipilih.'})

            kursor = koneksi.cursor(dictionary=True)
            placeholders = ', '.join(['%s'] * len(reports_to_process_ids))
            query_latest_report = f"""
                SELECT id, tahun, bulan
                FROM laporan_bulanan
                WHERE id IN ({placeholders})
                ORDER BY tahun DESC, bulan DESC
                LIMIT 1
            """
            kursor.execute(query_latest_report, tuple(reports_to_process_ids))
            last_report_for_dppa_target_data = kursor.fetchone()

            if not last_report_for_dppa_target_data:
                return jsonify({'success': False, 'message': 'Data laporan yang dipilih tidak valid.'})

            last_report_id_for_dppa_target = last_report_for_dppa_target_data['id']

            # Set informasi periode untuk pilihan laporan spesifik
            if len(selected_report_ids) == 1:
                query_single_report = "SELECT tahun, bulan FROM laporan_bulanan WHERE id = %s"
                kursor.execute(query_single_report, (reports_to_process_ids[0],))
                single_report_data = kursor.fetchone()
                if single_report_data:
                    report_period_info = f"Periode Laporan: {nama_bulan_dict.get(single_report_data['bulan'])} {single_report_data['tahun']}"
            else:
                # Untuk banyak laporan spesifik, diambil rentang dari laporan pertama dan terakhir yang dipilih
                query_min_max_dates = f"""
                    SELECT MIN(tahun) as min_tahun, MIN(bulan) as min_bulan,
                           MAX(tahun) as max_tahun, MAX(bulan) as max_bulan
                    FROM laporan_bulanan
                    WHERE id IN ({placeholders})
                """
                kursor.execute(query_min_max_dates, tuple(reports_to_process_ids))
                date_range_data = kursor.fetchone()
                if date_range_data:
                    start_period_str = f"{nama_bulan_dict.get(date_range_data['min_bulan'])} {date_range_data['min_tahun']}"
                    end_period_str = f"{nama_bulan_dict.get(date_range_data['max_bulan'])} {date_range_data['max_tahun']}"
                    if start_period_str == end_period_str:
                         report_period_info = f"Periode Laporan: {start_period_str}"
                    else:
                        report_period_info = f"Periode Laporan: {start_period_str} - {end_period_str}"


        else:
            return jsonify({'success': False, 'message': 'Harap pilih rentang bulan atau setidaknya satu laporan untuk diproses.'})

        # --- FASE 1: Ambil Realisasi Akumulatif ---
        placeholders = ', '.join(['%s'] * len(reports_to_process_ids))
        query_realisasi_akumulatif = f"""
            SELECT
                rp.nama_bagian,
                SUM(rp.total_realisasi) AS total_realisasi_akumulatif
            FROM realisasi_per_bagian rp
            WHERE rp.laporan_id IN ({placeholders})
            GROUP BY rp.nama_bagian
        """
        kursor = koneksi.cursor(dictionary=True)
        kursor.execute(query_realisasi_akumulatif, tuple(reports_to_process_ids))
        realisasi_akumulatif_raw = kursor.fetchall()

        realisasi_akumulatif_dict = {item['nama_bagian']: item['total_realisasi_akumulatif'] for item in realisasi_akumulatif_raw}

        # --- FASE 2: Ambil DPPA dan Target dari Laporan Terakhir yang Dipilih ---
        query_dppa_target_terakhir = """
            SELECT
                nama_kategori,
                nilai_dppa,
                nilai_target
            FROM dppa_target_per_kategori
            WHERE laporan_id = %s
        """
        kursor.execute(query_dppa_target_terakhir, (last_report_id_for_dppa_target,))
        dppa_target_terakhir_raw = kursor.fetchall()

        dppa_target_dict = {item['nama_kategori']: {'dppa': item['nilai_dppa'], 'target': item['nilai_target']} for item in dppa_target_terakhir_raw}

        # --- FASE 3: Lakukan Perhitungan untuk Grafik ---
        hasil_perhitungan = []
        for nama_bagian_db_key in nama_bagian_to_kategori.keys():
            nama_bagian_db = nama_bagian_db_key
            kategori_short = nama_bagian_to_kategori.get(nama_bagian_db_key)

            realisasi = realisasi_akumulatif_dict.get(nama_bagian_db, 0.0)

            dppa_info = dppa_target_dict.get(kategori_short.replace('_', ' ').title(), {'dppa': 0.0, 'target': 0.0})

            target = dppa_info['target']
            dppa_skpd = dppa_info['dppa']

            dppatarget = (float(target) / float(dppa_skpd)) if float(dppa_skpd) != 0 else 0.0
            deviasi_kotor = float(target) - float(realisasi)
            dpparealisasi = (float(realisasi) / float(dppa_skpd)) if float(dppa_skpd) != 0 else 0.0
            deviasi_bersih = float(dppatarget) - float(dpparealisasi)

            hasil_perhitungan.append({
                'nama_bagian': nama_bagian_db,
                'realisasi_akumulatif': realisasi,
                'target_terakhir': target,
                'dppa_skpd_terakhir': dppa_skpd,
                'dppatarget': dppatarget,
                'deviasi_bersih': deviasi_bersih
            })

        # --- FASE 4: Ranking dan Warna ---
        hasil_perhitungan_sorted = sorted(hasil_perhitungan, key=lambda x: x['deviasi_bersih'])

        for i, item in enumerate(hasil_perhitungan_sorted):
            item['rank'] = i + 1
            if item['deviasi_bersih'] <= 0.0001:
                item['color'] = '#28a745'
            elif item['deviasi_bersih'] <= 0.005:
                item['color'] = '#ffc107'
            else:
                item['color'] = '#dc3545'

        chart_labels = [item['nama_bagian'] for item in hasil_perhitungan_sorted]
        deviasi_bersih_values = [str(item['deviasi_bersih']) for item in hasil_perhitungan_sorted]
        bar_colors = [item['color'] for item in hasil_perhitungan_sorted]

        return jsonify({
            'success': True,
            'chart_labels': chart_labels,
            'deviasi_bersih_values': deviasi_bersih_values,
            'bar_colors': bar_colors,
            'ranking_data': hasil_perhitungan_sorted,
            'report_period_info': report_period_info
        })

    except Exception as e:
        app.logger.error(f"Error in process_reports: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if koneksi and koneksi.is_connected():
            koneksi.close()


@app.route("/hapus", methods=['GET', 'POST'])
@login_required
def halaman_hapus():
    koneksi = get_koneksi()
    kursor = koneksi.cursor(dictionary=True)

    if request.method == 'POST':
        ids_to_delete = request.form.getlist('laporan_id')

        if not ids_to_delete:
            flash('Tidak ada laporan yang dipilih untuk dihapus.', 'warning')
            return redirect(url_for('halaman_hapus'))

        try:
            placeholders = ', '.join(['%s'] * len(ids_to_delete))
            query_hapus = f"DELETE FROM laporan_bulanan WHERE id IN ({placeholders})"

            kursor.execute(query_hapus, tuple(ids_to_delete))
            koneksi.commit()

            flash(f'{len(ids_to_delete)} laporan berhasil dihapus.', 'success')
        except Exception as e:
            koneksi.rollback()
            flash(f'Gagal menghapus laporan: {e}', 'error')
        finally:
            koneksi.close()

        return redirect(url_for('halaman_hapus'))

    try:
        query_select = "SELECT id, tahun, bulan FROM laporan_bulanan ORDER BY tahun DESC, bulan DESC"
        kursor.execute(query_select)
        daftar_laporan = kursor.fetchall()
    except Exception as e:
        daftar_laporan = []
        flash(f'Gagal mengambil data laporan: {e}', 'error')
    finally:
        koneksi.close()

    nama_bulan = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    for laporan in daftar_laporan:
        laporan['nama_bulan'] = nama_bulan.get(laporan['bulan'], 'Tidak Valid')

    return render_template('hapus.html', daftar_laporan=daftar_laporan)


# --- RUTE BARU: GENERATE PDF ---
@app.route('/generate_pdf_report', methods=['POST'])
@login_required
def generate_pdf_report():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Tidak ada data JSON yang diterima.'}), 400

        ranking_data = data.get('ranking_data', [])
        report_period_info = data.get('report_period_info', 'Periode Tidak Diketahui')

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=30, leftMargin=30,
                                topMargin=30, bottomMargin=30)

        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(name='CenteredTitle',
                                  parent=styles['h1'],
                                  alignment=TA_CENTER,
                                  fontSize=16,
                                  spaceAfter=14))
        styles.add(ParagraphStyle(name='CenteredSubtitle',
                                  parent=styles['h2'],
                                  alignment=TA_CENTER,
                                  fontSize=12,
                                  spaceAfter=10))
        styles.add(ParagraphStyle(name='NormalParagraph',
                                  parent=styles['Normal'],
                                  fontSize=10,
                                  leading=12))

        elements = []

        elements.append(Paragraph("Laporan Analisis Deviasi Realisasi Anggaran", styles['CenteredTitle']))
        elements.append(Paragraph(report_period_info, styles['CenteredSubtitle']))
        elements.append(Spacer(1, 0.2 * A4[1]))

        elements.append(Paragraph("<b>Catatan:</b> Grafik visual tidak disertakan dalam PDF. Harap lihat halaman web untuk visualisasi interaktif.", styles['NormalParagraph']))
        elements.append(Spacer(1, 0.2 * A4[1]))

        elements.append(Paragraph("<b>Tabel Ranking Deviasi Bersih</b>", styles['h3']))
        elements.append(Spacer(1, 12))

        table_data = [
            ['Rank', 'Nama Bagian', 'Deviasi Bersih', 'Realisasi Akumulatif', 'Target Terakhir']
        ]
        for item in ranking_data:
            deviasi_formatted = f"{(item['deviasi_bersih'] * 100):.4f}%"
            realisasi_formatted = format_decimal(float(item['realisasi_akumulatif']), locale='id')
            target_formatted = format_decimal(float(item['target_terakhir']), locale='id')

            table_data.append([
                str(item['rank']),
                item['nama_bagian'],
                deviasi_formatted,
                realisasi_formatted,
                target_formatted
            ])

        # Sesuaikan lebar kolom sesuai kebutuhan. Contoh:
        # col_widths = [0.8*cm, 3.5*cm, 2.5*cm, 3.5*cm, 3.5*cm]
        # Jika nama bagian atau angka besar, bisa diperlebar
        col_widths = [0.8*cm, 4*cm, 2.5*cm, 4*cm, 4*cm] # Contoh lebar kolom yang sedikit diperlebar

        table = Table(table_data, colWidths=col_widths)

        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9ecef')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'), # Nama Bagian rata kiri
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'), # Angka Realisasi dan Target rata kanan
        ]))
        elements.append(table)

        doc.build(elements)

        buffer.seek(0)

        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=laporan_deviasi_esdm.pdf'
        return response

    except Exception as e:
        app.logger.error(f"Error generating PDF: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f"Gagal membuat PDF: {str(e)}"}), 500


# --- 4. BLOK PALING BAWAH UNTUK MENJALANKAN APLIKASI ---
if __name__ == '__main__':
    app.run(debug=True)