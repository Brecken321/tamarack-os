import pytest

from tamarack.colors import BLACK, RGB, WHITE, best_text_on, contrast_ratio


def test_parse_and_format() -> None:
    color = RGB.parse("#2e8b62")
    assert (color.r, color.g, color.b) == (46, 139, 98)
    assert color.hex == "#2E8B62"
    assert color.kde == "46,139,98"
    assert RGB.parse("FFFFFF") == WHITE


@pytest.mark.parametrize("bad", ["", "#12345", "#GGGGGG", "rgb(1,2,3)", "#1234567"])
def test_parse_rejects_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        RGB.parse(bad)


def test_contrast_reference_values() -> None:
    assert contrast_ratio(WHITE, BLACK) == pytest.approx(21.0)
    assert contrast_ratio(WHITE, WHITE) == pytest.approx(1.0)
    # WCAG reference: #767676 on white is the classic 4.54:1 example.
    assert contrast_ratio(RGB.parse("#767676"), WHITE) == pytest.approx(4.54, abs=0.01)


def test_mix_and_text_choice() -> None:
    assert WHITE.mix(BLACK, 0.5) == RGB(128, 128, 128)
    assert WHITE.mix(BLACK, 0) == WHITE
    with pytest.raises(ValueError):
        WHITE.mix(BLACK, 1.5)
    assert best_text_on(RGB.parse("#FFD600")) == BLACK
    assert best_text_on(RGB.parse("#15191B")) == WHITE
