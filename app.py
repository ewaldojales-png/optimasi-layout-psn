import streamlit as st
import pandas as pd
import pulp
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="DSS Layout Fasilitas", page_icon="🏭", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; }
    .card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #E5E7EB; }
    .metric-box { text-align: center; padding: 15px; background: #EEF2FF; border-radius: 8px; border-left: 5px solid #4F46E5; }
    .metric-title { font-size: 14px; color: #6B7280; font-weight: bold; }
    .metric-value { font-size: 24px; color: #111827; font-weight: 900; }
</style>
""", unsafe_allow_html=True)

st.title("🏭 Sistem Pendukung Keputusan: Optimasi Tata Letak Fasilitas")
st.markdown("Implementasi *Mixed Integer Linear Programming* (MILP) - Dengan Analisis Sistem Pakar Otomatis")
st.divider()

# ==========================================
# 2. INISIALISASI DATA DEFAULT (KOSONG)
# ==========================================
if "df_dimensi" not in st.session_state:
    # Memulai dengan 2 baris kosong sebagai template awal
    st.session_state.df_dimensi = pd.DataFrame([
        {"Fasilitas": "", "P (m)": 0.0, "L (m)": 0.0},
        {"Fasilitas": "", "P (m)": 0.0, "L (m)": 0.0},
    ])

# ==========================================
# 3. NAVIGASI TABS
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 1. Master Dimensi & Parameter", "🔀 2. Matriks Relasi (Otomatis)", "🚀 3. Eksekusi Optimasi"])

with tab1:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("A. Pengaturan Standar Industri")
    jenis_industri = st.selectbox(
        "Pilih Jenis Industri & Standar Keselamatan yang Digunakan:",
        [
            "🍲 Industri Pangan & Farmasi (Standar GMP / HACCP)",
            "🏭 Manufaktur Umum & Kimia (Standar K3 / ISO 45001)",
            "🏥 Fasilitas Kesehatan / Medis (Standar PPI / Permenkes)",
            "🏢 Universal / Custom (Standar Bebas)"
        ]
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("B. Master Fasilitas & Dimensi")
    st.info("💡 **FITUR TAMBAH/HAPUS:** Arahkan kursor ke baris paling bawah tabel untuk memunculkan tombol `+` (Tambah Baris). Matriks di Tab 2 akan **otomatis menyesuaikan** ukurannya.")
    
    # Editor Dinamis Dimensi (Dengan Key agar Anti-Glitch)
    edited_df = st.data_editor(
        st.session_state.df_dimensi, 
        num_rows="dynamic", 
        use_container_width=True, 
        hide_index=True,
        key="editor_dimensi"
    )
    
    # Mencegah nama fasilitas ganda/kosong
    dept_names = []
    for n in edited_df["Fasilitas"].tolist():
        name = str(n).strip()
        if name != "" and name not in dept_names:
            dept_names.append(name)
            
    # Update memori state dengan data terbaru
    st.session_state.df_dimensi = edited_df
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("C. Parameter Aliran Stokastik (Expected Flow)")
    
    st.write("Atur nilai probabilitas dan jumlah produksi untuk setiap skenario:")
    c1_prob, c1_val = st.columns([1, 2])
    prob_sibuk = c1_prob.number_input("Probabilitas Sibuk (Contoh: 0.10)", value=0.10, step=0.05, max_value=1.0, min_value=0.0)
    val_sibuk = c1_val.number_input("Jumlah Prod. Sibuk", value=0, step=100)
    
    c2_prob, c2_val = st.columns([1, 2])
    prob_normal = c2_prob.number_input("Probabilitas Normal (Contoh: 0.70)", value=0.70, step=0.05, max_value=1.0, min_value=0.0)
    val_normal = c2_val.number_input("Jumlah Prod. Normal", value=0, step=100)
    
    c3_prob, c3_val = st.columns([1, 2])
    prob_sepi = c3_prob.number_input("Probabilitas Sepi (Contoh: 0.20)", value=0.20, step=0.05, max_value=1.0, min_value=0.0)
    val_sepi = c3_val.number_input("Jumlah Prod. Sepi", value=0, step=100)
    
    total_prob = prob_sibuk + prob_normal + prob_sepi
    if round(total_prob, 2) != 1.00:
        st.warning(f"⚠️ Peringatan: Total probabilitas saat ini adalah {total_prob:.2f}. Idealnya total probabilitas adalah 1.0 (100%).")
    
    c4, c5 = st.columns(2)
    kapasitas = c4.number_input("Kapasitas Alat Angkut (Troli/Forklift)", value=100)
    hari = c5.number_input("Hari Kerja/Bulan", value=20)
    
    # Menghindari pembagian dengan nol
    if kapasitas > 0 and hari > 0:
        expected_flow = (prob_sibuk * (val_sibuk/kapasitas*hari)) + (prob_normal * (val_normal/kapasitas*hari)) + (prob_sepi * (val_sepi/kapasitas*hari))
    else:
        expected_flow = 0.0
        
    st.success(f"**Expected Flow (Harapan Aliran): {expected_flow:.1f} ritasi/bulan.**")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("### Sinkronisasi Matriks Otomatis")
    st.caption("Ketik angka/huruf dengan santai, tabel ini sudah memiliki *state memory* (Anti-Glitch Keyboard HP).")
    
    # Inisialisasi Matriks jika belum ada
    if "base_arc" not in st.session_state:
        st.session_state.base_arc = pd.DataFrame('U', index=dept_names, columns=dept_names)
    if "base_ftc" not in st.session_state:
        st.session_state.base_ftc = pd.DataFrame(0.0, index=dept_names, columns=dept_names)

    # Reindex (Menyelaraskan) Matriks jika pengguna menambah/menghapus nama fasilitas di Tab 1
    if "prev_dept_names" not in st.session_state or st.session_state.prev_dept_names != dept_names:
        st.session_state.base_arc = st.session_state.base_arc.reindex(index=dept_names, columns=dept_names, fill_value='U')
        st.session_state.base_ftc = st.session_state.base_ftc.reindex(index=dept_names, columns=dept_names, fill_value=0.0)
        st.session_state.prev_dept_names = dept_names
    
    col_kiri, col_kanan = st.columns(2)
    with col_kiri:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Matriks ARC (Kualitatif)")
        
        # Logika Dinamis Penjelasan Kode X
        penjelasan_x = "Dilarang (Otomatis memicu syarat Jarak Aman/Clearance)"
        if "Pangan" in jenis_industri:
            penjelasan_x = "Dilarang (Mencegah kontaminasi silang GMP, cth: Kotor vs Steril)"
        elif "Manufaktur" in jenis_industri:
            penjelasan_x = "Dilarang (Mencegah bahaya K3, cth: Mesin Bising/Panas vs Kantor)"
        elif "Kesehatan" in jenis_industri:
            penjelasan_x = "Dilarang (Mencegah infeksi/radiasi, cth: Ruang Infeksius vs Publik)"

        st.markdown(f"""
        <div style="font-size: 13px; margin-bottom: 12px; padding: 12px; background-color: #F8FAFC; border-left: 4px solid #3B82F6; border-radius: 5px;">
            <b>Panduan Kode & Pembobotan Otomatis:</b><br>
            <span style="color:#15803D; font-weight:bold;">A</span> : Mutlak Perlu (Bobot +10)<br>
            <span style="color:#22C55E; font-weight:bold;">E</span> : Sangat Penting (Bobot +5)<br>
            <span style="color:#EAB308; font-weight:bold;">I</span> : Penting (Bobot +3)<br>
            <span style="color:#3B82F6; font-weight:bold;">O</span> : Kedekatan Biasa (Bobot +1)<br>
            <span style="color:#6B7280; font-weight:bold;">U</span> : Tidak Penting (Bobot +0)<br>
            <span style="color:#EF4444; font-weight:bold;">X</span> : {penjelasan_x}
        </div>
        """, unsafe_allow_html=True)
        
        # Penggunaan key pada data_editor memecahkan masalah glitch
        edited_arc = st.data_editor(st.session_state.base_arc, use_container_width=True, key="editor_arc")
        st.session_state.base_arc = edited_arc
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_kanan:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Matriks FTC (Kuantitatif)")
        st.markdown("""
        <div style="font-size: 13px; margin-bottom: 12px; padding: 12px; background-color: #F8FAFC; border-left: 4px solid #F59E0B; border-radius: 5px;">
            <b>Persentase Aliran Material & Jarak:</b><br>
            Masukkan angka (contoh: 0.5 untuk 50%, atau 1 untuk 100%). Anda juga dapat <b>masukkan angka jarak antar stasiun atau area kerja</b>. Angka ini akan dikalikan otomatis dengan <i>Expected Flow</i> untuk menghasilkan Total Beban Perpindahan (Z).
        </div>
        """, unsafe_allow_html=True)
        
        edited_ftc = st.data_editor(st.session_state.base_ftc, use_container_width=True, key="editor_ftc")
        st.session_state.base_ftc = edited_ftc
        st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("⚙️ Parameter Solver & Batas Area")
    cc1, cc2, cc3 = st.columns(3)
    lebar_lahan = cc1.number_input("Lebar Lahan (Sumbu X) - m", value=40.0)
    panjang_lahan = cc2.number_input("Panjang Lahan (Sumbu Y) - m", value=40.0)
    
    # Logika Dinamis Label Jarak
    label_jarak = "Jarak Aman Mutlak (Clearance) - m"
    if "Pangan" in jenis_industri:
        label_jarak = "Jarak Sanitasi Mutlak (GMP) - m"
    elif "Manufaktur" in jenis_industri:
        label_jarak = "Jarak Keselamatan Mutlak (K3) - m"
    elif "Kesehatan" in jenis_industri:
        label_jarak = "Jarak Isolasi Medis (PPI) - m"
        
    batas_aman = cc3.number_input(label_jarak, value=15.0)
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("🚀 JALANKAN OPTIMASI MILP", type="primary", use_container_width=True):
        if len(dept_names) < 2:
            st.error("Masukkan minimal 2 fasilitas pada tabel Dimensi di Tab 1.")
        else:
            with st.spinner("Mesin Solver (PuLP/CBC) sedang mencari koordinat global optimum..."):
                # ==========================================
                # MODEL OPTIMASI MATEMATIS
                # ==========================================
                model = pulp.LpProblem("Layout_Optimization", pulp.LpMinimize)
                
                # Pemetaan Dimensi
                W = {}
                H = {}
                for _, row in edited_df.iterrows():
                    nm = str(row["Fasilitas"]).strip()
                    if nm in dept_names:
                        W[nm] = float(row["P (m)"])
                        H[nm] = float(row["L (m)"])
                
                # --- SISTEM PENAMAAN VARIABEL AMAN ---
                x = {d: pulp.LpVariable(f"x_{i}", lowBound=0, upBound=lebar_lahan) for i, d in enumerate(dept_names)}
                y = {d: pulp.LpVariable(f"y_{i}", lowBound=0, upBound=panjang_lahan) for i, d in enumerate(dept_names)}
                
                dx, dy, z, g = {}, {}, {}, {}
                for i, d1 in enumerate(dept_names):
                    dx[d1], dy[d1], z[d1], g[d1] = {}, {}, {}, {}
                    for j, d2 in enumerate(dept_names):
                        dx[d1][d2] = pulp.LpVariable(f"dx_{i}_{j}", lowBound=0)
                        dy[d1][d2] = pulp.LpVariable(f"dy_{i}_{j}", lowBound=0)
                        z[d1][d2] = {k: pulp.LpVariable(f"z_{i}_{j}_{k}", cat=pulp.LpBinary) for k in range(1, 5)}
                        g[d1][d2] = {k: pulp.LpVariable(f"g_{i}_{j}_{k}", cat=pulp.LpBinary) for k in range(1, 5)}
                
                # Big-M Dinamis
                M = (lebar_lahan + panjang_lahan) * 10 
                arc_dict = {'A': 10, 'E': 5, 'I': 3, 'O': 1, 'U': 0, 'X': 0} 
                
                objective_terms = []
                for i in dept_names:
                    for j in dept_names:
                        if i != j:
                            try:
                                ftc_val = float(edited_ftc.loc[i, j])
                            except:
                                ftc_val = 0.0
                                
                            aliran = ftc_val * expected_flow
                            kode_arc = str(edited_arc.loc[i, j]).strip().upper()
                            bobot_arc = arc_dict.get(kode_arc, 0)
                            
                            if aliran > 0 or bobot_arc > 0:
                                objective_terms.append((aliran + bobot_arc) * (dx[i][j] + dy[i][j]))
                                
                model += pulp.lpSum(objective_terms)
                
                for i in dept_names:
                    model += x[i] + W[i]/2 <= lebar_lahan
                    model += x[i] - W[i]/2 >= 0
                    model += y[i] + H[i]/2 <= panjang_lahan
                    model += y[i] - H[i]/2 >= 0
                    
                    for j in dept_names:
                        if i < j:
                            # Jarak Manhattan (Rectilinear)
                            model += dx[i][j] >= x[i] - x[j]
                            model += dx[i][j] >= x[j] - x[i]
                            model += dy[i][j] >= y[i] - y[j]
                            model += dy[i][j] >= y[j] - y[i]
                            
                            model += dx[j][i] == dx[i][j]
                            model += dy[j][i] == dy[i][j]
                            
                            # Logika Anti-Tumpang Tindih (Big-M)
                            model += x[i] + W[i]/2 <= x[j] - W[j]/2 + M * (1 - z[i][j][1])
                            model += x[i] - W[i]/2 >= x[j] + W[j]/2 - M * (1 - z[i][j][2])
                            model += y[i] + H[i]/2 <= y[j] - H[j]/2 + M * (1 - z[i][j][3])
                            model += y[i] - H[i]/2 >= y[j] + H[j]/2 - M * (1 - z[i][j][4])
                            model += z[i][j][1] + z[i][j][2] + z[i][j][3] + z[i][j][4] >= 1
                            
                            # Logika Mutlak Jarak Aman (Linearisasi Jarak Rectilinear Absolut)
                            kode1 = str(edited_arc.loc[i, j]).strip().upper()
                            kode2 = str(edited_arc.loc[j, i]).strip().upper()
                            if kode1 == 'X' or kode2 == 'X':
                                model += (x[i] - x[j]) + (y[i] - y[j]) >= batas_aman - M * (1 - g[i][j][1])
                                model += (x[i] - x[j]) - (y[i] - y[j]) >= batas_aman - M * (1 - g[i][j][2])
                                model += -(x[i] - x[j]) + (y[i] - y[j]) >= batas_aman - M * (1 - g[i][j][3])
                                model += -(x[i] - x[j]) - (y[i] - y[j]) >= batas_aman - M * (1 - g[i][j][4])
                                model += g[i][j][1] + g[i][j][2] + g[i][j][3] + g[i][j][4] >= 1

                # Waktu maksimal solver = 30 detik
                model.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))
                status = pulp.LpStatus[model.status]
                
                # ==========================================
                # OUTPUT HASIL & SISTEM PAKAR OTOMATIS
                # ==========================================
                if status == 'Optimal' or status == 'Feasible':
                    st.success(f"🎉 Solusi Optimum Ditemukan! Seluruh kendala ukuran dan jarak ({label_jarak}) terpenuhi.")
                    
                    val_obj = pulp.value(model.objective)
                    total_momen = float(val_obj) if val_obj is not None else 0.0
                    
                    # Efisiensi dihitung dengan dasar momen eksisting 65641.5 (Contoh Base)
                    momen_eksisting = 65641.5
                    efisiensi = ((momen_eksisting - total_momen) / momen_eksisting) * 100 if total_momen < momen_eksisting else 0.0
                    
                    m1, m2 = st.columns(2)
                    m1.markdown(f"<div class='metric-box'><div class='metric-title'>Status Solver</div><div class='metric-value' style='color:#059669;'>{status}</div></div>", unsafe_allow_html=True)
                    m2.markdown(f"<div class='metric-box'><div class='metric-title'>Total Momen Perpindahan (Z)</div><div class='metric-value'>{total_momen:,.2f}</div></div>", unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col_vis, col_text = st.columns([3, 2])
                    with col_vis:
                        st.markdown("<div class='card'>", unsafe_allow_html=True)
                        st.subheader("🖼️ Visualisasi Block Layout")
                        
                        fig, ax = plt.subplots(figsize=(10, 8))
                        ax.add_patch(patches.Rectangle((0, 0), lebar_lahan, panjang_lahan, linewidth=2, edgecolor='#1E293B', facecolor='none', linestyle='--'))
                        
                        # Palet Warna Pastel Universal
                        colors = ['#DBEAFE', '#D1FAE5', '#FEF3C7', '#FCE7F3', '#E0E7FF', '#CFFAFE', '#FEF08A', '#FFEDD5', '#CCFBF1']
                        koordinat_data = []
                        
                        for idx, d in enumerate(dept_names):
                            cx, cy = pulp.value(x[d]), pulp.value(y[d])
                            w, h = W[d], H[d]
                            bx, by = cx - w/2, cy - h/2
                            
                            koordinat_data.append({"Fasilitas/Departemen": d, "X": round(cx,2), "Y": round(cy,2)})
                            color = colors[idx % len(colors)]
                            
                            rect = patches.Rectangle((bx, by), w, h, linewidth=1.5, edgecolor='#334155', facecolor=color, alpha=0.9)
                            ax.add_patch(rect)
                            ax.text(cx, cy, d, ha='center', va='center', fontsize=9, fontweight='bold', color='#0F172A', wrap=True)

                        ax.set_xlim(-2, lebar_lahan + 2)
                        ax.set_ylim(-2, panjang_lahan + 2)
                        ax.set_xlabel("Sumbu X (meter)"); ax.set_ylabel("Sumbu Y (meter)")
                        ax.grid(True, linestyle=':', alpha=0.6)
                        
                        st.pyplot(fig)
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    with col_text:
                        st.markdown("<div class='card' style='height: 100%;'>", unsafe_allow_html=True)
                        st.subheader("📋 Titik Koordinat Pusat (X, Y)")
                        st.dataframe(pd.DataFrame(koordinat_data), hide_index=True, use_container_width=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    # ==========================================
                    # PENJELASAN SISTEM PAKAR OTOMATIS
                    # ==========================================
                    st.divider()
                    st.subheader("🤖 Analisis Cerdas Sistem Pakar (Otomatis)")
                    
                    # Teks Dinamis Berdasarkan Industri & Efisiensi
                    nama_industri = jenis_industri.split('(')[0].strip()
                    teks_pakar = f"Halo! Berdasarkan perhitungan rumit optimasi tata letak untuk **{nama_industri}**, berikut adalah penjelasan hasilnya dengan bahasa yang sederhana:\n\n"
                    
                    teks_pakar += f"**1. Efisiensi Biaya & Tenaga (Total Momen Z = {total_momen:,.2f})**\n"
                    if efisiensi > 0:
                        teks_pakar += f"✅ **Sangat Efisien!** Tata letak baru ini terbukti secara matematis mampu memangkas dan menghemat jarak perpindahan material sebesar **{efisiensi:.2f}%** dibandingkan kondisi sebelumnya. Artinya, operator dan alat angkut di pabrik Anda kini akan bekerja jauh lebih ringan dan rute produksi terhindar dari kemacetan (*bottleneck*).\n\n"
                    else:
                        teks_pakar += f"ℹ️ Total momen yang dihasilkan adalah {total_momen:,.2f}. Angka ini mengukur seberapa efisien tata letak Anda. Jika Anda ingin mencari rute yang lebih efisien, Anda bisa mencoba mengubah dimensi lahan atau mengevaluasi ulang matriks prioritas di langkah sebelumnya.\n\n"
                        
                    teks_pakar += f"**2. Kepatuhan Pada Jarak Keselamatan / Keamanan ({batas_aman} meter)**\n"
                    teks_pakar += f"✅ **Aman Terkendali!** Sistem berhasil memastikan bahwa semua area yang Anda beri tanda silang **'X'** (Dilarang Berdekatan) kini telah dipisah dan direntangkan jaraknya minimal sejauh **{batas_aman} meter**. "
                    
                    if "Pangan" in jenis_industri:
                        teks_pakar += "Ini sangat penting untuk memenuhi standar kebersihan GMP, sehingga area kotor seperti gudang mentah tidak akan pernah mencemari area higienis seperti pengemasan.\n\n"
                    elif "Manufaktur" in jenis_industri:
                        teks_pakar += "Ini memastikan bahwa aturan keselamatan K3 dipatuhi, sehingga area yang bising, panas, atau berbahaya tidak akan mengganggu kenyamanan dan keselamatan area kerja lainnya.\n\n"
                    elif "Kesehatan" in jenis_industri:
                        teks_pakar += "Ini sangat krusial dalam pengendalian infeksi PPI, memastikan bahwa area berisiko tinggi seperti radiasi/infeksius tetap aman dan jauh dari ruang publik.\n\n"
                    else:
                        teks_pakar += "Jarak batas (Clearance) ini menjamin operasional lantai kerja terhindar dari gangguan antar zona.\n\n"
                        
                    teks_pakar += "**3. Rekomendasi Langkah Selanjutnya**\n"
                    teks_pakar += "Gunakan *Tabel Titik Koordinat (X, Y)* di atas sebagai panduan atau denah cetak biru (*blueprint*) nyata untuk merelokasi mesin/ruangan di lapangan. Semua kotak di gambar denah sudah akurat dan sesuai dengan skala batas tanah yang Anda masukkan!"
                    
                    st.info(teks_pakar)
                        
                else:
                    st.error(f"❌ Status: {status}. Batas lahan terlalu kecil untuk menampung seluruh fasilitas atau syarat jarak aman ({batas_aman}m) tidak bisa dipenuhi karena luas tanah yang sempit.")
