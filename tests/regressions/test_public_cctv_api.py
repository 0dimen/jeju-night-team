import io,json
from urllib.error import HTTPError
import pytest
from agent.data.cctv_api import decode_page,fetch_page,CCTVAPIError


def payload(rows,total=1):return {'response':{'header':{'resultCode':'0'},'body':{'pageNo':1,'totalCount':total,'items':{'item':rows}}}}
ROW={'OPN_ATMY_GRP_CD':'6520000','MNG_NO':'sample'}


def test_page_handles_empty_and_rejects_cross_region_or_duplicate():
    assert decode_page(payload([],0),'6520000',1)==([],0)
    with pytest.raises(CCTVAPIError):decode_page(payload([ROW]),'6510000',1)
    with pytest.raises(CCTVAPIError):decode_page(payload([ROW,ROW],2),'6520000',1)


def test_api_key_url_never_in_exception_text():
    key='fake-private-key+test='
    def failing(request,timeout):raise HTTPError(request.full_url,403,'not allowed',{},None)
    with pytest.raises(CCTVAPIError) as error:fetch_page('6520000',1,key,opener=failing)
    assert key not in str(error.value) and 'serviceKey' not in str(error.value) and error.value.__cause__ is None


def test_response_echo_key_is_redacted_before_return():
    key='fake-private-key+test='
    class Response(io.BytesIO):status=200
    data=payload([{**ROW,'note':key}])
    result=fetch_page('6520000',1,key,opener=lambda request,timeout:Response(json.dumps(data).encode()))
    assert key not in json.dumps(result) and result['response']['body']['items']['item'][0]['note']=='[REDACTED]'


def test_provider_rejection_not_accepted_as_empty_success():
    with pytest.raises(CCTVAPIError):decode_page({'response':{'header':{'resultCode':'30'},'body':{}}},'6520000',1)
