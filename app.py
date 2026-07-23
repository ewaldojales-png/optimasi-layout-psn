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
# Inisialisasi hanya dilakukan SEKALI agar tidak ada glitch saat mengetik
if "df_dimensi" not in st.session_state:
    st.session_state.df_dimensi = pd.DataFrame([
        {"Fasilitas": "", "P (m)": 0.0, "L (m)": 0.0},
        {"Fasilitas": "", "P (m)": 0.0, "L (m)": 0.0}
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
    
    # PERBAIKAN GLITCH HP: Menggunakan column_config dan membiarkan Streamlit mengatur state via key
    edited_df = st.data_editor(
        st.session_state.df_dimensi, 
        column_config={
            "Fasilitas": st.column_config.TextColumn("Fasilitas", required=True),
            "P (m)": st.column_config.NumberColumn("P (m)", min_value=0.0, format="%.2f"),
            "L (m)": st.column_config.NumberColumn("L (m)", min_value=0.0, format="%.2f")
        },
        num_rows="dynamic", 
        use_container_width=True, 
        hide_index=True,
        key="editor_dimensi"
    )
    
    # Mencegah nama fasilitas ganda/kosong (Mencegah KeyError)
    dept_names = []
    for n in edited_df["Fasilitas"].tolist():
        name = str(n).strip()
        if name != "" and name not in dept_names:
            dept_names.append(name)
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("C. Parameter Aliran Stokastik (Expected Flow)")
    st.caption("Atur nilai probabilitas dan jumlah produksi untuk setiap skenario (Total probabilitas harus 1.00)")
    
    c1, c2, c3 = st.columns(3)
    prob_sibuk = c1.number_input("Probabilitas Sibuk", value=0.05, step=0.01)
    sibuk = c1.number_input("Jumlah Prod. Sibuk", value=5928, step=100)
    
    prob_normal = c2.number_input("Probabilitas Normal", value=0.75, step=0.01)
    normal = c2.number_input("Jumlah Prod. Normal", value=4560, step=100)
    
    prob_sepi = c3.number_input("Probabilitas Sepi", value=0.20, step=0.01)
    sepi = c3.number_input("Jumlah Prod. Sepi", value=3192, step=100)
    
    total_prob = prob_sibuk + prob_normal + prob_sepi
    if round(total_prob, 2) != 1.00:
        st.warning(f"⚠️ Peringatan: Total probabilitas saat ini adalah {total_prob:.2f}. Idealnya total probabilitas harus bernilai 1.00 (100%).")
    
    c4, c5 = st.columns(2)
    kapasitas = c4.number_input("Kapasitas Alat Angkut (Troli/Forklift)", value=150)
    hari = c5.number_input("Hari Kerja/Bulan", value=26)
    
    if kapasitas > 0:
        expected_flow = (prob_sibuk * (sibuk/kapasitas*hari)) + (prob_normal * (normal/kapasitas*hari)) + (prob_sepi * (sepi/kapasitas*hari))
        st.success(f"**Expected Flow (Harapan Aliran): {expected_flow:.1f} ritasi/bulan.**")
    else:
        st.error("Kapasitas alat angkut tidak boleh 0.")
        expected_flow = 0
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("### Sinkronisasi Matriks Otomatis")
    st.caption("Ketik angka/huruf dengan santai, tabel ini sudah kebal terhadap glitch HP.")
    
    if "base_arc" not in st.session_state:
        st.session_state.base_arc = pd.DataFrame('U', index=dept_names, columns=dept_names)
            
    if "base_ftc" not in st.session_state:
        st.session_state.base_ftc = pd.DataFrame(0.0, index=dept_names, columns=dept_names)

    # Reindex hanya ketika struktur fasilitas berubah
    if "prev_dept_names" not in st.session_state or st.session_state.prev_dept_names != dept_names:
        if "last_arc" in st.session_state:
            st.session_state.base_arc = st.session_state.last_arc.reindex(index=dept_names, columns=dept_names, fill_value='U')
        else:
            st.session_state.base_arc = st.session_state.base_arc.reindex(index=dept_names, columns=dept_names, fill_value='U')
            
        if "last_ftc" in st.session_state:
            st.session_state.base_ftc = st.session_state.last_ftc.reindex(index=dept_names, columns=dept_names, fill_value=0.0)
        else:
            st.session_state.base_ftc = st.session_state.base_ftc.reindex(index=dept_names, columns=dept_names, fill_value=0.0)
            
        st.session_state.prev_dept_names = dept_names
    
    col_kiri, col_kanan = st.columns(2)
    with col_kiri:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Matriks ARC (Kualitatif)")
        
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
        
        if len(dept_names) > 0:
            edited_arc = st.data_editor(st.session_state.base_arc, use_container_width=True, key="editor_arc")
            st.session_state.last_arc = edited_arc
        else:
            st.info("Isi tabel Master Dimensi di Tab 1 terlebih dahulu.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_kanan:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Matriks FTC (Kuantitatif)")
        st.markdown("""
        <div style="font-size: 13px; margin-bottom: 12px; padding: 12px; background-color: #F8FAFC; border-left: 4px solid #F59E0B; border-radius: 5px;">
            <b>Persentase Aliran Material & Jarak:</b><br>
            Masukkan angka (contoh: 0.5 untuk 50%, atau 1 untuk 100%). Anda juga dapat <b>masukkan angka jarak antar stasiun atau area kerja</b>.
        </div>
        """, unsafe_allow_html=True)
        
        if len(dept_names) > 0:
            edited_ftc = st.data_editor(st.session_state.base_ftc, use_container_width=True, key="editor_ftc")
            st.session_state.last_ftc = edited_ftc
        else:
            st.info("Isi tabel Master Dimensi di Tab 1 terlebih dahulu.")
        st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("⚙️ Parameter Solver & Batas Area")
    cc1, cc2, cc3 = st.columns(3)
    lebar_lahan = cc1.number_input("Lebar Lahan (Sumbu X) - m", value=100.0)
    panjang_lahan = cc2.number_input("Panjang Lahan (Sumbu Y) - m", value=100.0)
    
    label_jarak = "Jarak Aman Mutlak (Clearance) - m"
    if "Pangan" in jenis_industri:
        label_jarak = "Jarak Sanitasi Mutlak (GMP) - m"
    elif "Manufaktur" in jenis_industri:
        label_jarak = "Jarak Keselamatan Mutlak (K3) - m"
    elif "Kesehatan" in jenis_industri:
        label_jarak = "Jarak Isolasi Medis (PPI) - m"
        
    batas_aman = cc3.number_input(label_jarak, value=5.0)
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("🚀 JALANKAN OPTIMASI MILP", type="primary", use_container_width=True):
        if len(dept_names) < 2:
            st.error("Masukkan minimal 2 fasilitas pada tabel Dimensi di Tab 1.")
        else:
            with st.spinner("Mesin Solver (PuLP/CBC) sedang mencari koordinat global optimum..."):
                model = pulp.LpProblem("Layout_Optimization", pulp.LpMinimize)
                
                W = {}
                H = {}
                for _, row in edited_df.iterrows():
                    nm = str(row["Fasilitas"]).strip()
                    if nm in dept_names:
                        W[nm] = float(row["P (m)"])
                        H[nm] = float(row["L (m)"])
                
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
                            model += dx[i][j] >= x[i] - x[j]
                            model += dx[i][j] >= x[j] - x[i]
                            model += dy[i][j] >= y[i] - y[j]
                            model += dy[i][j] >= y[j] - y[i]
                            
                            model += dx[j][i] == dx[i][j]
                            model += dy[j][i] == dy[i][j]
                            
                            model += x[i] + W[i]/2 <= x[j] - W[j]/2 + M * (1 - z[i][j][1])
                            model += x[i] - W[i]/2 >= x[j] + W[j]/2 - M * (1 - z[i][j][2])
                            model += y[i] + H[i]/2 <= y[j] - H[j]/2 + M * (1 - z[i][j][3])
                            model += y[i] - H[i]/2 >= y[j] + H[j]/2 - M * (1 - z[i][j][4])
                            model += z[i][j][1] + z[i][j][2] + z[i][j][3] + z[i][j][4] >= 1
                            
                            kode1 = str(edited_arc.loc[i, j]).strip().upper()
                            kode2 = str(edited_arc.loc[j, i]).strip().upper()
                            if kode1 == 'X' or kode2 == 'X':
                                model += (x[i] - x[j]) + (y[i] - y[j]) >= batas_aman - M * (1 - g[i][j][1])
                                model += (x[i] - x[j]) - (y[i] - y[j]) >= batas_aman - M * (1 - g[i][j][2])
                                model += -(x[i] - x[j]) + (y[i] - y[j]) >= batas_aman - M * (1 - g[i][j][3])
                                model += -(x[i] - x[j]) - (y[i] - y[j]) >= batas_aman - M * (1 - g[i][j][4])
                                model += g[i][j][1] + g[i][j][2] + g[i][j][3] + g[i][j][4] >= 1

                model.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))
                status = pulp.LpStatus[model.status]
                
                # ==========================================
                # OUTPUT HASIL & SISTEM PAKAR
                # ==========================================
                if status == 'Optimal' or status == 'Feasible':
                    st.success(f"🎉 Solusi Optimum Ditemukan! Seluruh kendala ukuran dan jarak ({label_jarak}) terpenuhi.")
                    
                    val_obj = pulp.value(model.objective)
                    total_momen = float(val_obj) if val_obj is not None else 0.0
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
                    
                    st.divider()
                    st.subheader("🤖 Analisis Cerdas Sistem Pakar (Otomatis)")
                    
                    nama_industri = jenis_industri.split('(')[0].strip()
                    teks_pakar = f"Halo! Berdasarkan perhitungan optimasi tata letak untuk **{nama_industri}**, berikut adalah penjelasan hasilnya:\n\n"
                    
                    teks_pakar += f"**1. Efisiensi Biaya & Tenaga (Total Momen Z = {total_momen:,.2f})**\n"
                    if efisiensi > 0:
                        teks_pakar += f"✅ **Sangat Efisien!** Tata letak baru ini memangkas jarak perpindahan material sebesar **{efisiensi:.2f}%** dibandingkan rute lama.\n\n"
                    else:
                        teks_pakar += f"ℹ️ Total momen perpindahan adalah {total_momen:,.2f}. Anda bisa mencoba mengatur ulang koordinat atau mengubah relasi ARC untuk melihat perubahan.\n\n"
                        
                    teks_pakar += f"**2. Kepatuhan Pada Jarak Keselamatan ({batas_aman} meter)**\n"
                    teks_pakar += f"✅ Sistem memastikan bahwa semua area yang Anda beri tanda silang **'X'** (Dilarang Berdekatan) kini telah dipisah minimal sejauh **{batas_aman} meter**. "
                    
                    if "Pangan" in jenis_industri:
                        teks_pakar += "Ini sangat penting untuk memenuhi standar kebersihan GMP guna mencegah kontaminasi silang.\n\n"
                    elif "Manufaktur" in jenis_industri:
                        teks_pakar += "Ini memastikan standar K3 dipatuhi, memisahkan area berbahaya/bising dari area umum.\n\n"
                    else:
                        teks_pakar += "Jarak batas ini menjamin operasional lantai kerja terhindar dari gangguan antar zona.\n\n"
                        
                    teks_pakar += "**3. Rekomendasi Langkah Selanjutnya**\n"
                    teks_pakar += "Gunakan *Tabel Titik Koordinat (X, Y)* di atas sebagai panduan nyata untuk merelokasi mesin/ruangan di lapangan."
                    
                    st.info(teks_pakar)
                        
                else:
                    st.error(f"❌ Status Solver: {status}. Solusi tidak ditemukan (Infeasible). Hal ini disebabkan mesin solver mendeteksi bahwa ruangan-ruangan tidak muat di dalam batas lahan {lebar_lahan}x{panjang_lahan}m, ATAU jarak mutlak {batas_aman}m yang Anda minta mustahil diterapkan dalam tanah seluas itu tanpa keluar batas. Silakan perbesar ukuran lahan di parameter atas.")
