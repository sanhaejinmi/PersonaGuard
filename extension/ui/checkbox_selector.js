/**
 * checkbox_selector.js
 * 감지 항목의 "마스킹 / 그대로 전송" 선택(pill 버튼) 렌더링과 이벤트 바인딩을 담당.
 * 상태(state) 자체는 갖지 않고, 현재 선택값을 받아 마크업을 그려주고
 * 클릭 시 콜백으로 선택값을 넘겨주는 역할만 함 (상태 관리는 result_panel.js가 소유).
 */
const CheckboxSelector = (function () {
  const OPTIONS = [
    { value: 'mask', label: '마스킹' },
    { value: 'keep', label: '그대로 전송' }
  ];

  /**
   * @param {string} groupId - 선택 그룹 식별자 (예: 'health', 'code')
   * @param {string|null} selectedValue - 현재 선택된 값 ('mask' | 'keep' | null)
   * @returns {string} choice-row HTML
   */
  function renderChoiceRow(groupId, selectedValue) {
    const pills = OPTIONS.map(opt => {
      const active = selectedValue === opt.value ? 'active' : '';
      return `<button class="pill ${active}" data-group="${groupId}" data-value="${opt.value}">${opt.label}</button>`;
    }).join('');
    return `<div class="choice-row">${pills}</div>`;
  }

  /**
   * container 내부에서 해당 groupId를 가진 pill 버튼들에 클릭 이벤트를 바인딩.
   * @param {HTMLElement} container - pill 버튼들을 포함하는 상위 엘리먼트 (보통 #app)
   * @param {string} groupId
   * @param {(value: string) => void} onSelect - 버튼 클릭 시 선택된 값을 전달받는 콜백
   */
  function bindChoiceRow(container, groupId, onSelect) {
    container.querySelectorAll(`.pill[data-group="${groupId}"]`).forEach(btn => {
      btn.onclick = () => onSelect(btn.dataset.value);
    });
  }

  return { renderChoiceRow, bindChoiceRow };
})();