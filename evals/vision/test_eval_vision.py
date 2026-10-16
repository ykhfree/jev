"""Offline tests for the vision eval harness: no Jev or Claude calls."""

import pytest

import eval_vision as ev
from pages import LOCATE_CASES, PAGES, WHICH_CASES


def box(left, top, right, bottom):
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def test_hit_uses_the_center_as_click_point():
    target = box(0.4, 0.4, 0.6, 0.6)
    assert ev.hit(box(0.45, 0.45, 0.55, 0.55), target)
    # covers the target but its center falls outside: a merged box over two buttons
    assert not ev.hit(box(0.0, 0.4, 0.6, 0.6), target)


def test_iou():
    a = box(0.0, 0.0, 0.5, 0.5)
    assert ev.iou(a, a) == pytest.approx(1.0)
    assert ev.iou(a, box(0.5, 0.5, 1.0, 1.0)) == 0.0
    assert ev.iou(a, box(0.25, 0.0, 0.75, 0.5)) == pytest.approx(1 / 3)


def test_zoom_region_grows_small_boxes_and_stays_inside_the_image():
    r = ev.zoom_region(box(0.95, 0.02, 0.98, 0.05))  # small icon in the top-right corner
    assert r["right"] == pytest.approx(1.0) and r["top"] == pytest.approx(0.0)
    assert r["right"] - r["left"] == pytest.approx(ev.ZOOM_MIN)
    big = ev.zoom_region(box(0.1, 0.4, 0.4, 0.5))
    assert big["right"] - big["left"] == pytest.approx(0.9)  # 3x a 0.3-wide box
    assert big["left"] == pytest.approx(0.0)  # shifted right to stay inside the image


def test_zoom_region_caps_at_the_whole_image():
    r = ev.zoom_region(box(0.1, 0.1, 0.9, 0.9))
    assert (r["left"], r["top"], r["right"], r["bottom"]) == pytest.approx((0, 0, 1, 1))


def test_to_full_inverts_the_crop():
    region = box(0.5, 0.2, 0.8, 0.6)
    full = ev.to_full(box(0.0, 0.5, 1.0, 1.0), region)
    assert (full["left"], full["top"], full["right"], full["bottom"]) == pytest.approx((0.5, 0.4, 0.8, 0.6))


def test_claude_size_stays_under_the_pixel_budget():
    w, h = ev.claude_size(2560, 1600)
    assert w * h <= ev.CLAUDE_MAX_PIXELS and w <= 1568
    assert ev.claude_size(800, 600) == (800, 600)


def test_parse_claude():
    assert ev.parse_claude('{"present": true, "box": [10, 20, 30, 40]}', 100, 200) == (
        True, box(0.1, 0.1, 0.3, 0.2))
    assert ev.parse_claude('Sure: {"present": false, "box": null}', 100, 100) == (False, None)
    assert ev.parse_claude("I cannot tell", 100, 100) == (None, None)
    assert ev.parse_claude('{"present": "yes"}', 100, 100) == (None, None)


def test_cases_point_at_real_pages_and_unique_ids():
    ids = [c[0] for c in LOCATE_CASES] + [c[0] for c in WHICH_CASES]
    assert len(ids) == len(set(ids))
    assert all(c[1] in PAGES for c in LOCATE_CASES)
    assert all(c[2] is None or f'data-t="{c[2]}"' in PAGES[c[1]][3] for c in LOCATE_CASES)
    assert all(g <= set(PAGES) for _, _, g in WHICH_CASES)


def test_flagged_counts_low_verify_scores_per_hit_group():
    rows = [{"jev_hit": False, "verify": 0.1}, {"jev_hit": False, "verify": 0.9},
            {"jev_hit": True, "verify": 0.2}, {"jev_hit": True, "verify": 0.95}, {"jev_hit": True, "verify": 0.6}]
    assert ev.flagged(rows, False) == "1/2"
    assert ev.flagged(rows, True) == "1/3"


ELEMENTS = [
    {"type": "other", "id": "remember", "label": "Remember me", "frame": [0, 100, 402, 44]},
    {"type": "switch", "id": "remember", "label": "Remember me", "frame": [330, 106, 51, 31]},
    {"type": "button", "id": "", "label": "Delete", "frame": [20, 400, 160, 44]},
]


def test_pick_element_takes_the_first_match_and_narrows_by_type():
    assert ev.pick_element(ELEMENTS, (None, "remember", None))["type"] == "other"  # container comes first
    assert ev.pick_element(ELEMENTS, ("switch", "remember", None))["frame"] == [330, 106, 51, 31]
    assert ev.pick_element(ELEMENTS, ("button", None, "Delete"))["label"] == "Delete"
    with pytest.raises(ValueError):
        ev.pick_element(ELEMENTS, ("button", None, "Cancel"))


def test_frame_fraction_is_relative_to_the_window():
    assert ev.frame_fraction([100, 200, 50, 100], [0, 0, 400, 800]) == box(0.25, 0.25, 0.375, 0.375)
    assert ev.frame_fraction([110, 220, 50, 100], [10, 20, 400, 800]) == box(0.25, 0.25, 0.375, 0.375)


def test_sim_cases_point_at_declared_targets_and_ids_are_unique_across_suites():
    from sim_cases import SIM_LOCATE_CASES, SIM_SCREENS, SIM_TARGETS, SIM_WHICH_CASES
    ids = [c[0] for c in LOCATE_CASES + SIM_LOCATE_CASES] + [c[0] for c in WHICH_CASES + SIM_WHICH_CASES]
    assert len(ids) == len(set(ids))
    assert set(SIM_TARGETS) == set(SIM_SCREENS)
    assert all(c[2] is None or c[2] in SIM_TARGETS[c[1]] for c in SIM_LOCATE_CASES)
    assert all(g <= set(SIM_SCREENS) for _, _, g in SIM_WHICH_CASES)
    assert not set(SIM_SCREENS) & set(PAGES)  # shots of both suites share one name space
