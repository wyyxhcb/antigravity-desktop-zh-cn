/* Local-only translation data and matching, shared by DOM and native menu labels. */
const agZh = (() => {
  'use strict';
  const exact = /*__ZH_CN_DICTIONARY__*/ {};
  const patternData = /*__ZH_CN_PATTERNS__*/ [];
  const normalize = value => value.trim().replace(/\s+/g, ' ').replace(/…/g, '...').replace(/[‘’]/g, "'").replace(/[“”]/g, '"');
  const normalized = new Map(Object.entries(exact).map(([k,v]) => [normalize(k),v]));
  const patterns = patternData.map(item => [new RegExp(item.regex, item.flags || ''), item.replacement]);
  const cache = new Map();
  function translate(value) {
    if (typeof value !== 'string' || !value || value.length > 2500 || !/[A-Za-z]/.test(value)) return value;
    if (cache.has(value)) return cache.get(value);
    const key = value.trim();
    let result = Object.prototype.hasOwnProperty.call(exact,key) ? exact[key] : normalized.get(normalize(key));
    if (result === undefined) {
      for (const [regex,replacement] of patterns) {
        regex.lastIndex=0;
        if (regex.test(key)) { regex.lastIndex=0; result=key.replace(regex,replacement); break; }
      }
    }
    const output = result === undefined ? value : value.slice(0,value.indexOf(key))+result+value.slice(value.indexOf(key)+key.length);
    if (cache.size >= 4096) cache.clear();
    cache.set(value,output);
    return output;
  }
  function menu(items) {
    if (!Array.isArray(items)) return items;
    return items.map(item => {
      if (!item || typeof item !== 'object') return item;
      const translated={...item};
      if (typeof item.label === 'string') translated.label=translate(item.label);
      if (Array.isArray(item.submenu)) translated.submenu=menu(item.submenu);
      return translated;
    });
  }
  function knownStatic(value) {
    const key=value.trim();
    return key.length>=16 && (Object.prototype.hasOwnProperty.call(exact,key) || normalized.has(normalize(key)));
  }
  return Object.freeze({translate,menu,normalize,knownStatic});
})();
