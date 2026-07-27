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
  rewrite: '재작성 결과',
  sent: '전송 완료'
};

const state = {
  stack: ['main'],
  analysis: null,   // { original, masked, entities, candidates, session_id, tabId, analyzedAt } | null
  choices: {},      // { [entityIndex:string]: true(보호/마스킹) | false(원문유지) }
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
  const entities = state.analysis?.entities ?? [];
  entities.forEach((entity, idx) => {
    // 기본값: 보호(true, 마스킹). 고유식별정보는 항상 true로 강제됨(ApprovalSender가 처리).
    state.choices[String(idx)] = true;
  });
}

async function loadAnalysis(){
  state.loading = true;
  render();
  try {
    const data = await ApprovalSender.getLatestAnalysis();
    state.analysis = data;
    initChoicesFromAnalysis();
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
      <p class="protect-title">보호 중이에요</p>
      <p class="protect-desc">입력하는 개인정보를 실시간으로 감지해요</p>
      <button class="protect-off-btn" id="toggleProtect">보호 끄기</button>
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
    // ⚠️ candidates[idx]가 entities[idx]와 매칭된다는 가정. 백엔드팀 확인 필요.
    const suggestion = candidates[idx] ?? '(재작성 제안 없음)';

    return `
      <div class="negotiation-card">
        <div class="negotiation-head">
          <div class="detect-head-left"><span class="dot" style="background:${forced ? '#993C1D' : '#BA7517'};"></span><span class="detect-label">${entity.type}</span></div>
          <span class="negotiation-status ${isMasked ? 'done' : ''}">${forced ? '강제 보호' : (isMasked ? '마스킹 적용' : '원본 유지')}</span>
        </div>
        <p class="muted" style="margin:0 0 3px;">원본</p>
        <p class="text-orig">${entity.value}</p>
        <div class="arrow-center"><i class="ti ti-arrow-down" aria-hidden="true"></i></div>
        <p class="muted" style="margin:0 0 3px;">AI 제안</p>
        <p class="text-suggest">${suggestion}</p>
        ${forced ? '' : `
        <div class="negotiation-actions">
          <button class="accept ${isMasked ? 'active' : ''}" data-idx="${idx}" data-mode="mask">마스킹 적용</button>
          <button disabled>직접 수정</button>
          <button class="keep ${!isMasked ? 'active' : ''}" data-idx="${idx}" data-mode="keep">원본 유지</button>
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

function bindNegotiationDialogEvents(){
  document.getElementById('closeNegotiationDialog').onclick = closeNegotiationDialog;

  negotiationDialogBox.querySelectorAll('button[data-idx]').forEach((btn) => {
    btn.onclick = () => {
      const idx = btn.dataset.idx;
      state.choices[idx] = btn.dataset.mode === 'mask';
      openNegotiationDialog();
    };
  });

  document.getElementById('goRewrite').onclick = async () => {
    state.rewriteLoading = true;
    state.rewriteError = null;
    openNegotiationDialog();

    const decisions = ApprovalSender.buildDecisions(getEntities(), state.choices);
    const res = await ApprovalSender.requestRewrite(
      state.analysis?.session_id,
      decisions,
      state.analysis?.tabId
    );

    state.rewriteLoading = false;

    if (!res.ok) {
      state.rewriteError = '재작성 요청에 실패했어요. (백엔드 /rewrite 연동 전이면 정상입니다)';
      openNegotiationDialog();
      return;
    }

    const data = res.data ?? {};
    state.rewriteResult = data.rewritten ?? data.masked ?? data.text ?? null;
    closeNegotiationDialog();
    push('rewrite');
  };
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

const renderers = { main: renderMain, risk: renderRisk, detection: renderDetection, rewrite: renderRewrite, sent: renderSent };

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
    document.getElementById('toggleProtect').onclick = () => {};
  } else if(scr === 'risk'){
    document.getElementById('goDetection').onclick = () => push('detection');
  } else if(scr === 'detection'){
    getEntities().forEach((entity, idx) => {
      if (!ApprovalSender.canKeepOriginal(entity)) return;
      CheckboxSelector.bindChoiceRow(app, String(idx), (value) => {
        state.choices[String(idx)] = value === 'mask';
        render();
      });
    });
    document.getElementById('goNegotiation').onclick = () => openNegotiationDialog();
  } else if(scr === 'rewrite'){
    document.getElementById('backToNegotiation').onclick = () => { goBack(); openNegotiationDialog(); };
    document.getElementById('goApprove').onclick = () => push('sent');
  } else if(scr === 'sent'){
    document.getElementById('restartBtn').onclick = () => restart();
  }
}

loadAnalysis();