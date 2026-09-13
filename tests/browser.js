const results = document.querySelector('#results');
const frame = document.querySelector('#app');
const checks = [];
function assert(condition, message) {
  if (!condition) throw new Error(message);
  checks.push(message);
}
function settle() {
  return new Promise(resolve => setTimeout(resolve, 50));
}
frame.onload = async function () {
  try {
    const w = frame.contentWindow;
    const d = frame.contentDocument;
    const find = selector => d.querySelector(selector);
    const key = (node, value) =>
      node.dispatchEvent(new w.KeyboardEvent('keydown', { key: value, bubbles: true, cancelable: true }));
    assert(d.querySelectorAll('#rows tr').length === 25, '25 deployments by default');
    assert(!w.injected && !find('#rows img'), 'Deployment messages render as text');
    find('#select').click();
    assert(find('#selected').textContent === '25 selected', 'Select visible selects one page');
    find('#next').click();
    assert(!find('#rows input:checked'), 'Next page has no unintended selection');
    find('#send').click();
    await settle();
    assert(
      w.sent[0].includes('25 Vercel') && !w.sent[0].includes('"id": "d25"'),
      'Deletion prompt contains only selected IDs'
    );
    find('#refresh').click();
    await settle();
    assert(
      w.sent[1].includes('"project":"demo"') && w.sent[1].includes('preserve the project'),
      'Refresh preserves restricted project'
    );
    find('#project-trigger').click();
    const input = find('.picker-search');
    input.value = 'empty';
    input.dispatchEvent(new w.Event('input'));
    key(input, 'Enter');
    assert(
      find('#empty').hidden === false && find('#selected').textContent === '0 selected',
      'Empty project clears selection'
    );
    find('#project-trigger').click();
    input.value = 'no matches';
    input.dispatchEvent(new w.Event('input'));
    assert(!find('.picker-empty').hidden, 'Project search has empty state');
    key(input, 'Escape');
    assert(d.activeElement === find('#project-trigger'), 'Escape restores focus');
    find('#project-trigger').click();
    input.value = 'demo';
    input.dispatchEvent(new w.Event('input'));
    key(input, 'Enter');
    find('.badge').focus();
    assert(find('#deployment-tooltip:popover-open'), 'Keyboard focus opens status tooltip');
    find('#target-trigger').click();
    assert(
      d.querySelectorAll(':popover-open').length === 1 && find('#target-panel:popover-open'),
      'Tooltip and dropdown do not overlap'
    );
    key(find('#target-list'), 'End');
    key(find('#target-list'), 'Enter');
    assert(find('#target').value === 'preview', 'Environment supports keyboard selection');
    find('#target-trigger').click();
    key(find('#target-list'), 'Home');
    key(find('#target-list'), 'Enter');
    for (const width of [320, 390, 720, 1440]) {
      frame.style.width = width + 'px';
      await settle();
      find('#project-trigger').click();
      await settle();
      const rect = find('#project-panel').getBoundingClientRect();
      assert(
        rect.left >= 0 && rect.right <= width && d.documentElement.scrollWidth <= width,
        `Layout and dropdown fit ${width}px`
      );
      const style = w.getComputedStyle(input);
      assert(
        style.borderTopWidth === '0px' && style.borderBottomWidth === '1px' && style.borderTopLeftRadius === '5px',
        `Inset search corners and border at ${width}px`
      );
      key(input, 'Escape');
    }
    frame.onload = null;
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin');
    const original = JSON.parse(fixture.match(/const data = (.*);/)[1]);
    let variants = 0;
    for (const width of [320, 390, 736, 1024, 1440]) {
      for (const count of [0, 1, 25, 26, 60]) {
        for (const bridge of [false, true]) {
          for (const detached of [false, true]) {
            for (const theme of ['light', 'dark']) {
              const data = structuredClone(original);
              data.projects[0].deployments = data.projects[0].deployments.slice(0, count);
              let html = fixture.replace(
                /const data = .*;/,
                () => `const data = ${JSON.stringify(data).replaceAll('<', '\\u003c')};`
              );
              if (!bridge) html = html.replace(/<script>window.sent=[\s\S]*?<\/script>/, '');
              if (detached) {
                const scripts = [];
                html =
                  html.replace(/<script>[\s\S]*?<\/script>/g, script => {
                    scripts.push(script);
                    return '';
                  }) + scripts.join('');
              }
              frame.style.width = width + 'px';
              await new Promise((resolve, reject) => {
                const timer = setTimeout(() => reject(new Error('Fresh render timed out')), 3000);
                frame.onload = () => {
                  clearTimeout(timer);
                  resolve();
                };
                frame.srcdoc = `<style>:root {color-scheme:${theme}}</style>` + html;
              });
              const d = frame.contentDocument;
              const label = `${width}px, ${count} deployments, bridge=${bridge}, detached=${detached}, ${theme}`;
              assert(d.querySelectorAll('#rows tr').length === Math.min(count, 25), `First render: ${label}`);
              d.querySelector('#select').click();
              assert(d.querySelector('#selected').textContent === `${Math.min(count, 25)} selected`, `Selection: ${label}`);
              assert(!d.querySelector('#rows img'), `Escaping: ${label}`);
              variants++;
            }
          }
        }
      }
    }
    assert(variants === 200, '200 independent first-render variants passed');
    results.textContent = 'PASS\n' + checks.join('\n');
    document.title = 'PASS — Shear browser tests';
  } catch (error) {
    results.textContent = 'FAIL\n' + error.stack + '\nPassed:\n' + checks.join('\n');
    document.title = 'FAIL — Shear browser tests';
  }
};
frame.srcdoc = fixture;
