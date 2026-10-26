// Tamarack OS default Firefox preferences.
//
// These are *defaults* (pref, not lockPref): every one of them can be changed
// back in Firefox's own settings. They remove sponsored content and turn off
// optional data collection; they do not change the search engine, add
// extensions or block anything else.

// No sponsored shortcuts or sponsored stories on the New Tab page.
pref("browser.newtabpage.activity-stream.showSponsored", false);
pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);
pref("browser.newtabpage.activity-stream.showSponsoredCheckboxes", false);
pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);

// No sponsored suggestions in the address bar.
pref("browser.urlbar.suggest.quicksuggest.sponsored", false);
pref("browser.urlbar.sponsoredTopSites", false);

// No personalized extension/feature recommendations.
pref("browser.discovery.enabled", false);
pref("extensions.htmlaboutaddons.recommendations.enabled", false);
pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.addons", false);
pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.features", false);

// Optional telemetry, studies and usage pings start off (opt-in).
pref("datareporting.healthreport.uploadEnabled", false);
pref("datareporting.policy.dataSubmissionEnabled", false);
pref("toolkit.telemetry.enabled", false);
pref("app.shield.optoutstudies.enabled", false);
pref("app.normandy.enabled", false);
pref("browser.newtabpage.activity-stream.feeds.telemetry", false);
pref("browser.newtabpage.activity-stream.telemetry", false);
pref("dom.private-attribution.submission.enabled", false);
