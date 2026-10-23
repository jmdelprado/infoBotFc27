import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from infobot import analyzer
from infobot.config import Config
from infobot.db import DB
from infobot.models import Item, Tweet
from infobot.render import telegram_format as fmt
from infobot.sources.base import parse_cookies
from infobot.state import empty_state, expire, merge

FIX = Path(__file__).parent / "fixtures"


def tweet(i: str, media=None, hours_ago=1) -> Tweet:
    return Tweet(
        id=i, account="JuniorSintress", created_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        text=f"tweet {i}", url=f"https://x.com/JuniorSintress/status/{i}", local_media=media or [],
    )


def cfg() -> Config:
    return Config(accounts=["JuniorSintress"])


# --- cookies ---
def test_parse_cookies_string_and_json():
    assert parse_cookies("auth_token=a; ct0=b") == {"auth_token": "a", "ct0": "b"}
    assert parse_cookies('[{"name":"auth_token","value":"a"},{"name":"ct0","value":"b"}]') == {"auth_token": "a", "ct0": "b"}
    assert parse_cookies("") == {}


# --- db: sin duplicados ---
def test_db_dedup_and_status():
    db = DB(":memory:")
    assert db.add_tweet(tweet("1"))
    assert not db.add_tweet(tweet("1"))
    assert [t.id for t in db.pending_tweets()] == ["1"]
    db.mark_tweets(["1"], "done")
    assert db.pending_tweets() == []


def test_db_attempts_mark_failed():
    db = DB(":memory:")
    db.add_tweet(tweet("1"))
    for _ in range(3):
        db.bump_attempts(["1"])
    assert db.pending_tweets() == []
    assert db.conn.execute("SELECT status FROM tweets").fetchone()[0] == "failed"


# --- analizador ---
def test_parse_claude_output_structured_and_text():
    out = json.dumps({"type": "result", "is_error": False, "structured_output": {"items": [], "ignored_tweet_ids": ["1"]}})
    assert analyzer.parse_claude_output(out)["ignored_tweet_ids"] == ["1"]
    out = json.dumps({"type": "result", "result": 'texto {"items": [], "ignored_tweet_ids": []} fin'})
    assert analyzer.parse_claude_output(out) == {"items": [], "ignored_tweet_ids": []}


def test_validate_filters_and_detects_missing():
    tweets = [tweet("1", ["1_0.jpg"]), tweet("2"), tweet("3")]
    result = {
        "ignored_tweet_ids": ["2"],
        "items": [
            {"kind": "sbc", "source_type": "official", "title": "T", "summary": "S", "details": "D",
             "key_facts": [], "tweet_ids": ["1", "999"], "images": ["C:/x/1_0.jpg", "inventada.jpg"]},
            {"kind": "raro", "source_type": "official", "title": "X", "summary": "", "details": "",
             "key_facts": [], "tweet_ids": ["3"], "images": []},
        ],
    }
    items, ignored, missing = analyzer.validate(result, tweets)
    assert len(items) == 1
    assert items[0].tweet_ids == ["1"]
    assert items[0].images == ["1_0.jpg"]  # solo imágenes reales de sus tweets
    assert ignored == {"2"}
    assert missing == {"3"}  # el de tipo inválido se reintentará


def test_build_prompt_contains_tweets_and_images():
    p = analyzer._build_prompt([tweet("7", ["7_0.jpg"])], empty_state(), ["Ya publicado"], "Europe/Madrid")
    assert "tweet_id: 7" in p and "7_0.jpg" in p and "Ya publicado" in p


# --- estado ---
def _item(**kw) -> Item:
    base = dict(kind="promo", source_type="leak", title="t", summary="s", details="", key_facts=[], tweet_ids=["1"], images=[])
    base.update(kw)
    return Item(**base)


def test_state_merge_official_overrides_leak_but_not_reverse():
    st = merge(empty_state(), _item(extra={"promo": {"name": "Heroes"}}))
    assert st["active_promo"]["source_type"] == "leak"
    st = merge(st, _item(source_type="official", extra={"promo": {"name": "Heroes", "end": "2099-01-01"}}))
    assert st["active_promo"]["source_type"] == "official"
    st = merge(st, _item(source_type="leak", extra={"promo": {"name": "Heroes", "end": "2000-01-01"}}))
    assert st["active_promo"]["end"] == "2099-01-01"


def test_state_expire():
    st = empty_state()
    st["objectives"] = [{"name": "viejo", "ends": "2000-01-01 10:00"}, {"name": "vivo", "ends": "2099-01-01"}, {"name": "sin fecha"}]
    st["active_promo"] = {"name": "P", "end": "2000-01-01"}
    st = expire(st)
    assert [o["name"] for o in st["objectives"]] == ["vivo", "sin fecha"]
    assert st["active_promo"] is None


def test_state_cards_dedup():
    card = {"player": "Mbappé", "rating": 91, "promo": "X"}
    st = merge(empty_state(), _item(kind="card", extra={"cards": [card]}))
    st = merge(st, _item(kind="card", extra={"cards": [card]}))
    assert len(st["recent_cards"]) == 1


# --- formato Telegram ---
def test_item_message_escapes_and_tags():
    it = _item(kind="sbc", source_type="official", title="A <b> & B", summary="x", details="línea 1\nlínea 2",
               key_facts=[{"label": "Media", "value": "84"}])
    it.urls = ["https://x.com/JuniorSintress/status/1"]
    html = fmt.item_message(it)
    assert "A &lt;b&gt; &amp; B" in html
    assert "#SBC #Oficial #FC27" in html
    assert "<blockquote expandable>" in html
    assert "@JuniorSintress" in html


def test_split_html_respects_limit_and_blockquotes():
    long = "cabecera\n<blockquote expandable>" + "\n".join("x" * 50 for _ in range(200)) + "</blockquote>\n#tag"
    parts = fmt.split_html(long, limit=1000)
    assert len(parts) > 1
    assert all(len(p) <= 1000 for p in parts)
    for p in parts:
        assert p.count("<blockquote") == p.count("</blockquote>")


def test_pinned_and_daily_render():
    st = merge(empty_state(), _item(extra={"promo": {"name": "Heroes", "end": "2099-10-30 19:00"}}))
    html = fmt.pinned_message(st)
    assert "Heroes" in html and "30/10 19:00" in html
    assert len(fmt.pinned_message(empty_state())) < 4096
    d = fmt.daily_message([_item(title="Uno"), _item(kind="sbc", title="Dos", source_type="official")], "23/10/2026")
    assert "Uno" in d and "Dos" in d and "#ResumenDiario" in d


# --- pipeline con datos de ejemplo (sin red ni Claude) ---
def test_pipeline_fixture_dry_run(tmp_path, monkeypatch):
    from infobot import pipeline
    from infobot.__main__ import load_fixture_tweets

    monkeypatch.setattr(pipeline, "OUT_DIR", tmp_path)
    import infobot.outbox as outbox
    monkeypatch.setattr(outbox, "OUT_DIR", tmp_path)

    class FakeRenderer:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def render(self, html, dest, full_page=False):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"png")
            return dest

    monkeypatch.setattr(pipeline, "CoverRenderer", FakeRenderer)
    from infobot.__main__ import load_fixture_analysis

    analysis = load_fixture_analysis()
    res = pipeline.run(cfg(), dry_run=True, tweets=load_fixture_tweets(), analysis_override=analysis,
                       db_path=tmp_path / "x.db", state_path=tmp_path / "state.json")
    assert res["posted"] == 5
    assert not (tmp_path / "state.json").exists()  # en dry-run no se guarda el estado


# --- secciones y calendario ---
def test_topic_routing():
    from infobot.models import topic_for

    assert topic_for("sbc", "official") == "sbc"
    assert topic_for("evolution", "official") == "evolution"
    assert topic_for("sbc", "leak") == "leak"
    assert topic_for("raro", "official") == "event"


def test_state_evolutions_and_future_promo():
    st = merge(empty_state(), _item(kind="evolution", source_type="official",
                                    extra={"evolutions": [{"name": "Speedster", "ends": "2099-01-01"}]}))
    assert st["evolutions"][0]["name"] == "Speedster"
    st = merge(st, _item(extra={"promo": {"name": "Futura", "start": "2099-05-01 19:00"}}))
    assert st["active_promo"] is None  # aún no ha empezado
    assert st["events"][0]["name"] == "Promo Futura"


def test_calendar_buckets():
    from infobot.render.calendar import bucketize, calendar_text, entries_from_state

    now = datetime(2026, 10, 23, 12, 0)
    st = empty_state()
    st["sbcs"] = [{"name": "Hoy", "ends": "2026-10-23 19:00"}, {"name": "Mañana", "ends": "2026-10-24 19:00"},
                  {"name": "Caducado", "ends": "2026-10-22 19:00"}]
    st["evolutions"] = [{"name": "Semana", "ends": "2026-10-28"}, {"name": "Lejos", "ends": "2026-12-01"}]
    st["objectives"] = [{"name": "SinFecha"}]
    st["events"] = [{"name": "Futuro", "starts": "2026-10-25 09:00"}]
    g = bucketize(entries_from_state(st), now)
    names = {k: [e.name for e in v] for k, v in g.items()}
    assert names == {"today": ["Hoy"], "tomorrow": ["Mañana"], "week": ["Semana"], "later": ["Lejos"],
                     "nodate": ["SinFecha"], "soon": ["Futuro"]}
    txt = calendar_text(st, now=now)
    assert "Caducado" not in txt and "Termina hoy" in txt and "Próximamente" in txt


def test_sections_created_once_and_routed(tmp_path):
    from infobot.outbox import Outbox
    from infobot.pipeline import Sections

    db = DB(":memory:")
    pub = Outbox(tmp_path)
    s = Sections(db, pub, dry_run=False)
    a = s.thread("sbc")
    assert s.thread("sbc") == a
    assert json.loads(db.get_meta("topics")) == {"sbc": a}
    assert pub.topics[a] == "🧩 SBC"
