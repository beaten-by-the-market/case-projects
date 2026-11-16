"""s09h 코스닥 검토 기록 — 서식(유형)별로 한 기준을 정해 s09_review_kosdaq.json 에 적는다

왜: 코스닥 1,780사를 서브에이전트(API 대신, 사용자 지시 2026-11-16)가 묶음별로 판별했더니, 몇 가지 정관 서식에서 묶음마다
    태그가 갈렸다(같은 서식에 정관yes·정관yesorno·확인필요가 섞임). 서식을 정규식으로 가르고 기준을 하나로 정한다.
    기준은 tagging-guide 의 판별 순서·함정과 코스피 사람 검토(s09_review.json)의 선례를 따른다.

서식과 판정
  소멸시효조 잔존문구  스팩 표준 서식 — 이익배당 조 ③은 '이사회 결의로 정하는 배당기준일', 그런데 배당금지급청구권 소멸시효 조
                      ②에 '제1항의 배당은 매결산기말 현재 … 지급한다'가 남아 있다. 그 '제1항'은 소멸시효 조 ①(지급청구권 5년)을
                      가리켜 뜻이 통하지 않는다 → 옛 이익배당 조 문구가 지워지지 않고 남은 것으로 보고 정관no
                      (코스피 현대모비스: 같은 항의 새 문구가 옛 문구를 대신한 것으로 본 선례).
  기준일조 354단서     결산배당 조는 '매결산기말 현재'로 고정, 기준일(주주명부 폐쇄) 조는 상법 제354조 문구대로 '의결권을 행사하거나
                      배당을 받을 자 … 를 정하기 위하여 이사회 결의로 … 정한 날' → 결산배당에 대해 고정과 이사회 지정이 둘 다
                      살아 있으므로 정관yesorno (지침 판별 순서 5: 기준일 조가 배당을 명시하면 결산배당 규정으로 본다 — 그 반대 방향).
                      ①의 고정 폐쇄기간·③의 '임시주주총회의 소집 기타 필요한 경우' 이사회 문구는 여기에 들지 않는다(한 문장 안에서만 잡음).
  택일형              '정기주주총회에서 권리를 행사할 주주로 하거나 이사회 결의로 정하는 배당기준일 현재의 주주' → 정관yesorno.
                      다만 정기주총 기준일 자체가 이사회 결정이면(고정일 없음) 정관no 로 둔 서브에이전트 판단을 그대로 둔다.
  임시주총 조항 참조   결산배당 조가 기준일 조 전체(또는 '임시주주총회의 소집 기타 필요한 경우' 항)를 가리키는 경우 → 그 항은 결산배당
                      기준일 규정이 아니므로(지침 함정) 고정일만 남아 정관yes — 개별 판정(CASES)

출력  data/interim/s09_review_kosdaq.json  {종목코드: {tag, by, at, why, llm_tag, kind}}  — s09c --sfx kosdaq 가 읽는다
      판정이 서브에이전트 태그와 같아도 검토 대상(review)이면 '유형 확인'으로 적어 둔다.

    python -X utf8 scripts/s09h_kosdaq_review.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import read_json, write_json  # noqa: E402
import s09a_dividend_excerpt as X  # noqa: E402
import s09c_dividend_build as C  # noqa: E402

SFX = "kosdaq"
BY = "Claude(kospi-charter-9c) 서식 판정"
AT = "2026-11-16"
SM = re.compile(r"소\s*멸\s*시\s*효|消\s*滅\s*時\s*效")
TAEK = re.compile(r"권리를행사할주주로하거나(?:이사회|이사회의)")
C354 = re.compile(r"배당을받을자[^.。②③④⑤]{0,80}?정하기위하여[^.。②③④⑤]{0,15}?이사회|이사회[^.。②③④⑤]{0,80}?배당을받을자")
REMNANT = re.compile(r"소멸시효\)?.{0,400}?②제1항의배당은매결산기말현재")
S = lambda s: re.sub(r"\s", "", s)  # noqa: E731

WHY = {
    "소멸시효조 잔존문구": "스팩 서식 — 이익배당 조는 이사회가 배당기준일을 정하는데, 배당금지급청구권 소멸시효 조 ②에 '제1항의 배당은 "
                       "매결산기말 현재 … 지급'이 남아 있다. 그 '제1항'은 소멸시효 조 ①을 가리켜 뜻이 통하지 않으므로 옛 문구가 "
                       "지워지지 않은 것으로 보고 이익배당 조를 따른다 → 정관no",
    "기준일조 354단서": "결산배당 조는 결산기말 고정이지만 기준일 조가 상법 제354조 문구대로 '배당을 받을 자'를 정하기 위해 이사회가 "
                     "날을 정할 수 있게 한다 — 결산배당에 대해 고정과 이사회 지정이 함께 살아 있으므로 정관yesorno",
    "택일형": "결산배당 대상을 '정기주총 권리행사 주주(결산기말)로 하거나 이사회가 정하는 배당기준일 주주'로 둔 택일형 — 고정과 "
            "이사회 지정이 함께 살아 있으므로 정관yesorno",
}
# 개별 판정 — 원문 대조
CASES = {
    "0132G0": ("정관no", "소멸시효조 잔존문구", "第56조(배당금지급청구권의 소멸시효) ②에 '제1항의 배당은 매결산기말 현재 …' 가 남은 스팩 서식"
               "(조 머리가 한자라 정규식이 놓침) — 이익배당 조 제55조 ③(이사회가 정하는 배당기준일)을 따른다 → 정관no"),
    "456070": ("정관yes", "임시주총 조항 참조", "결산배당 조가 제16조 전체를 가리키지만 ③은 '임시주주총회의 소집 기타 필요한 경우' 이사회 기준일이라 "
               "결산배당 규정이 아니다. ②의 '매사업년도의 말일' 고정만 남는다 → 정관yes"),
    "270870": ("정관yes", "임시주총 조항 참조", "이익배당 조 ②가 매 결산기말 현재로 고정하고, ③이 가리키는 제15조 ②는 '임시주주총회의 소집 기타 "
               "필요한 경우' 이사회 기준일이다 — ①(12월 31일)을 가리키려던 참조 오기로 본다(코스피 쏘카 선례) → 정관yes"),
    "327260": ("정관yes", "임시주총 조항 참조", "결산배당 조가 제16조 전체를 가리키는데 ②는 '임시주주총회의 소집 기타 필요한 경우' 이사회 기준일이라 "
               "결산배당 규정이 아니고 ①이 매년 12월 31일. 소멸시효 조 ②의 '매결산기말' 문구도 고정 → 정관yes"),
    "252990": ("정관yesorno", "기준일조 기본값", "결산배당 조는 이사회가 정하는 배당기준일이지만, 기준일 조 ①이 '배당을 받을 자'를 목적에 넣고 ③이 "
               "이사회가 정하지 않으면 매 결산기 최종일 주주로 본다 — 기준일 조가 배당을 명시해 기본값을 고정하므로 지침 판별 순서 5에 따라 "
               "정관yesorno"),
    "039290": ("정관yes", "부칙·본문 불일치", "본문 제53조 ③은 매 결산기말 고정. 부칙(2021.03.30) 정관변경 내역은 이 항을 '이사회 결의로 정하는 "
               "배당기준일'로 바꿨다고 적지만 본문에 반영되지 않았다 — 본문 기준 정관yes 로 두고 특이사항에 적는다"),
}
# 서식 판정 밖의 검토 대상 — 서브에이전트 메모와 규칙 판별을 대조해 태그를 그대로 둔다 (원문 대조가 아니라 메모 대조임을 by 에 밝힌다)
BY_NOTE = "Claude(kospi-charter-9c) 메모·규칙 대조"


def note_why(r: dict) -> str:
    llm, rt, note = r["llm_tag"], r["rule_tag"], r["note"] or ""
    if llm == "정관no" and rt == "정관yesorno":
        return ("규칙의 결산기말 고정(F)은 기준일 조의 '12월 31일 … 정기주주총회에서 권리를 행사할 주주' 문구를 잡은 것 — 결산배당 조는 "
                "이사회가 기준일을 정한다 → 정관no 유지")
    if llm == "정관yesorno":
        return "고정과 이사회 지정이 함께 살아 있음(기준일 조 '다만 … 배당을 받을 자' 단서, 같은 조 고정 항+이사회 항, 외국 법인 정관 등) → 정관yesorno 유지"
    if llm == "정관yes" and "※" in note:
        return "표준정관 ※ 주석('다른 날로 배당기준일을 정할 수 있음')은 결정 주체가 없는 안내 문구로 본문 규정이 아니다 → 정관yes 유지"
    return "서브에이전트 메모와 규칙 판별 대조 — 태그 유지"


def classify(excerpt: str) -> dict:
    t = re.sub(r"^\[발췌 \d+ · [^\]\n]*\]$", "", excerpt, flags=re.M)
    d = {"div_b": False, "div_f": False, "sm_f": False, "taek": False, "c354": False}
    for head, seg in C.segments(t):
        h = head.split("\n")[0]
        if C.SUBART.search(h) and not re.search(r"(?:이\s*익|利\s*益)\s*" + X.배당 + r"\s*(?:및|과|,)", h):
            continue
        if SM.search(h):
            d["sm_f"] |= C.f_hit(seg)
            continue
        if re.search(X.배당, h):
            d["div_b"] |= bool(C.B.search(seg)) or bool(C.B_DIV.search(seg))
            d["div_f"] |= C.f_hit(seg)
            d["taek"] |= bool(TAEK.search(S(seg)))
        else:
            d["c354"] |= bool(C354.search(S(seg)))
    d["remnant"] = bool(REMNANT.search(S(t)))
    return d


def decide(d: dict, llm: str) -> tuple[str | None, str | None]:
    if d["taek"]:
        return ("정관yesorno" if llm != "정관no" else "정관no"), "택일형"
    if d["div_b"] and not d["div_f"] and (d["sm_f"] or d["remnant"]):
        return "정관no", "소멸시효조 잔존문구"
    if d["div_f"] and not d["div_b"] and d["c354"]:
        return "정관yesorno", "기준일조 354단서"
    return None, None


def main():
    P = X.paths(SFX)
    ex = {e["stock_code"]: e for e in map(json.loads, P["excerpts"].read_text(encoding="utf-8").splitlines())}
    rows = read_json(P["out_json"])
    old = read_json(P["review"]) if P["review"].exists() else {}
    out = {k: v for k, v in old.items() if not str(v.get("by", "")).startswith((BY, BY_NOTE))}    # 사람이 따로 적은 것은 둔다
    cnt = Counter()
    for r in rows:
        code, llm = r["stock_code"], r["llm_tag"]
        if not llm or code in out:
            continue
        if code in CASES:
            tag, kind, why = CASES[code]
        else:
            tag, kind = decide(classify(ex[code]["excerpt"]), llm)
            if not kind or (tag == llm and not r["review"]):
                continue
            why = WHY[kind] + ("" if tag != llm else " (서브에이전트 태그와 같음 — 유형 확인)")
            if kind == "택일형" and tag == "정관no":
                why = "택일형이지만 정기주총 기준일 자체도 이사회 결정(고정일 없음) — 두 갈래 모두 이사회 지정이므로 정관no (서브에이전트 판단 유지)"
        out[code] = {"tag": tag, "by": BY, "at": AT, "why": why, "llm_tag": llm, "kind": kind}
        cnt[(kind, llm, tag)] += 1
    for r in rows:                                       # 남은 검토 대상 (확인필요는 s09f 로)
        code, llm = r["stock_code"], r["llm_tag"]
        if code in out or not r["review"] or not llm or llm == "확인필요":
            continue
        out[code] = {"tag": llm, "by": BY_NOTE, "at": AT, "why": note_why(r), "llm_tag": llm, "kind": "메모 대조"}
        cnt[("메모 대조", llm, llm)] += 1
    write_json(P["review"], out)
    for k, n in sorted(cnt.items()):
        print(k, n)
    print(f"검토 기록 {len(out)}건 → {P['review'].name} (바뀐 태그 {sum(1 for v in out.values() if v['tag'] != v['llm_tag'])})")


if __name__ == "__main__":
    main()
