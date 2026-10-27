/* Settings for the tester view of reports/browse.html (read only when ?dev=1 is absent). Edit this file; nothing else needs to change.
 *
 *   feedbackUrl  where "Report a problem" goes: a Discord invite, a form, an issue tracker. Replace the placeholder before the site is shared.
 *   prefill      "clipboard": the report (card, group, search, page address) is copied for the tester to paste into the channel; use this for Discord, which cannot take pre-filled fields.
 *                "query": the report is added to the address as ?title=...&body=..., for a form or issue tracker that accepts them (the parameter names are below).
 *   titleParam, bodyParam   the names used by "query".
 *   TESTER_FILTERS  true: group pages get a filter and sort bar (colour, type, mana value) and a "Narrow by group" row (reports/testerfilters.js and .css are loaded and exported).
 *                   false: neither file is requested or exported, and every other file is unchanged.
 *   TYPE_GROUPS     true: a page for every card type, supertype and subtype with 5 or more cards ("Card types" in the left column and in the search; a "Subtype" row in the filter bar). Files: typegroups.js/.css,
 *                   build/type_groups/index.json and members.json. They are filters and pages, never placements.
 *   NARROW_NO_CUT   true: "Narrow by group" needs 2 shared cards instead of 3 (a link adds the 1-card groups), orders by shared count then group size, folds chips that pick the same cards, shows 12 then
 *                   "Show more" up to 60, and always shows its row. Needs TESTER_FILTERS.
 *   COLOUR_MODES    true: colour match is Any of these (default) / Includes all / Only these / Not these. Needs TESTER_FILTERS.
 *   FLIP_FACES      true: a Flip control on the large card view; name search finds a card by either face; colour and type filters read both faces. Files: flipfaces.js/.css, build/faces/faces.json.
 *                   Each of these four: absent or false means the page behaves, requests and exports exactly as before the flag existed.
 */
window.APP_CONFIG = {
  feedbackUrl: "https://discord.gg/DUwMhDCcMg",
  prefill: "clipboard",
  titleParam: "title",
  bodyParam: "body",
  TESTER_FILTERS: true,
  TYPE_GROUPS: true,
  NARROW_NO_CUT: true,
  COLOUR_MODES: true,
  FLIP_FACES: true
};
