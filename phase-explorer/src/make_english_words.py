#!/usr/bin/env python3
"""One-off: write data/english_words.txt, the "standard English" word list the group search uses to decide that a typed word is real (and so never "corrected").

    pip install wordfreq            (MIT/Apache; not needed to build or run anything else)
    python src/make_english_words.py

The 40,000 most frequent English words in wordfreq's large list, lower case, letters only, 3 or more letters, apostrophes dropped (the same folding the search uses). The output is a plain input file
that is kept in the repo, so the build never needs wordfreq.
"""
import io
import os
import re

from wordfreq import top_n_list

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
words = sorted({re.sub("'", "", w) for w in top_n_list("en", 40000) if re.fullmatch(r"[a-z']{3,}", w)})
words = [w for w in words if len(w) >= 3]
with io.open(os.path.join(HERE, "data", "english_words.txt"), "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(words) + "\n")
print(len(words), "words")
