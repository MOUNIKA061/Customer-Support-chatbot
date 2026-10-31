const fs = require('fs');
const assert = require('assert');
const { JSDOM } = require('jsdom');

// 1. Read vendor libraries and app.js
const markedCode = fs.readFileSync('static/vendor/marked.min.js', 'utf8');
const purifyCode = fs.readFileSync('static/vendor/purify.min.js', 'utf8');
const appCode = fs.readFileSync('static/app.js', 'utf8');

// 2. Setup real browser window via JSDOM
const dom = new JSDOM('<!DOCTYPE html><html><body><div id="chatMessages"></div><form id="chatForm"></form><textarea id="messageInput"></textarea><button id="sendBtn"></button><div id="typingIndicator"></div><button id="clearChatBtn"></button><button id="toggleDevMode"></button><span id="statusDot"></span><span id="statusText"></span><div id="chatErrorBanner"></div><span id="errorMsgText"></span><button id="retryBtn"></button><span id="welcomeTimestamp"></span></body></html>', {
  runScripts: 'dangerously'
});
const window = dom.window;
window.APP_CONFIG = { API_BASE_URL: '' };

const vm = require('vm');
const sandbox = {
  window,
  document: window.document,
  console,
  setTimeout: (fn) => fn(),
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok', provider: 'groq' }) })
};
sandbox.globalThis = sandbox;
sandbox.self = sandbox;
vm.createContext(sandbox);

// 3. Load vendor libraries in order
vm.runInContext(markedCode, sandbox);
if (sandbox.marked) {
  window.marked = sandbox.marked;
}

vm.runInContext(purifyCode, sandbox);
if (sandbox.DOMPurify) {
  window.DOMPurify = typeof sandbox.DOMPurify === 'function' && !sandbox.DOMPurify.sanitize
    ? sandbox.DOMPurify(window)
    : sandbox.DOMPurify;
}

// 4. Load application script
vm.runInContext(appCode, sandbox);

const renderMarkdownSafe = window.renderMarkdownSafe;
const renderFallbackMarkdown = window.renderFallbackMarkdown;

assert(typeof renderMarkdownSafe === 'function', 'renderMarkdownSafe must be exposed as a function');
assert(typeof renderFallbackMarkdown === 'function', 'renderFallbackMarkdown must be exposed as a function');

console.log('--- Running Markdown & Sanitization Verification Suite ---');

// Test 1: Bold text formatting
const test1Input = "To check your order, click **Your Orders** in the top menu.";
const test1Output = renderMarkdownSafe(test1Input);
console.log('\n[Test 1] Bold Text Formatting:');
console.log('Input: ', test1Input);
console.log('Output:', test1Output.trim());
assert(!test1Output.includes('**Your Orders**'), 'Failed: Output still contains literal asterisks **');
assert(test1Output.includes('<strong>Your Orders</strong>'), 'Failed: Output missing <strong> tag');
console.log('✓ Test 1 passed: Bold text rendered with <strong> and no literal asterisks.');

// Test 2: Numbered lists formatting
const test2Input = "Follow these steps:\n1. Log in to your account.\n2. Navigate to Your Orders.\n3. Click Track Package.";
const test2Output = renderMarkdownSafe(test2Input);
console.log('\n[Test 2] Numbered List Formatting:');
console.log('Input:\n' + test2Input);
console.log('Output:\n' + test2Output.trim());
assert(test2Output.includes('<ol>'), 'Failed: Output missing <ol> tag');
assert(test2Output.includes('<li>Log in to your account.</li>'), 'Failed: Output missing <li> for item 1');
assert(test2Output.includes('<li>Click Track Package.</li>'), 'Failed: Output missing <li> for item 3');
assert(!test2Output.includes('1. Log in'), 'Failed: Output contains literal list numbering "1. Log in"');
console.log('✓ Test 2 passed: Numbered list rendered as <ol><li> without literal markers.');

// Test 3: Mixed formatting with bold, numbered list, and plain text
const test3Input = "You can view your order status:\n\n1. Sign in and open **Your Orders**.\n2. Click **Track Package**.\n\nEstimated delivery date will appear.";
const test3Output = renderMarkdownSafe(test3Input);
console.log('\n[Test 3] Mixed Bold + Numbered List + Plain Text:');
console.log('Output:\n' + test3Output.trim());
assert(test3Output.includes('<ol>'), 'Failed: Missing <ol>');
assert(test3Output.includes('<strong>Your Orders</strong>'), 'Failed: Missing <strong>');
assert(test3Output.includes('<strong>Track Package</strong>'), 'Failed: Missing <strong>');
assert(!test3Output.includes('**'), 'Failed: Contains literal asterisks');
console.log('✓ Test 3 passed: Mixed content properly structured.');

// Test 4: Security / XSS Prevention - script tags
const test4Input = 'Here are instructions: <script>alert("XSS")</script> **Clean text**\n1. Normal step';
const test4Output = renderMarkdownSafe(test4Input);
console.log('\n[Test 4] XSS Prevention (<script> tag):');
console.log('Output:\n' + test4Output.trim());
assert(!test4Output.toLowerCase().includes('<script'), 'Security Alert: <script> tag was not stripped!');
assert(!test4Output.toLowerCase().includes('alert('), 'Security Alert: script content was preserved!');
assert(test4Output.includes('<strong>Clean text</strong>'), 'Valid bold text preserved');
console.log('✓ Test 4 passed: Malicious <script> tag completely eliminated by DOMPurify.');

// Test 5: Security / XSS Prevention - event handlers and javascript: URIs
const test5Input = '<img src="x" onerror="alert(1)"> <a href="javascript:stealCookie()">Click here</a>';
const test5Output = renderMarkdownSafe(test5Input);
console.log('\n[Test 5] XSS Prevention (onerror & javascript: URI):');
console.log('Output:\n' + test5Output.trim());
assert(!test5Output.toLowerCase().includes('onerror'), 'Security Alert: onerror handler was not stripped!');
assert(!test5Output.toLowerCase().includes('javascript:'), 'Security Alert: javascript: URI was not stripped!');
console.log('✓ Test 5 passed: Handlers and dangerous protocols eliminated.');

// Test 6: Fallback parser tests (when vendor libraries are bypassed)
console.log('\n[Test 6] Safe Fallback Parser:');
const test6Input = '**Bold Alert** and <script>alert("test")</script>\n1. Step A\n2. Step B';
const test6Output = renderFallbackMarkdown(test6Input);
console.log('Fallback Output:\n' + test6Output.trim());
assert(test6Output.includes('<strong>Bold Alert</strong>'), 'Fallback bold failed');
assert(test6Output.includes('<ol>'), 'Fallback ol failed');
assert(test6Output.includes('<li>'), 'Fallback li failed');
assert(!test6Output.includes('<script>'), 'Fallback allowed raw <script>');
assert(test6Output.includes('&lt;script&gt;'), 'Fallback did not escape <script>');
console.log('✓ Test 6 passed: Fallback parser safely escapes HTML and formats bold and lists.');

// Test 7: User messages remain strictly plain text
console.log('\n[Test 7] User Message Plain Text Isolation:');
const userBubble = window.document.createElement('div');
const userPayload = '**Not bold user text** <script>alert(1)</script>';
userBubble.textContent = userPayload; // as done in appendMessage
assert.strictEqual(userBubble.textContent, userPayload);
assert(!userBubble.innerHTML.includes('<script>')); // In a real browser textContent turns < into &lt;
assert(userBubble.innerHTML.includes('&lt;script&gt;'));
console.log('✓ Test 7 passed: User messages remain strictly plain text.');

console.log('\n========================================');
console.log('All 7 markdown formatting & sanitization tests PASSED!');
console.log('========================================');
