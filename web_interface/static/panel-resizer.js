/**
 * Panel Resizer — makes the Node Palette, Properties Panel, and
 * Live Execution Panel drag-resizable.
 *
 * Each panel gets a thin drag-handle bar on its resize edge.
 * The handle responds to mousedown/mousemove/mouseup (and touch
 * equivalents) to let the user drag the edge freely.
 *
 * Min/max sizes are enforced so panels can't be collapsed to zero
 * or blown past a useful maximum.
 */

(function () {
    'use strict';

    /* ── Constants ── */
    const PALETTE_MIN   = 180;
    const PALETTE_MAX   = 600;
    const PROPS_MIN     = 200;
    const PROPS_MAX     = 700;
    const EXEC_MIN      = 300;
    const EXEC_MAX      = 900;

    /* ── Shared state ── */
    let activeResize = null;   // { panel, handle, axis, startPos, startSize }

    /* ── Helpers ── */

    /** Inject a resize-handle <div> adjacent to a panel element. */
    function createHandle(id, className) {
        const h = document.createElement('div');
        h.id = id;
        h.className = `panel-resize-handle ${className}`;
        return h;
    }

    /** Clamp a value between min and max. */
    function clamp(val, min, max) { return Math.max(min, Math.min(max, val)); }

    /** Save panel widths to localStorage so they survive reloads. */
    function persist(key, width) {
        try { localStorage.setItem(`panel-width-${key}`, String(Math.round(width))); } catch (_) {}
    }

    /** Restore a saved width, or return null. */
    function restore(key) {
        try {
            const v = localStorage.getItem(`panel-width-${key}`);
            return v ? Number(v) : null;
        } catch (_) { return null; }
    }

    /* ── Global mouse / touch handlers (registered once) ── */

    function onPointerMove(e) {
        if (!activeResize) return;
        e.preventDefault();

        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const { panel, startPos, startSize, min, max, direction, key } = activeResize;

        // direction: 1 means "drag right increases width" (palette, exec)
        //           -1 means "drag left increases width"  (properties)
        const delta = (clientX - startPos) * direction;
        const newWidth = clamp(startSize + delta, min, max);

        panel.style.width = `${newWidth}px`;
        persist(key, newWidth);
    }

    function onPointerUp() {
        if (!activeResize) return;
        activeResize.handle.classList.remove('resizing');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        activeResize = null;
    }

    document.addEventListener('mousemove', onPointerMove);
    document.addEventListener('mouseup', onPointerUp);
    document.addEventListener('touchmove', onPointerMove, { passive: false });
    document.addEventListener('touchend', onPointerUp);

    /** Start a resize operation. */
    function beginResize(e, panel, handle, { min, max, direction, key }) {
        e.preventDefault();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        activeResize = {
            panel,
            handle,
            startPos: clientX,
            startSize: panel.offsetWidth,
            min,
            max,
            direction,
            key,
        };
        handle.classList.add('resizing');
        document.body.style.cursor = direction === 1 ? 'ew-resize' : 'ew-resize';
        document.body.style.userSelect = 'none';
    }

    /* ── Bootstrap on DOMContentLoaded ── */
    document.addEventListener('DOMContentLoaded', () => {

        /* ──────────────────────────────────
           1) NODE PALETTE (right edge handle)
           ────────────────────────────────── */
        const palette = document.querySelector('.node-palette');
        if (palette) {
            const h = createHandle('palette-resize-handle', 'handle-right');
            palette.appendChild(h);

            // Restore saved width
            const saved = restore('palette');
            if (saved) palette.style.width = `${clamp(saved, PALETTE_MIN, PALETTE_MAX)}px`;

            const opts = { min: PALETTE_MIN, max: PALETTE_MAX, direction: 1, key: 'palette' };
            h.addEventListener('mousedown', (e) => beginResize(e, palette, h, opts));
            h.addEventListener('touchstart', (e) => beginResize(e, palette, h, opts), { passive: false });
        }

        /* ──────────────────────────────────
           2) PROPERTIES PANEL (left edge handle)
           ────────────────────────────────── */
        const props = document.querySelector('.properties-panel');
        if (props) {
            const h = createHandle('props-resize-handle', 'handle-left');
            props.appendChild(h);

            const saved = restore('props');
            if (saved) props.style.width = `${clamp(saved, PROPS_MIN, PROPS_MAX)}px`;

            const opts = { min: PROPS_MIN, max: PROPS_MAX, direction: -1, key: 'props' };
            h.addEventListener('mousedown', (e) => beginResize(e, props, h, opts));
            h.addEventListener('touchstart', (e) => beginResize(e, props, h, opts), { passive: false });
        }

        /* ──────────────────────────────────
           3) LIVE EXECUTION PANEL (right edge handle)
           ────────────────────────────────── */
        const exec = document.getElementById('live-exec-panel');
        if (exec) {
            const h = createHandle('exec-resize-handle', 'handle-right');
            // Place on the panel div itself (not inside .live-exec-container
            // which has overflow:hidden). The panel is position:fixed so
            // the handle at right:0 sits on its right edge.
            exec.appendChild(h);

            const saved = restore('exec');
            if (saved) exec.style.width = `${clamp(saved, EXEC_MIN, EXEC_MAX)}px`;

            const opts = { min: EXEC_MIN, max: EXEC_MAX, direction: 1, key: 'exec' };
            h.addEventListener('mousedown', (e) => {
                // Don't allow resize while collapsed
                if (exec.classList.contains('collapsed')) return;
                beginResize(e, exec, h, opts);
            });
            h.addEventListener('touchstart', (e) => {
                if (exec.classList.contains('collapsed')) return;
                beginResize(e, exec, h, opts);
            }, { passive: false });
        }
    });
})();
