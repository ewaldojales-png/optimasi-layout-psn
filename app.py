import streamlit as st
import pandas as pd
import pulp
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math

# ==========================================
# 1. KONFIGURASI HALAMAN & TEMA (Gaya Figma)
# ==========================================
st.set_page_config(page_title="DSS Layout Pabrik PSN", page_icon="🏭", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; }
    .css-1d391kg { padding-top: 1rem; }
    h1, h2, h3 { color: #1F2937; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #E5E7EB; }
    .metric-box { text-align: center; padding: 15px; background: #EEF2FF; border-radius: 8px; border-left: 5px solid #4F46E5; }
    .metric-title { font-size: 14px; color: #6B7280; font-weight: bold; }
    .metric-value { font-size: 24px; color: #111827; font-weight: 900; }
</style>
""", unsafe_allow_html=True)

st.title("🏭 Sistem Pendukung Keputusan: Optimasi Tata Letak PT. PSN")
st.markdown("Implementasi *Mixed Integer Linear Programming* (MILP) mempertimbangkan standar sanitasi *Good Manufacturing Practices* (GMP).")
st.divider()

# ==========================================
# 2. INISIALISASI SESSION STATE (Data Dinamis)
# ==========================================
# A. Data Dimensi Fasilitas
if "df_dimensi" not in st.session_state:
    st.session_state.df_dimensi = pd.DataFrame([
        {"Fasilitas": "Gudang Bahan Baku", "P (m)": 8.0, "L (m)": 3.5},
        {"Fasilitas": "R. Giling & Adonan", "P (m)": 6.7, "L (m)": 4.6},
        {"Fasilitas": "R. Pencetakan", "P (m)": 20.0, "L (m)": 7.0},
        {"Fasilitas": "R. Toping", "P (m)": 8.0, "L (m)": 4.0},
        {"Fasilitas": "Pengukusan", "P (m)": 12.0, "L (m)": 5.0},
        {"Fasilitas": "Penirisan", "P (m)": 12.0, "L (m)": 7.0},
        {"Fasilitas": "Packing", "P (m)": 4.0, "L (m)": 4.0},
        {"Fasilitas": "Gudang Finish Good", "P (m)": 6.2, "L (m)": 3.0},
    ])

# Ambil daftar nama departemen saat ini (Hapus yang kosong)
dept_names = [str(d).strip() for d in st.session_state.df_dimensi["Fasilitas"].tolist() if str(d).strip() != ""]

# B. Data Matriks ARC
if "df_arc" not in st.session_state:
    arc = pd.DataFrame('U', index=dept_names, columns=dept_names)
    # Default GMP
    arc.loc["Gudang Bahan Baku", "Packing"] = 'X'
    arc.loc["Gudang Bahan Baku", "Gudang Finish Good"] = 'X'
    arc.loc["R. Giling & Adonan", "Packing"] = 'X'
    arc.loc["R. Giling & Adonan", "Gudang Finish Good"] = 'X'
    st.session_state.df_arc = arc

# C. Data Matriks FTC
if "df_ftc" not in st.session_state:
    ftc = pd.DataFrame(0.0, index=dept_names, columns=dept_names)
    # Default Sekuensial
    ftc.loc["Gudang Bahan Baku", "R. Giling & Adonan"] = 1.0
    ftc.loc["R. Giling & Adonan", "R. Pencetakan"] = 1.0
    ftc.loc["R. Pencetakan", "R. Toping"] = 1.0
    ftc.loc["R. Toping", "Pengukusan"] = 1.0
    ftc.loc["Pengukusan", "Penirisan"] = 1.0
    ftc.loc["Penirisan", "Packing"] = 1.0
    ftc.loc["Packing", "Gudang Finish Good"] = 1.0
    st.session_state.df_ftc = ftc

# --- FUNGSI SINKRONISASI MATRIKS (Otomatis menyesuaikan baris & kolom) ---
st.session_state.df_arc = st.session_state.df_arc.reindex(index=dept_names, columns=dept_names, fill_value='U')
st.session_state.df_ftc = st.session_state.df_ftc.reindex(index=dept_names, columns=dept_names, fill_value=0.0)

# Dictionary Bobot ARC
arc_dict = {'A': 10, 'E': 5, 'I': 3, 'O': 1, 'U': 0, 'X': -10}

# ==========================================
# 3. STRUKTUR NAVIGASI (TABS)
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 1. Parameter & Peramalan", "🔀 2. Relasi (ARC & FTC)", "🚀 3. Eksekusi Optimasi & Analisis"])

# --- TAB 1: PARAMETER DASAR ---
with tab1:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("A. Peramalan Aliran Material (Pendekatan Stokastik)")
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        sibuk = st.number_input("Produksi/Hari (Sibuk) - Prob 0.05", value=5928, step=100)
    with col_b:
        normal = st.number_input("Produksi/Hari (Normal) - Prob 0.75", value=4560, step=100)
    with col_c:
        sepi = st.number_input("Produksi/Hari (Sepi) - Prob 0.20", value=3192, step=100)
        
    c_cap, c_hari = st.columns(2)
    kapasitas = c_cap.number_input("Kapasitas Troli (Pack)", value=150)
    hari_kerja = c_hari.number_input("Hari Kerja/Bulan", value=26)
    
    # Hitung Ritasi
    rit_sibuk = (sibuk / kapasitas) * hari_kerja
    rit_normal = (normal / kapasitas) * hari_kerja
    rit_sepi = (sepi / kapasitas) * hari_kerja
    expected_flow = (0.05 * rit_sibuk) + (0.75 * rit_normal) + (0.20 * rit_sepi)
    
    st.info(f"💡 **Expected Flow (Aliran Harapan): {expected_flow:.1f} ritasi/bulan.** Angka ini dikalikan otomatis dengan persentase FTC.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("B. Dimensi Fasilitas Produksi")
    st.caption("✨ Anda dapat **menambah (Add Row)** atau **menghapus** departemen di sini. Matriks ARC dan FTC di Tab 2 akan otomatis menyesuaikan bentuknya!")
    
    # Editor Dimensi (Bisa tambah/hapus baris)
    edited_dimensi = st.data_editor(
        st.session_state.df_dimensi, 
        num_rows="dynamic", # FITUR TAMBAH BARIS AKTIF
        use_container_width=True, 
        hide_index=True
    )
    # Simpan perubahan ke session state
    st.session_state.df_dimensi = edited_dimensi
    st.markdown("</div>", unsafe_allow_html=True)

# --- TAB 2: ARC & FTC ---
with tab2:
    st.info("💡 Matriks di bawah ini otomatis menyesuaikan (baris & kolom) dengan jumlah fasilitas yang Anda input di Tab 1.")
    col_kiri, col_kanan = st.columns([1, 1])
    
    with col_kiri:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Tabel Kedekatan ARC")
        st.caption("Kode: A (10), E (5), I (3), O (1), U (0), X (-10 / Dilarang)")
        
        edited_arc = st.data_editor(st.session_state.df_arc, use_container_width=True)
        st.session_state.df_arc = edited_arc
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_kanan:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Matriks From-To Chart (FTC)")
        st.caption("Persentase aliran material antar fasilitas (%)")
        
        edited_ftc = st.data_editor(st.session_state.df_ftc, use_container_width=True)
        st.session_state.df_ftc = edited_ftc
        st.markdown("</div>", unsafe_allow_html=True)

# --- TAB 3: OPTIMASI & HASIL ---
with tab3:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("⚙️ Parameter Solver & Batas Lahan")
    
    c1, c2, c3 = st.columns(3)
    lebar_lahan = c1.number_input("Lebar Area Lahan (Sumbu X) - meter", value=40.0)
    panjang_lahan = c2.number_input("Panjang Area Lahan (Sumbu Y) - meter", value=40.0)
    batas_gmp = c3.number_input("Jarak Minimal Sanitasi (GMP) - meter", value=15.0)
    
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("🚀 JALANKAN OPTIMASI MILP", use_container_width=True, type="primary"):
        # Update nama departemen terkini
        current_depts = [str(d).strip() for d in st.session_state.df_dimensi["Fasilitas"].tolist() if str(d).strip() != ""]
        
        if len(current_depts) < 2:
            st.error("Masukkan minimal 2 fasilitas di Tab 1 untuk melakukan optimasi.")
        else:
            with st.spinner('Solver sedang mencari koordinat global optimum (menghindari tumpang tindih & menerapkan GMP)...'):
                
                # --- SETUP MODEL PuLP ---
                model = pulp.LpProblem("Layout_PSN", pulp.LpMinimize)
                
                # Dimensi dari tabel
                W = {row["Fasilitas"]: row["P (m)"] for _, row in st.session_state.df_dimensi.iterrows() if row["Fasilitas"] in current_depts}
                H = {row["Fasilitas"]: row["L (m)"] for _, row in st.session_state.df_dimensi.iterrows() if row["Fasilitas"] in current_depts}
                
                # Variabel Koordinat Titik Tengah
                x = pulp.LpVariable.dicts("x", current_depts, lowBound=0, upBound=lebar_lahan, cat=pulp.LpContinuous)
                y = pulp.LpVariable.dicts("y", current_depts, lowBound=0, upBound=panjang_lahan, cat=pulp.LpContinuous)
                
                # Variabel Jarak Rectilinear
                dx = pulp.LpVariable.dicts("dx", (current_depts, current_depts), lowBound=0, cat=pulp.LpContinuous)
                dy = pulp.LpVariable.dicts("dy", (current_depts, current_depts), lowBound=0, cat=pulp.LpContinuous)
                
                # Variabel Biner Non-Overlap (Metode Big-M)
                z_bin = pulp.LpVariable.dicts("z_bin", (current_depts, current_depts, range(1, 5)), 0, 1, pulp.LpBinary)
                M = 1000 # Big-M
                
                # --- FUNGSI TUJUAN ---
                objective_terms = []
                for i in current_depts:
                    for j in current_depts:
                        if i != j:
                            aliran = st.session_state.df_ftc.loc[i, j] * expected_flow
                            kode_arc = st.session_state.df_arc.loc[i, j]
                            bobot_arc = arc_dict.get(kode_arc, 0)
                            
                            if aliran > 0 or bobot_arc > 0:
                                objective_terms.append((aliran + bobot_arc) * (dx[i][j] + dy[i][j]))
                                
                model += pulp.lpSum(objective_terms)
                
                # --- FUNGSI KENDALA (CONSTRAINTS) ---
                for i in current_depts:
                    model += x[i] + W[i]/2 <= lebar_lahan
                    model += x[i] - W[i]/2 >= 0
                    model += y[i] + H[i]/2 <= panjang_lahan
                    model += y[i] - H[i]/2 >= 0
                    
                    for j in current_depts:
                        if i < j:
                            # 1. Linearisasi Jarak Manhattan
                            model += dx[i][j] >= x[i] - x[j]
                            model += dx[i][j] >= x[j] - x[i]
                            model += dy[i][j] >= y[i] - y[j]
                            model += dy[i][j] >= y[j] - y[i]
                            
                            # 2. Kendala Non-Overlap (Big-M)
                            model += x[i] + W[i]/2 <= x[j] - W[j]/2 + M * (1 - z_bin[i][j][1])
                            model += x[i] - W[i]/2 >= x[j] + W[j]/2 - M * (1 - z_bin[i][j][2])
                            model += y[i] + H[i]/2 <= y[j] - H[j]/2 + M * (1 - z_bin[i][j][3])
                            model += y[i] - H[i]/2 >= y[j] + H[j]/2 - M * (1 - z_bin[i][j][4])
                            model += z_bin[i][j][1] + z_bin[i][j][2] + z_bin[i][j][3] + z_bin[i][j][4] >= 1
                            
                            # 3. Kendala Sanitasi GMP ('X' di ARC)
                            if st.session_state.df_arc.loc[i, j] == 'X' or st.session_state.df_arc.loc[j, i] == 'X':
                                model += dx[i][j] + dy[i][j] >= batas_gmp

                # --- RUN SOLVER ---
                model.solve(pulp.PULP_CBC_CMD(msg=0))
                status = pulp.LpStatus[model.status]
                
                # ==========================================
                # HASIL & DASHBOARD
                # ==========================================
                if status == 'Optimal':
                    st.success("🎉 Solusi Global Optimum Ditemukan!")
                    total_momen = pulp.value(model.objective)
                    
                    # Tampilkan Objective Value
                    st.metric(label="Global Objective Value (Total Biaya/Jarak Terbobot)", value=f"{total_momen:,.2f}")
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col_vis, col_text = st.columns([3, 2])
                    
                    with col_vis:
                        st.markdown("<div class='card'>", unsafe_allow_html=True)
                        st.subheader("🖼️ Visualisasi Block Layout (Usulan)")
                        
                        fig, ax = plt.subplots(figsize=(10, 8))
                        ax.add_patch(patches.Rectangle((0, 0), lebar_lahan, panjang_lahan, linewidth=2, edgecolor='red', facecolor='none', linestyle='--'))
                        
                        colors = ['#DBEAFE', '#D1FAE5', '#FEF3C7', '#FCE7F3', '#E0E7FF', '#CFFAFE', '#FEF08A', '#N/A']
                        koordinat_data = []
                        
                        for idx, d in enumerate(current_depts):
                            cx, cy = pulp.value(x[d]), pulp.value(y[d])
                            w, h = W[d], H[d]
                            bx, by = cx - w/2, cy - h/2
                            
                            koordinat_data.append({"Departemen": d, "X (Pusat)": round(cx,2), "Y (Pusat)": round(cy,2)})
                            
                            # Pewarnaan khusus GMP (Otomatis jika ada huruf 'X' di ARC)
                            is_kotor = any(st.session_state.df_arc.loc[d, k] == 'X' for k in current_depts)
                            color = "#FCA5A5" if is_kotor and idx < len(current_depts)/2 else ("#6EE7B7" if is_kotor else colors[idx % len(colors)])
                            
                            rect = patches.Rectangle((bx, by), w, h, linewidth=1.5, edgecolor='#1F2937', facecolor=color, alpha=0.9)
                            ax.add_patch(rect)
                            ax.text(cx, cy, d, ha='center', va='center', fontsize=9, fontweight='bold', color='#111827', wrap=True)

                        ax.set_xlim(-2, lebar_lahan + 2)
                        ax.set_ylim(-2, panjang_lahan + 2)
                        ax.set_title("Denah Tata Letak (Block Layout)", fontweight='bold')
                        ax.set_xlabel("Sumbu X (meter)"); ax.set_ylabel("Sumbu Y (meter)")
                        ax.grid(True, linestyle=':', alpha=0.6)
                        st.pyplot(fig)
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    with col_text:
                        st.markdown("<div class='card' style='height: 100%;'>", unsafe_allow_html=True)
                        st.subheader("💡 Interpretasi & Rekomendasi")
                        
                        if total_momen < 50000:
                            st.success("**Analisis:** Tata letak sudah sangat efisien (optimal).")
                            st.write("Rekomendasi: Tata letak ini dapat langsung dipertimbangkan untuk diterapkan karena telah meminimalkan *material handling* secara signifikan.")
                        else:
                            st.warning("**Analisis:** Tata letak cukup efisien, namun beban jarak masih relatif tinggi.")
                            st.write("Rekomendasi: Pertimbangkan untuk merevisi nilai matriks FTC atau menyesuaikan batas area lahan pabrik.")
                        
                        st.divider()
                        st.markdown("📋 **Tabel Koordinat (X, Y)**")
                        st.dataframe(pd.DataFrame(koordinat_data), hide_index=True, use_container_width=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                else:
                    st.error("❌ Solusi Tidak Ditemukan (Infeasible).")
                    st.warning("Penyebab umum: Batas Lahan terlalu kecil untuk menampung seluruh ruangan, atau jarak GMP terlalu besar. Silakan tambah lebar/panjang lahan di atas.")
