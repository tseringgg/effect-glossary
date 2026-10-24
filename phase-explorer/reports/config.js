/* Settings for the tester view of reports/browse.html (read only when ?dev=1 is absent). Edit this file; nothing else needs to change.
 *
 *   feedbackUrl  where "Report a problem" goes: a Discord invite, a form, an issue tracker. Replace the placeholder before the site is shared.
 *   prefill      "clipboard": the report (card, group, search, page address) is copied for the tester to paste into the channel; use this for Discord, which cannot take pre-filled fields.
 *                "query": the report is added to the address as ?title=...&body=..., for a form or issue tracker that accepts them (the parameter names are below).
 *   titleParam, bodyParam   the names used by "query".
 */
window.APP_CONFIG = {
  feedbackUrl: "https://discord.gg/DUwMhDCcMg",
  prefill: "clipboard",
  titleParam: "title",
  bodyParam: "body"
};
