tester.js, testerfilters.js and config.js as they were before the flags DEFAULT_POPULARITY, ACTIVE_GROUP_HIGHLIGHT and QUERY_MATCH_BLOCK existed, and the manifest of the export they gave
(the four earlier flags on). src/test_tester_popularity.py serves a flags-off export with these scripts swapped in and checks the current scripts, flags off, draw the same page and make the same
requests. Not part of any export (src/ is never exported).
