/**
 * Render a True 3D Interactive WebGL Window using Three.js
 * @param {HTMLElement} container The DOM element to render into
 * @param {number} width Width in mm
 * @param {number} height Height in mm
 * @param {string} category Typology category (sliding, casement, fixed, etc.)
 * @param {boolean} hasMesh Whether to render insect mesh
 */
function renderCadWindow(container, width, height, category, hasMesh = false) {
    if (!width || !height || width <= 0 || height <= 0) {
        container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;background:#f8f9fa;color:#888;font-size:12px;font-weight:bold;">Valid dimensions required</div>';
        return;
    }

    // Clean up previous 3D instance if it exists
    if (container._cleanup3D) container._cleanup3D();

    // Clear previous render
    container.innerHTML = '';
    
    // Add overlay hint
    const hint = document.createElement('div');
    hint.innerHTML = '<span style="background:rgba(0,0,0,0.5);color:white;padding:4px 8px;border-radius:4px;font-size:10px;font-weight:bold;pointer-events:none;">Click & Drag to Rotate 3D</span>';
    hint.style.position = 'absolute';
    hint.style.top = '10px';
    hint.style.right = '10px';
    hint.style.zIndex = '10';
    container.style.position = 'relative';
    container.appendChild(hint);

    // Three.js Setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#fdfdfd');
    
    // Add a subtle grid to the floor
    const maxDim = Math.max(width, height);
    const gridHelper = new THREE.GridHelper(maxDim * 3, 30, '#e8eaed', '#e8eaed');
    gridHelper.position.y = -height/2 - 100;
    scene.add(gridHelper);

    const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 1, 10000);
    
    // Position camera dynamically based on window size
    camera.position.z = maxDim * 1.8;
    camera.position.x = maxDim * 0.5;
    camera.position.y = maxDim * 0.5;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(maxDim, maxDim, maxDim);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 1024;
    dirLight.shadow.mapSize.height = 1024;
    scene.add(dirLight);
    
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
    fillLight.position.set(-maxDim, 0, maxDim);
    scene.add(fillLight);

    // Materials
    const frameMaterial = new THREE.MeshStandardMaterial({ 
        color: '#3c4043', 
        roughness: 0.4,
        metalness: 0.1
    });
    
    const glassMaterial = new THREE.MeshPhysicalMaterial({
        color: '#cae8ff',
        metalness: 0.1,
        roughness: 0.05,
        transmission: 0.8, // glass-like transparency
        thickness: 5,
        transparent: true,
        opacity: 0.6
    });

    const meshMaterial = new THREE.MeshStandardMaterial({
        color: '#5f6368',
        roughness: 0.8,
        wireframe: true,
        transparent: true,
        opacity: 0.5
    });

    // We build the window centered around 0,0,0
    const wGroup = new THREE.Group();
    
    // Proportions
    const frameDepth = Math.max(50, maxDim * 0.06);
    const frameThick = Math.max(40, maxDim * 0.05);
    const sashDepth = frameDepth * 0.8;
    const sashThick = frameThick * 0.8;

    // Helper: create a rectangular hollow frame
    function createFrame(fw, fh, fThick, fDepth, material) {
        const group = new THREE.Group();
        // Top
        const top = new THREE.Mesh(new THREE.BoxGeometry(fw, fThick, fDepth), material);
        top.position.set(0, fh/2 - fThick/2, 0);
        top.castShadow = true;
        top.receiveShadow = true;
        group.add(top);
        // Bottom
        const bot = new THREE.Mesh(new THREE.BoxGeometry(fw, fThick, fDepth), material);
        bot.position.set(0, -fh/2 + fThick/2, 0);
        bot.castShadow = true;
        bot.receiveShadow = true;
        group.add(bot);
        // Left
        const left = new THREE.Mesh(new THREE.BoxGeometry(fThick, fh - fThick*2, fDepth), material);
        left.position.set(-fw/2 + fThick/2, 0, 0);
        left.castShadow = true;
        left.receiveShadow = true;
        group.add(left);
        // Right
        const right = new THREE.Mesh(new THREE.BoxGeometry(fThick, fh - fThick*2, fDepth), material);
        right.position.set(fw/2 - fThick/2, 0, 0);
        right.castShadow = true;
        right.receiveShadow = true;
        group.add(right);
        return group;
    }

    // Outer Frame
    wGroup.add(createFrame(width, height, frameThick, frameDepth, frameMaterial));

    const innerW = width - frameThick*2;
    const innerH = height - frameThick*2;

    if (category === 'sliding') {
        const midW = innerW / 2 + sashThick/2;
        
        // Left Sash (Back track)
        const sash1 = createFrame(midW, innerH, sashThick, sashDepth, frameMaterial);
        sash1.position.set(-innerW/2 + midW/2, 0, -sashDepth/2);
        wGroup.add(sash1);
        
        const glass1 = new THREE.Mesh(new THREE.BoxGeometry(midW - sashThick*2, innerH - sashThick*2, 4), glassMaterial);
        glass1.position.set(-innerW/2 + midW/2, 0, -sashDepth/2);
        wGroup.add(glass1);
        
        if (hasMesh) {
            const m = new THREE.Mesh(new THREE.PlaneGeometry(midW - sashThick*2, innerH - sashThick*2), meshMaterial);
            m.position.set(-innerW/2 + midW/2, 0, -sashDepth/2 + 3);
            wGroup.add(m);
        }

        // Right Sash (Front track)
        const sash2 = createFrame(midW, innerH, sashThick, sashDepth, frameMaterial);
        sash2.position.set(innerW/2 - midW/2, 0, sashDepth/2);
        wGroup.add(sash2);
        
        const glass2 = new THREE.Mesh(new THREE.BoxGeometry(midW - sashThick*2, innerH - sashThick*2, 4), glassMaterial);
        glass2.position.set(innerW/2 - midW/2, 0, sashDepth/2);
        wGroup.add(glass2);
        
    } else if (category === 'casement' || category === 'awning') {
        const sash = createFrame(innerW, innerH, sashThick, sashDepth, frameMaterial);
        // Slightly open it for casement effect
        sash.position.set(-innerW/2, 0, sashDepth/2); 
        
        const sashGroup = new THREE.Group();
        sash.position.set(innerW/2, 0, 0); // origin to hinge
        
        const glass = new THREE.Mesh(new THREE.BoxGeometry(innerW - sashThick*2, innerH - sashThick*2, 4), glassMaterial);
        glass.position.set(innerW/2, 0, 0);
        
        sashGroup.add(sash);
        sashGroup.add(glass);
        
        if (hasMesh) {
            const m = new THREE.Mesh(new THREE.PlaneGeometry(innerW, innerH), meshMaterial);
            m.position.set(0, 0, -sashDepth/2);
            wGroup.add(m); // Mesh on fixed frame
        }

        sashGroup.position.set(-innerW/2, 0, 0);
        sashGroup.rotation.y = Math.PI / 8; // Open 22.5 degrees
        wGroup.add(sashGroup);

    } else if (category === 'door') {
        const sash = createFrame(innerW, innerH, sashThick*1.5, sashDepth, frameMaterial);
        const glass = new THREE.Mesh(new THREE.BoxGeometry(innerW - sashThick*3, innerH - sashThick*3, 4), glassMaterial);
        
        const sashGroup = new THREE.Group();
        sash.position.set(innerW/2, 0, 0);
        glass.position.set(innerW/2, 0, 0);
        
        // Door Handle
        const handle = new THREE.Mesh(new THREE.BoxGeometry(frameThick*0.4, frameThick*3, frameDepth*1.5), new THREE.MeshStandardMaterial({color: '#b0bec5', metalness: 0.8, roughness: 0.2}));
        handle.position.set(innerW - frameThick, 0, 0);
        
        sashGroup.add(sash);
        sashGroup.add(glass);
        sashGroup.add(handle);
        
        sashGroup.position.set(-innerW/2, 0, 0);
        sashGroup.rotation.y = Math.PI / 6; // Open 30 degrees
        wGroup.add(sashGroup);
        
        if (hasMesh) {
            const m = new THREE.Mesh(new THREE.PlaneGeometry(innerW, innerH), meshMaterial);
            m.position.set(0, 0, -sashDepth/2);
            wGroup.add(m);
        }

    } else {
        // Fixed
        const glass = new THREE.Mesh(new THREE.BoxGeometry(innerW, innerH, 4), glassMaterial);
        wGroup.add(glass);
        if (hasMesh) {
            const m = new THREE.Mesh(new THREE.PlaneGeometry(innerW, innerH), meshMaterial);
            m.position.set(0, 0, 3);
            wGroup.add(m);
        }
    }

    // --- ADD 3D DIMENSION LINES ---
    function addDimensionLine(startPoint, endPoint, text, offsetDir) {
        const dir = new THREE.Vector3().subVectors(endPoint, startPoint);
        const length = dir.length();
        dir.normalize();
        const mid = new THREE.Vector3().addVectors(startPoint, endPoint).multiplyScalar(0.5);
        
        const thickness = Math.max(1.5, maxDim * 0.004);
        const lineGeo = new THREE.CylinderGeometry(thickness, thickness, length, 8);
        const lineMat = new THREE.MeshBasicMaterial({ color: '#202124' });
        const lineMesh = new THREE.Mesh(lineGeo, lineMat);
        
        const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
        lineMesh.quaternion.copy(quaternion);
        lineMesh.position.copy(mid);
        wGroup.add(lineMesh);
        
        const tickLength = maxDim * 0.06;
        const tickGeo = new THREE.CylinderGeometry(thickness*1.5, thickness*1.5, tickLength, 8);
        
        const t1 = new THREE.Mesh(tickGeo, lineMat);
        t1.position.copy(startPoint);
        t1.rotation.z = Math.PI / 4;
        wGroup.add(t1);
        
        const t2 = new THREE.Mesh(tickGeo, lineMat);
        t2.position.copy(endPoint);
        t2.rotation.z = Math.PI / 4;
        wGroup.add(t2);

        // Extension lines connecting to the frame
        const extLength = maxDim * 0.08;
        const extGeo = new THREE.CylinderGeometry(thickness*0.5, thickness*0.5, extLength, 8);
        const extMat = new THREE.MeshBasicMaterial({ color: '#9aa0a6' });
        
        const e1 = new THREE.Mesh(extGeo, extMat);
        e1.position.copy(startPoint).add(offsetDir.clone().multiplyScalar(-extLength/2));
        e1.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0), offsetDir));
        wGroup.add(e1);

        const e2 = new THREE.Mesh(extGeo, extMat);
        e2.position.copy(endPoint).add(offsetDir.clone().multiplyScalar(-extLength/2));
        e2.quaternion.copy(e1.quaternion);
        wGroup.add(e2);

        // Text Sprite
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 128;
        const ctx = canvas.getContext('2d');
        ctx.font = "Bold 65px 'Inter', Arial, sans-serif";
        ctx.fillStyle = "#202124";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(text, 256, 64);
        
        const tex = new THREE.CanvasTexture(canvas);
        const spriteMat = new THREE.SpriteMaterial({ map: tex, depthTest: false });
        const sprite = new THREE.Sprite(spriteMat);
        
        // Offset text slightly above the line
        sprite.position.copy(mid).add(offsetDir.clone().multiplyScalar(maxDim * 0.05));
        const spriteScale = maxDim * 0.45;
        sprite.scale.set(spriteScale, spriteScale * 0.25, 1);
        wGroup.add(sprite);
    }
    
    // Width Dimension (Top)
    const yOffset = height/2 + maxDim * 0.08;
    addDimensionLine(
        new THREE.Vector3(-width/2, yOffset, 0),
        new THREE.Vector3(width/2, yOffset, 0),
        width + " mm",
        new THREE.Vector3(0, 1, 0)
    );
    
    // Height Dimension (Left)
    const xOffset = -width/2 - maxDim * 0.08;
    addDimensionLine(
        new THREE.Vector3(xOffset, -height/2, 0),
        new THREE.Vector3(xOffset, height/2, 0),
        height + " mm",
        new THREE.Vector3(-1, 0, 0)
    );

    scene.add(wGroup);

    // Animation loop
    let animationId;
    function animate() {
        animationId = requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();

    // Handle Resize
    const resizeObserver = new ResizeObserver(() => {
        if (!container || !renderer) return;
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    });
    resizeObserver.observe(container);
    
    // Cleanup function if element is replaced
    container._cleanup3D = function() {
        cancelAnimationFrame(animationId);
        resizeObserver.disconnect();
        if (renderer.domElement) container.removeChild(renderer.domElement);
        renderer.dispose();
    };
}

function initCadContainers() {
    document.querySelectorAll('.cad-container').forEach(el => {
        if (el._cleanup3D) el._cleanup3D(); // Clean up old renderer
        const w = parseFloat(el.getAttribute('data-width'));
        const h = parseFloat(el.getAttribute('data-height'));
        const cat = el.getAttribute('data-category');
        const hasMesh = el.getAttribute('data-has-mesh') === 'true';
        renderCadWindow(el, w, h, cat, hasMesh);
    });
}

document.addEventListener('DOMContentLoaded', initCadContainers);
