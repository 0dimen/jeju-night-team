import pytest

from agent.data.facility_route import build_graph, nearest_node, plan_routes, score_edges, walkable

CENTER = (126.5, 33.5)
A, B, C, D = (126.5, 33.5), (126.501, 33.5), (126.5, 33.5004), (126.501, 33.5004)


def elements(extra=()):
    nodes = [{'type': 'node', 'id': i, 'lon': p[0], 'lat': p[1]} for i, p in enumerate((A, B, C, D), 1)]
    ways = [{'type': 'way', 'id': 10, 'nodes': [1, 2], 'tags': {'highway': 'residential'}},
            {'type': 'way', 'id': 11, 'nodes': [1, 3, 4, 2], 'tags': {'highway': 'footway'}}]
    return nodes + ways + list(extra)


def graph_with_lights():
    graph = build_graph(elements(), CENTER)
    lights = [(126.5 + 0.0001 * i, 33.5004) for i in range(11)] + [(126.5, 33.5002), (126.501, 33.5002)]
    score_edges(graph, lights, 15, 'light')
    return graph


def test_shortest_and_facility_preferred_differ_when_lights_are_on_the_detour():
    graph = graph_with_lights()
    result = plan_routes(graph, 1, 2, light_weight=2.0, cctv_weight=0.0, max_detour=2.5)
    assert result['shortest']['nodes'] == [1, 2]
    assert result['facility_preferred']['nodes'] == [1, 3, 4, 2]
    assert result['shortest']['light_fraction'] < 0.4 < result['facility_preferred']['light_fraction']
    assert result['same_route'] is False
    assert result['shortest']['coordinates'][0] == result['facility_preferred']['coordinates'][0]


def test_detour_limit_falls_back_to_shortest():
    result = plan_routes(graph_with_lights(), 1, 2, light_weight=2.0, cctv_weight=0.0, max_detour=1.0)
    assert result['same_route'] is True
    assert result['weights_used']['light'] < 2.0


def test_no_facilities_means_both_routes_are_the_shortest():
    result = plan_routes(build_graph(elements(), CENTER), 1, 2)
    assert result['same_route'] is True
    assert result['shortest']['light_fraction'] == 0 and result['shortest']['cctv_fraction'] == 0


def test_car_only_and_private_ways_are_not_used():
    assert not walkable({'highway': 'motorway'})
    assert not walkable({'highway': 'residential', 'access': 'private'})
    assert walkable({'highway': 'service', 'access': 'private', 'foot': 'yes'})
    shortcut = {'type': 'way', 'id': 12, 'nodes': [3, 2], 'tags': {'highway': 'trunk'}}
    graph = build_graph(elements([shortcut]), CENTER)
    assert all(edge['way'] != 12 for edge in graph['edges'])


def test_nearest_node_and_input_checks():
    graph = build_graph(elements(), CENTER)
    node, distance = nearest_node(graph, (126.50001, 33.50001))
    assert node == 1 and distance < 2
    with pytest.raises(ValueError):
        plan_routes(graph, 1, 1)
    with pytest.raises(ValueError):
        plan_routes(graph, 1, 2, max_detour=0.5)
    with pytest.raises(ValueError):
        score_edges(graph, [], 0, 'light')
    with pytest.raises(ValueError):
        build_graph([{'type': 'node', 'id': 1, 'lon': 126.5, 'lat': 33.5}], CENTER)


def test_missing_osm_node_does_not_create_bridge():
    data=elements()
    data[4]['nodes']=[1,999,2]
    graph=build_graph(data,CENTER)
    assert all(edge['way']!=10 for edge in graph['edges'])
    assert plan_routes(graph,1,2)['shortest']['nodes']==[1,3,4,2]


def test_explicit_pedestrian_oneway_not_reversed():
    data=elements();data[4]['tags']['oneway:foot']='yes'
    graph=build_graph(data,CENTER)
    assert plan_routes(graph,2,1,light_weight=0,cctv_weight=0)['shortest']['nodes']==[2,4,3,1]
