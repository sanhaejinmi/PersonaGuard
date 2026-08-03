/**
 * approval_sender.js
 *
 * 팝업(result_panel.html) 쪽에서 실행되는 모듈.
 * 사용자가 협상(Negotiation) 화면에서 항목별로 "보호 적용(true)" / "원문 유지(false)"를
 * 정한 뒤, 그 결과를 백엔드(/rewrite)가 요구하는 decisions 형태로 만들어 전달한다.
 *
 * ⚠️ 실제 마스킹/치환/삭제 방식(무엇을 마스킹하고, 무엇을 치환하고, 무엇을 삭제할지)은
 *    이제 Extension이 아니라 백엔드 pipeline.run_rewrite()가 결정한다.
 *    Extension은 "이 항목을 보호할지 말지"만 boolean으로 넘기면 된다.
 *
 * decisions 형태 (백엔드 pipeline.py 기준):
 *   { "TYPE:start:end": true | false }
 *   예) { "PHONE:10:23": true, "NAME:0:3": false }
 *
 * ── 고유식별정보 강제 규칙 ──
 *   주민등록번호/여권번호/운전면허번호 등은 사용자가 false(원문 유지)를 선택해도
 *   무조건 true로 강제한다.
 *   ⚠️ 이상적으로는 백엔드가 Entity.tier 필드로 이걸 알려줘야 하지만
 *      (아직 미정, 논의 중) 그 전까지는 FORCED_MASK_TYPES로 프론트에서 임시 판단.
 *
 * result_panel.js에서는 이렇게 사용:
 *   const decisions = ApprovalSender.buildDecisions(analysis.entities, {
 *     '0': true, '1': false   // key: entities 배열의 index
 *   });
 *   const res = await ApprovalSender.requestRewrite(analysis.sessionId, decisions, analysis.tabId);
 *   // res.data 안에 최종 재작성 텍스트가 들어있음 (필드명은 백엔드 확정 후 조정 필요)
 */

const ApprovalSender = (function () {
  // ⚠️ 백엔드 Entity.tier 필드가 생기기 전까지 쓰는 임시 판단 기준.
  //    type 값이 실제 백엔드 pipeline과 맞는지 확인 필요.
  const FORCED_MASK_TYPES = new Set(['RRN', 'PASSPORT', 'DRIVER_LICENSE', 'NUM']);

  function isForcedMask(entity) {
    // 나중에 백엔드가 entity.tier === 1 같은 필드를 주면 그걸 우선 사용
    if (entity.tier != null) return entity.tier === 1;
    return FORCED_MASK_TYPES.has(entity.type);
  }

  /**
   * entities + 사용자의 항목별 boolean 선택을 백엔드가 요구하는 decisions 딕셔너리로 변환.
   *
   * @param {Array<{type:string, value:string, start:number, end:number, tier?:number}>} entities
   * @param {Object<string, boolean>} userChoices - key는 entities 배열의 index(문자열), value는 true(보호)/false(원문유지)
   * @returns {Object<string, boolean>} - key: "TYPE:start:end", value: boolean
   */
  function buildDecisions(entities, userChoices) {
    const decisions = {};

    entities.forEach((entity, idx) => {
      const key = `${entity.type}:${entity.start}:${entity.end}`;
      // 기본값: entity.default_masked(백엔드가 목적 필요성 판단 등으로 제안한 값).
      // 없으면(구버전 분석 결과 등) 보호(true)로 안전하게 fallback.
      let protect = userChoices[String(idx)] ?? entity.default_masked ?? true;

      if (isForcedMask(entity) && protect === false) {
        protect = true; // 고유식별정보는 원문 유지 선택 불가 → 강제 보호
      }

      decisions[key] = protect;
    });

    return decisions;
  }

  /**
   * 항목이 "그대로 전송(원문 유지)" 선택 가능한지 여부.
   * UI(checkbox_selector.js 등)에서 고유식별정보는 이 버튼 자체를 숨기거나 비활성화할 때 사용.
   */
  function canKeepOriginal(entity) {
    return !isForcedMask(entity);
  }

  /**
   * 백엔드 /rewrite에 최종 요청을 보낸다. (background.js가 실제 fetch를 수행)
   * @param {string} sessionId - /analyze 응답에 포함된 session_id
   * @param {Object<string, boolean>} decisions
   * @param {number|null} tabId - GET_LATEST_ANALYSIS로 받은 tabId
   */
  function requestRewrite(sessionId, decisions, tabId) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: 'REQUEST_REWRITE', payload: { sessionId, decisions, tabId } },
        (response) => resolve(response ?? { ok: false, error: '백그라운드로부터 응답 없음' })
      );
    });
  }

  /**
   * 팝업이 열릴 때 가장 최근 분석 결과를 background.js(storage)로부터 읽어온다.
   * 반환값: { original, masked, entities, candidates, session_id, tabId, analyzedAt } | null
   */
  async function getLatestAnalysis() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'GET_LATEST_ANALYSIS' }, (response) => {
        resolve(response?.data ?? null);
      });
    });
  }

  return { buildDecisions, canKeepOriginal, requestRewrite, getLatestAnalysis };
})();