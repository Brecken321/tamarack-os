.pragma library
// Icon and color role of each app bundle in bundles.toml, shared by the Apps
// page and the Welcome flow.

var bundles = {
    "gaming": ["applications-games", "neutral"],
    "communication": ["mail-message", "link"],
    "office": ["applications-office", "highlight"],
    "creator": ["camera-video", "visited"],
    "media": ["applications-multimedia", "negative"],
    "browsers": ["applications-internet", "link"],
    "development": ["applications-development", "visited"],
    "utilities": ["applications-utilities", "positive"]
};

function bundleIcon(id) {
    return (bundles[id] || ["applications-other"])[0];
}

// `theme` is Kirigami.Theme, so the colors follow the active color scheme.
function bundleTint(id, theme) {
    var role = (bundles[id] || [null, "highlight"])[1];
    return {
        "neutral": theme.neutralTextColor,
        "link": theme.linkColor,
        "visited": theme.visitedLinkColor,
        "negative": theme.negativeTextColor,
        "positive": theme.positiveTextColor,
        "highlight": theme.highlightColor
    }[role];
}
