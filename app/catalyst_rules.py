"""Catalysts without the model: published rules over what the terminal fetched.

The library was filled by a model call per scan, paid for on the owner's key,
and asked about as "is there no way to make the catalyst scan not require my AI
credits? its a web search of catalysts for the specific ticker essentially
across several factors". There is, and this is it. It reads the same stories
the model was shown, and for one company its own headlines, the wires that
name it, its 8-K filings and its next report date, with rules a reader can
check against the source.

**What makes a story a catalyst.** Its headline has to say who acted and what
they did: a government, legislature, central bank, regulator or court taking
an action on a market theme, or a named company doing something that outlasts
the session (a deal, a large investment, a ruling against it, a halted
launch). Or a benchmark has to break a level, "highest since 2002", "past 7%".
Measured on the week's 120 stories on 2026-09-29, a theme word alone filed 45
of them, and most were commentary: "Jim Cramer says these stocks can win",
"How the Fed should measure inflation", a Fed governor's speech, a warning
letter, a bank's approved application. Requiring the actor and the action
filed 17, and every one was an event.

**What rules cannot do**, and the page's method note says so: tell a new
programme from a restatement of an old one, write a title of their own (the
headline is the title and the story's own summary is the summary), or weigh
how much an event matters to a company the story names.

**Company links are of two kinds, and each says which it is.** A company is
linked directly when the story names it, by a name on the list below or by an
exchange ticker in the text, and the caller checks every symbol against EDGAR.
And a subject carries the few US-listed companies whose economics it reaches
in the standard way: the crude price is a producer's revenue and an airline's
fuel bill. Those are labelled as the standard read-through, never as something
the story said.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ------------------------------------------------------------------ noise
#
# Shapes that are never an event, whatever words they contain. Matched on the
# headline. Kept to shapes rather than topics, as the News tab's filler rule is,
# because a topic list would drop real news that happens to share a word.
_NOISE = [re.compile(p) for p in (
    # Questions, explainers and how-tos.
    r"\?\s*$",
    r"^(?:How|Why|What|Who|When|Where|Which|Here's|Here are|Here is|Is|Are|Can|Could|"
    r"Should|Would|Will|Do|Does|Did)\b",
    r"^(?:Watch|Video|Listen|Podcast|Opinion|Analysis|Explainer|Live|Quiz|Guest Contribution)\b",
    r"^(?:The|A|An) (?:[Hh]idden|[Rr]eal|[Tt]rue|[Bb]ig|[Cc]ase|[Pp]roblem|[Tt]rouble|[Ll]essons?|[Mm]yth)\b",
    r"^(?:Five|Four|Three|Ten|\d+) (?:takeaways|things|charts|stocks|ways|reasons)\b",
    # Commentary and newsletter slots.
    r"\bCramer\b", r"\bMorning Squawk\b", r"\bMarket Talk\b", r"\bRoundup\b",
    r"\bPharmalittle\b", r"\bWe're reading about\b", r"\b[Nn]ewsletter\b",
    r"\b[Ss]tocks? to watch\b", r"\bbiggest moves\b", r"^Tech Now$",
    r"^Stock Market Today\b", r"^Top (?:Analyst|Research|Stock) (?:Reports|Picks)\b",
    r"\bOutlook Highlights\b", r"\bZacks\b", r"\bAnalyst Blog\b",
    # A named person's quoted remark, and a columnist's byline.
    r"^[A-Z][\w.'-]+(?: [A-Z][\w.'-]+)?: ['‘“\"]",
    r"^[A-Z][\w.'-]+ [A-Z][\w.'-]+ \| ",
    # Routine notices from the agencies.
    r"\b[Aa]pproval of (?:[Aa]n )?[Aa]pplication\b", r"\b[Ee]nforcement [Aa]ction\b",
    r"\bRules of Practice\b", r"\bFederal Register Notices?\b", r"\bFAQs?\b",
    r"\bStaff Advisory\b", r"\b[Rr]egular [Rr]eview\b", r"\bOpening Remarks\b",
    r"\b[Cc]onsent [Dd]ecree\b",
    # A CBO cost estimate names a bill by number; an FDA warning letter is a
    # firm, a letter number and a date.
    r"^(?:S|H\.R|H\.J\.Res|S\.J\.Res)\. ?\d+",
    r" - \d{5,7} - \d{2}/\d{2}/\d{4}$",
)]
# Central-bank speeches are titled "Surname, Title" or "Name: Title". Only for
# those sources: in a wire headline the same shape is "Trump, Xi agree to".
_SPEECH = re.compile(r"^[A-Z][\w.'-]+(?: [A-Z]\.?)?(?: [A-Z][\w.'-]+)?(?:,|:) ")
_SPEECH_SOURCES = {"Federal Reserve", "European Central Bank", "New York Fed",
                   "Bank of England", "Bank of Japan", "Bank of Canada"}


def is_noise(title: str, source: str = "") -> bool:
    text = title or ""
    if any(p.search(text) for p in _NOISE):
        return True
    return source in _SPEECH_SOURCES and bool(_SPEECH.search(text))


# ---------------------------------------------------------------- actors
#
# Who can make an event. Case-insensitive except "US", which lowercased is a
# pronoun.
_ACTOR_TABLE: List[Tuple[str, str]] = [
    ("central-bank", r"\b(?:fed|federal reserve|fomc|powell|warsh|ecb|lagarde"
                     r"|bank of (?:england|japan|canada)|boe|boj|pboc|people's bank of china"
                     r"|central banks?)\b"),
    ("regulator", r"\b(?:fda|ftc|sec|cftc|doj|justice department|department of justice|fcc|ferc"
                  r"|faa|nhtsa|cfpb|occ|fdic|finra|epa|usda|ustr|regulators?|watchdog"
                  r"|antitrust enforcers|european commission|brussels)\b"),
    ("court", r"\b(?:judge|judges|court|courts|supreme court|jury|tribunal)\b"),
    ("government", r"\b(?:trump|white house|administration|president|congress|senate"
                   r"|lawmakers|legislators|house (?:passes|votes|panel|committee|republicans"
                   r"|democrats|speaker|bill)|treasury(?! (?:yields?|bonds?|notes?|bills?|market"
                   r"|auction))|commerce department|pentagon|state department"
                   r"|energy department|interior department|government|parliament"
                   r"|prime minister|chancellor|g7|g20|nato|opec\+?|imf)\b"),
    ("state", r"\b(?:u\.s\.|america|washington|china|beijing|russia|moscow|ukraine|kyiv|iran"
              r"|tehran|israel|saudi arabia|riyadh|eu|european union|uk|britain|japan|tokyo"
              r"|india|canada|ottawa|mexico|germany|france|taiwan|south korea|seoul)\b"),
]
_ACTORS = [(kind, re.compile(p, re.I)) for kind, p in _ACTOR_TABLE]
_US = re.compile(r"(?<![A-Za-z])US(?![A-Za-z])")


def actors_in(title: str) -> List[str]:
    kinds = [kind for kind, rx in _ACTORS if rx.search(title or "")]
    if _US.search(title or "") and "state" not in kinds:
        kinds.append("state")
    return kinds


# --------------------------------------------------------------- actions
#
# What an actor did: a decision, a move toward one, or a consequence with a
# number on it. Not "says", "meets", "weighs in", which are remarks.
_ACTION = re.compile(r"""\b(?:
    approv(?:e|es|ed|al)|bans?|banned|bars?|barred|lifts?|lifted|impos(?:e|es|ed)|slaps?|slapped
  | announc(?:e|es|ed)|agre(?:e|es|ed)|signed|signs?\ (?:a|an|the|into|off|deal|law|order|bill)
  | pass(?:es|ed)|advanc(?:e|es|ed)
  | vot(?:e|es|ed)\ (?:to|on)|cuts?|rais(?:e|es|ed)|hik(?:e|es|ed)|holds?\ (?:rates|steady)
  | keeps?\ rates|lower(?:s|ed)?|halt(?:s|ed)?|paus(?:e|es|ed)|suspend(?:s|ed)?|block(?:s|ed)?
  | reject(?:s|ed)?|rules?\ out|rules\ (?:that|against|for)|ordered|orders|propos(?:e|es|ed|al|als)
  | finali[sz](?:e|es|ed)|launch(?:es|ed)?\ (?:a\ )?(?:probe|investigation|review)
  | opens?\ (?:a\ )?(?:probe|investigation)|probes?|investigat(?:e|es|ed|ing|ion)
  | sues?|sued|lawsuit|fined|fines|penalt(?:y|ies)|settle(?:s|d|ment)?|wins?|won|loses|losing
  | threaten(?:s|ed)?|consider(?:s|ing)|plans?\ (?:to|for)|planned
  | unveil(?:s|ed)?|extend(?:s|ed)?|expand(?:s|ed)?|restrict(?:s|ed|ions?)|tighten(?:s|ed)?
  | eas(?:e|es|ed)\ (?:rules|restrictions|sanctions)|invad(?:e|es|ed)|invasion|strikes?\ on
  | attack(?:s|ed)?|seiz(?:e|es|ed)|sanction(?:s|ed)|takes?\ effect|comes?\ into\ force
  | come\ into\ force|roll(?:s|ed)?\ back|rollback|repeal(?:s|ed)?|scrap(?:s|ped)?|delay(?:s|ed)?
  | requests?\ public\ comment|changes\ to|mandat(?:e|es|ed)|requir(?:e|es|ed)
  | invest(?:s|ed|ment)?|backs|backed|inject(?:s|ed)?|acquir(?:e|es|ed)|acquisition|merg(?:e|es|ed|er)
  | buyout|takeover|stake|ipo|files?\ for|s-1|bankrupt(?:cy)?|default(?:s|ed)?|resign(?:s|ed)?
  | steps?\ down|appoint(?:s|ed)?|nominat(?:e|es|ed)|oust(?:s|ed)?|recall(?:s|ed)?
  | ceasefire|blockade|emergency|shutdown|declar(?:e|es|ed)
  | to\ (?:cut|raise|lower|impose|ban|lift|end|scrap|expand|invest|build|buy|sell|acquire|merge
         |pay|open|close|exit)
)\b""", re.I | re.X)
# Money in the headline: a deal size, a fine, an investment.
_MONEY = re.compile(r"(?:[$€£]\s?\d[\d.,]*\s?(?:bn|billion|trillion|tn|m\b|million)"
                    r"|\d[\d.,]*\s?(?:billion|trillion)\b)", re.I)


# ------------------------------------------------------------ market moves
#
# A benchmark through a level is an event without an actor.
_BENCHMARK = re.compile(r"\b(?:treasury yields?|(?:2|5|10|30)-year(?: treasury)?(?: yield)?"
                        r"|bond yields?|mortgage rates?|oil prices?|crude(?: oil)?|brent|wti"
                        r"|gold(?: price| prices| futures)?|silver|copper prices?|natural gas prices?"
                        r"|henry hub|dollar(?! general| tree)|yen|euro|yuan|bitcoin)\b", re.I)
_THRESHOLD = re.compile(r"\b(?:highest since|lowest since|\d+-year (?:high|low)|record (?:high|low)"
                        r"|all-time (?:high|low)|breaks? (?:above|below|past|through)"
                        r"|broke (?:above|below|past|through)|tops? [$€£]?\d|crosses"
                        r"|(?:surges?|jumps?|plunges?|falls?|drops?) (?:past|above|below|to) "
                        r"[$€£]?\d)", re.I)


# --------------------------------------------------------------- themes
#
# What an event is about. `policy` themes are the kind of action; `subject`
# themes are the sector or commodity it reaches, and carry the sectors a
# ticker search reaches through and the standard read-through companies.
#
# Exposures are (ticker, directness, strength, why), kept to links that are
# structural and long-lived, in words that stay true.
THEMES: List[Dict[str, Any]] = [
    # --- policy
    {"id": "trade", "label": "Tariffs and trade", "kind": "policy", "category": "geopolitical",
     "horizon": "long-term",
     "patterns": [r"\btariffs?\b", r"\btrade (?:war|deal|talks|truce|agreement|pact|dispute)s?\b",
                  r"\bimport (?:restrictions?|duty|duties|quotas?|bans?)\b", r"\bcustoms dut(?:y|ies)\b",
                  r"\b(?:ban|bans|banned) on [\w\s]{0,30}imports\b"],
     "sectors": ["Industrials", "Consumer Discretionary", "Materials"]},
    {"id": "export", "label": "Export controls", "kind": "policy", "category": "geopolitical",
     "horizon": "long-term",
     "patterns": [r"\bexport (?:controls?|curbs?|restrictions?|bans?|licen[cs]es?)\b", r"\bentity list\b"],
     "sectors": []},
    {"id": "sanctions", "label": "Sanctions", "kind": "policy", "category": "geopolitical",
     "horizon": "long-term",
     "patterns": [r"\bsanctions?\b", r"\bembargo(?:es)?\b", r"\basset freezes?\b"], "sectors": []},
    {"id": "conflict", "label": "War and conflict", "kind": "policy", "category": "geopolitical",
     "horizon": "medium-term",
     "patterns": [r"(?<!trade )(?<!price )(?<!bidding )(?<!star )\bwars?\b", r"\binvasion\b",
                  r"\bairstrikes?\b", r"\bceasefire\b", r"\bblockade\b", r"\bhormuz\b",
                  r"\bmilitary\b", r"\btroops\b"],
     "sectors": ["Energy", "Industrials"]},
    {"id": "monetary", "label": "Central-bank policy", "kind": "policy", "category": "monetary-policy",
     "horizon": "medium-term",
     "patterns": [r"\brate (?:cuts?|hikes?|increases?|decisions?|path)\b", r"\binterest rates\b",
                  r"\bmonetary policy\b", r"\bquantitative (?:easing|tightening)\b",
                  r"\bbalance sheet\b", r"\bfed chair\b"],
     "sectors": ["Financials", "Real Estate"]},
    {"id": "antitrust", "label": "Antitrust", "kind": "policy", "category": "regulatory",
     "horizon": "long-term",
     "patterns": [r"\bantitrust\b", r"\bmonopol(?:y|ies|istic)\b", r"\bcompetition (?:law|probe|case)\b",
                  r"\bdigital markets act\b"],
     "sectors": []},
    {"id": "regulation", "label": "Rules and approvals", "kind": "policy", "category": "regulatory",
     "horizon": "long-term",
     "patterns": [r"\bregulat(?:ory|ion|ions|es|ed|ing)\b", r"\bframework\b", r"\brules?\b",
                  r"\bstandards\b", r"\bapprov(?:e|es|ed|al)\b", r"\bguidance\b", r"\bpatent\b",
                  r"\blawsuit\b", r"\bsuit\b", r"\bsettlement\b", r"\bcharges\b", r"\bprobe\b",
                  r"\binvestigation\b"],
     "sectors": []},
    {"id": "legislation", "label": "Legislation", "kind": "policy", "category": "government",
     "horizon": "long-term",
     "patterns": [r"\blegislation\b", r"\bbill\b", r"\bact\b", r"\bsenate\b", r"\bcongress\b",
                  r"\blawmakers\b", r"\bexecutive orders?\b"],
     "sectors": []},
    {"id": "fiscal", "label": "Budget and taxes", "kind": "policy", "category": "government",
     "horizon": "medium-term",
     "patterns": [r"\bbudget\b", r"\bgovernment shutdown\b", r"\bdebt ceiling\b", r"\bstimulus\b",
                  r"\btax(?:es)?\b", r"\bsubsid(?:y|ies)\b", r"\bspending\b"],
     "sectors": []},
    {"id": "industrial", "label": "Industrial policy", "kind": "policy", "category": "government",
     "horizon": "long-term",
     "patterns": [r"\bplant\b", r"\bfactory\b", r"\bjoint venture\b", r"\bpublic investment\b",
                  r"\bnational security\b", r"\bstrategic reserve\b"],
     "sectors": []},

    # --- subjects
    {"id": "oil", "label": "Crude oil", "kind": "subject", "category": "commodity",
     "horizon": "medium-term",
     "patterns": [r"\bcrude\b", r"\bopec\+?", r"\bbrent\b", r"\bwti\b", r"\boil\b", r"\bbarrels?\b",
                  r"\bhormuz\b"],
     "sectors": ["Energy"],
     "exposures": [
         ("XOM", "direct", "strong", "An integrated oil major, so its earnings move with the crude price."),
         ("CVX", "direct", "strong", "An integrated oil major, so its earnings move with the crude price."),
         ("COP", "direct", "strong", "The largest US independent producer, so crude is most of its revenue."),
     ]},
    {"id": "fuel", "label": "Refined fuel", "kind": "subject", "category": "commodity",
     "horizon": "medium-term",
     "patterns": [r"\bdiesel\b", r"\bgasoline\b", r"\bjet fuel\b", r"\brefiner(?:y|ies|s)?\b",
                  r"\bfuel (?:prices?|bill|supply|exports?)\b"],
     "sectors": ["Energy"],
     "exposures": [
         ("MPC", "direct", "strong", "The largest US refiner by capacity."),
         ("VLO", "direct", "strong", "Among the largest US refiners."),
         ("PSX", "direct", "moderate", "A refiner with large chemicals and pipeline businesses."),
     ]},
    {"id": "gas", "label": "Natural gas and LNG", "kind": "subject", "category": "commodity",
     "horizon": "medium-term",
     "patterns": [r"\bnatural gas\b", r"\blng\b", r"\bgas (?:prices?|supply|exports?)\b", r"\bhenry hub\b"],
     "sectors": ["Energy", "Utilities"],
     "exposures": [
         ("LNG", "direct", "strong", "The largest US exporter of liquefied natural gas."),
         ("EQT", "direct", "strong", "Among the largest US natural-gas producers."),
     ]},
    {"id": "power", "label": "Power and grids", "kind": "subject", "category": "government",
     "horizon": "long-term",
     "patterns": [r"\belectricity\b", r"\bpower grids?\b", r"\bgrid\b", r"\bnuclear power\b",
                  r"\butilit(?:y|ies)\b"],
     "sectors": ["Utilities"]},
    {"id": "clean", "label": "Clean energy and EVs", "kind": "subject", "category": "government",
     "horizon": "long-term",
     "patterns": [r"\belectric vehicles?\b", r"\bevs?\b", r"\bsolar\b", r"\bwind (?:power|farms?|energy)\b",
                  r"\brenewables?\b", r"\brenewable energy\b", r"\bclean energy\b"],
     "sectors": ["Utilities", "Consumer Discretionary"],
     "exposures": [
         ("FSLR", "direct", "strong", "The largest US maker of solar panels."),
         ("NEE", "direct", "moderate", "The largest US developer of wind and solar power."),
         ("TSLA", "direct", "moderate", "The largest US maker of electric vehicles."),
     ]},
    {"id": "autos", "label": "Autos", "kind": "subject", "category": "regulatory",
     "horizon": "long-term",
     "patterns": [r"\bautos?\b", r"\bcarmakers?\b", r"\bautomakers?\b", r"\bfuel economy\b",
                  r"\bemissions standards?\b", r"\bvehicles?\b"],
     "sectors": ["Consumer Discretionary"],
     "exposures": [
         ("GM", "direct", "moderate", "The largest US carmaker by sales."),
         ("F", "direct", "moderate", "A US carmaker whose profit rests on trucks and SUVs."),
         ("STLA", "direct", "moderate", "Owns Jeep, Ram and Chrysler, and sells heavily in the US."),
     ]},
    {"id": "steel", "label": "Steel and aluminium", "kind": "subject", "category": "commodity",
     "horizon": "long-term",
     "patterns": [r"\bsteel\b", r"\balumin(?:i)?um\b"],
     "sectors": ["Materials"],
     "exposures": [
         ("NUE", "direct", "strong", "The largest US steelmaker."),
         ("STLD", "direct", "moderate", "A US steelmaker."),
         ("AA", "direct", "moderate", "The largest US aluminium producer."),
     ]},
    {"id": "minerals", "label": "Critical minerals", "kind": "subject", "category": "commodity",
     "horizon": "long-term",
     "patterns": [r"\bcritical minerals?\b", r"\brare earths?\b", r"\blithium\b", r"\bcopper\b",
                  r"\bnickel\b", r"\bcobalt\b", r"\buranium\b"],
     "sectors": ["Materials"],
     "exposures": [
         ("MP", "direct", "strong", "Runs the only large rare-earth mine in the US."),
         ("ALB", "direct", "strong", "Among the largest lithium producers."),
         ("FCX", "direct", "strong", "Among the largest listed copper miners."),
     ]},
    {"id": "gold", "label": "Gold", "kind": "subject", "category": "commodity",
     "horizon": "medium-term",
     "patterns": [r"\bgold (?:prices?|futures|rally|record)\b", r"\bbullion\b", r"\bprecious metals?\b"],
     "sectors": ["Materials"],
     "exposures": [("NEM", "direct", "strong", "The largest gold miner, so its revenue moves with gold.")]},
    {"id": "chips", "label": "Semiconductors", "kind": "subject", "category": "technology",
     "horizon": "long-term",
     "patterns": [r"\bsemiconductors?\b", r"(?<!blue )(?<!potato )\bchips?\b", r"\bchipmakers?\b",
                  r"\bgpus?\b"],
     "sectors": ["Technology"],
     "exposures": [
         ("NVDA", "direct", "strong", "The largest maker of AI accelerators, the chips export rules restrict most."),
         ("TSM", "direct", "strong", "Manufactures most of the world's leading-edge chips."),
         ("AMD", "direct", "moderate", "The other large supplier of data-centre GPUs."),
         ("AMAT", "direct", "moderate", "The largest US maker of chip-making equipment."),
     ]},
    {"id": "ai", "label": "Artificial intelligence", "kind": "subject", "category": "technology",
     "horizon": "long-term",
     "patterns": [r"\bai\b", r"\bartificial intelligence\b", r"\bdata cent(?:er|re)s?\b",
                  r"\bchatbots?\b", r"\bopenai\b", r"\banthropic\b"],
     "sectors": ["Technology", "Communication Services"],
     "exposures": [
         ("NVDA", "direct", "moderate", "Sells most of the chips AI models are trained and run on."),
         ("MSFT", "indirect", "moderate", "Runs one of the largest AI clouds and is OpenAI's largest backer."),
     ]},
    {"id": "drugs", "label": "Drugs and health care", "kind": "subject", "category": "regulatory",
     "horizon": "medium-term",
     "patterns": [r"\bfda\b", r"\bdrugs?\b", r"\bdrugmakers?\b", r"\bpharma(?:ceuticals?)?\b",
                  r"\bmedicare\b", r"\bmedicaid\b", r"\bvaccines?\b", r"\btreatments?\b",
                  r"\bclinical trials?\b", r"\bbiotech\b", r"\bobesity\b"],
     "sectors": ["Health Care"]},
    {"id": "tobacco", "label": "Tobacco and nicotine", "kind": "subject", "category": "regulatory",
     "horizon": "long-term",
     "patterns": [r"\btobacco\b", r"\bcigarettes?\b", r"\bnicotine\b", r"\bvap(?:e|es|ing)\b",
                  r"\bmenthol\b", r"\bpmta\b"],
     "sectors": ["Consumer Staples"],
     "exposures": [
         ("MO", "direct", "strong", "Sells Marlboro in the US, the largest US cigarette maker."),
         ("PM", "direct", "strong", "Sells Marlboro outside the US and owns Zyn and IQOS."),
         ("BTI", "direct", "moderate", "Owns Reynolds American, the second US cigarette maker."),
     ]},
    {"id": "banks", "label": "Banking", "kind": "subject", "category": "regulatory",
     "horizon": "medium-term",
     # Not a central bank, the World Bank or a "Bank of" anything: those are
     # actors or names, and the Bank of England is no read-through for JPMorgan.
     "patterns": [r"(?<!central )(?<!world )(?<!reserve )\bbanks?\b(?! of )", r"\bbanking\b",
                  r"\bcapital (?:rules?|requirements?)\b",
                  r"\bstress tests?\b", r"\bbasel\b", r"\bdeposits?\b"],
     "sectors": ["Financials"],
     "exposures": [
         ("JPM", "direct", "moderate", "The largest US bank."),
         ("BAC", "direct", "moderate", "The second-largest US bank."),
     ]},
    {"id": "crypto", "label": "Crypto and stablecoins", "kind": "subject", "category": "regulatory",
     "horizon": "medium-term",
     "patterns": [r"\bcrypto(?:currenc(?:y|ies))?\b", r"\bbitcoin\b", r"\bstablecoins?\b",
                  r"\bdigital assets?\b", r"\bblockchain\b"],
     "sectors": ["Financials"],
     "exposures": [
         ("COIN", "direct", "strong", "The largest US crypto exchange."),
         ("CRCL", "direct", "strong", "Issues USDC, the second-largest stablecoin."),
         ("HOOD", "direct", "moderate", "A brokerage with a large crypto trading business."),
     ]},
    {"id": "defence", "label": "Defence", "kind": "subject", "category": "government",
     "horizon": "long-term",
     "patterns": [r"\bdefen[cs]e\b", r"\bpentagon\b", r"\bnato\b", r"\bweapons\b", r"\bmunitions\b",
                  r"\bmissiles?\b"],
     "sectors": ["Industrials"],
     "exposures": [
         ("LMT", "direct", "strong", "The largest US defence contractor."),
         ("RTX", "direct", "moderate", "Makes missiles and missile-defence systems."),
         ("NOC", "direct", "moderate", "A US defence prime contractor."),
     ]},
    {"id": "airlines", "label": "Airlines", "kind": "subject", "category": "commodity",
     "horizon": "medium-term",
     "patterns": [r"\bairlines?\b", r"\bair travel\b", r"\bjet fuel\b"],
     "sectors": ["Industrials"],
     "exposures": [
         ("DAL", "indirect", "moderate", "Fuel is one of an airline's two largest costs."),
         ("UAL", "indirect", "moderate", "Fuel is one of an airline's two largest costs."),
     ]},
    {"id": "farm", "label": "Agriculture", "kind": "subject", "category": "commodity",
     "horizon": "medium-term",
     "patterns": [r"\bfarm(?:ers?|ing|land)?\b", r"\bcrops?\b", r"\bsoybeans?\b", r"\bcorn\b",
                  r"\bwheat\b", r"\bgrains?\b", r"\bpesticides?\b", r"\bfertili[sz]ers?\b",
                  r"\bagricultur(?:e|al)\b", r"\bdairy\b"],
     "sectors": ["Consumer Staples", "Materials"],
     "exposures": [
         ("ADM", "direct", "moderate", "Among the largest grain traders and processors."),
         ("DE", "indirect", "moderate", "The largest maker of farm equipment, so farm income is its demand."),
     ]},
    {"id": "housing", "label": "Housing", "kind": "subject", "category": "monetary-policy",
     "horizon": "medium-term",
     "patterns": [r"\bmortgages?\b", r"\bhousing\b", r"\bhome ?builders?\b", r"\bhome sales\b",
                  r"\bhomebuyers?\b"],
     "sectors": ["Real Estate", "Consumer Discretionary"],
     "exposures": [
         ("DHI", "indirect", "moderate", "The largest US homebuilder: rates decide how many buyers can afford a home."),
         ("LEN", "indirect", "moderate", "The second-largest US homebuilder."),
     ]},
    {"id": "rates", "label": "Bond yields", "kind": "subject", "category": "monetary-policy",
     "horizon": "medium-term",
     "patterns": [r"\btreasury yields?\b", r"\bbond yields?\b", r"\byields?\b", r"\b(?:2|5|10|30)-year\b",
                  r"\btreasuries\b"],
     "sectors": ["Financials", "Real Estate", "Utilities"]},
    {"id": "alcohol", "label": "Alcohol", "kind": "subject", "category": "commodity",
     "horizon": "medium-term",
     "patterns": [r"\balcohol\b", r"\bbeer\b", r"\bwine\b", r"\bspirits\b", r"\bwhisk(?:e)?y\b",
                  r"\bbourbon\b"],
     "sectors": ["Consumer Staples"],
     "exposures": [
         ("STZ", "direct", "moderate", "Imports Corona and Modelo, the largest US beer imports."),
         ("BF-B", "direct", "moderate", "Makes Jack Daniel's, and sells much of it abroad."),
     ]},
    {"id": "shipping", "label": "Shipping and supply chains", "kind": "subject", "category": "geopolitical",
     "horizon": "medium-term",
     "patterns": [r"\bshipping\b", r"\bfreight\b", r"\bsupply chains?\b", r"\bred sea\b", r"\bsuez\b",
                  r"\bpanama canal\b", r"\bports?\b"],
     "sectors": ["Industrials"],
     "exposures": [
         ("FDX", "indirect", "moderate", "A global parcel network, so freight disruption reaches its costs."),
         ("UPS", "indirect", "moderate", "A global parcel network, so freight disruption reaches its costs."),
     ]},
    {"id": "platforms", "label": "Big Tech", "kind": "subject", "category": "technology",
     "horizon": "long-term",
     "patterns": [r"\bbig tech\b", r"\btech giants?\b", r"\bsocial media\b", r"\bapp stores?\b",
                  r"\bsearch engine\b", r"\bonline advertising\b"],
     "sectors": ["Communication Services", "Technology"]},
]

THEME_BY_ID = {t["id"]: t for t in THEMES}
_COMPILED = [(t, [re.compile(p, re.I) for p in t["patterns"]]) for t in THEMES]
# Policy themes that say a government did something without saying about what.
_GENERIC = {"legislation", "fiscal", "regulation", "industrial"}
# The words a theme is named or found by. "gold" alone matches no pattern (the
# theme wants "gold prices"), and a reader typing it still means the theme.
_THEME_WORDS = {
    w for t in THEMES
    for w in re.findall(r"[a-z]{2,}", (t["label"] + " " + " ".join(
        re.sub(r"\\[bBdswDSW]", " ", p) for p in t["patterns"])).lower())}


def themes_in(text: str) -> List[Dict[str, Any]]:
    """The themes a text is about, in table order."""
    return [t for t, pats in _COMPILED if any(p.search(text or "") for p in pats)]


def is_theme_word(word: str) -> bool:
    """Whether a word is one the themes or actors are found by: "oil", "gold",
    "ai" and "fed", which are also tickers."""
    w = (word or "").strip().lower()
    if not w:
        return False
    return bool(themes_in(w)) or bool(actors_in(w)) or w in _THEME_WORDS


# -------------------------------------------------------- named companies
#
# Names as a story writes them. Matched with case, because "apple", "target"
# and "delta" are words; and the names that are ordinary words even with a
# capital (Visa, Target, Delta, United, Block, Ford, Arm, Lilly) only in the
# longer form a story uses for the company.
NAMES: Dict[str, str] = {
    "Apple": "AAPL", "Microsoft": "MSFT", "Nvidia": "NVDA", "NVIDIA": "NVDA", "Amazon": "AMZN",
    "Alphabet": "GOOGL", "Google": "GOOGL", "Meta Platforms": "META", "Meta": "META",
    "Facebook": "META", "Tesla": "TSLA", "Broadcom": "AVGO", "Oracle": "ORCL",
    "Netflix": "NFLX", "AMD": "AMD", "Advanced Micro Devices": "AMD", "Intel": "INTC",
    "Qualcomm": "QCOM", "Micron": "MU", "TSMC": "TSM", "Taiwan Semiconductor": "TSM",
    "Salesforce": "CRM", "Adobe": "ADBE", "IBM": "IBM", "Cisco": "CSCO", "Palantir": "PLTR",
    "Uber": "UBER", "Shopify": "SHOP", "CrowdStrike": "CRWD", "Palo Alto Networks": "PANW",
    "ServiceNow": "NOW", "Super Micro": "SMCI", "Supermicro": "SMCI", "Arista": "ANET",
    "Arm Holdings": "ARM", "Applied Materials": "AMAT", "Lam Research": "LRCX", "ASML": "ASML",
    "CoreWeave": "CRWV", "Robinhood": "HOOD", "Coinbase": "COIN", "PayPal": "PYPL",
    "MicroStrategy": "MSTR", "Circle Internet": "CRCL", "SoFi": "SOFI",
    "JPMorgan": "JPM", "JP Morgan": "JPM", "Goldman Sachs": "GS", "Goldman": "GS",
    "Morgan Stanley": "MS", "Bank of America": "BAC", "Citigroup": "C", "Wells Fargo": "WFC",
    "BlackRock": "BLK", "KKR": "KKR", "Blackstone": "BX", "Berkshire Hathaway": "BRK-B",
    "Berkshire": "BRK-B", "Visa Inc": "V", "Mastercard": "MA", "American Express": "AXP",
    "Walmart": "WMT", "Costco": "COST", "Target Corp": "TGT", "Home Depot": "HD", "Nike": "NKE",
    "Disney": "DIS", "McDonald's": "MCD", "Starbucks": "SBUX", "Coca-Cola": "KO",
    "PepsiCo": "PEP", "Procter & Gamble": "PG", "Eli Lilly": "LLY", "UnitedHealth": "UNH",
    "Johnson & Johnson": "JNJ", "Pfizer": "PFE", "Merck": "MRK", "AbbVie": "ABBV",
    "Novo Nordisk": "NVO", "Novo": "NVO", "Moderna": "MRNA", "Amgen": "AMGN", "Gilead": "GILD",
    "Bristol-Myers": "BMY", "AstraZeneca": "AZN", "Summit Therapeutics": "SMMT",
    "Exxon": "XOM", "ExxonMobil": "XOM", "Exxon Mobil": "XOM", "Chevron": "CVX",
    "ConocoPhillips": "COP", "Occidental": "OXY", "Shell": "SHEL", "BP": "BP",
    "Valero": "VLO", "Marathon Petroleum": "MPC", "Phillips 66": "PSX", "Cheniere": "LNG",
    "Boeing": "BA", "Caterpillar": "CAT", "GE Aerospace": "GE", "GE Vernova": "GEV",
    "Lockheed Martin": "LMT", "Lockheed": "LMT", "Raytheon": "RTX",
    "Northrop Grumman": "NOC", "Northrop": "NOC", "General Dynamics": "GD", "Honeywell": "HON",
    "Deere": "DE", "FedEx": "FDX", "Delta Air Lines": "DAL", "United Airlines": "UAL",
    "American Airlines": "AAL", "General Motors": "GM", "Ford Motor": "F", "Stellantis": "STLA",
    "Toyota": "TM", "Rivian": "RIVN", "Nucor": "NUE", "Alcoa": "AA", "Freeport-McMoRan": "FCX",
    "Newmont": "NEM", "Albemarle": "ALB", "MP Materials": "MP",
    "Cameco": "CCJ", "First Solar": "FSLR", "Enphase": "ENPH", "NextEra": "NEE",
    "Corteva": "CTVA", "Archer-Daniels-Midland": "ADM", "Bunge": "BG", "Nutrien": "NTR",
    "Lennar": "LEN", "D.R. Horton": "DHI", "Altria": "MO",
    "Philip Morris": "PM", "British American Tobacco": "BTI", "Constellation Brands": "STZ",
    "Diageo": "DEO", "Molson Coors": "TAP", "Verizon": "VZ", "AT&T": "T", "T-Mobile": "TMUS",
    "Comcast": "CMCSA", "Spotify": "SPOT", "Airbnb": "ABNB", "Booking Holdings": "BKNG",
    "Lululemon": "LULU", "Chipotle": "CMG", "GameStop": "GME", "Hasbro": "HAS", "Mattel": "MAT",
    "National Grid": "NGG", "Humana": "HUM", "CVS Health": "CVS",
}
# A name followed by one of these is not the company.
_NOT_THE_COMPANY = {
    "Amazon": r"\s+(?:rainforest|river|basin|deforestation|region)",
    "Apple": r"\s+(?:juice|pie|orchards?|cider)",
    "Oracle": r" of Omaha",
    "Shell": r"\s*(?:compan(?:y|ies)|corporations?|games?|shock|-shocked)",
}
# "Ex-Tesla team raises $12.5M" is not Tesla raising anything, and "Names
# Former ExxonMobil Executive to Board" is not Exxon naming anyone.
NOT_FORMER = r"(?<![A-Za-z0-9])(?<!Ex-)(?<!ex-)(?<!Former )(?<!former )"
_NAME_RES = [(name, sym, re.compile(NOT_FORMER + re.escape(name) + r"(?![A-Za-z0-9])"))
             for name, sym in sorted(NAMES.items(), key=lambda kv: -len(kv[0]))]
# An exchange-prefixed or cash-tagged symbol is the company naming itself.
_TICKER_IN_TEXT = re.compile(
    r"\((?:NASDAQ|Nasdaq|NYSE|NYSE American|NYSE Arca|NYSEAMERICAN)\s*:\s*([A-Z]{1,5}(?:[.\-][A-Z])?)\)"
    r"|(?<![A-Za-z0-9$])\$([A-Z]{1,5})\b")

# Private companies whose news reaches listed ones, and how. Public facts that
# stay true for years, labelled as the standard read-through.
STAKEHOLDERS: Dict[str, List[Tuple[str, str, str, str]]] = {
    "OpenAI": [("MSFT", "indirect", "moderate",
                "Microsoft is OpenAI's largest outside investor and its main cloud.")],
    "Anthropic": [
        ("AMZN", "indirect", "moderate", "Amazon is a major investor in Anthropic and its main cloud."),
        ("GOOGL", "indirect", "moderate", "Google is a major investor in Anthropic."),
    ],
}
_STAKE_RES = [(name, re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])"))
              for name in STAKEHOLDERS]


def named_companies(text: str) -> List[str]:
    """Tickers of the listed companies a text names, in the order it names them."""
    text = text or ""
    found: List[Tuple[int, str]] = []
    taken: List[Tuple[int, int]] = []
    for name, sym, rx in _NAME_RES:
        for m in rx.finditer(text):
            # Inside a longer name already matched ("Meta" in "Meta Platforms").
            if any(a <= m.start() < b for a, b in taken):
                continue
            guard = _NOT_THE_COMPANY.get(name)
            if guard and re.match(guard, text[m.end():], re.I):
                continue
            taken.append((m.start(), m.end()))
            found.append((m.start(), sym))
    for m in _TICKER_IN_TEXT.finditer(text):
        found.append((m.start(), m.group(1) or m.group(2)))
    out: List[str] = []
    for _at, sym in sorted(found):
        if sym not in out:
            out.append(sym)
    return out


def stakeholders_in(text: str) -> List[str]:
    return [name for name, rx in _STAKE_RES if rx.search(text or "")]


def named_positions(text: str) -> List[Tuple[int, str]]:
    """Where each company a text names first appears: listed ones by ticker,
    private ones by name."""
    text = text or ""
    found: Dict[str, int] = {}
    for name, sym, rx in _NAME_RES:
        for m in rx.finditer(text):
            guard = _NOT_THE_COMPANY.get(name)
            if guard and re.match(guard, text[m.end():], re.I):
                continue
            if sym not in found or m.start() < found[sym]:
                found[sym] = m.start()
            break
    for m in _TICKER_IN_TEXT.finditer(text):
        found.setdefault(m.group(1) or m.group(2), m.start())
    for name, rx in _STAKE_RES:
        m = rx.search(text)
        if m:
            found.setdefault(name, m.start())
    return sorted((at, sym) for sym, at in found.items())


def _first_name_at(text: str) -> int:
    """Where the first listed or stakeholder company in a text is named."""
    at = [m.start() for _n, _s, rx in _NAME_RES for m in [rx.search(text or "")] if m]
    at += [m.start() for _n, rx in _STAKE_RES for m in [rx.search(text or "")] if m]
    return min(at) if at else len(text or "") + 1


def _first_actor_at(text: str) -> int:
    at = [m.start() for _k, rx in _ACTORS for m in [rx.search(text or "")] if m]
    m = _US.search(text or "")
    if m:
        at.append(m.start())
    return min(at) if at else len(text or "") + 1


# ------------------------------------------------------------- one story

def read_story(story: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """What the rules make of one story: None, or why it is a catalyst.

    Decided on the headline. The summary adds themes and sectors to a story
    that already qualified and never qualifies one on its own: a passing
    mention in the second paragraph is not what a story is about.
    """
    title = str(story.get("title") or "").strip()
    if not title or is_noise(title, str(story.get("source") or "")):
        return None
    head_themes = themes_in(title)
    policy = [t for t in head_themes if t["kind"] == "policy"]
    subjects = [t for t in head_themes if t["kind"] == "subject"]
    actors = actors_in(title)
    companies = named_companies(title)
    private = stakeholders_in(title)
    acted = bool(_ACTION.search(title))

    # A headline led by a company it names is that company's event, whoever
    # else it mentions: "Shell backs $23 billion LNG Canada expansion" is
    # Shell's decision, not Canada's.
    company_led = bool(companies or private) and _first_name_at(title) < _first_actor_at(title)

    kind = None
    if _BENCHMARK.search(title) and _THRESHOLD.search(title):
        kind = "market"
    elif company_led and acted:
        kind = "company"
    elif actors and acted and (subjects or any(t["id"] not in _GENERIC for t in policy)):
        # A bill about college sports, an election pledge: a government acted,
        # on nothing a market prices. A bill or a budget counts when it is
        # about a subject.
        kind = "policy"
    if kind is None and (companies or private) and (acted or _MONEY.search(title)):
        # A company's own headline counts when it did something that outlasts
        # the day: the action rule, or money in the headline.
        kind = "company"
    if kind is None:
        return None

    both = themes_in(title + " " + str(story.get("summary") or ""))
    head_ids = {t["id"] for t in head_themes}
    return {"kind": kind, "actors": actors, "policy": policy, "subjects": subjects,
            "head_themes": head_themes,
            "more_themes": [t for t in both if t["id"] not in head_ids],
            "companies": companies, "private": private}


def _category_horizon(read: Dict[str, Any]) -> Tuple[str, str]:
    actors, policy, subjects = read["actors"], read["policy"], read["subjects"]
    if read["kind"] == "market":
        lead = subjects[0] if subjects else THEME_BY_ID["rates"]
        return lead["category"], "medium-term"
    if read["kind"] == "company":
        legal = ("court" in actors or "regulator" in actors) and any(
            t["id"] in ("antitrust", "regulation") for t in policy)
        tech = any(t["id"] in ("ai", "chips", "platforms") for t in subjects)
        commodity = any(t["category"] == "commodity" for t in subjects)
        return ("regulatory" if legal else "technology" if tech
                else "commodity" if commodity else "corporate"), "medium-term"
    specific = [t for t in policy if t["id"] not in _GENERIC]
    if specific:
        return specific[0]["category"], specific[0]["horizon"]
    if "regulator" in actors or "court" in actors:
        return "regulatory", "long-term"
    if "central-bank" in actors:
        # A framework or a rule from a central bank is supervision, not policy.
        if any(t["id"] == "regulation" for t in policy):
            return "regulatory", "long-term"
        return "monetary-policy", "medium-term"
    return "government", (policy[0]["horizon"] if policy else "long-term")


# ------------------------------------------------------- the library scan

NAMED_WHY = ("Named in the story. How much it matters to this company is not "
             "something the story says, so the strength is the default.")
MAX_COMPANIES = 8
_WORD = re.compile(r"[a-z0-9$%.]+")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "as", "at", "by",
         "with", "from", "is", "are", "be", "its", "it", "after", "over", "new", "says",
         "said", "will", "could", "may", "us", "u.s", "into", "than", "this", "that",
         "amid", "more", "what", "how", "here's"}


def _words(text: str) -> set:
    out = set()
    text = re.sub(r"['\u2019]s\b", "", (text or "").lower())
    # "$5.7bn" and "$5.7 billion" are one number.
    text = re.sub(r"(\d)\s?bn\b", r"\1 billion", text.replace("$", ""))
    for w in _WORD.findall(text):
        w = w.strip(".")
        if len(w) > 2 and w not in _STOP:
            out.add(w)
    return out


def same_event(a: str, b: str) -> bool:
    """Two headlines about one event: most of their words in common, or three
    of the words that carry it."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    shared = wa & wb
    return len(shared) / float(len(wa | wb)) >= 0.5 or len(shared) >= 3


def _companies(read: Dict[str, Any], text_named: Sequence[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()

    def add(sym: str, directness: str, strength: str, why: str) -> None:
        if sym not in seen:
            seen.add(sym)
            out.append({"ticker": sym, "directness": directness, "strength": strength, "why": why})

    for sym in text_named:
        add(sym, "direct", "moderate", NAMED_WHY)
    for name in read["private"]:
        for sym, directness, strength, why in STAKEHOLDERS[name]:
            add(sym, directness, strength, "Standard read-through: " + why)
    # The standard read-through is for events that reach an industry. One a
    # story aims at a company it names is about that company: two grain
    # traders under "Antitrust Case Against Corteva", or three steelmakers
    # under "Apple ordered to pay $5.7bn", would be noise. A headline that
    # names no subject takes the summary's: "import restrictions come into
    # force" says what they cover a sentence later.
    subjects = read["subjects"] or [t for t in read["more_themes"] if t["kind"] == "subject"]
    if read["kind"] != "company" and not read["companies"]:
        for theme in subjects:
            for sym, directness, strength, why in theme.get("exposures") or []:
                add(sym, directness, strength,
                    "Standard read-through for {}: {}".format(theme["label"].lower(), why))
    return out[:MAX_COMPANIES]


def _open(story: Dict[str, Any]) -> bool:
    return story.get("access") in ("open", "metered")


# Desk labels a feed puts in front of a headline, which are not part of it.
_PREFIX = re.compile(r"^(?:STAT\+|Exclusive|EXCLUSIVE|Breaking|BREAKING|Update|UPDATE|Market Chatter)"
                     r"(?: \d+)?:\s+")


def display_title(title: str) -> str:
    return _PREFIX.sub("", str(title or "")).strip()


def extract(stories: List[Dict[str, Any]],
            library: Optional[List[Dict[str, Any]]] = None,
            reachable: Optional[Callable[[Dict[str, Any]], bool]] = None) -> List[Dict[str, Any]]:
    """The scan's answer from rules, in the shape the model's took.

    Stories about one event become one catalyst citing all of them. The title
    and the summary are the lead story's own, because rules do not write
    prose, and the lead is cited first so the caller links the story the
    title came from. `library` is the model's signature; the caller knows a
    stored story by its URL.
    """
    reachable = reachable or _open
    groups: List[Dict[str, Any]] = []
    for story in stories:
        read = read_story(story)
        if read is None:
            continue
        title = str(story.get("title") or "")
        home = next((g for g in groups
                     if any(same_event(s["title"], title) for s in g["stories"])), None)
        if home is None:
            home = {"stories": [], "reads": []}
            groups.append(home)
        home["stories"].append(story)
        home["reads"].append(read)

    found: List[Dict[str, Any]] = []
    for g in groups:
        # The first report leads, the first a reader without a subscription
        # can open when there is one. A later story on the same event is more
        # often analysis of it than news.
        order = sorted(range(len(g["stories"])),
                       key=lambda i: str(g["stories"][i].get("published") or ""))
        lead_at = next((i for i in order if reachable(g["stories"][i])), order[0])
        order = [lead_at] + [i for i in order if i != lead_at]
        stories_in = [g["stories"][i] for i in order]
        reads = [g["reads"][i] for i in order]
        lead, read = stories_in[0], reads[0]
        category, horizon = _category_horizon(read)
        labels: List[str] = []
        sectors: List[str] = []
        for r in reads:
            for t in r["head_themes"] + r["more_themes"]:
                if t["label"] not in labels:
                    labels.append(t["label"])
                for sec in t.get("sectors") or []:
                    if sec not in sectors:
                        sectors.append(sec)
        text = " ".join(str(s.get("title") or "") + " " + str(s.get("summary") or "")
                        for s in stories_in)
        found.append({
            "story_ids": [s["id"] for s in stories_in if s.get("id")],
            "title": display_title(lead.get("title")),
            "summary": str(lead.get("summary") or "") or next(
                (str(s.get("summary") or "") for s in stories_in if s.get("summary")), ""),
            "category": category,
            "horizon": horizon,
            "themes": labels[:4],
            "sectors": sectors[:5],
            "companies": _companies(read, named_companies(text)),
            "rule": read["kind"],
        })
    return found


# ------------------------------------------------------------ one ticker

# The News tab's catalyst types, as the library's categories, horizons, and
# the factor each is filed under on the ticker panel.
_TYPE_CATEGORY = {
    "legislation": "government", "policy / supply chain": "government",
    "macro event": "monetary-policy", "legal / regulatory": "regulatory",
    "regulatory / clinical": "regulatory",
}
_TYPE_HORIZON = {
    "earnings": "short-term", "guidance": "short-term", "analyst action": "short-term",
    "short interest": "short-term", "legislation": "long-term", "legal / regulatory": "long-term",
    "policy / supply chain": "long-term", "M&A": "long-term",
}
TYPE_FACTOR = {
    "earnings": "Earnings and guidance", "guidance": "Earnings and guidance",
    "analyst action": "Analyst actions", "M&A": "Deals", "commercial deal": "Deals",
    "regulatory / clinical": "Regulatory and legal", "legal / regulatory": "Regulatory and legal",
    "capital return": "Capital return", "management change": "Management",
    "restructuring": "Restructuring", "short interest": "Short interest",
    "policy / supply chain": "Policy and macro", "legislation": "Policy and macro",
    "macro event": "Policy and macro", "product news": "Products",
}
_IMPORTANCE_STRENGTH = {"high": "strong", "medium": "moderate", "low": "weak"}

# 8-K items, as catalysts: the company's own classification of its news. Items
# not listed (exhibits, bylaw tidying, vote tallies) are not catalysts.
ITEM_RULES: Dict[str, Tuple[str, str, str, str, str]] = {
    # item: (what, factor, category, horizon, strength)
    "1.01": ("Material agreement signed", "Deals", "corporate", "medium-term", "moderate"),
    "1.02": ("Material agreement ended", "Deals", "corporate", "medium-term", "moderate"),
    "1.03": ("Bankruptcy or receivership", "Restructuring", "corporate", "long-term", "strong"),
    "1.05": ("Cybersecurity incident", "Regulatory and legal", "corporate", "medium-term", "moderate"),
    "2.01": ("Acquisition or disposal completed", "Deals", "corporate", "long-term", "strong"),
    "2.02": ("Results of operations", "Earnings and guidance", "corporate", "short-term", "strong"),
    "2.03": ("New debt obligation", "Capital return", "corporate", "medium-term", "weak"),
    "2.05": ("Exit or restructuring costs", "Restructuring", "corporate", "medium-term", "moderate"),
    "2.06": ("Material impairment", "Restructuring", "corporate", "medium-term", "moderate"),
    "3.01": ("Listing or compliance notice", "Regulatory and legal", "regulatory", "medium-term", "strong"),
    "4.01": ("Change of auditor", "Management", "corporate", "medium-term", "moderate"),
    "4.02": ("Earlier financials no longer reliable", "Regulatory and legal", "regulatory", "long-term",
             "strong"),
    "5.01": ("Change in control", "Deals", "corporate", "long-term", "strong"),
    "5.02": ("Director or officer change", "Management", "corporate", "medium-term", "moderate"),
    "7.01": ("Regulation FD disclosure", "Earnings and guidance", "corporate", "short-term", "weak"),
    "8.01": ("Other material event", "Company announcements", "corporate", "short-term", "weak"),
}
# The heaviest item names a filing that carries several.
_ITEM_ORDER = ["1.03", "4.02", "5.01", "2.01", "3.01", "2.02", "1.01", "1.02", "2.05",
               "2.06", "1.05", "5.02", "4.01", "7.01", "2.03", "8.01"]
FILING_WINDOW_DAYS = 120


def row_id(url: str, title: str) -> str:
    return hashlib.sha1(((url or "") + "|" + (title or "")).encode("utf-8")).hexdigest()[:16]


def _cap(kind: str) -> str:
    return kind[:1].upper() + kind[1:] if kind else kind


def company_rows(ticker: str, name: str, sector: str, items: Iterable[Dict[str, Any]],
                 today: date, basis: str = "headline",
                 classify: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
                 leads: Optional[Callable[[str], bool]] = None,
                 rule: bool = True) -> List[Dict[str, Any]]:
    """The stories about one company that carry a catalyst.

    `items` are stories already known to name the company, each with the
    News tab's catalyst types in `catalysts`. One counts when that taxonomy
    finds a catalyst in it above product chatter, which keeps this panel and
    the News tab agreeing about a headline, or when the library's own rule
    does: "Apple ordered to pay $5.7bn after losing vibration tech patent
    suit" names no type the News tab knows. Commentary never counts, whoever
    it names: "Why Nvidia stock jumped today" is not the reason it did.

    `classify` is the News tab's taxonomy, run on the headline alone: over
    headline and summary together it filed "Nvidia's record buyback shows
    chipmaker's stock is too cheap" under earnings on a word in the summary.
    `leads` says whether the company is the one the headline is about, which
    "Nio Slides 4% as Geely Takes 30% Stake in Nio Power Unit; XPeng Drops 4%,
    Tesla Slips" is not for Tesla. `rule` lets the library's rule qualify a
    story the taxonomy does not: on for the news desks, off for Yahoo's feed,
    which is mostly commentary written around a verb ("Elon Musk Wants To
    Build 20,000 Optimus Robots A Week").
    """
    rows: List[Dict[str, Any]] = []
    for a in items or []:
        if a.get("about_company") is False:
            continue
        title = display_title(a.get("title"))
        source = str(a.get("publisher") or a.get("source") or "")
        if not title or is_noise(title, source):
            continue
        if leads is not None and not leads(title):
            continue
        raw = classify(title) if classify is not None else (a.get("catalysts") or [])
        # The News tab files any headline with "chip" in it under policy and
        # supply chain. On a company's own panel that is a mention, not a
        # catalyst, unless the policy is in the headline too.
        cats = [c for c in raw if c.get("importance") in ("high", "medium")
                and (c.get("type") != "policy / supply chain" or _POLICY_WORDS.search(title))]
        read = read_story({"title": title, "summary": a.get("summary"), "source": source}) \
            if rule else None
        if not cats and read is None:
            continue
        if cats:
            kind = str(cats[0].get("type") or "")
            factor = TYPE_FACTOR.get(kind, "Company news")
            category = _TYPE_CATEGORY.get(kind, "corporate")
            horizon = _TYPE_HORIZON.get(kind, "medium-term")
            themes = [_cap(str(c.get("type") or "")) for c in cats][:3]
            strength = _IMPORTANCE_STRENGTH.get(cats[0].get("importance"), "moderate")
            why = "The story names this company and reads as {}.".format(kind)
        else:
            category, horizon = _category_horizon(read)
            factor = ("Regulatory and legal" if category == "regulatory"
                      else "Policy and macro" if read["kind"] in ("policy", "market")
                      else "Company events")
            themes = [t["label"] for t in read["head_themes"]][:3]
            strength = "moderate"
            why = "The story names this company, and the library's rule reads it as an event."
        rows.append({
            "id": row_id(a.get("url") or "", title),
            "event_date": str(a.get("published") or "")[:10] or today.isoformat(),
            "title": title,
            "summary": str(a.get("summary") or "")[:600],
            "category": category,
            "horizon": horizon,
            "themes": themes,
            "sectors": [sector] if sector else [],
            "factor": factor,
            "basis": basis,
            "companies": [{"ticker": ticker, "name": name, "directness": "direct",
                           "strength": strength, "why": why}],
            "source_url": a.get("url") or None,
            "source_name": source[:80] or None,
        })
    return rows


_POLICY_WORDS = re.compile(r"\btariffs?\b|\bexport (?:controls?|curbs?|bans?|restrictions?)\b"
                           r"|\bsanctions?\b|\bentity list\b", re.I)

# Where a story comes from, best first, for the one that stands for an event
# several outlets carried.
_BASIS_RANK = {"filing": 0, "wire": 1, "headline": 2}


def merge_events(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per event: the same verdict from BBC News, CNBC and Insider
    Monkey is one catalyst with three sources, not three catalysts. The row
    kept is a news desk's over Yahoo's feed, then the earliest, and the other
    outlets are named in `also`. Filings are never merged: each is its own."""
    groups: List[List[Dict[str, Any]]] = []
    for r in sorted(rows, key=lambda r: str(r.get("event_date") or "")):
        home = None
        if r.get("basis") in ("headline", "wire"):
            home = next((g for g in groups if g[0].get("basis") in ("headline", "wire")
                         and any(same_event(x["title"], r["title"]) for x in g)), None)
        if home is None:
            groups.append([r])
        else:
            home.append(r)
    out = []
    for g in groups:
        g.sort(key=lambda r: (_BASIS_RANK.get(r.get("basis"), 3), str(r.get("event_date") or "")))
        lead = dict(g[0])
        also = []
        for r in g[1:]:
            name = r.get("source_name") or ""
            if name and name != lead.get("source_name") and name not in also:
                also.append(name)
        if also:
            lead["also"] = also
        out.append(lead)
    return out


def filing_rows(ticker: str, name: str, sector: str, filings: Iterable[Dict[str, Any]],
                today: date) -> List[Dict[str, Any]]:
    """The company's 8-Ks from the last FILING_WINDOW_DAYS, by their items."""
    start = today - timedelta(days=FILING_WINDOW_DAYS)
    rows: List[Dict[str, Any]] = []
    for f in filings or []:
        if f.get("form") != "8-K":
            continue
        filed = str(f.get("filed") or "")
        try:
            if datetime.strptime(filed, "%Y-%m-%d").date() < start:
                continue
        except ValueError:
            continue
        items = [i.strip() for i in str(f.get("items") or "").split(",") if i.strip() in ITEM_RULES]
        if not items:
            continue
        items.sort(key=_ITEM_ORDER.index)
        what, factor, category, horizon, strength = ITEM_RULES[items[0]]
        title = "{} 8-K: {}".format(name or ticker, what)
        also = ["item {}, {}".format(i, ITEM_RULES[i][0]) for i in items[1:]]
        rows.append({
            "id": row_id(f.get("url") or "", title),
            "event_date": filed,
            "title": title,
            "summary": "Filed with the SEC on {} under item {}, {}{}.".format(
                filed, items[0], what, "; also " + "; ".join(also) if also else ""),
            "category": category,
            "horizon": horizon,
            "themes": [ITEM_RULES[i][0] for i in items][:4],
            "sectors": [sector] if sector else [],
            "factor": factor,
            "basis": "filing",
            "companies": [{"ticker": ticker, "name": name, "directness": "direct",
                           "strength": strength,
                           "why": "The company's own filing, item {} of Form 8-K.".format(items[0])}],
            "source_url": f.get("url") or None,
            "source_name": "SEC EDGAR",
        })
    return rows


def earnings_row(ticker: str, name: str, sector: str, when: Optional[str],
                 today: date) -> Optional[Dict[str, Any]]:
    """The next scheduled report, when the calendar has one ahead."""
    try:
        day = datetime.strptime(str(when or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    days = (day - today).days
    if days < 0 or days > 120:
        return None
    ahead = "today" if days == 0 else "tomorrow" if days == 1 else "in {} days".format(days)
    title = "{} reports earnings on {}".format(name or ticker, day.isoformat())
    return {
        "id": row_id("", title),
        "event_date": day.isoformat(),
        "title": title,
        "summary": ("The next scheduled report, {}, from the earnings calendar. A date "
                    "the company has not confirmed can move.").format(ahead),
        "category": "corporate",
        "horizon": "short-term",
        "themes": ["Scheduled report"],
        "sectors": [sector] if sector else [],
        "factor": "Earnings and guidance",
        "basis": "calendar",
        "upcoming": True,
        "companies": [{"ticker": ticker, "name": name, "directness": "direct",
                       "strength": "strong", "why": "Its own report."}],
        "source_url": None,
        "source_name": "Earnings calendar",
    }


# Yahoo's sector names, as the library's (the ones the scan tags with).
SECTOR_NAMES = {
    "Financial Services": "Financials", "Healthcare": "Health Care",
    "Consumer Cyclical": "Consumer Discretionary", "Consumer Defensive": "Consumer Staples",
    "Basic Materials": "Materials",
}


def library_sector(yahoo_sector: str) -> str:
    return SECTOR_NAMES.get(yahoo_sector or "", yahoo_sector or "")
