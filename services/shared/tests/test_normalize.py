from laiive_shared.normalize import genre_slug, norm


def test_norm_strips_case_space_diacritics():
    assert norm("  Café Berlín ") == "cafe berlin"
    assert norm("Niña de las Dunas") == "nina de las dunas"
    assert norm("BERGHAIN") == "berghain"


def test_genre_slug():
    assert genre_slug("Indie Rock") == "indie-rock"
    assert genre_slug("  Drum & Bass ") == "drum-bass"
    assert genre_slug("Electrónica") == "electronica"
    assert genre_slug("jazz") == "jazz"
