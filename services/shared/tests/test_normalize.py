from laiive_shared.normalize import genre_family, genre_slug, norm


def test_norm_strips_case_space_diacritics():
    assert norm("  Café Berlín ") == "cafe berlin"
    assert norm("Niña de las Dunas") == "nina de las dunas"
    assert norm("BERGHAIN") == "berghain"


def test_genre_slug():
    assert genre_slug("Indie Rock") == "indie-rock"
    assert genre_slug("  Drum & Bass ") == "drum-bass"
    assert genre_slug("Ópera") == "opera"
    assert genre_slug("jazz") == "jazz"
    # "Electrónica" used to slug to 'electronica' and sit beside 'electronic'
    # as a second node for the same genre; the pages this graph is built from
    # are Spanish and Catalan as often as English.
    assert genre_slug("Electrónica") == "electronic"


class TestGenreVocabulary:
    """One genre, one node — and a word that is not a genre gets no node."""

    def test_aliases_collapse_to_one_spelling(self):
        assert genre_slug("Electronica") == "electronic"
        assert genre_slug("R&B") == "rnb"
        assert genre_slug("Reguetón") == "reggaeton"

    def test_a_word_that_is_not_a_genre_comes_back_empty(self):
        """Callers already treat an empty slug as "no genre"."""
        for word in ("various", "Varios", "OTHER", "live", "music"):
            assert genre_slug(word) == ""

    def test_a_regional_label_is_left_alone(self):
        """'flamenco' and 'punjabi' are more scene than style, and still useful."""
        assert genre_slug("Punjabi") == "punjabi"
        assert genre_slug("Flamenco") == "flamenco"

    def test_the_family_reaches_every_stored_spelling(self):
        assert genre_family("electronic") == [
            "edm",
            "electro",
            "electronic",
            "electronica",
        ]
        # asking by a variant finds the canonical, and its siblings
        assert genre_family("EDM") == genre_family("electronic")

    def test_a_genre_with_no_variants_is_just_itself(self):
        assert genre_family("techno") == ["techno"]

    def test_a_non_genre_has_no_family(self):
        assert genre_family("various") == []
