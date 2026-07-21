# -*- coding: utf-8 -*-
"""
Step 3.1B Part B - D04 SDID Donor Feasibility (PILOT / feasibility only).
Builds a ~1 km grid over a SE-Bangladesh analysis extent, classifies
treated / spillover-excluded / donor zones by distance to nearest camp,
extracts Hansen GFC v1.12 baseline forest + annual loss proportion 2001-2016,
filters donor candidates, and compares pre-2017 trends.

NOTE: This is a FEASIBILITY test only. Treatment definition is NOT locked.
Covariates (elevation/slope/road/PA/built-up) are DEFERRED (need SRTM/OSM/WDPA).
"""
import os, math, csv, time
os.environ.setdefault("GDAL_HTTP_UNSAFESSL", "YES")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "120")
os.environ.setdefault("VSI_CACHE", "TRUE")
os.environ.setdefault("CPL_VSIL_CURL_CACHE_SIZE", "200000000")
import numpy as np, rasterio
from rasterio.windows import from_bounds

BASE = "https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12"
TILE = "30N_090E"
OUTDIR = r"07_Python_Analysis/Step3.1B_D04_Donor_Feasibility"

# ---- Analysis extent (SE Bangladesh coastal/forest; W of intl border) ----
MINLON, MAXLON = 91.90, 92.30
MINLAT, MAXLAT = 20.90, 22.20

# ---- Camp reference points (approx centroids of Rohingya camp clusters) ----
CAMPS = [
    ("Kutupalong-Balukhali", 21.200, 92.160),
    ("Shamlapur",            21.100, 92.140),
    ("Leda-Unchiprang",      21.030, 92.180),
    ("Nayapara-Teknaf",      20.870, 92.280),
]

# ---- Zone thresholds (km) ----
TREATED_KM  = 5.0     # 0-5 km  = provisional treated
SPILL_KM    = 20.0    # 5-20 km = spillover, excluded
# > 20 km = donor candidate

FOREST_TC = 25        # treecover2000 >= 25% counts as baseline forest
BLOCK = 36            # 36 Hansen px (~1.0 km at this latitude)

def km_dist(lat, lon, lat0, lon0):
    dy = (lat - lat0) * 110.57
    dx = (lon - lon0) * 111.32 * math.cos(math.radians((lat + lat0) / 2.0))
    return math.hypot(dx, dy)

def nearest_camp_km(lat, lon):
    return min(km_dist(lat, lon, c[1], c[2]) for c in CAMPS)

print("Reading Hansen layers over extent ...", flush=True)
t0 = time.time()
layers = {}
for name in ["lossyear", "treecover2000", "datamask"]:
    url = f"/vsicurl/{BASE}/Hansen_GFC-2024-v1.12_{name}_{TILE}.tif"
    with rasterio.open(url) as src:
        win = from_bounds(MINLON, MINLAT, MAXLON, MAXLAT, src.transform)
        win = win.round_offsets().round_lengths()
        arr = src.read(1, window=win)
        transform = src.window_transform(win)
    layers[name] = arr
    print(f"  {name}: {arr.shape} read ({time.time()-t0:.1f}s)", flush=True)

loss = layers["lossyear"]; tc = layers["treecover2000"]; dm = layers["datamask"]
H, W = loss.shape
# top-left origin from transform
originx, px = transform.c, transform.a      # px > 0
originy, py = transform.f, transform.e      # py < 0

nrow = H // BLOCK
ncol = W // BLOCK
print(f"Grid: {nrow} rows x {ncol} cols = {nrow*ncol} cells (block {BLOCK}px)", flush=True)

rows = []
YEARS = list(range(2001, 2017))  # 2001-2016 pre-period
for i in range(nrow):
    r0 = i * BLOCK
    for j in range(ncol):
        c0 = j * BLOCK
        b_loss = loss[r0:r0+BLOCK, c0:c0+BLOCK]
        b_tc   = tc[r0:r0+BLOCK, c0:c0+BLOCK]
        b_dm   = dm[r0:r0+BLOCK, c0:c0+BLOCK]
        land = (b_dm == 1)
        n_land = int(land.sum())
        n_tot = b_dm.size
        # centroid lon/lat
        clon = originx + (c0 + BLOCK/2) * px
        clat = originy + (r0 + BLOCK/2) * py
        forest0 = land & (b_tc >= FOREST_TC)
        n_forest = int(forest0.sum())
        tc_mean = float(b_tc[land].mean()) if n_land else 0.0
        dist = nearest_camp_km(clat, clon)
        # annual loss proportion relative to baseline forest px
        ann = {}
        for y in YEARS:
            code = y - 2000
            lost = int((forest0 & (b_loss == code)).sum())
            ann[y] = (lost / n_forest) if n_forest else 0.0
        cum_pre = sum(ann.values())
        # also total loss all years (for disturbance flag)
        n_loss_any = int((forest0 & (b_loss > 0)).sum())
        row = {
            "Grid_ID": f"G{i:03d}_{j:03d}",
            "row": i, "col": j,
            "lat": round(clat, 5), "lon": round(clon, 5),
            "Distance_to_Camp_km": round(dist, 2),
            "Land_Frac": round(n_land / n_tot, 3),
            "Forest_Frac": round(n_forest / n_tot, 3),
            "Tree_Cover_2000_mean": round(tc_mean, 1),
            "N_forest_px": n_forest,
            "Cumulative_Pre_Loss_2001_2016": round(cum_pre, 4),
            "Loss_any_frac_of_forest": round(n_loss_any / n_forest, 4) if n_forest else 0.0,
        }
        for y in YEARS:
            row[f"loss_{y}"] = round(ann[y], 5)
        rows.append(row)

print(f"Built {len(rows)} cells ({time.time()-t0:.1f}s)", flush=True)

# ---------- classify zones ----------
FOREST_MIN = 0.10   # >=10% of cell is baseline forest to be usable
for r in rows:
    d = r["Distance_to_Camp_km"]
    if d <= TREATED_KM:
        r["Treatment_Status"] = "treated"
    elif d <= SPILL_KM:
        r["Treatment_Status"] = "spillover_excluded"
    else:
        r["Treatment_Status"] = "donor_candidate"

treated = [r for r in rows if r["Treatment_Status"] == "treated"]
# treated cells must actually have baseline forest to inform pre-trend
treated_forest = [r for r in treated if r["Forest_Frac"] >= FOREST_MIN]
spill = [r for r in rows if r["Treatment_Status"] == "spillover_excluded"]
donor_cand = [r for r in rows if r["Treatment_Status"] == "donor_candidate"]

# ---------- treated pre-2017 mean trend ----------
def mean_trend(cells):
    out = {}
    for y in YEARS:
        vals = [c[f"loss_{y}"] for c in cells]
        out[y] = float(np.mean(vals)) if vals else 0.0
    return out

tr_tc = np.array([c["Tree_Cover_2000_mean"] for c in treated_forest]) if treated_forest else np.array([0])
tr_tc_mean, tr_tc_sd = float(tr_tc.mean()), float(tr_tc.std())
treated_trend = mean_trend(treated_forest)
tr_cum = np.array([c["Cumulative_Pre_Loss_2001_2016"] for c in treated_forest]) if treated_forest else np.array([0])
tr_cum_mean, tr_cum_sd = float(tr_cum.mean()), float(tr_cum.std())

# ---------- donor filtering ----------
def rmse_trend(cell, ref):
    return math.sqrt(np.mean([(cell[f"loss_{y}"] - ref[y])**2 for y in YEARS]))

# similarity thresholds (feasibility, generous)
TC_LOW  = max(0.0, tr_tc_mean - 2*tr_tc_sd)
TC_HIGH = tr_tc_mean + 2*tr_tc_sd
CUM_HIGH = tr_cum_mean + 3*tr_cum_sd + 0.05   # big-disturbance guard
TREND_RMSE_MAX = 0.02

eligible = []
reason_counts = {"forest_absent":0,"tc_mismatch":0,"big_disturbance":0,"trend_mismatch":0,"data_missing":0}
for r in donor_cand:
    if r["Land_Frac"] < 0.5:
        r["Donor_Eligible"] = 0; r["Reject_Reason"] = "data_missing/water"; reason_counts["data_missing"]+=1; continue
    if r["Forest_Frac"] < FOREST_MIN:
        r["Donor_Eligible"] = 0; r["Reject_Reason"] = "forest_absent"; reason_counts["forest_absent"]+=1; continue
    if not (TC_LOW <= r["Tree_Cover_2000_mean"] <= TC_HIGH):
        r["Donor_Eligible"] = 0; r["Reject_Reason"] = "tc_mismatch"; reason_counts["tc_mismatch"]+=1; continue
    if r["Cumulative_Pre_Loss_2001_2016"] > CUM_HIGH:
        r["Donor_Eligible"] = 0; r["Reject_Reason"] = "big_disturbance"; reason_counts["big_disturbance"]+=1; continue
    rm = rmse_trend(r, treated_trend)
    r["PreTrend_RMSE"] = round(rm, 5)
    if rm > TREND_RMSE_MAX:
        r["Donor_Eligible"] = 0; r["Reject_Reason"] = "trend_mismatch"; reason_counts["trend_mismatch"]+=1; continue
    r["Donor_Eligible"] = 1; r["Reject_Reason"] = ""
    eligible.append(r)

donor_trend = mean_trend(eligible)

# per-year mismatch (treated vs eligible donor mean)
mismatch = {y: round(treated_trend[y] - donor_trend[y], 5) for y in YEARS}
worst = sorted(mismatch.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]

# ---------- write CSV ----------
csv_path = os.path.join(OUTDIR, "d04_grid_1km_feasibility.csv")
fields = ["Grid_ID","row","col","lat","lon","Distance_to_Camp_km","Treatment_Status",
          "Land_Frac","Forest_Frac","Tree_Cover_2000_mean","N_forest_px",
          "Cumulative_Pre_Loss_2001_2016","Loss_any_frac_of_forest",
          "Donor_Eligible","Reject_Reason","PreTrend_RMSE"] + [f"loss_{y}" for y in YEARS]
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)

# ---------- summary ----------
print("\n" + "="*64)
print("STEP 3.1B - D04 SDID DONOR FEASIBILITY (PILOT)")
print("="*64)
print(f"Analysis extent: lon {MINLON}-{MAXLON}, lat {MINLAT}-{MAXLAT}")
print(f"Camp reference points: {[c[0] for c in CAMPS]}")
print(
    f"Grid size: provisional 36 × 36 Hansen pixels "
    f"(~1.08 km north–south); total cells = {len(rows)}"
)
print("Grid/distance caveat: final grid and buffers will use projected CRS (EPSG:32646); no Bangladesh admin mask applied.")
print(f"Forest def: treecover2000 >= {FOREST_TC}%; usable forest_frac >= {FOREST_MIN}")
print("-"*64)
print(f"Treated cells (0-5 km): {len(treated)}  (with baseline forest: {len(treated_forest)})")
print(f"Spillover excluded (5-20 km): {len(spill)}")
print(f"Initial donor candidates (>20 km): {len(donor_cand)}")
print(f"Eligible donors after filters: {len(eligible)}")
print("  reject reasons:", reason_counts)
print("-"*64)
print(f"Treated baseline tree cover: mean {tr_tc_mean:.1f}% (sd {tr_tc_sd:.1f})")
print(f"Treated cumulative pre-loss 2001-2016: mean {tr_cum_mean:.3f} (sd {tr_cum_sd:.3f})")
print(f"Donor eligibility TC band: {TC_LOW:.1f}-{TC_HIGH:.1f}% ; trend RMSE max {TREND_RMSE_MAX}")
print("-"*64)
print("Pre-2017 annual forest-loss proportion (treated vs eligible-donor mean):")
print(f"  {'year':<6}{'treated':>10}{'donor':>10}{'diff':>10}")
for y in YEARS:
    print(f"  {y:<6}{treated_trend[y]:>10.4f}{donor_trend[y]:>10.4f}{mismatch[y]:>10.4f}")
print(f"Worst mismatch years: {[(y,d) for y,d in worst]}")
donor_cum = float(np.mean([c['Cumulative_Pre_Loss_2001_2016'] for c in eligible])) if eligible else 0.0
print(f"Cumulative pre-loss: treated {tr_cum_mean:.3f} vs eligible-donor {donor_cum:.3f}")
print("-"*64)

# This is a count-based feasibility screen, not evidence of acceptable SDID pre-fit.
if len(eligible) >= max(50, 3*len(treated_forest)):
    decision = "Preliminary donor pool numerically sufficient"
elif len(eligible) >= max(20, len(treated_forest)):
    decision = "Preliminary donor pool potentially sufficient; wider search may be needed"
else:
    decision = "Donor pool currently weak"
print("DECISION:", decision)
print(
    "FIT CAVEAT: Whether SDID can achieve acceptable weighted pre-treatment fit remains to be demonstrated "
    "through unit/time weights, support diagnostics, placebo tests and sensitivity analyses."
)
print("CSV saved:", csv_path)
