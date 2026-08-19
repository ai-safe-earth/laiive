from agent.classifier import Classification, Constraints
from agent.router import PlanKind, route


def classify(**kwargs) -> Classification:
    defaults = {
        "query_type": "event_search",
        "moment": "first_query",
        "sub_queries": [],
    }
    defaults.update(kwargs)
    return Classification(**defaults)


def test_smalltalk_and_out_of_scope_get_no_plans():
    assert route(classify(query_type="smalltalk"), has_location=False) == []
    assert route(classify(query_type="out_of_scope"), has_location=True) == []


def test_ambiguous_without_subqueries_gets_no_plans():
    c = classify(moment="ambiguous", clarification="which city")
    assert route(c, has_location=False) == []


def test_structured_constraints_route_to_template():
    c = classify(sub_queries=[Constraints(city="Madrid", genre="jazz")])
    plans = route(c, has_location=False)
    assert [p.kind for p in plans] == [PlanKind.TEMPLATE]


def test_near_me_with_location_routes_to_nearby():
    c = classify(query_type="nearby", sub_queries=[Constraints(near_me=True)])
    assert [p.kind for p in route(c, has_location=True)] == [PlanKind.NEARBY]


def test_near_me_without_location_is_dropped():
    c = classify(query_type="nearby", sub_queries=[Constraints(near_me=True)])
    assert route(c, has_location=False) == []


def test_free_text_routes_to_vector():
    c = classify(sub_queries=[Constraints(free_text="intimate candle-lit jazz")])
    assert [p.kind for p in route(c, has_location=False)] == [PlanKind.VECTOR]


def test_custom_cypher_flag_wins():
    c = classify(
        sub_queries=[
            Constraints(
                query_text="how many venues host techno?", needs_custom_cypher=True
            )
        ]
    )
    assert [p.kind for p in route(c, has_location=False)] == [PlanKind.LLM_CYPHER]


def test_multi_intent_produces_one_plan_each():
    c = classify(
        sub_queries=[
            Constraints(city="Madrid", genre="jazz"),
            Constraints(artist="Klangfeld"),
        ]
    )
    plans = route(c, has_location=False)
    assert len(plans) == 2
    assert all(p.kind == PlanKind.TEMPLATE for p in plans)


def test_place_less_query_with_a_location_routes_to_nearby():
    """The gap: no city, no "near me" phrasing — TEMPLATE had no city filter."""
    c = classify(sub_queries=[Constraints(genre="techno", date_from="2026-08-21")])
    assert [p.kind for p in route(c, has_location=True)] == [PlanKind.NEARBY]
    assert [p.kind for p in route(c, has_location=False)] == [PlanKind.TEMPLATE]


def test_a_named_place_still_wins_over_the_shared_location():
    c = classify(sub_queries=[Constraints(city="Madrid", genre="jazz")])
    assert [p.kind for p in route(c, has_location=True)] == [PlanKind.TEMPLATE]
    c = classify(sub_queries=[Constraints(country_code="ES", genre="jazz")])
    assert [p.kind for p in route(c, has_location=True)] == [PlanKind.TEMPLATE]


def test_identity_asks_are_not_cut_to_a_radius():
    """ "when does Klangfeld play?" means anywhere, location shared or not."""
    for c in (Constraints(artist="Klangfeld"), Constraints(venue="Sala Apolo")):
        plans = route(classify(sub_queries=[c]), has_location=True)
        assert [p.kind for p in plans] == [PlanKind.TEMPLATE]


def test_empty_constraints_with_a_location_still_get_no_plan():
    c = classify(sub_queries=[Constraints()])
    assert route(c, has_location=True) == []


def test_free_text_with_a_location_still_routes_to_vector():
    c = classify(sub_queries=[Constraints(free_text="something loud")])
    assert [p.kind for p in route(c, has_location=True)] == [PlanKind.VECTOR]
