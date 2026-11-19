import sqlite3, os, time
from pathlib import Path

APP = Path(os.environ["APPDATA"]) / "sh.voicebox.app"
p = APP / "voicebox.db"
con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tabs = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for (t,) in tabs:
    c = con.execute(f"SELECT count(*) FROM '{t}'").fetchone()[0]
    print(f"{t}: {c}")
print("---")
for cand in ("profiles", "voice_profiles", "voice_profile"):
    try:
        rows = con.execute(f"SELECT id, name FROM {cand}").fetchall()
        print(f"[{cand}] ->", rows)
    except Exception as e:
        pass
for t in ("generations", "generation_versions"):
    try:
        rows = con.execute(f"SELECT count(*), status FROM {t} GROUP BY status").fetchall()
        print(f"[{t} by status] ->", rows)
    except Exception:
        pass
con.close()
