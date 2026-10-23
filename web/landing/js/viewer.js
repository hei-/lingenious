// Minimal GLB viewer on three.js (vendored in ../vendor). Renders on demand.
import * as THREE from 'three';
import { OrbitControls } from '../vendor/OrbitControls.js';

async function loadGLB(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(url + ' ' + res.status);
  const buf = await res.arrayBuffer();
  const dv = new DataView(buf);
  if (dv.getUint32(0, true) !== 0x46546C67) throw new Error('not a GLB');
  const jl = dv.getUint32(12, true);
  const json = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 20, jl)));
  const bo = 20 + jl + 8; // binary chunk payload
  const geoms = json.meshes.map((m) => {
    const prim = m.primitives[0];
    const g = new THREE.BufferGeometry();
    for (const [name, ai] of Object.entries(prim.attributes)) {
      const a = json.accessors[ai], v = json.bufferViews[a.bufferView];
      const arr = new Float32Array(buf.slice(bo + v.byteOffset, bo + v.byteOffset + v.byteLength));
      g.setAttribute(name === 'POSITION' ? 'position' : 'normal', new THREE.BufferAttribute(arr, 3));
    }
    return { g, mode: prim.mode };
  });
  return geoms;
}

export class Viewer {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(32, 1, 1, 2000);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = false;
    this.controls.addEventListener('change', () => this.draw());
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x666666, 1.1));
    const d = new THREE.DirectionalLight(0xffffff, 1.6); d.position.set(0.6, 1, 0.8); this.scene.add(d);
    const d2 = new THREE.DirectionalLight(0xffffff, 0.5); d2.position.set(-1, -0.3, -0.6); this.scene.add(d2);
    this.group = new THREE.Group(); this.scene.add(this.group);
    this.marker = new THREE.Group(); this.scene.add(this.marker);
    this.center = new THREE.Vector3(); this.cache = {};
    this.edgesOn = true; this.markerOn = true; this.visible = true;
    this.mats();
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement);
    new IntersectionObserver((e) => { this.visible = e[0].isIntersecting; if (this.visible) this.draw(); }).observe(canvas);
    this.resize();
  }
  mats() {
    const css = getComputedStyle(document.documentElement);
    const dark = matchMedia('(prefers-color-scheme: dark)').matches;
    const t = document.documentElement.dataset.theme;
    const isDark = t ? t === 'dark' : dark;
    this.solid = new THREE.MeshStandardMaterial({ color: isDark ? 0x9aa6b2 : 0xaab4be, metalness: 0.15, roughness: 0.55, side: THREE.DoubleSide });
    this.line = new THREE.LineBasicMaterial({ color: isDark ? 0xe8e4da : 0x1d1c1a });
    this.accent = new THREE.Color(isDark ? 0xe8825a : 0xb23a13);
    void css;
  }
  setTheme() {
    this.mats();
    if (this.current) this.show(this.current, this.markerPos, true);
    else this.draw();
  }
  resize() {
    const p = this.canvas.parentElement, w = p.clientWidth, h = p.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
    this.draw();
  }
  async get(url) { return (this.cache[url] ||= loadGLB(url)); }
  // url: GLB path; markerPos: [x,y,z] in CAD coordinates (Z up) or null
  async show(url, markerPos, keepView) {
    const geoms = await this.get(url);
    this.current = url; this.markerPos = markerPos;
    this.group.clear(); this.marker.clear();
    for (const { g, mode } of geoms) {
      if (mode === 4) this.group.add(new THREE.Mesh(g, this.solid));
      else { this.edges = new THREE.LineSegments(g, this.line); this.group.add(this.edges); }
    }
    this.edges.visible = this.edgesOn;
    if (!this.framed) {
      // frame once, from the final part; later parts share the same origin so rounds stay comparable
      const box = new THREE.Box3().setFromBufferAttribute(geoms[0].g.getAttribute('position'));
      box.getCenter(this.center);
      const size = box.getSize(new THREE.Vector3()).length();
      this.size = size;
      this.camera.position.copy(this.center).add(new THREE.Vector3(0.9, 0.75, 1.15).normalize().multiplyScalar(size * 2.1));
      this.controls.target.copy(this.center);
      this.home = { p: this.camera.position.clone(), t: this.center.clone() };
      this.framed = true;
    }
    if (markerPos) {
      const [x, y, z] = markerPos; // CAD (Z up) -> glTF (Y up): (x, z, -y)
      const pos = new THREE.Vector3(x, z, -y);
      const ring = new THREE.Mesh(new THREE.SphereGeometry(this.size * 0.035, 20, 14),
        new THREE.MeshBasicMaterial({ color: this.accent, transparent: true, opacity: 0.85, depthTest: false }));
      ring.position.copy(pos); ring.renderOrder = 10;
      const halo = new THREE.Mesh(new THREE.SphereGeometry(this.size * 0.07, 20, 14),
        new THREE.MeshBasicMaterial({ color: this.accent, transparent: true, opacity: 0.22, depthTest: false }));
      halo.position.copy(pos); halo.renderOrder = 9;
      this.marker.add(ring, halo);
    }
    this.marker.visible = this.markerOn;
    this.controls.update();
    this.draw();
  }
  setEdges(v) { this.edgesOn = v; if (this.edges) this.edges.visible = v; this.draw(); }
  setMarker(v) { this.markerOn = v; this.marker.visible = v; this.draw(); }
  reset() {
    if (!this.home) return;
    this.camera.position.copy(this.home.p); this.controls.target.copy(this.home.t);
    this.controls.update(); this.draw();
  }
  draw() {
    if (!this.visible) return;
    cancelAnimationFrame(this._raf);
    this._raf = requestAnimationFrame(() => this.renderer.render(this.scene, this.camera));
  }
}
