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
  healthChoice: null, // 'mask' | 'keep'
  codeChoice: null,
  healthDecision: null, // 'accept' | 'keep'
  codeDecision: null
};

const app = document.getElementById('app');
const backBtn = document.getElementById('backBtn');
const screenTitle = document.getElementById('screenTitle');

function push(screen){ state.stack.push(screen); render(); }
function goBack(){ if(state.stack.length > 1){ state.stack.pop(); render(); } }
function restart(){
  state.stack = ['main'];
  state.healthChoice = null;
  state.codeChoice = null;
  state.healthDecision = null;
  state.codeDecision = null;
  closeNegotiationDialog();
  render();
}

backBtn.addEventListener('click', goBack);

function current(){ return state.stack[state.stack.length - 1]; }

function renderMain(){
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
      <p class="stats-title">오늘의 보호 현황</p>
      <div class="stats-row">
        <div class="stat-box">
          <p class="stat-num detect">12</p>
          <p class="stat-label">탐지 건수</p>
        </div>
        <div class="stat-box">
          <p class="stat-num mask">9</p>
          <p class="stat-label">마스킹 건수</p>
        </div>
      </div>
    </div>

    <div class="main-cta">
      <button class="btn-primary" id="goRisk">방금 감지된 프롬프트 확인하기</button>
    </div>
  `;
}

function renderRisk(){
  return `
    <div class="section">
      <p class="muted">이 프롬프트의 위험도</p>
      <p class="risk-level">높음</p>
      <div class="gauge-arrow-wrap"><div class="gauge-arrow"></div></div>
      <div class="gauge-bar">
        <div style="background:#97C459;"></div>
        <div style="background:#EF9F27;"></div>
        <div style="background:#E24B4A;"></div>
      </div>
      <div class="gauge-labels"><span>낮음</span><span>보통</span><span>높음</span></div>
      <p class="info-text">총 4건의 민감정보가 감지되었어요. 그중 2건은 직접 확인이 필요해요.</p>
    </div>
    <div class="section" style="border-bottom:none;">
      <p class="cat-list-title">카테고리별 감지 건수</p>
      <div class="cat-row">
        <div class="cat-left"><span class="dot" style="background:#1D9E75;"></span><span class="cat-label">고유식별정보 · 일반개인정보</span></div>
        <span class="cat-status">2건 · 자동처리</span>
      </div>
      <div class="cat-row">
        <div class="cat-left"><span class="dot" style="background:#BA7517;"></span><span class="cat-label">민감정보 (문맥형)</span></div>
        <span class="cat-status warn">1건 · 선택필요</span>
      </div>
      <div class="cat-row">
        <div class="cat-left"><span class="dot" style="background:#993C1D;"></span><span class="cat-label">기업 민감정보</span></div>
        <span class="cat-status danger">1건 · 선택필요</span>
      </div>
    </div>
    <div class="cta-wrap"><button class="btn-primary" id="goDetection">항목별로 확인하기</button></div>
  `;
}

function renderDetection(){
  const maskedCount = 2 + (state.healthChoice === 'mask' ? 1 : 0) + (state.codeChoice === 'mask' ? 1 : 0);
  const keptCount = (state.healthChoice === 'keep' ? 1 : 0) + (state.codeChoice === 'keep' ? 1 : 0);
  return `
    <p class="muted" style="padding:10px 16px 0;">정형 정보는 자동 마스킹되고, 문맥형 정보는 직접 선택할 수 있어요</p>
    <div style="padding:6px 16px 0;">
      <div class="detect-item">
        <div class="detect-head">
          <div class="detect-head-left"><span class="dot" style="background:#1D9E75;"></span><span class="detect-label">전화번호</span></div>
          <span class="auto-tag">자동 마스킹</span>
        </div>
        <p class="detect-sample">010-1234-5678 → <b>[PHONE]</b></p>
      </div>
      <div class="detect-item">
        <div class="detect-head">
          <div class="detect-head-left"><span class="dot" style="background:#1D9E75;"></span><span class="detect-label">이메일</span></div>
          <span class="auto-tag">자동 마스킹</span>
        </div>
        <p class="detect-sample">hong@company.com → <b>[EMAIL]</b></p>
      </div>
      <div class="detect-item">
        <div class="detect-head-left" style="display:flex;align-items:center;gap:8px;">
          <span class="dot" style="background:#BA7517;"></span><span class="detect-label">건강정보</span><span class="badge warn">선택 필요</span>
        </div>
        <p class="detect-quote">"우울증 약을 먹고 있어서..."</p>
        ${CheckboxSelector.renderChoiceRow('health', state.healthChoice)}
      </div>
      <div class="detect-item">
        <div class="detect-head-left" style="display:flex;align-items:center;gap:8px;">
          <span class="dot" style="background:#993C1D;"></span><span class="detect-label">사내 코드</span><span class="badge danger">선택 필요</span>
        </div>
        <p class="detect-quote">함수명 및 내부 API 키 포함</p>
        ${CheckboxSelector.renderChoiceRow('code', state.codeChoice)}
      </div>
    </div>
    <div style="padding:12px 16px 16px;">
      <p class="muted" style="margin:0 0 8px;">총 4건 감지 · 마스킹 ${maskedCount}건 · 원본유지 ${keptCount}건</p>
      <button class="btn-primary" id="goNegotiation">선택 적용하고 전송</button>
    </div>
  `;
}

function renderNegotiation(){
  const negotiationDone = !!(state.healthDecision && state.codeDecision);
  const decidedCount = (state.healthDecision ? 1 : 0) + (state.codeDecision ? 1 : 0);
  const healthLabel = state.healthDecision === 'accept' ? '제안 수락됨' : (state.healthDecision === 'keep' ? '원본 유지됨' : '미결정');
  const codeLabel = state.codeDecision === 'accept' ? '제안 수락됨' : (state.codeDecision === 'keep' ? '원본 유지됨' : '미결정');
  return `
    <p class="muted" style="padding:10px 16px 0;">AI가 제안한 표현을 검토하고 선택하세요</p>
    <div style="padding:12px 16px 4px;">
      <div class="negotiation-card">
        <div class="negotiation-head">
          <div class="detect-head-left"><span class="dot" style="background:#BA7517;"></span><span class="detect-label">건강정보</span></div>
          <span class="negotiation-status ${state.healthDecision?'done':''}">${healthLabel}</span>
        </div>
        <p class="muted" style="margin:0 0 3px;">원본</p>
        <p class="text-orig">우울증 약을 먹고 있어서 야근이 힘들 것 같아요</p>
        <div class="arrow-center"><i class="ti ti-arrow-down" aria-hidden="true"></i></div>
        <p class="muted" style="margin:0 0 3px;">AI 제안</p>
        <p class="text-suggest">건강상의 이유로 야근이 어려울 것 같아요</p>
        <div class="negotiation-actions">
          <button class="accept ${state.healthDecision==='accept'?'active':''}" id="acceptHealth">제안 수락</button>
          <button disabled>직접 수정</button>
          <button class="keep ${state.healthDecision==='keep'?'active':''}" id="keepHealth">원본 유지</button>
        </div>
      </div>
      <div class="negotiation-card">
        <div class="negotiation-head">
          <div class="detect-head-left"><span class="dot" style="background:#993C1D;"></span><span class="detect-label">사내 코드</span></div>
          <span class="negotiation-status ${state.codeDecision?'done':''}">${codeLabel}</span>
        </div>
        <p class="muted" style="margin:0 0 3px;">원본</p>
        <p class="text-orig">calcRiskScore() 함수에 API_KEY=sk-8x2... 하드코딩됨</p>
        <div class="arrow-center"><i class="ti ti-arrow-down" aria-hidden="true"></i></div>
        <p class="muted" style="margin:0 0 3px;">AI 제안</p>
        <p class="text-suggest">함수 로직 설명 (API 키 등 식별정보 제거)</p>
        <div class="negotiation-actions">
          <button class="accept ${state.codeDecision==='accept'?'active':''}" id="acceptCode">제안 수락</button>
          <button disabled>직접 수정</button>
          <button class="keep ${state.codeDecision==='keep'?'active':''}" id="keepCode">원본 유지</button>
        </div>
      </div>
    </div>
    <div class="cta-wrap">
      <p class="muted" style="margin:0 0 8px;">2건의 제안 중 ${decidedCount}건 결정됨</p>
      <button class="btn-primary" id="goRewrite" ${negotiationDone?'':'disabled'}>적용하고 계속하기</button>
    </div>
  `;
}

function renderRewrite(){
  return `
    <p class="muted" style="padding:10px 16px 0;">선택하신 내용을 반영해 안전하게 재작성했어요</p>
    <div style="padding:12px 16px 4px;">
      <p class="muted" style="margin:0 0 4px;">원본 프롬프트</p>
      <div class="rewrite-box orig">
        김철수입니다. 제 번호는 <mark class="pii-orig">010-1234-5678</mark>이고 이메일은 <mark class="pii-orig">hong@company.com</mark>이에요. 요즘 <mark class="pii-orig">우울증 약을 먹고 있어서 야근이 힘들 것</mark> 같은데, 팀장님께 보낼 메일 좀 다듬어주세요. 참고로 <mark class="pii-orig">calcRiskScore() 함수에 API_KEY=sk-8x2... 하드코딩된</mark> 부분도 리팩토링 제안해주세요.
      </div>
      <div class="arrow-center" style="gap:6px;">
        <i class="ti ti-arrow-down" style="color:#0F6E56;" aria-hidden="true"></i>
        <span style="font-size:10px;color:#0F6E56;">PersonaGuard 재작성</span>
      </div>
      <p class="muted" style="margin:0 0 4px;">재작성된 프롬프트</p>
      <div class="rewrite-box new">
        김철수입니다. 제 번호는 <mark class="pii-new">[PHONE]</mark>이고 이메일은 <mark class="pii-new">[EMAIL]</mark>이에요. <mark class="pii-new">건강상의 이유로 야근이 어려울 것</mark> 같은데, 팀장님께 보낼 메일 좀 다듬어주세요. 참고로 <mark class="pii-new">특정 함수에 API 키 등 식별정보가 하드코딩된</mark> 부분도 리팩토링 제안해주세요.
      </div>
    </div>
    <div class="chip-row">
      <span class="chip">전화번호 마스킹</span>
      <span class="chip">이메일 마스킹</span>
      <span class="chip">건강정보 재작성</span>
      <span class="chip">코드 재작성</span>
    </div>
    <div class="actions-2">
      <button class="btn-outline" id="backToNegotiation">다시 수정하기</button>
      <button class="btn-fill" id="goApprove">승인하고 전송</button>
    </div>
  `;
}

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

const topbar = document.querySelector('.topbar');

const renderers = { main: renderMain, risk: renderRisk, detection: renderDetection, rewrite: renderRewrite, sent: renderSent };

function render(){
  const scr = current();

  // 메인 화면은 자체 브랜드 헤더를 쓰므로 공통 상단바(뒤로가기+타이틀)를 숨김
  topbar.style.display = scr === 'main' ? 'none' : 'flex';
  screenTitle.textContent = TITLES[scr];
  backBtn.style.visibility = state.stack.length > 1 ? 'visible' : 'hidden';

  app.innerHTML = renderers[scr]();
  bindEvents(scr);
}

/* ===== 협상(Negotiation) 팝업(Dialog) ===== */
const negotiationDialog = document.getElementById('negotiationDialog');
const negotiationDialogBox = document.getElementById('negotiationDialogBox');

function openNegotiationDialog(){
  negotiationDialogBox.innerHTML = `
    <div class="dialog-header">
      <span class="dialog-title">${TITLES.negotiation}</span>
      <span class="dialog-close" id="closeNegotiationDialog" aria-label="닫기">&times;</span>
    </div>
    ${renderNegotiation()}
  `;
  negotiationDialog.classList.remove('hidden');
  bindNegotiationDialogEvents();
}

function closeNegotiationDialog(){
  negotiationDialog.classList.add('hidden');
}

function bindNegotiationDialogEvents(){
  document.getElementById('closeNegotiationDialog').onclick = closeNegotiationDialog;
  document.getElementById('acceptHealth').onclick = () => { state.healthDecision = 'accept'; openNegotiationDialog(); };
  document.getElementById('keepHealth').onclick = () => { state.healthDecision = 'keep'; openNegotiationDialog(); };
  document.getElementById('acceptCode').onclick = () => { state.codeDecision = 'accept'; openNegotiationDialog(); };
  document.getElementById('keepCode').onclick = () => { state.codeDecision = 'keep'; openNegotiationDialog(); };
  document.getElementById('goRewrite').onclick = () => {
    if(state.healthDecision && state.codeDecision){
      closeNegotiationDialog();
      push('rewrite');
    }
  };
}

function bindEvents(scr){
  if(scr === 'main'){
    document.getElementById('goRisk').onclick = () => push('risk');
    // TODO: 보호 on/off 상태 관리 로직은 담당자와 논의 후 연결 (지금은 UI만)
    document.getElementById('toggleProtect').onclick = () => {};
  } else if(scr === 'risk'){
    document.getElementById('goDetection').onclick = () => push('detection');
  } else if(scr === 'detection'){
    CheckboxSelector.bindChoiceRow(app, 'health', (value) => { state.healthChoice = value; render(); });
    CheckboxSelector.bindChoiceRow(app, 'code', (value) => { state.codeChoice = value; render(); });
    document.getElementById('goNegotiation').onclick = () => openNegotiationDialog();
  } else if(scr === 'rewrite'){
    document.getElementById('backToNegotiation').onclick = () => { goBack(); openNegotiationDialog(); };
    document.getElementById('goApprove').onclick = () => push('sent');
  } else if(scr === 'sent'){
    document.getElementById('restartBtn').onclick = () => restart();
  }
}


render();