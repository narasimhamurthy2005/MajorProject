import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const canvas = document.getElementById("hero-canvas");
const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(
  55,
  window.innerWidth / window.innerHeight,
  0.1,
  1000
);
camera.position.set(0, 2.2, 9);

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

// ---------- Lighting ----------
scene.add(new THREE.AmbientLight(0x99aaff, 0.5));
const sun = new THREE.DirectionalLight(0xffffff, 2.2);
sun.position.set(6, 4, 6);
scene.add(sun);
const rim = new THREE.PointLight(0x4fd6ff, 1.2, 30);
rim.position.set(-6, -2, -4);
scene.add(rim);

// ---------- Starfield ----------
function makeStars(count, spread) {
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    positions[i * 3] = (Math.random() - 0.5) * spread;
    positions[i * 3 + 1] = (Math.random() - 0.5) * spread;
    positions[i * 3 + 2] = (Math.random() - 0.5) * spread;
  }
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.06, transparent: true, opacity: 0.8 });
  return new THREE.Points(geo, mat);
}
scene.add(makeStars(2200, 140));
scene.add(makeStars(700, 60));

// ---------- Earth (simple glowing sphere) ----------
const earthGeo = new THREE.SphereGeometry(2, 48, 48);
const earthMat = new THREE.MeshStandardMaterial({
  color: 0x123a6b,
  emissive: 0x0a2a55,
  emissiveIntensity: 0.4,
  roughness: 0.8,
  metalness: 0.1,
});
const earth = new THREE.Mesh(earthGeo, earthMat);
earth.position.set(0, -4.4, 0);
scene.add(earth);

const glowGeo = new THREE.SphereGeometry(2.15, 48, 48);
const glowMat = new THREE.MeshBasicMaterial({ color: 0x4fd6ff, transparent: true, opacity: 0.08 });
const glow = new THREE.Mesh(glowGeo, glowMat);
glow.position.copy(earth.position);
scene.add(glow);

// ---------- Procedural satellite ----------
const satellite = new THREE.Group();

const bodyMat = new THREE.MeshStandardMaterial({ color: 0xd7dde8, metalness: 0.7, roughness: 0.35 });
const goldMat = new THREE.MeshStandardMaterial({ color: 0xd8a84e, metalness: 0.8, roughness: 0.3 });
const panelMat = new THREE.MeshStandardMaterial({
  color: 0x123a6b,
  emissive: 0x1a4d8f,
  emissiveIntensity: 0.3,
  metalness: 0.4,
  roughness: 0.5,
});
const darkMat = new THREE.MeshStandardMaterial({ color: 0x2a2f3a, metalness: 0.6, roughness: 0.4 });

// core body
const body = new THREE.Mesh(new THREE.BoxGeometry(1.3, 1.0, 1.3), bodyMat);
satellite.add(body);

// gold insulation wrap on top/bottom
const capTop = new THREE.Mesh(new THREE.BoxGeometry(1.34, 0.15, 1.34), goldMat);
capTop.position.y = 0.58;
satellite.add(capTop);
const capBottom = capTop.clone();
capBottom.position.y = -0.58;
satellite.add(capBottom);

// dish / antenna
const dish = new THREE.Mesh(
  new THREE.SphereGeometry(0.5, 24, 24, 0, Math.PI * 2, 0, Math.PI / 2.2),
  darkMat
);
dish.rotation.x = Math.PI;
dish.position.set(0, 0.85, 0.4);
satellite.add(dish);
const dishStem = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.4, 8), darkMat);
dishStem.position.set(0, 0.62, 0.4);
satellite.add(dishStem);

// thin antenna rods
for (const [x, z] of [[0.5, 0.5], [-0.5, 0.5], [0.5, -0.5], [-0.5, -0.5]]) {
  const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.9, 6), darkMat);
  rod.position.set(x, -0.9, z);
  satellite.add(rod);
}

// solar panel wings (each made of a frame + panel segments)
function makeSolarWing(direction) {
  const wing = new THREE.Group();
  const panelCount = 4;
  const panelW = 0.85, panelH = 1.7;
  for (let i = 0; i < panelCount; i++) {
    const seg = new THREE.Mesh(new THREE.BoxGeometry(panelW, panelH, 0.04), panelMat);
    seg.position.x = direction * (0.75 + i * (panelW + 0.03));
    wing.add(seg);
    // grid lines for detail
    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(seg.geometry),
      new THREE.LineBasicMaterial({ color: 0x0b1830 })
    );
    edges.position.copy(seg.position);
    wing.add(edges);
  }
  const strut = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.7, 8), darkMat);
  strut.rotation.z = Math.PI / 2;
  strut.position.x = direction * 0.35;
  wing.add(strut);
  return wing;
}
satellite.add(makeSolarWing(1));
satellite.add(makeSolarWing(-1));

satellite.rotation.z = 0.35;
satellite.rotation.x = 0.15;
scene.add(satellite);

// ---------- Controls ----------
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.6;
controls.enableZoom = true;
controls.minDistance = 5;
controls.maxDistance = 16;
controls.target.set(0, 0.5, 0);

// ---------- Animation ----------
const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();

  satellite.rotation.y += 0.006;
  satellite.position.y = Math.sin(t * 0.5) * 0.25;

  earth.rotation.y += 0.0015;
  glow.rotation.y = earth.rotation.y;

  controls.update();
  renderer.render(scene, camera);
}
animate();

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
