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
    /* The three worked poses, added 2026-11-03 for Milo's activity states: at
     * the desk with the laptop, holding the tablet, writing in the notebook.
     * Appended, never inserted: the indices are a contract with
     * static/scout/frames.json and the renderer's FRAMES. */
    'desk': 22, 'desk-half': 23, 'desk-closed': 24, 'desk-type': 25,
    'tablet': 26, 'tablet-half': 27, 'tablet-closed': 28, 'tablet-near': 29,
    'write': 30, 'write-half': 31, 'write-closed': 32, 'write-1': 33, 'write-2': 34,
    /* In-between arm positions, so the wave is a wave: see GESTURE below. */
    'arm-a': 35, 'arm-b': 36, 'arm-c': 37,
    /* Thinking with his hand under his jaw, for the persistent companion. chin-2 and chin-3 are the
     * small head moves it ponders on: the hand is held in the head's frame in the renderer, so the
     * chin stays in the mitt while he shifts and glances off. */
    'chin': 38, 'chin-half': 39, 'chin-closed': 40, 'chin-2': 41, 'chin-3': 42,
  };
  var COUNT = 43;

  /* How many frames the browser ACTUALLY has, which is not always COUNT.
   *
   * The count lives in four files that deploy separately: the renderer, frames.json, FRAME above, and
   * background-size in the stylesheets. Each is served with max-age=14400 and no version in its URL, so for
   * four hours after the count changes a browser can hold any mix of old and new. Every disagreement slices
   * him wrong: on 2026-11-03 a fresh stylesheet against a cached script put every frame at 1.76x its offset,
   * and the owner saw a Milo cut in half.
   *
   * So the sheet is measured instead of assumed. It is one row of equal frames, so the number of them is its
   * width over its height times the frame's own aspect; frames.json carries that aspect and is the one file
   * served no-cache. The measurement drives the frame offset and background-size for every figure and for
   * the button's badge, and a frame past the end of the sheet is never asked for. Both sheets always hold
   * the same frames, so measuring one answers for both. */
  var LIVE = COUNT;                     // what we actually slice by
  var BOX = { w: 288, h: 380 };         // one full frame, until an element on the page says otherwise
  var sized = false;

  function publishSize() {
    try {
      var root = global.document.documentElement;
      root.style.setProperty('--scout-frames', (LIVE * 100) + '%');
      root.style.setProperty('--scout-step', (100 / Math.max(1, LIVE - 1)).toFixed(4) + '%');
    } catch (e) { /* no DOM */ }
    for (var i = 0; i < live.length; i++) {
      if (live[i] && live[i].el && live[i].el.isConnected) live[i].show(live[i].frameName);
    }
  }

  /* Measured from `el`, the first figure to appear: its box carries one frame's aspect (the stylesheet gives
   * it an aspect-ratio), and the sheet is one row of frames with that aspect, so the number of them is the
   * picture's width over its height times that ratio. Nothing is fetched: the sprite is already being loaded
   * for the element, so this reads the same file out of the cache. */
  function measure(el) {
    if (sized || !global.document || !global.Image) return;
    sized = true;
    try {
      var r = (global.getComputedStyle(el).aspectRatio || '').split('/');
      var w = parseFloat(r[0]), h = parseFloat(r[1]);
      if (!(w > 0 && h > 0)) { var b = el.getBoundingClientRect(); w = b.width; h = b.height; }
      if (w > 0 && h > 0) BOX = { w: w, h: h };
    } catch (e) { /* the compiled frame box stands */ }
    publishSize();                      // the compiled count, until the picture answers
    var im = new global.Image();
    im.onload = function () {
      if (!im.naturalWidth || !im.naturalHeight) return;
      var n = Math.round(im.naturalWidth / im.naturalHeight * (BOX.h / BOX.w));
      // A sheet that measures as nothing, or as a single frame, means the picture is wrong rather than the
      // count: keep what was compiled in.
      if (n >= 2) LIVE = n;
      publishSize();
    };
    im.src = '/scout/scout-full@' + ((global.devicePixelRatio || 1) >= 2.5 ? '3x' : '2x') + '.webp';
  }

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
    desk: ['desk', 'desk-half', 'desk-closed'],
    tablet: ['tablet', 'tablet-half', 'tablet-closed'],
    write: ['write', 'write-half', 'write-closed'],
    chin: ['chin', 'chin-half', 'chin-closed'],
  };
  var POSE = {
    /* `thinking` is his hand under his jaw since 2026-11-03: the brief asks for a pose, not a head angle,
     * and a tilt alone was not telling anyone he was thinking. `listening` is the attentive tilt he wears
     * while someone is typing; it is named for the composer, not for a microphone, and nothing in Optic
     * records audio. */
    idle: 'idle', listening: 'tilt', thinking: 'chin', searching: 'tilt',
    streaming: 'idle', error: 'concerned',
    /* Milo's activity states. These are scenes, not head angles, so they sit
     * outside the upright/lean/tilt/curious ladder: LEVEL has no entry for
     * them and a change to one is a cut rather than a walk. */
    researching: 'desk', analyzing: 'tablet', writing: 'write',
  };
  var WORK = { desk: 1, tablet: 1, write: 1, chin: 1 };

  /* Gestures, as [frame, ms].
   *
   * The arm has seven positions, not three: arm-a, arm-1, arm-b, arm-2, arm-c, arm-3 climb 15, 30, 47, 65,
   * 82 and 100 degrees from the shoulder. Until 2026-11-03 the wave used only arm-1, arm-2 and arm-3 and cut
   * between them, so the hand crossed 35 degrees in 60 ms, about 580 deg/s, and at the welcome size it
   * jumped roughly 18 px across and 36 px up with nothing in between. It read as a twitch, which is what the
   * owner called it. Every step is now about 17 degrees over 50 ms, near 300 deg/s, which is where a wave
   * actually sits. */
  var GESTURE = {
    wave: [['arm-a', 50], ['arm-1', 50], ['arm-b', 52], ['arm-2', 52], ['arm-c', 55], ['arm-3', 120],
      ['arm-c', 60], ['arm-2', 70], ['arm-c', 60], ['arm-3', 110],
      ['arm-c', 55], ['arm-2', 52], ['arm-b', 50], ['arm-1', 50], ['arm-a', 45]],
    ack: [['arm-a', 50], ['arm-1', 52], ['arm-b', 55], ['arm-2', 110], ['arm-b', 55], ['arm-1', 52],
      ['arm-a', 48]],
    nod: [['nod-1', 90], ['nod-2', 170], ['nod-1', 90]],
    look: [['look-l1', 120], ['look-l2', 520], ['look-l1', 110], ['lean', 90],
      ['look-r1', 120], ['look-r2', 520], ['look-r1', 110], ['lean', 90]],
    curious: [['curious', 1300], ['curious-half', 40], ['curious-closed', 50],
      ['curious-half', 40], ['curious', 280]],
    point: [['arm-a', 50], ['arm-1', 52], ['arm-b', 55], ['arm-2', 900], ['arm-b', 55], ['arm-1', 52],
      ['arm-a', 48]],
    /* The small motion each pose loops on: hands moving over the keys, a look down at the tablet, the
     * pencil travelling across the page, and - the slowest of them, because it is the one state with
     * nothing in his hands - a settle and a glance away while he thinks. */
    type: [['desk-type', 170], ['desk', 150], ['desk-type', 170], ['desk', 150], ['desk-type', 160]],
    read: [['tablet-near', 820], ['tablet', 180]],
    pen: [['write-1', 190], ['write-2', 240], ['write-1', 180], ['write', 150]],
    ponder: [['chin-2', 880], ['chin', 680], ['chin-3', 1060], ['chin', 520]],
  };
  /* The loop that belongs to each pose. Until 2026-11-03 this was a chain of equality tests that ended
   * in `pen`, so `chin` - the one pose that is not a desk or a tablet - answered the fallback and Milo
   * played the notebook-writing frames while the panel said Thinking. The owner saw him "switch to
   * writing" during thinking, which is exactly what that was. */
  var LOOP = { desk: 'type', tablet: 'read', write: 'pen', chin: 'ponder' };
  /* The ladder level each gesture starts from: upright for the arm and the
   * nod, leaning for a look around, tilted for the curious look. */
  var GESTURE_FROM = { wave: 0, ack: 0, nod: 0, point: 0, look: 1, curious: 3 };

  var STORE = 'optic.scout.motion.v1';
  var reduceQuery = global.matchMedia ? global.matchMedia('(prefers-reduced-motion: reduce)') : null;

  function choice() {
    try {
      var v = global.localStorage.getItem(STORE);
      return v === 'full' || v === 'subtle' || v === 'still' ? v : null;
    } catch (e) { return null; }
  }
  function motion() {
    // v2's Settings, Motion: Reduce (html[data-motion]) counts as the system asking, so a choice made here still wins
    var asked = (reduceQuery && reduceQuery.matches) || document.documentElement.getAttribute('data-motion') === 'reduce';
    return choice() || (asked ? 'still' : 'full');
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
    this.lastWave = 0;
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
    var i = FRAME[name];
    // Never ask for a frame the sheet in this browser does not have: a script newer than the picture would
    // otherwise point past its end and show nothing.
    if (i === undefined || i >= LIVE) { name = 'idle'; i = 0; }
    this.frameName = name;
    this.el.setAttribute('data-frame', name);
    this.el.style.setProperty('--scout-x', (i / Math.max(1, LIVE - 1) * 100).toFixed(4) + '%');
  };
  Ctl.prototype.pose = function () {
    var name = POSE[this.state] || 'idle';
    // Still motion holds him in the resting pose. What he is working with is
    // the state itself and not decoration, so the desk, the tablet and the
    // notebook stay; only the movement goes.
    return motion() === 'still' && !WORK[name] ? 'idle' : name;
  };
  Ctl.prototype.level = function () { return LEVEL[FACE[this.pose()][0]] || 0; };
  Ctl.prototype.rest = function () { this.show(FACE[this.pose()][0]); };

  /* A scene - the desk, the tablet, the notebook, the hand under the jaw - is a change of situation and
   * not a notch on the head ladder, so there are no in-between frames to walk through and a straight
   * swap reads as a cut: the laptop is simply gone and a tablet is in its place. He dips out and back
   * instead, and the frame changes while there is nothing on screen to see change. Ladder moves keep
   * their walk, which is already smooth, and Still motion keeps the cut rather than inventing a fade. */
  var SWAP_MS = 90;
  Ctl.prototype.dip = function (then) {
    var self = this, el = this.el;
    if (motion() === 'still' || !this.running() || !el.classList) { then(); return; }
    // Researching -> Analyzing -> Writing can land inside a second. A second dip on top of one still in
    // flight would read as a flicker, so the later change rides the dip already running and only the
    // last one arrives: he fades once and comes back in the scene he ended up in.
    if (this.swapThen && el.classList.contains('is-swap')) { this.swapThen = then; return; }
    this.cancel();
    this.swapThen = then;
    el.classList.add('is-swap');
    this.seq = setTimeout(function () {
      self.seq = null;
      var land = self.swapThen;
      self.swapThen = null;
      if (el.classList) el.classList.remove('is-swap');
      if (land) land();
    }, SWAP_MS);
  };
  /* Settle into the current state's pose, behind the dip when that means arriving in a scene he is not
   * already standing in. `then` runs once he is there. */
  Ctl.prototype.settle = function (then) {
    var self = this;
    var pose = this.pose(), at = this.frameName || '';
    var here = (FACE[pose] || []).indexOf(at) >= 0 || at.indexOf(pose) === 0;
    var land = function () { self.rest(); if (then) then(); };
    if (!WORK[pose] || here) { land(); return; }
    this.dip(land);
  };

  Ctl.prototype.cancel = function () {
    clearTimeout(this.seq);
    this.seq = null;
    // A dip cut short - he scrolled off screen, the panel closed, the figure was taken away mid-swap -
    // would otherwise leave him faded out with nothing left to bring him back.
    this.swapThen = null;
    if (this.el.classList) this.el.classList.remove('is-swap');
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
      self.settle(function () {
        if (state === 'searching') self.gesture('look');
        else self.schedule();
      });
    });
  };

  /* A gesture, then back to the pose of the current state. Subtle and still
   * motion have none: the state's pose alone carries it. */
  Ctl.prototype.gesture = function (name, then) {
    if (!this.alive()) return;
    var self = this;
    var done = function () { self.settle(function () { self.schedule(); if (then) then(); }); };
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
   * now and then a curious look or, on the welcome screen, a wave. While Pulse
   * is searching, a look around sometimes takes a blink's place; while
   * thinking, a small bob of the head. Streaming keeps to blinks so the words
   * have the attention.
   *
   * Twice as often as at first (asked for 2026-10-12: "have him blink and wave
   * in shorter intervals to make it more frequent"): a beat every 2.5-5 s
   * rather than 5-10, and the welcome figure waves on his own about every
   * 20-40 s. Waves and looks stay Full-motion only; the small figures beside
   * answers never wave. */
  var WAVE_GAP_MS = 20000;
  Ctl.prototype.schedule = function () {
    var self = this;
    clearTimeout(this.idleT);
    this.idleT = null;
    if (!this.running()) return;
    var busy = this.state === 'thinking' || this.state === 'searching' || !!WORK[this.pose()];
    // A pose with a loop of its own should look occupied. Measured in the panel on 2026-11-03, the old
    // busy gap left him standing still for the first 2.4 s of Thinking and moving once in four seconds,
    // which is most of a short wait spent as a photograph.
    var ms = LOOP[this.pose()] ? rand(1200, 2400) : busy ? rand(2000, 4000) : rand(2500, 5000);
    this.idleT = setTimeout(function () {
      self.idleT = null;
      if (!self.running()) return;
      if (self.seq) { self.schedule(); return; }
      var r = Math.random();
      var full = motion() === 'full';
      if (full && self.state === 'idle' && self.slot === 'welcome' && r < 0.3
          && Date.now() - self.lastWave > WAVE_GAP_MS) {
        self.lastWave = Date.now();
        self.gesture('wave');
      } else if (full && self.state === 'idle' && r < 0.45 && Date.now() - self.lastCurious > 20000) {
        self.lastCurious = Date.now();
        self.gesture('curious');
      } else if (full && self.state === 'searching' && r < 0.45) {
        self.gesture('look');
      } else if (full && LOOP[self.pose()] && r < 0.72) {
        self.gesture(LOOP[self.pose()]);
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
    measure(el);        // the first figure to appear tells us how many frames the sheet really has
    c.rest();
    if (io) io.observe(el); else c.wake();
    return c;
  }

  /* The setting, mirrored onto <html> for what CSS alone animates: the
   * Pulse button's blinking badge stops when this says still. */
  function markMotion() {
    try { document.documentElement.setAttribute('data-scout-motion', motion()); } catch (e) { /* no DOM */ }
  }
  markMotion();

  function setMotion(v) {
    try {
      if (v === 'full' || v === 'subtle' || v === 'still') global.localStorage.setItem(STORE, v);
    } catch (e) { /* private window: the choice lasts this page */ }
    markMotion();
    live.slice().forEach(function (c) { c.sleep(); c.wake(); });
  }

  document.addEventListener('visibilitychange', function () {
    live.slice().forEach(function (c) { if (document.hidden) c.sleep(); else c.wake(); });
  });
  if (reduceQuery) {
    var onReduce = function () { markMotion(); live.slice().forEach(function (c) { c.sleep(); c.wake(); }); };
    if (reduceQuery.addEventListener) reduceQuery.addEventListener('change', onReduce);
    else if (reduceQuery.addListener) reduceQuery.addListener(onReduce);
  }

  global.OpticScout = {
    html: html, attach: attach, motion: motion, choice: choice, setMotion: setMotion,
    FRAME: FRAME, COUNT: COUNT,
  };
})(window);
