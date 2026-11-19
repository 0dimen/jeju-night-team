"""보행 도로망에서 최단 경로와 시설 인접 구간을 선호하는 경로를 직접 계산한다.

연구용 계산부다. 온라인 요청을 하지 않으며 기본 에이전트·운영 추천 설정을 변경하지 않는다.
'시설 선호 경로'는 가로등·공공 CCTV 위치와 가까운 구간의 비용을 낮춘 경로일 뿐
안전을 보장하거나 밝기·작동 상태를 확인한 경로가 아니다.
"""
import heapq
from math import cos, hypot, isfinite, radians

from agent.geometry import covered_length

# 연구용 보행 태그 필터. 전체 OSRM 규칙·실제 통행을 재현한 것은 아니다. 자동차 전용 종류는 제외.
FOOT_HIGHWAYS = frozenset({
    'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link',
    'unclassified', 'residential', 'road', 'living_street', 'service', 'track', 'path',
    'steps', 'pedestrian', 'footway', 'pier'})
WALK_METERS_PER_MINUTE = 75.0  # 4.5km/h 가정. 실측 아님


def walkable(tags):
    if tags.get('highway') not in FOOT_HIGHWAYS or tags.get('area') == 'yes':
        return False
    foot = tags.get('foot')
    if foot in ('no', 'private'):
        return False
    if tags.get('access') in ('no', 'private') and foot not in ('yes', 'designated', 'permissive'):
        return False
    return True


def build_graph(elements, center):
    """Overpass JSON의 node·way 목록으로 보행 그래프를 만든다. center는 (경도, 위도)."""
    lon0, lat0 = center
    scale = (cos(radians(lat0)) * 111320.0, 110540.0)
    coords = {e['id']: (e['lon'], e['lat']) for e in elements if e.get('type') == 'node'}
    graph = {'nodes': {}, 'edges': [], 'adjacency': {}, 'center': (lon0, lat0), 'scale': scale}
    for element in elements:
        if element.get('type') != 'way' or not walkable(element.get('tags', {})):
            continue
        refs = element.get('nodes', [])
        for a, b in zip(refs, refs[1:]):
            if a == b or a not in coords or b not in coords:
                continue
            for node in (a, b):
                if node not in graph['nodes']:
                    graph['nodes'][node] = {'lonlat': coords[node], 'xy': project(graph, coords[node])}
            (x1, y1), (x2, y2) = graph['nodes'][a]['xy'], graph['nodes'][b]['xy']
            length = hypot(x2 - x1, y2 - y1)
            if length <= 0:
                continue
            index = len(graph['edges'])
            graph['edges'].append({'a': a, 'b': b, 'length': length, 'way': element['id'],
                                   'light': 0.0, 'cctv': 0.0,
                                   'walk_tags': {k:v for k,v in element.get('tags',{}).items() if k in ('highway','access','foot','sidewalk','crossing','surface','lit','wheelchair','incline')}})
            tags=element.get('tags', {})
            direction=tags.get('oneway:foot')
            graph['adjacency'].setdefault(a, [])
            graph['adjacency'].setdefault(b, [])
            if direction != '-1' and tags.get('foot:forward') != 'no':
                graph['adjacency'][a].append((b,index))
            if direction not in ('yes','1','true') and tags.get('foot:backward') != 'no':
                graph['adjacency'][b].append((a,index))
    if not graph['edges']:
        raise ValueError('보행 가능한 도로가 없습니다.')
    return graph


def project(graph, lonlat):
    lon0, lat0 = graph['center']
    kx, ky = graph['scale']
    return ((lonlat[0] - lon0) * kx, (lonlat[1] - lat0) * ky)


def score_edges(graph, facilities, radius, key):
    """각 도로 조각에서 시설 반경 안에 드는 길이 비율(0~1)을 edge[key]에 기록한다."""
    if key not in ('light', 'cctv'):
        raise ValueError('시설 종류 확인')
    if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not isfinite(radius) or not 0 < radius <= 200:
        raise ValueError('반경은0초과200미터이하')
    cell = max(float(radius), 25.0)
    grid = {}
    for lonlat in facilities:
        x, y = project(graph, lonlat)
        grid.setdefault((int(x // cell), int(y // cell)), []).append({'x': x, 'y': y})
    for edge in graph['edges']:
        a, b = graph['nodes'][edge['a']]['xy'], graph['nodes'][edge['b']]['xy']
        x_range = range(int((min(a[0], b[0]) - radius) // cell), int((max(a[0], b[0]) + radius) // cell) + 1)
        y_range = range(int((min(a[1], b[1]) - radius) // cell), int((max(a[1], b[1]) + radius) // cell) + 1)
        near = [f for i in x_range for j in y_range for f in grid.get((i, j), ())]
        covered = covered_length([a, b], near, radius)[0] if near else 0.0
        edge[key] = min(1.0, covered / edge['length'])
    return graph


def nearest_node(graph, lonlat):
    x, y = project(graph, lonlat)
    node = min(graph['adjacency'], key=lambda n: hypot(graph['nodes'][n]['xy'][0] - x, graph['nodes'][n]['xy'][1] - y))
    nx, ny = graph['nodes'][node]['xy']
    return node, hypot(nx - x, ny - y)


def shortest_path(graph, start, goal, cost):
    best = {start: 0.0}
    previous = {}
    heap = [(0.0, start)]
    while heap:
        total, node = heapq.heappop(heap)
        if node == goal:
            break
        if total > best.get(node, float('inf')):
            continue
        for other, index in graph['adjacency'].get(node, ()):
            candidate = total + cost(graph['edges'][index])
            if candidate < best.get(other, float('inf')):
                best[other] = candidate
                previous[other] = (node, index)
                heapq.heappush(heap, (candidate, other))
    if goal not in best:
        raise ValueError('출발·도착이 보행 도로망에서 연결되지 않습니다.')
    nodes, edges = [goal], []
    while nodes[-1] != start:
        node, index = previous[nodes[-1]]
        nodes.append(node)
        edges.append(index)
    return nodes[::-1], edges[::-1]


def summarize(graph, nodes, edge_indexes):
    edges = [graph['edges'][i] for i in edge_indexes]
    length = sum(e['length'] for e in edges)
    return {'nodes': nodes, 'edge_indexes': edge_indexes, 'coordinates': [list(graph['nodes'][n]['lonlat']) for n in nodes],
            'length_m': round(length, 1), 'duration_minutes': round(length / WALK_METERS_PER_MINUTE, 2),
            'light_fraction': round(sum(e['length'] * e['light'] for e in edges) / length, 4),
            'cctv_fraction': round(sum(e['length'] * e['cctv'] for e in edges) / length, 4)}


def plan_routes(graph, start, goal, light_weight=1.0, cctv_weight=1.0, max_detour=1.5):
    """최단 경로와 시설 선호 경로를 함께 돌려준다.

    시설 선호 비용 = 길이 × (1 + light_weight×(1-가로등 인접 비율) + cctv_weight×(1-CCTV 인접 비율)).
    결과가 최단 거리의 max_detour배를 넘으면 가중치를 절반씩 줄여 다시 찾는다.
    """
    for value in (light_weight, cctv_weight, max_detour):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise ValueError('가중치·우회 한도는 음수가 아닌 유한한 수')
    if max_detour < 1 or start == goal:
        raise ValueError('우회 한도는1이상, 출발·도착은 달라야 합니다.')
    base = shortest_path(graph, start, goal, lambda e: e['length'])
    base_summary = summarize(graph, *base)
    lw, cw = float(light_weight), float(cctv_weight)
    preferred_summary = None
    for _ in range(7):
        preferred = shortest_path(graph, start, goal,
                                  lambda e: e['length'] * (1 + lw * (1 - e['light']) + cw * (1 - e['cctv'])))
        candidate = summarize(graph, *preferred)
        if candidate['length_m'] <= base_summary['length_m'] * max_detour + 1e-6:
            preferred_summary = candidate
            break
        lw, cw = lw / 2, cw / 2
    if preferred_summary is None:
        preferred_summary, lw, cw = base_summary, 0.0, 0.0
    return {'shortest': base_summary, 'facility_preferred': preferred_summary,
            'same_route': base_summary['nodes'] == preferred_summary['nodes'],
            'weights_used': {'light': lw, 'cctv': cw}, 'max_detour': max_detour,
            'meaning': '연구용 비교. 시설 위치 인접 비율이며 안전 확률·밝기·작동 상태가 아님'}
