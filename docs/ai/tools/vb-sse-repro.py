"""SSE progress reproduction for Voicebox sidecar.

Usage: python vb-sse-repro.py [profile_id]
Posts a ~900-char Japanese text via REST, streams /generate/{id}/status,
and prints a timestamped timeline of every event. Closes the stream view
after 8 minutes max, then cancels the generation to free the GPU.
"""
import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:17999"
TEXT = (
    "夕暮れの海岸に、波が静かに打ち寄せていた。空はオレンジと紫色に染まり、"
    "水平線のかなたに太陽がゆっくりと沈んでいく。砂浜には昼間の喧騒の名残はなく、"
    "ただ風の音と波の音だけが響いていた。少年は靴を脱ぎ、冷たい波打ち際まで歩いた。"
    "波が足元を洗うたびに、過去の記憶が思い出されるようだった。夏休みの終わり、"
    "この海岸で交わした会話、笑い声、そして約束。あれから幾年もの歳月が流れ、"
    "少年は大人になり、この町を離れていた。しかし今日、彼は久しぶりにこの場所に戻ってきた。"
    "懐かしさと、言い知れぬ不安を抱えながら。波打ち際に残した足跡は、次の波が来るたびに"
    "消えていく。消えていく足跡を眺めながら、少年は考えていた。忘れたつもりでいた記憶も、"
    "実は心のどこかでずっと生き続けていたのではないか、と。空には星が出始め、"
    "最初のひとつが瞬いていた。少年は深呼吸をすると、胸の奥にため込んでいた言葉を、"
    "静かな海に向かってゆっくりと呟いた。返事はない。それでも構わなかった。"
    "伝える相手は、もうこの世にはいないのだから。ただ、風が少しだけ強くなった気がした。"
    "海は答えない。海はいつも答えをくれない。それでも少年は、もう一度だけ海を見つめた。"
    "水平線は今日も赤く、明日には必ずまた昇ることを、誰もかれもが知っている。"
    "しかし消えた人が戻ってくることを知っている者はいない。少年は踵を返し、砂浜を離れた。"
    "振り返らないことにしていた。歩幅は少しだけ軽くなっていた。町への坂道を登りきると、"
    "背後の海から、一瞬だけ波の音が消えたような気がした。立ち止まり、振り返る。海はそこにあり、"
    "相変わらず穏やかに、何も変わらない顔で、水平線で夜を吞み込んでいた。"
    "少年はポケットから小さな貝殻を取り出した。あの夏の日に、二人で拾った貝殻。"
    "耳に当てると、遠い日の笑い声が聞こえる気がした。もう聞こえないはずの声なのに。"
    "貝殻を大切にもう一度ポケットに戻し、少年は歩き出した。背後では夜が降り、星が海を銀に染めている。"
)
assert len(TEXT) > 800, len(TEXT)

t0 = time.time()
def ts():
    return f"[{time.time() - t0:7.1f}s]"

def log(msg):
    print(f"{ts()} {msg}", flush=True)

with httpx.Client(timeout=30) as client:
    r = client.get(f"{BASE}/health")
    log(f"health: {r.status_code}")

    profiles = client.get(f"{BASE}/profiles").json()
    pid = sys.argv[1] if len(sys.argv) > 1 else None
    if not pid:
        pid = profiles[0]["id"]
    prof = next(p for p in profiles if p["id"] == pid)
    log(f"profile: {prof.get('name')} engine={prof.get('engine')} language={prof.get('language')}")

    body = {"profile_id": pid, "text": TEXT, "language": "ja"}
    r = client.post(f"{BASE}/generate", json=body)
    log(f"POST /generate -> {r.status_code}")
    gid = r.json()["id"]
    log(f"generation_id={gid}")

    events = 0
    got_progress = False
    stream_closed_at = None
    with client.stream("GET", f"{BASE}/generate/{gid}/status", timeout=None) as resp:
        log(f"GET /status -> {resp.status_code} content-type={resp.headers.get('content-type')}")
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            data = json.loads(line[6:])
            events += 1
            prog = data.get("progress")
            log(f"event #{events} status={data.get('status')} progress={prog} source={data.get('source')}")
            if prog:
                got_progress = True
            if data.get("status") in ("completed", "failed", "not_found"):
                break
            if time.time() - t0 > 480:
                log("TIME LIMIT 480s — closing view")
                break
        stream_closed_at = time.time()
    log(f"SSE stream closed after {stream_closed_at - t0:.1f}s, events={events}, progress_seen={got_progress}")

    if not got_progress or stream_closed_at - t0 < 100:
        r = client.post(f"{BASE}/generate/{gid}/cancel")
        log(f"POST /cancel -> {r.status_code} {r.text[:200]}")

print(f"\nRESULT: events={events} progress_seen={got_progress} stream_alive={stream_closed_at and (stream_closed_at - t0) or 0:.0f}s")
