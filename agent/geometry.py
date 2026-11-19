"""미터 평면의 선분과 반경 원 합집합 길이. 실제·합성 엔진의 공통 계산."""
from math import sqrt,hypot,isfinite
from numbers import Real


def covered_length(points, facilities, radius):
    if isinstance(radius,bool) or not isinstance(radius,Real) or not isfinite(radius) or radius <= 0:
        raise ValueError('반경은 양수여야 합니다.')
    covered = total = 0.
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        length = hypot(x2-x1, y2-y1)
        if length == 0:
            continue
        total += length
        ux, uy = (x2-x1)/length, (y2-y1)/length
        intervals = []
        for f in facilities:
            dx, dy = f['x']-x1, f['y']-y1
            along = dx*ux + dy*uy
            perpendicular2 = max(0., dx*dx + dy*dy - along*along)
            if perpendicular2 > radius*radius:
                continue
            delta = sqrt(max(0., radius*radius-perpendicular2))
            left, right = max(0., along-delta), min(length, along+delta)
            if right > left:
                intervals.append((left, right))
        end = -1.
        for left, right in sorted(intervals):
            covered += max(0., right-max(left, end))
            end = max(end, right)
    return covered, total


def indexed_covered_length(points,facilities,radius):
    """원 합집합 길이와 같은 식. 각 선분 주변 격자만 조회해 긴 경로 계산을 제한한다."""
    if isinstance(radius,bool) or not isinstance(radius,Real) or not isfinite(radius) or radius<=0:raise ValueError('반경은 양수')
    cell=max(float(radius),25.0);grid={}
    for f in facilities:grid.setdefault((int(f['x']//cell),int(f['y']//cell)),[]).append(f)
    total=covered=0.0
    for a,b in zip(points,points[1:]):
        near=[]
        for x in range(int((min(a[0],b[0])-radius)//cell),int((max(a[0],b[0])+radius)//cell)+1):
            for y in range(int((min(a[1],b[1])-radius)//cell),int((max(a[1],b[1])+radius)//cell)+1):near.extend(grid.get((x,y),()))
        c,length=covered_length([a,b],near,radius);covered+=c;total+=length
    return covered,total
