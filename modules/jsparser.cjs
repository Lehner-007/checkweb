/* Trusted, data-only Acorn adapter. Never executes inspected JavaScript. */
'use strict';
const fs = require('fs');
let acorn;
try { acorn = require('acorn'); }
catch (_) { process.stdout.write(JSON.stringify({unavailable:true})); process.exit(0); }

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = input.source;
function parseMode(mode) {
  return acorn.parse(source, {
    ecmaVersion: 'latest', sourceType: mode, locations: true,
    allowHashBang: true, allowReturnOutsideFunction: mode === 'script'
  });
}
function errorInfo(error) {
  return {message: String(error.message || 'Parsefehler').slice(0, 240),
          line: error.loc ? error.loc.line : 0,
          column: error.loc ? error.loc.column + 1 : 0};
}
let ast, mode = input.mode, ambiguous = false;
if (mode === 'auto') {
  try { ast = parseMode('script'); mode = 'script'; }
  catch (scriptError) {
    try { ast = parseMode('module'); mode = 'module'; ambiguous = true; }
    catch (moduleError) {
      process.stdout.write(JSON.stringify({ok:false, error:errorInfo(moduleError)}));
      process.exit(0);
    }
  }
} else {
  try { ast = parseMode(mode); }
  catch (error) {
    process.stdout.write(JSON.stringify({ok:false, error:errorInfo(error)}));
    process.exit(0);
  }
}

const nodes = [];
const MAX_AST_NODES = 100000;
function collect(node) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) { for (const item of node) collect(item); return; }
  if (typeof node.type === 'string') {
    nodes.push(node);
    if (nodes.length > MAX_AST_NODES) throw new Error('analysis_limit');
  }
  for (const [key, value] of Object.entries(node)) {
    if (key !== 'loc' && key !== 'start' && key !== 'end') collect(value);
  }
}
try { collect(ast); }
catch (_) {
  process.stdout.write(JSON.stringify({ok:false, limit:'ast_nodes'}));
  process.exit(0);
}

// If fetch is declared or shadowed anywhere, do not claim a global fetch call.
// This favors a missed possible reference over an invented network target.
function bindingHasName(node, name) {
  if (!node) return false;
  if (node.type === 'Identifier') return node.name === name;
  if (node.type === 'RestElement') return bindingHasName(node.argument, name);
  if (node.type === 'AssignmentPattern') return bindingHasName(node.left, name);
  if (node.type === 'ArrayPattern') return node.elements.some(x => bindingHasName(x, name));
  if (node.type === 'ObjectPattern') return node.properties.some(p => bindingHasName(p.value || p.argument, name));
  return false;
}
const fetchShadowed = nodes.some(n => n.type === 'VariableDeclarator' && bindingHasName(n.id,'fetch')) ||
  nodes.some(n => n.type === 'FunctionDeclaration' && n.id && n.id.name === 'fetch') ||
  nodes.some(n => ['ClassDeclaration','ClassExpression'].includes(n.type) && n.id && n.id.name === 'fetch') ||
  nodes.some(n => ['ImportSpecifier','ImportDefaultSpecifier','ImportNamespaceSpecifier'].includes(n.type) && n.local && n.local.name === 'fetch') ||
  nodes.some(n => n.type === 'CatchClause' && bindingHasName(n.param,'fetch')) ||
  nodes.some(n => n.type === 'AssignmentExpression' && n.left && n.left.type === 'Identifier' && n.left.name === 'fetch');
const fetchParameterRanges = nodes.filter(n => ['FunctionDeclaration','FunctionExpression','ArrowFunctionExpression'].includes(n.type) &&
  (n.params || []).some(p => bindingHasName(p,'fetch')) && n.body).map(n => [n.body.start,n.body.end]);

const xhrNames = new Set();
const reassigned = new Set();
for (const n of nodes) {
  if (n.type === 'VariableDeclarator' && n.id && n.id.type === 'Identifier' &&
      n.init && n.init.type === 'NewExpression' && n.init.callee.type === 'Identifier' &&
      n.init.callee.name === 'XMLHttpRequest') xhrNames.add(n.id.name);
  if (n.type === 'AssignmentExpression' && n.left && n.left.type === 'Identifier') reassigned.add(n.left.name);
  if (n.type === 'UpdateExpression' && n.argument && n.argument.type === 'Identifier') reassigned.add(n.argument.name);
}
for (const name of reassigned) xhrNames.delete(name);

function stringLiteral(node) {
  if (node && node.type === 'Literal' && typeof node.value === 'string') return node.value;
  if (node && node.type === 'TemplateLiteral' && node.expressions.length === 0)
    return node.quasis[0] && node.quasis[0].value.cooked;
  return null;
}
function methodFromOptions(node) {
  if (!node) return 'GET';
  if (node.type !== 'ObjectExpression') return null;
  let method = 'GET';
  for (const prop of node.properties) {
    if (prop.type === 'SpreadElement' || prop.computed) return null;
    const key = prop.key && (prop.key.name || prop.key.value);
    if (key === 'method') method = stringLiteral(prop.value);
  }
  return method && method.toUpperCase();
}
const refs = [];
const unverified = [];
let refsLimited = false;
function addRef(url, loc) {
  if (url && url.trim() && loc) {
    if (url.length <= 1024 && refs.length < 32)
      refs.push({url, line:loc.start.line, column:loc.start.column + 1});
    else refsLimited = true;
  }
}
for (const n of nodes) {
  if (n.type === 'ImportExpression') {
    const url=stringLiteral(n.source);
    if (url !== null) addRef(url,n.loc);
    else if (n.loc && unverified.length < 500)
      unverified.push({kind:'dynamic_import',line:n.loc.start.line,column:n.loc.start.column+1});
    continue;
  }
  if (['ImportDeclaration','ExportNamedDeclaration','ExportAllDeclaration'].includes(n.type) && n.source)
    addRef(stringLiteral(n.source),n.loc);
  if (n.type !== 'CallExpression') continue;
  let url = null;
  let candidate=false;
  if (n.callee.type === 'Identifier' && n.callee.name === 'fetch' && !fetchShadowed &&
      !fetchParameterRanges.some(([start,end]) => n.start>=start && n.end<=end)) {
    candidate=true;
    const method = methodFromOptions(n.arguments[1]);
    if (method === 'GET' || method === 'HEAD') url = stringLiteral(n.arguments[0]);
  } else if (n.callee.type === 'MemberExpression' &&
             ((!n.callee.computed && n.callee.property.type === 'Identifier' && n.callee.property.name === 'fetch') ||
              (n.callee.computed && stringLiteral(n.callee.property)==='fetch'))) {
    candidate=true;
  } else if (n.callee.type === 'MemberExpression' && !n.callee.computed &&
             n.callee.property.type === 'Identifier' && n.callee.property.name === 'open' &&
             n.callee.object.type === 'Identifier' && xhrNames.has(n.callee.object.name) &&
             n.arguments.length >= 2) {
    candidate=true;
    const method = stringLiteral(n.arguments[0]);
    if (method && ['GET','HEAD'].includes(method.toUpperCase())) url = stringLiteral(n.arguments[1]);
  }
  if (url !== null && url.trim() && n.loc) {
    if (url.length <= 1024 && refs.length < 32)
      refs.push({url, line:n.loc.start.line, column:n.loc.start.column + 1});
    else refsLimited = true;
  } else if (candidate && n.loc && unverified.length < 500) {
    unverified.push({kind:'dynamic_request',line:n.loc.start.line,column:n.loc.start.column+1});
  }
}
if (refsLimited && unverified.length < 500) unverified.push({kind:'analysis_limit',line:0,column:0});
process.stdout.write(JSON.stringify({ok:true, mode, ambiguous, refs, unverified}));
