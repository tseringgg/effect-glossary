tester.js, testerfilters.js and config.js as they were before the flags DEFAULT_POPULARITY, ACTIVE_GROUP_HIGHLIGHT and QUERY_MATCH_BLOCK existed, and the manifest of the export they gave
(the four earlier flags on). src/test_tester_popularity.py serves a flags-off export with these scripts swapped in and checks the current scripts, flags off, draw the same page and make the same
requests. Not part of any export (src/ is never exported).

2026-10-27: the reports/browse.html entry of dist_manifest_before.json was updated to the committed file at HEAD (f5c40d9). Commit f5c40d9 changed that file after this manifest was saved (the needCards load is now shared: 4 added lines, 1 removed, nothing else). No other entry was touched.
