/**
 * background.js (MV3 service worker)
 *
 * 역할:
 * 1. content_script.js가 감지한 프롬프트 텍스트를 받아 백엔드(/analyze)에 보내고
 *    결과(original, masked, entities, candidates, session_id)를 chrome.storage.local에 저장
 * 2. 팝업(result_panel.js)이 열릴 때 GET_LATEST_ANALYSIS로 이 저장값을 읽어감
 * 3. 사용자가 팝업에서 항목별 보호 여부(true/false)를 정하고 승인하면
 *    REQUEST_REWRITE로 session_id + decisions를 받아 백엔드(/rewrite)에 전달,
 *    최종 재작성된 텍스트를 content_script로 넘겨 페이지 입력창에 채움
 *
 * ⚠️ 백엔드 /rewrite, AnalyzeResponse.session_id는 아직 백엔드팀 작업 중(미완료).
 *    연동 전까지는 fetch가 404/오류를 낼 수 있음 — 정상입니다.
 *    (백엔드 API: POST /analyze { prompt } -> { original, masked, entities, candidates, session_id }
 *                POST /rewrite { session_id, decisions } -> { rewritten (필드명 미확정) })
 */

const API_BASE_URL = 'http://127.0.0.1:8000';
const STORAGE_KEY_LATEST_ANALYSIS = 'personaguard:latestAnalysis';

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case 'ANALYZE_PROMPT':
      handleAnalyzePrompt(message.payload, sender, sendResponse);
      return true; // 비동기 응답을 위해 true 반환 (Chrome 확장 필수 규칙)

    case 'REQUEST_REWRITE':
      handleRequestRewrite(message.payload, sendResponse);
      return true;

    case 'GET_LATEST_ANALYSIS':
      chrome.storage.local.get(STORAGE_KEY_LATEST_ANALYSIS, (result) => {
        sendResponse({ ok: true, data: result[STORAGE_KEY_LATEST_ANALYSIS] ?? null });
      });
      return true;

    case 'FILL_APPROVED_TEXT':
      // (레거시 경로) 프론트에서 이미 완성한 텍스트를 그냥 페이지에 채워달라는 경우.
      // /rewrite 정식 연동 이후에는 REQUEST_REWRITE 쪽을 쓰는 게 기본 경로.
      if (message.payload.tabId) {
        chrome.tabs.sendMessage(message.payload.tabId, {
          type: 'FILL_REWRITTEN_TEXT',
          payload: { text: message.payload.text }
        });
      }
      sendResponse({ ok: true });
      return true;

    default:
      return false;
  }
});

/**
 * content_script가 페이지에서 캡처한 프롬프트를 백엔드(/analyze)로 보낸다.
 * 응답 형태: { original, masked, entities: [{type,value,start,end}], candidates: [] }
 */
async function handleAnalyzePrompt(payload, sender, sendResponse) {
  try {
    const res = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: payload.text })
    });

    if (!res.ok) {
      throw new Error(`백엔드 응답 오류: ${res.status}`);
    }

    const analysis = await res.json(); // { original, masked, entities, candidates }

    // 민감정보가 없으면 저장하지 않음
    if (!Array.isArray(analysis.entities) || analysis.entities.length === 0) {
      sendResponse({ ok: true, data: analysis });
      return;
    }

    // content_script.js는 자기 tabId를 모르므로, background가 sender.tab.id로 받아서 저장한다.
    // 이게 없으면 나중에 FILL_REWRITTEN_TEXT를 어느 탭에 보낼지 알 수 없다.
    await chrome.storage.local.set({
      [STORAGE_KEY_LATEST_ANALYSIS]: {
        analyzedAt: Date.now(),
        tabId: sender.tab?.id ?? null,
        ...analysis
      }
    });

    // 뱃지에 감지 건수 표시 (민감정보가 있을 때만)
    if (Array.isArray(analysis.entities) && analysis.entities.length > 0) {
      chrome.action.setBadgeText({ text: String(analysis.entities.length) });
      chrome.action.setBadgeBackgroundColor({ color: '#0F6E56' });
    } else {
      // 민감정보가 없으면 배지 제거
      chrome.action.setBadgeText({ text: '' });
    }

    sendResponse({ ok: true, data: analysis });
  } catch (err) {
    console.error('[PersonaGuard] analyze 요청 실패:', err);
    sendResponse({ ok: false, error: String(err) });
  }
}

/**
 * 팝업(approval_sender.js)에서 사용자가 항목별로 보호 여부(true/false)를 다 정한 뒤
 * "적용하고 전송"을 누르면 호출됨.
 * 백엔드(/rewrite)에 session_id + decisions를 보내 최종 재작성된 텍스트를 받고,
 * 그 텍스트를 content_script로 전달해 페이지 입력창에 채워 넣게 함.
 *
 * 요청 형태: { session_id: string, decisions: { "TYPE:start:end": true|false },
 *              custom_values: { "TYPE:start:end": string } }
 * 응답 형태: 백엔드 team 확정 전이라 { rewritten: string } 정도로 가정. 실제 필드명 확인 필요.
 */
async function handleRequestRewrite(payload, sendResponse) {
  try {
    const res = await fetch(`${API_BASE_URL}/rewrite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: payload.sessionId,
        decisions: payload.decisions,
        custom_values: payload.customValues ?? {}
      })
    });

    if (!res.ok) {
      throw new Error(`백엔드 응답 오류: ${res.status}`);
    }

    const result = await res.json();
    const finalText = result.rewritten ?? result.masked ?? result.text;

    if (payload.tabId && finalText != null) {
      chrome.tabs.sendMessage(payload.tabId, {
        type: 'FILL_REWRITTEN_TEXT',
        payload: { text: finalText }
      });
    }

    sendResponse({ ok: true, data: result });
  } catch (err) {
    console.error('[PersonaGuard] rewrite 요청 실패:', err);
    sendResponse({ ok: false, error: String(err) });
  }
}