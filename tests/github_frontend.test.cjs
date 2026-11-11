const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../frontend/js/github.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
function fixture(fetchRepos) {
  function element() {
    return {
      children: [], events: {}, hidden: false, textContent: '',
      appendChild(child) { this.children.push(child); },
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      addEventListener(type, handler) { this.events[type] = handler; },
      setAttribute() {},
    };
  }
  const elements = Object.fromEntries(['githubProjects', 'githubStatus', 'githubList', 'githubRetry', 'githubMore']
    .map(id => [id, element()]));
  const context = vm.createContext({
    document: { getElementById: id => elements[id], createElement: element },
    apiGetGithubRepos: fetchRepos, errorText: error => error.message,
  });
  vm.runInContext(source, context);
  return { ui: context.createGithubProjects(), showcase: context.createRepoShowcase, ...elements };
}
const repo = name => ({ name, url: `https://github.com/demo/${name}`, description: '<script>text</script>', language: 'Python' });

test('missing username shows guidance without a request', () => {
  let calls = 0;
  const view = fixture(async () => { calls++; });
  view.ui.setUsername('');
  assert.equal(calls, 0);
  assert.match(view.githubStatus.textContent, /Edit profil/);
  assert.equal(view.githubMore.hidden, true);
});

test('loads repositories and appends the next page', async () => {
  const pages = [];
  const view = fixture(async (username, page) => {
    pages.push(page);
    return { repositories: [repo(`repo-${page}`)], has_next: page === 1 };
  });
  view.ui.setUsername('demo');
  await flush();
  assert.equal(view.githubList.children.length, 1);
  assert.equal(view.githubList.children[0].children[1].textContent, '<script>text</script>');
  assert.equal(view.githubMore.hidden, false);
  await view.githubMore.events.click();
  assert.deepEqual(pages, [1, 2]);
  assert.equal(view.githubList.children.length, 2);
  assert.equal(view.githubMore.hidden, true);
});

test('errors preserve loaded repositories and retry the failed page', async () => {
  let fail = true;
  const view = fixture(async (username, page) => {
    if (page === 2 && fail) throw new Error('Rate limited');
    return { repositories: [repo(`repo-${page}`)], has_next: page === 1 };
  });
  view.ui.setUsername('demo');
  await flush();
  await view.githubMore.events.click();
  assert.equal(view.githubList.children.length, 1);
  assert.match(view.githubStatus.textContent, /Rate limited/);
  assert.equal(view.githubRetry.hidden, false);
  fail = false;
  await view.githubRetry.events.click();
  assert.equal(view.githubList.children.length, 2);
  assert.equal(view.githubRetry.hidden, true);
});

test('changing username ignores delayed results for the old owner', async () => {
  let finishOld;
  const view = fixture(username => username === 'old'
    ? new Promise(resolve => { finishOld = resolve; })
    : Promise.resolve({ repositories: [], has_next: false }));
  view.ui.setUsername('old');
  view.ui.setUsername('new');
  await flush();
  finishOld({ repositories: [repo('old-repo')], has_next: true });
  await flush();
  assert.equal(view.githubList.children.length, 0);
  assert.match(view.githubStatus.textContent, /@new/);
  assert.equal(view.githubMore.hidden, true);
});

test('unsafe repository URLs show an error instead of a clickable link', async () => {
  const view = fixture(async () => ({ repositories: [{ name: 'bad', url: 'javascript:alert(1)' }] }));
  view.ui.setUsername('demo');
  await flush();
  assert.equal(view.githubList.children.length, 0);
  assert.equal(view.githubRetry.hidden, false);
});

test('showcase displays at most three repos and reuses requests across roster renders', async () => {
  let calls = 0;
  const view = fixture(async () => {
    calls++;
    return { repositories: [repo('first'), repo('second'), repo('third'), repo('fourth')] };
  });
  const first = view.showcase('demo');
  const second = view.showcase('DEMO');
  await flush();
  assert.equal(calls, 1);
  for (const section of [first, second]) {
    const list = section.children[2];
    assert.equal(list.children.length, 3);
    assert.deepEqual(Array.from(list.children, item => item.children[0].textContent), ['first', 'second', 'third']);
    assert.equal(list.children[0].children[0].href, 'https://github.com/demo/first');
  }
});

test('showcase retries a failed request instead of caching the error', async () => {
  let fail = true;
  const view = fixture(async () => {
    if (fail) throw new Error('Offline');
    return { repositories: [repo('recovered')] };
  });
  const section = view.showcase('demo');
  await flush();
  assert.match(section.children[1].textContent, /Offline/);
  assert.equal(section.children[3].hidden, false);
  fail = false;
  await section.children[3].events.click();
  assert.equal(section.children[2].children.length, 1);
  assert.equal(section.children[3].hidden, true);
});
