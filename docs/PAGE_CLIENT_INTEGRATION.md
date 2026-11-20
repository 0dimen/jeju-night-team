# 페이지 상태 연결 모듈

`client/page_conversation.mjs`는 화면 없이 재사용할 수 있는 연결 모듈입니다. 페이지 변수에만 위치·대화 상태를 두며 브라우저 저장소나 쿠키에 쓰지 않습니다.

```javascript
import { createPageConversation } from './client/page_conversation.mjs';
const page = createPageConversation();
// 지도에서 사용자가 선택한 위치를 전달합니다. 가상 좌표나 대표 지점을 실제 위치로 확정하지 않습니다.
page.setLocations({ origin: selectedOrigin, destination: selectedDestination });
const result = await page.send('3시에 갈거야');
if (result) renderResult(result);
// 단일 페이지 앱의 화면 이동·컴포넌트 해제 시에도 호출합니다.
page.dispose();
```

- 기본 요청 주소는 같은 서버의 `/agent/conversation`입니다. 서버·화면 연결 시 같은 출처로 제공하거나 별도 접속 정책을 확인해야 합니다.
- 페이지 이탈은 상태를 비우고 요청을 중단합니다. 브라우저 뒤로가기 복원도 빈 상태로 시작합니다.
- 초기화 후 늦게 도착한 응답은 무시하여 위치를 되살리지 않습니다.
- 화면에 반환하는 응답에서는 위치 상태를 제거합니다. 화면도 결과나 선택 위치를 따로 저장하지 않아야 합니다.
- 단일 페이지 앱 이동에는 반드시 `dispose()`를 연결해야 합니다. 전체 지도 화면·서비스 페이지는 아직 없습니다.

검사: Node.js 20 이상에서 `node --test tests/browser/test_page_conversation.mjs`. 5개 검사는 페이지 이벤트·새 인스턴스·늦은 응답·화면 응답·해제 후 요청을 모의 환경에서 확인합니다. 실제 브라우저·지도·페이지 이탈 통합 검사는 화면 연결 뒤에 필요합니다.
