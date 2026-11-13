import re

PLACE = re.compile(
    r"(?<!\w)(?:remote|hybrid|on-?site|usa?|u\.s\.?|united states|uk|united kingdom|canada|germany|spain|ireland|"
    r"france|india|emea|amer|americas|apac|latam|europe|australia|brazil|mexico|japan|netherlands|poland|"
    r"singapore|israel|portugal|sweden|nyc|new york|san francisco|sf|seattle|london|berlin|toronto|dublin|amsterdam|aarhus|copenhagen|stockholm|oslo|helsinki|paris|munich|zurich|madrid|barcelona|lisbon|warsaw|prague|vienna|milan|brussels|bangalore|bengaluru|hyderabad|pune|tokyo|seoul|sydney|melbourne|sao paulo|são paulo|mexico city|vancouver|montreal|austin|dallas|houston|boston|chicago|denver|atlanta|raleigh|portland|los angeles|san diego|miami|phoenix|washington|dc|korea|benelux|mena|asean|anz|nordics|dach)(?!\w)",
    re.IGNORECASE,
)
TAIL = re.compile(r"(?:\s*[-–—|/,]\s*|\s*\()([^-–—|/,()]*)\)?\s*$")  # last " - X", " | X", ", X", "(X)"


# Same job, different words per region. Used for the dedupe KEY only; displayed titles are untouched.
SYNONYMS = {"developer": "engineer", "engineering": "engineer", "sr": "senior"}


def _only_places(segment: str) -> bool:
    leftover = re.sub(r"(?<!\w)(?:and|or)(?!\w)|[\s&+.]", "", PLACE.sub("", segment), flags=re.IGNORECASE)
    return bool(segment.strip()) and not leftover


def role_key(title: str | None) -> str:
    t = (title or "").strip()
    while (m := TAIL.search(t)) and m.start() > 0 and _only_places(m.group(1)):
        t = t[: m.start()]  # drop a trailing location, repeat
    words = re.sub(r"[^a-z0-9+#]+", " ", t.lower()).split()  # punctuation-insensitive
    return " ".join(SYNONYMS.get(w, w) for w in words)
