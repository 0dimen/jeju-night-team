from copy import deepcopy
import json
from pathlib import Path
import pytest
from agent.common import ROOT
from agent.data.routes import load_routes,segment_distance


def sample():
    return json.loads((ROOT/'data/route_examples/SYNTHETIC_routes.geojson').read_text(encoding='utf-8'))


def test_import_keeps_synthetic_and_distances():
    result=load_routes(ROOT/'data/route_examples/SYNTHETIC_routes.geojson')
    assert result['metadata']['synthetic'] is True
    assert 180<result['routes'][0]['length_m']<190
    assert result['routes'][1]['length_m']>result['routes'][0]['length_m']
    assert segment_distance([0,0],[0,1])==pytest.approx(111194.927,abs=.001)


@pytest.mark.parametrize('change', ['missing_source','unconfirmed_walk','bool_duration','nan_coordinate','reversed_range','different_end','duplicate_id','zero_length','projected_crs'])
def test_bad_routes_are_rejected(tmp_path,change):
    data=sample();a,b=data['features'];props=a['properties'];geometry=a['geometry']
    if change=='missing_source':del data['properties']['license_note']
    elif change=='unconfirmed_walk':props['walkability_checked']=False
    elif change=='bool_duration':props['duration_minutes']=True
    elif change=='nan_coordinate':geometry['coordinates'][0][0]=float('nan')
    elif change=='reversed_range':geometry['coordinates'][0]=[33.25,126.56]
    elif change=='different_end':b['geometry']['coordinates'][-1]=[126.563,33.25]
    elif change=='duplicate_id':b['properties']['id']=props['id']
    elif change=='zero_length':geometry['coordinates']=[[126.56,33.25],[126.56,33.25]]
    elif change=='projected_crs':data['crs']={'name':'EPSG:5186'}
    path=tmp_path/'routes.geojson';path.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError):load_routes(path)
