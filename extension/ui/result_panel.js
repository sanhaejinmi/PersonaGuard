/**
 * result_panel.js
 *
 * ⚠️ 이 파일은 이제 하드코딩된 값 대신, ApprovalSender.getLatestAnalysis()로
 *    background.js(chrome.storage)에 저장된 실제 /analyze 결과를 읽어와 화면을 그린다.
 *
 * 여전히 임시/가정으로 처리한 부분들 (백엔드 확정되면 수정 필요):
 *  - 위험도(risk_level): 백엔드 스키마에 아직 없어서, 감지 건수 기준으로 프론트에서 임시 산정
 *  - "오늘의 탐지/마스킹 통계"(메인 화면): 일별 누적 통계 API가 아직 없어서, 이번 분석 1건 기준으로만 표시
 *  - 협상 화면의 "AI 제안" 문구: candidates 배열이 entities와 몇 번째로 매칭되는지 백엔드팀 확인 필요.
 *    지금은 같은 index로 매칭한다고 가정.
 */

const TITLES = {
  main: '',
  risk: '위험 분석',
  detection: '감지 내역',
  negotiation: '협상 · 안전한 표현 제안',
  custom_rewrite: '직접 재작성',
  rewrite_loading: '재작성 중',
  rewrite: '재작성 결과',
  sent: '전송 완료'
};

const state = {
  stack: ['main'],
  analysis: null,   // { original, masked, entities, candidates, session_id, tabId, analyzedAt } | null
  choices: {},      // { [entityIndex:string]: true(보호/마스킹) | false(원문유지) }
  entityMode: {},   // { [entityIndex:string]: 'mask' | 'keep' | 'custom' } - 협상 카드 버튼 활성 표시용
  isProtected: true, // 보호 활성화 여부 (기본값: true)
  customRewriteText: null, // (레거시, 더 이상 사용 안 함 - 엔티티 단위 수정으로 대체됨)
  customEditIdx: null,       // 지금 협상 카드 중 어떤 엔티티(index)를 직접 수정 중인지
  customEntityValues: {},    // { [entityIndex:string]: 사용자가 입력한 대체 텍스트 }
  rewriteResult: null, // /rewrite 응답으로 받은 최종 텍스트
  loading: true,
  rewriteLoading: false,
  rewriteError: null
};

const app = document.getElementById('app');
const backBtn = document.getElementById('backBtn');
const screenTitle = document.getElementById('screenTitle');
const topbar = document.querySelector('.topbar');

function push(screen){ state.stack.push(screen); render(); }
function goBack(){ if(state.stack.length > 1){ state.stack.pop(); render(); } }
function restart(){
  state.stack = ['main'];
  state.rewriteResult = null;
  state.rewriteError = null;
  initChoicesFromAnalysis();
  closeNegotiationDialog();
  render();
}

backBtn.addEventListener('click', goBack);

function current(){ return state.stack[state.stack.length - 1]; }

/* ===== 데이터 로딩 ===== */

function initChoicesFromAnalysis(){
  state.choices = {};
  state.customEntityValues = {}; // 새 분석 결과면 이전 직접수정 내용도 초기화
  state.entityMode = {}; // idx별 현재 선택 모드: 'mask' | 'keep' | 'custom'
  const entities = state.analysis?.entities ?? [];
  entities.forEach((entity, idx) => {
    // 기본값은 백엔드가 제안한 entity.default_masked를 따른다 — ADDRESS/ORGANIZATION은
    // 목적 필요성 판단 결과로 true/false가 갈릴 수 있음. 필드가 없으면(구버전 분석
    // 결과 등) 보호(true)로 안전하게 fallback. 고유식별정보는 항상 true로 강제됨
    // (ApprovalSender가 처리).
    const defaultMasked = entity.default_masked ?? true;
    state.choices[String(idx)] = defaultMasked;
    state.entityMode[String(idx)] = defaultMasked ? 'mask' : 'keep';
  });
}

async function loadAnalysis(){
  state.loading = true;
  render();
  try {
    const data = await ApprovalSender.getLatestAnalysis();
    state.analysis = data;
    initChoicesFromAnalysis();
    
    // storage에서 보호 상태 읽기
    await new Promise((resolve) => {
      chrome.storage.local.get('personaguard:protection_enabled', (result) => {
        state.isProtected = result['personaguard:protection_enabled'] !== false;
        resolve();
      });
    });
  } catch (err) {
    console.error('[PersonaGuard] 분석 결과 로딩 실패:', err);
    state.analysis = null;
  } finally {
    state.loading = false;
    render();
  }
}

/* ===== 파생 데이터 ===== */

function getEntities(){
  return state.analysis?.entities ?? [];
}

function getForcedCount(){
  return getEntities().filter((e) => !ApprovalSender.canKeepOriginal(e)).length;
}

function getOptionalCount(){
  return getEntities().filter((e) => ApprovalSender.canKeepOriginal(e)).length;
}

// ⚠️ 백엔드에 risk_level 필드가 아직 없어서, 감지 건수 기준으로 임시 산정.
function computeRiskLevel(){
  const forced = getForcedCount();
  const total = getEntities().length;
  if (forced > 0) return { label: '높음', color: '#A32D2D', gaugePos: '83%' };
  if (total > 0) return { label: '보통', color: '#BA7517', gaugePos: '50%' };
  return { label: '낮음', color: '#1D9E75', gaugePos: '15%' };
}

/* ===== 화면: 메인 ===== */

function renderMain(){
  const total = getEntities().length;
  const maskedCount = getEntities().filter((e, idx) => state.choices[String(idx)]).length;
  const isProtected = state.isProtected !== false; // 기본값: true (보호 중)

  return `
    <div class="main-header">
      <div class="main-header-left">
        <div class="main-logo"><i class="ti ti-shield-check" aria-hidden="true"></i></div>
        <span class="main-brand">PersonaGuard</span>
      </div>
      <i class="ti ti-settings main-settings" aria-hidden="true"></i>
    </div>

    <div class="protect-card">
      <div class="protect-icon-outer">
        <div class="protect-icon-inner"><i class="ti ti-shield-check" aria-hidden="true"></i></div>
      </div>
      <p class="protect-title">${isProtected ? '보호 중이에요' : '보호 꺼짐'}</p>
      <p class="protect-desc">${isProtected ? '입력하는 개인정보를 실시간으로 감지해요' : '민감정보 감지가 비활성화되었습니다'}</p>
      <button class="protect-off-btn" id="toggleProtect">${isProtected ? '보호 끄기' : '보호 켜기'}</button>
    </div>

    <div class="stats-section">
      <p class="stats-title">최근 분석 현황</p>
      <div class="stats-row">
        <div class="stat-box">
          <p class="stat-num detect">${total}</p>
          <p class="stat-label">탐지 건수</p>
        </div>
        <div class="stat-box">
          <p class="stat-num mask">${maskedCount}</p>
          <p class="stat-label">마스킹 건수</p>
        </div>
      </div>
    </div>

    <div class="main-cta">
      <button class="btn-primary" id="goRisk" ${total === 0 ? 'disabled' : ''}>
        ${total === 0 ? '아직 감지된 프롬프트가 없어요' : '방금 감지된 프롬프트 확인하기'}
      </button>
      <button class="btn-outline" id="quickRewrite" style="margin-top:8px;width:100%;" ${total === 0 ? 'disabled' : ''}>
        바로 재작성하기
      </button>
    </div>
  `;
}

/* ===== 화면: 위험 분석 ===== */

function renderRisk(){
  const entities = getEntities();
  const total = entities.length;
  const forced = getForcedCount();
  const optional = getOptionalCount();
  const risk = computeRiskLevel();

  // 타입별로 묶어서 카테고리 행을 만듦
  const byType = {};
  entities.forEach((e) => {
    byType[e.type] = (byType[e.type] ?? 0) + 1;
  });
  const categoryRows = Object.entries(byType).map(([type, count]) => {
    const sampleEntity = entities.find((e) => e.type === type);
    const forcedType = sampleEntity && !ApprovalSender.canKeepOriginal(sampleEntity);
    return `
      <div class="cat-row">
        <div class="cat-left"><span class="dot" style="background:${forcedType ? '#993C1D' : '#1D9E75'};"></span><span class="cat-label">${type}</span></div>
        <span class="cat-status ${forcedType ? 'danger' : ''}">${count}건 · ${forcedType ? '자동처리' : '선택필요'}</span>
      </div>
    `;
  }).join('');

  return `
    <div class="section">
      <p class="muted">이 프롬프트의 위험도</p>
      <p class="risk-level" style="color:${risk.color};">${risk.label}</p>
      <div class="gauge-arrow-wrap"><div class="gauge-arrow" style="left:${risk.gaugePos};"></div></div>
      <div class="gauge-bar">
        <div style="background:#97C459;"></div>
        <div style="background:#EF9F27;"></div>
        <div style="background:#E24B4A;"></div>
      </div>
      <div class="gauge-labels"><span>낮음</span><span>보통</span><span>높음</span></div>
      <p class="info-text">총 ${total}건의 민감정보가 감지되었어요. 그중 ${optional}건은 직접 확인이 필요해요.</p>
    </div>
    <div class="section" style="border-bottom:none;">
      <p class="cat-list-title">카테고리별 감지 건수</p>
      ${categoryRows || '<p class="muted">감지된 항목이 없어요.</p>'}
    </div>
    <div class="cta-wrap"><button class="btn-primary" id="goDetection" ${total === 0 ? 'disabled' : ''}>항목별로 확인하기</button></div>
  `;
}

/* ===== 화면: 감지 내역 ===== */

function renderDetection(){
  const entities = getEntities();
  const maskedCount = entities.filter((e, idx) => state.choices[String(idx)]).length;
  const keptCount = entities.length - maskedCount;

  const items = entities.map((entity, idx) => {
    const forced = !ApprovalSender.canKeepOriginal(entity);
    const isMasked = state.choices[String(idx)];

    if (forced) {
      return `
        <div class="detect-item">
          <div class="detect-head">
            <div class="detect-head-left"><span class="dot" style="background:#993C1D;"></span><span class="detect-label">${entity.type}</span></div>
            <span class="auto-tag">자동 마스킹</span>
          </div>
          <p class="detect-sample">${entity.value} → <b>보호됨</b></p>
        </div>
      `;
    }

    return `
      <div class="detect-item">
        <div class="detect-head-left" style="display:flex;align-items:center;gap:8px;">
          <span class="dot" style="background:#BA7517;"></span><span class="detect-label">${entity.type}</span>
        </div>
        <p class="detect-quote">"${entity.value}"</p>
      </div>
    `;
  }).join('');

  return `
    <p class="muted" style="padding:10px 16px 0;">고유식별정보는 자동 마스킹되고, 그 외 항목은 직접 선택할 수 있어요</p>
    <div style="padding:6px 16px 0;">
      ${items || '<p class="muted">감지된 항목이 없어요.</p>'}
    </div>
    <div style="padding:12px 16px 16px;">
      <p class="muted" style="margin:0 0 8px;">총 ${entities.length}건 감지 · 마스킹 ${maskedCount}건 · 원본유지 ${keptCount}건</p>
      <button class="btn-primary" id="goNegotiation" ${entities.length === 0 ? 'disabled' : ''}>다음</button>
    </div>
  `;
}

/* ===== 협상 Dialog ===== */

function renderNegotiationCards(){
  const entities = getEntities();
  const candidates = state.analysis?.candidates ?? [];

  return entities.map((entity, idx) => {
    const forced = !ApprovalSender.canKeepOriginal(entity);
    const isMasked = state.choices[String(idx)];
    const mode = state.entityMode[String(idx)] ?? (isMasked ? 'mask' : 'keep');
    const hasCustom = mode === 'custom' && state.customEntityValues[String(idx)] != null;
    // ⚠️ candidates[idx]가 entities[idx]와 매칭된다는 가정. 백엔드팀 확인 필요.
    const suggestion = hasCustom ? state.customEntityValues[String(idx)] : (candidates[idx] ?? '(재작성 제안 없음)');
    const suggestionLabel = hasCustom ? '직접 수정' : 'AI 제안';
    const statusLabel = forced ? '강제 보호' : (hasCustom ? '직접 수정 적용' : (isMasked ? '마스킹 적용' : '원본 유지'));

    return `
      <div class="negotiation-card">
        <div class="negotiation-head">
          <div class="detect-head-left"><span class="dot" style="background:${forced ? '#993C1D' : '#BA7517'};"></span><span class="detect-label">${entity.type}</span></div>
          <span class="negotiation-status ${isMasked ? 'done' : ''}">${statusLabel}</span>
        </div>
        <p class="muted" style="margin:0 0 3px;">원본</p>
        <p class="text-orig">${entity.value}</p>
        <div class="arrow-center"><i class="ti ti-arrow-down" aria-hidden="true"></i></div>
        <p class="muted" style="margin:0 0 3px;">${suggestionLabel}</p>
        <p class="text-suggest">${suggestion}</p>
        ${forced ? '' : `
        <div class="negotiation-actions">
          <button class="accept ${mode === 'mask' ? 'active' : ''}" style="${mode === 'mask' ? 'background:#0F6E56;color:#fff;border-color:#0F6E56;' : ''}" data-idx="${idx}" data-mode="mask">마스킹 적용</button>
          <button class="edit ${mode === 'custom' ? 'active' : ''}" style="${mode === 'custom' ? 'background:#0F6E56;color:#fff;border-color:#0F6E56;' : ''}" data-idx="${idx}" id="editBtn-${idx}">직접 수정</button>
          <button class="keep ${mode === 'keep' ? 'active' : ''}" style="${mode === 'keep' ? 'background:#0F6E56;color:#fff;border-color:#0F6E56;' : ''}" data-idx="${idx}" data-mode="keep">원본 유지</button>
        </div>`}
      </div>
    `;
  }).join('');
}

function openNegotiationDialog(){
  negotiationDialogBox.innerHTML = `
    <div class="dialog-header">
      <span class="dialog-title">${TITLES.negotiation}</span>
      <span class="dialog-close" id="closeNegotiationDialog" aria-label="닫기">&times;</span>
    </div>
    <div style="padding:12px 16px 4px;">
      ${renderNegotiationCards()}
    </div>
    <div class="cta-wrap">
      <p class="muted" style="margin:0 0 8px;" id="rewriteErrorMsg">${state.rewriteError ? state.rewriteError : ''}</p>
      <button class="btn-primary" id="goRewrite" ${state.rewriteLoading ? 'disabled' : ''}>
        ${state.rewriteLoading ? '재작성 중...' : '적용하고 계속하기'}
      </button>
    </div>
  `;
  negotiationDialog.classList.remove('hidden');
  bindNegotiationDialogEvents();
}

function closeNegotiationDialog(){
  negotiationDialog.classList.add('hidden');
}

/**
 * 재작성 화면(rewrite / rewrite_loading)에서 협상 다이얼로그로 돌아갈 때 쓰는 함수.
 * 어떤 경로(일반 협상 경로 vs 바로 재작성하기)로 들어왔든 상관없이
 * rewrite / rewrite_loading을 스택에서 걷어내고 detection 화면 위에서 다이얼로그를 연다.
 */
function returnToNegotiation(){
  while (current() === 'rewrite' || current() === 'rewrite_loading') {
    state.stack.pop();
  }
  if (current() !== 'detection') {
    push('detection'); // render() 포함됨
  } else {
    render();
  }
  openNegotiationDialog();
}

/**
 * AI 기본 판단(state.choices의 기본값)대로 바로 재작성 요청을 보낸다.
 * 협상 화면을 거치지 않고 main에서 바로 호출될 수 있음.
 */
async function performQuickRewrite(){
  state.rewriteError = null;
  push('rewrite_loading');

  const decisions = ApprovalSender.buildDecisions(getEntities(), state.choices, state.customEntityValues);
  const res = await ApprovalSender.requestRewrite(
    state.analysis?.session_id,
    decisions,
    state.analysis?.tabId
  );

  if (!res.ok) {
    state.rewriteError = '재작성 요청에 실패했어요. (백엔드 /rewrite 연동 전이면 정상입니다)';
    returnToNegotiation(); // 실패 시 세부 조정할 수 있게 협상 화면으로
    return;
  }

  const data = res.data ?? {};
  state.rewriteResult = data.rewritten ?? data.masked ?? data.text ?? null;
  push('rewrite');
}

function bindNegotiationDialogEvents(){
  document.getElementById('closeNegotiationDialog').onclick = closeNegotiationDialog;

  // 마스킹 적용 / 원본 유지 버튼
  negotiationDialogBox.querySelectorAll('button[data-mode]').forEach((btn) => {
    btn.onclick = () => {
      const idx = btn.dataset.idx;
      const mode = btn.dataset.mode; // 'mask' | 'keep'
      state.choices[idx] = mode === 'mask';
      state.entityMode[idx] = mode;
      delete state.customEntityValues[idx]; // 직접 수정 값이 있었다면 해제 (모드 전환)
      openNegotiationDialog();
    };
  });

  // 직접 수정 버튼
  negotiationDialogBox.querySelectorAll('button.edit').forEach((btn) => {
    btn.onclick = () => {
      state.customEditIdx = btn.dataset.idx; // 어떤 카드를 수정 중인지 기억
      closeNegotiationDialog();
      push('custom_rewrite');
    };
  });

  document.getElementById('goRewrite').onclick = async () => {
    state.rewriteError = null;
    closeNegotiationDialog();
    
    // 직접 수정한 텍스트가 있으면, 그걸 다시 분석해야 함
    if (state.customRewriteText) {
      push('rewrite_loading');
      
      try {
        // 1. 직접 수정 텍스트를 새로 분석
        const analyzeRes = await fetch('http://127.0.0.1:8000/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: state.customRewriteText })
        });
        
        if (!analyzeRes.ok) {
          throw new Error('직접 수정 텍스트 분석 실패');
        }
        
        const newAnalysis = await analyzeRes.json();
        const newSession = {
          original: state.customRewriteText,
          items: newAnalysis.entities.map((e, idx) => ({
            type: e.type,
            value: e.value,
            start: e.start,
            end: e.end,
            tier: e.tier ?? 3
          }))
        };
        
        // 2. 새로운 entities에 decisions 적용
        const decisions = {};
        newAnalysis.entities.forEach((e, idx) => {
          const key = `${e.type}:${e.start}:${e.end}`;
          decisions[key] = true; // 직접 수정 텍스트의 모든 항목은 보호 처리
        });
        
        // 3. /rewrite 호출 (새로운 텍스트 기준)
        const rewriteRes = await fetch('http://127.0.0.1:8000/rewrite', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: state.analysis?.session_id,
            decisions: decisions,
            custom_text: state.customRewriteText  // 백엔드가 처리 필요
          })
        });
        
        if (!rewriteRes.ok) {
          throw new Error('재작성 요청 실패');
        }
        
        const data = await rewriteRes.json();
        state.rewriteResult = data.rewritten ?? data.masked ?? data.text ?? null;
        push('rewrite');
      } catch (err) {
        state.rewriteError = err.message || '직접 수정 텍스트 처리 실패';
        returnToNegotiation();
      }
      return;
    }

    // 직접 수정이 없으면 기존 로직
    push('rewrite_loading');

    const decisions = ApprovalSender.buildDecisions(getEntities(), state.choices, state.customEntityValues);
    const res = await ApprovalSender.requestRewrite(
      state.analysis?.session_id,
      decisions,
      state.analysis?.tabId
    );

    if (!res.ok) {
      state.rewriteError = '재작성 요청에 실패했어요. (백엔드 /rewrite 연동 전이면 정상입니다)';
      returnToNegotiation();
      return;
    }

    const data = res.data ?? {};
    state.rewriteResult = data.rewritten ?? data.masked ?? data.text ?? null;
    push('rewrite');
  };
}

/* ===== 화면: 직접 재작성 ===== */

function renderCustomRewrite(){
  const idx = state.customEditIdx;
  const entity = getEntities()[Number(idx)];
  const candidates = state.analysis?.candidates ?? [];
  const defaultSuggestion = candidates[idx] ?? '';
  const currentText = state.customEntityValues[idx] ?? defaultSuggestion;

  return `
    <p class="muted" style="padding:10px 16px 0;">이 항목을 원하는 표현으로 직접 바꿀 수 있어요</p>
    <div style="padding:12px 16px 4px;">
      <p class="muted" style="margin:0 0 6px;">원본</p>
      <div class="rewrite-box orig">${escapeHtml(entity?.value ?? '')}</div>
      <p class="muted" style="margin:12px 0 6px;">바꿀 표현</p>
      <textarea id="customRewriteInput" class="custom-rewrite-textarea">${escapeHtml(currentText)}</textarea>
    </div>
    <div class="actions-2">
      <button class="btn-outline" id="cancelCustomRewrite">취소</button>
      <button class="btn-fill" id="saveCustomRewrite">저장</button>
    </div>
  `;
}

/* ===== 화면: 재작성 로딩 ===== */

function renderRewriteLoading(){
  const maskedCount = getEntities().filter((e, idx) => state.choices[String(idx)]).length;
  const keptCount = getEntities().length - maskedCount;

  return `
    <div class="section" style="text-align:center;padding:48px 16px;">
      <div class="loading-spinner">
        <div class="spinner-circle"></div>
      </div>
      <p class="loading-title">프롬프트를 안전하게 재작성하고 있어요</p>
      <p class="loading-desc">마스킹 ${maskedCount}건 · 원본유지 ${keptCount}건이 적용됩니다</p>
    </div>
  `;
}

/* ===== 화면: 재작성 결과 ===== */

function renderRewrite(){
  const original = state.analysis?.original ?? '';
  const rewritten = state.rewriteResult ?? '(재작성된 텍스트를 받지 못했어요)';

  return `
    <p class="muted" style="padding:10px 16px 0;">선택하신 내용을 반영해 안전하게 재작성했어요</p>
    <div style="padding:12px 16px 4px;">
      <p class="muted" style="margin:0 0 4px;">원본 프롬프트</p>
      <div class="rewrite-box orig">${escapeHtml(original)}</div>
      <div class="arrow-center" style="gap:6px;">
        <i class="ti ti-arrow-down" style="color:#0F6E56;" aria-hidden="true"></i>
        <span style="font-size:10px;color:#0F6E56;">PersonaGuard 재작성</span>
      </div>
      <p class="muted" style="margin:0 0 4px;">재작성된 프롬프트</p>
      <div class="rewrite-box new">${escapeHtml(rewritten)}</div>
    </div>
    <div class="actions-2">
      <button class="btn-outline" id="backToNegotiation">다시 수정하기</button>
      <button class="btn-fill" id="goApprove" ${!state.rewriteResult ? 'disabled' : ''}>승인하고 전송</button>
    </div>
  `;
}

function escapeHtml(str){
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ===== 화면: 전송 완료 ===== */

function renderSent(){
  return `
    <div class="sent">
      <div class="sent-icon"><i class="ti ti-check" aria-hidden="true"></i></div>
      <p class="sent-title">안전하게 전송됐어요</p>
      <p class="sent-desc">민감정보가 마스킹된 프롬프트가 전달되었습니다</p>
      <button class="btn-outline" style="width:100%;" id="restartBtn">처음부터 다시 보기</button>
    </div>
  `;
}

/* ===== 로딩 화면 ===== */

function renderLoading(){
  return `<div class="section" style="text-align:center;padding:48px 16px;"><p class="muted">분석 결과를 불러오는 중...</p></div>`;
}

/* ===== 렌더 총괄 ===== */

const renderers = { main: renderMain, risk: renderRisk, detection: renderDetection, custom_rewrite: renderCustomRewrite, rewrite_loading: renderRewriteLoading, rewrite: renderRewrite, sent: renderSent };

function render(){
  const scr = current();

  topbar.style.display = scr === 'main' ? 'none' : 'flex';
  screenTitle.textContent = TITLES[scr];
  backBtn.style.visibility = state.stack.length > 1 ? 'visible' : 'hidden';

  app.innerHTML = state.loading ? renderLoading() : renderers[scr]();
  if (!state.loading) bindEvents(scr);
}

const negotiationDialog = document.getElementById('negotiationDialog');
const negotiationDialogBox = document.getElementById('negotiationDialogBox');

function bindEvents(scr){
  if(scr === 'main'){
    document.getElementById('goRisk').onclick = () => push('risk');

    const quickBtn = document.getElementById('quickRewrite');
    if (quickBtn) {
      quickBtn.onclick = () => performQuickRewrite();
    }

    const toggleBtn = document.getElementById('toggleProtect');
    if (toggleBtn) {
      toggleBtn.onclick = () => {
        state.isProtected = !state.isProtected;
        chrome.storage.local.set({ 'personaguard:protection_enabled': state.isProtected });
        render();
      };
    }
  } else if(scr === 'risk'){
    document.getElementById('goDetection').onclick = () => push('detection');
  } else if(scr === 'detection'){
    getEntities().forEach((entity, idx) => {
      if (!ApprovalSender.canKeepOriginal(entity)) return;
      CheckboxSelector.bindChoiceRow(app, String(idx), (value) => {
        state.choices[String(idx)] = value === 'mask';
        state.entityMode[String(idx)] = value === 'mask' ? 'mask' : 'keep';
        delete state.customEntityValues[String(idx)];
        render();
      });
    });
    document.getElementById('goNegotiation').onclick = () => openNegotiationDialog();
  } else if(scr === 'custom_rewrite'){
    const textarea = document.getElementById('customRewriteInput');
    document.getElementById('saveCustomRewrite').onclick = () => {
      const idx = state.customEditIdx;
      state.customEntityValues[idx] = textarea.value;
      state.choices[idx] = true; // 직접 수정한 값은 적용(마스킹)된 것으로 처리
      state.entityMode[idx] = 'custom';
      state.customEditIdx = null;
      goBack(); // 협상 다이얼로그로 돌아가기
      openNegotiationDialog();
    };
    document.getElementById('cancelCustomRewrite').onclick = () => {
      state.customEditIdx = null;
      goBack(); // 협상 다이얼로그로 돌아가기
      openNegotiationDialog();
    };
  } else if(scr === 'rewrite'){
    document.getElementById('backToNegotiation').onclick = () => returnToNegotiation();
    document.getElementById('goApprove').onclick = () => {
      // 최종 텍스트를 content_script로 전달
      chrome.runtime.sendMessage({
        type: 'FILL_APPROVED_TEXT',
        payload: {
          text: state.rewriteResult,
          tabId: state.analysis?.tabId
        }
      });
      push('sent');
    };
  } else if(scr === 'sent'){
    document.getElementById('restartBtn').onclick = () => restart();
  }
}

loadAnalysis();