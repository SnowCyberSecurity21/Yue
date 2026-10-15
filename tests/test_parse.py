import pytest

from yue.ai.parse import EXPRESSIONS, Action, clean_markdown, parse_reply, stream_visible


@pytest.mark.parametrize("expr", EXPRESSIONS)
def test_expression_tag(expr):
    r = parse_reply(f"[{expr}] Matn.")
    assert r.expression == expr and r.text == "Matn."


def test_missing_or_unknown_expression():
    assert parse_reply("Shunchaki matn.").expression == "neutral"
    r = parse_reply("[evil] Matn.")
    assert r.expression == "neutral" and r.text == "Matn."


def test_all_tags():
    raw = (
        "[happy] Yozdim. Soat 09:00 da eslataman.\n"
        '<vazifa vaqt="2026-10-14 09:00">Dori ichish</vazifa>\n'
        '<vazifa vaqt="08:00" takror="har_kuni">Suv ichish</vazifa>\n'
        "<vazifa>Hisobotni yozish</vazifa>\n"
        "<bajarildi>3</bajarildi><ochir>#7</ochir>\n"
        "<eslab>Ismi Aziz, dasturchi</eslab>\n"
        "<salomatlik>Penitsillinga allergiyasi bor</salomatlik>"
    )
    r = parse_reply(raw)
    assert r.text == "Yozdim. Soat 09:00 da eslataman."
    assert r.actions == [
        Action("task", "Dori ichish", when="2026-10-14 09:00"),
        Action("task", "Suv ichish", when="08:00", repeat="har_kuni"),
        Action("task", "Hisobotni yozish"),
        Action("done", task_id=3),
        Action("delete", task_id=7),
        Action("remember", "Ismi Aziz, dasturchi"),
        Action("health", "Penitsillinga allergiyasi bor"),
    ]


def test_english_aliases():
    r = parse_reply(
        '[neutral] Ok. <task time="2026-01-01 10:00">X</task><done>1</done>'
        "<remember>Y</remember><health>Z</health><delete>2</delete>"
    )
    assert [a.kind for a in r.actions] == ["task", "done", "remember", "health", "delete"]
    assert r.actions[0].when == "2026-01-01 10:00"


def test_bad_tags_not_executed():
    raw = (
        "[neutral] Mana.\n"
        "<vazifa vaqt=\"ertaga\">Noto'g'ri vaqt</vazifa>\n"
        "<bajarildi>hech</bajarildi>\n"
        "<run>rm -rf /</run>\n"
        "<vazifa>yopilmagan teg"
    )
    r = parse_reply(raw)
    kinds = [(a.kind, a.when, a.task_id) for a in r.actions]
    assert kinds == [("task", None, None)]  # noto'g'ri vaqt → muddatsiz; qolganlari bajarilmaydi
    assert "<vazifa" not in r.text and "yopilmagan" in r.text
    assert "<run>" in r.text  # oq ro'yxatda yo'q teg — oddiy matn, hech narsa bajarilmaydi


def test_daily_with_full_datetime_keeps_time():
    r = parse_reply('<vazifa vaqt="2026-10-14 21:30" takror="har_kuni">Dori</vazifa>')
    assert r.actions == [Action("task", "Dori", when="21:30", repeat="har_kuni")]


def test_markdown_cleanup():
    raw = (
        "## Sarlavha\n**Muhim:** `pip install x`\n* birinchi\n* ikkinchi\n```python\nprint(1)\n```"
    )
    out = clean_markdown(raw)
    assert "**" not in out and "#" not in out and "```" not in out and "`" not in out
    assert "- birinchi" in out and "print(1)" in out and "pip install x" in out


def test_repeated_expression_tags_removed():
    assert parse_reply("[happy] Salom [smug] dedim.").text == "Salom dedim."


def test_action_limit():
    raw = "[neutral] ok " + "".join(f"<eslab>f{i}</eslab>" for i in range(20))
    assert len(parse_reply(raw).actions) == 8


@pytest.mark.parametrize("name", ["o_pish", "bagirga_bosil", "erka"])
def test_affection_commands_are_not_allowlisted(name):
    reply = parse_reply(f"[love] *jilmayadi* <harakat>{name}</harakat>")
    assert reply.command is None and reply.expression == "happy"
    assert reply.text == "*jilmayadi*"


def test_shy_command_is_allowlisted():
    assert parse_reply("[shy] B-bu maqtovmi? <harakat>uyal</harakat>").command == "uyal"


@pytest.mark.parametrize(
    ("partial", "visible"),
    [
        ("", ""),
        ("[hap", ""),
        ("[happy] Sal", "Sal"),
        ("[happy] Salom! <vaz", "Salom!"),
        ("[happy] Salom! <", "Salom!"),
        ("[happy] x < 5 bo'lsa, yaxshi", "x < 5 bo'lsa, yaxshi"),
        ("[happy] Tayyor.\n<eslab>fakt", "Tayyor."),
    ],
)
def test_stream_visible(partial, visible):
    assert stream_visible(partial) == visible
