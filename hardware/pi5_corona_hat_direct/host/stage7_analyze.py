import csv, sys, math, statistics
rows = list(csv.DictReader(open(sys.argv[1])))
b = [r for r in rows if r["phase"] == "burst"]; d = [r for r in rows if r["phase"] == "decay"]
t0 = float(b[0]["t_s"])
for frac in (0.02, 0.05, 0.1, 0.2, 0.5, 0.99):
    r = b[min(int(len(b) * frac), len(b) - 1)]
    print(f"burst +{float(r['t_s']) - t0:.3f}s AIN0={r['ain0_V']} bridge={r['bridge_V']}")
ts = float(d[0]["t_s"]); pts = [(float(r["t_s"]) - ts, float(r["ain0_V"])) for r in d]
for tt in (0, 0.5, 1, 2, 3, 5, 8, 12, 15):
    p = min(pts, key=lambda x: abs(x[0] - tt)); print(f"decay +{p[0]:.2f}s AIN0={p[1]:.4f}")
a = [p for p in pts if p[1] > 0.0015]
if len(a) > 5:
    xs = [p[0] for p in a]; ys = [math.log(p[1]) for p in a]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sl = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    print(f"fit tau ~ {-1/sl:.2f} s over {xs[0]:.1f}-{xs[-1]:.1f}s")
