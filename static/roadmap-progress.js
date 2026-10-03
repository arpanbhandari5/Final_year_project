/**
 * Prayash — Shared Roadmap Progress Engine
 * =========================================
 * A single source of truth for learning-roadmap progress, shared by the
 * authenticated Workplace (static/script.js) and the standalone guided flow
 * (static/career-analysis.js). Having one engine means progress is written
 * and read identically everywhere — no divergent copies, no key drift.
 *
 * Persistence is two-tier, mirroring the backend that already exists:
 *   1. localStorage  → instant, offline-friendly, device-local mirror.
 *   2. /api/roadmap-progress (GET/POST) → authoritative, per-account,
 *      backed by the existing ``roadmap_progress`` table (storage.py).
 *      Server values win on load so progress follows the user across devices.
 *
 * Progress is keyed ``"<targetRole>::<phaseIndex>::<itemIndex>"`` so the same
 * roadmap for the same target role resumes on any page. All methods are
 * defensive: a network/storage failure degrades to local-only, never throws.
 *
 * Exposed as ``window.RoadmapProgress``.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'prayash-roadmap-progress';

  // A single live state object that is *mutated in place* (never reassigned)
  // so any external reference (e.g. career-analysis.js's ``roadmapCompletion``)
  // always observes the current data.
  var state = {};
  var targetRole = '';
  var weeklyHours = 8;

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') || '' : '';
  }

  function progressKey(phaseIdx, itemIdx) {
    return (targetRole || 'default') + '::' + phaseIdx + '::' + itemIdx;
  }

  function readLocal() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      var parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function writeLocal() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      /* storage full / private mode — local mirror is best-effort */
    }
  }

  /** Point the engine at a target role (and optional weekly hours). */
  function configure(role, hours) {
    targetRole = String(role || '').trim() || 'default';
    var h = parseInt(hours, 10);
    if (Number.isFinite(h) && h > 0) weeklyHours = h;
    return targetRole;
  }

  /** Load local mirror, then merge the server's authoritative copy on top. */
  function load() {
    var local = readLocal();
    Object.keys(state).forEach(function (k) { delete state[k]; });
    Object.assign(state, local);
    writeLocal();

    if (!targetRole || targetRole === 'default') return Promise.resolve(state);

    return fetch('/api/roadmap-progress?target_role=' + encodeURIComponent(targetRole), {
      headers: { Accept: 'application/json' },
    })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (data && data.success && data.progress && data.progress.progress &&
            typeof data.progress.progress === 'object') {
          Object.assign(state, data.progress.progress); // server wins
          if (Number.isFinite(parseInt(data.progress.weekly_hours, 10))) {
            weeklyHours = parseInt(data.progress.weekly_hours, 10);
          }
          writeLocal();
        }
        return state;
      })
      .catch(function () { return state; });
  }

  /** Persist to the local mirror immediately, then to the server (best-effort). */
  function save() {
    writeLocal();
    if (!targetRole || targetRole === 'default') return Promise.resolve(false);
    return fetch('/api/roadmap-progress', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify({ target_role: targetRole, progress: state, weekly_hours: weeklyHours }),
    })
      .then(function (res) { return res.ok; })
      .catch(function () { return false; });
  }

  function isComplete(phaseIdx, itemIdx) {
    return !!state[progressKey(phaseIdx, itemIdx)];
  }

  function setComplete(phaseIdx, itemIdx, value) {
    var k = progressKey(phaseIdx, itemIdx);
    if (value) state[k] = true;
    else delete state[k];
    return !!state[k];
  }

  /** Flip an item's completion and persist. Returns the new completed state. */
  function toggle(phaseIdx, itemIdx) {
    var now = !isComplete(phaseIdx, itemIdx);
    setComplete(phaseIdx, itemIdx, now);
    save();
    return now;
  }

  // ── Stable, name-based completion ──────────────────────────────────
  // Index-based keys drift when a roadmap is regenerated (a skill moves
  // between phases), which would silently attach "done" to the wrong item.
  // These key by a stable identifier (e.g. a skill name) instead, scoped to
  // the configured target role so different roles never share progress.
  function slug(value) {
    return String(value || '')
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 80);
  }

  function itemKey(name) {
    return (targetRole || 'default') + '::item::' + slug(name);
  }

  function isDone(name) {
    return !!state[itemKey(name)];
  }

  function setDone(name, value) {
    var k = itemKey(name);
    if (value) state[k] = true;
    else delete state[k];
    return !!state[k];
  }

  /** Flip a name-keyed item's completion and persist. Returns new state. */
  function toggleKey(name) {
    var now = !isDone(name);
    setDone(name, now);
    save();
    return now;
  }

  /**
   * Completion roll-up for a phase mapping: each phase exposes ``skills`` or
   * ``stages`` (the two shapes used across pages).
   */
  function stats(phases) {
    var total = 0;
    var done = 0;
    (phases || []).forEach(function (phase, pIdx) {
      var items = phase.skills || phase.stages || [];
      items.forEach(function (skill, sIdx) {
        total++;
        var p = skill && skill._phaseIdx != null ? skill._phaseIdx : pIdx;
        var i = skill && skill._skillIdx != null ? skill._skillIdx : sIdx;
        if (isComplete(p, i)) done++;
      });
    });
    return { total: total, completed: done, pct: total ? Math.round((done / total) * 100) : 0 };
  }

  /**
   * Name-keyed roll-up over a flat list of named items (each ``{name}``).
   * Preferred for the personalized roadmap, where items are identified by
   * their stable skill name rather than a positional index.
   */
  function statsByKey(items) {
    var total = 0;
    var done = 0;
    (items || []).forEach(function (item) {
      var name = item && (item.name || item.skill || item.course);
      if (!name) return;
      total++;
      if (isDone(name)) done++;
    });
    return { total: total, completed: done, pct: total ? Math.round((done / total) * 100) : 0 };
  }

  /** Clear every item (in place) and persist. */
  function reset() {
    Object.keys(state).forEach(function (k) { delete state[k]; });
    return save();
  }

  window.RoadmapProgress = {
    configure: configure,
    load: load,
    save: save,
    isComplete: isComplete,
    setComplete: setComplete,
    toggle: toggle,
    isDone: isDone,
    setDone: setDone,
    toggleKey: toggleKey,
    stats: stats,
    statsByKey: statsByKey,
    reset: reset,
    key: progressKey,
    slug: slug,
    get state() { return state; },
    get targetRole() { return targetRole; },
    get weeklyHours() { return weeklyHours; },
  };
})();
