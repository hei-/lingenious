import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { focusPose, type V3 } from './focus';

export interface Palette { bg: string; model: string; edge: string; grid: string; gridMain: string }
export interface Dims { x: number; y: number; z: number } // CAD axes (mm): X, Y, Z-up
export type Placeholder = 'box' | 'bracket';
export interface MarkerSpec { id: string; locs: V3[]; severity: 'error' | 'warning'; label: string }
export type LoadResult = { dims: Dims; fallback: boolean };

function cssPalette(): Palette {
  const cs = getComputedStyle(document.documentElement);
  const g = (n: string, d: string) => cs.getPropertyValue(n).trim() || d;
  return { bg: g('--viewer-bg', '#f3f5f7'), model: g('--viewer-model', '#9aa9b8'), edge: g('--viewer-edge', '#26313d'), grid: g('--viewer-grid', '#d3d9df'), gridMain: g('--viewer-grid-main', '#aab4be') };
}

/**
 * Owns the whole three.js scene. glTF is Y-up (OCCT exports CAD-Z as glTF-Y), so CAD dims are
 * X = size.x, Y = size.z, Z = size.y. Renders on demand (no idle GPU load).
 */
export class SceneController {
  readonly renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private persp = new THREE.PerspectiveCamera(35, 1, 0.1, 10000);
  private ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, -10000, 10000);
  private camera: THREE.Camera = this.persp;
  private controls: OrbitControls;
  private modelRoot: THREE.Group | null = null;
  private meshes: THREE.Mesh[] = [];
  private edgeLines: THREE.LineSegments[] = [];
  private helpers = new THREE.Group();
  private dimsGroup = new THREE.Group();
  private box = new THREE.Box3();
  private sphere = new THREE.Sphere();
  private palette = cssPalette();
  private raf = 0;
  private disposed = false;
  private loadToken = 0;
  private ro: ResizeObserver;
  private labels: { el: HTMLElement; axis: 0 | 1 | 2 }[] = [];
  private flags = { wire: false, edges: true, ortho: false, axes: true, dims: true };
  private modelMat = new THREE.MeshStandardMaterial({ roughness: 0.55, metalness: 0.15, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
  private edgeMat = new THREE.LineBasicMaterial();
  private ghostMat = new THREE.MeshBasicMaterial({ color: 0xe5484d, transparent: true, opacity: 0.38, depthWrite: false, side: THREE.DoubleSide });
  private mainFrame: THREE.Object3D | null = null;
  private ghostRoot: THREE.Group | null = null;
  private ghostFrame: THREE.Object3D | null = null;
  private ghostToken = 0;
  private markerLayer: HTMLElement;
  private markerSpecs: MarkerSpec[] = [];
  private markerCb: ((id: string) => void) | null = null;
  private markers: { id: string; anchor: THREE.Object3D; el: HTMLElement }[] = [];
  private activeMarker: string | null = null;
  private tween = 0;
  private ray = new THREE.Raycaster();

  constructor(private host: HTMLElement, private overlay: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    host.appendChild(this.renderer.domElement);
    this.markerLayer = document.createElement('div');
    this.markerLayer.className = 'marker-layer';
    host.appendChild(this.markerLayer);
    this.renderer.domElement.style.display = 'block';
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x667788, 1.1));
    const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(3, 5, 4); this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.8); fill.position.set(-4, 2, -3); this.scene.add(fill);
    this.scene.add(this.helpers, this.dimsGroup);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = false;
    this.controls.addEventListener('change', this.request);
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(host);
    this.applyPalette(this.palette);
    this.resize();
  }

  private request = () => {
    if (this.raf || this.disposed) return;
    this.raf = requestAnimationFrame(() => { this.raf = 0; this.render(); });
  };

  private render() {
    if (this.disposed) return;
    this.renderer.render(this.scene, this.camera);
    this.updateLabels();
    this.updateMarkers();
  }

  private resize() {
    const w = Math.max(1, this.host.clientWidth), h = Math.max(1, this.host.clientHeight);
    this.renderer.setSize(w, h, false);
    this.renderer.domElement.style.width = '100%'; this.renderer.domElement.style.height = '100%';
    this.persp.aspect = w / h; this.persp.updateProjectionMatrix();
    this.syncOrtho();
    this.request();
  }

  private syncOrtho() {
    const aspect = this.persp.aspect;
    const half = this.orthoHalf;
    this.ortho.left = -half * aspect; this.ortho.right = half * aspect; this.ortho.top = half; this.ortho.bottom = -half;
    this.ortho.updateProjectionMatrix();
  }
  private orthoHalf = 50;

  private updateLabels() {
    const w = this.host.clientWidth, h = this.host.clientHeight;
    if (!this.labels.length) return;
    const { min, max } = this.box;
    const c = this.box.getCenter(new THREE.Vector3());
    const px = (p: THREE.Vector3) => { const v = p.clone().project(this.camera); return { x: ((v.x + 1) / 2) * w, y: ((1 - v.y) / 2) * h, z: v.z }; };
    const cp = px(c);
    const placed: { x: number; y: number; w: number; h: number; l: { el: HTMLElement; axis: 0 | 1 | 2 } }[] = [];
    for (const l of this.labels) {
      // candidate edges parallel to this axis; use the one farthest from the projected centre (outermost on screen)
      const cands: THREE.Vector3[] = [];
      for (const a of [0, 1]) for (const b of [0, 1]) {
        const lo = a === 0, lo2 = b === 0;
        cands.push(l.axis === 0 ? new THREE.Vector3(c.x, lo ? min.y : max.y, lo2 ? min.z : max.z)
          : l.axis === 1 ? new THREE.Vector3(lo ? min.x : max.x, c.y, lo2 ? min.z : max.z)
          : new THREE.Vector3(lo ? min.x : max.x, lo2 ? min.y : max.y, c.z));
      }
      let best = px(cands[0]), bd = -1;
      for (const p of cands) { const q = px(p); const d = Math.hypot(q.x - cp.x, q.y - cp.y); if (d > bd) { bd = d; best = q; } }
      let dx = best.x - cp.x, dy = best.y - cp.y;
      const len = Math.hypot(dx, dy) || 1; dx /= len; dy /= len;
      const vis = this.flags.dims && best.z < 1;
      l.el.style.display = vis ? '' : 'none';
      if (!vis) continue;
      const lw = l.el.offsetWidth || 50, lh = l.el.offsetHeight || 18;
      const off = 14 + Math.min(lw, 60) / 2 * Math.abs(dx);
      placed.push({ x: best.x + dx * off, y: best.y + dy * (14 + lh / 2), w: lw, h: lh, l });
    }
    // nudge apart vertically when rects overlap
    for (let pass = 0; pass < 6; pass++) {
      let moved = false;
      for (let i = 0; i < placed.length; i++) for (let j = i + 1; j < placed.length; j++) {
        const a = placed[i], b = placed[j];
        const ox = (a.w + b.w) / 2 + 4 - Math.abs(a.x - b.x), oy = (a.h + b.h) / 2 + 4 - Math.abs(a.y - b.y);
        if (ox > 0 && oy > 0) { const s = a.y <= b.y ? 1 : -1; a.y -= (s * oy) / 2; b.y += (s * oy) / 2; moved = true; }
      }
      if (!moved) break;
    }
    for (const p of placed) {
      const x = Math.min(w - p.w / 2 - 2, Math.max(p.w / 2 + 2, p.x)), y = Math.min(h - p.h / 2 - 2, Math.max(p.h / 2 + 2, p.y));
      p.l.el.style.transform = `translate(-50%,-50%) translate(${x}px, ${y}px)`;
    }
  }

  applyPalette(p: Palette) {
    this.palette = p;
    this.renderer.setClearColor(new THREE.Color(p.bg), 1);
    this.modelMat.color.set(p.model);
    this.edgeMat.color.set(p.edge);
    this.rebuildHelpers();
    this.request();
  }
  refreshPalette() { this.applyPalette(cssPalette()); }

  setFlag(k: keyof SceneController['flags'], on: boolean) {
    this.flags[k] = on;
    if (k === 'wire') this.modelMat.wireframe = on;
    if (k === 'edges') this.edgeLines.forEach((l) => (l.visible = on));
    if (k === 'axes') this.helpers.visible = on;
    if (k === 'dims') this.dimsGroup.visible = on;
    if (k === 'ortho') this.switchCamera(on);
    this.request();
  }

  private switchCamera(ortho: boolean) {
    const from = this.camera, to = ortho ? this.ortho : this.persp;
    if (from === to) return;
    const dist = from.position.distanceTo(this.controls.target);
    to.position.copy(from.position); to.quaternion.copy(from.quaternion);
    if (ortho) {
      this.orthoHalf = dist * Math.tan(THREE.MathUtils.degToRad(this.persp.fov / 2));
      this.ortho.zoom = 1; this.syncOrtho();
      this.ortho.near = -this.sphere.radius * 20; this.ortho.far = dist + this.sphere.radius * 20; this.ortho.updateProjectionMatrix();
    }
    this.camera = to;
    this.controls.object = to;
    this.controls.update();
  }

  fit() {
    if (this.sphere.radius <= 0) return;
    const r = this.sphere.radius, c = this.sphere.center;
    const dist = (r / Math.sin(THREE.MathUtils.degToRad(this.persp.fov / 2))) * 1.05;
    const dir = new THREE.Vector3(1, 0.75, 1.1).normalize();
    this.persp.near = Math.max(r / 200, 0.01); this.persp.far = dist + r * 20; this.persp.updateProjectionMatrix();
    this.orthoHalf = r * 1.15; this.ortho.zoom = 1; this.syncOrtho();
    this.ortho.near = -r * 20; this.ortho.far = dist + r * 20; this.ortho.updateProjectionMatrix();
    for (const cam of [this.persp, this.ortho]) { cam.position.copy(c).addScaledVector(dir, dist); cam.lookAt(c); }
    this.controls.target.copy(c);
    this.controls.update();
    this.request();
  }

  private rebuildHelpers() {
    this.clearGroup(this.helpers);
    if (this.box.isEmpty()) return;
    const size = this.box.getSize(new THREE.Vector3());
    const span = Math.max(size.x, size.z, 1) * 2.4;
    const step = niceStep(span / 12);
    const n = Math.max(2, Math.ceil(span / step / 2) * 2);
    const grid = new THREE.GridHelper(n * step, n, new THREE.Color(this.palette.gridMain), new THREE.Color(this.palette.grid));
    const c = this.box.getCenter(new THREE.Vector3());
    grid.position.set(c.x, this.box.min.y - size.y * 0.002, c.z);
    const axes = new THREE.AxesHelper(Math.max(size.x, size.y, size.z) * 0.35);
    axes.position.copy(this.box.min);
    this.helpers.add(grid, axes);
    this.helpers.visible = this.flags.axes;
  }

  private rebuildDims() {
    this.clearGroup(this.dimsGroup);
    this.overlay.replaceChildren();
    this.labels = [];
    if (this.box.isEmpty()) return;
    const helper = new THREE.Box3Helper(this.box, new THREE.Color(this.palette.edge));
    (helper.material as THREE.LineBasicMaterial).transparent = true;
    (helper.material as THREE.LineBasicMaterial).opacity = 0.35;
    this.dimsGroup.add(helper);
    const s = this.box.getSize(new THREE.Vector3());
    const mk = (txt: string, axis: 0 | 1 | 2) => {
      const el = document.createElement('span'); el.className = 'dim-label'; el.textContent = txt; this.overlay.appendChild(el);
      this.labels.push({ el, axis });
    };
    const f = (n: number) => n.toFixed(n >= 100 ? 0 : 1);
    mk(`X ${f(s.x)}`, 0); // three x = CAD X
    mk(`Y ${f(s.z)}`, 2); // three z = CAD Y
    mk(`Z ${f(s.y)}`, 1); // three y = CAD Z
    this.dimsGroup.visible = this.flags.dims;
  }

  private clearGroup(g: THREE.Group) {
    for (const o of [...g.children]) { g.remove(o); disposeObject(o); }
  }

  private clearModel() {
    if (this.modelRoot) { this.scene.remove(this.modelRoot); disposeObject(this.modelRoot, true); }
    this.modelRoot = null; this.mainFrame = null; this.meshes = []; this.edgeLines = [];
  }

  private adopt(root: THREE.Group, frame: THREE.Object3D) {
    this.clearModel();
    this.modelRoot = root;
    this.mainFrame = frame;
    root.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) {
        const m = o as THREE.Mesh;
        const old = m.material; (Array.isArray(old) ? old : [old]).forEach((x) => x.dispose());
        m.material = this.modelMat;
        const e = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry, 28), this.edgeMat);
        e.visible = this.flags.edges; m.add(e);
        this.meshes.push(m); this.edgeLines.push(e);
      }
    });
    this.scene.add(root);
    this.box.setFromObject(root);
    this.box.getBoundingSphere(this.sphere);
    this.rebuildHelpers(); this.rebuildDims(); this.fit();
    this.rebuildMarkers();
  }

  /** The node whose transform maps the script frame (Z-up) to the world: the glb root node, else a synthetic Z-up->Y-up group. */
  private findFrame(scene: THREE.Group): THREE.Object3D {
    const c = scene.children.length === 1 ? scene.children[0] : scene;
    if (c.quaternion.angleTo(new THREE.Quaternion()) > 1e-6) return c;
    const g = new THREE.Group(); g.rotation.x = -Math.PI / 2; scene.add(g); return g; // contract says rotated; be safe if it is not
  }

  private placeholderModel(dims: Dims, kind: Placeholder, url: string | null, mat: THREE.Material): THREE.Group {
    const root = new THREE.Group();
    const cad = new THREE.Group(); cad.rotation.x = -Math.PI / 2; root.add(cad); // CAD frame is Z-up
    if (kind === 'box') {
      const m = new THREE.Mesh(new THREE.BoxGeometry(dims.x, dims.y, dims.z), mat); m.position.z = dims.z / 2; cad.add(m);
      return root;
    }
    const bt = 6, wt = 3, wh = Math.max(dims.z - bt, 1);
    const base = new THREE.Mesh(new THREE.BoxGeometry(dims.x, dims.y, bt), mat); base.position.z = bt / 2;
    const wall = new THREE.Mesh(new THREE.BoxGeometry(dims.x, wt, wh), mat); wall.position.set(0, -dims.y / 2 + wt / 2, bt + wh / 2);
    cad.add(base, wall);
    if (!(url ?? '').includes('r1')) { // later rounds carry the inner fillet
      const r = 3, sh = new THREE.Shape();
      sh.moveTo(0, 0); sh.lineTo(r, 0); sh.absarc(r, r, r, -Math.PI / 2, -Math.PI, true); sh.lineTo(0, 0);
      const g = new THREE.ExtrudeGeometry(sh, { depth: dims.x, bevelEnabled: false, curveSegments: 10 });
      g.applyMatrix4(new THREE.Matrix4().makeBasis(new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1), new THREE.Vector3(1, 0, 0)));
      g.translate(-dims.x / 2, -dims.y / 2 + wt, bt);
      cad.add(new THREE.Mesh(g, mat));
    }
    return root;
  }

  async load(url: string | null, fallbackDims: Dims, placeholder: Placeholder = 'box'): Promise<LoadResult> {
    const token = ++this.loadToken;
    if (url) {
      try {
        const gltf = await new GLTFLoader().loadAsync(url);
        if (this.disposed || token !== this.loadToken) { disposeObject(gltf.scene); return { dims: fallbackDims, fallback: false }; }
        this.adopt(gltf.scene, this.findFrame(gltf.scene));
        const s = this.box.getSize(new THREE.Vector3());
        return { dims: { x: s.x, y: s.z, z: s.y }, fallback: false };
      } catch { /* missing or invalid glb: use placeholder */ }
    }
    if (this.disposed || token !== this.loadToken) return { dims: fallbackDims, fallback: true };
    const g = this.placeholderModel(fallbackDims, placeholder, url, this.modelMat);
    this.adopt(g, g.children[0]);
    return { dims: fallbackDims, fallback: true };
  }

  /** Translucent red "before" geometry drawn over the main model (null removes it). */
  async loadGhost(url: string | null, fallbackDims: Dims, placeholder: Placeholder = 'box') {
    const token = ++this.ghostToken;
    this.clearGhost();
    if (!url) { this.rebuildMarkers(); return; }
    let root: THREE.Group | null = null, frame: THREE.Object3D | null = null;
    try {
      const gltf = await new GLTFLoader().loadAsync(url);
      if (this.disposed || token !== this.ghostToken) { disposeObject(gltf.scene); return; }
      root = gltf.scene; frame = this.findFrame(root);
      root.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { (Array.isArray(m.material) ? m.material : [m.material]).forEach((x) => x.dispose()); m.material = this.ghostMat; m.renderOrder = 2; } });
    } catch {
      if (this.disposed || token !== this.ghostToken) return;
      root = this.placeholderModel(fallbackDims, placeholder, url, this.ghostMat); frame = root.children[0];
      root.traverse((o) => { o.renderOrder = 2; });
    }
    this.ghostRoot = root; this.ghostFrame = frame;
    this.scene.add(root);
    this.rebuildMarkers();
    this.request();
  }

  private clearGhost() {
    if (this.ghostRoot) { this.scene.remove(this.ghostRoot); disposeObject(this.ghostRoot); }
    this.ghostRoot = null; this.ghostFrame = null;
  }

  /** Issue markers (HTML overlay buttons of constant screen size, anchored to 3D points in the script frame). */
  setMarkers(specs: MarkerSpec[], onClick: (id: string) => void) {
    this.markerSpecs = specs; this.markerCb = onClick;
    this.rebuildMarkers();
  }

  private rebuildMarkers() {
    for (const m of this.markers) m.anchor.parent?.remove(m.anchor);
    this.markerLayer.replaceChildren();
    this.markers = [];
    const frame = this.ghostFrame ?? this.mainFrame;
    if (frame) {
      for (const sp of this.markerSpecs) sp.locs.forEach((loc, k) => {
        const anchor = new THREE.Object3D(); anchor.position.set(loc[0], loc[1], loc[2]); frame.add(anchor); // inherits the glb root transform
        const el = document.createElement('button');
        el.type = 'button'; el.className = `marker sev-${sp.severity}` + (this.activeMarker === sp.id ? ' active' : '') + (k ? ' second' : '');
        el.setAttribute('aria-label', sp.label);
        const ring = document.createElement('span'); ring.className = 'ring';
        const lab = document.createElement('span'); lab.className = 'mlabel'; lab.textContent = sp.label;
        el.append(ring, lab);
        el.addEventListener('click', (e) => { e.stopPropagation(); this.markerCb?.(sp.id); });
        this.markerLayer.appendChild(el);
        this.markers.push({ id: sp.id, anchor, el });
      });
    }
    frame?.updateWorldMatrix(true, true);
    this.request();
  }

  setHighlight(id: string | null) {
    this.activeMarker = id;
    for (const m of this.markers) m.el.classList.toggle('active', m.id === id);
  }

  private updateMarkers() {
    if (!this.markers.length) return;
    const w = this.host.clientWidth, h = this.host.clientHeight;
    const v = new THREE.Vector3(), wp = new THREE.Vector3();
    const tol = Math.max(this.sphere.radius * 0.02, 0.3);
    for (const m of this.markers) {
      m.anchor.getWorldPosition(wp); v.copy(wp).project(this.camera);
      const vis = v.z < 1 && Math.abs(v.x) < 1.1 && Math.abs(v.y) < 1.1;
      m.el.style.display = vis ? '' : 'none';
      m.el.style.transform = `translate(-50%,-50%) translate(${((v.x + 1) / 2) * w}px, ${((1 - v.y) / 2) * h}px)`;
      if (vis) { // dim (not hide) markers that sit behind the part
        this.ray.setFromCamera(new THREE.Vector2(v.x, v.y), this.camera);
        const d = wp.clone().sub(this.ray.ray.origin).dot(this.ray.ray.direction);
        const hit = this.ray.intersectObjects(this.meshes, false)[0];
        m.el.classList.toggle('occluded', !!hit && hit.distance < d - tol);
      }
    }
  }

  /** Move the camera to look at a marker, keeping the view direction (animated unless reduced motion). */
  focusMarker(id: string) {
    const m = this.markers.find((x) => x.id === id);
    if (!m) return;
    m.anchor.updateWorldMatrix(true, false);
    const t = m.anchor.getWorldPosition(new THREE.Vector3());
    const cam = this.camera as THREE.PerspectiveCamera | THREE.OrthographicCamera, ctl = this.controls;
    const pose = focusPose([t.x, t.y, t.z], [cam.position.x, cam.position.y, cam.position.z], [ctl.target.x, ctl.target.y, ctl.target.z], this.sphere.radius || 1);
    const from = { p: cam.position.clone(), t: ctl.target.clone(), z: cam.zoom };
    const to = { p: new THREE.Vector3(...pose.position), t: new THREE.Vector3(...pose.target), z: this.camera === this.ortho ? Math.max(cam.zoom, 2) : cam.zoom };
    cancelAnimationFrame(this.tween);
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const t0 = performance.now(), dur = reduce ? 0 : 280;
    const step = (now: number) => {
      if (this.disposed) return;
      const k = dur ? Math.min(1, (now - t0) / dur) : 1, e = k * k * (3 - 2 * k);
      cam.position.lerpVectors(from.p, to.p, e); ctl.target.lerpVectors(from.t, to.t, e); cam.zoom = from.z + (to.z - from.z) * e;
      cam.updateProjectionMatrix(); ctl.update(); this.request();
      if (k < 1) this.tween = requestAnimationFrame(step);
    };
    this.tween = requestAnimationFrame(step);
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.ro.disconnect();
    this.controls.removeEventListener('change', this.request);
    this.controls.dispose();
    cancelAnimationFrame(this.tween); this.ghostToken++;
    this.markerLayer.remove(); this.markers = [];
    this.clearGhost(); this.ghostMat.dispose();
    this.clearModel(); this.clearGroup(this.helpers); this.clearGroup(this.dimsGroup);
    this.modelMat.dispose(); this.edgeMat.dispose();
    this.overlay.replaceChildren();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
    this.renderer.domElement.remove();
  }
}

function niceStep(x: number) {
  const p = Math.pow(10, Math.floor(Math.log10(x)));
  const m = x / p;
  return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p;
}

/** Dispose geometries of an object tree (materials are shared and disposed by the controller). */
function disposeObject(o: THREE.Object3D, _materials = false) {
  void _materials;
  o.traverse((c) => { (c as THREE.Mesh).geometry?.dispose?.(); });
}
