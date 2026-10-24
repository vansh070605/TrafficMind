import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import type { Vehicle } from '../types';

interface Viewport3DProps {

  vehicles: Vehicle[];
  tlsState: string;
  currentPhase: number;
}

export const Viewport3D: React.FC<Viewport3DProps> = ({ vehicles, tlsState, currentPhase }) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const vehicleMeshesRef = useRef<Map<string, THREE.Group>>(new Map());
  const lightsRef = useRef<{ [key: string]: THREE.Mesh }>({});

  useEffect(() => {
    if (!mountRef.current) return;
    const width = mountRef.current.clientWidth;
    const height = mountRef.current.clientHeight || 520;

    // 1. Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060914);
    scene.fog = new THREE.FogExp2(0x060914, 0.0035);
    sceneRef.current = scene;

    // 2. Camera
    const camera = new THREE.PerspectiveCamera(48, width / height, 0.1, 1000);
    // Angled isometric-style perspective over intersection center
    camera.position.set(0, 180, 230);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // 3. Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    rendererRef.current = renderer;
    mountRef.current.appendChild(renderer.domElement);

    // 4. Lighting
    const ambientLight = new THREE.AmbientLight(0x2a3b5c, 1.8);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xa5c9ff, 1.2);
    dirLight.position.set(80, 150, 100);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 1024;
    dirLight.shadow.mapSize.height = 1024;
    scene.add(dirLight);

    // Cyan accent light in intersection center
    const centerGlow = new THREE.PointLight(0x00f0ff, 2.5, 90);
    centerGlow.position.set(0, 8, 0);
    scene.add(centerGlow);

    // 5. Ground / Urban Plane with Grid
    const groundGeo = new THREE.PlaneGeometry(800, 800);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x070c18,
      roughness: 0.85,
      metalness: 0.1,
    });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.2;
    ground.receiveShadow = true;
    scene.add(ground);

    const gridHelper = new THREE.GridHelper(600, 40, 0x1e3a8a, 0x0f172a);
    gridHelper.position.y = 0.05;
    scene.add(gridHelper);

    // 6. Roads (Cross Intersection)
    const ROAD_WIDTH = 28;
    const ROAD_LENGTH = 500;
    const roadMat = new THREE.MeshStandardMaterial({ color: 0x13192b, roughness: 0.6 });

    // North-South Road
    const nsRoadGeo = new THREE.PlaneGeometry(ROAD_WIDTH, ROAD_LENGTH);
    const nsRoad = new THREE.Mesh(nsRoadGeo, roadMat);
    nsRoad.rotation.x = -Math.PI / 2;
    nsRoad.position.y = 0.1;
    scene.add(nsRoad);

    // East-West Road
    const ewRoadGeo = new THREE.PlaneGeometry(ROAD_LENGTH, ROAD_WIDTH);
    const ewRoad = new THREE.Mesh(ewRoadGeo, roadMat);
    ewRoad.rotation.x = -Math.PI / 2;
    ewRoad.position.y = 0.1;
    scene.add(ewRoad);

    // Center Junction Zone
    const centerJuncGeo = new THREE.PlaneGeometry(ROAD_WIDTH, ROAD_WIDTH);
    const centerJuncMat = new THREE.MeshStandardMaterial({ color: 0x1a233d, roughness: 0.5 });
    const centerJunc = new THREE.Mesh(centerJuncGeo, centerJuncMat);
    centerJunc.rotation.x = -Math.PI / 2;
    centerJunc.position.y = 0.15;
    scene.add(centerJunc);

    // Lane Markings (Yellow center dash & white borders)
    const createDashes = (isVertical: boolean) => {
      const dashGeo = new THREE.PlaneGeometry(isVertical ? 0.6 : 3.5, isVertical ? 3.5 : 0.6);
      const dashMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, opacity: 0.6, transparent: true });
      for (let i = -ROAD_LENGTH / 2; i <= ROAD_LENGTH / 2; i += 12) {
        if (Math.abs(i) < ROAD_WIDTH / 2) continue; // skip junction center
        const dash = new THREE.Mesh(dashGeo, dashMat);
        dash.rotation.x = -Math.PI / 2;
        dash.position.y = 0.2;
        if (isVertical) dash.position.set(0, 0.2, i);
        else dash.position.set(i, 0.2, 0);
        scene.add(dash);
      }
    };
    createDashes(true);
    createDashes(false);

    // 7. Traffic Light Gantries with glowing spherical orbs
    const createTrafficLight = (name: string, x: number, z: number, angleY: number) => {
      const group = new THREE.Group();
      group.position.set(x, 0, z);
      group.rotation.y = angleY;

      // Pole
      const poleGeo = new THREE.CylinderGeometry(0.5, 0.5, 18);
      const poleMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.7 });
      const pole = new THREE.Mesh(poleGeo, poleMat);
      pole.position.y = 9;
      group.add(pole);

      // Light Head Box
      const headGeo = new THREE.BoxGeometry(2.4, 6.5, 1.8);
      const headMat = new THREE.MeshStandardMaterial({ color: 0x090d16 });
      const head = new THREE.Mesh(headGeo, headMat);
      head.position.set(0, 15, 0);
      group.add(head);

      // Spheres (Red, Yellow, Green)
      const lightGeo = new THREE.SphereGeometry(0.8, 16, 16);
      const redMat = new THREE.MeshBasicMaterial({ color: 0x330000 });
      const yellowMat = new THREE.MeshBasicMaterial({ color: 0x332200 });
      const greenMat = new THREE.MeshBasicMaterial({ color: 0x003300 });

      const redMesh = new THREE.Mesh(lightGeo, redMat);
      redMesh.position.set(0, 16.8, 1.0);
      group.add(redMesh);

      const yellowMesh = new THREE.Mesh(lightGeo, yellowMat);
      yellowMesh.position.set(0, 15, 1.0);
      group.add(yellowMesh);

      const greenMesh = new THREE.Mesh(lightGeo, greenMat);
      greenMesh.position.set(0, 13.2, 1.0);
      group.add(greenMesh);

      lightsRef.current[`${name}_red`] = redMesh;
      lightsRef.current[`${name}_yellow`] = yellowMesh;
      lightsRef.current[`${name}_green`] = greenMesh;

      scene.add(group);
    };

    createTrafficLight('N', -18, 20, 0);
    createTrafficLight('S', 18, -20, Math.PI);
    createTrafficLight('E', -20, -18, Math.PI / 2);
    createTrafficLight('W', 20, 18, -Math.PI / 2);

    // 8. Animation Loop
    let animId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Gentle camera orbit sway
      camera.position.x = Math.sin(elapsed * 0.15) * 25;
      camera.lookAt(0, 4, 0);

      renderer.render(scene, camera);
    };
    animate();

    // Resize Handler
    const handleResize = () => {
      if (!mountRef.current || !rendererRef.current || !cameraRef.current) return;
      const w = mountRef.current.clientWidth;
      const h = mountRef.current.clientHeight || 520;
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animId);
      if (rendererRef.current && mountRef.current) {
        mountRef.current.removeChild(rendererRef.current.domElement);
        rendererRef.current.dispose();
      }
    };
  }, []);

  // Update Traffic Lights Visual State
  useEffect(() => {
    // Current Phase: 0 = NS Green, 1 = NS Yellow, 2 = EW Green, 3 = EW Yellow
    const isNSGreen = currentPhase === 0;
    const isNSYellow = currentPhase === 1;
    const isEWGreen = currentPhase === 2;
    const isEWYellow = currentPhase === 3;

    const setSignal = (arm: 'N' | 'S' | 'E' | 'W', state: 'green' | 'yellow' | 'red') => {
      const red = lightsRef.current[`${arm}_red`];

      const yellow = lightsRef.current[`${arm}_yellow`];
      const green = lightsRef.current[`${arm}_green`];

      if (red) (red.material as THREE.MeshBasicMaterial).color.setHex(state === 'red' ? 0xff2244 : 0x220508);
      if (yellow) (yellow.material as THREE.MeshBasicMaterial).color.setHex(state === 'yellow' ? 0xffbb00 : 0x2b1e03);
      if (green) (green.material as THREE.MeshBasicMaterial).color.setHex(state === 'green' ? 0x00ff88 : 0x042813);
    };

    if (isNSGreen) {
      setSignal('N', 'green');
      setSignal('S', 'green');
    } else if (isNSYellow) {
      setSignal('N', 'yellow');
      setSignal('S', 'yellow');
    } else {
      setSignal('N', 'red');
      setSignal('S', 'red');
    }

    if (isEWGreen) {
      setSignal('E', 'green');
      setSignal('W', 'green');
    } else if (isEWYellow) {
      setSignal('E', 'yellow');
      setSignal('W', 'yellow');
    } else {
      setSignal('E', 'red');
      setSignal('W', 'red');
    }
  }, [currentPhase, tlsState]);

  // Update Dynamic Vehicles
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    const activeSet = new Set<string>();

    vehicles.forEach((v) => {
      activeSet.add(v.id);
      let group = vehicleMeshesRef.current.get(v.id);

      // Convert SUMO coordinate system (intersection center is around (100, 100))
      // Offset relative to center (100, 100)
      const worldX = (v.x - 100) * 1.5;
      const worldZ = -(v.y - 100) * 1.5;

      if (!group) {
        group = new THREE.Group();

        // Car Body
        const isEmergency = v.isEmergency || v.id.includes('EMERGENCY');
        const bodyGeo = new THREE.BoxGeometry(3.2, 1.8, 6.0);
        const carColor = isEmergency
          ? 0xff1744
          : v.origin === 'N'
          ? 0x38bdf8
          : v.origin === 'S'
          ? 0x10b981
          : v.origin === 'E'
          ? 0xa855f7
          : 0xf59e0b;

        const bodyMat = new THREE.MeshStandardMaterial({
          color: carColor,
          roughness: 0.3,
          metalness: 0.7,
        });
        const carMesh = new THREE.Mesh(bodyGeo, bodyMat);
        carMesh.position.y = 1.0;
        carMesh.castShadow = true;
        group.add(carMesh);

        // Cabin / Glass
        const cabinGeo = new THREE.BoxGeometry(2.8, 1.3, 3.2);
        const cabinMat = new THREE.MeshStandardMaterial({ color: 0x050914, roughness: 0.1, metalness: 0.9 });
        const cabin = new THREE.Mesh(cabinGeo, cabinMat);
        cabin.position.set(0, 2.1, -0.4);
        group.add(cabin);

        // Headlights (Beams)
        const hlGeo = new THREE.BoxGeometry(0.8, 0.4, 0.2);
        const hlMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
        const hlL = new THREE.Mesh(hlGeo, hlMat);
        hlL.position.set(-1.0, 1.0, -3.0);
        const hlR = new THREE.Mesh(hlGeo, hlMat);
        hlR.position.set(1.0, 1.0, -3.0);
        group.add(hlL);
        group.add(hlR);

        // Taillights
        const tlGeo = new THREE.BoxGeometry(0.8, 0.4, 0.2);
        const tlMat = new THREE.MeshBasicMaterial({ color: 0xff1e28 });
        const tlL = new THREE.Mesh(tlGeo, tlMat);
        tlL.position.set(-1.0, 1.0, 3.0);
        const tlR = new THREE.Mesh(tlGeo, tlMat);
        tlR.position.set(1.0, 1.0, 3.0);
        group.add(tlL);
        group.add(tlR);

        // Emergency Flashing Beacon
        if (isEmergency) {
          const beaconGeo = new THREE.CylinderGeometry(0.5, 0.5, 0.6);
          const beaconMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff });
          const beacon = new THREE.Mesh(beaconGeo, beaconMat);
          beacon.position.set(0, 3.0, -0.4);
          group.add(beacon);

          const sirenLight = new THREE.PointLight(0xff1744, 3, 20);
          sirenLight.position.set(0, 4.0, -0.4);
          group.add(sirenLight);
        }

        scene.add(group);
        vehicleMeshesRef.current.set(v.id, group);
      }

      // Smooth Position Interpolation
      group.position.x += (worldX - group.position.x) * 0.45;
      group.position.z += (worldZ - group.position.z) * 0.45;

      // SUMO Angle: 0 is North (towards +y), 90 is East (+x), 180 is South (-y), 270 is West (-x)
      // Three.js rotation around Y-axis
      const rad = THREE.MathUtils.degToRad(-v.angle + 180);
      group.rotation.y = rad;
    });

    // Cleanup departed vehicles
    vehicleMeshesRef.current.forEach((mesh, id) => {
      if (!activeSet.has(id)) {
        scene.remove(mesh);
        vehicleMeshesRef.current.delete(id);
      }
    });
  }, [vehicles]);

  return (
    <div className="relative w-full h-[540px] rounded-2xl overflow-hidden border border-slate-700/50 shadow-2xl bg-[#060914]">
      <div ref={mountRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
      
      {/* 3D Viewport HUD Overlay */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-3 bg-slate-900/80 backdrop-blur-md px-3.5 py-1.5 rounded-xl border border-cyan-500/20 shadow-lg">
        <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse"></span>
        <span className="text-xs font-mono font-bold tracking-wider text-cyan-300">WEBGL 3D INTERSECTION RADAR</span>
        <span className="text-[11px] text-slate-400 border-l border-slate-700 pl-2">ACTIVE: {vehicles.length} VEH</span>
      </div>

      <div className="absolute bottom-4 left-4 z-10 flex items-center gap-2 bg-slate-900/70 backdrop-blur-sm px-3 py-1 rounded-lg border border-slate-800 text-[11px] text-slate-400 font-mono">
        <span>PERSPECTIVE: ORTHO-ISOMETRIC</span>
        <span>•</span>
        <span>DRIVE RIGHT</span>
      </div>
    </div>
  );
};
