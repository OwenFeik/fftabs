"""
Script to query open Firefox tabs based on a search string. Tabs returned might
be slightly out of date as they're loaded from the session store file on disk.
"""

import difflib
import json
import os
import urllib.parse

import lz4.block

# Based on: https://gist.github.com/snorey/3eaa683d43b0e08057a82cf776fd7d83
def read_jsonlz4(path):
    """Load .jsonlz4 file as JSON."""

    with open(path, "rb") as f:
        f.read(8)  # file header
        data = f.read()
        text = lz4.block.decompress(data)
    return json.loads(text)


def tab_info(data):
    """From a sessionstore JSON file, return a list of tabs [(title, url)]."""

    tabs = []
    for window in data["windows"]:
        for tab in window["tabs"]:
            for entry in tab["entries"]:
                tabs.append((entry["title"], entry["url"]))
    return tabs


def diff_value(query, title, url):
    """Sum of difflib ratios for title and various url parts."""

    parts = urllib.parse.urlparse(url)

    matcher = difflib.SequenceMatcher()
    matcher.set_seq1(query)

    strings = [title, url, parts.hostname, parts.path]

    total = 0
    for string in strings:
        if string:
            matcher.set_seq2(string)
            total += matcher.ratio()

    return total


def value(query, tab):
    """A numeric closeness score for a given query, pair."""

    MIN_LENGTH = 3  # Minimum exact string match length.
    EXACT_VALUE = 3  # Score for finding an exact match.
    RATIO_COEFF = 1  # Multiplied by diff_value result.

    (title, url) = tab

    query = query.lower()
    title = title.lower()
    url = url.lower()

    total = 0

    if len(query) >= MIN_LENGTH:
        if query in title:
            total += EXACT_VALUE
        if query in url:
            total += EXACT_VALUE

    total += diff_value(query, title, url) * RATIO_COEFF

    return total


def suggest_tabs(tabs, query, nmax=10):
    """Suggest tabs from data which match query well."""

    THRESHOLD = 1.5  # Minimum value to return.

    return sorted(
        filter(lambda tab: value(query, tab) > THRESHOLD, tabs),
        key=lambda tab: -value(query, tab),
    )[:nmax]


def session_files():
    """Returns a list of discovered sessionstore files. Windows only."""

    FILENAME = "sessionstore.jsonlz4"
    FALLBACK = "sessionstore-backups/recovery.jsonlz4"

    if os.name == "nt":
        profile_folder = os.path.join(
            os.getenv("APPDATA"), "Mozilla", "Firefox", "Profiles"
        )
    else:
        return []

    files = []
    for profile in os.listdir(profile_folder):
        primary = os.path.join(profile_folder, profile, FILENAME)
        if os.path.isfile(primary):
            files.append(primary)

        fallback = os.path.join(profile_folder, profile, FALLBACK)
        if os.path.isfile(fallback):
            files.append(fallback)

    return files


if __name__ == "__main__":
    import sys

    tabs = set()
    for file in session_files():
        data = read_jsonlz4(file)
        tabs.update(tab_info(data))

    if len(sys.argv) > 1:
        query = sys.argv[1]
        suggested = suggest_tabs(tabs, query)
    else:
        suggested = tabs

    for (i, tab) in enumerate(suggested, 1):
        print(f"[{i}]", tab)