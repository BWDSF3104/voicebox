"""split_text_into_chunks の日本語長文挙動の実地確認（案D検討用スクラッチ）"""
import sys

sys.path.insert(0, r"S:\Documents\Kilo_Commons\voicebox")
from backend.utils.chunked_tts import split_text_into_chunks

sample = (
    "その日、町には乾いた風が吹いていた。街角の古い時計台が、午后三時の鐘を鳴らす。"
    "「またか」と彼は呟いた。彼女は何も言わずに、ただ窓の外を見ていた。\n"
    "遠くの山並みは霞んで見える。風が止むと、街の喧騒だけがやけに大きく響いた。"
    "彼はコートを翻し、扉を開けた。背後で「気をつけて」という声がした気がするが、"
    "振り返らなかった。振り返れば、もう行けない気がしたのだ。\n"
    "路地裏の猫が、彼を見送るように一鳴きした。石畳に影が伸びる。時計の針は三時十五分。"
    "駅の改札は混雑していたが、彼の足取りは止まらなかった。切符売り場の機械が緑の光を灯す。"
    "ホームに降りると、線路の向こうに夕陽が見えた。来るはずのない電車を、彼は待った。\n"
    "十分後、電車は本当にやって来た。ドアが開く。誰も降りてこない車内に、彼は乗り込んだ。"
    "席に座ると、ポケットから古い写真が出てきた。写っているのは二人。もう一人の顔は、"
    "日焼けで褪せて見えない。彼はそっと写真をしまい、目を閉じた。車窓に映る自分の顔が、"
    "少しだけ笑っていたような気がした。\n"
    "次の駅で、誰かが乗り歩いてきた。顔は分からない。声も聞こえない。"
    "ただ、足音だけが続いていく。電子は終点へと進んでいく。彼の旅が終わる場所は、まだ決まっていない。"
)

sample = sample * 4
print(f"sample chars: {len(sample)}")
for max_chars in (800, 2000):
    chunks = split_text_into_chunks(sample, max_chars)
    print(f"\n=== max_chunk_chars={max_chars}: {len(chunks)} chunks ===")
    for i, c in enumerate(chunks):
        head = c[:14].replace("\n", "\\n")
        tail = c[-14:].replace("\n", "\\n")
        print(f"[{i}] len={len(c):4d} | {head} ... {tail}")
        if not c.endswith(("。", "！", "？", "」", "…", "\n")):
            print("      ^^^ 文の途中で切れている可能性")
