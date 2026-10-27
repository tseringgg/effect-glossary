The two page scripts as they were before the features TYPE_GROUPS, NARROW_NO_CUT, COLOUR_MODES and FLIP_FACES existed (tester.js and testerfilters.js; nothing else in reports/ changed except the new files
and the four flag lines in config.js). src/test_tester_features.py serves a flags-off export with these two files swapped in and checks the current scripts, with the flags off, draw the same page and
make the same requests. Not part of any export (src/ is never exported).
