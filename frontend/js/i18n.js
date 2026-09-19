/* i18n.js — Lightweight UI internationalisation
 *
 * Usage:
 *   await I18n.init();             // call once on DOMContentLoaded
 *   I18n.t('toast_new_chat');      // → translated string for current lang
 *   I18n.t('toast_lang_changed', { lang: 'Español' });  // with variable substitution
 *   I18n.setLang('es');            // switch language + re-render the page
 */

const I18n = (() => {
  let _strings = null;
  let _lang = "en";

  // Map of ISO code → display name used in toasts
  const LANG_NAMES = {
    en: "English",
    es: "Español",
    pt: "Português",
    fr: "Français",
    hi: "हिन्दी",
  };

  // Elements that carry a data-i18n="key" attribute get their textContent
  // replaced automatically.  Elements that carry data-i18n-placeholder="key"
  // get their placeholder attribute replaced.
  function _applyToDOM() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.dataset.i18n;
      el.textContent = t(key);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.dataset.i18nPlaceholder;
      el.setAttribute("placeholder", t(key));
    });
  }

  async function init() {
    try {
      const res = await fetch("i18n/strings.json");
      _strings = await res.json();
    } catch (e) {
      console.warn("[i18n] Could not load strings.json — falling back to keys.", e);
      _strings = {};
    }
  }

  /**
   * Translate a key, optionally substituting {variable} placeholders.
   * Falls back to the English string, then to the raw key.
   *
   * @param {string} key   - Key from strings.json  (e.g. "toast_new_chat")
   * @param {object} [vars] - Variable map           (e.g. { lang: "Español" })
   */
  function t(key, vars = {}) {
    if (!_strings) return key;

    let text =
      (_strings[_lang] && _strings[_lang][key]) ||
      (_strings["en"] && _strings["en"][key]) ||
      key;

    Object.entries(vars).forEach(([k, v]) => {
      text = text.replace(`{${k}}`, v);
    });

    return text;
  }

  /**
   * Switch the active language, persist to sessionStorage, and re-render
   * all data-i18n elements in the DOM.
   */
  function setLang(code) {
    _lang = code || "en";
    try { sessionStorage.setItem("ci_lang", _lang); } catch (_) {}
    _applyToDOM();
  }

  function getLang() { return _lang; }
  function getLangName(code) { return LANG_NAMES[code || _lang] || code; }

  return { init, t, setLang, getLang, getLangName };
})();
