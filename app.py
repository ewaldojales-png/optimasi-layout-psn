import streamlit as st
import pandas as pd
import pulp
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# ==========================================
# 1. KONFIGURASI HALAMAN & STYLE
# ==========================================
st.set_page_config(page_title="MILP Facility Layout - PSN", layout="wide")

st.markdown("""
<style>
    .reportview-container .main .block-container{ padding-top: 2rem; }
    h1, h2, h3 { color: #2E4053; }
    .stButton>button { background-color: #2E86C1; color: white; border-radius: 5px; width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🏭 Optimasi Tata Letak Fasilitas PSN")
st.markdown("---")

# ==========================================
# 2. INPUT PARAMETER (SIDEBAR)
# ==========================================
with st.sidebar:
    st.header("⚙️ Parameter Input")
    
    skenario = st.selectbox("Skenario Produksi", ["Normal", "Sibuk", "Sangat Sibuk"])
    
    st.subheader("📏 Batas Area Lahan")
    lebar_lahan = st.number_input("Lebar Lahan (X) - meter", value=30.0)
    panjang_lahan = st.number_input("Panjang Lahan (Y) - meter", value=25.0)
    
    st.subheader("⚖️ Konfigurasi Bobot (w)")
    st.caption("Total bobot harus = 1.0")
    w1 = st.slider("Bobot Aliran Material (w1)", 0.0, 1.0, 0.4)
    w2 = st.slider("Bobot Waktu MHT (w2)", 0.0, 1.0, 0.3)
    w3 = st.slider("Bobot Jumlah Pekerja (w3)", 0.0, 1.0, 0.3)

# ==========================================
# 3. INPUT DATA DEPARTEMEN & RELASI
# ==========================================
st.header("1. Data Departemen & Parameter Interaksi")

# Data Default (Contoh untuk PSN)
if "data_tabel" not in st.session_state:
    st.session_state["data_tabel"] = pd.DataFrame([
        {"dept1": "Gudang", "dept2": "Produksi", "aliran": 15.0, "waktu": 3.0, "pekerja": 4},
        {"dept1": "Gudang", "dept2": "Finishing", "aliran": 10.0, "waktu": 4.0, "pekerja": 2},
        {"dept1": "Produksi", "dept2": "Finishing", "aliran": 25.0, "waktu": 2.0, "pekerja": 8},
    ])

# Tabel Input yang Bisa Diedit
data_input = st.data_editor(
    st.session_state["data_tabel"],
    num_rows="dynamic",
    use_container_width=True,
    key="editor_relasi"
)

# ==========================================
# 4. LOGIKA OPTIMASI (GABUNGAN main.py)
# ==========================================
st.header("2. Jalankan Optimasi & Hasil")

if st.button("🚀 Jalankan Optimasi Global", key="tombol_optimasi"):
    
    # --- A. PRE-PROCESSING DATA ---
    df = pd.DataFrame(data_input)
    # Hapus baris kosong
    df = df.dropna(subset=['dept1', 'dept2'])
    
    # Ambil daftar unik departemen
    departemen = sorted(list(set(df['dept1']).union(set(df['dept2']))))
    N = len(departemen)
    
    if N < 2:
        st.error("❌ Masukkan minimal 2 departemen yang saling berelasi.")
        st.stop()
        
    # --- B. DEFINISI MODEL PuLP ---
    model = pulp.LpProblem("Optimasi_Layout_PSN", pulp.LpMinimize)
    
    # --- C. VARIABEL KEPUTUSAN ---
    # Asumsi: Setiap departemen dianggap memiliki dimensi default (misal 5x5m)
    # untuk ilustrasi. Dalam skripsi asli Anda, variabel lebar/panjang dept
    # harus diambil dari data input.
    W_dept = {d: 5.0 for d in departemen}
    H_dept = {d: 5.0 for d in departemen}
    
    # Koordinat titik tengah (x, y)
    x = pulp.LpVariable.dicts("x", departemen, 0, lebar_lahan, pulp.LpContinuous)
    y = pulp.LpVariable.dicts("y", departemen, 0, panjang_lahan, pulp.LpContinuous)
    
    # Jarak absolut (x_ij, y_ij)
    dx = pulp.LpVariable.dicts("dx", (departemen, departemen), lowbound=0, cat=pulp.LpContinous)
    dy = pulp.LpVariable.dicts("dy", (departemen, departemen), lowbound=0, cat=pulp.LpContinous)
    
    # Variabel biner untuk overlap (misal: z_ij)
    # ... (Masukkkan logika constraint overlap asli dari main.py Anda di sini) ...
    # Placeholder logika overlap biner
    z = pulp.LpVariable.dicts("z", (departemen, departemen), 0, 1, pulp.LpBinary)

    # --- D. FUNGSI TUJUAN ---
    cost = []
    for _, row in df.iterrows():
        d1, d2 = row['dept1'], row['dept2']
        flow = row['aliran']
        
        # Hitung skor interaksi terbobot
        skor_interaksi = (w1 * flow) + (w2 * row['waktu']) + (w3 * row['pekerja'])
        
        # Minimasi jarak Manhattan * Skor
        cost.append(skor_interaksi * (dx[d1][d2] + dy[d1][d2]))
        
    model += pulp.lpSum(cost)
    
    # --- E. CONSTRAINTS (KENDALA) ---
    for i in departemen:
        # Kendala Batas Area Lahan
        model += x[i] + W_dept[i]/2 <= lebar_lahan
        model += x[i] - W_dept[i]/2 >= 0
        model += y[i] + H_dept[i]/2 <= panjang_lahan
        model += y[i] - H_dept[i]/2 >= 0
        
        for j in departemen:
            if i < j:
                # Kendala Jarak Absolut (Linearisasi Manhattan)
                model += dx[i][j] >= x[i] - x[j]
                model += dx[i][j] >= x[j] - x[i]
                model += dy[i][j] >= y[i] - y[j]
                model += dy[i][j] >= y[j] - y[i]
                
                # Kendala Non-Overlap (Biner)
                # ... (Masukkan logika biner asli Anda di sini) ...
                # Placeholder biner agar model bisa running
                model += x[i] + W_dept[i]/2 <= x[j] - W_dept[j]/2 + 1000 * (1 - z[i][j])

    # --- F. RUN SOLVER ---
    model.solve(pulp.PULP_CBC_CMD(msg=0))
    
    # --- G. HASIL & VISUALISASI ---
    status = pulp.LpStatus[model.status]
    
    if status == 'Optimal':
        st.success(f"✅ Optimasi Berhasil! Status: {status}")
        
        # 1. Tampilkan Tabel Koordinat
        res_data = []
        for i in departemen:
            res_data.append({
                "Departemen": i,
                "Titik Tengah X": round(pulp.value(x[i]), 2),
                "Titik Tengah Y": round(pulp.value(y[i]), 2),
                "Lebar": W_dept[i],
                "Panjang": H_dept[i]
            })
        
        st.subheader("📋 Tabel Koordinat Hasil Optimasi")
        st.table(res_data)
        
        # 2. Generate Denah Block Layout (Matplotlib)
        st.subheader("🖼️ Denah Block Layout Tata Letak")
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Gambar Batas Lahan
        batas_lahan = patches.Rectangle((0, 0), lebar_lahan, panjang_lahan, 
                                          linewidth=2, edgecolor='black', facecolor='none', linestyle='--')
        ax.add_patch(batas_lahan)
        
        # Gambar Setiap Departemen
        for r in res_data:
            # Hitung pojok kiri bawah (anchor point patches.Rectangle)
            bottom_left_x = r["Titik Tengah X"] - r["Lebar"]/2
            bottom_left_y = r["Titik Tengah Y"] - r["Panjang"]/2
            
            rect = patches.Rectangle(
                (bottom_left_x, bottom_left_y), 
                r["Lebar"], r["Panjang"],
                linewidth=1, edgecolor='#2E4053', facecolor='#AED6F1', alpha=0.8
            )
            ax.add_patch(rect)
            
            # Tambah Label Nama Departemen
            ax.text(r["Titik Tengah X"], r["Titik Tengah Y"], r["Departemen"],
                    horizontalalignment='center', verticalalignment='center', fontsize=10, fontweight='bold')
            
        # Konfigurasi Plot
        ax.set_xlim(-1, lebar_lahan + 1)
        ax.set_ylim(-1, panjang_lahan + 1)
        ax.set_aspect('equal')
        ax.set_xlabel("Lebar Area (meter)")
        ax.set_ylabel("Panjang Area (meter)")
        ax.set_title(f"Block Layout PT. PSN - Skenario {skenario}", fontweight='bold')
        ax.grid(True, linestyle=':', alpha=0.5)
        
        # Tampilkan Gambar di Streamlit
        st.pyplot(fig)
        
    else:
        st.error(f"❌ Solusi tidak ditemukan. Status solver: {status}")
        st.warning("Coba besarkan batas area lahan atau periksa kembali relasi antar departemen.")
