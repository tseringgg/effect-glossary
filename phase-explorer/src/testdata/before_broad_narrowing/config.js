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
 *   DEFAULT_POPULARITY      true: the sort on group pages has "Most popular first" (the default for the card list; the EDHREC rank already in build/manual_index.json, unranked last), "Default order" (what was "Best match"),
 *                           "Mana value" and "Name"; the choice is remembered. Needs TESTER_FILTERS. "Might also fit" stays on its score order until a sort is chosen.
 *   ACTIVE_GROUP_HIGHLIGHT  true: the open group stays marked in the search results and the tree until another group opens.
 *   QUERY_MATCH_BLOCK       true: a group opened from a search row that matched by its description shows the cards whose own ability line has the query's words, above its list.
 *                           Each of these three adds no file and no request: absent or false means the page behaves, requests and exports exactly as before the flag existed.
 *   ABILITY_TYPE_PAGES      true: an "Ability types" area beside "Card types" (triggered, activated, static, replacement abilities, by trigger, cost and kind), in the left column and in the search.
 *                           Files: abilitypages.js/.css, build/ability_pages/index.json and one small file per page under build/ability_pages/p/. Filters and pages, never placements.
 *   ABILITY_TYPE_FILTERS    true: "Trigger", "Cost" and "Kind" rows in the filter bar (changes only testerfilters.js; needs TESTER_FILTERS and ABILITY_TYPE_PAGES).
 *                           Each of these two: absent or false means the page behaves, requests and exports exactly as before the flag existed.
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
  FLIP_FACES: true,
  DEFAULT_POPULARITY: true,
  ACTIVE_GROUP_HIGHLIGHT: true,
  QUERY_MATCH_BLOCK: true,
  ABILITY_TYPE_PAGES: true,
  ABILITY_TYPE_FILTERS: true
};
