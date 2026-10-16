# Vision eval report

Model `jev-1.14.0`, Claude `opus`. 38 locate cases (30 present), 8 which queries x 8 screens.

## Locate

| metric | jev_box | jev_zoom | claude |
|---|---|---|---|
| presence correct | 38/38 (100%) | (same) | 38/38 (100%) |
| click point inside target | 25/30 (83%) | 22/30 (73%) | 30/30 (100%) |
| mean IoU | 0.51 | 0.53 | 0.87 |
| mean latency | 0.22 s | +1 request | 4.67 s |
| mean input tokens / cost | 3991.68 tok | +1670.73 tok | $0.02 |

Marker verify (flag when < 0.5): flags 5/5 jev_box misses and 1/25 jev_box hits.

| case | jev hit | conf | verify | zoom hit | zoom conf | claude hit |
|---|---|---|---|---|---|---|
| shop-signin | True | 0.79 | 0.93 | True | 0.74 | True |
| shop-cart | True | 0.79 | 0.67 | True | 0.93 | True |
| shop-gear | False | 0.78 | 0.01 | False | 0.86 | True |
| shop-bell | False | 0.76 | 0.01 | True | 0.34 | True |
| shop-zebra | True | 0.56 | 0.99 | True | 0.67 | True |
| shop-buy2 | True | 0.58 | 0.99 | True | 0.96 | True |
| signup-terms | True | 0.87 | 0.92 | True | 0.86 | True |
| signup-cancel | False | 0.79 | 0.01 | True | 0.34 | True |
| signup-create | True | 0.92 | 0.99 | True | 0.86 | True |
| signup-pw | True | 0.85 | 0.99 | True | 0.85 | True |
| dash-refund | True | 0.48 | 0.75 | True | 0.72 | True |
| dash-export | True | 0.90 | 0.97 | True | 0.86 | True |
| dash-rev | True | 0.77 | 0.99 | True | 0.70 | True |
| orders-edit103 | True | 0.67 | 0.97 | False | 0.31 | True |
| orders-del102 | True | 0.65 | 0.35 | False | 0.37 | True |
| orders-bulk | True | 0.95 | 0.96 | True | 0.95 | True |
| settings-sms | True | 0.84 | 0.98 | False | 0.39 | True |
| settings-billing | False | 0.58 | 0.00 | False | 0.34 | True |
| settings-save | True | 0.94 | 0.99 | True | 0.94 | True |
| modal-close | True | 0.76 | 0.93 | True | 0.90 | True |
| modal-archive | True | 0.87 | 0.86 | True | 0.47 | True |
| modal-keep | True | 0.87 | 0.98 | True | 0.96 | True |
| mhome-fab | True | 0.92 | 0.99 | True | 0.95 | True |
| mhome-search | True | 0.26 | 0.99 | True | 0.90 | True |
| mhome-profile | False | 0.23 | 0.00 | False | 0.20 | True |
| mhome-pic | True | 0.94 | 0.98 | True | 0.93 | True |
| mset-air | True | 0.76 | 0.99 | False | 0.58 | True |
| mset-bt | True | 0.81 | 0.99 | False | 0.26 | True |
| mset-signout | True | 0.91 | 0.99 | True | 0.91 | True |
| mset-wifi | True | 0.91 | 0.98 | True | 0.93 | True |

| absent case | jev presence | claude presence |
|---|---|---|
| shop-absent | 0.010 | False |
| signup-absent | 0.010 | False |
| dash-absent | 0.010 | False |
| orders-absent | 0.010 | False |
| settings-absent | 0.010 | False |
| modal-absent | 0.010 | False |
| mhome-absent | 0.070 | False |
| mset-absent | 0.010 | False |

## Which

Per (query, screen) pair correct: Jev 64/64, Claude 64/64. Jev top-1 (or no_match) correct: 8/8 (100%). Claude mean cost per query $0.10.

| query | gold | jev >= 0.5 | claude |
|---|---|---|---|
| which-zebra | ['shop'] | ['shop'] | ['shop'] |
| which-create | ['signup'] | ['signup'] | ['signup'] |
| which-table | ['orders'] | ['orders'] | ['orders'] |
| which-toggle | ['m_settings', 'settings'] | ['m_settings', 'settings'] | ['m_settings', 'settings'] |
| which-dialog | ['modal'] | ['modal'] | ['modal'] |
| which-map | [] | [] | [] |
| which-cart | ['dash', 'modal', 'orders', 'shop', 'signup'] | ['dash', 'modal', 'orders', 'shop', 'signup'] | ['dash', 'modal', 'orders', 'shop', 'signup'] |
| which-checkbox | ['signup'] | ['signup'] | ['signup'] |
