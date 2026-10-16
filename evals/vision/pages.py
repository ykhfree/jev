"""Synthetic fixture screens for the vision eval. Every target carries a `data-t` id, so its
DOM bounding box is the ground truth. No real user data appears on any screen."""

ICON = {
    "cart": '<circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.7 13.4a2 2 0 0 0 2 1.6h9.7a2 2 0 0 0 2-1.6L23 6H6"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0"/>',
    "home": '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.3-4.3"/>',
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "trash": '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>',
    "close": '<path d="M18 6 6 18M6 6l12 12"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "chev": '<path d="M9 18l6-6-6-6"/>',
}


def icon(name, size=22):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round">{ICON[name]}</svg>')


CSS = """<style>
body{font-family:-apple-system,Helvetica,Arial;margin:0;color:#222;background:#fff}
header{display:flex;align-items:center;gap:24px;padding:14px 32px;border-bottom:1px solid #ddd}
nav a{margin-right:18px;color:#444;text-decoration:none}.sp{flex:1}
button{font:inherit;padding:9px 18px;border-radius:6px;border:1px solid #bbb;background:#fff;color:inherit}
.pri{background:#2563eb;color:#fff;border-color:#2563eb}.dan{background:#dc2626;color:#fff;border-color:#dc2626}
.ic{padding:6px;border:none;background:none}main{padding:28px 32px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}
.card{border:1px solid #e3e3e3;border-radius:8px;padding:12px}.thumb{height:120px;border-radius:6px}
input[type=text],input[type=password]{font:inherit;padding:8px;width:320px;border:1px solid #bbb;border-radius:6px;display:block;margin:6px 0 16px}
table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:10px 12px;border-bottom:1px solid #eee}
.tog{display:inline-block;width:44px;height:24px;border-radius:12px;background:#ccc;position:relative;vertical-align:middle}
.tog.on{background:#16a34a}.tog::after{content:"";position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:#fff}
.tog.on::after{left:23px}
</style>"""

HEADER = (
    '<header><b>Acme</b><nav><a href="#">Home</a><a href="#">Shop</a><a href="#">Blog</a></nav><span class="sp"></span>'
    f'<button class="ic" data-t="cart" aria-label="cart">{icon("cart")}</button>'
    f'<button class="ic" data-t="gear" aria-label="settings">{icon("gear")}</button>'
    f'<button class="ic" data-t="bell" aria-label="notifications">{icon("bell")}</button>'
    '<button data-t="signin">Sign in</button></header>'
)


def card(i, color, title, price):
    return (f'<div class="card"><div class="thumb" data-t="thumb{i}" style="background:{color}"></div>'
            f'<p>{title}</p><b>{price}</b><br><br><button class="pri" data-t="buy{i}">Add to cart</button></div>')


def order_row(n, name, status):
    return (f'<tr><td>#{n}</td><td>{name}</td><td>{status}</td>'
            f'<td><button data-t="edit{n}">Edit</button> '
            f'<button class="ic" data-t="del{n}" aria-label="delete">{icon("trash", 18)}</button></td></tr>')


def setting_row(t, label, on):
    return (f'<tr><td>{label}</td><td style="text-align:right">'
            f'<span class="tog{" on" if on else ""}" data-t="{t}"></span></td></tr>')


MOBILE_CSS = """<style>
body{font-family:-apple-system,Helvetica;margin:0;background:#f2f2f7;color:#111}
.bar{position:fixed;left:0;right:0;bottom:0;display:flex;justify-content:space-around;padding:10px 0 28px;background:#fff;border-top:1px solid #ddd}
.bar span{display:flex;flex-direction:column;align-items:center;font-size:11px;color:#666}
.top{padding:56px 20px 12px;font-size:30px;font-weight:700}
.fab{position:fixed;right:20px;bottom:100px;width:56px;height:56px;border-radius:28px;background:#2563eb;color:#fff;display:flex;align-items:center;justify-content:center}
.list{background:#fff;margin:0 16px;border-radius:12px}
.row{display:flex;align-items:center;padding:14px 16px;border-bottom:1px solid #eee}.row .sp{flex:1}
.tog{display:inline-block;width:50px;height:30px;border-radius:15px;background:#ccc;position:relative}
.tog.on{background:#34c759}.tog::after{content:"";position:absolute;top:2px;left:2px;width:26px;height:26px;border-radius:50%;background:#fff}
.tog.on::after{left:22px}
.post{background:#fff;margin:12px 16px;border-radius:12px;padding:12px}.pic{height:180px;border-radius:8px}
</style>"""


def tab(t, name, label):
    return f'<span data-t="{t}">{icon(name, 26)}{label}</span>'


def mrow(label, right, t=None):
    attr = f' data-t="{t}"' if t else ""
    return f'<div class="row"{attr}><span>{label}</span><span class="sp"></span>{right}</div>'


# name -> (viewport width, viewport height, device scale factor, html)
PAGES = {
    "shop": (1280, 800, 2, CSS + HEADER + '<main><h2>New arrivals</h2><div class="grid">'
             + card(1, "linear-gradient(135deg,#f97316,#facc15)", "Sunset lamp", "$49")
             + card(2, "linear-gradient(135deg,#0ea5e9,#22c55e)", "Ocean mug", "$15")
             + card(3, "#7c3aed", "Violet notebook", "$9")
             + card(4, "repeating-linear-gradient(45deg,#111 0 10px,#fff 10px 20px)", "Zebra scarf", "$32")
             + '</div></main>'),
    "signup": (1280, 800, 2, CSS + HEADER
               + '<main><h2>Create your account</h2><label>Email<input type="text" data-t="email" placeholder="you@example.com"></label>'
               '<label>Password<input type="password" data-t="pw"></label>'
               '<label><input type="checkbox" data-t="terms"> I agree to the terms</label><br><br>'
               '<button class="pri" data-t="create">Create account</button> <button data-t="cancel">Cancel</button></main>'),
    "dash": (1280, 800, 2, CSS + HEADER
             + '<main><h2>Dashboard</h2><div class="grid">'
             '<div class="card"><p>Revenue</p><h1 data-t="rev">$12,400</h1></div><div class="card"><p>Orders</p><h1>318</h1></div>'
             '<div class="card"><p>Refunds</p><h1 style="color:#dc2626" data-t="refund">7</h1></div><div class="card"><p>Visitors</p><h1>9,210</h1></div></div>'
             '<br><button data-t="export">Export CSV</button> <button class="pri" data-t="newrep">New report</button></main>'),
    "orders": (1280, 800, 2, CSS + HEADER
               + '<main><h2>Orders</h2><table><tr><th>No.</th><th>Customer</th><th>Status</th><th></th></tr>'
               + order_row(101, "Mina Park", "Paid") + order_row(102, "Leo Kim", "Refunded")
               + order_row(103, "Sara Choi", "Pending") + order_row(104, "Jun Lee", "Paid")
               + '</table><br><button class="dan" data-t="bulkdel">Delete selected</button></main>'),
    "settings": (1280, 800, 2, CSS.replace("background:#fff}", "background:#111827;color:#e5e7eb}", 1)
                 + "<style>button{background:#1f2937;border-color:#4b5563}</style>"
                 + '<main><h2>Settings</h2><div style="display:flex;gap:8px;margin-bottom:20px">'
                 '<button data-t="tab_general">General</button><button class="pri" data-t="tab_privacy">Privacy</button>'
                 '<button data-t="tab_billing">Billing</button></div><table style="width:560px">'
                 + setting_row("tog_email", "Email notifications", True) + setting_row("tog_sms", "SMS notifications", False)
                 + setting_row("tog_track", "Usage tracking", True)
                 + '</table><br><button class="pri" data-t="save">Save changes</button></main>'),
    "modal": (1280, 800, 2, CSS + HEADER
              + '<main><h2>Projects</h2><p>Three projects in this workspace.</p></main>'
              '<div style="position:fixed;inset:0;background:rgba(0,0,0,.45)"></div>'
              '<div style="position:fixed;left:440px;top:240px;width:400px;background:#fff;border-radius:10px;padding:24px">'
              f'<button class="ic" data-t="mclose" aria-label="close" style="position:absolute;right:12px;top:12px">{icon("close")}</button>'
              '<h3>Archive project?</h3><p>You can restore it later from Settings.</p><br>'
              '<button data-t="mkeep">Keep</button> <button class="dan" data-t="marchive">Archive</button></div>'),
    "m_home": (390, 844, 3, MOBILE_CSS
               + '<div class="top">Feed</div>'
               '<div class="post"><div class="pic" data-t="mpic1" style="background:linear-gradient(#60a5fa,#fde68a)"></div><p>Beach day</p></div>'
               '<div class="post"><div class="pic" style="background:#065f46"></div><p>Forest walk</p></div>'
               f'<div class="fab" data-t="mfab">{icon("plus", 28)}</div>'
               '<div class="bar">' + tab("mtab_home", "home", "Home") + tab("mtab_search", "search", "Search")
               + tab("mtab_profile", "user", "Profile") + '</div>'),
    "m_settings": (390, 844, 3, MOBILE_CSS
                   + '<div class="top">Settings</div><div class="list">'
                   + mrow("Wi-Fi", f'<span style="color:#888">Home-5G</span>{icon("chev", 18)}', "mwifi")
                   + mrow("Bluetooth", '<span class="tog on" data-t="mtog_bt"></span>')
                   + mrow("Airplane mode", '<span class="tog" data-t="mtog_air"></span>')
                   + mrow("Notifications", icon("chev", 18), "mnotif")
                   + '</div><br><div class="list">' + mrow('<span style="color:#dc2626">Sign out</span>', "", "msignout")
                   + '</div>'),
}

# (id, page, target data-t or None when absent, description of what to find)
LOCATE_CASES = [
    ("shop-signin", "shop", "signin", "the 'Sign in' button"),
    ("shop-cart", "shop", "cart", "the shopping cart icon button"),
    ("shop-gear", "shop", "gear", "the settings (gear) icon button"),
    ("shop-bell", "shop", "bell", "the notification bell icon button"),
    ("shop-zebra", "shop", "thumb4", "the product image with black and white zebra stripes"),
    ("shop-buy2", "shop", "buy2", "the 'Add to cart' button of the Ocean mug product"),
    ("shop-absent", "shop", None, "the 'Checkout' button"),
    ("signup-terms", "signup", "terms", "the checkbox for agreeing to the terms"),
    ("signup-cancel", "signup", "cancel", "the 'Cancel' button"),
    ("signup-create", "signup", "create", "the 'Create account' button"),
    ("signup-pw", "signup", "pw", "the password input field"),
    ("signup-absent", "signup", None, "the product thumbnail image of a shopping cart item"),
    ("dash-refund", "dash", "refund", "the number shown in red"),
    ("dash-export", "dash", "export", "the 'Export CSV' button"),
    ("dash-rev", "dash", "rev", "the revenue amount"),
    ("dash-absent", "dash", None, "the 'Delete account' button"),
    ("orders-edit103", "orders", "edit103", "the 'Edit' button in the row of order #103"),
    ("orders-del102", "orders", "del102", "the delete (trash can) icon in the row of order #102"),
    ("orders-bulk", "orders", "bulkdel", "the red 'Delete selected' button"),
    ("orders-absent", "orders", None, "the pagination 'Next page' button"),
    ("settings-sms", "settings", "tog_sms", "the toggle switch for SMS notifications"),
    ("settings-billing", "settings", "tab_billing", "the 'Billing' tab"),
    ("settings-save", "settings", "save", "the 'Save changes' button"),
    ("settings-absent", "settings", None, "the profile photo upload area"),
    ("modal-close", "modal", "mclose", "the close (X) button of the dialog"),
    ("modal-archive", "modal", "marchive", "the 'Archive' button in the dialog"),
    ("modal-keep", "modal", "mkeep", "the 'Keep' button in the dialog"),
    ("modal-absent", "modal", None, "the 'Delete forever' button"),
    ("mhome-fab", "m_home", "mfab", "the floating '+' action button"),
    ("mhome-search", "m_home", "mtab_search", "the Search tab in the bottom tab bar"),
    ("mhome-profile", "m_home", "mtab_profile", "the Profile tab in the bottom tab bar"),
    ("mhome-pic", "m_home", "mpic1", "the photo of the 'Beach day' post"),
    ("mhome-absent", "m_home", None, "the camera shutter button"),
    ("mset-air", "m_settings", "mtog_air", "the toggle switch for Airplane mode"),
    ("mset-bt", "m_settings", "mtog_bt", "the toggle switch for Bluetooth"),
    ("mset-signout", "m_settings", "msignout", "the 'Sign out' row"),
    ("mset-wifi", "m_settings", "mwifi", "the Wi-Fi row"),
    ("mset-absent", "m_settings", None, "the 'Delete account' row"),
]

# (id, description, pages that show it); an empty set means no screen shows it
WHICH_CASES = [
    ("which-zebra", "a product image with black and white zebra stripes", {"shop"}),
    ("which-create", "a 'Create account' button", {"signup"}),
    ("which-table", "a table listing customer orders", {"orders"}),
    ("which-toggle", "a toggle switch", {"settings", "m_settings"}),
    ("which-dialog", "a confirmation dialog", {"modal"}),
    ("which-map", "a map", set()),
    # harder: on most screens, and a near miss (toggles and checkboxes look alike at a glance)
    ("which-cart", "a shopping cart icon", {"shop", "signup", "dash", "orders", "modal"}),
    ("which-checkbox", "a checkbox", {"signup"}),
]
