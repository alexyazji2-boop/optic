"""What crawlers are allowed to fetch.

Reported as an assistant, asked to read the site on the owner's behalf,
answering "all blocked by the site's own robots.txt". They were: the file said
`Disallow: /` for every agent. That rule was aimed at search engines and caught
everything, and refusing a reader's own assistant was not what it was for.

Parsed with `urllib.robotparser` rather than read as text, because the question
is what a crawler concludes, not what the file appears to say. A `Disallow`
under the wrong `User-agent` block, or an `Allow` ordered so it never wins, is
invisible to a substring check and decisive to a parser.
"""

from __future__ import annotations

from urllib.robotparser import RobotFileParser

import pytest

ROBOTS = open("static/robots.txt", encoding="utf-8").read()
HTML = open("static/index.html", encoding="utf-8").read()

SITE = "https://theopticterminal.com"


def _parser():
    rp = RobotFileParser()
    rp.parse(ROBOTS.splitlines())
    return rp


# Fetch-on-demand agents: something a person asked to go and read the page.
READERS = ["ClaudeBot", "Claude-User", "Claude-SearchBot", "PerplexityBot",
           "Googlebot", "Bingbot", "SomeUnknownAgent/1.0"]

# Corpus collectors. A different question with a different answer.
TRAINERS = ["GPTBot", "CCBot", "Google-Extended"]


@pytest.mark.parametrize("agent", READERS)
def test_an_assistant_may_read_the_pages(agent):
    """The reported failure. One request, with a reader on the other end."""
    rp = _parser()
    assert rp.can_fetch(agent, SITE + "/"), agent
    assert rp.can_fetch(agent, SITE + "/styles.css"), agent


@pytest.mark.parametrize("agent", READERS)
def test_nobody_may_walk_the_api(agent):
    """The rule that was always the real one.

    Every ticker load hits a rate-limited free data feed shared by everyone on
    the site. A crawler walking /api/ticker/<symbol> across a few thousand
    symbols is a few thousand expensive requests and takes the feed down for
    real readers. The HTML is one small page; this is the surface worth
    protecting, and the only one."""
    rp = _parser()
    for path in ("/api/", "/api/ticker/AAPL", "/api/chat", "/api/home"):
        assert not rp.can_fetch(agent, SITE + path), "{} {}".format(agent, path)


@pytest.mark.parametrize("agent", TRAINERS)
def test_training_crawlers_are_still_refused(agent):
    """Allowing an assistant to read the site when its reader asks costs one
    request. Allowing a corpus collector costs the whole site, forever, with
    nobody on the other end."""
    rp = _parser()
    assert not rp.can_fetch(agent, SITE + "/"), agent


def test_the_file_is_not_a_blanket_refusal_any_more():
    """The specific line that caused the report. Asserted on the parse rather
    than the text so a re-indented or reordered file still counts."""
    rp = _parser()
    assert rp.can_fetch("*", SITE + "/"), \
        "a wildcard Disallow: / is what broke this"


def test_staying_out_of_search_rests_on_the_meta_tag_not_this_file():
    """These two are not interchangeable and only one can do the job.

    A crawler told not to fetch a page never sees the noindex on it, and
    Google's own guidance is that such a URL can still appear in results from
    external links. Allowing the fetch is what makes the noindex effective, so
    the tag has to still be there now that robots.txt no longer duplicates it.
    """
    assert '<meta name="robots" content="noindex, nofollow, noarchive">' in HTML


def test_the_file_says_it_is_not_access_control():
    """It is a request. Anything that ignores it will crawl regardless, and
    the file is public, so it must never hint at paths worth hiding."""
    # Comment markers and wrapping sit inside the sentence, so the raw text
    # never contains it verbatim. Normalise before looking.
    prose = " ".join(ROBOTS.replace("#", " ").split()).lower()
    assert "only real access control is authentication" in prose
