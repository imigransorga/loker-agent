// Kantor AI Loker — ruang kantor 3D interaktif (Three.js)
// Karakter dibangun dari bentuk dasar (tanpa model eksternal).
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";

const host = document.getElementById("office3d");
const DATA = JSON.parse(document.getElementById("agents-data").textContent);
const BOARD = JSON.parse(document.getElementById("board-data").textContent);
const dark = matchMedia("(prefers-color-scheme: dark)").matches;
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------- renderer, scene, camera ----------
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
host.appendChild(renderer.domElement);

const labels = new CSS2DRenderer();
labels.domElement.className = "labels3d";
host.appendChild(labels.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(dark ? 0x15162b : 0xe9eef7);
scene.fog = new THREE.Fog(scene.background, 14, 28);

const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
const HOME_POS = new THREE.Vector3(0, 5.2, 8.6);
const HOME_TARGET = new THREE.Vector3(0, 1.45, -0.1);
const HOME_DIR = HOME_POS.clone().sub(HOME_TARGET);
let userMoved = false;
camera.position.copy(HOME_POS);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.copy(HOME_TARGET);
controls.enableDamping = true;
controls.minDistance = 2.5;
controls.maxDistance = 14;
controls.maxPolarAngle = Math.PI * 0.47;
controls.enablePan = false;

// ---------- lampu ----------
scene.add(new THREE.HemisphereLight(0xffffff, dark ? 0x30343c : 0xb8a58e, dark ? 1.2 : 1.6));
const sun = new THREE.DirectionalLight(0xfff2dd, dark ? 1.4 : 2.2);
sun.position.set(-5, 9, 6);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 30 });
sun.shadow.bias = -0.0005;
scene.add(sun);

// ---------- helper ----------
const mat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.75, ...extra });
function mesh(geo, material, pos = [0, 0, 0], parent = null, cast = true) {
  const m = new THREE.Mesh(geo, material);
  m.position.set(...pos);
  m.castShadow = cast;
  m.receiveShadow = true;
  if (parent) parent.add(m);
  return m;
}
const box = (w, h, d) => new THREE.BoxGeometry(w, h, d);
const cyl = (rt, rb, h, s = 20) => new THREE.CylinderGeometry(rt, rb, h, s);
const sph = (r, ws = 24, hs = 18, ...rest) => new THREE.SphereGeometry(r, ws, hs, ...rest);

function canvasTexture(w, h, draw) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  draw(c.getContext("2d"));
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

// ---------- ruangan ----------
const floorTex = canvasTexture(512, 512, g => {
  g.fillStyle = dark ? "#2a2f3a" : "#d9c3a5"; g.fillRect(0, 0, 512, 512);
  g.strokeStyle = dark ? "#232833" : "#c9b190"; g.lineWidth = 4;
  for (let i = 0; i <= 512; i += 64) { g.beginPath(); g.moveTo(0, i); g.lineTo(512, i); g.stroke(); }
  for (let r = 0; r < 8; r++) for (let i = (r % 2) * 128; i <= 512; i += 256) {
    g.beginPath(); g.moveTo(i, r * 64); g.lineTo(i, r * 64 + 64); g.stroke();
  }
});
floorTex.wrapS = floorTex.wrapT = THREE.RepeatWrapping;
floorTex.repeat.set(5, 4);
const floor = mesh(new THREE.PlaneGeometry(24, 16), mat(0xffffff, { map: floorTex }), [0, 0, 1], scene, false);
floor.rotation.x = -Math.PI / 2;

const wallMat = mat(dark ? 0x2b3140 : 0xf5f1ea);
mesh(box(24, 6, 0.2), wallMat, [0, 3, -3.2], scene, false);
const sideWall = mesh(box(0.2, 6, 12), wallMat, [-9, 3, 2.8], scene, false);
mesh(box(24, 0.25, 0.25), mat(dark ? 0x3a4152 : 0xe3dccf), [0, 0.12, -3.05], scene, false);

// jendela
const win = new THREE.Group();
mesh(box(3.4, 2, 0.08), mat(0x9fd3ff, { emissive: 0x6fb4ff, emissiveIntensity: dark ? 0.6 : 0.35 }), [0, 0, 0], win, false);
const frameMat = mat(0xffffff);
mesh(box(3.6, 0.1, 0.12), frameMat, [0, 1.05, 0.02], win, false);
mesh(box(3.6, 0.1, 0.12), frameMat, [0, -1.05, 0.02], win, false);
mesh(box(0.1, 2.1, 0.12), frameMat, [0, 0, 0.02], win, false);
mesh(box(0.1, 2.1, 0.12), frameMat, [-1.75, 0, 0.02], win, false);
mesh(box(0.1, 2.1, 0.12), frameMat, [1.75, 0, 0.02], win, false);
win.position.set(-4.6, 3, -3.08);
scene.add(win);

// papan tulis berisi statistik
const boardTex = canvasTexture(1024, 512, g => {
  g.fillStyle = "#fbfbf8"; g.fillRect(0, 0, 1024, 512);
  g.fillStyle = "#1d2330"; g.font = "bold 64px -apple-system, Segoe UI, sans-serif";
  g.fillText("TARGET: DAPAT KERJA 💼", 48, 100);
  g.font = "48px -apple-system, Segoe UI, sans-serif";
  g.fillStyle = "#2f6fed"; g.fillText(`• Loker terkumpul : ${BOARD.total}`, 60, 210);
  g.fillStyle = "#1f9d55"; g.fillText(`• Sangat cocok    : ${BOARD.high}`, 60, 290);
  g.fillStyle = "#c77d0a"; g.fillText(`• Sudah dilamar   : ${BOARD.applied}`, 60, 370);
  g.fillStyle = "#d64545"; g.fillText(`• Interview       : ${BOARD.interview}`, 60, 450);
});
const board = new THREE.Group();
mesh(box(3.3, 1.75, 0.06), mat(0xbfc5cf), [0, 0, 0], board, false);
mesh(new THREE.PlaneGeometry(3.15, 1.6), mat(0xffffff, { map: boardTex, roughness: 0.4 }), [0, 0, 0.035], board, false);
board.position.set(1.6, 2.9, -3.05);
scene.add(board);

// jam dinding (jarumnya bergerak sesuai waktu asli)
const clock = new THREE.Group();
const clockFace = mesh(cyl(0.42, 0.42, 0.06, 40), mat(0xffffff), [0, 0, 0], clock, false);
clockFace.rotation.x = Math.PI / 2;
const rim = mesh(new THREE.TorusGeometry(0.42, 0.04, 10, 40), mat(0x333842), [0, 0, 0.02], clock, false);
const hourHand = new THREE.Group(), minHand = new THREE.Group();
mesh(box(0.04, 0.22, 0.02), mat(0x222222), [0, 0.11, 0], hourHand, false);
mesh(box(0.025, 0.33, 0.02), mat(0x222222), [0, 0.16, 0], minHand, false);
hourHand.position.z = minHand.position.z = 0.05;
clock.add(hourHand, minHand);
clock.position.set(5.6, 3.4, -3.05);
scene.add(clock);

// tanaman besar di pojok + rak buku
function bigPlant(x, z) {
  const g = new THREE.Group();
  mesh(cyl(0.3, 0.24, 0.55), mat(0xc96f4a), [0, 0.28, 0], g);
  const leaf = mat(0x3f9a5a);
  [[0, 1.0, 0, 0.45], [0.22, 1.35, 0.05, 0.35], [-0.2, 1.3, -0.05, 0.36], [0, 1.65, 0, 0.3]]
    .forEach(([a, b, c, r]) => mesh(new THREE.IcosahedronGeometry(r, 1), leaf, [a, b, c], g));
  g.position.set(x, 0, z);
  scene.add(g);
}
bigPlant(-8.1, -2.3);
bigPlant(7.6, -2.4);

const shelf = new THREE.Group();
mesh(box(1.6, 2.2, 0.45), mat(0x8e6440), [0, 1.1, 0], shelf);
const bookColors = [0x2f6fed, 0xe0773b, 0x1f9d74, 0x8a5cf6, 0xd64545, 0xf2c14e];
for (let row = 0; row < 3; row++) {
  mesh(box(1.5, 0.04, 0.42), mat(0x6c4b30), [0, 0.45 + row * 0.62, 0.02], shelf);
  for (let i = 0; i < 7; i++) {
    const h = 0.35 + Math.random() * 0.15;
    mesh(box(0.15, h, 0.32), mat(bookColors[(i + row) % 6]), [-0.6 + i * 0.19, 0.47 + row * 0.62 + h / 2, 0.04], shelf);
  }
}
shelf.position.set(-8.6, 0, 1.2);
shelf.rotation.y = Math.PI / 2;
scene.add(shelf);

// karpet
const rug = mesh(new THREE.CircleGeometry(5.6, 48), mat(dark ? 0x30384a : 0xcfd8e6), [0, 0.01, 0.8], scene, false);
rug.rotation.x = -Math.PI / 2;
rug.scale.y = 0.55;

// ---------- karakter ----------
const agents = {};      // key -> objek animasi
// depan: karyawan yang aktif, belakang: yang belum masuk kerja
const LAYOUT = {
  scout: [-3.75, 1.2], info: [-1.25, 1.45], analyst: [1.25, 1.45], coach: [3.75, 1.2],
  applier: [-2.75, -1.75], builder: [0, -1.6], manager: [2.75, -1.75],
};
const SCALE = 1.3;
const clickable = [];   // mesh yang bisa diklik

function buildAgent(a, index, total) {
  const L = a.look;
  const root = new THREE.Group();
  // 2 baris: depan 3 meja, belakang 2 meja
  const [x, z] = LAYOUT[a.key] || [(index - 3) * 2.6, 3.5];
  root.position.set(x, 0, z);
  root.rotation.y = -x * 0.05;
  root.scale.setScalar(SCALE);
  root.userData.key = a.key;
  scene.add(root);

  const shirt = mat(L.shirt), skin = mat(L.skin), hairM = mat(L.hair), dark1 = mat(0x222222);

  // kursi
  mesh(box(0.62, 0.08, 0.6), mat(0x3c4250), [0, 0.48, -0.05], root);
  mesh(box(0.62, 0.7, 0.08), mat(0x3c4250), [0, 0.9, -0.38], root);
  mesh(cyl(0.04, 0.04, 0.4), mat(0x888888), [0, 0.26, -0.05], root);
  mesh(cyl(0.3, 0.3, 0.04), mat(0x555555), [0, 0.04, -0.05], root);

  // badan
  const body = new THREE.Group();
  root.add(body);
  mesh(new THREE.CapsuleGeometry(0.22, 0.32, 6, 16), shirt, [0, 0.9, -0.02], body);
  mesh(box(0.5, 0.18, 0.5), mat(0x2d3341), [0, 0.6, 0.12], body); // paha

  // kepala
  const head = new THREE.Group();
  head.position.set(0, 1.22, 0);
  body.add(head);
  mesh(cyl(0.06, 0.07, 0.12), skin, [0, 0, 0], head);
  const face = mesh(sph(0.19), skin, [0, 0.2, 0.01], head);

  const eyes = new THREE.Group();
  eyes.position.set(0, 0.22, 0.17);
  head.add(eyes);
  mesh(sph(0.022, 10, 8), dark1, [-0.065, 0, 0], eyes, false);
  mesh(sph(0.022, 10, 8), dark1, [0.065, 0, 0], eyes, false);
  const mouth = mesh(new THREE.TorusGeometry(0.045, 0.009, 6, 14, Math.PI), mat(0x7a3b2e), [0, 0.13, 0.172], head, false);
  mouth.rotation.z = Math.PI;
  // pipi merona
  const blush = mat(0xff8a80, { transparent: true, opacity: 0.35 });
  mesh(sph(0.03, 10, 8), blush, [-0.11, 0.16, 0.15], head, false);
  mesh(sph(0.03, 10, 8), blush, [0.11, 0.16, 0.15], head, false);

  // rambut / aksesoris kepala
  if (L.hair_style === "short") {
    mesh(sph(0.2, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2.1), hairM, [0, 0.22, -0.015], head);
  } else if (L.hair_style === "long") {
    mesh(sph(0.205, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), hairM, [0, 0.22, -0.02], head);
    mesh(box(0.38, 0.42, 0.14), hairM, [0, 0.05, -0.12], head);
  } else if (L.hair_style === "hijab") {
    mesh(sph(0.235), hairM, [0, 0.21, -0.04], head);
    mesh(cyl(0.2, 0.3, 0.3), hairM, [0, -0.02, -0.02], head);
    face.position.z = 0.05; face.scale.set(0.92, 1, 0.9);
    eyes.position.z = 0.19; mouth.position.z = 0.19;
  } else if (L.hair_style === "bun") {
    mesh(sph(0.2, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2.1), hairM, [0, 0.22, -0.015], head);
    mesh(sph(0.09, 16, 12), hairM, [0, 0.43, -0.08], head);
  } else if (L.hair_style === "curly") {
    [[-0.12, 0.33, 0], [0, 0.38, 0], [0.12, 0.33, 0], [-0.17, 0.24, -0.04], [0.17, 0.24, -0.04], [-0.07, 0.36, -0.1], [0.07, 0.36, -0.1], [0, 0.3, -0.16]]
      .forEach(p => mesh(sph(0.085, 12, 10), hairM, p, head));
  } else if (L.hair_style === "cap") {
    mesh(sph(0.205, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), mat(0xd64545), [0, 0.24, 0], head);
    const brim = mesh(cyl(0.16, 0.16, 0.02, 24), mat(0xd64545), [0, 0.25, 0.17], head);
    brim.scale.z = 0.9;
  }
  if (L.extra === "glasses") {
    const gm = mat(0x222222);
    [-0.065, 0.065].forEach(gx => mesh(new THREE.TorusGeometry(0.045, 0.008, 8, 20), gm, [gx, 0.22, 0.185], head, false));
    mesh(box(0.04, 0.008, 0.008), gm, [0, 0.22, 0.19], head, false);
  }
  if (L.extra === "headset") {
    const hm = mat(0x2a2a2a);
    const band = mesh(new THREE.TorusGeometry(0.21, 0.018, 8, 24, Math.PI), hm, [0, 0.22, 0], head);
    band.rotation.y = Math.PI / 2; band.rotation.z = 0;
    band.rotation.set(0, Math.PI / 2, 0);
    mesh(cyl(0.055, 0.055, 0.05), hm, [-0.205, 0.2, 0], head).rotation.z = Math.PI / 2;
    mesh(cyl(0.055, 0.055, 0.05), hm, [0.205, 0.2, 0], head).rotation.z = Math.PI / 2;
    const mic = mesh(box(0.015, 0.015, 0.16), hm, [-0.19, 0.13, 0.08], head);
    mic.rotation.y = -0.4;
  }

  // lengan (pivot di bahu)
  function arm(side) {
    const pivot = new THREE.Group();
    pivot.position.set(side * 0.27, 1.08, 0);
    body.add(pivot);
    mesh(new THREE.CapsuleGeometry(0.065, 0.3, 4, 10), shirt, [0, -0.2, 0], pivot);
    const hand = mesh(sph(0.065, 14, 10), skin, [0, -0.41, 0], pivot);
    pivot.rotation.x = -1.15;  // menjulur ke keyboard
    pivot.rotation.z = side * 0.12;
    return { pivot, hand };
  }
  const armL = arm(-1), armR = arm(1);

  // meja
  const deskMat = mat(0xb9875a, { roughness: 0.6 });
  mesh(box(1.7, 0.06, 0.85), deskMat, [0, 0.78, 0.62], root);
  mesh(box(1.7, 0.66, 0.04), mat(0x9a7049), [0, 0.42, 1.0], root); // panel depan menutupi kaki
  [[-0.8, 0.25], [0.8, 0.25]].forEach(([dx, dz]) => mesh(box(0.06, 0.75, 0.06), mat(0x8e6440), [dx, 0.38, dz], root));

  // laptop
  const lap = new THREE.Group();
  lap.position.set(0, 0.81, 0.5);
  root.add(lap);
  mesh(box(0.56, 0.025, 0.38), mat(0xc7ccd6, { metalness: 0.4, roughness: 0.4 }), [0, 0, 0], lap);
  const lid = new THREE.Group();
  lid.position.set(0, 0.01, 0.19);
  lap.add(lid);
  mesh(box(0.56, 0.36, 0.02), mat(0xc7ccd6, { metalness: 0.4, roughness: 0.4 }), [0, 0.18, 0], lid);
  const screenMat = new THREE.MeshStandardMaterial({ color: 0x0b1020, emissive: 0x5fb4ff, emissiveIntensity: 0.9 });
  mesh(new THREE.PlaneGeometry(0.5, 0.3), screenMat, [0, 0.18, -0.012], lid, false).rotation.y = Math.PI;
  const logoMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.6 });
  mesh(cyl(0.035, 0.035, 0.005, 20), logoMat, [0, 0.19, 0.012], lid, false).rotation.x = Math.PI / 2;
  lid.rotation.x = 0.28;
  const screenLight = new THREE.PointLight(0x7cc4ff, 1.2, 1.3, 2);
  screenLight.position.set(0, 1.05, 0.3);
  root.add(screenLight);

  // kopi + uap
  mesh(cyl(0.06, 0.05, 0.12), mat(0xf4f1ea), [0.6, 0.87, 0.55], root);
  mesh(new THREE.TorusGeometry(0.035, 0.012, 6, 12), mat(0xf4f1ea), [0.66, 0.87, 0.55], root).rotation.y = Math.PI / 2;
  const steam = [];
  for (let i = 0; i < 3; i++) {
    const s = mesh(sph(0.025, 8, 6), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.5 }), [0.6, 0.95, 0.55], root, false);
    s.userData.phase = i / 3;
    steam.push(s);
  }
  // tanaman meja
  mesh(cyl(0.07, 0.06, 0.12), mat(0xc96f4a), [-0.62, 0.87, 0.7], root);
  mesh(new THREE.IcosahedronGeometry(0.11, 0), mat(0x3f9a5a), [-0.62, 1.0, 0.7], root);

  // cincin seleksi di lantai
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.95, 1.08, 48),
    new THREE.MeshBasicMaterial({ color: 0x4f86ff, transparent: true, opacity: 0, side: THREE.DoubleSide }));
  ring.rotation.x = -Math.PI / 2;
  ring.position.set(0, 0.02, 0.3);
  root.add(ring);

  // label HTML: gelembung status + papan nama
  const bubble = document.createElement("div");
  bubble.className = "bubble3d";
  const bubbleObj = new CSS2DObject(bubble);
  bubbleObj.position.set(0, 1.9, 0);
  root.add(bubbleObj);
  const plate = document.createElement("div");
  plate.className = "plate3d";
  plate.innerHTML = `<b>${a.icon} ${a.name}</b><small>${a.role}</small>`;
  plate.title = a.role;
  plate.addEventListener("click", () => window.selectAgent(a.key));
  const plateObj = new CSS2DObject(plate);
  plateObj.position.set(0, 0.25, 1.15);
  root.add(plateObj);

  root.traverse(o => { if (o.isMesh) { o.userData.key = a.key; clickable.push(o); } });

  const ag = {
    key: a.key, root, body, head, eyes, armL, armR, lid, screenMat, logoMat, screenLight, ring, steam,
    bubble, plate, state: a.state, phase: Math.random() * 10, hover: 0, wave: 0, selected: false,
  };
  setState(ag, a.state);
  agents[a.key] = ag;
}

const BUBBLE_TEXT = {
  work: { scout: "Siap cari loker! 🔎", analyst: "Laporan siap 📈", coach: "Yuk latihan interview 🎤", info: "Ada kabar baru 📬" },
  busy: { scout: "Lagi nyari loker… 🔥", coach: "Lagi nyiapin materi… ✍️" },
  off: "Zzz 💤",
  done: "Selesai! ✅",
};

function setState(ag, state) {
  ag.state = state;
  ag.bubble.className = "bubble3d " + state;
  const txt = BUBBLE_TEXT[state];
  ag.bubble.textContent = typeof txt === "object" ? (txt[ag.key] || "Sedang kerja…") : txt;
  const on = state !== "off";
  ag.screenMat.emissiveIntensity = on ? 0.9 : 0.02;
  ag.logoMat.emissiveIntensity = on ? 0.6 : 0;
  ag.screenLight.intensity = on ? 1.2 : 0;
  ag.lid.rotation.x = on ? 0.28 : 0.9;   // laptop agen yang tidur setengah tertutup
  ag.steam.forEach(s => (s.visible = on));
}

DATA.forEach((a, i) => buildAgent(a, i, DATA.length));

// ---------- interaksi ----------
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let hovered = null, downAt = null;

function pick(ev) {
  const r = renderer.domElement.getBoundingClientRect();
  pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
  pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(clickable, false)[0];
  return hit ? hit.object.userData.key : null;
}
renderer.domElement.addEventListener("pointermove", ev => {
  hovered = pick(ev);
  renderer.domElement.style.cursor = hovered ? "pointer" : "grab";
});
renderer.domElement.addEventListener("pointerleave", () => (hovered = null));
renderer.domElement.addEventListener("pointerdown", ev => (downAt = [ev.clientX, ev.clientY]));
renderer.domElement.addEventListener("pointerup", ev => {
  if (!downAt) return;
  const moved = Math.hypot(ev.clientX - downAt[0], ev.clientY - downAt[1]);
  downAt = null;
  if (moved > 6) return; // itu drag untuk memutar, bukan klik
  const key = pick(ev);
  if (key) window.selectAgent(key);
});

// ---------- kamera fokus ----------
let camGoal = null;
function focusAgent(key) {
  const ag = agents[key];
  if (!ag) return;
  const target = ag.root.position.clone().add(new THREE.Vector3(0, 1.2, 0.35));
  const dir = new THREE.Vector3(ag.root.position.x * 0.2, 1.2, 3.8);
  camGoal = { target, pos: target.clone().add(dir) };
}
function resetView() { camGoal = { target: HOME_TARGET.clone(), pos: HOME_POS.clone() }; }
controls.addEventListener("start", () => { camGoal = null; userMoved = true; });

document.addEventListener("agent-selected", e => {
  Object.values(agents).forEach(ag => (ag.selected = ag.key === e.detail.key));
  const ag = agents[e.detail.key];
  if (ag) { ag.wave = 1.6; if (e.detail.focus !== false) focusAgent(e.detail.key); }
});
document.addEventListener("agent-busy", e => {
  const ag = agents[e.detail.key];
  if (ag) setState(ag, e.detail.state);
});
document.getElementById("resetView")?.addEventListener("click", resetView);

// ---------- ukuran ----------
function resize() {
  const w = host.clientWidth, h = host.clientHeight;
  renderer.setSize(w, h);
  labels.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  // mundurkan kamera bila layar sempit supaya 5 karyawan muat semua
  const fit = Math.max(1, 1.62 / camera.aspect);
  HOME_POS.copy(HOME_TARGET).add(HOME_DIR.clone().multiplyScalar(fit));
  if (!userMoved && !camGoal) camera.position.copy(HOME_POS);
}
new ResizeObserver(resize).observe(host);
resize();

// ---------- animasi ----------
const clockT = new THREE.Clock();
function animate() {
  const dt = Math.min(clockT.getDelta(), 0.05);
  const t = clockT.elapsedTime;
  const m = reduceMotion ? 0.15 : 1;

  for (const ag of Object.values(agents)) {
    const p = t + ag.phase;
    ag.hover += ((hovered === ag.key ? 1 : 0) - ag.hover) * Math.min(1, dt * 10);

    if (ag.state === "off") {
      ag.head.rotation.set(0.35 + Math.sin(p * 0.8) * 0.03 * m, 0, 0.25);
      ag.eyes.scale.y = 0.12;
      ag.armL.pivot.rotation.x = ag.armR.pivot.rotation.x = -1.35;
      ag.body.position.y = Math.sin(p * 0.8) * 0.01 * m;   // napas tidur
    } else {
      const speed = ag.state === "busy" ? 22 : 11;
      const amp = (ag.state === "busy" ? 0.12 : 0.07) * m;
      ag.armL.pivot.rotation.x = -1.15 + Math.sin(p * speed) * amp;
      ag.armR.pivot.rotation.x = -1.15 + Math.sin(p * speed + Math.PI) * amp;
      ag.head.rotation.set(0.12 + Math.sin(p * 0.9) * 0.04 * m, Math.sin(p * 0.5) * 0.12 * m, 0);
      ag.body.position.y = 0;
      // kedip tiap ~4 detik
      ag.eyes.scale.y = (p % 4) < 0.12 ? 0.1 : 1;
      if (ag.state === "busy") ag.screenMat.emissive.setHSL(0.58 + Math.sin(t * 6) * 0.05, 0.9, 0.55);
      else ag.screenMat.emissive.setHex(0x5fb4ff);
    }

    // melambai saat dipilih
    if (ag.wave > 0) {
      ag.wave -= dt;
      ag.armR.pivot.rotation.x = -2.9;
      ag.armR.pivot.rotation.z = 0.35 + Math.sin(t * 14) * 0.35;
      ag.head.rotation.set(-0.05, 0, Math.sin(t * 4) * 0.08);
      ag.eyes.scale.y = 1;
    } else {
      ag.armR.pivot.rotation.z = 0.12;
    }

    // efek hover & seleksi
    const lift = ag.hover * 0.06 + (ag.selected ? 0.03 : 0);
    ag.root.position.y += (lift - ag.root.position.y) * Math.min(1, dt * 8);
    ag.ring.material.opacity = ag.selected ? 0.55 + Math.sin(t * 3) * 0.2 : ag.hover * 0.35;
    ag.ring.rotation.z = t * 0.3;
    ag.bubble.classList.toggle("hot", ag.hover > 0.5 || ag.selected);
    ag.plate.classList.toggle("selected", ag.selected);

    // uap kopi
    ag.steam.forEach(s => {
      const k = (t * 0.5 + s.userData.phase) % 1;
      s.position.y = 0.95 + k * 0.3;
      s.position.x = 0.6 + Math.sin(k * 8 + s.userData.phase * 6) * 0.03;
      s.material.opacity = (1 - k) * 0.45;
      s.scale.setScalar(0.7 + k);
    });
  }

  // jam dinding
  const now = new Date();
  minHand.rotation.z = -(now.getMinutes() + now.getSeconds() / 60) / 60 * Math.PI * 2;
  hourHand.rotation.z = -((now.getHours() % 12) + now.getMinutes() / 60) / 12 * Math.PI * 2;

  // gerak kamera halus ke target
  if (camGoal) {
    const k = Math.min(1, dt * 3.2);
    controls.target.lerp(camGoal.target, k);
    camera.position.lerp(camGoal.pos, k);
    if (camera.position.distanceTo(camGoal.pos) < 0.02) camGoal = null;
  }
  controls.update();
  renderer.render(scene, camera);
  labels.render(scene, camera);
  requestAnimationFrame(animate);
}
animate();

// 3D berhasil dimuat -> sembunyikan versi 2D cadangan
document.getElementById("office2d").hidden = true;
host.hidden = false;
document.getElementById("office3dHelp").hidden = false;
resize();
window.office3dReady = true;
if (window.currentAgent) {
  Object.values(agents).forEach(ag => (ag.selected = ag.key === window.currentAgent));
}
