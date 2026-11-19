// 페이지당 준비 확인 한 번. 검색어·위치·외부 제공사 요청 없이 병렬 실행한다.
export function createPreparation(fetcher = fetch, timeoutMs = 5000) {
  let preparation;
  return (signal) => {
    if (preparation) return preparation;
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) abort();
    else signal?.addEventListener("abort", abort, { once: true });
    const timeout = setTimeout(abort, timeoutMs);
    preparation = (async () => {
      try {
        if (controller.signal.aborted) return false;
        const response = await fetcher("/health", {
          method: "GET", cache: "no-store", credentials: "omit",
          signal: controller.signal,
        });
        return response.ok;
      } catch {
        return false; // 준비 확인 실패가 검색 조작을 막지 않는다.
      } finally {
        clearTimeout(timeout);
        signal?.removeEventListener("abort", abort);
      }
    })();
    return preparation;
  };
}
