from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from pulp import *

app = FastAPI(title="MILP Optimizer PT PSN")

# --- STRUKTUR DATA BARU ---
class Departemen(BaseModel):
    nama: str
    panjang: float
    lebar: float

class Relasi(BaseModel):
    dept1: str
    dept2: str
    aliran: float    # O1: Aliran Material
    waktu: float     # O2: Waktu MHT
    pekerja: float   # O3: Jumlah Pekerja
    closeness: float # O4: Closeness Rating

class OptimasiRequest(BaseModel):
    hx: float
    hy: float
    w1: float
    w2: float
    w3: float
    w4: float
    skenario: str
    list_dept: List[Departemen]
    list_relasi: List[Relasi]

# --- FUNGSI OPTIMASI MILP ---
@app.post("/solve")
async def solve_endpoint(req: OptimasiRequest):
    try:
        n = len(req.list_dept)
        if n == 0:
            raise HTTPException(status_code=400, detail="Data kosong")

        # 1. Setup Skenario Ketidakpastian (Stochastic)
        multiplier = {"Sibuk": 1.5, "Normal": 1.0, "Rendah": 0.5}.get(req.skenario, 1.0)

        # 2. Mapping Index Departemen
        dept_names = [d.nama for d in req.list_dept]
        P = [d.panjang for d in req.list_dept]
        L = [d.lebar for d in req.list_dept]

        # 3. Matriks Relasi Antar Departemen (Gabungan 4 Parameter)
        R_matrix = { (i, j): 0.0 for i in range(n) for j in range(n) }
        
        for rel in req.list_relasi:
            if rel.dept1 in dept_names and rel.dept2 in dept_names:
                i = dept_names.index(rel.dept1)
                j = dept_names.index(rel.dept2)
                
                # Formula Paper IDEC Eq 1-5: W1*O1 + W2*O2 + W3*O3 - W4*O4
                # Closeness dikurangi (-) karena nilai closeness tinggi = makin dekat = penalty turun
                skor = (req.w1 * rel.aliran) + (req.w2 * rel.waktu) + (req.w3 * rel.pekerja) - (req.w4 * rel.closeness)
                
                R_matrix[(i, j)] = skor * multiplier
                R_matrix[(j, i)] = skor * multiplier # Simetris

        # 4. Model Matematis MILP
        model = LpProblem("Tata_Letak_Stochastic", LpMinimize)
        
        cx = LpVariable.dicts("cx", range(n), 0, req.hx)
        cy = LpVariable.dicts("cy", range(n), 0, req.hy)
        dx = LpVariable.dicts("dx", (range(n), range(n)), 0)
        dy = LpVariable.dicts("dy", (range(n), range(n)), 0)
        z = LpVariable.dicts("z", (range(n), range(n), range(4)), cat='Binary')

        # Fungsi Tujuan (Global Optimum)
        model += lpSum([ R_matrix[(i, j)] * (dx[i][j] + dy[i][j]) for i in range(n) for j in range(i+1, n) ])

        # Batasan Non-Overlapping & Area
        M = max(req.hx, req.hy) * 2
        for i in range(n):
            model += cx[i] + (P[i]/2) <= req.hx
            model += cx[i] - (P[i]/2) >= 0
            model += cy[i] + (L[i]/2) <= req.hy
            model += cy[i] - (L[i]/2) >= 0
            for j in range(i + 1, n):
                model += dx[i][j] >= cx[i] - cx[j]
                model += dx[i][j] >= cx[j] - cx[i]
                model += dy[i][j] >= cy[i] - cy[j]
                model += dy[i][j] >= cy[j] - cy[i]
                model += cx[i] + (P[i]/2) <= cx[j] - (P[j]/2) + M * (1 - z[i][j][0])
                model += cx[j] + (P[j]/2) <= cx[i] - (P[i]/2) + M * (1 - z[i][j][1])
                model += cy[i] + (L[i]/2) <= cy[j] - (L[j]/2) + M * (1 - z[i][j][2])
                model += cy[j] + (L[j]/2) <= cy[i] - (L[i]/2) + M * (1 - z[i][j][3])
                model += lpSum([z[i][j][k] for k in range(4)]) >= 1

        # 5. Solving
        model.solve(PULP_CBC_CMD(msg=0))
        
        if LpStatus[model.status] == 'Optimal':
            return {
                "status": "Optimal",
                "objective_value": value(model.objective),
                "hasil": [ {"nama": dept_names[i], "x": value(cx[i]), "y": value(cy[i])} for i in range(n) ]
            }
        return {"status": "Infeasible", "message": "Lahan tidak mencukupi untuk tata letak ini."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root(): return {"message": "API Backend Aktif"}