"""Validácia antológie, lokálne vyhľadávanie a export diskusie. Bez závislosti na AI."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import json
import math
import re
import unicodedata
from zoneinfo import ZoneInfo

MAX_TURNS = 20
ID_RE = re.compile(r"FPJ\d{2}-\d{4}", re.IGNORECASE)
WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
TYPES = {"paragraph", "heading", "note", "term"}


class CorpusError(ValueError):
    pass


def read_corpus(path: str | Path) -> list[dict]:
    path = Path(path)
    try:
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise CorpusError(f"Chýba dátový súbor {path.name}.") from exc
    except json.JSONDecodeError as exc:
        raise CorpusError(f"Neplatný JSON na riadku {exc.lineno}, stĺpci {exc.colno}.") from exc
    if not isinstance(rows, list) or not rows:
        raise CorpusError("Antológia musí byť neprázdny zoznam záznamov.")
    seen = set()
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            raise CorpusError(f"Záznam {i} nie je objekt.")
        rid = r.get("id")
        if not isinstance(rid, str) or not ID_RE.fullmatch(rid) or rid in seen:
            raise CorpusError(f"Neplatné alebo opakované ID v zázname {i}: {rid!r}.")
        seen.add(rid)
        if r.get("type") not in TYPES or not isinstance(r.get("text"), str) or not r["text"].strip():
            raise CorpusError(f"Záznam {rid} nemá platný typ alebo text.")
        for name in ("work_id", "work_title", "author", "chapter"):
            if not isinstance(r.get(name), str) or not r[name].strip():
                raise CorpusError(f"V zázname {rid} chýba {name}.")
        if r["type"] == "term" and not str(r.get("term", "")).strip():
            raise CorpusError(f"V terminologickom zázname {rid} chýba názov hesla.")
    return rows


def works(rows: list[dict], *, glossary=False) -> list[dict]:
    result = {}
    for r in rows:
        if (r.get("work_kind") == "terminology") != glossary:
            continue
        result.setdefault(r["work_id"], {
            "id": r["work_id"], "title": r["work_title"],
            "author": r["author"], "chapter": r["chapter"],
        })
    return list(result.values())


def authors(rows: list[dict]) -> list[str]:
    return list(dict.fromkeys(w["author"] for w in works(rows)))


def normalize(s: str) -> str:
    """Diakriticky tolerantné vyhľadávanie, nie úprava primárneho textu."""
    s = unicodedata.normalize("NFKD", str(s).casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def tokens(s: str) -> list[str]:
    return [w for w in WORD_RE.findall(normalize(s)) if len(w) > 2]


STOP = set("ako čo co alebo lebo teda kde kedy kto ktorý ktoré ktorá ktory ktore ktora tento toto táto tam táto jeho jej som sme ste sú su bol bola byť byt mám mať mat vtedy preto ktorý a keď ked medzi pred po pre pri do od z na si sa je ze že nie ani ale aby by iba možno možné má majú ak v tom ako to tak že hoci keď".split())


class PassageIndex:
    """Jednoduché vyhľadávanie v lokálnom zdroji bez sťahovania iných prameňov."""
    def __init__(self, rows: list[dict]):
        self.rows = [r for r in rows if r["type"] in ("paragraph", "term")]
        self.positions = {r["id"]: i for i, r in enumerate(self.rows)}
        self.docs = [Counter(t for t in tokens(" ".join([r["text"], r["work_title"],
                          r["author"], r.get("term", ""), r.get("subchapter", "")])) if t not in STOP)
                     for r in self.rows]
        self.df = Counter(t for doc in self.docs for t in doc)

    def find(self, query: str, *, work_ids: set[str] | None = None,
             focus_id: str | None = None, limit: int = 10, include_terms: bool = True) -> list[dict]:
        query_terms = {t for t in tokens(query) if t not in STOP}
        refids = {x.upper() for x in ID_RE.findall(query)}
        scored = []
        for i, r in enumerate(self.rows):
            if r["type"] == "term":
                if not include_terms:
                    continue
            elif work_ids is not None and r["work_id"] not in work_ids:
                continue
            doc = self.docs[i]
            score = sum((1 + math.log(doc[t])) * math.log(1 + (len(self.rows)+1)/(self.df[t]+1))
                        for t in query_terms if doc[t])
            if query_terms and any(k.startswith(t[:6]) for t in query_terms if len(t)>6 for k in doc):
                score += 0.25
            if r["id"].upper() in refids:
                score += 250
            if focus_id == r["id"]:
                score += 1000
            if r["type"] == "term":
                word = normalize(r.get("term", ""))
                if any(t == word or t in word.split() for t in query_terms):
                    score += 6
                # Terminológia nie je automaticky prioritnejšia ako primárny text.
                score *= 0.75
            if score > 0:
                scored.append((score, i))
        top = [i for _, i in sorted(scored, key=lambda x:(-x[0], x[1]))[:limit]]
        if focus_id in self.positions:
            pos = self.positions[focus_id]
            row = self.rows[pos]
            near = [pos] + [j for j in (pos-1, pos+1)
                            if 0 <= j < len(self.rows)
                            and self.rows[j]["work_id"] == row["work_id"]
                            and self.rows[j]["type"] == row["type"]]
            top = list(dict.fromkeys(near + top))[:limit]
        return [self.rows[i] for i in top]


def source_label(r: dict) -> str:
    fields = [r["author"], r["work_title"]]
    if r.get("subchapter") and r["subchapter"] != r["work_title"]:
        fields.append(r["subchapter"])
    page = r.get("source_print_page")
    if page is not None:
        fields.append("s. " + str(page))
    return " | ".join(fields) + f" | interné ID {r['id']}"


def context_for_model(index: PassageIndex, question: str, *, work_ids: set[str] | None = None,
                      focus_id: str | None = None, limit: int = 11,
                      char_budget: int = 14000) -> str:
    rows = index.find(question, work_ids=work_ids, focus_id=focus_id, limit=limit)
    if not rows:
        return "Nenašla sa relevantná pasáž. Nevyvodzuj obsah z iných diel ani z pamäti."
    parts, remaining = [], char_budget
    for r in rows:
        genre = "TERMINOLOGICKÁ POZNÁMKA (P. Cmorej)" if r["type"] == "term" else "FILOZOFICKÁ ŠTÚDIA"  # označenie, nie primárny text
        header = f"[{genre}; {source_label(r)}]"
        max_len = 4000 if focus_id == r["id"] else 1600
        budget = min(len(r["text"]), max_len, remaining - len(header) - 35)
        if budget < 50:
            break
        body = r["text"] if budget >= len(r["text"]) else r["text"][:budget].rsplit(" ", 1)[0] + " […] [skrátené]"
        part = header + "\n" + body
        parts.append(part)
        remaining -= len(part) + 2
    return "\n\n".join(parts) + "\n\nInterné identifikátory FPJxx-yyyy nie sú číslovaním autorov. OCR môže obsahovať chyby."


def glossary_search(rows: list[dict], query: str) -> list[dict]:
    terms = [r for r in rows if r["type"] == "term"]
    needle = normalize(query.strip())
    if not needle:
        return terms
    return [r for r in terms if needle in normalize(r.get("term", "") + " " + r["text"])]


def api_error_message(exc: Exception, model: str) -> str:
    code = getattr(exc, "code", None)
    msg = str(exc).lower()
    if code == 429 or "429" in msg or "resource_exhausted" in msg:
        return f"Gemini API prekročilo alebo nemá dostupnú kvótu (429; model {model}). Skontrolujte limity v Google AI Studio."
    if code == 503 or "503" in msg or "service_unavailable" in msg:
        return "Gemini API je dočasne nedostupné (503). Skúste opakovať neskôr."
    if code == 404 or "404" in msg or "not_found" in msg:
        return f"Model {model} nie je dostupný (404). Skontrolujte GEMINI_MODEL v Streamlit Secrets."
    if code in (401, 403) or "401" in msg or "403" in msg:
        return "Gemini API odmietlo prístup. Skontrolujte API kľúč a oprávnenia projektu."
    if "timeout" in msg or "timed out" in msg:
        return "Gemini nestihlo odpovedať v stanovenom časovom limite (ReadTimeout)."
    return f"Požiadavka zlyhala ({type(exc).__name__}). Detail nájdete v Streamlit Logs."


def export_transcript(messages: list[dict], name: str, model: str, session_id: str,
                      scope: str, when: datetime | None = None) -> str:
    when = when or datetime.now(ZoneInfo("Europe/Bratislava"))
    out = ["FILOZOFIA PRIRODZENÉHO JAZYKA – SOKRATOVSKÝ DIALÓG", "="*56,
           "Študent/ka: " + (name.strip() or "(neuvedené)"),
           "Dátum: " + when.strftime("%d. %m. %Y %H:%M %Z"),
           "Model: " + model, "Relácia: " + session_id,
           "Použité pramene: " + scope,
           f"Počet otázok: {sum(m['role']=='user' for m in messages)}/{MAX_TURNS}", "", "PREPIS", "="*56, ""]
    for msg in messages:
        out.extend(["ŠTUDENT:" if msg["role"] == "user" else "AI TÚTOR:", msg["content"], ""])
    return "\n".join(out)
