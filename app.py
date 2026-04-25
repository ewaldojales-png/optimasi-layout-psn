import streamlit as st
import pandas as pd
import pulp
import itertools

st.set_page_config(page_title="MILP PSN", layout="wide")
st.title("Sistem Optimasi Tata Letak (Model Multi-Variabel)")

# --- 1. SIDEBAR PARAMETER ---
with st.sidebar:
    st.header("Skenario Produksi")
    skenario = st.selectbox("Tingkat Permintaan", ["Rendah", "Normal", "Sibuk"], index=1)
    
    st.header("Batas Area Lahan")
    hx = st.number_input("Lebar Lahan (X)", value=30.0)
    hy = st.number_input("Panjang Lahan (Y)", value=25.0)

    st.header("Konfigurasi Bobot (w)")
    st.caption("Sesuai kriteria Paper IDEC 2018")
    w1 = st.slider("Aliran Material (w1)", 0.0, 1.0, 0.30)
    w2 = st.slider("Waktu MHT (w2)", 0.0, 1.0, 0.15)
    w3 = st.slider("Jumlah Pekerja (w3)", 0.0, 1.0, 0.20)
    w4 = st.slider("Closeness Rating (w4)", 0.0, 1.0, 0.35)

# --- 2. TABEL INPUT DEPARTEMEN ---
st.subheader("1. Dimensi Departemen")
df_dept_awal = pd.DataFrame([
    {"nama": "Gudang", "panjang": 5.0, "lebar": 5.0},
    {"nama": "Produksi", "panjang": 8.0, "lebar": 6.0},
    {"nama": "Finishing", "panjang": 4.0, "lebar": 4.0}
])
edited_dept = st.data_editor(df_dept_awal, num_rows="dynamic", key="tabel_dept")

# --- 3. TABEL INPUT RELASI (OTOMATIS) ---
st.subheader("2. Matriks Relasi Antar Departemen")
st.info("Isi parameter interaksi. Tabel ini otomatis menyesuaikan dengan departemen di atas.")

# Membuat kombinasi unik antar departemen (Misal: Gudang-Produksi, Gudang-Finishing)
nama_dept = edited_dept["nama"].dropna().tolist()
kombinasi = list(itertools.combinations(nama_dept, 2))

df_relasi_awal = []
for dept1, dept2 in kombinasi:
    df_relasi_awal.append({
        "dept1": dept1, "dept2": dept2, 
        "aliran": 10.0, "waktu": 2.5, "pekerja": 2.0, "closeness": 5.0
    })

if len(df_relasi_awal) > 0:
    edited_relasi = st.data_editor(pd.DataFrame(df_relasi_awal), disabled=["dept1", "dept2"], hide_index=True)
else:
    st.warning("Tambahkan minimal 2 departemen di tabel pertama.")

# --- 4. EKSEKUSI API ---
if st.button("🚀 Jalankan Optimasi Global"):
    if edited_dept.isnull().values.any() or (len(df_relasi_awal) > 0 and edited_relasi.isnull().values.any()):
        st.error("Error: Pastikan semua sel di kedua tabel terisi angka!")
    else:
        payload = {
            "hx": hx, "hy": hy, "w1": w1, "w2": w2, "w3": w3, "w4": w4, "skenario": skenario,
            "list_dept": edited_dept.to_dict(orient="records"),
            "list_relasi": edited_relasi.to_dict(orient="records") if len(df_relasi_awal) > 0 else []
        }
        
        with st.spinner(f"Menghitung tata letak skenario {skenario}..."):
            try:
                if st.button("🚀 Jalankan Optimasi Global", key="hitung_ulang"):
                    # 1. Ambil data dari tabel input Streamlit
                    df_input = st.session_state["data_tabel"] 
    
                    # 2. Inisialisasi Model PuLP (Logika dari main.py pindah ke sini)
                    model = pulp.LpProblem("Optimasi_Layout_PSN", pulp.LpMinimize)
    
                    # ... (masukkan logika variabel keputusan x, y, dan kendala/constraints di sini) ...
    
                    # 3. Jalankan Solver
                    model.solve(pulp.PULP_CBC_CMD(msg=0))
    
                    # 4. Tampilkan Hasil Langsung di Layar
                    if pulp.LpStatus[model.status] == 'Optimal':
                        st.success("✅ Optimasi Berhasil!")
                        # Tampilkan koordinat baru atau penurunan jarak
                    else:
                        st.error("❌ Solusi tidak ditemukan, coba periksa batasan lahan.")
                
                
                if res_data.get("status") == "Optimal":
                    st.success("Solusi Optimal Ditemukan!")
                    st.metric("Global Objective Value (Z)", round(res_data["objective_value"], 4))
                    st.table(pd.DataFrame(res_data["hasil"]))
                else:
                    st.error(res_data.get("message", "Terjadi kesalahan pada mesin perhitungan."))
            except Exception as e:
                st.error(f"Gagal menghubungi server Backend! Pastikan uvicorn berjalan. Detail: {e}")
