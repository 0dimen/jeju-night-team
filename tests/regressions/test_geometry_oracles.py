"""부록 B 산식의 독립 기하 답안·변환 관계. 모두 합성 미터 평면이다."""
from math import cos,hypot,sin
import random
import numpy as np
import pytest
from stubs.engine import covered_length,analyze,FACILITIES


def facility(x,y=0):
    return {'x':float(x),'y':float(y)}


@pytest.mark.parametrize('points,facilities,radius,expected,total',[
    ([(0,0),(100,0)],[facility(50,6)],10,16,100),
    ([(0,0),(100,0)],[facility(40),facility(50)],10,30,100),
    ([(0,0),(100,0)],[facility(50),facility(50)],10,20,100),
    ([(0,0),(100,0)],[facility(50,10)],10,0,100),
    ([(0,0),(100,0)],[facility(0)],10,10,100),
    ([(0,0),(100,0),(100,100)],[facility(100)],10,20,200),
    ([(0,0),(0,0),(100,0)],[],10,0,100),
])
def test_closed_form_intersections(points,facilities,radius,expected,total):
    """현의 길이 2√(r²-d²), 끝점은 반경 길이, 겹침은 합집합이라는 독립 답안."""
    covered,length=covered_length(points,facilities,radius)
    assert covered==pytest.approx(expected,abs=1e-9)
    assert length==pytest.approx(total,abs=1e-9)


def test_rigid_transform_reverse_split_and_radius_relations():
    points=[(0.,0.),(100.,0.),(100.,100.)]
    facilities=[facility(30,4),facility(85,5),facility(100,70)]
    baseline=covered_length(points,facilities,12)
    theta=.731;c,s=cos(theta),sin(theta)
    def transform(x,y):return (c*x-s*y+10000,s*x+c*y-30000)
    transformed=[transform(*p) for p in points]
    shifted=[facility(*transform(f['x'],f['y'])) for f in facilities]
    assert covered_length(transformed,shifted,12)==pytest.approx(baseline,abs=1e-7)
    assert covered_length(list(reversed(points)),list(reversed(facilities)),12)==pytest.approx(baseline)
    split=[(0.,0.),(40.,0.),(100.,0.),(100.,20.),(100.,100.)]
    assert covered_length(split,facilities,12)==pytest.approx(baseline)
    values=[covered_length(points,facilities,r)[0] for r in (5,12,30)]
    assert values==sorted(values)
    assert 0<=values[0]<=values[-1]<=baseline[1]


def test_random_geometry_against_independent_midpoint_sampling():
    """각 표본의 원 내부 여부만 세며 선분-원 교차 공식을 사용하지 않는다.

    원 하나가 선분에서 만드는 구간의 끝점은 최대 둘이다. 중점 표본 오차를
    원 수×표본 간격의 두 배로 제한해 우연한 그리드 경계를 허용한다.
    """
    rng=random.Random(20261118);count=16000
    for _ in range(12):
        points=[(rng.uniform(-100,100),rng.uniform(-100,100)) for _ in range(4)]
        facilities=[facility(rng.uniform(-100,100),rng.uniform(-100,100)) for _ in range(6)]
        radius=rng.uniform(5,45);sampled=total=0.
        for start,end in zip(points,points[1:]):
            length=hypot(end[0]-start[0],end[1]-start[1]);total+=length
            t=(np.arange(count)+.5)/count
            x=start[0]+t*(end[0]-start[0]);y=start[1]+t*(end[1]-start[1])
            inside=np.zeros(count,dtype=bool)
            for f in facilities:
                inside|=(x-f['x'])**2+(y-f['y'])**2<=radius**2
            sampled+=float(inside.mean())*length
        covered,length=covered_length(points,facilities,radius)
        assert length==pytest.approx(total)
        assert covered==pytest.approx(sampled,abs=2*len(facilities)*total/count+1e-8)
        assert 0<=covered<=length+1e-8


def test_R5_quantities_ignore_facility_iteration_order(request_data):
    first=analyze(request_data)
    second=analyze(request_data,facilities=list(reversed(FACILITIES)))
    # 순서를 포함한 자료 해시는 달라도, 집합으로 계산하는 수치·정렬은 같다.
    assert first['routes']==second['routes']


def test_radius_changes_logic_and_numbers_without_claiming_new_data(request_data):
    small=analyze(request_data,radius=30);large=analyze(request_data,radius=80)
    assert small['data_version']==large['data_version']
    assert small['logic_version']!=large['logic_version']
    a={r['id']:r['indicators']['cctv']['value'] for r in small['routes']}
    b={r['id']:r['indicators']['cctv']['value'] for r in large['routes']}
    assert all(a[k]<=b[k] for k in a)
