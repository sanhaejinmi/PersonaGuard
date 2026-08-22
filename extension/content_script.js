/**
 * content_script.js
 *
 * ChatGPT / Claude 페이지에 삽입되어:
 * 1. 프롬프트 입력창(textarea)을 찾아서 텍스트 변화를 감지
 * 2. 사용자가 전송(Enter, 전송 버튼 클릭)하려는 시점에 가로채서
 *    background.js에 분석 요청을 보내고, 팝업에서 검토가 끝날 때까지 실제 전송을 막음
 * 3. background로부터 재작성된 최종 텍스트를 받으면 입력창에 채워 넣고 전송 진행
 *
 * ⚠️ 사이트별 입력창 선택자(selector)는 실제 페이지 구조에 맞게 조정이 필요합니다.
 *    아래 SELECTORS는 임시값이며, 배포 전 각 사이트에서 직접 확인해야 합니다.
 */

const SELECTORS = {
  // ChatGPT — #prompt-textarea는 현재 textarea가 아니라 contenteditable div로 렌더링됨
  // (2026 기준 실측). getInputText/setInputText가 이미 contenteditable을 처리하므로
  // 태그명을 selector에서 뺐다 — 나중에 다시 textarea로 바뀌어도 그대로 매치된다.
  'chat.openai.com': '#prompt-textarea, textarea[data-id="root"]',
  'chatgpt.com': '#prompt-textarea, textarea[data-id="root"]',
  // Claude
  'claude.ai': 'div[contenteditable="true"]'
};

let pendingApprovedText = null; // 팝업 승인 후 채워 넣을 텍스트를 임시 보관

function getInputSelector() {
  return SELECTORS[location.hostname] ?? 'textarea';
}

function getInputElement() {
  return document.querySelector(getInputSelector());
}

function getInputText(el) {
  if (!el) return '';
  return el.tagName === 'TEXTAREA' ? el.value : el.innerText;
}

function setInputText(el, text) {
  if (!el) return;
  if (el.tagName === 'TEXTAREA') {
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype,
      'value'
    ).set;
    nativeSetter.call(el, text);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  } else {
    el.innerText = text;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

/**
 * 사용자가 전송을 시도하는 시점(Enter 키)을 가로채서
 * 아직 검토 전이면 전송을 막고 분석 요청을 보낸다.
 * 이미 검토/승인이 끝난 텍스트(pendingApprovedText)라면 그대로 통과시킨다.
 */
document.addEventListener(
  'keydown',
  (e) => {
    const el = getInputElement();
    if (!el || e.target !== el) return;
    if (e.key !== 'Enter' || e.shiftKey) return; // Shift+Enter는 줄바꿈이므로 무시

    const currentText = getInputText(el);
    if (!currentText.trim()) return;

    // 이미 승인받아 채워 넣은 텍스트라면 그대로 전송 허용
    if (pendingApprovedText && currentText === pendingApprovedText) {
      pendingApprovedText = null;
      return;
    }

    // 아직 검토 전 → 전송 막고 분석 요청
    e.preventDefault();
    e.stopPropagation();
    requestAnalysis(currentText);
  },
  true
);

function requestAnalysis(text) {
  // 보호 끄기 상태 확인
  chrome.storage.local.get('personaguard:protection_enabled', (result) => {
    const isEnabled = result['personaguard:protection_enabled'] !== false;
    if (!isEnabled) {
      // 보호가 꺼져있으면 분석하지 않음
      return;
    }

    chrome.runtime.sendMessage(
      { type: 'ANALYZE_PROMPT', payload: { text } },
      (response) => {
        if (!response || !response.ok) {
          console.error('[PersonaGuard] 분석 요청 실패', response?.error);
          return;
        }
        // 민감정보가 감지되면 안내 메시지 표시
        const entities = response?.data?.entities ?? [];
        if (entities.length > 0) {
          showReviewBadgeHint();
        }
      }
    );
  });
}

function showReviewBadgeHint() {
  // 간단한 시각적 알림: 입력창 근처에 짧은 안내 표시 (선택 사항, 추후 UI팀과 스타일 맞춰 개선)
  const el = getInputElement();
  if (!el) return;
  const hint = document.createElement('div');
  hint.textContent = 'PersonaGuard가 민감정보를 확인했어요. 툴바 아이콘을 눌러 검토해주세요.';
  hint.style.cssText =
    'position:fixed;bottom:80px;right:24px;background:#0F6E56;color:#fff;' +
    'padding:10px 14px;border-radius:8px;font-size:13px;z-index:999999;' +
    'box-shadow:0 4px 12px rgba(0,0,0,0.15);';
  document.body.appendChild(hint);
  setTimeout(() => hint.remove(), 4000);
}

// background.js가 rewrite 결과를 다시 이 페이지로 보내면, 입력창에 채워 넣고 전송 대기 상태로 표시
chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'FILL_REWRITTEN_TEXT') {
    const el = getInputElement();
    if (!el) return;
    pendingApprovedText = message.payload.text;
    setInputText(el, message.payload.text);
    el.focus();
  }
});