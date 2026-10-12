/* Scout: Pulse's mascot.
 *
 * Concept 03 ("Scout") from the user's snowman sheet, rendered in 3D: two
 * ivory clay snowballs, the Optic aperture inset as each eye with the logo's
 * chart line raised inside it, a carved smile, a muted gold scarf blowing in
 * the wind, stub arms and feet. (The Pulse mark was tried as his whole face
 * and set aside for the two eyes.) The renders are transparent frames, one
 * sprite per size and density (static/scout/, made by
 * optic-brand/scout/render_scout.py, which also writes frames.json, the
 * order FRAME below copies). Every frame shares
 * one camera and one light rig, so a blink or a turn is a change of picture,
 * never a stretched one.
 *
 * Two sizes of the same poses:
 *   full     the whole figure, the welcome figure in the empty chat
 *   compact  a bust with the right arm, beside the reply being written
 *
 * A snowman lived in this panel once before (removed 2026-09-24 as "creepy")
 * and tests/test_pulse_mark.py still forbids its class names. Scout is a
 * different figure from the user's own concept art, under its own names.
 *
 * WHAT MOVES HIM. Pulse's real events, passed in by app.js, never a loop of
 * its own: the panel opening (one wave), typing (a curious tilt, once, not per
 * key), a question sent (one acknowledging wave, then thinking), a search the
 * server reports (a look around), the first words of the answer (stillness),
 * the end (a small nod), an error (a gentle concerned face). Between events
 * he blinks every 5-10 s (open, half, closed, half, open), now and then
 * twice, and, idle, now and then looks curious: the head tilts and one eye
 * opens a little wider. His scarf's tail flutters in the
 * wind while he is on screen with motion set to Full. Nothing he does says anything
 * about a market: no pose reads as up, down, sure or unsure, and the end of an
 * answer gets a nod, never a celebration.
 *
 * One timer per figure, and it runs only while the figure is on screen in a
 * visible tab; the scarf's CSS loop runs only under the same condition (the
 * is-windy class). A figure removed from the page stops itself on its next
 * tick.
 *
 * MOTION SETTING. full, subtle (poses and single blinks, no gestures) or
 * still (the resting frame only). Remembered per device; with nothing chosen
 * it follows prefers-reduced-motion, so a reader who asked their system for
 * less motion gets a still Scout without asking twice.
 *
 * A classic script loaded before app.js, as knowledge.js is, exposing
 * window.OpticScout. Nothing is fetched but the sprites, from this site.
 */

(function (global) {
  'use strict';

  var FRAME = {
    'idle': 0, 'idle-half': 1, 'idle-closed': 2,
    'lean': 3,
    'tilt': 4, 'tilt-half': 5, 'tilt-closed': 6,
    'curious': 7, 'curious-half': 8, 'curious-closed': 9,
    'arm-1': 10, 'arm-2': 11, 'arm-3': 12,
    'look-l1': 13, 'look-l2': 14, 'look-r1': 15, 'look-r2': 16,
    'nod-1': 17, 'nod-2': 18,
    'concerned': 19, 'concerned-half': 20, 'concerned-closed': 21,
  };
  var COUNT = 22;

  /* How far over the head is, so a change of pose walks through the frames
   * in between instead of jumping: upright, leaning, tilted, curious. */
  var LEVEL = { 'lean': 1, 'look-l1': 1, 'look-l2': 1, 'look-r1': 1, 'look-r2': 1,
    'tilt': 2, 'tilt-half': 2, 'tilt-closed': 2,
    'curious': 3, 'curious-half': 3, 'curious-closed': 3 };
  var LADDER = ['idle', 'lean', 'tilt', 'curious'];

  /* Each resting pose has its own half-closed and closed lid, so a blink
   * never changes the pose it happens in. */
  var FACE = {
    idle: ['idle', 'idle-half', 'idle-closed'],
    tilt: ['tilt', 'tilt-half', 'tilt-closed'],
    curious: ['curious', 'curious-half', 'curious-closed'],
    concerned: ['concerned', 'concerned-half', 'concerned-closed'],
  };
  var POSE = {
    idle: 'idle', listening: 'tilt', thinking: 'tilt', searching: 'tilt',
    streaming: 'idle', error: 'concerned',
  };

  /* Gestures, as [frame, ms]. Short on purpose. */
  var GESTURE = {
    wave: [['arm-1', 60], ['arm-2', 60], ['arm-3', 130], ['arm-2', 80], ['arm-3', 130],
      ['arm-2', 75], ['arm-1', 60]],
    ack: [['arm-1', 55], ['arm-2', 105], ['arm-1', 55]],
    nod: [['nod-1', 90], ['nod-2', 170], ['nod-1', 90]],
    look: [['look-l1', 120], ['look-l2', 520], ['look-l1', 110], ['lean', 90],
      ['look-r1', 120], ['look-r2', 520], ['look-r1', 110], ['lean', 90]],
    curious: [['curious', 1300], ['curious-half', 40], ['curious-closed', 50],
      ['curious-half', 40], ['curious', 280]],
    point: [['arm-1', 80], ['arm-2', 950], ['arm-1', 80]],
    bob: [['lean', 260]],
  };
  /* The ladder level each gesture starts from: upright for the arm and the
   * nod, leaning for a look around, tilted for the curious look. */
  var GESTURE_FROM = { wave: 0, ack: 0, nod: 0, point: 0, look: 1, curious: 3, bob: 2 };

  var STORE = 'optic.scout.motion.v1';
  var reduceQuery = global.matchMedia ? global.matchMedia('(prefers-reduced-motion: reduce)') : null;

  function choice() {
    try {
      var v = global.localStorage.getItem(STORE);
      return v === 'full' || v === 'subtle' || v === 'still' ? v : null;
    } catch (e) { return null; }
  }
  function motion() {
    return choice() || (reduceQuery && reduceQuery.matches ? 'still' : 'full');
  }

  function html(opts) {
    opts = opts || {};
    var cls = 'scout ' + (opts.size === 'compact' ? 'scout-compact' : 'scout-full');
    /* The box has a fixed aspect ratio in CSS, so it holds its space before
     * the sprite arrives and nothing near it moves when it does. */
    var fig = '<span class="' + cls + '" aria-hidden="true" data-frame="idle"></span>';
    if (!opts.label) return fig;
    return '<button type="button" class="scout-btn" aria-haspopup="menu" aria-expanded="false"'
      + ' aria-label="' + opts.label + '">' + fig + '</button>';
  }

  var live = [];
  var io = global.IntersectionObserver ? new global.IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      var c = e.target.scoutCtl;
      if (!c) return;
      c.visible = e.isIntersecting;
      c.reported = true;
      if (c.visible) c.wake(); else c.sleep();
    });
  }) : null;

  function rand(lo, hi) { return lo + Math.random() * (hi - lo); }

  function Ctl(el, slot) {
    this.el = el;
    this.slot = slot || null;
    this.state = 'idle';
    this.frameName = 'idle';
    this.seq = null;        // the running gesture or transition
    this.idleT = null;      // the next blink / curious look
    this.visible = !io;
    this.reported = !io;    // whether the observer has measured him yet
    this.pending = null;    // a gesture asked for just before he came on screen
    this.lastCurious = 0;
  }

  Ctl.prototype.alive = function () {
    if (this.el.isConnected) return true;
    this.stop();
    return false;
  };
  Ctl.prototype.running = function () {
    return this.visible && !document.hidden && motion() !== 'still' && this.alive();
  };
  Ctl.prototype.show = function (name) {
    this.frameName = name;
    this.el.setAttribute('data-frame', name);
    this.el.style.setProperty('--scout-x', (FRAME[name] / (COUNT - 1) * 100).toFixed(4) + '%');
  };
  Ctl.prototype.pose = function () {
    return motion() === 'still' ? 'idle' : POSE[this.state] || 'idle';
  };
  Ctl.prototype.level = function () { return LEVEL[FACE[this.pose()][0]] || 0; };
  Ctl.prototype.rest = function () { this.show(FACE[this.pose()][0]); };

  Ctl.prototype.cancel = function () {
    clearTimeout(this.seq);
    this.seq = null;
  };

  /* Play frames one after another, then `then`. Off screen, or with motion
   * set to still, the frames are skipped and `then` runs at once, so a state
   * change is never lost and he is never left mid-gesture. */
  Ctl.prototype.run = function (steps, then) {
    var self = this;
    this.cancel();
    if (!this.running() || !steps.length) { if (then) then(); else this.rest(); return; }
    var i = 0;
    (function next() {
      if (!self.alive()) return;
      if (i >= steps.length) { self.seq = null; if (then) then(); else self.rest(); return; }
      var s = steps[i++];
      self.show(s[0]);
      self.seq = setTimeout(next, s[1]);
    })();
  };

  /* The frames between the current pose and level `to` on the ladder. */
  Ctl.prototype.path = function (to) {
    var from = LEVEL[this.frameName] || 0;
    var out = [];
    var step = from < to ? 1 : -1;
    for (var l = from + step; step > 0 ? l < to : l > to; l += step) out.push([LADDER[l], 70]);
    return out;
  };

  /* Change state. `via` names a gesture to enter it by (a question in:
   * the acknowledging wave; an answer done: the nod); the gesture ends in
   * the new state's pose. */
  Ctl.prototype.set = function (state, via) {
    if (!this.alive()) return;
    // The same state again (a second "searching" event, another key) is
    // not news: nothing restarts.
    if (state === this.state && !via) return;
    this.state = state;
    this.pending = null;
    var self = this;
    clearTimeout(this.idleT);
    if (via) { this.gesture(via); return; }
    this.run(this.path(this.level()), function () {
      self.rest();
      if (state === 'searching') self.gesture('look');
      else self.schedule();
    });
  };

  /* A gesture, then back to the pose of the current state. Subtle and still
   * motion have none: the state's pose alone carries it. */
  Ctl.prototype.gesture = function (name, then) {
    if (!this.alive()) return;
    var self = this;
    var done = function () { self.rest(); self.schedule(); if (then) then(); };
    if (motion() !== 'full') { done(); return; }
    if (!this.running()) {
      // Asked for as he comes on screen (the panel opening, a figure just
      // redrawn and not yet measured): play it when he is, if that is soon.
      // Until then he keeps the frame he has, so the new state's pose does
      // not flash up ahead of the gesture that leads into it.
      if (motion() === 'full' && (!this.reported || name === 'wave' || name === 'ack')) {
        this.pending = { name: name, at: Date.now(), then: then };
      } else { this.rest(); if (then) then(); }
      return;
    }
    clearTimeout(this.idleT);
    this.idleT = null;
    this.run(this.path(GESTURE_FROM[name] || 0).concat(GESTURE[name]), function () {
      self.run(self.path(self.level()), done);
    });
  };

  Ctl.prototype.blink = function (twice) {
    var f = FACE[this.pose()];
    var steps = [[f[1], 35], [f[2], 50], [f[1], 40]];
    if (twice) steps = steps.concat([[f[0], 120]], steps);
    var self = this;
    this.run(steps, function () { self.rest(); self.schedule(); });
  };

  /* The next thing he does on his own: a blink, now and then two, and idle,
   * now and then a curious look. While Pulse is searching, a look around
   * sometimes takes a blink's place; while thinking, a small bob of the head.
   * Streaming keeps to blinks so the words have the attention. */
  Ctl.prototype.schedule = function () {
    var self = this;
    clearTimeout(this.idleT);
    this.idleT = null;
    if (!this.running()) return;
    var busy = this.state === 'thinking' || this.state === 'searching';
    var ms = busy ? rand(3500, 6500) : rand(5000, 10000);
    this.idleT = setTimeout(function () {
      self.idleT = null;
      if (!self.running()) return;
      if (self.seq) { self.schedule(); return; }
      var r = Math.random();
      var full = motion() === 'full';
      if (full && self.state === 'idle' && r < 0.2 && Date.now() - self.lastCurious > 20000) {
        self.lastCurious = Date.now();
        self.gesture('curious');
      } else if (full && self.state === 'searching' && r < 0.45) {
        self.gesture('look');
      } else if (full && self.state === 'thinking' && r < 0.25) {
        self.gesture('bob');
      } else {
        self.blink(full && r > 0.85);
      }
    }, ms);
  };

  /* The scarf in the wind: on while he is running at Full, off otherwise. */
  Ctl.prototype.windy = function (on) {
    this.el.classList.toggle('is-windy', !!on);
  };

  Ctl.prototype.wake = function () {
    this.windy(this.running() && motion() === 'full');
    if (!this.running()) { this.rest(); return; }
    var p = this.pending;
    this.pending = null;
    if (p && Date.now() - p.at < 2500) { this.gesture(p.name, p.then); return; }
    if (!this.seq) this.rest();
    if (!this.seq && !this.idleT) this.schedule();
  };

  /* Hidden: no timers, and the resting frame of his state, never a frame
   * from the middle of a gesture. */
  Ctl.prototype.sleep = function () {
    this.windy(false);
    this.cancel();
    clearTimeout(this.idleT);
    this.idleT = null;
    this.rest();
  };

  Ctl.prototype.stop = function () {
    this.windy(false);
    this.cancel();
    clearTimeout(this.idleT);
    this.idleT = null;
    this.pending = null;
    if (io) io.unobserve(this.el);
    this.el.scoutCtl = null;
    var self = this;
    live = live.filter(function (c) { return c !== self; });
  };

  /* Start a figure. `slot` names a place that holds one moving Scout at a
   * time (the reply being written): starting a new one there stops the old,
   * which keeps its last resting frame (an error keeps its concerned face). */
  function attach(el, opts) {
    opts = opts || {};
    if (!el) return null;
    if (el.scoutCtl) return el.scoutCtl;
    live.slice().forEach(function (c) {
      if (!c.el.isConnected || (opts.slot && c.slot === opts.slot)) c.stop();
    });
    var c = new Ctl(el, opts.slot);
    el.scoutCtl = c;
    live.push(c);
    c.rest();
    if (io) io.observe(el); else c.wake();
    return c;
  }

  function setMotion(v) {
    try {
      if (v === 'full' || v === 'subtle' || v === 'still') global.localStorage.setItem(STORE, v);
    } catch (e) { /* private window: the choice lasts this page */ }
    live.slice().forEach(function (c) { c.sleep(); c.wake(); });
  }

  document.addEventListener('visibilitychange', function () {
    live.slice().forEach(function (c) { if (document.hidden) c.sleep(); else c.wake(); });
  });
  if (reduceQuery) {
    var onReduce = function () { live.slice().forEach(function (c) { c.sleep(); c.wake(); }); };
    if (reduceQuery.addEventListener) reduceQuery.addEventListener('change', onReduce);
    else if (reduceQuery.addListener) reduceQuery.addListener(onReduce);
  }

  global.OpticScout = {
    html: html, attach: attach, motion: motion, choice: choice, setMotion: setMotion,
    FRAME: FRAME, COUNT: COUNT,
  };
})(window);
