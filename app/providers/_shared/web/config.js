'use strict';

(function () {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get('lang') || 'en';
  const language = /^[a-z]{2}(?:-[A-Z]{2})?$/.test(requested)
    ? requested : 'en';

  async function loadPack(code) {
    const response = await fetch(
      '/api/languages/' + encodeURIComponent(code) + '.json',
      { credentials: 'same-origin', cache: 'no-store' }
    );
    if (!response.ok) throw new Error('Language pack unavailable: ' + code);
    const pack = await response.json();
    if (!pack || !pack.interface || typeof pack.interface !== 'object') {
      throw new Error('Invalid language pack: ' + code);
    }
    return pack;
  }

  window.OCNotifierI18nReady = (async function () {
    let selected;
    try {
      selected = await loadPack(language);
    } catch (error) {
      selected = await loadPack('en');
    }

    let english = selected;
    if (language !== 'en') {
      try {
        english = await loadPack('en');
      } catch (error) {
        english = selected;
      }
    }

    document.documentElement.lang = selected.code || language;

    window.OCNotifierI18n = {
      language: selected.code || language,
      t: function (key) {
        return selected.interface[key] ??
          english.interface[key] ??
          key;
      }
    };

    return window.OCNotifierI18n;
  })();
})();
