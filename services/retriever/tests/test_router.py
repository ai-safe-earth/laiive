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
