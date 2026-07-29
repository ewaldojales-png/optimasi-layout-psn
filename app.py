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
# 2. INISIALISASI DATA DEFAULT (KOSONG / MANUAL)
# ==========================================
if "df_dimensi" not in st.session_state:
    st.session_state.df_dimensi = pd.DataFrame([
        {"Fasilitas": "", "P (m)": 0.0, "L (m)": 0.0},
        {"Fasilitas": "", "P (m)": 0.0, "L (m)": 0.0}
    ])

# ==========================================
# 3. NAVIGASI TABS
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 1. Master Dimensi & Parameter", "🔀 2. Matriks Relasi", "🚀 3. Eksekusi Optimasi"])

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
    st.info("💡 **FITUR TAMBAH/HAPUS:** Arahkan kursor ke baris paling bawah tabel untuk memunculkan tombol `+` (Tambah Baris). Ketik manual data Anda.")
    
    edited_df = st.data_editor(
        st.session_state.df_dimensi, 
        column_config={
            "Fasilitas": st.column_config.TextColumn("Fasilitas", required=True),
            "P (m)": st.column_config.NumberColumn("P (m)", min_value=0.0, format="%.2f"),
            "L (m)": st.column_config.NumberColumn("L (m)", min_value=0.0, format="%.2f")
        },
        num_rows="dynamic", use_container_width=True, hide_index=True, key="editor_dimensi"
    )
    
    dept_names = []
    for n in edited_df["Fasilitas"].tolist():
        name = str(n).strip()
        if name != "" and name not in dept_names:
            dept_names.append(name)
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("C. Parameter Aliran Stokastik (Expected Flow)")
    
    c1, c2, c3 = st.columns(3)
    prob_sibuk = c1.number_input("Probabilitas Sibuk", value=0.05, step=0.01)
    sibuk = c1.number_input("Jumlah Prod. Sibuk", value=5928, step=100)
    
    prob_normal = c2.number_input("Probabilitas Normal", value=0.75, step=0.01)
    normal = c2.number_input("Jumlah Prod. Normal", value=4560, step=100)
    
    prob_sepi = c3.number_input("Probabilitas Sepi", value=0.20, step=0.01)
    sepi = c3.number_input("Jumlah Prod. Sepi", value=3192, step=100)
    
    c4, c5 = st.columns(2)
    kapasitas = c4.number_input("Kapasitas Alat Angkut (Troli/Forklift)", value=150)
    hari = c5.number_input("Hari Kerja/Bulan", value=26)
    
    if kapasitas > 0:
        expected_flow = (prob_sibuk * (sibuk/kapasitas*hari)) + (prob_normal * (normal/kapasitas*hari)) + (prob_sepi * (sepi/kapasitas*hari))
        st.success(f"**Expected Flow (Harapan Aliran): {expected_flow:.1f} ritasi/bulan.**")
    else:
        expected_flow = 0
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("### Sinkronisasi Matriks Otomatis")
    
    if "base_arc" not in st.session_state:
        st.session_state.base_arc = pd.DataFrame('U', index=dept_names, columns=dept_names)
    if "base_ftc" not in st.session_state:
        st.session_state.base_ftc = pd.DataFrame(0.0, index=dept_names, columns=dept_names)

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
        st.markdown("""<div style="font-size:13px; color:#6B7280;">Masukkan kode A, E, I, O, U, atau X. Kode <b>X</b> akan memicu batas jarak mutlak keamanan.</div>""", unsafe_allow_html=True)
        
        if len(dept_names) > 0:
            edited_arc = st.data_editor(st.session_state.base_arc, use_container_width=True, key="editor_arc")
            st.session_state.last_arc = edited_arc
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_kanan:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Matriks Jarak Eksisting (m)")
        st.markdown("""<div style="font-size:13px; color:#B45309; font-weight:bold; background:#FEF3C7; padding:8px; border-radius:5px;">
        Masukkan JARAK LAMA antar fasilitas (contoh: 13, 22). Angka ini akan digunakan untuk menghitung Momen Eksisting.
        </div>""", unsafe_allow_html=True)
        
        if len(dept_names) > 0:
            edited_ftc = st.data_editor(st.session_state.base_ftc, use_container_width=True, key="editor_ftc")
            st.session_state.last_ftc = edited_ftc
        st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("⚙️ Parameter Solver & Batas Area")
    cc1, cc2, cc3 = st.columns(3)
    lebar_lahan = cc1.number_input("Lebar Lahan (Sumbu X) - m", value=100.0)
    panjang_lahan = cc2.number_input("Panjang Lahan (Sumbu Y) - m", value=100.0)
    batas_aman = cc3.number_input("Jarak Keamanan Mutlak ('X') - m", value=15.0)
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("🚀 JALANKAN OPTIMASI MILP", type="primary", use_container_width=True):
        if len(dept_names) < 2:
            st.error("Masukkan minimal 2 fasilitas di Tab 1.")
        else:
            with st.spinner("Solver sedang memproses koordinat global optimum..."):
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
                
                objective_terms = []
                momen_eksisting_kalkulasi = 0.0
                
                for i in dept_names:
                    for j in dept_names:
                        if i != j:
                            try:
                                # Mengambil JARAK LAMA yang diinputkan user di matriks kanan
                                jarak_lama = float(edited_ftc.loc[i, j])
                            except:
                                jarak_lama = 0.0
                                
                            if jarak_lama > 0:
                                # 1. MENGHITUNG MOMEN EKSISTING (Otomatis dari input user)
                                # Rumus: Jarak Lama x Flow
                                momen_eksisting_kalkulasi += (jarak_lama * expected_flow)
                                
                                # 2. MENGHITUNG FUNGSI TUJUAN MILP (Jarak Baru x Flow)
                                # Jarak lama TIDAK DIKALIKAN lagi di sini untuk menghindari ledakan angka
                                objective_terms.append(expected_flow * (dx[i][j] + dy[i][j]))
                                
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
                
                if status == 'Optimal' or status == 'Feasible':
                    st.success(f"🎉 Solusi Optimum Ditemukan! Seluruh kendala jarak {batas_aman}m terpenuhi.")
                    
                    val_obj = pulp.value(model.objective)
                    total_momen_usulan = float(val_obj) if val_obj is not None else 0.0
                    
                    # Menghitung efisiensi secara real-time berdasarkan input user
                    efisiensi = ((momen_eksisting_kalkulasi - total_momen_usulan) / momen_eksisting_kalkulasi) * 100 if momen_eksisting_kalkulasi > 0 and total_momen_usulan < momen_eksisting_kalkulasi else 0.0
                    
                    m1, m2, m3 = st.columns(3)
                    m1.markdown(f"<div class='metric-box'><div class='metric-title'>Momen Eksisting Lama</div><div class='metric-value' style='color:#DC2626;'>{momen_eksisting_kalkulasi:,.2f}</div></div>", unsafe_allow_html=True)
                    m2.markdown(f"<div class='metric-box'><div class='metric-title'>Momen Usulan (Z)</div><div class='metric-value' style='color:#059669;'>{total_momen_usulan:,.2f}</div></div>", unsafe_allow_html=True)
                    m3.markdown(f"<div class='metric-box'><div class='metric-title'>Efisiensi Tata Letak</div><div class='metric-value' style='color:#2563EB;'>{efisiensi:.2f}%</div></div>", unsafe_allow_html=True)
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
                        
                else:
                    st.error(f"❌ Solusi tidak ditemukan (Infeasible). Perbesar ukuran lahan.")
