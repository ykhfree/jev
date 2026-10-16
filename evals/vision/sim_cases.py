"""Cases for the `sim` suite: screens captured on the iPhone 17 simulator (iOS 27.0) by sim/UITests.
Fixture screens hold made-up data. `s_sysprefs` is the iOS Settings app with no signed-in account;
the simulator's system language is Korean, so its labels are Korean."""

SIM_SCREENS = ["s_signin", "s_inbox", "s_settings", "s_alert", "s_gallery", "s_sysprefs"]

# target -> (element type, identifier, label) in the dumped accessibility tree; None matches anything.
# A SwiftUI Toggle's frame covers its whole row, so toggle targets are described as rows.
SIM_TARGETS = {
    "s_signin": {
        "cancel": ("button", "cancel", None),
        "signin": ("button", "signin", None),
        "forgot": ("button", "forgot", None),
        "remember": ("switch", "remember", None),
        "password": ("secureTextField", "password", None),
    },
    "s_inbox": {
        "filter": ("button", "filter", None),
        "compose": ("button", "compose", None),
        "tab_search": ("button", None, "Search"),
        "tab_profile": ("button", None, "Profile"),
        "msg_sara": ("text", "msg_sara", None),
    },
    "s_settings": {
        "bluetooth": ("switch", "bluetooth", None),
        "increment": ("button", "fontsize-Increment", None),
        "decrement": ("button", "fontsize-Decrement", None),
        "seg_auto": ("button", None, "Auto"),
        "volume": ("slider", "volume", None),
    },
    "s_alert": {
        "alert_cancel": ("button", None, "Cancel"),
        "alert_delete": ("button", None, "Delete"),
    },
    "s_gallery": {
        "moon": ("image", "tile_moon", None),
        "paw": ("image", "tile_paw", None),
        "drop": ("image", "tile_drop", None),
    },
    "s_sysprefs": {
        "account": ("button", "com.apple.settings.primaryAppleAccount", None),
        "general": ("button", "com.apple.settings.general", None),
        "camera": ("button", "com.apple.settings.camera", None),
        "search_row": ("button", "com.apple.settings.search", None),
        "search_field": ("searchField", None, "검색"),
    },
}

# (id, screen, target or None when absent, description of what to find)
SIM_LOCATE_CASES = [
    ("s-signin-cancel", "s_signin", "cancel", "the 'Cancel' button"),
    ("s-signin-signin", "s_signin", "signin", "the 'Sign In' button"),
    ("s-signin-forgot", "s_signin", "forgot", "the 'Forgot password?' link"),
    ("s-signin-remember", "s_signin", "remember", "the 'Remember me' row with its switch"),
    ("s-signin-password", "s_signin", "password", "the password input field"),
    ("s-signin-absent", "s_signin", None, "the 'Sign in with Apple' button"),
    ("s-inbox-filter", "s_inbox", "filter", "the filter icon button in the top toolbar"),
    ("s-inbox-compose", "s_inbox", "compose", "the compose (pencil on a square) icon button"),
    ("s-inbox-tab-search", "s_inbox", "tab_search", "the Search tab in the bottom tab bar"),
    ("s-inbox-tab-profile", "s_inbox", "tab_profile", "the Profile tab in the bottom tab bar"),
    ("s-inbox-sara", "s_inbox", "msg_sara", "the message from Sara Choi"),
    ("s-inbox-absent", "s_inbox", None, "the 'Archive all' button"),
    ("s-settings-bluetooth", "s_settings", "bluetooth", "the Bluetooth row"),
    ("s-settings-increment", "s_settings", "increment", "the + (increment) button of the font size stepper"),
    ("s-settings-decrement", "s_settings", "decrement", "the - (decrement) button of the font size stepper"),
    ("s-settings-auto", "s_settings", "seg_auto", "the 'Auto' segment of the theme picker"),
    ("s-settings-volume", "s_settings", "volume", "the volume slider"),
    ("s-settings-absent", "s_settings", None, "the 'Sign out' button"),
    ("s-alert-cancel", "s_alert", "alert_cancel", "the 'Cancel' button in the alert"),
    ("s-alert-delete", "s_alert", "alert_delete", "the 'Delete' button in the alert"),
    ("s-alert-absent", "s_alert", None, "the 'Share' button"),
    ("s-gallery-moon", "s_gallery", "moon", "the sticker tile with a purple crescent moon"),
    ("s-gallery-paw", "s_gallery", "paw", "the sticker tile with a paw print"),
    ("s-gallery-drop", "s_gallery", "drop", "the sticker tile with a water drop"),
    ("s-gallery-absent", "s_gallery", None, "the sticker tile with a cat face"),
    ("s-sys-account", "s_sysprefs", "account", "the Apple Account row at the top"),
    ("s-sys-general", "s_sysprefs", "general", "the '일반' (General) row"),
    ("s-sys-camera", "s_sysprefs", "camera", "the '카메라' (Camera) row"),
    ("s-sys-search-row", "s_sysprefs", "search_row", "the '검색' (Search) settings row in the list"),
    ("s-sys-search-field", "s_sysprefs", "search_field", "the search field at the bottom of the screen"),
    ("s-sys-absent", "s_sysprefs", None, "the '배터리' (Battery) row"),
]

# (id, description, screens that show it); near misses: Search tab vs search field, toggle vs stepper
SIM_WHICH_CASES = [
    ("sim-which-alert", "an alert dialog", {"s_alert"}),
    ("sim-which-tabbar", "a bottom tab bar", {"s_inbox"}),
    ("sim-which-toggle", "a toggle switch", {"s_signin", "s_settings"}),
    ("sim-which-stepper", "a stepper with minus and plus buttons", {"s_settings"}),
    ("sim-which-heart", "a heart icon", {"s_gallery"}),
    ("sim-which-password", "a password field", {"s_signin"}),
    ("sim-which-searchfield", "a search text field", {"s_sysprefs"}),
    ("sim-which-map", "a map", set()),
]
