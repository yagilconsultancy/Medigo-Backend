"""Block passwords that are on well-known breach lists or trivially guessable.

The length and character-class rules alone still allow "Password123!" or
"Qwerty12345!". This module catches those by reducing a password to its
"core" (lower case, common letter-for-symbol swaps undone, leading and
trailing digits and symbols removed) and checking that core against a small
built-in list, a few product words, the user's own email name, and runs of
repeated or sequential characters.

The list is deliberately small and kept in code so there is no file or
network dependency; it is a backstop, not a full breach-corpus check.
"""

import string

# Roughly the 300 most common passwords and base words from public breach
# compilations (SecLists / NCSC top lists), lower case.
_COMMON_PASSWORDS: frozenset[str] = frozenset(
    """
    123456 123456789 12345678 12345 1234567 1234567890 123123 111111 000000
    1234 123 654321 666666 121212 112233 123321 7777777 888888 999999 555555
    222222 333333 444444 159753 147258 147258369 789456 987654321 0987654321
    1q2w3e4r 1q2w3e4r5t 1q2w3e 1qaz2wsx qazwsx qwerty qwertyuiop qwerty123
    qwe123 asdfgh asdfghjkl asdf zxcvbn zxcvbnm azerty qwertz password
    passw0rd password1 password123 pass pass123 passwd pa55word p4ssword
    letmein welcome welcome1 welcome123 admin admin123 administrator root
    toor login guest master master123 changeme default secret secret123
    test test123 testing demo user user123 iloveyou iloveu loveyou lovely
    love monkey dragon shadow sunshine princess football baseball basketball
    soccer hockey superman batman spiderman ironman starwars pokemon
    trustno1 whatever freedom flower hello hello123 hellothere abc123
    abcdef abcdefg abcd1234 aa123456 a123456 a12345 q123456 zaq12wsx
    michael jennifer jessica ashley charlie daniel thomas jordan hunter
    killer tigger summer winter autumn spring computer internet access
    mustang ferrari porsche corvette harley yamaha nissan toyota honda
    maverick cheese cookie chocolate banana orange apple pepper ginger
    matrix nothing silver golden diamond hannah samantha amanda michelle
    nicole jasmine daniela andrea maria jordan23 buster soccer1 jordan1
    family friends forever blessed angel angels baby babygirl babyboy
    butterfly purple yellow rainbow ranger zxcvbnm123 qwertyui 123qwe
    123abc qwerty1 qwerty12 qwerty1234 password12 password1234 passwort
    motdepasse contrasena senha 123456a 123456q 1234qwer qwer1234 asd123
    asdf1234 zxc123 qazxsw qweasd qweasdzxc 1qazxsw2 q1w2e3r4 q1w2e3r4t5
    a1b2c3 a1b2c3d4 1a2b3c4d 11111111 00000000 12341234 11223344 12121212
    123654 1111 0000 2000 2020 2021 2022 2023 2024 2025 2026 1990 1991
    canada ontario toronto london newyork chicago america usa england
    football1 baseball1 superman1 batman1 princess1 sunshine1 monkey1
    dragon1 shadow1 master1 letmein1 welcome2 trustno1 iloveyou1
    loveme lovelove mylove sweety sweetie honey cutie beautiful
    jesus christ god faith heaven grace blessing lord
    pussy fuckyou fuckoff asshole bitch shit sex sexy
    michael1 robert david james john richard william joseph charles
    george thomas1 anthony matthew andrew joshua justin brandon tyler
    chelsea arsenal liverpool manchester barcelona realmadrid juventus
    lakers yankees cowboys steelers patriots raiders packers eagles
    mercedes bmw audi volkswagen chevrolet tesla
    computer1 internet1 samsung iphone google facebook youtube twitter
    instagram linkedin microsoft windows apple123 android
    office work company business money cash dollar
    health hospital doctor nurse medical medicine clinic patient
    driver rider ride taxi uber lyft transport
    letmein123 welcome1234 changeme123 temp temp123 temporary
    summer2024 summer2025 winter2024 winter2025 spring2025 fall2025
    january february march april may june july august september october
    november december monday tuesday friday sunday saturday
    zaq1zaq1 zaq1xsw2 !qaz2wsx 1qaz!qaz
    abcabc abc12345 aaaaaa aaaaaaaa abcdabcd
    """.split()
)

# Product and company words that are guessable by anyone attacking MediGo.
_BLOCKED_WORDS: tuple[str, ...] = (
    "password",
    "passw0rd",
    "medigo",
    "mediride",
    "qwerty",
    "letmein",
    "iloveyou",
)

_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
     "@": "a", "$": "s", "!": "i", "|": "l", "+": "t"}
)

_STRIP = string.digits + string.punctuation + " "

_SEQUENCES = (
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789012",
    "qwertyuiopasdfghjklzxcvbnm",
)


def _is_repeated(s: str) -> bool:
    """'aaaaaa', 'abcabcabc', '12121212' - a short unit repeated."""
    n = len(s)
    if n < 2:
        return False
    for size in range(1, n // 2 + 1):
        if n % size == 0 and s[:size] * (n // size) == s:
            return True
    return False


def _is_sequential(s: str) -> bool:
    """Whole string is one run up or down a keyboard/alphabet/digit row."""
    if len(s) < 4:
        return False
    for seq in _SEQUENCES:
        if s in seq or s in seq[::-1]:
            return True
    return False


def _cores(password: str) -> set[str]:
    lower = password.lower()
    candidates = {lower, lower.strip(_STRIP)}
    leet = lower.translate(_LEET)
    candidates.add(leet)
    candidates.add(leet.strip(_STRIP))
    # Strip after undoing swaps of letters only (keeps trailing digits off).
    candidates.add(lower.strip(_STRIP).translate(_LEET))
    return {c for c in candidates if c}


def is_common_password(password: str, email: str | None = None) -> bool:
    """True if the password is common, guessable or built from the email.

    Case-insensitive. ``email`` is optional; when given, a password that
    contains the email's local part (4+ characters) is treated as common.
    """
    if not password:
        return True

    lower = password.lower()
    cores = _cores(password)

    for core in cores:
        if core in _COMMON_PASSWORDS:
            return True
        if _is_repeated(core) or _is_sequential(core):
            return True

    # Whole password made of one repeated unit or one sequence.
    if _is_repeated(lower) or _is_sequential(lower):
        return True

    leet = lower.translate(_LEET)
    for word in _BLOCKED_WORDS:
        if word in lower or word in leet:
            return True

    if email and "@" in email:
        local = email.split("@", 1)[0].lower()
        # Ignore plus-addressing and dots: "jane.doe+x" -> also "janedoe".
        local = local.split("+", 1)[0]
        variants = {local, local.replace(".", "").replace("_", "").replace("-", "")}
        for v in variants:
            if len(v) >= 4 and (v in lower or v in leet):
                return True

    return False
