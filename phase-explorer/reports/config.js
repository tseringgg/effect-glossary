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
 *   BROAD_NARROWING         true: the first level of "Narrow by group" is 15 topics (Card draw, Counters, Tokens, ...), each with a dropdown of its specific groups; the flat chips are behind "Show all groups".
 *                           Topics are filters, never placements. Needs TESTER_FILTERS and NARROW_NO_CUT. Adds one data file, build/buckets/map.json (src/build_buckets.py); changes only testerfilters.js.
 *                           Absent or false means the page behaves, requests and exports exactly as before the flag existed.
 *   MODAL_ABILITIES         true: the large card view gets an "Abilities" block under "In these groups": the ability pages the card is on (triggered, activated, static, replacement) as chips, each with the card's own line,
 *                           and its keyword abilities as chips to the keyword pages. Needs ABILITY_TYPE_PAGES; follows the Flip control when FLIP_FACES is on. Files: modalabilities.js/.css and
 *                           build/ability_pages/cards.json (src/build_ability_cards.py), read the first time a card opens. Filters and links, never placements.
 *                           Absent or false means the page behaves, requests and exports exactly as before the flag existed.
 *   PERSIST_FILTERS         true: colour, colour match, type and mana value stay on when another group opens (this browser tab only; sort keeps its own memory). Narrowing, Subtype and Trigger/Cost/Kind start
 *                           empty on each group. A line over the bar names the kept filters with "Clear all"; an empty list says so; a pinned card the filters hide says which. Needs TESTER_FILTERS; changes only
 *                           testerfilters.js. Filters are views, never placements.
 *   COLOUR_IDENTITY         true: a "Based on" switch under the colour pips, Card colour | Colour identity (default identity, remembered). Identity is Scryfall's colour identity; the four colour modes apply to it.
 *                           Needs TESTER_FILTERS. One data file, build/colour_identity/cards.json (src/build_colour_identity.py), requested once when the filter code loads; changes only testerfilters.js.
 *                           Each of these two: absent or false means the page behaves, requests and exports exactly as before the flag existed.
 *   SEARCH_FIXES            true: the group search is ranked and laid out with six fixes (reports/groupsearch.js, reports/tester.js; no data file, no request): a hand-defined group's row says how many cards are placed
 *                           in it by hand, and one with none ranks after every group that has members unless the query is its name or alias; a longer word that only begins with a typed whole word (flash ->
 *                           Flashback) ranks after the whole-word matches, and a typed word that is itself a group-name word is not also tried as its stem ("cycling" no longer reaches Cyclops; "cycl" still reaches
 *                           Cycling); groups whose only match is a description that is one member's quoted card line sit in one collapsed row; a list of more than 10 is two or three headed blocks of 10 with an
 *                           honest count. Presentation and ranking only. Absent or false means the search behaves, requests and exports exactly as before the flag existed.
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
  ABILITY_TYPE_FILTERS: true,
  BROAD_NARROWING: true,
  MODAL_ABILITIES: true,
  PERSIST_FILTERS: true,
  COLOUR_IDENTITY: true,
  SEARCH_FIXES: true
};
