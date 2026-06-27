import streamlit as st
import pandas as pd
import pulp
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="DSS Layout Pabrik PSN", page_icon="🏭", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; }
    .card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #E5E7EB; }
    .metric-box { text-align: center; padding: 15px; background: #EEF2FF; border-radius: 8px; border-left: 5px solid #4F46E5; }
    .metric-title { font-size: 14px; color: #6B7280; font-weight: bold; }
    .metric-value { font-size: 24px; color: #111827; font-weight: 900; }
</style>
""", unsafe_allow_html=True)

st.title("🏭 Sistem Pendukung Keputusan: Optimasi Tata Letak PT. PSN")
st.markdown("Implementasi *Mixed Integer Linear Programming* (MILP) - Anti Glitch & Stabil")
st.divider()

# ==========================================
# 2. INISIALISASI DATA DEFAULT
# ==========================================
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

# ==========================================
# 3. NAVIGASI TABS
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 1. Master Dimensi & Parameter", "🔀 2. Matriks Relasi (Otomatis)", "🚀 3. Eksekusi Optimasi"])

with tab1:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("A. Master Fasilitas & Dimensi")
    st.info("💡 **FITUR TAMBAH/HAPUS:** Arahkan kursor ke baris paling bawah tabel untuk memunculkan tombol `+` (Tambah Baris). Matriks di Tab 2 akan **otomatis menyesuaikan**.")
    
    # Editor Dinamis Dimensi
    edited_df = st.data_editor(
        st.session_state.df_dimensi, 
        num_rows="dynamic", 
        use_container_width=True, 
        hide_index=True
    )
    
    # Mencegah nama fasilitas ganda/kosong (Mencegah KeyError)
    dept_names = []
    for n in edited_df["Fasilitas"].tolist():
        name = str(n).strip()
        if name != "" and name not in dept_names:
            dept_names.append(name)
            
    st.session_state.df_dimensi = edited_df
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("B. Parameter Aliran Stokastik (Expected Flow)")
    c1, c2, c3 = st.columns(3)
    sibuk = c1.number_input("Prod. Sibuk (Prob. 0.05)", value=5928, step=100)
    normal = c2.number_input("Prod. Normal (Prob. 0.75)", value=4560, step=100)
    sepi = c3.number_input("Prod. Sepi (Prob. 0.20)", value=3192, step=100)
    
    c4, c5 = st.columns(2)
    kapasitas = c4.number_input("Kapasitas Troli", value=150)
    hari = c5.number_input("Hari Kerja/Bulan", value=26)
    
    expected_flow = (0.05 * (sibuk/kapasitas*hari)) + (0.75 * (normal/kapasitas*hari)) + (0.20 * (sepi/kapasitas*hari))
    st.success(f"**Expected Flow (Harapan Aliran): {expected_flow:.1f} ritasi/bulan.**")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("### Sinkronisasi Matriks Otomatis")
    st.caption("Ketik angka dengan santai, tabel ini sudah kebal terhadap glitch *refresh*.")
    
    if "arc_matrix" not in st.session_state:
        st.session_state.arc_matrix = pd.DataFrame('U', index=dept_names, columns=dept_names)
        if "Gudang Bahan Baku" in dept_names and "Packing" in dept_names:
            st.session_state.arc_matrix.loc["Gudang Bahan Baku", "Packing"] = 'X'
        if "Gudang Bahan Baku" in dept_names and "Gudang Finish Good" in dept_names:
            st.session_state.arc_matrix.loc["Gudang Bahan Baku", "Gudang Finish Good"] = 'X'
            
    if "ftc_matrix" not in st.session_state:
        st.session_state.ftc_matrix = pd.DataFrame(0.0, index=dept_names, columns=dept_names)

    # Reindex hanya ketika struktur fasilitas berubah
    if "prev_dept_names" not in st.session_state or st.session_state.prev_dept_names != dept_names:
        st.session_state.arc_matrix = st.session_state.arc_matrix.reindex(index=dept_names, columns=dept_names, fill_value='U')
        st.session_state.ftc_matrix = st.session_state.ftc_matrix.reindex(index=dept_names, columns=dept_names, fill_value=0.0)
        st.session_state.prev_dept_names = dept_names
    
    col_kiri, col_kanan = st.columns(2)
    with col_kiri:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Matriks ARC")
        st.caption("A, E, I, O, U, atau X")
        edited_arc = st.data_editor(st.session_state.arc_matrix, use_container_width=True, key="editor_arc")
        st.session_state.arc_matrix = edited_arc
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_kanan:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Matriks FTC")
        st.caption("Persentase aliran material")
        edited_ftc = st.data_editor(st.session_state.ftc_matrix, use_container_width=True, key="editor_ftc")
        st.session_state.ftc_matrix = edited_ftc
        st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("⚙️ Parameter Solver & Batas Area")
    cc1, cc2, cc3 = st.columns(3)
    lebar_lahan = cc1.number_input("Lebar Lahan (Sumbu X) - m", value=40.0)
    panjang_lahan = cc2.number_input("Panjang Lahan (Sumbu Y) - m", value=40.0)
    batas_gmp = cc3.number_input("Jarak Mutlak GMP - m", value=15.0)
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("🚀 JALANKAN OPTIMASI MILP", type="primary", use_container_width=True):
        if len(dept_names) < 2:
            st.error("Masukkan minimal 2 fasilitas pada tabel Dimensi.")
        else:
            with st.spinner("Solver sedang memproses algoritma optimasi kompleks..."):
                # ==========================================
                # MODEL OPTIMASI MATEMATIS
                # ==========================================
                model = pulp.LpProblem("Layout_PSN", pulp.LpMinimize)
                
                # Pemetaan Dimensi
                W = {}
                H = {}
                for _, row in edited_df.iterrows():
                    nm = str(row["Fasilitas"]).strip()
                    if nm in dept_names:
                        W[nm] = float(row["P (m)"])
                        H[nm] = float(row["L (m)"])
                
                x = pulp.LpVariable.dicts("x", dept_names, lowBound=0, upBound=lebar_lahan, cat=pulp.LpContinuous)
                y = pulp.LpVariable.dicts("y", dept_names, lowBound=0, upBound=panjang_lahan, cat=pulp.LpContinuous)
                dx = pulp.LpVariable.dicts("dx", (dept_names, dept_names), lowBound=0, cat=pulp.LpContinuous)
                dy = pulp.LpVariable.dicts("dy", (dept_names, dept_names), lowBound=0, cat=pulp.LpContinuous)
                z = pulp.LpVariable.dicts("z", (dept_names, dept_names, range(1, 5)), 0, 1, pulp.LpBinary)
                
                # Big-M Dinamis (Menyesuaikan Lahan agar solver tidak Infeasible)
                M = (lebar_lahan + panjang_lahan) * 10
                
                # PERBAIKAN FATAL: 'X' tidak boleh minus di objektif, X adalah Hard Constraint murni!
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
                            # Manhattan Distance
                            model += dx[i][j] >= x[i] - x[j]
                            model += dx[i][j] >= x[j] - x[i]
                            model += dy[i][j] >= y[i] - y[j]
                            model += dy[i][j] >= y[j] - y[i]
                            
                            model += dx[j][i] == dx[i][j]
                            model += dy[j][i] == dy[i][j]
                            
                            # Big-M Non Overlap
                            model += x[i] + W[i]/2 <= x[j] - W[j]/2 + M * (1 - z[i][j][1])
                            model += x[i] - W[i]/2 >= x[j] + W[j]/2 - M * (1 - z[i][j][2])
                            model += y[i] + H[i]/2 <= y[j] - H[j]/2 + M * (1 - z[i][j][3])
                            model += y[i] - H[i]/2 >= y[j] + H[j]/2 - M * (1 - z[i][j][4])
                            model += z[i][j][1] + z[i][j][2] + z[i][j][3] + z[i][j][4] >= 1
                            
                            # GMP Constraints Mutlak (Linearisasi Diamond Absolute)
                            kode1 = str(edited_arc.loc[i, j]).strip().upper()
                            kode2 = str(edited_arc.loc[j, i]).strip().upper()
                            if kode1 == 'X' or kode2 == 'X':
                                idx_i, idx_j = dept_names.index(i), dept_names.index(j)
                                g1 = pulp.LpVariable(f"gmp_{idx_i}_{idx_j}_1", 0, 1, pulp.LpBinary)
                                g2 = pulp.LpVariable(f"gmp_{idx_i}_{idx_j}_2", 0, 1, pulp.LpBinary)
                                g3 = pulp.LpVariable(f"gmp_{idx_i}_{idx_j}_3", 0, 1, pulp.LpBinary)
                                g4 = pulp.LpVariable(f"gmp_{idx_i}_{idx_j}_4", 0, 1, pulp.LpBinary)
                                
                                model += (x[i] - x[j]) + (y[i] - y[j]) >= batas_gmp - M * (1 - g1)
                                model += (x[i] - x[j]) - (y[i] - y[j]) >= batas_gmp - M * (1 - g2)
                                model += -(x[i] - x[j]) + (y[i] - y[j]) >= batas_gmp - M * (1 - g3)
                                model += -(x[i] - x[j]) - (y[i] - y[j]) >= batas_gmp - M * (1 - g4)
                                model += g1 + g2 + g3 + g4 >= 1

                model.solve(pulp.PULP_CBC_CMD(msg=0))
                status = pulp.LpStatus[model.status]
                
                # ==========================================
                # OUTPUT HASIL
                # ==========================================
                if status == 'Optimal':
                    st.success("🎉 Solusi Global Optimum Ditemukan! Seluruh kendala GMP terpenuhi tanpa overlapping.")
                    
                    val_obj = pulp.value(model.objective)
                    total_momen = float(val_obj) if val_obj is not None else 0.0
                    momen_eksisting = 65641.5
                    efisiensi = ((momen_eksisting - total_momen) / momen_eksisting) * 100 if total_momen < momen_eksisting else 0
                    
                    m1, m2, m3 = st.columns(3)
                    m1.markdown(f"<div class='metric-box'><div class='metric-title'>Status Solver</div><div class='metric-value' style='color:#059669;'>{status}</div></div>", unsafe_allow_html=True)
                    m2.markdown(f"<div class='metric-box'><div class='metric-title'>Total Momen (Z)</div><div class='metric-value'>{total_momen:,.2f}</div></div>", unsafe_allow_html=True)
                    m3.markdown(f"<div class='metric-box'><div class='metric-title'>Efisiensi</div><div class='metric-value' style='color:#2563EB;'>{efisiensi:.2f} %</div></div>", unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col_vis, col_text = st.columns([3, 2])
                    with col_vis:
                        st.markdown("<div class='card'>", unsafe_allow_html=True)
                        st.subheader("🖼️ Block Layout (Usulan)")
                        
                        fig, ax = plt.subplots(figsize=(10, 8))
                        ax.add_patch(patches.Rectangle((0, 0), lebar_lahan, panjang_lahan, linewidth=2, edgecolor='red', facecolor='none', linestyle='--'))
                        
                        colors = ['#DBEAFE', '#D1FAE5', '#FEF3C7', '#FCE7F3', '#E0E7FF', '#CFFAFE', '#FEF08A', '#N/A']
                        koordinat_data = []
                        
                        for idx, d in enumerate(dept_names):
                            cx, cy = pulp.value(x[d]), pulp.value(y[d])
                            w, h = W[d], H[d]
                            bx, by = cx - w/2, cy - h/2
                            
                            koordinat_data.append({"Departemen": d, "X": round(cx,2), "Y": round(cy,2)})
                            
                            color = colors[idx % len(colors)]
                            d_lower = d.lower()
                            if "gudang bahan baku" in d_lower or "giling" in d_lower: color = "#FCA5A5" 
                            if "packing" in d_lower or "finish good" in d_lower: color = "#6EE7B7" 
                            
                            rect = patches.Rectangle((bx, by), w, h, linewidth=1.5, edgecolor='#1F2937', facecolor=color, alpha=0.9)
                            ax.add_patch(rect)
                            ax.text(cx, cy, d, ha='center', va='center', fontsize=9, fontweight='bold', color='#111827', wrap=True)

                        ax.set_xlim(-2, lebar_lahan + 2)
                        ax.set_ylim(-2, panjang_lahan + 2)
                        ax.set_xlabel("Sumbu X (meter)"); ax.set_ylabel("Sumbu Y (meter)")
                        ax.grid(True, linestyle=':', alpha=0.6)
                        
                        ax.plot([], [], 's', color='#FCA5A5', label='Area Kotor (Sanitasi Rendah)')
                        ax.plot([], [], 's', color='#6EE7B7', label='Area Steril (Sanitasi Tinggi)')
                        ax.legend(loc='upper right', fontsize=8)
                        
                        st.pyplot(fig)
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    with col_text:
                        st.markdown("<div class='card' style='height: 100%;'>", unsafe_allow_html=True)
                        st.subheader("💡 Analisis Skripsi")
                        st.markdown(f"Model MILP berhasil meminimalkan total beban perpindahan menjadi **{total_momen:,.2f}** "
                                    f"dengan penghematan jarak **{efisiensi:.2f}%**. "
                                    f"Batasan mutlak GMP (**{batas_gmp} meter**) antar area Kotor dan Steril telah terpenuhi secara efektif "
                                    f"melalui linearisasi jarak *rectilinear* absolut.")
                        st.divider()
                        st.markdown("📋 **Tabel Koordinat Pusat (X, Y)**")
                        st.dataframe(pd.DataFrame(koordinat_data), hide_index=True, use_container_width=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.error("❌ Solusi Tidak Ditemukan. Pastikan total luas fasilitas tidak melebihi Lahan, atau kurangi jarak mutlak GMP jika lahan sempit.")
